"""Real-behavior CLI coverage: overdue deadline posture and rate preview.

``aeat app modelo work calculate`` on an overdue period must surface the
voluntary filing deadline and an explicitly unassessed Article 27 rate preview
in text mode and JSON. The preview carries a rate-reference date, never a
presentation date, and the notice makes no surcharge or interest liability
claim. An in-time period carries neither an overdue notice nor a preview.

These tests drive a real Modelo 130 calculate through the CLI and the profile
worker over an enrolled profile and a real ledger income row. The worker
observes the voluntary deadline from its own Europe/Madrid civil date, so the
expected overdue / in-time posture is derived from the registry deadline
windows the engine itself resolves (``resolve_filing_window``) around the
date the worker actually reads, bracketed by sampling that date before and
after the run.

Period selection is self-calibrating: rather than hardcode a filing year or
quarter, each test derives the supported horizon from the registry catalogue,
enumerates the M130 quarterly windows, and chooses the most recently closed
window (overdue) or the earliest still-open one (in time) for that date.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from ....application.modelo.work_plazo import ModeloWorkDeadlinePosture
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.period import Period, PeriodKind, registry_period_kind
from ....core.time.clock import today_madrid
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import (
    published_legal_reference,
    published_selected_revision_id,
    published_supported_filing_years,
)
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.plazo import resolve_filing_window
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_schema_envelope as _result
from .._modelo_rendering import _work_unit_deadline_output_from_posture
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_UNASSESSED_PREVIEW_NOTICE_CODE = "modelo.work.calculate.plazo_vencido_unassessed_preview"
_RECARGO_LEGAL_REF = "ley-58-2003:art-27.2"
_M130_CALCULATE_OPTIONS = (
    # Casilla 02 (gastos) is bucket-bound (ledger-aggregated) and cannot be
    # supplied via --casilla; immaterial to the recargo-notice assertions.
    "--casilla",
    "05=0.00",
    "--casilla",
    "06=0.00",
    "--binding",
    "irpf.previous_year_economic_activity_net_income=13000",
    "--binding",
    "modelo-130-resultados-negativos-anteriores=0",
)


def _natural_person_facts() -> dict[str, str]:
    """The application readiness baseline with the natural-person operator's identity."""
    facts = {
        fact.path: (str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value))
        for fact in MODELO_READY_PROFILE_FACTS
    }
    facts.update(
        {
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Readiness",
            "activities.description": "design",
        }
    )
    return facts


def _scope(client_id: UUID) -> AccessScope:
    """Grant the Modelo 130 work lifecycle the calculate route submits."""
    operation_ids = frozenset(
        {
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
            MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        }
    )
    return AccessScope(
        operations=operation_ids,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in operation_ids
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _seed_m130_income(bucket_id: str, *, filing_year: int, source_key: str) -> None:
    """Store one real actividad-economica income row for source-bound M130 casilla 01."""
    value_date = date(filing_year, 2, 15)
    # Transactions validate against registry facts, as they do under a CLI invocation's lease.
    with bundled_indexed_authority().operation():
        income = Transaction.model_validate(
            {
                "raw": RawTransaction(
                    provider_transaction_id=f"m130-income-{source_key}-{filing_year}",
                    booked_date=value_date,
                    value_date=value_date,
                    amount=Decimal("12000.00"),
                    currency="EUR",
                    counterparty="Cliente SA",
                    description=f"M130 oracle income {source_key}",
                    provenance=RawProvenance(
                        source_path=Path(__file__),
                        source_sha256="b" * 64,
                        source_row_index=1,
                        source_format=SourceFormat.MANUAL,
                        ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                        provider_name="manual-ledger",
                    ),
                    raw_fields={"source_kind": "m130_oracle_income", "source_key": source_key},
                ),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "business_classification": BusinessClassification.BUSINESS,
                "source_jurisdiction": "ES",
                "business_pct": None,
                "category_id": None,
                "taxable_base": Decimal("12000.00"),
                "iva_rate": None,
                "iva_amount": None,
                "irpf_category": "actividad_economica",
                "purchase_invoice_evidence_id": None,
                "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
                "classified_by": "manual",
            },
        )
    TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions((income,)))


@contextmanager
def _m130_session(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    seed: Callable[[str], None],
) -> Iterator[NativeApiCliSession[None]]:
    """Complete a natural-person operator, seed its income row and serve its native worker."""

    def prepare(profile_id: UUID, root: Path) -> None:
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            tuple(UserProfileFact(path=path, value=value) for path, value in _natural_person_facts().items()),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        seed(str(profile_id))

    with native_api_cli_session(tmp_path, scope_for_destination=_scope, prepare_profile=prepare) as session:
        yield session


