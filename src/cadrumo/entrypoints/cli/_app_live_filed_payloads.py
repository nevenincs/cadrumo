"""Typed JSON transport schemas for the live filed service."""

from __future__ import annotations

from typing import Literal

from ...core.period import Period
from ...core.identity import AeatExpedienteId
from ...core.json_contract import OutputSchema


class FiledListingRowPayload(OutputSchema):
    """JSON projection of one :class:`FiledDataListingRow`.

    The row comes from AEAT's declaration register only; the boolean fields say
    which submitted-file, declaration-copy, or justificante links were visible
    without downloading those artefacts.
    """

    modelo: str
    year: int
    period: str
    expediente_id: AeatExpedienteId
    status: str
    presented_at: str
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledHistoryDiscoveryPairPayload(OutputSchema):
    """JSON projection of one :class:`FiledHistoryDiscoveryPair`.

    ``signals`` is the load-bearing field and is deliberately NOT collapsed to a
    boolean or dropped once the union is built: it is what tells a reader whether
    an empty result for this pair means anything. ``zero_rows_is_an_anomaly``
    carries the derived answer so a consumer of the JSON does not have to
    reimplement the rule and possibly get it wrong.
    """

    modelo: str
    ejercicio: int
    signals: list[str]
    zero_rows_is_an_anomaly: bool


class FiledCaptureFailurePayload(OutputSchema):
    """JSON projection of one :class:`FiledDataCaptureFailureRow`."""

    modelo: str
    year: int
    period: str | None = None
    expediente_id: AeatExpedienteId | None = None
    error_type: str
    message: str


class FiledListResult(OutputSchema):
    """List result for declaration-register rows returned by the live filed surface.

    Single-modelo calls mirror
    :class:`FiledDataListingReport`; registry-wide calls
    mirror :class:`BulkFiledDataListingReport` and may
    include per-modelo failure rows. No filed artefact bodies are captured by
    this schema.
    """

    modelo_filter: str | None
    year_from: int
    year_to: int
    row_count: int
    failed_count: int = 0
    rows: list[FiledListingRowPayload]
    failures: list[FiledCaptureFailurePayload] = []


class FiledDiscoverResult(OutputSchema):
    """Discovery result: which ``(modelo, ejercicio)`` pairs a history pull would walk.

    Mirrors :class:`FiledHistoryDiscoveryReport`. Read-only; nothing is captured
    or persisted by the verb that emits this.

    The two count fields are not decoration. ``profile_expected_count`` is the
    only number in this payload that supports a completeness claim, because only
    the profile signal is taxpayer-specific by construction;
    ``register_options_only_count`` counts pairs offered by a list whose scoping
    is unconfirmed, which widens the walk but proves nothing about this
    taxpayer's history.

    Attributes:
        pairs: Every pair a history pull would walk, each tagged with the
            signal(s) that nominated it.
        pair_count: Total pairs in the walk grid.
        profile_expected_count: Pairs the taxpayer's own declared facts expected.
        register_options_only_count: Pairs offered ONLY by the register's option
            list. A zero-row outcome for one of these is a plain negative.
        profile_year_span_determined: Whether the profile declared the activity
            start date the year axis needs. ``False`` means the profile signal
            contributed nothing and this payload is NOT a coverage denominator.
        register_options_read: Whether the register's option lists were read.
        carries_a_taxpayer_specific_denominator: Whether any coverage claim can
            rest on this report at all.
    """

    pairs: list[FiledHistoryDiscoveryPairPayload]
    pair_count: int
    profile_expected_count: int
    register_options_only_count: int
    profile_year_span_determined: bool
    register_options_read: bool
    carries_a_taxpayer_specific_denominator: bool


class FiledHistoryPairOutcomePayload(OutputSchema):
    """What one walked ``(modelo, ejercicio)`` pair actually produced.

    ``failure_message`` being set is a DIFFERENT fact from ``row_count`` being
    zero, and the two are carried separately on purpose. A truncated register
    page is refused by the walker and absorbed into a failure row, so folding it
    into "zero rows" would render a parse refusal as "no filings found" — the
    silent under-report this whole cluster exists to remove. Read
    :attr:`refused` before reading :attr:`row_count`.

    Attributes:
        modelo: Modelo code.
        ejercicio: Filing year.
        signals: The discovery signal(s) that nominated this pair.
        row_count: Register rows the walk returned. Meaningful only when the
            pair did not refuse.
        captured_count: Declaraciones actually captured from those rows.
        refused: Whether the pair produced a failure row instead of an answer.
        failure_type: Exception type of the refusal, when refused.
        failure_message: Bounded refusal text, when refused.
    """

    modelo: str
    ejercicio: int
    signals: list[str]
    row_count: int = 0
    captured_count: int = 0
    refused: bool = False
    failure_type: str | None = None
    failure_message: str | None = None


