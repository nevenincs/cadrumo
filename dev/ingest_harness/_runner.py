"""The harness runner: collects rows, refuses unquotable ones, prints the header.

The runner exists to make a figure hard to quote bare. Every report opens with
the key's content hash, the derived denominators, and the sanity line proving the
comparison path is exact decimal; every row it accepts carries its model
identity, revision, engine route and tier; and a row missing its tier is refused
rather than warned about.

**The runner does not read documents.** It takes measured rows from a caller that
drove the real product entry points. That is deliberate: a harness that
reimplements the reader it measures measures itself, and a 409-line shadow parser
was deleted from an earlier harness for exactly that reason. Keeping the engine
outside also means the runner needs no import of a product private module -- see
the package docstring for the reachability finding that makes this more than a
stylistic preference today.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from ._caveats import TWIN_LINK_IS_PROSE
from ._field_mapping import slots_unavailable_at
from ._key import CorpusKey
from ._result import FLOAT_SANITY_PROBE, EmittedOnly, HarnessRefusalError, ModelTier, ResultRow, Scored

__all__ = ["HarnessReport", "format_report", "verify_decimal_comparison_path"]


class HarnessReport:
    """A collection of measured rows bound to one pinned key.

    Rows are validated on the way IN rather than on the way out, so an
    unquotable row cannot sit in a report until someone happens to render it.
    """

    def __init__(self, key: CorpusKey) -> None:
        self._key = key
        self._rows: list[ResultRow] = []

    @property
    def rows(self) -> tuple[ResultRow, ...]:
        """Every accepted row, in insertion order."""
        return tuple(self._rows)

    def add(self, row: ResultRow) -> None:
        """Accept one row, refusing it if it cannot be honestly quoted.

        Raises:
            HarnessRefusalError: When the row was scored against a different key,
                names a document this key does not contain, or scores a slot its
                declared stage structurally cannot produce.
        """
        if row.key_sha256 != self._key.sha256:
            raise HarnessRefusalError(
                f"{row.doc_id}: row was scored against key {row.key_sha256[:12]} but this report is "
                f"pinned to {self._key.sha256[:12]}; figures from two keys must never share a report",
            )
        document = self._key.document(row.doc_id)
        # The capture POINT is a property of the measurement, and until this
        # refusal existed the report could not tell a reader that failed to
        # produce a field from a capture taken before the field exists. Both
        # read as a miss, and the residual reads as a product gap -- which on
        # record nearly bought a probabilistic replacement for two
        # deterministic authorities. Refused rather than silently dropped from
        # the denominator: the caller must move the capture, which is the fix.
        if isinstance(row.outcome, Scored):
            unavailable = slots_unavailable_at(document, row.stage)
            if unavailable:
                raise HarnessRefusalError(
                    f"{row.doc_id}: refused a row measured at {row.stage.value} that scores "
                    f"{', '.join(unavailable)}, which no output of that stage can carry. Scoring "
                    "them books a guaranteed miss against the reader and reports a product gap "
                    "that is an artefact of where the capture was taken. Drive the pipeline to "
                    "the stage that produces them and score the draft it hands on.",
                )
        self._rows.append(row)

    def extend(self, rows: Iterable[ResultRow]) -> None:
        """Accept many rows, refusing the first that cannot be quoted."""
        for row in rows:
            self.add(row)

    def baseline_rows(self) -> tuple[ResultRow, ...]:
        """Rows whose tier may inform an acceptance floor."""
        return tuple(row for row in self._rows if row.is_baseline_eligible)

    def reference_rows(self) -> tuple[ResultRow, ...]:
        """Rows that bound the pipeline from above and set no floor."""
        return tuple(row for row in self._rows if not row.is_baseline_eligible)


def require_model_tier(payload: dict[str, Any]) -> ModelTier:
    """Resolve a tier from an external payload, refusing a row that omits it.

    The typed row already makes the tier mandatory for anything built in
    process. This is the same gate at the boundary where rows arrive as data --
    a persisted result file, another tool's output -- which is the direction the
    omission would actually come from.

    Raises:
        HarnessRefusalError: When the tier is absent, blank, or not a known member.
    """
    raw = payload.get("model_tier")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise HarnessRefusalError(
            f"result row for {payload.get('doc_id', '<unknown document>')!r} carries no model_tier. "
            "A figure without its tier is as unfalsifiable as one without its key hash: the design "
            f"target is a small on-host model, so a number that could have come from any of "
            f"{[member.value for member in ModelTier]} states nothing about the shipped product.",
        )
    try:
        return ModelTier(raw)
    except ValueError as exc:
        raise HarnessRefusalError(
            f"result row for {payload.get('doc_id', '<unknown document>')!r} names an unknown "
            f"model_tier {raw!r}; accepted tiers are {[member.value for member in ModelTier]}",
        ) from exc


def verify_decimal_comparison_path() -> str:
    """Return the sanity line proving comparison never widens to binary float.

    Printed in every header. The same arithmetic that is false in binary floating
    point is exact here, so a reader can see from the report itself that a cent
    tolerance means a cent.

    Raises:
        HarnessRefusalError: If the comparison path is not exact, which would mean the
            amounts in every figure above it are untrustworthy.
    """
    tenth, fifth, three_tenths = FLOAT_SANITY_PROBE
    if tenth + fifth != three_tenths:
        raise HarnessRefusalError("decimal comparison path is not exact; every amount figure is untrustworthy")
    if 0.1 + 0.2 == 0.3:
        raise HarnessRefusalError("binary float unexpectedly exact; the sanity probe proves nothing here")
    return (
        "decimal path: Decimal('0.1') + Decimal('0.2') == Decimal('0.3') is True, "
        "while 0.1 + 0.2 == 0.3 is False in binary float. Amount comparison is exact decimal "
        "with a whole-cent tolerance taken from the key."
    )


def _outcome_line(row: ResultRow) -> str:
    outcome = row.outcome
    if isinstance(outcome, Scored):
        percent = (outcome.accuracy * Decimal(100)).quantize(Decimal("0.1"))
        return (
            f"{outcome.matched}/{outcome.scorable_field_count} matched ({percent}%), "
            f"{outcome.wrong} wrong, {outcome.missed} missed, {outcome.fabricated} FABRICATED"
        )
    return f"emitted {outcome.emitted_field_count} field(s) - NO ACCURACY: {outcome.why_unscored}"


def format_report(report: HarnessReport, *, key: CorpusKey) -> str:
    """Render the full report: provenance header, denominators, then rows.

    The header comes first and unconditionally, so there is no rendering path
    that emits a figure before the key it was measured against.
    """
    denominators = key.denominators
    lines: list[str] = [
        "=" * 78,
        "GROUND TRUTH KEY",
        f"  sha256                {key.sha256}",
        f"  bytes                 {key.byte_length}",
        f"  schema_version        {key.stale_schema_version!r}  <- STALE, NEVER CITE THIS; "
        "it has not tracked the key through v1..v5. Cite the sha256.",
        "-" * 78,
        "DENOMINATORS (re-derived from this key, not inherited from prose)",
        f"  documents             {denominators.documents}"
        f"  = {denominators.generated} generated"
        f" + {denominators.acquired_real} acquired-real"
        f" + {denominators.operator} operator",
        f"  stage1 reference text {denominators.stage1_reference_text}",
        f"  twin pairs            {denominators.twin_pairs}",
        f"  vision-path documents {denominators.vision_path}",
        f"  category-scorable     {denominators.category_scorable}",
        f"  NO authored truth     {denominators.documents_without_authored_truth}"
        "  <- accuracy is UNDEFINED over these, never zero",
        f"  fabrication traps     {denominators.fabrication_trap_slots} null-truth field slot(s)",
        "-" * 78,
        f"  {verify_decimal_comparison_path()}",
        f"  twin link: {TWIN_LINK_IS_PROSE}",
        "=" * 78,
    ]

    baseline = report.baseline_rows()
    reference = report.reference_rows()
    lines.append(f"ROWS: {len(report.rows)} total - {len(baseline)} baseline-eligible, {len(reference)} reference-only")
    for row in report.rows:
        lines.append("")
        lines.append(f"  {row.doc_id}  [{row.stage.value}]")
        lines.append(
            f"    model    {row.model_identity} rev {row.model_revision} "
            f"| tier {row.model_tier.value}"
            f"{'' if row.is_baseline_eligible else '  (UPPER REFERENCE - sets no floor)'}"
            f" | route {row.engine_route.value}",
        )
        lines.append(f"    result   {_outcome_line(row)}")
        for caveat in row.caveats:
            lines.append(f"    CAVEAT   {caveat}")
    return "\n".join(lines)


def emitted_or_scored(
    *, authored_field_count: int, emitted_field_count: int, matched: int, wrong: int, fabricated: int
) -> Scored | EmittedOnly:
    """Choose the outcome type from whether truth exists, never from preference.

    A convenience for callers assembling rows in bulk: the branch is made once,
    here, on the only fact that may decide it.
    """
    if authored_field_count == 0:
        return EmittedOnly(emitted_field_count=emitted_field_count)
    return Scored(
        scorable_field_count=authored_field_count,
        matched=matched,
        wrong=wrong,
        fabricated=fabricated,
    )


def sorted_rows_by_document(rows: Sequence[ResultRow]) -> tuple[ResultRow, ...]:
    """Return rows in a deterministic order for stable report diffs."""
    return tuple(sorted(rows, key=lambda row: (row.stage.value, row.doc_id)))
