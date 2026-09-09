"""Every shipped export field must agree with the official row it derives from.

The registry is generated from published AEAT record designs, and until now
nothing compared the two. Reproducibility was gated -- a committed tree must
equal a fresh render -- but reproducibility only proves the generator is stable,
not that it read the design correctly. A column the generator never consulted
produced a stable, reproducible, wrong answer across a fifth of the corpus, and
every gate stayed green while it did.

This is the missing instrument. The join it needs already exists: each generated
tree ships a provenance manifest whose entries carry the official ``parser_field``
beside the ``field`` derived from it, so the comparison is a read rather than a
reconstruction. No coordinate matching is involved and none is permitted: offsets
restart per page, and a coordinate join on this corpus produced a confident number
that was pure noise.

The axes checked here are the ones the design STATES. Where the design is silent
the comparison says nothing, because inventing a verdict from silence is the
failure this file exists to catch.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The design's own type vocabulary, from its type note: "Num: numerico sin
#: signo", "N: numerico con signo". A token outside this set is not a type the
#: design states, and this gate reports rather than guesses.
_SIGNED_TYPE = "N"
_UNSIGNED_TYPE = "Num"


class _Derivation(NamedTuple):
    """One official row paired with the shipped field derived from it."""

    subject: str
    field_id: str
    aeat_type: str | None
    derivation_code: str | None
    signed: bool


def _shipped_derivations() -> Iterator[_Derivation]:
    root = bundled_path("registry", "aeat", "modelos")
    for manifest_path in sorted(root.glob("*/revisions/*/export/_generation.provenance.json")):
        parts = manifest_path.parts
        subject = f"{parts[-5]}/{parts[-3]}"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("field_derivations") or ():
            parser_field = entry.get("parser_field") or {}
            field = entry.get("field") or {}
            yield _Derivation(
                subject=subject,
                field_id=str(field.get("id") or entry.get("export_record_id") or "<unnamed>"),
                aeat_type=parser_field.get("aeat_type"),
                derivation_code=entry.get("derivation_code"),
                signed=bool(field.get("signed")),
            )


def _sign_disagreements(derivations: Iterator[_Derivation]) -> list[str]:
    """Return one line per field whose shipped sign contradicts its official type."""
    disagreements: list[str] = []
    for derivation in derivations:
        if derivation.aeat_type == _SIGNED_TYPE and not derivation.signed:
            disagreements.append(
                f"{derivation.subject} {derivation.field_id}: design says '{_SIGNED_TYPE}' "
                f"(numerico con signo), shipped declares unsigned "
                f"[{derivation.derivation_code}]",
            )
        elif derivation.aeat_type == _UNSIGNED_TYPE and derivation.signed:
            disagreements.append(
                f"{derivation.subject} {derivation.field_id}: design says '{_UNSIGNED_TYPE}' "
                f"(numerico sin signo), shipped declares signed "
                f"[{derivation.derivation_code}]",
            )
    return disagreements


def test_the_corpus_carries_derivations_to_compare() -> None:
    """A gate that silently compares nothing is worse than no gate at all."""
    derivations = list(_shipped_derivations())

    assert len(derivations) > 10_000, f"expected the full generated corpus, found {len(derivations)}"
    assert any(item.aeat_type == _SIGNED_TYPE for item in derivations), "no signed rows to compare"


def test_no_shipped_field_contradicts_the_official_type_column() -> None:
    """The published design and the implementation must not diverge on sign.

    This is the axis that diverged unnoticed: the generator wrote a constant
    where the design stated a fact, and 2,117 fields shipped contradicting their
    own source. Reproducibility could not see it because the wrong answer was
    perfectly stable.
    """
    disagreements = _sign_disagreements(_shipped_derivations())

    assert not disagreements, (
        f"{len(disagreements)} shipped field(s) contradict the official type column:\n"
        + "\n".join(disagreements[:40])
    )


def test_a_planted_divergence_is_detected() -> None:
    """The comparison has teeth: a contradicting pair is reported, not tolerated.

    Planted in the comparison's own input rather than in the shipped corpus, so
    the proof neither mutates the working tree nor depends on a defect surviving
    in committed data.
    """
    planted = iter(
        (
            _Derivation("999/2026", "planted-signed", _SIGNED_TYPE, "numeric-decimal-v1", signed=False),
            _Derivation("999/2026", "planted-unsigned", _UNSIGNED_TYPE, "numeric-decimal-v1", signed=True),
            _Derivation("999/2026", "agreeing", _SIGNED_TYPE, "numeric-decimal-v1", signed=True),
        ),
    )

    disagreements = _sign_disagreements(planted)

    assert len(disagreements) == 2
    assert "planted-signed" in disagreements[0]
    assert "planted-unsigned" in disagreements[1]