class FiledHistoryOnboardingResult(OutputSchema):
    """One history-onboarding run: what was walked, captured and reconciled.

    **This payload carries no completeness percentage and no fraction, and that
    absence is a decision rather than an omission.** A ratio computed over the
    walked pairs would be a ratio over a denominator that partly comes from
    AEAT's offered option list, whose scoping to this NIF is unconfirmed — so the
    number would look like coverage while resting on a set that may have nothing
    to do with this taxpayer. ``denominator_note`` says in prose what the
    denominator actually was, which is the honest form of the same information.
    A gate asserts no percentage or fraction field regrows here.

    Attributes:
        pairs: Per-pair outcomes, each tagged with the signal(s) behind it.
        pair_count: Pairs walked.
        profile_expected_count: Pairs the taxpayer's declared facts expected.
        register_options_only_count: Pairs offered only by the unconfirmed list.
        refused_count: Pairs that produced a failure row rather than an answer.
        empty_count: Pairs that legitimately returned no rows.
        captured_count: Declaraciones captured across the run.
        reached_count: Declaraciones the sweep REACHED. Distinct from
            ``captured_count``, which counts written observation paths and so
            stays zero in a preview — leaving it unable to say whether a limited
            sweep stopped early on the very path where that matters most.
        scoping_signal: The offline reading of whether the register's option list
            looks NIF-scoped. Advisory; every value is a hedge.
        denominator_note: Prose statement of what the coverage denominator was
            and what it does not establish.
        iva_wallet_status: Outcome token for the IVA wallet stage.
        iva_wallet_divergence: The wallet reconciliation's divergence verdict.
        iva_wallet_blocked: Whether the wallet divergence blocks verify/file.
        notificaciones_status: Outcome token for the notificaciones stage.
        notificaciones_row_count: Notificaciones rows the pull observed.
        stage_failures: One line per stage that did not complete, so a partial
            run reports which part failed instead of reading as a whole one.
    """

    pairs: list[FiledHistoryPairOutcomePayload]
    pair_count: int
    profile_expected_count: int
    register_options_only_count: int
    refused_count: int
    empty_count: int
    captured_count: int
    reached_count: int
    scoping_signal: str
    denominator_note: str
    iva_wallet_status: str
    iva_wallet_divergence: str | None = None
    iva_wallet_blocked: bool = False
    notificaciones_status: str
    notificaciones_row_count: int = 0
    stage_failures: list[str] = []


class FiledCaptureResult(OutputSchema):
    """Capture result for encrypted filed-declaration observations and artefacts.

    In ``single`` mode the payload mirrors
    :class:`FiledDataCaptureReport`; in ``bulk`` mode it
    mirrors :class:`BulkFiledDataCaptureReport`. The
    ``observation_paths`` and ``artefact_refs`` fields identify local encrypted
    stores, while justificante and filing-evidence counts report local metadata
    enrolment against existing :class:`ModeloRecord`
    records.
    """

    mode: Literal["single", "bulk"] = "single"
    output_root: str
    modelo: str | None = None
    year: int | None = None
    modelos: list[str] = []
    year_from: int | None = None
    year_to: int | None = None
    captured_count: int
    failed_count: int = 0
    dry_run: bool = False
    observation_paths: list[str]
    artefact_refs: list[str]
    justificante_metadata_count: int = 0
    justificante_csvs: list[str] = []
    filing_evidence_stamped_count: int = 0
    filing_record_ids: list[str] = []
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: list[str] = []
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]
    failures: list[FiledCaptureFailurePayload] = []


class FiledCaptureSourcesResult(OutputSchema):
    """Source-observation capture result for a target filing's registry dependencies.

    Mirrors :class:`SourceFiledDataCaptureReport`: the
    target :class:`Period` is resolved through registry authority, prior filed
    observations are persisted as encrypted local evidence, and matching
    justificantes may enrol local filing evidence without mutating AEAT state.
    """

    output_root: str
    target_modelo: str
    target_year: int
    target_period: Period
    captured_count: int
    observation_paths: list[str]
    artefact_refs: list[str]
    justificante_metadata_count: int = 0
    justificante_csvs: list[str] = []
    filing_evidence_stamped_count: int = 0
    filing_record_ids: list[str] = []
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: list[str] = []
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]


__all__ = [
    "FiledCaptureFailurePayload",
    "FiledCaptureResult",
    "FiledCaptureSourcesResult",
    "FiledDiscoverResult",
    "FiledHistoryDiscoveryPairPayload",
    "FiledHistoryOnboardingResult",
    "FiledHistoryPairOutcomePayload",
    "FiledListResult",
    "FiledListingRowPayload",
]
