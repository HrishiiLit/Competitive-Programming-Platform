from typing import Optional


def normalize_output(text: Optional[str] = "") -> str:
    """Normalize text comparator rules (docs/judging.md section 4):
    1. Normalize CRLF to LF.
    2. Strip trailing whitespace from every individual line.
    3. Strip trailing blank lines at the end of the text.
    4. Preserve leading and internal whitespace on non-blank lines.
    """
    if not text:
        return ""
    # Normalize line endings
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # Strip trailing whitespace on each line
    normalized_lines = [line.rstrip() for line in lines]
    # Remove trailing empty lines
    while normalized_lines and normalized_lines[-1] == "":
        normalized_lines.pop()
    return "\n".join(normalized_lines)


def compare_outputs(actual: Optional[str], expected: Optional[str]) -> bool:
    """Deterministic comparison between participant output and expected output."""
    return normalize_output(actual) == normalize_output(expected)
