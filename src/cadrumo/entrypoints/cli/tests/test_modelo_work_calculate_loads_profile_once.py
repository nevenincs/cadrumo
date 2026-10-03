"""``aeat app modelo work calculate`` decrypts the profile once for the whole command.

The command runs the readiness gate twice, the IVA-wallet and ledger gates,
the profile binding tier, the source mesh (relation prefill, previous-filing
carry, Renta expenses, the Modelo 303 annual-summary scope) and the
post-calculation advisories. Each of those used to decrypt the profile capsule
on its own; the calculation now loads it once and every consumer reads that
record.

The CLI no longer runs the calculation itself: it submits the registered
operation to the profile's own worker process, which holds the profile. So the
claim is proven where each part of it now lives. Through the real CLI and its
native worker, each command reaches its outcome while the CLI side decrypts no
profile at all. In the production executor the worker hosts, one calculation
decrypts the profile exactly once, counted at the capsule store so a consumer
that bypasses the record repository is counted too.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ....application.aggregation.retenciones import (
    Modelo180PropertyEvidence,
    Modelo180StructuredAddress,
    RetencionObservation,
)
from ....application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ....application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
)
from ....application.modelo.aggregate_contracts import MODELO_AGGREGATE_OPERATION_DEFINITION_ID
from ....application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
)
from ....application.modelo.m303_attestation_operation import MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ....application.modelo.profile_readiness_gate import load_modelo_work_profile, require_profile_ready_for_work_unit
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.capsule_record import LoadedProfileRecord, ProfileRecordStore
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.aggregation import AggregationCaptureKind, BindingSourceKind, RetencionScheme
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope
from ...adapter_composition import build_retencion_observation_ports
from ...tests.modelo_operator_work_storage import seeded_operator_work
from ._modelo_work_ux_support import (
    m111_withholding_aggregate_arguments,
    m111_withholding_invoice_arguments,
    operator_profile_facts,
)
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_OPERATIONS = frozenset(
    {
        INVOICE_ADD_OPERATION_DEFINITION_ID,
        MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
    }
)


@pytest.fixture
def profile_decrypts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every profile-record decrypt in this process, still performing it."""
    decrypts: list[str] = []
    real_load = ProfileRecordStore.load

    def counting_load(self: ProfileRecordStore) -> LoadedProfileRecord:
        decrypts.append(str(self.session.profile_id))
        return real_load(self)

    monkeypatch.setattr(ProfileRecordStore, "load", counting_load)
    return decrypts


