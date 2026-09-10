"""The pipeline-owned ledger of generated-tree dispositions.

A disposition is a source-pinned declaration explaining why a generated tree is
in a state other than "reproduces its inputs and agrees with its design": its
records drift from the inputs, its design refuses to render, or it reproduces
while the inputs contradict the official type column. Each kind carries the fact
that falsifies it, so a row cannot outlive the condition it describes.

The renderer reads the type-column rulings to adjudicate a field's verdict, and
the comparison and publication tools read the rest, so the ledger stands apart
from both rather than inside either.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import rtoml
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "GeneratedTreeRecordDriftDisposition",
    "GeneratedTreeRenderRefusalDisposition",
    "GeneratedTreeTypeColumnContradictionDisposition",
    "disposition_ledger_from_path",
    "record_drift_dispositions",
    "render_refusal_dispositions",
    "type_column_contradiction_dispositions",
    "type_column_rulings_for",
]

_DISPOSITIONS_PATH = Path(__file__).with_name("generated_tree_dispositions.toml")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GeneratedTreeRecordDriftDisposition(_StrictModel):
    """One source-bound declaration that a tree's records differ from its inputs.

    A row says the shipped records and the current inputs disagree. It does NOT
    say which side is right, and the two directions demand opposite actions, so
    ``remedy`` states it and nothing infers it.
    """

    kind: Literal["record_drift"]
    modelo: str = Field(pattern=r"^[0-9]{3}$")
    revision: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    remedy: Literal["republish", "repair_inputs"]
    """Which side is wrong, and therefore what fixes the difference.

    ``republish`` - the INPUTS are right and the shipped bytes are stale, so
    regenerating is the fix. The sign corrections are this: the generator now
    reads the official type column and the committed trees predate it.

    ``repair_inputs`` - the SHIPPED bytes are right and the inputs are wrong, so
    regenerating would ship the defect. Modelo 347 is the live case: its Tipo-2
    record must repeat per declarado, a fresh render does not reproduce that, and
    republishing would emit ONE record and drop every counterparty after the
    first - turning a complete informative return into one naming a single third
    party.

    Declared rather than derived, because both directions produce identical
    record drift and a reader cannot tell them apart from the comparison. A
    republication path that treated every row as permission would have shipped
    that truncation.
    """
    differing_records: int = Field(gt=0)
    """How many records this row explains, checked against the live comparison.

    Without it a row asserts only THAT the tree differs, never that the
    difference is the one it describes. A revision drifting for reason A and
    later also for reason B stayed green under the row written for A, so the
    row's scope grew while its wording did not. Modelo 390 proved it: retiring
    its rows uncovered eighty fields they had been silently covering, and the
    only reason anyone found out is that the rows were removed.

    An attestation whose scope can outgrow its wording is worse than one that
    fails, because nothing surfaces it. This is the number that fails.
    """
    reason: str = Field(min_length=1)
    reconsideration_condition: str = Field(min_length=1)

    @property
    def subject(self) -> str:
        """Return the canonical modelo/revision disposition identity."""
        return f"{self.modelo}/{self.revision}"


class GeneratedTreeTypeColumnContradictionDisposition(_StrictModel):
    """One source-bound declaration that a REPRODUCING tree still contradicts its design.

    Distinct from record drift, and the distinction is the reason this class
    exists. Drift means the shipped bytes and the current inputs disagree, so
    one of them is stale. Here they AGREE: the tree reproduces byte for byte,
    and the inputs themselves declare a representation the official type column
    contradicts. Regenerating changes nothing, so a drift row would be dormant
    the moment it was written - and the reproduction gate now fails a dormant
    drift row, correctly.

    Modelo 390 filing year 2025 is the live case. Its "Nota 2: estas casillas
    deben estar rellenas a 0" slots are declared unsigned while the design's
    type column says N. The note mandates the VALUE zero and states nothing
    about sign, so unsigned is a claim the document does not make. It cannot
    simply be corrected either: a signed amount renders through the ``money``
    wire type, which carries no value domain, so declaring the field signed
    would silently drop the mandated zero. The export schema cannot hold a
    closed domain and a sign at once, and until it can, neither reading is
    fully derivable.

    ``field_count`` keeps the row honest. It asserts how large the contradiction
    is, so a row written for eighty fields cannot quietly go on explaining eight
    hundred, and a row whose population has been repaired away fails rather than
    standing as a permanent exemption.
    """

    kind: Literal["type_column_contradiction"]
    modelo: str = Field(pattern=r"^[0-9]{3}$")
    revision: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derivation_code: str = Field(min_length=1)
    """The single derivation path the contradicting fields render through."""
    field_count: int = Field(gt=0)
    """Exactly how many shipped fields contradict the type column under this row."""
    reason: str = Field(min_length=1)
    reconsideration_condition: str = Field(min_length=1)

    @property
    def subject(self) -> str:
        """Return the canonical modelo/revision disposition identity."""
        return f"{self.modelo}/{self.revision}"


class GeneratedTreeRenderRefusalDisposition(_StrictModel):
    """One source-bound declaration for a tree the generator REFUSES to render.

    Distinct from record drift, and not a softer form of it. A drifting tree
    renders and its bytes disagree with the shipped ones; a refused tree does
    not render at all, because the generator declines to emit a wire fact it
    could not determine. The two need different remedies and different gate
    handling: drift is diffed, refusal is raised.

    ``refusal_marker`` is what keeps the row honest. A refusal row asserts not
    merely that rendering fails but that it fails for the reason declared here,
    so a row cannot outlive its cause and cannot silently absorb a DIFFERENT
    refusal that appears later in the same tree.
    """

    kind: Literal["render_refusal"]
    modelo: str = Field(pattern=r"^[0-9]{3}$")
    revision: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    refusal_marker: str = Field(min_length=1)
    """A substring the raised refusal MUST contain, so the pin names its cause."""
    reason: str = Field(min_length=1)
    reconsideration_condition: str = Field(min_length=1)

    @property
    def subject(self) -> str:
        """Return the canonical modelo/revision disposition identity."""
        return f"{self.modelo}/{self.revision}"


_GeneratedTreeDisposition = Annotated[
    GeneratedTreeRecordDriftDisposition
    | GeneratedTreeRenderRefusalDisposition
    | GeneratedTreeTypeColumnContradictionDisposition,
    Field(discriminator="kind"),
]


class _GeneratedTreeDispositionLedger(_StrictModel):
    schema_version: Literal[4]
    dispositions: tuple[_GeneratedTreeDisposition, ...]


def disposition_ledger_from_path(path: Path) -> tuple[_GeneratedTreeDisposition, ...]:
    """Load and identity-check one disposition ledger file.

    The path is a parameter so the ledger's refusals can be proven against an
    isolated fixture. A detector whose teeth are shown only by patching the
    module it protects has not been shown to have teeth at all.
    """
    ledger = _GeneratedTreeDispositionLedger.model_validate_json(
        json.dumps(rtoml.load(path)),
    )
    subjects = tuple(item.subject for item in ledger.dispositions)
    if len(subjects) != len(set(subjects)):
        raise ValueError("generated tree disposition ledger contains duplicate subjects")
    return ledger.dispositions


def _load_disposition_ledger() -> tuple[_GeneratedTreeDisposition, ...]:
    """Load and identity-check the strict pipeline-owned declaration set."""
    return disposition_ledger_from_path(_DISPOSITIONS_PATH)


def record_drift_dispositions() -> tuple[GeneratedTreeRecordDriftDisposition, ...]:
    """Load the strict pipeline-owned record-drift declaration set."""
    return tuple(item for item in _load_disposition_ledger() if isinstance(item, GeneratedTreeRecordDriftDisposition))


def render_refusal_dispositions() -> tuple[GeneratedTreeRenderRefusalDisposition, ...]:
    """Load the strict pipeline-owned render-refusal declaration set."""
    return tuple(item for item in _load_disposition_ledger() if isinstance(item, GeneratedTreeRenderRefusalDisposition))


def type_column_contradiction_dispositions() -> tuple[GeneratedTreeTypeColumnContradictionDisposition, ...]:
    """Load the strict pipeline-owned type-column contradiction declaration set."""
    return tuple(
        item for item in _load_disposition_ledger() if isinstance(item, GeneratedTreeTypeColumnContradictionDisposition)
    )


def type_column_rulings_for(source_ref: str, source_sha256: str) -> dict[str, str]:
    """Return ``{derivation_code: ruling}`` for the type-column rows pinned to one design.

    A row adjudicates only the exact design bytes it was written against, so a
    changed design falls back to no ruling and its divergences refuse again.
    """
    return {
        row.derivation_code: f"type_column_contradiction {row.subject} {row.derivation_code}"
        for row in type_column_contradiction_dispositions()
        if row.source_ref == source_ref and row.source_sha256 == source_sha256
    }
