"""Screen: fields declared optional because the design was SILENT, not because it said so.

A shipped export field carries `required` as a boolean, and the derivation sets
it true only where the official validation cell reads exactly "obligatorio".
Everything else becomes false: a cell that genuinely says the field is optional,
a cell that is blank, and a cell carrying a token the matcher does not
recognise. Three distinct official facts, one emitted value.

Why this matters is not tidiness. The fixed-width codec REFUSES to render an
absent value for a field declared required, so an omitted mandatory figure
cannot reach a filing as a zero. That guard is real and it is correct. It fires
only when `required` is true, so every field that says "optional" because its
design said nothing has silently disarmed the one check that would have caught a
missing mandatory figure.

This screen does not change what is emitted. It measures how much of the shipped
`required = false` population is a derivation from an official statement and how
much is a fabrication standing in for silence, using the validation cell that
every generated manifest already carries beside the field it produced.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path


class RequirednessBasis(StrEnum):
    """What the official validation cell actually said about a field."""

    STATED_MANDATORY = "stated_mandatory"
    """The cell reads obligatorio, and the emitted `required = true` derives from it."""

    STATED_OTHERWISE = "stated_otherwise"
    """The cell says something else. The field is optional on the design's word."""

    DESIGN_SILENT = "design_silent"
    """The cell is blank. `required = false` here is a fabrication, not a derivation."""


#: The one token the derivation recognises, as it recognises it.
_MANDATORY_TOKEN = "obligatorio"


@dataclass(frozen=True, slots=True)
class RequirednessObservation:
    """One shipped field, its emitted required flag, and what the design said."""

    modelo: str
    revision: str
    export_field_id: str
    emitted_required: bool
    basis: RequirednessBasis

    @property
    def is_fabricated(self) -> bool:
        """Whether the emitted value stands in for a statement the design never made."""
        return self.basis is RequirednessBasis.DESIGN_SILENT


def classify_requiredness(validation: str | None) -> RequirednessBasis:
    """Classify the official validation cell into the state it actually expresses."""
    if validation is None or not validation.strip():
        return RequirednessBasis.DESIGN_SILENT
    if validation.strip().casefold() == _MANDATORY_TOKEN:
        return RequirednessBasis.STATED_MANDATORY
    return RequirednessBasis.STATED_OTHERWISE


def shipped_requiredness(modelos_root: Path | None = None) -> Iterator[RequirednessObservation]:
    """Yield one observation per generated field, from the manifests already shipped."""
    root = modelos_root if modelos_root is not None else bundled_path("registry", "aeat", "modelos")
    for manifest_path in sorted(root.glob("*/revisions/*/export/_generation.provenance.json")):
        parts = manifest_path.parts
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("field_derivations") or ():
            field = entry.get("field") or {}
            identity = field.get("id")
            if not isinstance(identity, str):
                continue
            yield RequirednessObservation(
                modelo=parts[-5],
                revision=parts[-3],
                export_field_id=identity,
                emitted_required=bool(field.get("required")),
                basis=classify_requiredness((entry.get("parser_field") or {}).get("validation")),
            )


def screen_authority(_authority: object = None, _modelo_ids: Sequence[str] = ()) -> Sequence[RequirednessObservation]:
    """Entry point matching the screens register's calling convention.

    Returns the whole examined population, flagged, rather than the fabrications
    alone: the ratio is the finding, and a count without its denominator has
    been misread on this codebase before.
    """
    return tuple(shipped_requiredness())


def main() -> int:
    """Report how much of the shipped optional population is derived, and how much is not."""
    observations = tuple(shipped_requiredness())
    fabricated = [item for item in observations if item.is_fabricated]
    stated_optional = [item for item in observations if item.basis is RequirednessBasis.STATED_OTHERWISE]
    mandatory = [item for item in observations if item.basis is RequirednessBasis.STATED_MANDATORY]
    print(f"generated fields examined: {len(observations)}")
    print(f"  design states obligatorio:   {len(mandatory)}")
    print(f"  design states something else: {len(stated_optional)}")
    print(f"  design SILENT:                {len(fabricated)}")
    print(
        "\nEvery silent field ships `required = false`, and the codec's refusal to render an absent\n"
        "REQUIRED value therefore never fires for it. The guard is real; these fields disarm it.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