def _scope(client_id: UUID) -> AccessScope:
    """Grant the work lifecycle and the evidence captures these commands submit."""
    return AccessScope(
        operations=_OPERATIONS,
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
                    for definition_id in _OPERATIONS
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


@contextmanager
def _operator_session(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> Iterator[NativeApiCliSession[None]]:
    """Enrol the operator profile the modelo work UX suites run against, served by its worker."""

    def prepare(profile_id: UUID, root: Path) -> None:
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            tuple(UserProfileFact(path=path, value=value) for path, value in operator_profile_facts().items()),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE

    with native_api_cli_session(tmp_path, scope_for_destination=_scope, prepare_profile=prepare) as session:
        yield session


def _invoke(session: NativeApiCliSession[None], *arguments: str) -> tuple[int, str]:
    result = session.invoke_password(*arguments)
    return result.exit_code, result.output


def _create_work_unit(
    session: NativeApiCliSession[None], *, modelo: str, year: int, period: str, revision: str | None = None
) -> str:
    """Create a work unit through the real CLI; without a revision, on the one the law selects."""
    exit_code, output = _invoke(
        session,
        "app", "modelo", "work", "create",
        "--modelo", modelo, "--year", str(year), "--period", period,
        *(() if revision is None else ("--revision", revision)),
    )  # fmt: skip
    assert exit_code == 0, output
    work_unit_id = unwrap_schema_envelope(output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _capture_m111_invoice_withholding(session: NativeApiCliSession[None]) -> None:
    """Record one received professional invoice's paid retención, so Modelo 111 is not an all-blank quarter."""
    exit_code, output = _invoke(session, *m111_withholding_invoice_arguments())
    assert exit_code == 0, output
    invoice_id = unwrap_schema_envelope(output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, output
    exit_code, output = _invoke(session, *m111_withholding_aggregate_arguments(invoice_id))
    assert exit_code == 0, output


def _capture_m115_invoice_withholding(session: NativeApiCliSession[None]) -> None:
    """Record one received urban-rent invoice's paid retención as Modelo 115 2025 1T evidence.

    The invoice has a 2700.00 base and a 19% retención of 513.00; the settlement is
    its grand total (2700.00 + 21% IVA = 3267.00) less the retención: 2754.00.
    """
    paid_on = date(2025, 3, 15)
    exit_code, output = _invoke(
        session,
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-name", "Arrendador Ejemplo SL",
        "--counterparty-nif", "B12345674",
        "--invoice-number", "M115-RENT-2025-001",
        "--invoice-date", paid_on.isoformat(),
        "--country-code", "ES",
        "--taxable-base", "2700.00", "--iva-rate", "21",
        "--retention-rate", "0.19", "--retention-amount", "513.00",
        "--iva-category", "domestic_general",
    )  # fmt: skip
    assert exit_code == 0, output
    invoice_id = unwrap_schema_envelope(output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, output
    request = InvoiceWithholdingEvidenceRequest(
        invoice_id=invoice_id,
        income_kind=WithholdingIncomeKind.URBAN_RENT,
        scheme="arrendamiento_urbano",
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="m115-rent-payment-2025-03-15",
        payment_occurred_on=paid_on,
        allocation_id="m115-rent-allocation-1",
        allocated_base=Decimal("2700.00"),
        allocated_withholding=Decimal("513.00"),
        allocated_settlement=Decimal("2754.00"),
        idempotency_key="m115-rent-allocation-1",
        modelo_180_property=Modelo180PropertyEvidence(
            property_key="m115-rent-property",
            situation="1",
            cadastral_reference="1234567VK4713C0001XY",
            address=Modelo180StructuredAddress(
                province_code="28",
                municipality_code="079",
                municipality="Madrid",
                locality="Madrid",
                postal_code="28001",
                street_type="CL",
                street_name="Ejemplo",
                number_type="NUM",
                house_number="1",
            ),
            recipient_province_code="28",
            modality="1",
            accrual_year=2025,
            withholding_percentage=Decimal("19.00"),
        ),
    )
    exit_code, output = _invoke(
        session,
        "app", "modelo", "aggregate",
        "--modelo", "115", "--year", "2025", "--period", "1T",
        "--received-invoice-retencion", request.model_dump_json(),
    )  # fmt: skip
    assert exit_code == 0, output


def _calculate(session: NativeApiCliSession[None], decrypts: list[str], *arguments: str) -> tuple[int, str]:
    """Run one real ``work calculate`` and keep only the decrypts this process performed for it."""
    decrypts.clear()
    return _invoke(session, "app", "modelo", "work", "calculate", *arguments)


def test_m111_calculate_succeeds_through_its_worker_without_a_client_decrypt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, profile_decrypts: list[str]
) -> None:
    with _operator_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session, modelo="111", year=2025, period="1T", revision="2019-y-siguientes")
        _capture_m111_invoice_withholding(session)

        exit_code, output = _calculate(session, profile_decrypts, work_unit_id)

    assert exit_code == 0, output
    assert profile_decrypts == [], profile_decrypts


def test_m115_calculate_succeeds_through_its_worker_without_a_client_decrypt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, profile_decrypts: list[str]
) -> None:
    with _operator_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session, modelo="115", year=2025, period="1T")
        _capture_m115_invoice_withholding(session)

        exit_code, output = _calculate(session, profile_decrypts, work_unit_id, "--casilla", "04=0")

    assert exit_code == 0, output
    assert profile_decrypts == [], profile_decrypts


def test_m100_calculate_reaches_its_outcome_without_a_client_decrypt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, profile_decrypts: list[str]
) -> None:
    """The Modelo 100 scenario is counted up to whatever outcome the command reaches."""
    with _operator_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session, modelo="100", year=2024, period="0A", revision="2024")

        _, output = _calculate(
            session,
            profile_decrypts,
            work_unit_id,
            "--binding",
            "renta-modelo-100-estimacion-directa-es-normal=1",
        )

    envelope = json.loads(output)
    assert envelope["command"] == "modelo.work.calculate", output
    # Any outcome counts, except never reaching the worker that hosts the calculation.
    assert (envelope.get("error") or {}).get("code") != "REFUSED_LOCAL_RUNTIME", output
    assert profile_decrypts == [], (profile_decrypts, output)


