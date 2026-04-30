"""`aeat financial txs` command group."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer

from ...financial import CsvProvider, OfxProvider, XlsxProvider, detect_provider
from ...financial._decimal import canonical_decimal
from ...financial.categories import CATEGORY_PROFILES_2025, SpendingCategory
from ...financial.categories._proportionality import ProportionalityKind
from ...financial.providers import RawTransaction
from ...financial.transactions import (
    BusinessClassification,
    LLMClassifierError,
    ModelTier,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionError,
    find_transaction,
    resolve_classifier,
    set_classification,
)
from ._catalogue import (
    catalogue_repository,
    load_catalogue_or_empty,
    load_catalogue_required,
)

_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")

app = typer.Typer(
    name="txs",
    no_args_is_help=True,
    help="Transaction catalogue helpers (#74).",
)


@app.command(
    name="list",
    help="List stored transactions, optionally filtering by classification state or decision confidence.",
)
def list_cmd(
    state: BusinessClassification | None = typer.Option(
        None,
        "--state",
        case_sensitive=False,
        help=(
            "Filter to one BusinessClassification value: BUSINESS, PERSONAL, MIXED, "
            "NOT_YET_PROCESSED, PROCESSED_UNCLASSIFIED, SKIPPED_BY_RULE, or FAILED_VALIDATION."
        ),
    ),
    unclassified: bool = typer.Option(
        False,
        "--unclassified",
        help="Deprecated; alias for --state PROCESSED_UNCLASSIFIED.",
        hidden=True,
    ),
    confidence_below: str | None = typer.Option(
        None,
        "--confidence-below",
        help="Show only transactions whose classification confidence is strictly below this threshold (0..1).",
    ),
) -> None:
    """List transactions from the configured catalogue file."""
    if state is not None and unclassified:
        typer.echo("--state and --unclassified are mutually exclusive.", err=True)
        raise typer.Exit(code=2)
    effective_state: BusinessClassification | None = state
    if effective_state is None and unclassified:
        effective_state = BusinessClassification.PROCESSED_UNCLASSIFIED
    threshold = _parse_confidence_threshold(confidence_below)
    catalogue = load_catalogue_or_empty()
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if _matches_filters(transaction, state=effective_state, threshold=threshold)
    )
    if not transactions:
        if threshold is not None and len(catalogue) > 0:
            typer.echo(
                "No transactions found below that confidence threshold. "
                "Note: manual classifications default to confidence 1.0, so --confidence-below "
                "only surfaces results when a rule engine or LLM classifier has assigned a "
                "lower score (not yet implemented for transactions)."
            )
        else:
            typer.echo("No transactions found.")
        return
    typer.echo("transaction_id\tdirection\tamount\tcurrency\tclassification\tcategory\tconfidence\tnarrative")
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
    help="Build the configured transaction catalogue from NDJSON or a source CSV/XLSX/OFX statement.",
)
def build_cmd(
    source: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        help="Path to ingest NDJSON or a source CSV/XLSX/OFX statement export.",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Overwrite an existing transaction catalogue instead of refusing.",
    ),
) -> None:
    """Persist a transaction catalogue from ingest output."""
    repo = catalogue_repository()
    target = repo.envelope_path
    if target.exists() and not replace:
        typer.echo(
            f"transaction catalogue already exists at {target}; rerun with --replace to overwrite it",
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        catalogue = _build_catalogue(source)
        repo.save(catalogue)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"built {len(catalogue)} transaction(s) into {target}")


@app.command(name="show", help="Show one stored transaction as JSON.")
def show_cmd(
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
) -> None:
    """Show one transaction from the configured catalogue file."""
    catalogue = load_catalogue_required()
    transaction = find_transaction(catalogue, transaction_id)
    if transaction is None:
        typer.echo(f"transaction not found: {transaction_id}", err=True)
        raise typer.Exit(code=2)
    typer.echo(transaction.model_dump_json(indent=2))


@app.command(
    name="classify",
    help="Persist a manual transaction classification in the configured catalogue.",
)
def classify_cmd(
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
    classification: BusinessClassification | None = typer.Option(
        None,
        "--as",
        case_sensitive=False,
        help=(
            "Optional classification target: BUSINESS, PERSONAL, MIXED, "
            "NOT_YET_PROCESSED, PROCESSED_UNCLASSIFIED, SKIPPED_BY_RULE, or FAILED_VALIDATION. "
            "Omit --as to update only category/reason metadata on an existing classification."
        ),
    ),
    pct: str | None = typer.Option(
        None,
        "--pct",
        help="Business-use percentage in the inclusive 0..1 range for MIXED.",
    ),
    category: SpendingCategory | None = typer.Option(
        None,
        "--category",
        case_sensitive=False,
        help="Specific spending category from the AEAT 39-category catalogue.",
    ),
    reason: str = typer.Option(
        "",
        "--reason",
        help="Optional free-text override justification; recorded in the history chain.",
    ),
    confidence: str | None = typer.Option(
        None,
        "--confidence",
        help=(
            "Advanced: record a non-default decision confidence (0..1). "
            "Manual classifications default to 1.0; override only when recording the score "
            "of a rule engine or LLM output rather than your own judgement."
        ),
    ),
) -> None:
    """Classify one transaction and write the updated catalogue to disk."""
    repo = catalogue_repository()
    catalogue = load_catalogue_required()
    current = find_transaction(catalogue, transaction_id)
    if current is None:
        typer.echo(f"transaction not found: {transaction_id}", err=True)
        raise typer.Exit(code=2)
    if classification is None and category is None and not reason and pct is None and confidence is None:
        typer.echo("no changes requested; pass --as, --category, --reason, --pct, or --confidence", err=True)
        raise typer.Exit(code=2)
    try:
        business_pct = Decimal(pct) if pct is not None else None
    except InvalidOperation as exc:
        typer.echo(f"invalid --pct value: {pct}", err=True)
        raise typer.Exit(code=2) from exc
    resolved_confidence = _parse_confidence_option(confidence)
    effective_classification = classification if classification is not None else current.business_classification
    if classification is not None and classification is not BusinessClassification.MIXED and business_pct is not None:
        typer.echo(
            "--pct can only be used together with --as MIXED; omit --pct for non-MIXED classifications",
            err=True,
        )
        raise typer.Exit(code=2)
    effective_category = category.value if category is not None else None
    if effective_category is not None:
        if current.direction is not TransactionDirection.OUTGOING:
            typer.echo(
                "spending categories apply only to outgoing expense transactions; "
                "incoming payments should not be assigned an expense category",
                err=True,
            )
            raise typer.Exit(code=2)
        if effective_classification not in {
            BusinessClassification.BUSINESS,
            BusinessClassification.PERSONAL,
            BusinessClassification.MIXED,
        }:
            typer.echo(
                "--category requires a business/private classification first; "
                "pass --as BUSINESS, PERSONAL, or MIXED before assigning a category",
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
    help=(
        "Classify transactions via an LLM (claude / gemini / codex). "
        "Pass a transaction ID for one record, or --all to process every "
        "NOT_YET_PROCESSED transaction. Results feed the same history "
        "chain as manual or rule-based decisions."
    ),
)
def classify_llm_cmd(
    transaction_id: str | None = typer.Argument(None, help="Stable transaction identifier (omit with --all)."),
    provider: str = typer.Option(
        ...,
        "--provider",
        case_sensitive=False,
        help="LLM provider: claude, gemini, or codex (must be on PATH).",
    ),
    tier: str | None = typer.Option(
        None,
        "--tier",
        case_sensitive=False,
        help=(
            "Minimum model-capability tier: low, medium, or high. "
            "Defaults to medium (enforced floor for classification)."
        ),
    ),
    model_alias: str | None = typer.Option(
        None,
        "--model-alias",
        case_sensitive=False,
        help=(
            "Stable tier-catalogue alias (e.g. claude-sonnet, gemini-pro, codex-o3). "
            "Decouples Kent from shifting provider model IDs."
        ),
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Advanced: pin a raw provider-specific model ID (skips tier enforcement).",
    ),
    all_pending: bool = typer.Option(
        False,
        "--all",
        help="Classify every NOT_YET_PROCESSED transaction in the catalogue.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run the classifier and print the results without saving.",
    ),
    max_total_seconds: float | None = typer.Option(
        None,
        "--max-total-seconds",
        help=(
            "Stop the --all loop after this many wall-clock seconds elapsed. "
            "Classifications already persisted before the budget is exhausted are kept. "
            "Omit for no ceiling."
        ),
    ),
    category_hint: SpendingCategory | None = typer.Option(
        None,
        "--category-hint",
        case_sensitive=False,
        help=(
            "Optional category Kent expects. The LLM is told the category is pre-set and "
            "must not pick a different one — mirrors the manual `--category` flag."
        ),
    ),
    pct_override: str | None = typer.Option(
        None,
        "--pct-override",
        help=(
            "When classification is MIXED, override the business-use percentage regardless "
            "of the LLM's answer. Takes the same 0..1 range as manual `--pct`."
        ),
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        help=(
            "Optional Kent-authored justification prepended to the LLM's reason. "
            "Matches the shape of the manual `--reason` flag."
        ),
    ),
) -> None:
    """Classify one or many transactions through an LLM CLI.

    Persists each successful classification immediately so a Ctrl+C or
    a later subprocess failure does not lose the classifications Kent
    has already paid API tokens for.
    """
    import time

    if all_pending and transaction_id is not None:
        typer.echo("--all is mutually exclusive with a transaction-id argument.", err=True)
        raise typer.Exit(code=2)
    if not all_pending and transaction_id is None:
        typer.echo("Pass a transaction-id argument or use --all.", err=True)
        raise typer.Exit(code=2)
    if max_total_seconds is not None and max_total_seconds <= 0:
        typer.echo("--max-total-seconds must be strictly positive.", err=True)
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
        typer.echo("No transactions selected for LLM classification.")
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
                f"[{index - 1}/{total}] --max-total-seconds reached; keeping {successes} classified so far.",
                err=True,
            )
            break
        prefix = f"[{index}/{total} {target.transaction_id[:16]}]"
        try:
            response = classifier.classify(target)
        except LLMClassifierError as exc:
            failures += 1
            typer.echo(f"{prefix} {provider} error: {exc}", err=True)
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
        line = (
            f"{prefix} {response.classification.value} @ {canonical_decimal(response.confidence)} — {combined_reason}"
        )
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
            except TransactionError as exc:
                failures += 1
                typer.echo(f"{prefix} persist error: {exc}", err=True)
                continue
        successes += 1

    if not dry_run and dirty:
        try:
            repo.save(updated_catalogue)
        except TransactionError as exc:
            failures += successes
            successes = 0
            typer.echo(f"final save error: {exc}", err=True)

    tail = "dry-run" if dry_run else "persisted"
    if stopped_early:
        tail += " (stopped at --max-total-seconds)"
    typer.echo(f"{successes} classified / {failures} failed / {tail}")
    if failures and successes == 0:
        raise typer.Exit(code=2)


def _parse_pct_override(raw: str | None) -> Decimal | None:
    """Parse a --pct-override value and range-check against [0, 1]."""
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
    """Compute the business_pct that should be persisted for a classification.

    Precedence (first non-None wins):
    1. Kent's explicit ``--pct-override`` (same UX as manual ``--pct``).
    2. The CategoryProfile's ``fixed_pct`` (FIXED_PERCENTAGE rules).
    3. The CategoryProfile's ``default_ratio`` (USAGE_RATIO_* rules —
       e.g. the 30% home-office default from #253).
    4. ``None`` — let the ``Transaction`` validator enforce the
       classification+business_pct coupling (None is required unless
       the classification is ``MIXED``, and MIXED with None raises).

    When classification is NOT ``MIXED``, we always return ``None`` so
    the profile's ratio does not corrupt a non-mixed row.
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
    """Combine Kent's optional authored reason with the LLM's rationale."""
    if kent_reason is None or not kent_reason.strip():
        return llm_reason
    return f"{kent_reason.strip()} — LLM: {llm_reason}"


