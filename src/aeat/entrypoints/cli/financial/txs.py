"""Implement the ``aeat financial txs`` Typer command group.

Surfaces the persisted transaction catalogue
(:mod:`aeat.domain.transactions`) as CLI verbs (``list``, ``show``,
``build``, ``classify``, ``classify-llm``) and bridges to the LLM
classifier registry via
:func:`aeat.domain.transactions.resolve_classifier`. The ``classify``
verb persists manual decisions; ``classify-llm`` runs a configured
provider against either a single transaction or the catalogue's
pending rows, persisting each successful classification immediately so
intermediate failures do not lose progress.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer
from pydantic import ValidationError

from ....adapters.inbound.financial._decimal import canonical_decimal
from ....adapters.inbound.financial.providers import CsvProvider, OfxProvider, XlsxProvider, detect_provider
from ....adapters.inbound.financial.providers._base import FinancialProviderError
from ....domain.categories import CATEGORY_PROFILES_2025, ProportionalityKind, SpendingCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMClassifierError,
    ModelTier,
    RawTransaction,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionError,
    find_transaction,
    resolve_classifier,
    set_classification,
)
from .._i18n import tr
from ._catalogue import (
    catalogue_repository,
    load_catalogue_or_empty,
    load_catalogue_required,
)

_CONFIDENCE_MIN = Decimal("0")
"""Inclusive lower bound for confidence and percentage decimals."""

_CONFIDENCE_MAX = Decimal("1")
"""Inclusive upper bound for confidence and percentage decimals."""

app = typer.Typer(
    name="txs",
    no_args_is_help=True,
    help=tr("cli.txs.app_help"),
)


@app.command(
    name="list",
    help=tr("cli.txs.list.help"),
)
def list_cmd(
    state: BusinessClassification | None = typer.Option(
        None,
        "--state",
        case_sensitive=False,
        help=tr("cli.txs.list.state_help"),
    ),
    confidence_below: str | None = typer.Option(
        None,
        "--confidence-below",
        help=tr("cli.txs.list.confidence_below_help"),
    ),
) -> None:
    """List transactions from the configured catalogue, optionally filtered.

    The ``--state`` filter composes with the decision-confidence filter
    ``--confidence-below`` under AND semantics implemented in
    :func:`_matches_filters`.

    Args:
        state: Optional
            :class:`aeat.domain.transactions.BusinessClassification`
            filter restricting the listing to one classification state.
        confidence_below: Optional decision-confidence ceiling. When
            set, only transactions whose confidence is strictly below
            the threshold are listed.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when
            ``--confidence-below`` is outside the inclusive ``[0, 1]``
            range.
    """
    effective_state: BusinessClassification | None = state
    threshold = _parse_confidence_threshold(confidence_below)
    catalogue = load_catalogue_or_empty()
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if _matches_filters(transaction, state=effective_state, threshold=threshold)
    )
    if not transactions:
        if threshold is not None and len(catalogue) > 0:
            typer.echo(tr("cli.txs.list.no_matches_confidence"))
        else:
            typer.echo(tr("cli.txs.list.no_transactions"))
        return
    typer.echo(tr("cli.txs.list.header"))
    for transaction in sorted(
        transactions,
        key=lambda item: ((item.raw.value_date or item.raw.booked_date), item.transaction_id),
    ):
        typer.echo(
            "\t".join(
                [
                    transaction.transaction_id,
                    transaction.direction.value,
                    canonical_decimal(transaction.raw.amount),
                    transaction.raw.currency,
                    transaction.business_classification.value,
                    transaction.category_id or "",
                    _format_optional_decimal(transaction.classification_confidence),
                    transaction.raw.description,
                ]
            )
        )


@app.command(
    name="build",
    help=tr("cli.txs.build.help"),
)
def build_cmd(
    source: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        help=tr("cli.txs.build.source_help"),
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help=tr("cli.txs.build.replace_help"),
    ),
) -> None:
    """Persist a transaction catalogue from ingest output.

    Accepts either NDJSON produced by ``aeat financial ingest --output-json``
    or a raw provider-native source (CSV / XLSX / OFX). The result is
    saved through :func:`aeat.entrypoints.cli.financial._catalogue.catalogue_repository`.

    Args:
        source: Path to ingest NDJSON or a CSV/XLSX/OFX statement
            export.
        replace: When ``True``, overwrite an existing catalogue rather
            than refusing.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the catalogue
            already exists without ``--replace`` or when the build
            raises :exc:`aeat.domain.transactions.TransactionError`.
    """
    repo = catalogue_repository()
    target = repo.envelope_path
    if target.exists() and not replace:
        typer.echo(
            tr("cli.txs.build.exists_err", target=target),
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        catalogue = _build_catalogue(source)
        repo.save(catalogue)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(tr("cli.txs.build.success"))


@app.command(name="show", help=tr("cli.txs.show.help"))
def show_cmd(
    transaction_id: str = typer.Argument(..., help=tr("cli.txs.show.id_help")),
) -> None:
    """Show one transaction from the configured catalogue file.

    Args:
        transaction_id: Stable transaction identifier looked up via
            :func:`aeat.domain.transactions.find_transaction`.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when no transaction
            matches ``transaction_id``.
    """
    catalogue = load_catalogue_required()
    transaction = find_transaction(catalogue, transaction_id)
    if transaction is None:
        typer.echo(
            tr("cli.txs.show.not_found_err"),
            err=True,
        )
        raise typer.Exit(code=2)
    typer.echo(transaction.model_dump_json(indent=2))


@app.command(
    name="classify",
    help=tr("cli.txs.classify.help"),
)
def classify_cmd(
    transaction_id: str = typer.Argument(..., help=tr("cli.txs.classify.id_help")),
    classification: BusinessClassification | None = typer.Option(
        None,
        "--as",
        case_sensitive=False,
        help=tr("cli.txs.classify.as_help"),
    ),
    pct: str | None = typer.Option(
        None,
        "--pct",
        help=tr("cli.txs.classify.pct_help"),
    ),
    category: SpendingCategory | None = typer.Option(
        None,
        "--category",
        case_sensitive=False,
        help=tr("cli.txs.classify.category_help"),
    ),
    reason: str = typer.Option(
        "",
        "--reason",
        help=tr("cli.txs.classify.reason_help"),
    ),
    confidence: str | None = typer.Option(
        None,
        "--confidence",
        help=tr("cli.txs.classify.confidence_help"),
    ),
) -> None:
    """Classify one transaction and write the updated catalogue to disk.

    Resolves the effective classification, business percentage,
    category, and confidence from the operator-supplied options,
    enforces the cross-field invariants
    (:class:`aeat.domain.transactions.BusinessClassification` /
    ``business_pct`` / category coupling), and persists the change via
    :func:`aeat.domain.transactions.set_classification`.

    Args:
        transaction_id: Stable transaction identifier.
        classification: Optional new classification state. Omit to
            update only category / reason / pct / confidence metadata
            on the existing classification.
        pct: Optional business-use percentage in the inclusive ``0..1``
            range. Only valid for the
            :attr:`~aeat.domain.transactions.BusinessClassification.MIXED`
            classification.
        category: Optional spending category from
            :class:`aeat.domain.categories.SpendingCategory`. Requires
            an outgoing transaction and a business-side classification.
        reason: Optional override justification recorded in the
            history chain.
        confidence: Advanced override for the persisted decision
            confidence; defaults to ``1.0`` for manual classifications.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the transaction
            is missing, when no changes were requested, when ``--pct``
            cannot be parsed or is misused, when ``--confidence`` is
            out of range, or when
            :exc:`aeat.domain.transactions.TransactionError` surfaces
            during persistence.
    """
    repo = catalogue_repository()
    catalogue = load_catalogue_required()
    current = find_transaction(catalogue, transaction_id)
    if current is None:
        typer.echo(
            tr("cli.txs.show.not_found_err"),
            err=True,
        )
        raise typer.Exit(code=2)
    if classification is None and category is None and not reason and pct is None and confidence is None:
        typer.echo(
            tr("cli.txs.classify.no_changes_err"),
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        business_pct = Decimal(pct) if pct is not None else None
    except InvalidOperation as exc:
        typer.echo(
            tr("cli.txs.classify.invalid_pct_err"),
            err=True,
        )
        raise typer.Exit(code=2) from exc
    resolved_confidence = _parse_confidence_option(confidence)
    effective_classification = classification if classification is not None else current.business_classification
    if classification is not BusinessClassification.MIXED and business_pct is not None:
        typer.echo(
            tr("cli.txs.classify.mixed_pct_err"),
            err=True,
        )
        raise typer.Exit(code=2)
    effective_category = category.value if category is not None else None
    if effective_category is not None:
        if current.direction is not TransactionDirection.OUTGOING:
            typer.echo(
                tr("cli.txs.classify.outgoing_category_err"),
                err=True,
            )
            raise typer.Exit(code=2)
        if effective_classification not in {
            BusinessClassification.BUSINESS,
            BusinessClassification.PERSONAL,
            BusinessClassification.MIXED,
        }:
            typer.echo(
                tr("cli.txs.classify.business_category_err"),
                err=True,
            )
            raise typer.Exit(code=2)
    effective_pct = _resolve_classify_pct(
        current=current,
        requested_classification=classification,
        requested_pct=business_pct,
    )
    try:
        updated = set_classification(
            catalogue,
            transaction_id,
            classification=effective_classification,
            business_pct=effective_pct,
            category_id=effective_category,
            notes=reason if reason else None,
            classified_by="manual",
            reason=reason,
            confidence=resolved_confidence,
        )
        repo.save(updated)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    updated_transaction = find_transaction(updated, transaction_id)
    assert updated_transaction is not None
    typer.echo(updated_transaction.model_dump_json(indent=2))


@app.command(
    name="classify-llm",
    help=tr("cli.txs.classify_llm.help"),
)
def classify_llm_cmd(
    transaction_id: str | None = typer.Argument(None, help=tr("cli.txs.classify_llm.id_help")),
    provider: str = typer.Option(
        ...,
        "--provider",
        case_sensitive=False,
        help=tr("cli.txs.classify_llm.provider_help"),
    ),
    tier: str | None = typer.Option(
        None,
        "--tier",
        case_sensitive=False,
        help=tr("cli.txs.classify_llm.tier_help"),
    ),
    model_alias: str | None = typer.Option(
        None,
        "--model-alias",
        case_sensitive=False,
        help=tr("cli.txs.classify_llm.model_alias_help"),
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help=tr("cli.txs.classify_llm.model_help"),
    ),
    all_pending: bool = typer.Option(
        False,
        "--all",
        help=tr("cli.txs.classify_llm.all_help"),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=tr("cli.txs.classify_llm.dry_run_help"),
    ),
    max_total_seconds: float | None = typer.Option(
        None,
        "--max-total-seconds",
        help=tr("cli.txs.classify_llm.max_seconds_help"),
    ),
    category_hint: SpendingCategory | None = typer.Option(
        None,
        "--category-hint",
        case_sensitive=False,
        help=tr("cli.txs.classify_llm.category_hint_help"),
    ),
    pct_override: str | None = typer.Option(
        None,
        "--pct-override",
        help=tr("cli.txs.classify_llm.pct_override_help"),
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        help=tr("cli.txs.classify_llm.reason_help"),
    ),
) -> None:
    """Classify one or many transactions through an LLM CLI.

    Resolves a classifier via
    :func:`aeat.domain.transactions.resolve_classifier`, walks the
    selected target set, and persists each successful classification
    immediately so a ``Ctrl+C`` or a later subprocess failure does not
    lose classifications already produced by paid API calls.

    Args:
        transaction_id: Stable transaction identifier; mutually
            exclusive with ``--all``.
        provider: LLM provider name (``claude``, ``gemini``, ``codex``).
        tier: Minimum
            :class:`aeat.domain.transactions.ModelTier` capability
            (``low``, ``medium``, ``high``); defaults to the enforced
            classification floor.
        model_alias: Stable tier-catalogue alias decoupling the operator
            from shifting provider model IDs.
        model: Advanced raw provider-specific model ID; skips tier
            enforcement.
        all_pending: Process every
            :attr:`~aeat.domain.transactions.BusinessClassification.NOT_YET_PROCESSED`
            and
            :attr:`~aeat.domain.transactions.BusinessClassification.PROCESSED_UNCLASSIFIED`
            row.
        dry_run: Run the classifier and print results without saving.
        max_total_seconds: Optional wall-clock budget for the
            ``--all`` loop; classifications already persisted are kept.
        category_hint: Optional category the operator expects; the LLM
            is told the category is pre-set and may not deviate.
        pct_override: Override business percentage for MIXED
            classifications regardless of the LLM's answer.
        reason: Optional operator-authored justification prepended to
            the LLM's reason in the history chain.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the argument set
            is invalid, when ``--max-total-seconds`` is non-positive,
            when ``--pct-override`` cannot be parsed, when classifier
            resolution fails, or when every classification attempt
            failed (no successes).
    """
    import time

    if all_pending and transaction_id is not None:
        typer.echo(
            tr("cli.txs.classify_llm.errors.exclusive_all_id"),
            err=True,
        )
        raise typer.Exit(code=2)
    if not all_pending and transaction_id is None:
        typer.echo(
            tr("cli.txs.classify_llm.errors.missing_target"),
            err=True,
        )
        raise typer.Exit(code=2)
    if max_total_seconds is not None and max_total_seconds <= 0:
        typer.echo(
            tr("cli.txs.classify_llm.errors.invalid_max_seconds"),
            err=True,
        )
        raise typer.Exit(code=2)
    resolved_pct_override: Decimal | None
    try:
        resolved_pct_override = _parse_pct_override(pct_override)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    try:
        resolved_tier = _parse_tier(tier)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    try:
        classifier = resolve_classifier(
            provider,
            alias=model_alias,
            model=model,
            minimum_tier=resolved_tier,
        )
    except LLMClassifierError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    repo = catalogue_repository()
    catalogue = load_catalogue_required()
    targets = _select_llm_targets(catalogue, transaction_id=transaction_id, all_pending=all_pending)
    if not targets:
        typer.echo(tr("cli.txs.classify_llm.labels.no_targets"))
        return

    total = len(targets)
    updated_catalogue = catalogue
    successes = 0
    failures = 0
    stopped_early = False
    dirty = False
    started = time.monotonic()
    for index, target in enumerate(targets, start=1):
        if max_total_seconds is not None and time.monotonic() - started >= max_total_seconds:
            stopped_early = True
            typer.echo(
                tr("cli.txs.classify_llm.timeout"),
                err=True,
            )
            break
        prefix = f"[{index}/{total} {target.transaction_id[:16]}]"
        try:
            response = classifier.classify(target)
        except LLMClassifierError:
            failures += 1
            typer.echo(
                tr("cli.txs.classify_llm.errors.classification_failed", prefix=prefix, provider=provider),
                err=True,
            )
            continue
        effective_category: SpendingCategory | None = response.category
        if category_hint is not None and effective_category != category_hint:
            effective_category = category_hint
        effective_pct = _resolve_effective_pct(
            classification=response.classification,
            response_category=effective_category,
            pct_override=resolved_pct_override,
        )
        combined_reason = _combine_reason(kent_reason=reason, llm_reason=response.reason)
        llm_suffix = tr("cli.txs.classify_llm.llm_suffix")
        confidence = canonical_decimal(response.confidence)
        line = f"{prefix} {response.classification.value} @ {confidence}{llm_suffix}{combined_reason}"
        typer.echo(line)
        if not dry_run:
            try:
                updated_catalogue = set_classification(
                    updated_catalogue,
                    target.transaction_id,
                    classification=response.classification,
                    business_pct=effective_pct,
                    classified_by=classifier.decided_by,
                    reason=combined_reason,
                    confidence=response.confidence,
                    category_id=effective_category.value if effective_category is not None else None,
                    notes=combined_reason,
                )
                dirty = True
            except TransactionError:
                failures += 1
                typer.echo(
                    tr("cli.txs.classify_llm.errors.persistence_failed", prefix=prefix),
                    err=True,
                )
                continue
        successes += 1

    if not dry_run and dirty:
        try:
            repo.save(updated_catalogue)
        except TransactionError:
            failures += successes
            successes = 0
            typer.echo(
                tr("cli.txs.classify_llm.errors.save_failed"),
                err=True,
            )

    tail = tr("cli.txs.classify_llm.dry_run_label") if dry_run else tr("cli.txs.classify_llm.persisted_label")
    if stopped_early:
        tail += tr("cli.txs.classify_llm.stopped_early_suffix")
    typer.echo(
        tr(
            "cli.txs.classify_llm.summary",
            successes=successes,
            failures=failures,
            tail=tail,
        )
    )
    if failures and successes == 0:
        raise typer.Exit(code=2)


def _parse_pct_override(raw: str | None) -> Decimal | None:
    """Parse a ``--pct-override`` value and range-check against ``[0, 1]``.

    Args:
        raw: Operator-supplied decimal text or ``None``.

    Returns:
        Parsed :class:`decimal.Decimal` or ``None`` when ``raw`` is
        ``None``.

    Raises:
        ValueError: When ``raw`` is not a valid decimal or falls
            outside the inclusive ``[0, 1]`` range.
    """
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"--pct-override {raw!r} is not a valid decimal") from exc
    if not _CONFIDENCE_MIN <= value <= _CONFIDENCE_MAX:
        raise ValueError("--pct-override must be within the inclusive 0..1 range")
    return value


def _resolve_effective_pct(
    *,
    classification: BusinessClassification,
    response_category: SpendingCategory | None,
    pct_override: Decimal | None,
) -> Decimal | None:
    """Compute the ``business_pct`` to persist for a classification.

    Precedence (first non-``None`` wins):

    * Operator-supplied ``--pct-override`` (same UX as manual
      ``--pct``).
    * The
      :class:`~aeat.domain.categories.CategoryProfile`'s ``fixed_pct``
      for
      :attr:`~aeat.domain.categories.ProportionalityKind.FIXED_PERCENTAGE`
      rules.
    * The :class:`~aeat.domain.categories.CategoryProfile`'s
      ``default_ratio`` for ``USAGE_RATIO_*`` rules.
    * ``None`` — let the
      :class:`aeat.domain.transactions.Transaction` validator enforce
      the classification + ``business_pct`` coupling.

    When ``classification`` is not
    :attr:`~aeat.domain.transactions.BusinessClassification.MIXED`,
    always returns ``None`` so the profile's ratio does not corrupt
    a non-mixed row.

    Args:
        classification: The classification the LLM produced (or the
            override was applied to).
        response_category: Optional spending category resolved for
            the row.
        pct_override: Operator-supplied override.

    Returns:
        The business percentage to persist, or ``None``.
    """
    if classification is not BusinessClassification.MIXED:
        return None
    if pct_override is not None:
        return pct_override
    if response_category is None:
        return None
    profile = CATEGORY_PROFILES_2025.get(response_category)
    if profile is None:
        return None
    rule = profile.proportionality
    if rule.kind is ProportionalityKind.FIXED_PERCENTAGE and rule.fixed_pct is not None:
        return rule.fixed_pct
    if rule.default_ratio is not None:
        return rule.default_ratio
    return None


def _combine_reason(*, kent_reason: str | None, llm_reason: str) -> str:
    """Combine an optional operator-authored reason with the LLM's rationale.

    Args:
        kent_reason: Optional operator justification.
        llm_reason: Mandatory LLM rationale.

    Returns:
        Either ``llm_reason`` alone (when no operator reason was given)
        or ``"<kent_reason> — LLM: <llm_reason>"``.
    """
    if kent_reason is None or not kent_reason.strip():
        return llm_reason
    return f"{kent_reason.strip()} — LLM: {llm_reason}"


def _parse_tier(raw: str | None) -> ModelTier:
    """Parse a ``--tier`` string into a :class:`~aeat.domain.transactions.ModelTier`.

    Defaults to the enforced minimum classification tier
    (:data:`aeat.domain.transactions.MINIMUM_CLASSIFICATION_TIER`).

    Args:
        raw: Operator-supplied tier name or ``None``.

    Returns:
        The resolved :class:`~aeat.domain.transactions.ModelTier`.

    Raises:
        ValueError: When ``raw`` does not match a known tier.
    """
    from ....domain.transactions import MINIMUM_CLASSIFICATION_TIER

    if raw is None:
        return MINIMUM_CLASSIFICATION_TIER
    normalised = raw.strip().upper()
    try:
        return ModelTier[normalised]
    except KeyError as exc:
        known = ", ".join(t.name.lower() for t in ModelTier)
        raise ValueError(f"unknown --tier value {raw!r}; valid: {known}") from exc


_LLM_RETRY_STATES: frozenset[BusinessClassification] = frozenset(
    {
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.PROCESSED_UNCLASSIFIED,
    }
)
"""Classification states the ``--all`` LLM loop is allowed to revisit."""


def _select_llm_targets(
    catalogue: TransactionCatalogue,
    *,
    transaction_id: str | None,
    all_pending: bool,
) -> list[Transaction]:
    """Return the transactions ``classify-llm`` should process.

    When ``--all`` is set, the target set is restricted to the two
    "please decide" states:
    :attr:`~aeat.domain.transactions.BusinessClassification.NOT_YET_PROCESSED`
    (fresh ingest, never seen) and
    :attr:`~aeat.domain.transactions.BusinessClassification.PROCESSED_UNCLASSIFIED`
    (pipeline saw it and could not commit). Already-classified rows
    (``BUSINESS`` / ``PERSONAL`` / ``MIXED``) are skipped — operators
    should run ``classify`` manually to override. Rule-excluded
    (``SKIPPED_BY_RULE``) and invalid (``FAILED_VALIDATION``) rows
    are also skipped: they are deliberate negative signals from
    earlier pipeline stages that the LLM should not second-guess.

    Args:
        catalogue: Loaded transaction catalogue.
        transaction_id: Optional explicit identifier to target.
        all_pending: When ``True``, return every retry-eligible row.

    Returns:
        List of :class:`aeat.domain.transactions.Transaction` rows the
        classifier should process.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when an explicit
            ``transaction_id`` does not exist in the catalogue.
    """
    if transaction_id is not None:
        transaction = find_transaction(catalogue, transaction_id)
        if transaction is None:
            typer.echo(
                tr("cli.txs.show.not_found_err"),
                err=True,
            )
            raise typer.Exit(code=2)
        return [transaction]
    return [tx for tx in catalogue.values() if tx.business_classification in _LLM_RETRY_STATES]


def _parse_confidence_threshold(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence-below`` option value.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the value is not
            a valid decimal or falls outside the inclusive ``[0, 1]``
            range.
    """
    if value is None:
        return None
    try:
        threshold = Decimal(value)
    except InvalidOperation as exc:
        typer.echo(
            tr("cli.txs.classify.invalid_confidence_err"),
            err=True,
        )
        raise typer.Exit(code=2) from exc
    if not _CONFIDENCE_MIN <= threshold <= _CONFIDENCE_MAX:
        typer.echo(
            tr("cli.txs.classify.confidence_range_err"),
            err=True,
        )
        raise typer.Exit(code=2)
    return threshold