def _create_m130_work_unit(session: NativeApiCliSession[None], *, filing_year: int, period: str) -> str:
    created = session.invoke_password(
        "app", "modelo", "work", "create",
        "--modelo", "130", "--year", str(filing_year), "--period", period,
        "--revision", _revision_id(filing_year, period),
    )  # fmt: skip
    assert created.exit_code == 0, f"{created.output}\n{session.runtime_failure_observations!r}"
    work_unit_id = _result(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str) and work_unit_id, created.output
    return work_unit_id


def _calculate_m130(session: NativeApiCliSession[None], work_unit_id: str, *, output_format: str = "json") -> Any:
    result = session.invoke_password(
        "--language",
        "en",
        "app",
        "modelo",
        "work",
        "calculate",
        work_unit_id,
        *_M130_CALCULATE_OPTIONS,
        output_format=output_format,
    )
    assert result.exit_code == 0, f"{result.output}\n{session.runtime_failure_observations!r}"
    assert "Traceback" not in result.output
    return result


def _closes_on(filing_year: int, period_token: str) -> date:
    window = resolve_filing_window(
        "130",
        filing_year,
        Period.from_year_and_code(filing_year, period_token),
    )
    assert window is not None, f"registry must register an M130 {period_token} {filing_year} deadline window"
    return window.closes_on


def _registered_quarterly_closes() -> list[tuple[int, str, date]]:
    """(filing_year, period_token, closes_on) for every supported M130 quarter with a registry window."""
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    pairs = [
        (filing_year, token, _closes_on(filing_year, token))
        for filing_year in supported_years.years
        for token in {
            window.period.registry_token
            for modelo, _revision, window in DeadlineEngine().deadline_windows(filing_year)
            if modelo == "130" and registry_period_kind(window.period.registry_token) is PeriodKind.QUARTERLY
        }
    ]
    return sorted(pairs, key=lambda pair: pair[2])


def _overdue_case(observed_on: date) -> tuple[int, str, date]:
    """The most recently closed supported M130 quarter, as seen on ``observed_on``."""
    closed = [case for case in _registered_quarterly_closes() if case[2] < observed_on]
    assert closed, f"no supported M130 window has closed by {observed_on}"
    return closed[-1]


def _in_time_case(observed_on: date) -> tuple[int, str, date]:
    """The earliest supported M130 quarter still open on ``observed_on``."""
    still_open = [case for case in _registered_quarterly_closes() if case[2] >= observed_on]
    assert still_open, f"the supported registry horizon has no M130 window still open on {observed_on}"
    return still_open[0]


def _revision_id(filing_year: int, period_token: str) -> str:
    """Return the canonical law-selected M130 revision for one test coordinate."""
    return published_selected_revision_id("130", filing_year=filing_year, period=period_token)


