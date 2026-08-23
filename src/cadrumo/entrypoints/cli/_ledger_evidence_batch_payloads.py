"""Typed ``--json`` payload schemas for the ledger evidence batch run.

Every model here is referenced as an :class:`OutputSchema` deferred target, so the batch run's
``--json`` surface is introspectable from the same registry every other command's
payload is, rather than being an untyped dict assembled at the emit site.

Split into its own module rather than added to
:mod:`~entrypoints.cli._ledger_business_payloads`, following the same pattern
that module's own docstring documents for
:mod:`~entrypoints.cli._ledger_rule_payloads` and
:mod:`~entrypoints.cli._ledger_llm_payloads`: one transport family per module,
each under its owning surface.

The models here are the WIRE projection of the application-layer batch result
(:class:`~cadrumo.application.ledger.BatchRunResult` and its rows), not a second
definition of it. Every field is populated from that result's own
``model_dump(mode="json")``, so a field added to the engine's row surfaces here
by name or not at all -- the strict ``extra="forbid"`` base turns a drift into a
validation error at emit time rather than a silently narrowed payload.

The row set is the batch command's PRIMARY output, which is why it rides
``result`` rather than the notices channel: an operator automating a batch reads
per-item truth, and a diagnostic channel that a consumer may legitimately ignore
is the wrong home for the thing the command exists to produce
(``aeat-cli-contract``).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import Field

from ...core.identity import BucketId
from ...core.json_contract import OutputSchema, ResolvedPreconditionAction

__all__ = [
    "EvidenceBatchItemPayload",
    "EvidenceBatchPausePayload",
    "EvidenceBatchResult",
    "EvidenceBatchUnresolvedPayload",
]


class EvidenceBatchItemPayload(OutputSchema):
    """One document's row, mirroring :class:`~cadrumo.application.ledger.BatchItemResult`.

    ``refusal_code``, ``refusal_facts`` and ``refusal_action`` are present
    exactly when ``status`` is ``refused``; the engine's own model enforces that
    pairing in both directions before the row ever reaches this transport. The
    application owns the failed condition and its facts; this transport only
    resolves the verdict against the live action surface, adding no instruction
    or rendered explanation of its own.
    """

    content_address: str
    identity: str
    direction: str
    source_name: str
    status: str
    refusal_code: str | None = None
    refusal_facts: Mapping[str, str | int | bool | Decimal] = Field(default_factory=dict)
    refusal_action: ResolvedPreconditionAction | None = None
    needed_inference: bool = True


class EvidenceBatchUnresolvedPayload(OutputSchema):
    """A submitted source whose bytes could not be read at all.

    Kept in its own list rather than folded into the item rows, mirroring
    :class:`~cadrumo.application.ledger.UnresolvedBatchSource`: an item's
    identity IS its content address, and an unreadable file has none, so a
    placeholder would collide the moment a second file failed the same way.
    """

    source_name: str
    refusal_code: str
    refusal_facts: Mapping[str, str | int | bool | Decimal] = Field(default_factory=dict)
    refusal_action: ResolvedPreconditionAction | None = None


class EvidenceBatchPausePayload(OutputSchema):
    """One typed inference-lane refusal projected for the batch wire result.

    The application owns the measured facts and failed-condition verdict. This
    CLI-owned DTO resolves the verdict against the live action surface without
    adding an instruction or rendered explanation of its own.
    """

    facts: Mapping[str, str | int | bool] = Field(default_factory=dict)
    precondition_action: ResolvedPreconditionAction


class EvidenceBatchResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence batch``.

    ``any_failed`` and ``any_deferred`` are deliberately two booleans rather
    than one verdict. A paused item is not a failure -- nothing went wrong with
    the document and a re-run costs nothing because completed items are no-ops
    -- but it is not success either, and a consumer needs to tell "everything is
    done" from "the deterministic half is done". Folding them would also make
    ``pending_review`` read as breakage, which would train an operator to
    ignore the review gate working exactly as designed.

    ``summary`` carries every status at its tally including zero, because a
    status missing from a summary reads as "not applicable" rather than "none
    occurred".

    ``deterministic_completed`` and ``paced`` are carried beside the per-status
    summary rather than derived from it, because the summary cannot express
    them: a completed row looks identical whether it was read by a parser or
    through a model, so a consumer reading only the tally cannot tell a run that
    paced its whole inference half from one that paced nothing. Together the two
    figures are what makes pacing observable at all.
    """

    bucket_id: BucketId
    direction: str
    items: list[EvidenceBatchItemPayload] = []
    unresolved: list[EvidenceBatchUnresolvedPayload] = []
    inference_pause: EvidenceBatchPausePayload | None = None
    summary: dict[str, int] = {}
    deterministic_completed: int = 0
    paced: int = 0
    any_failed: bool
    any_deferred: bool
