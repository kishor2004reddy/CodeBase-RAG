"""
ingestion.parser
----------------
AST-based code parsers for Python and TypeScript.

Usage:
    from ingestion.parser import parse_file
    result = parse_file(source_code, "src/utils.py", Language.PYTHON)
"""

from ingestion.parser.models import Language, ParsedFile
from ingestion.parser.python_parser import parse_python_file
from ingestion.parser.typescript_parser import parse_typescript_file


def parse_file(source_code: str, file_path: str, language: Language) -> ParsedFile:
    """
    Parse a source file using the appropriate language parser.

    Parameters
    ----------
    source_code : str
        The raw file contents.
    file_path : str
        Relative path within the repo.
    language : Language
        Which parser to use.

    Returns
    -------
    ParsedFile
        Extracted symbols and relationships.

    Raises
    ------
    ValueError
        If the language is not supported.
    """
    if language == Language.PYTHON:
        return parse_python_file(source_code, file_path)
    elif language == Language.TYPESCRIPT:
        return parse_typescript_file(source_code, file_path)
    else:
        raise ValueError(f"Unsupported language: {language}")