def test_overdue_posture_fallback_emits_null_preview_without_rate_wording(
    *,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The real renderer emits a null preview and no displayed-rate warning."""
    deadline, notices = _work_unit_deadline_output_from_posture(
        ModeloWorkDeadlinePosture(
            closes_on=date(2026, 1, 30),
            nominal_closes_on=date(2026, 1, 30),
            holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
            days_overdue=1,
        ),
    )

    assert deadline is not None
    assert deadline.days_overdue == 1
    assert deadline.conditional_recargo_preview is None
    assert deadline.model_dump(mode="json")["conditional_recargo_preview"] is None
    assert len(notices) == 1
    context = notices[0].context
    assert context is not None
    assert context["legal_refs"] == _RECARGO_LEGAL_REF
    assert context["article_27_assessment_status"] == "unassessed"
    message = notices[0].message.lower()
    assert "displayed rate" not in message
    assert "previsualización no evaluada" not in message

    legal_entry = published_legal_reference(_RECARGO_LEGAL_REF)
    assert legal_entry.corpus_ref
    assert legal_entry.required_text


def test_calculate_overdue_period_surfaces_unassessed_preview_with_legal_context(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An overdue M130 period carries an unassessed preview and deadline posture.

    A quarter whose voluntary window has already closed is selected from the
    registry's M130 deadline windows, so once a calculate runs against it the
    envelope MUST carry an explicit ``unassessed`` status, a binding legal
    reference, and a non-null ``result.deadline`` overdue posture. Text and
    JSON must expose a conditional preview rather than a liability claim.
    """
    observed_before = today_madrid()
    filing_year, period, closes_on = _overdue_case(observed_before)

    with _m130_session(
        tmp_path,
        authority_operation,
        lambda bucket_id: _seed_m130_income(bucket_id, filing_year=filing_year, source_key="recargo-overdue"),
    ) as session:
        work_unit_id = _create_m130_work_unit(session, filing_year=filing_year, period=period)
        result = _calculate_m130(session, work_unit_id)
        text_result = _calculate_m130(session, work_unit_id, output_format="text")
    observed_after = today_madrid()

    envelope = json.loads(result.output)
    inner = _result(result.output)
    notices = unwrap_envelope_notices(result.output)

    # JSON status is no longer a bare success: a warning notice rode the spine.
    assert envelope["status"] == "warning", envelope

    preview_notices = [notice for notice in notices if notice["code"] == _UNASSESSED_PREVIEW_NOTICE_CODE]
    assert len(preview_notices) == 1, f"expected exactly one unassessed-preview notice; got {notices}"
    preview_notice = preview_notices[0]
    assert preview_notice["severity"] == "warning"
    assert "Art. 27" in preview_notice["message"]
    context = preview_notice["context"]
    assert context is not None, "preview notice must carry structured legal context"
    assert context.get("legal_refs") == _RECARGO_LEGAL_REF, "preview notice context must carry binding legal_refs"
    assert context.get("days_overdue"), "preview notice context must carry the overdue posture"
    assert context.get("article_27_assessment_status") == "unassessed"
    assert "presentation_date" not in context

    deadline = inner["deadline"]
    assert deadline is not None, "result.deadline must be populated for a resolvable period"
    assert deadline["closes_on"] == closes_on.isoformat()
    assert deadline["days_overdue"] is not None and int(deadline["days_overdue"]) >= 1
    assert deadline["days_remaining"] is None
    preview = deadline["conditional_recargo_preview"]
    assert preview is not None, "an overdue posture must resolve a rate preview"
    assert preview["legal_ref"] == _RECARGO_LEGAL_REF
    assert preview["assessment_status"] == "unassessed"
    # The worker's own civil date is the rate reference, never a presentation date.
    assert preview["rate_reference_on"] in {observed_before.isoformat(), observed_after.isoformat()}
    assert int(deadline["days_overdue"]) == (date.fromisoformat(preview["rate_reference_on"]) - closes_on).days
    assert "presentation_date" not in preview

    # Text mode exposes the same posture and explicitly unassessed preview.
    assert "Art. 27" in text_result.output
    assert "days_overdue\t" in text_result.output
    assert "conditional_recargo_preview_assessment_status\tunassessed" in text_result.output


def test_calculate_in_time_period_carries_no_unassessed_preview_notice(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An in-time M130 period carries no overdue notice or rate preview.

    Anti-tautology converse of the overdue test: a quarter whose voluntary
    window is still open is selected from the registry's M130 deadline
    windows, so the calculate envelope MUST NOT carry the overdue notice and
    ``result.deadline`` reports ``days_remaining`` with no overdue posture and
    no rate preview.
    """
    observed_before = today_madrid()
    filing_year, period, closes_on = _in_time_case(observed_before)

    with _m130_session(
        tmp_path,
        authority_operation,
        lambda bucket_id: _seed_m130_income(bucket_id, filing_year=filing_year, source_key="recargo-in-time"),
    ) as session:
        work_unit_id = _create_m130_work_unit(session, filing_year=filing_year, period=period)
        result = _calculate_m130(session, work_unit_id)
    observed_after = today_madrid()

    inner = _result(result.output)
    notices = unwrap_envelope_notices(result.output)

    assert [notice for notice in notices if notice["code"] == _UNASSESSED_PREVIEW_NOTICE_CODE] == [], (
        f"an in-time period must raise no overdue-preview notice; got {notices}"
    )

    deadline = inner["deadline"]
    assert deadline is not None, "result.deadline must be populated for a resolvable period"
    assert deadline["closes_on"] == closes_on.isoformat()
    assert deadline["days_remaining"] is not None
    assert int(deadline["days_remaining"]) in {
        (closes_on - observed_before).days,
        (closes_on - observed_after).days,
    }
    assert deadline["days_overdue"] is None
    assert deadline["conditional_recargo_preview"] is None
