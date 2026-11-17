"""Text input normalization and field wording for ledger forms."""

from collections.abc import Mapping

from ....core.i18n.render import tr


def blank_to_none(value: str) -> str | None:
    """A typed value, or ``None`` when the operator left it blank."""
    stripped = value.strip()
    return stripped or None


def field_label(name: str, table: Mapping[str, str]) -> str:
    """Render a field using its form's locale table."""
    return tr(table[name])
