"""Ledger ratios CLI command surface.

Use of :class:`BucketEventHistoryRepository` for compliance.
"""

from __future__ import annotations

import typer

from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.time import now
from ...domain.buckets import BucketEventType
from ._common import _bad, _emit_envelope, _no_active_profile_refusal, parse_decimal_amount
from ._common import activate_subcommand_output_language as _activate_subcommand_output_language

_log = get_logger(__name__)

ratios_app = typer.Typer(
    name="ratios",
    help=tr("cli.app.ledger.ratios.group_help", default="Per-category proportional-deduction overrides."),
    no_args_is_help=True,
)


def register_ratios_commands(app: typer.Typer) -> None:
    """Mount ratios commands on the ledger app."""
    app.add_typer(ratios_app, name="ratios")


def _ratios_bucket_id() -> str:
    """Return the active workflow bucket id or raise the standard CLI refusal."""
    from ...core import require_active_bucket_id
    from ...core.errors import NoActiveProfileError

    try:
        return require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc


def _ratios_bucket_and_profile() -> tuple[str, str | None]:
    """Return ``(bucket_id, active_profile_id)`` from workflow state."""
    from ...core import require_active_bucket_id, resolve_active_bucket_id
    from ...core.errors import NoActiveProfileError

    try:
        bucket_id = require_active_bucket_id()
    except NoActiveProfileError as exc:
        raise _no_active_profile_refusal() from exc
    return bucket_id, resolve_active_bucket_id()


def _emit_ratios_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    category: str,
    prior: object,
    new: object,
) -> None:
    """Append a ratios mutation event to the bucket-event-history catalogue."""
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = now()
    payload = {
        "category": category,
        "prior": "" if prior is None else str(prior),
        "new": "" if new is None else str(new),
    }
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=category,
        payload=payload,
    )
    repo = BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))
    catalogue = repo.load()
    repo.save(
        append_bucket_event(
            catalogue,
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=category,
                payload=payload,
                payload_version=1,
            ),
        ),
    )


def _emit_ratios_censo_override_warning(
    *,
    bucket_id: str,
    warning,
) -> None:
    """Append LEDGER_RATIOS_CENSO_OVERRIDE_WARNING to the bucket catalogue."""
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = now()
    payload = {
        "category": warning.category.value,
        "override_ratio": str(warning.override_ratio),
        "censo_derived_ratio": str(warning.censo_derived_ratio),
        "raw_afectacion_ratio": str(warning.raw_afectacion_ratio),
    }
    actor = "operator"
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PROFILE,
        object_id=warning.category.value,
        payload=payload,
    )
    repo = BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))
    catalogue = repo.load()
    repo.save(
        append_bucket_event(
            catalogue,
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=BucketEventType.LEDGER_RATIOS_CENSO_OVERRIDE_WARNING,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PROFILE,
                object_id=warning.category.value,
                payload=payload,
                payload_version=1,
            ),
        ),
    )


def _resolve_category(raw: str):
    from ...domain.categories import SpendingCategory

    try:
        return SpendingCategory(raw.strip())
    except ValueError as exc:
        raise _bad(
            tr("cli.app.ledger.ratios.unknown_category", default="Unknown spending category: {raw!r}", raw=raw),
        ) from exc