def _parse_tier(raw: str | None) -> ModelTier:
    """Parse a --tier string into a ModelTier; default is the enforced floor."""
    from ...financial.transactions import MINIMUM_CLASSIFICATION_TIER

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


def _select_llm_targets(
    catalogue: TransactionCatalogue,
    *,
    transaction_id: str | None,
    all_pending: bool,
) -> list[Transaction]:
    """Return the transactions the classify-llm command should process.

    When ``--all`` is set, the target set is restricted to the two
    "please decide" states: ``NOT_YET_PROCESSED`` (fresh ingest,
    never seen) and ``PROCESSED_UNCLASSIFIED`` (pipeline saw it and
    could not commit). Already-classified rows (``BUSINESS`` /
    ``PERSONAL`` / ``MIXED``) are skipped — Kent should `classify`
    them manually to override. Rule-excluded (``SKIPPED_BY_RULE``)
    and invalid (``FAILED_VALIDATION``) rows are also skipped: they
    are deliberate negative signals from earlier pipeline stages
    that the LLM should not second-guess.
    """
    if transaction_id is not None:
        transaction = find_transaction(catalogue, transaction_id)
        if transaction is None:
            typer.echo(f"transaction not found: {transaction_id}", err=True)
            raise typer.Exit(code=2)
        return [transaction]
    return [tx for tx in catalogue.values() if tx.business_classification in _LLM_RETRY_STATES]


