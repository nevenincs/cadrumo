"""Registry validation of each revision's declared form layout.

The integrity rules live with the family in the domain; this module enrols them
in the per-revision dispatch so a layout that omits, duplicates or invents a
casilla, misaddresses a binding or row set, or is stale against its revision
fails compilation before it can be published.
"""

from __future__ import annotations

from cadrumo.domain.calculations.registry.form_layout_integrity import form_layout_failures
from cadrumo.domain.calculations.registry.schema import ModeloRevision

__all__ = ["validate_form_layout_section"]


def validate_form_layout_section(*, prefix: str, revision: ModeloRevision) -> list[str]:
    """Return one failure line per departure of the revision's layout from the revision."""
    return [f"{prefix}: {failure}" for failure in form_layout_failures(revision)]