@ratios_app.command(
    "list",
    help=tr(
        "cli.app.ledger.ratios.list_help",
        default="List every per-category usage-ratio override on the active profile.",
    ),
)
def ratios_list(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List every per-category proportional-deduction override stored on the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.user_profile import CensoSyncService
    from ...domain.usage_ratios import (
        CensoRatioMismatchError,
        load_usage_ratios,
        load_usage_ratios_with_censo_guard,
    )
    from ._ledger_payloads import RatiosListResult

    bucket_id, profile_id = _ratios_bucket_and_profile()
    raw_afectacion = None
    if profile_id is not None:
        raw_afectacion = CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(
            profile_id=profile_id,
        )
    censo_mismatch: str | None = None
    try:
        profile = load_usage_ratios_with_censo_guard(
            bucket_id=bucket_id,
            raw_afectacion_ratio=raw_afectacion,
        )
    except CensoRatioMismatchError as exc:
        _log.debug("ledger ratios censo mismatch surfaced as warning", exc_info=True)
        censo_mismatch = str(exc)
        profile = load_usage_ratios(bucket_id=bucket_id)
    rows = [{"category": category.value, "ratio": str(ratio)} for category, ratio in profile.ratios.items()]
    payload = {
        "bucket_id": bucket_id,
        "rows": rows,
        "count": len(rows),
        "censo_mismatch": censo_mismatch,
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    if censo_mismatch is not None:
        lines.append(f"censo_mismatch\t{censo_mismatch}")
    lines.extend(f"{row['category']}\t{row['ratio']}" for row in rows)
    _emit_envelope(
        ctx,
        command="ledger.ratios.list",
        result=RatiosListResult.model_validate(payload),
        lines=lines,
    )


@ratios_app.command(
    "set",
    help=tr("cli.app.ledger.ratios.set_help", default="Set or replace one per-category usage-ratio override."),
)
def ratios_set(
    ctx: typer.Context,
    category: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.ratios.category_help", default="Spending category id (e.g. USAGE_RATIO_VEHICLE)."),
    ),
    ratio: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.ratios.ratio_help", default="Override ratio in the closed interval [0, 1]."),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Set or replace one per-category usage-ratio override on the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger import censo_override_warning, set_usage_ratio
    from ...application.user_profile import CensoSyncService
    from ._ledger_payloads import RatiosSetResult

    category_enum = _resolve_category(category)
    parsed = parse_decimal_amount(ratio, label="ratio")
    bucket_id, profile_id = _ratios_bucket_and_profile()
    prior = set_usage_ratio(bucket_id=bucket_id, category=category_enum, ratio=parsed)
    _emit_ratios_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_SET,
        category=category_enum.value,
        prior=prior,
        new=parsed,
    )
    if profile_id is not None:
        sync_service = CensoSyncService(bucket_id=bucket_id)
        raw_afectacion = sync_service.bound_raw_afectacion_ratio(profile_id=profile_id)
        warning = (
            censo_override_warning(
                category=category_enum,
                override_ratio=parsed,
                raw_afectacion_ratio=raw_afectacion if raw_afectacion is not None else parsed,
            )
            if raw_afectacion is not None
            else None
        )
        if warning is not None:
            _emit_ratios_censo_override_warning(bucket_id=bucket_id, warning=warning)
    payload = {"bucket_id": bucket_id, "category": category_enum.value, "ratio": str(parsed)}
    _emit_envelope(
        ctx,
        command="ledger.ratios.set",
        result=RatiosSetResult.model_validate(payload),
        lines=(f"bucket\t{bucket_id}", f"{category_enum.value}\t{parsed}"),
    )


@ratios_app.command(
    "unset",
    help=tr("cli.app.ledger.ratios.unset_help", default="Clear one per-category usage-ratio override."),
)
def ratios_unset(
    ctx: typer.Context,
    category: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.ratios.unset_category_help", default="Spending category id whose override to clear."),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Clear one per-category usage-ratio override from the active bucket."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger import unset_usage_ratio
    from ...domain.usage_ratios import UsageRatioValidationError
    from ._ledger_payloads import RatiosUnsetResult

    category_enum = _resolve_category(category)
    bucket_id = _ratios_bucket_id()
    try:
        prior = unset_usage_ratio(bucket_id=bucket_id, category=category_enum)
    except UsageRatioValidationError as exc:
        raise _bad(
            tr(
                "cli.app.ledger.ratios.no_override_error",
                default="No persisted override for category {category!r} on bucket {bucket_id!r}",
                category=category_enum.value,
                bucket_id=bucket_id,
            ),
        ) from exc
    _emit_ratios_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_RATIOS_UNSET,
        category=category_enum.value,
        prior=prior,
        new=None,
    )
    payload = {"bucket_id": bucket_id, "category": category_enum.value, "ratio": ""}
    _emit_envelope(
        ctx,
        command="ledger.ratios.unset",
        result=RatiosUnsetResult.model_validate(payload),
        lines=(f"bucket\t{bucket_id}", f"{category_enum.value}\t<unset>"),
    )


@ratios_app.command(
    "eligible",
    help=tr(
        "cli.app.ledger.ratios.eligible_help",
        default="List every category that may carry a per-category override.",
    ),
)
def ratios_eligible(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """List every ``SpendingCategory`` that may carry a per-category proportional-deduction override."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger import list_eligible_ratios_for_bucket
    from ._ledger_payloads import RatiosEligibleResult

    bucket_id = _ratios_bucket_id()
    rows = list_eligible_ratios_for_bucket(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        default = "" if row.default_ratio is None else str(row.default_ratio)
        override_marker = "X" if row.override_present else "."
        lines.append(
            f"{row.category.value}\t{row.proportionality_kind}\tdefault={default or '-'}\toverride={override_marker}",
        )
    _emit_envelope(
        ctx,
        command="ledger.ratios.eligible",
        result=RatiosEligibleResult.model_validate(payload),
        lines=lines,
    )


@ratios_app.command(
    "validate",
    help=tr(
        "cli.app.ledger.ratios.validate_help",
        default="Validate the per-category overrides against eligibility + bound rules.",
    ),
)
def ratios_validate(
    ctx: typer.Context,
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Validate per-category usage-ratio overrides against eligibility and bound rules without mutating state."""
    _activate_subcommand_output_language(ctx, output_language)
    from ...application.ledger import validate_ratios_for_bucket
    from ._ledger_payloads import RatiosValidateResult

    bucket_id = _ratios_bucket_id()
    report = validate_ratios_for_bucket(bucket_id=bucket_id)
    payload = report.model_dump(mode="json")
    lines = [
        f"bucket\t{bucket_id}",
        f"profile_present\t{report.profile_present}",
        f"eligible\t{report.eligible_count}",
        f"overrides\t{report.overrides_count}",
    ]
    if report.missing_overrides:
        lines.append("missing\t" + ",".join(c.value for c in report.missing_overrides))
    for finding in report.findings:
        detail = f"\t{finding.detail}" if finding.detail else ""
        lines.append(f"finding\t{finding.category.value}\t{finding.kind}{detail}")
    _emit_envelope(
        ctx,
        command="ledger.ratios.validate",
        result=RatiosValidateResult.model_validate(payload),
        lines=lines,
    )


__all__ = ["ratios_app", "register_ratios_commands"]
