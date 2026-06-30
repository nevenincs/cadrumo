"""Typed ``--json`` payload schemas for ledger rule commands.

Every declared payload is an
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass registered with
:func:`~aeat.entrypoints.cli._schemas.register_schema` for the ledger rule
command JSON-contract surface carried by
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`. These schemas are the
CLI projection of the secure, profile-local rule engine: persisted
:class:`~aeat.domain.transactions.LedgerClassificationRule` records are listed
and added through :mod:`aeat.entrypoints.cli._ledger_rules_cli`, while
:func:`~aeat.application.ledger.apply_classification_rules` owns live mutation
semantics.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class ClassificationRulePayload(OutputSchema):
    """One persisted ledger classification rule row.

    Mirrors :class:`~aeat.domain.transactions.LedgerClassificationRule` as
    emitted by ``ledger rule add`` and ``ledger rule list``.  ``rule_id`` is the
    content-addressed id, ``description_pattern`` is the regex evaluated against
    transaction descriptions, and lower ``priority`` values run before higher
    ones.
    """

    rule_id: str
    description_pattern: str
    classification: str
    category_id: str | None = None
    priority: int
    actor: str
    created_at: str


@register_schema("ledger.rule.add")
class RuleAddResult(ClassificationRulePayload):
    """JSON envelope for ``aeat app ledger rule add``.

    The command persists one
    :class:`~aeat.domain.transactions.LedgerClassificationRule` through
    :class:`~aeat.application.ledger.LedgerClassificationRuleRepository`; adding
    the same pattern/classification/category tuple is idempotent because the
    rule id is content-addressed.
    """


@register_schema("ledger.rule.list")
class RuleListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule list``.

    Rows are returned in the application evaluation order exposed by
    :meth:`~aeat.application.ledger.LedgerClassificationRuleRepository.list_rules`:
    priority ascending, then creation time ascending for ties.
    """

    rules: list[ClassificationRulePayload]


class RuleApplyMatchPayload(OutputSchema):
    """One non-mutating preview row for ``ledger rule apply --dry-run``.

    The row reports the first rule that would classify the transaction if the
    operator re-ran without ``--dry-run``. It previews the same priority-ordered
    :class:`~aeat.domain.transactions.LedgerClassificationRule` match selection
    as :func:`~aeat.application.ledger.apply_classification_rules`, but remains
    evidence only: no transaction state or bucket event is written for these
    rows.
    """

    transaction_id: str
    description: str
    matched_rule_id: str
    classification: str


class RuleApplyAppliedPayload(OutputSchema):
    """One transaction classified by a live ``ledger rule apply`` pass.

    Mirrors :class:`~aeat.application.ledger.ApplyRulesAppliedRow`: the
    transaction id, the matched content-addressed rule id, and the
    classification persisted through the shared manual transaction mutation
    path with ``rule:<rule_id>`` provenance.
    """

    transaction_id: str
    matched_rule_id: str
    classification: str


@register_schema("ledger.rule.apply")
class RuleApplyResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule apply``.

    Covers both the dry-run branch (``dry_run``, ``would_match``,
    ``count``) and the live-apply branch (``rules_evaluated``,
    ``transactions_scanned``, ``matched``, ``skipped_already_classified``,
    ``no_match``, ``applied``).  Live counts mirror
    :class:`~aeat.application.ledger.ApplyRulesResult`; dry-run rows preview the
    same first-match rule selection without writing transaction state.  Rows
    already classified by an operator are skipped unless the command is run with
    the explicit ``--reaffirm`` consent flag.
    """

    # Dry-run path
    dry_run: bool | None = None
    would_match: list[RuleApplyMatchPayload] | None = None
    count: int | None = None
    # Live-apply path
    rules_evaluated: int | None = None
    transactions_scanned: int | None = None
    matched: int | None = None
    skipped_already_classified: int | None = None
    no_match: int | None = None
    applied: list[RuleApplyAppliedPayload] | None = None


class LLMProviderAvailabilityPayload(OutputSchema):
    """One subprocess LLM provider's PATH availability.

    Mirrors :class:`~aeat.application.ledger.LLMProviderAvailability` from
    :func:`~aeat.application.ledger.available_llm_providers`.  The probe uses
    PATH lookup only; it does not spawn the provider CLI or send transaction
    data to a cloud service.
    """

    provider: str
    cli_binary: str
    available: bool
    resolved_path: str | None = None


class VisionProviderPayload(OutputSchema):
    """The on-host Ollama vision model's availability.

    Carries the local vision backend readiness surfaced beside subprocess LLM
    providers, including operator remediation text when the local model or
    service is unavailable.
    """

    service: str
    available: bool
    detail: str = ""
    remediation: str = ""


@register_schema("ledger.providers")
class LedgerProvidersResult(OutputSchema):
    """JSON envelope for ``aeat app ledger providers``.

    Reports subprocess cloud-provider CLIs from
    :func:`~aeat.application.ledger.available_llm_providers` and the on-host
    Ollama vision model probed by
    :func:`~aeat.application.provisioning.probe_ollama_vision`, so the operator
    sees every classification backend - cloud and local - in one place before
    running LLM-assisted classification.
    """

    providers: list[LLMProviderAvailabilityPayload]
    vision: VisionProviderPayload | None = None
