"""Screen: a field whose WIRE SHAPE changes between revisions of one modelo.

The registry is regenerated per revision from a separately published design, and
nothing compares a field's emitted shape in one revision against the same field
in the next. A shape that changes without a corresponding change in the official
designs is either a real regulatory change nobody recorded, or the generator
reading two designs differently -- and the second is how a fifth of the corpus
came to declare unsigned the slots its designs type as signed.

What this screen does NOT do is assert correctness from stability. On this corpus
agreement is mostly the ABSENCE of evidence: a layout copied forward unchanged
shows perfect agreement while tracking no regulatory change at all, and the sign
axis is stable across nearly every identity precisely because almost nothing
exercised it. A screen that read agreement as a pass would have reported the
corpus healthy on the very axis that was broken. So a change is reported as a
SUSPECT requiring an explanation, and agreement is reported as nothing.

The identity joined on is the export field id, which carries no revision token
and so survives across revisions of one modelo. Offsets are deliberately not
used: designs restart them per page, and a coordinate join on this corpus
produced a confident number that was pure noise.

The screen exits 0 whatever it finds. It reports; it does not gate.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Final

from cadrumo.core.resources.bundled_data import bundled_path

#: A field id is comparable across revisions only when it NAMES the slot. One
#: spelling does - `modelo-390-page-01-declared-representante-...` carries no
#: revision token and means the same thing in every revision. The other is
#: positional - `m151-2015.did.f006` - and its ordinal is assigned per render,
#: so `f006` in one revision is not the same slot as `f006` in the next.
#:
#: Stripping the epoch to make the positional spelling "join" was tried and
#: rejected: it lifted the compared population from 1,628 to 5,223 and produced
#: 745 transitions that are overwhelmingly field renumbering, a text field of 34
#: bytes "becoming" one of 1. That is a coordinate join wearing an identity's
#: clothes, and this corpus has already produced one confident number that way
#: which turned out to be pure noise.
#:
#: So only naming identities are compared, and the coverage is REPORTED rather
#: than assumed, because a screen reporting no transitions across a population it
#: never examined is indistinguishable from a clean corpus.
_POSITIONAL_IDENTITY: Final[re.Pattern[str]] = re.compile(r"^m\d{3}-[0-9]")


def identity_is_comparable_across_revisions(identity: str) -> bool:
    """Whether this field id names its slot rather than numbering it."""
    return not _POSITIONAL_IDENTITY.match(identity)


#: The emitted facts that together are a field's wire shape. A change in any of
#: them changes how a value reaches a filing, which is why they travel as one
#: tuple rather than being compared field by field.
_WIRE_FACTS: Final[tuple[str, ...]] = ("data_type", "length", "signed", "decimals")


@dataclass(frozen=True, slots=True)
class WireShapeTransition:
    """One field identity whose wire shape differs between two revisions."""

    modelo: str
    export_field_id: str
    earlier_revision: str
    later_revision: str
    earlier_shape: tuple[object, ...]
    later_shape: tuple[object, ...]
    earlier_aeat_type: str | None
    later_aeat_type: str | None

    @property
    def official_type_changed(self) -> bool:
        """Whether the official type column also moved.

        A shape change the DESIGN accounts for is a different thing from one it
        does not. Both are reported; only the second is unexplained by its own
        source.
        """
        return self.earlier_aeat_type != self.later_aeat_type


def _revision_shapes(modelo_root: Path) -> dict[str, dict[str, tuple[tuple[object, ...], str | None]]]:
    shapes: dict[str, dict[str, tuple[tuple[object, ...], str | None]]] = {}
    for manifest_path in sorted(modelo_root.glob("revisions/*/export/_generation.provenance.json")):
        revision = manifest_path.parts[-3]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_identity: dict[str, tuple[tuple[object, ...], str | None]] = {}
        for entry in manifest.get("field_derivations") or ():
            field = entry.get("field") or {}
            identity = field.get("id")
            if not isinstance(identity, str):
                continue
            shape = tuple(field.get(name) for name in _WIRE_FACTS)
            if not identity_is_comparable_across_revisions(identity):
                continue
            by_identity[identity] = (shape, (entry.get("parser_field") or {}).get("aeat_type"))
        shapes[revision] = by_identity
    return shapes


def cross_revision_wire_shape_transitions(modelos_root: Path | None = None) -> Iterator[WireShapeTransition]:
    """Yield every field identity whose wire shape moves between adjacent revisions.

    The root is a parameter so the comparison can be proven against a planted
    defect in an isolated tree. A detector shown to work only on the corpus it
    reports clean has not been shown to work.
    """
    modelos_root = modelos_root if modelos_root is not None else bundled_path("registry", "aeat", "modelos")
    for modelo_root in sorted(modelos_root.iterdir()):
        if not modelo_root.is_dir():
            continue
        shapes = _revision_shapes(modelo_root)
        revisions = sorted(shapes)
        for earlier, later in zip(revisions, revisions[1:], strict=False):
            for identity, (earlier_shape, earlier_type) in shapes[earlier].items():
                if identity not in shapes[later]:
                    continue
                later_shape, later_type = shapes[later][identity]
                if earlier_shape == later_shape:
                    continue
                yield WireShapeTransition(
                    modelo=modelo_root.name,
                    export_field_id=identity,
                    earlier_revision=earlier,
                    later_revision=later,
                    earlier_shape=earlier_shape,
                    later_shape=later_shape,
                    earlier_aeat_type=earlier_type,
                    later_aeat_type=later_type,
                )


def screen_authority(_authority: object = None, _modelo_ids: Sequence[str] = ()) -> Sequence[WireShapeTransition]:
    """Entry point matching the screens register's calling convention."""
    return tuple(cross_revision_wire_shape_transitions())


def main() -> int:
    """Report every wire-shape transition, and say what the report does not mean."""
    transitions = tuple(cross_revision_wire_shape_transitions())
    unexplained = [item for item in transitions if not item.official_type_changed]
    for item in transitions:
        marker = "design moved" if item.official_type_changed else "DESIGN SILENT"
        print(
            f"{item.modelo} {item.earlier_revision} -> {item.later_revision} "
            f"{item.export_field_id}: {item.earlier_shape} -> {item.later_shape} [{marker}]",
        )
    print(
        f"\n{len(transitions)} wire-shape transition(s), of which {len(unexplained)} carry no change "
        f"in the official type column. Agreement elsewhere is NOT evidence of correctness: an "
        f"unchanged layout agrees with itself.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
