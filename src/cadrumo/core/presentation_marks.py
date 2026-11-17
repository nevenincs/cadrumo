"""Untranslated flag tokens shared by text presentations."""


def flag_mark(value: bool) -> str:
    """Return ``Y`` for a true flag and ``-`` otherwise."""
    return "Y" if value else "-"