def _parse_confidence_threshold(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence-below`` option value."""
    if value is None:
        return None
    try:
        threshold = Decimal(value)
    except InvalidOperation as exc:
        typer.echo(f"invalid --confidence-below value: {value}", err=True)
        raise typer.Exit(code=2) from exc
    if not _CONFIDENCE_MIN <= threshold <= _CONFIDENCE_MAX:
        typer.echo("--confidence-below must be within the inclusive 0..1 range", err=True)
        raise typer.Exit(code=2)
    return threshold


def _parse_confidence_option(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence`` option value."""
    if value is None:
        return None
    try:
        resolved = Decimal(value)
    except InvalidOperation as exc:
        typer.echo(f"invalid --confidence value: {value}", err=True)
        raise typer.Exit(code=2) from exc
    if not _CONFIDENCE_MIN <= resolved <= _CONFIDENCE_MAX:
        typer.echo("--confidence must be within the inclusive 0..1 range", err=True)
        raise typer.Exit(code=2)
    return resolved


def _matches_filters(
    transaction: Transaction,
    *,
    state: BusinessClassification | None,
    threshold: Decimal | None,
) -> bool:
    """Return whether a transaction passes the current list filters (AND semantics)."""
    if state is not None and transaction.business_classification is not state:
        return False
    if threshold is not None:
        current = transaction.classification_confidence
        if current is None or current >= threshold:
            return False
    return True


def _format_optional_decimal(value: Decimal | None) -> str:
    """Render an optional ``Decimal`` for CLI tables, empty string for None."""
    if value is None:
        return ""
    return canonical_decimal(value)


def _resolve_classify_pct(
    *,
    current: Transaction,
    requested_classification: BusinessClassification | None,
    requested_pct: Decimal | None,
) -> Decimal | None:
    """Resolve the effective business percentage for one classify operation."""
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
    """Build a transaction catalogue from NDJSON or a provider-native source file."""
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
    except Exception as exc:
        raise TransactionError(f"unable to ingest transaction source: {source.resolve()}") from exc
    return _catalogue_from_raw_transactions(rows)


def _build_catalogue_from_ndjson(source: Path) -> TransactionCatalogue:
    """Load RawTransaction NDJSON and return the derived transaction catalogue."""
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
        except Exception as exc:
            raise TransactionError(f"invalid RawTransaction JSON at line {index} in {source.resolve()}") from exc
    if not rows:
        raise TransactionError(
            f"no RawTransaction rows were found in {source.resolve()}; "
            "re-run 'aeat financial ingest ... --output-json > file.ndjson' and verify the file is not empty"
        )
    return _catalogue_from_raw_transactions(rows)


def _read_ndjson_text(source: Path) -> str:
    """Read NDJSON text using the common encodings Kent may produce on Windows.

    UTF-16 is only attempted when the file carries a BOM (``\\xFF\\xFE`` or
    ``\\xFE\\xFF``) because UTF-16 decoding never raises ``UnicodeDecodeError``
    and would silently mis-interpret CP1252 bytes as paired UTF-16 code units.
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
    """Convert raw provider rows into the stored transaction catalogue."""
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
    except Exception as exc:
        raise TransactionError(f"unable to build transaction catalogue from the supplied rows: {exc}") from exc


def _fallback_provider_for_build(source: Path):
    """Mirror the ingest command's extension fallback for build-from-source."""
    suffix = source.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return CsvProvider()
    if suffix == ".xlsx":
        return XlsxProvider()
    if suffix in {".ofx", ".qfx"}:
        return OfxProvider()
    return None