def test_m303_attestation_cli_admits_only_a_sanitized_secure_reference_without_a_client_decrypt(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, profile_decrypts: list[str]
) -> None:
    with _operator_session(tmp_path, authority_operation) as session:
        profile_decrypts.clear()
        exit_code, output = _invoke(
            session,
            "app",
            "modelo",
            "work",
            "attest-m303-exonerado-390",
            "--year",
            "2025",
            # Only the year's last return asks the Modelo 390 exemption
            # (DP30301 Nota 4), so only its period admits the attestation.
            "--period",
            "4T",
            "--observed-at",
            "2025-12-31T12:00:00+00:00",
        )

    assert exit_code == 0, output
    payload = unwrap_schema_envelope(output)
    attachment_id = payload["attachment_id"]
    sha256 = payload["sha256"]
    assert isinstance(attachment_id, str) and len(attachment_id) == 64
    assert attachment_id == sha256
    assert payload["filing_year"] == 2025
    assert payload["period"] == {"filing_year": 2025, "code": "4T"}
    assert "profile_witness" not in output
    assert "attachment:" not in output
    assert "filing_evidence_reference" not in output
    assert profile_decrypts == [], profile_decrypts


def _store_one_m111_retencion(bucket_id: str, period: Period) -> None:
    """Store one paid professional retención, so the Modelo 111 quarter is not all blank."""
    build_retencion_observation_ports(bucket_id=bucket_id).repository.replace_observations(
        modelo="111",
        filing_year=period.filing_year,
        period=period,
        observations=(
            RetencionObservation(
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_object_id="a" * 64,
                perceptor_nif="B12345674",
                perceptor_name="Asesoria Profesional SL",
                scheme=RetencionScheme("actividades_profesionales"),
                taxable_base=Decimal("1000.00"),
                retencion_amount=Decimal("150.00"),
                accrued_on="2025-02-15",
            ),
        ),
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period_code"),
    (("111", 2025, "1T"), ("130", 2026, "1T")),
)
def test_the_hosted_calculate_executor_decrypts_the_profile_once(
    tmp_path: Path, profile_decrypts: list[str], modelo: str, filing_year: int, period_code: str
) -> None:
    """The production executor the worker hosts reads one decrypted record for the whole calculation."""
    with seeded_operator_work(tmp_path, modelo=modelo, filing_year=filing_year, period_code=period_code) as work:
        if modelo == "111":
            _store_one_m111_retencion(work.work_unit.bucket_id, work.work_unit.period)
        profile_decrypts.clear()

        work.recalculate()

        assert len(profile_decrypts) == 1, profile_decrypts


def test_the_readiness_gate_hands_back_the_profile_it_checked(tmp_path: Path) -> None:
    """Consumers downstream of the gate read the very record the gate refused or admitted."""
    with seeded_operator_work(tmp_path, modelo="111", filing_year=2025, period_code="1T") as work:
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        operation = work.operation
        loaded = load_modelo_work_profile(
            bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context()
        )
        assert loaded is not None
        checked = require_profile_ready_for_work_unit(
            work.work_unit,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
            profile=loaded,
        )
        loaded_by_gate = require_profile_ready_for_work_unit(
            work.work_unit,
            profile_decode_context=operation.profile_decode_context(),
            operation=operation,
        )

    assert checked is loaded
    assert loaded_by_gate.record == loaded.record