def _parse_confidence_option(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence`` option value.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the value is not
            a valid decimal or falls outside the inclusive ``[0, 1]``
            range.
    """
    if value is None:
        return None
    try:
        resolved = Decimal(value)
    except InvalidOperation as exc:
        typer.echo(
            tr("cli.txs.classify.invalid_confidence_err"),
            err=True,
        )
        raise typer.Exit(code=2) from exc
    if not _CONFIDENCE_MIN <= resolved <= _CONFIDENCE_MAX:
        typer.echo(
            tr("cli.txs.classify.confidence_range_err"),
            err=True,
        )
        raise typer.Exit(code=2)
    return resolved


def _matches_filters(
    transaction: Transaction,
    *,
    state: BusinessClassification | None,
    threshold: Decimal | None,
) -> bool:
    """Return whether ``transaction`` passes both list filters under AND semantics."""
    if state is not None and transaction.business_classification is not state:
        return False
    if threshold is not None:
        current = transaction.classification_confidence
        if current is None or current >= threshold:
            return False
    return True


def _format_optional_decimal(value: Decimal | None) -> str:
    """Render an optional :class:`decimal.Decimal` for CLI tables, empty string for ``None``."""
    if value is None:
        return ""
    return canonical_decimal(value)


def _resolve_classify_pct(
    *,
    current: Transaction,
    requested_classification: BusinessClassification | None,
    requested_pct: Decimal | None,
) -> Decimal | None:
    """Resolve the effective business percentage for one ``classify`` operation.

    When the request leaves the classification unchanged, an explicit
    ``--pct`` wins over the existing value; otherwise the existing
    business percentage is preserved. For
    :attr:`~aeat.domain.transactions.BusinessClassification.MIXED`
    targets, the explicit ``--pct`` wins, then the carried-over
    MIXED value, then ``None``. Non-MIXED targets always resolve to
    ``None`` so the validator can enforce the cross-field invariant.

    Args:
        current: The transaction in its persisted state.
        requested_classification: New classification or ``None`` to
            keep the current one.
        requested_pct: Operator-supplied ``--pct`` value or ``None``.

    Returns:
        The business percentage to persist, or ``None``.
    """
    if requested_classification is None:
        if requested_pct is not None:
            return requested_pct
        return current.business_pct
    if requested_classification is BusinessClassification.MIXED:
        if requested_pct is not None:
            return requested_pct
        if current.business_classification is BusinessClassification.MIXED and current.business_pct is not None:
            return current.business_pct
        return None
    return None


def _build_catalogue(source: Path) -> TransactionCatalogue:
    """Build a transaction catalogue from NDJSON or a provider-native source file.

    Args:
        source: Path to ingest NDJSON or a CSV/XLSX/OFX statement.

    Returns:
        A :class:`aeat.domain.transactions.TransactionCatalogue` ready
        to persist.

    Raises:
        :exc:`aeat.domain.transactions.TransactionError`: When no
            provider can handle ``source`` or when an ingest call fails.
    """
    suffix = source.suffix.lower()
    if suffix in {".ndjson", ".jsonl"}:
        return _build_catalogue_from_ndjson(source)
    provider = detect_provider(source) or _fallback_provider_for_build(source)
    if provider is None:
        raise TransactionError(
            f"unable to determine how to build a catalogue from {source.resolve()}; "
            "pass ingest NDJSON or a CSV/XLSX/OFX statement export"
        )
    try:
        rows = tuple(provider.ingest(source))
    except (FinancialProviderError, OSError) as exc:
        raise TransactionError(f"unable to ingest transaction source: {source.resolve()}") from exc
    return _catalogue_from_raw_transactions(rows)


def _build_catalogue_from_ndjson(source: Path) -> TransactionCatalogue:
    """Load :class:`~aeat.domain.transactions.RawTransaction` NDJSON into a catalogue.

    Raises:
        :exc:`aeat.domain.transactions.TransactionError`: When the
            file cannot be read, decoded, parsed, or yields zero rows.
    """
    try:
        lines = _read_ndjson_text(source).splitlines()
    except OSError as exc:
        raise TransactionError(f"unable to read NDJSON source: {source.resolve()}") from exc
    except UnicodeDecodeError as exc:
        raise TransactionError(
            f"unable to decode NDJSON source: {source.resolve()}; "
            "prefer 'aeat financial ingest ... --output-json > file.ndjson' from this CLI, "
            "which now emits ASCII-safe JSON"
        ) from exc
    rows: list[RawTransaction] = []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(RawTransaction.model_validate_json(line))
        except (ValueError, ValidationError) as exc:
            raise TransactionError(f"invalid RawTransaction JSON at line {index} in {source.resolve()}") from exc
    if not rows:
        raise TransactionError(
            f"no RawTransaction rows were found in {source.resolve()}; "
            "re-run 'aeat financial ingest ... --output-json > file.ndjson' and verify the file is not empty"
        )
    return _catalogue_from_raw_transactions(rows)


def _read_ndjson_text(source: Path) -> str:
    """Read NDJSON text tolerating the common encodings produced on Windows.

    UTF-16 is only attempted when the file carries a BOM
    (``\\xFF\\xFE`` or ``\\xFE\\xFF``) because UTF-16 decoding never
    raises :exc:`UnicodeDecodeError` and would silently mis-interpret
    CP1252 bytes as paired UTF-16 code units.

    Args:
        source: Path to the NDJSON file.

    Returns:
        The decoded text.

    Raises:
        UnicodeDecodeError: When none of the candidate encodings
            successfully decode the bytes.
    """
    raw = source.read_bytes()
    has_utf16_bom = raw[:2] in (b"\xff\xfe", b"\xfe\xff")
    candidates = ["utf-16", "utf-8-sig", "utf-8", "cp1252"] if has_utf16_bom else ["utf-8-sig", "utf-8", "cp1252"]
    for encoding in candidates:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("ndjson", raw, 0, len(raw), "unsupported NDJSON encoding")


def _catalogue_from_raw_transactions(rows: list[RawTransaction] | tuple[RawTransaction, ...]) -> TransactionCatalogue:
    """Convert raw provider rows into the stored transaction catalogue.

    Raises:
        :exc:`aeat.domain.transactions.TransactionError`: When any row
            fails :class:`~aeat.domain.transactions.Transaction`
            validation.
    """
    try:
        transactions = [
            Transaction.model_validate(
                {
                    "raw": raw,
                    "direction": TransactionDirection.OUTGOING if raw.amount < 0 else TransactionDirection.INCOMING,
                }
            )
            for raw in rows
        ]
        return TransactionCatalogue.from_transactions(transactions)
    except (ValueError, ValidationError) as exc:
        raise TransactionError(f"unable to build transaction catalogue from the supplied rows: {exc}") from exc


def _fallback_provider_for_build(source: Path):
    """Mirror the ingest command's extension fallback for build-from-source.

    Returns ``None`` when no extension-based fallback is available.
    """
    suffix = source.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return CsvProvider()
    if suffix == ".xlsx":
        return XlsxProvider()
    if suffix in {".ofx", ".qfx"}:
        return OfxProvider()
    return None
