"""
ingestion/repo_fetcher.py
-------------------------
Handles getting source code onto disk and discovering parseable files.

Two entry points:
  - clone_repo(github_url)  → clones a GitHub repo (shallow, fast)
  - extract_zip(zip_path)   → extracts an uploaded ZIP

Then:
  - discover_files(root)    → walks the tree, skips junk, returns SourceFiles
"""

import os
import shutil
import uuid
import zipfile
from pathlib import Path

from pydantic import BaseModel

from core.config import settings
from core.logging import get_logger
from ingestion.parser.models import Language

logger = get_logger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────


class SourceFile(BaseModel):
    """A single source file discovered in a repository."""

    absolute_path: str       # full path on disk
    relative_path: str       # path relative to repo root (used everywhere)
    language: Language
    size_bytes: int


# ── Constants ─────────────────────────────────────────────────────────────────

# File extensions → language mapping
EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
}

# Directories to skip during file discovery.
# These are huge, generated, or irrelevant to code understanding.
SKIP_DIRS: set[str] = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "env",
    ".tox",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".eggs",
    "*.egg-info",
}

# Files to skip (exact name matches)
SKIP_FILES: set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "poetry.lock",
}

# Maximum file size to parse (skip huge generated / vendored files)
MAX_FILE_SIZE = 1_000_000  # 1 MB


# ── Clone from GitHub ─────────────────────────────────────────────────────────


def clone_repo(github_url: str) -> Path:
    """
    Shallow-clone a GitHub repository to a temp directory.

    Parameters
    ----------
    github_url : str
        The HTTPS GitHub URL, e.g. "https://github.com/user/repo"

    Returns
    -------
    Path
        The local directory where the repo was cloned.

    Raises
    ------
    ValueError
        If the URL doesn't look like a valid GitHub repo.
    RuntimeError
        If git clone fails.
    """
    # Basic URL validation
    url = github_url.strip().rstrip("/")
    if not url.startswith(("https://github.com/", "http://github.com/")):
        raise ValueError(
            f"Expected a GitHub HTTPS URL, got: {url}"
        )

    # Add .git suffix if missing (GitPython needs it for some URLs)
    clone_url = url if url.endswith(".git") else url + ".git"

    # Generate a unique directory name
    repo_name = url.split("/")[-1].replace(".git", "")
    dest_dir = Path(settings.tmp_repo_dir) / f"{repo_name}_{uuid.uuid4().hex[:8]}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Cloning %s → %s", clone_url, dest_dir)

    try:
        import git
        git.Repo.clone_from(
            clone_url,
            str(dest_dir),
            depth=1,              # shallow clone — only latest commit
            single_branch=True,   # only the default branch
        )
    except git.GitCommandError as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed for {clone_url}: {e}") from e

    logger.info("Clone complete: %s (%d files on disk)", repo_name, _count_files(dest_dir))
    return dest_dir


# ── Extract ZIP ───────────────────────────────────────────────────────────────


def extract_zip(zip_path: str | Path) -> Path:
    """
    Extract an uploaded ZIP file to a temp directory.

    Parameters
    ----------
    zip_path : str | Path
        Path to the uploaded ZIP file on disk.

    Returns
    -------
    Path
        The root directory of the extracted contents.

    Raises
    ------
    ValueError
        If the file is not a valid ZIP.
    """
    zip_path = Path(zip_path)
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"Not a valid ZIP file: {zip_path}")

    dest_dir = Path(settings.tmp_zip_dir) / f"zip_{uuid.uuid4().hex[:8]}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting %s → %s", zip_path.name, dest_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)

    # If the ZIP contained a single top-level directory, step into it.
    # e.g. "my-repo-main/" wrapping everything — we want the contents.
    children = list(dest_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        actual_root = children[0]
        logger.info("ZIP has single root dir: %s", actual_root.name)
        return actual_root

    return dest_dir


# ── File discovery ────────────────────────────────────────────────────────────


def discover_files(root_dir: str | Path) -> list[SourceFile]:
    """
    Walk a directory tree and return all parseable source files.

    Skips:
      - Directories in SKIP_DIRS (node_modules, .git, etc.)
      - Files in SKIP_FILES (lock files)
      - Files larger than MAX_FILE_SIZE
      - Files whose extension isn't in EXTENSION_MAP

    Parameters
    ----------
    root_dir : str | Path
        The repository root to scan.

    Returns
    -------
    list[SourceFile]
        All discovered source files, sorted by relative path.
    """
    root = Path(root_dir).resolve()
    found: list[SourceFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # ── Prune directories we don't want to descend into ──
        # Modifying dirnames in-place tells os.walk to skip them.
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]

        for fname in filenames:
            # Skip known junk files
            if fname in SKIP_FILES:
                continue

            filepath = Path(dirpath) / fname
            ext = filepath.suffix.lower()

            # Only process files with extensions we support
            language = EXTENSION_MAP.get(ext)
            if language is None:
                continue

            # Skip very large files (likely generated / vendored)
            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            if size > MAX_FILE_SIZE:
                logger.debug("Skipping large file (%d bytes): %s", size, fname)
                continue

            if size == 0:
                continue  # empty files have nothing to parse

            relative = str(filepath.relative_to(root)).replace("\\", "/")

            found.append(SourceFile(
                absolute_path=str(filepath),
                relative_path=relative,
                language=language,
                size_bytes=size,
            ))

    found.sort(key=lambda f: f.relative_path)

    logger.info(
        "Discovered %d source files in %s (Python: %d, TypeScript: %d)",
        len(found),
        root.name,
        sum(1 for f in found if f.language == Language.PYTHON),
        sum(1 for f in found if f.language == Language.TYPESCRIPT),
    )
    return found


# ── Cleanup ───────────────────────────────────────────────────────────────────


def cleanup_repo(repo_dir: str | Path) -> None:
    """Remove a cloned / extracted repo directory after ingestion."""
    path = Path(repo_dir)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        logger.info("Cleaned up temp directory: %s", path)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _count_files(directory: Path) -> int:
    """Quick count of all files in a directory (for logging)."""
    return sum(1 for _ in directory.rglob("*") if _.is_file())
