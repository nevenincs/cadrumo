"""A Modelo 190 whose per-perceptor detail is empty must not be granted verificado completo.

Runs the live CLI parser end to end against the published registry: a filer
whose ledger holds four quarterly received professional invoices, each with 15%
retención practised, and whose per-perceptor withholding store is empty because
the withholding recognition path does not support that applicable year.

``work calculate`` still succeeds and materialises the percepciones count as an
explicit zero, because the bound casilla needs its fact and the pull surface
shares that resolver. ``work verify`` is where the zero stops: it exits 1 with a
blocking finding naming the modelo, the year, the source family and the remedy,
so the all-blank resumen anual cannot be filed locally (local filing requires a
granted verification).

The genuine nil filer keeps working: with every quarterly Modelo 111 window
attested as having satisfied no renta subject to retención, and nothing in the
ledger contradicting it, the same revision verifies and the disclosure survives
as an advisory.
"""

from __future__ import annotations

import json
import re
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.invoices.catalogue_add_operation import INVOICE_ADD_OPERATION_DEFINITION_ID
from ....application.ledger.ledger_add_contracts import LEDGER_ADD_OPERATION_DEFINITION_ID
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.i18n.render import lookup_translation
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_FILING_YEAR = "2022"
_ADVISER_NIF = "B12345674"
_ADVISER_NAME = "Asesoria Profesional SL"
_QUARTERLY_INVOICE_DATES = ("2022-03-20", "2022-06-20", "2022-09-20", "2022-12-20")
_ALL_QUARTERS_ATTESTED = "2022:1T,2022:2T,2022:3T,2022:4T"
_LEDGER_EVIDENCE_FINDING_KEY = "application.modelo.findings.withholding_detail_absent_against_ledger_evidence"


def _scope(client_id: UUID) -> AccessScope:
    """Grant source creation and the Modelo 190 lifecycle across all periods."""
    operation_ids = frozenset(
        {
            INVOICE_ADD_OPERATION_DEFINITION_ID,
            LEDGER_ADD_OPERATION_DEFINITION_ID,
            MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
            MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
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


def _profile_session(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    *,
    attested_periods: str | None = None,
) -> AbstractContextManager[NativeApiCliSession[None]]:
    """Complete one enrolled retenedor and serve its real native profile worker."""

    def prepare(profile_id: UUID, root: Path) -> None:
        values = {
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Retenedor",
            "activities.description": "design",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "censo.activity_start_date": "2020-01-01",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            "withholding.colegio_concertado": "false",
        }
        if attested_periods is not None:
            values["withholding.modelo_111_no_retenciones_periods"] = attested_periods
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            tuple(UserProfileFact(path=path, value=value) for path, value in values.items()),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE

    return native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope,
        prepare_profile=prepare,
    )


def _add_received_professional_invoice(session: NativeApiCliSession[None], *, number: str, invoice_date: str) -> str:
    """Mint one received professional invoice with 1000.00 base and 150.00 withheld."""
    created = session.invoke_password(
        "app", "ledger", "invoice", "add",
        "--kind", "received",
        "--counterparty-name", _ADVISER_NAME,
        "--counterparty-nif", _ADVISER_NIF,
        "--invoice-number", number,
        "--invoice-date", invoice_date,
        "--country-code", "ES",
        "--taxable-base", "1000.00", "--iva-rate", "21",
        "--retention-rate", "0.15", "--retention-amount", "150.00",
        "--iva-category", "domestic_general",
    )  # fmt: skip
    assert created.exit_code == 0, f"{created.output}\n{session.runtime_failure_observations!r}"
    invoice_id = _payload(created.output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, created.output
    return invoice_id


def _add_outgoing_professional_payment(session: NativeApiCliSession[None], *, description: str, paid_on: str) -> None:
    """Record one bank payment to a professional, carrying the IRPF withholding category."""
    added = session.invoke_password(
        "app", "ledger", "add",
        "--date", paid_on, "--value-date", paid_on,
        "--amount", "1000.00",
        "--direction", "OUTGOING",
        "--description", description,
        "--counterparty", _ADVISER_NAME,
        "--classification", "BUSINESS",
        "--irpf-category", "actividad_economica",
    )  # fmt: skip
    assert added.exit_code == 0, added.output


def _create_190_work_unit(session: NativeApiCliSession[None]) -> str:
    created = session.invoke_password(
        "app", "modelo", "work", "create",
        "--modelo", "190", "--year", _FILING_YEAR, "--period", "0A",
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(created.output))
    work_unit_id = payload["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate(session: NativeApiCliSession[None], work_unit_id: str) -> str:
    calculated = session.invoke_password(
        "--language",
        "en",
        "app",
        "modelo",
        "work",
        "calculate",
        work_unit_id,
    )
    assert calculated.exit_code == 0, calculated.output
    payload = _payload(calculated.output)
    values = STR_KEYED_MAPPING_ADAPTER.validate_python(payload["casilla_values"])
    assert values["decl.total-percepciones"] == "0", calculated.output
    assert values["decl.percepciones-total"] == "0.00", calculated.output
    assert values["decl.retenciones-total"] == "0.00", calculated.output
    assert any(
        "no per-perceptor-clave observations are persisted" in notice.get("context", {}).get("detail", "")
        for notice in unwrap_envelope_notices(calculated.output)
    ), calculated.output
    calculation_revision_id = payload["calculation_revision_id"]
    assert isinstance(calculation_revision_id, str)
    return calculation_revision_id


def _finding_facts(output: str, *, source_family: str = "withholding") -> dict[str, str]:
    """Return the notice context of the one withholding-detail finding.

    The verify payload renders each finding into localised prose; the
    locale-neutral facts ride the envelope notice channel, which is what a
    machine consumer routes on.
    """
    matching = [
        STR_KEYED_MAPPING_ADAPTER.validate_python(notice["context"])
        for notice in unwrap_envelope_notices(output)
        if notice["context"] is not None
        and STR_KEYED_MAPPING_ADAPTER.validate_python(notice["context"]).get("source_family") == source_family
    ]
    assert len(matching) == 1, output
    return {key: str(value) for key, value in matching[0].items()}


def test_verify_refuses_an_empty_190_contradicted_by_invoice_retenciones(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The four practised retenciones the store never received block the resumen anual."""
    with _profile_session(tmp_path, authority_operation) as session:
        for index, invoice_date in enumerate(_QUARTERLY_INVOICE_DATES, start=1):
            _add_received_professional_invoice(session, number=f"F-ASESOR-2022-{index:03d}", invoice_date=invoice_date)
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))

        verified = session.invoke_password(
            "app",
            "modelo",
            "work",
            "verify",
            calculation_revision_id,
        )

        assert verified.exit_code == 1, verified.output
        payload = _payload(verified.output)
        assert payload["granted_verificado_completo"] is False
        facts = _finding_facts(verified.output)
        assert facts["severity"] == "blocking"
        assert facts["modelo"] == "190"
        assert facts["filing_year"] == "2022"
        assert facts["source_family"] == "withholding"
        assert facts["source_modelo"] == "111"
        assert facts["contradicting_invoice_count"] == "4"
        assert facts["contradicting_ledger_row_count"] == "0"
        assert facts["legal_refs"] != ""


def test_verify_refuses_an_attested_nil_190_contradicted_by_a_ledger_payment(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """A professional paid through the bank ledger alone still owes its perceptor record.

    The obligation follows from satisfying the renta, so the attestation covering
    every quarterly window does not survive a payment the ledger records.
    """
    with _profile_session(tmp_path, authority_operation, attested_periods=_ALL_QUARTERS_ATTESTED) as session:
        _add_outgoing_professional_payment(session, description="Pago asesoria fiscal 3T", paid_on="2022-07-04")
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))

        verified = session.invoke_password(
            "app",
            "modelo",
            "work",
            "verify",
            calculation_revision_id,
        )

        assert verified.exit_code == 1, verified.output
        assert _payload(verified.output)["granted_verificado_completo"] is False
        facts = _finding_facts(verified.output)
        assert facts["severity"] == "blocking"
        assert facts["contradicting_invoice_count"] == "0"
        assert facts["contradicting_ledger_row_count"] == "1"
        assert facts["attested_periods"] == "1T|2T|3T|4T"


def test_verify_refuses_an_empty_190_that_nothing_attests(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An empty detail store with no ledger evidence and no attestation is still unproven."""
    with _profile_session(tmp_path, authority_operation) as session:
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))

        verified = session.invoke_password(
            "app",
            "modelo",
            "work",
            "verify",
            calculation_revision_id,
        )

        assert verified.exit_code == 1, verified.output
        facts = _finding_facts(verified.output)
        assert facts["severity"] == "blocking"
        assert facts["contradicting_invoice_count"] == "0"
        assert facts["unattested_periods"] == "1T|2T|3T|4T"
        assert facts["attestation_profile_path"] == "withholding.modelo_111_no_retenciones_periods"


def test_verify_grants_a_fully_attested_nil_190(tmp_path: Path, authority_operation: PinnedAuthorityOperation) -> None:
    """Every quarter attested and a clean ledger keeps the nil filer's path open."""
    with _profile_session(tmp_path, authority_operation, attested_periods=_ALL_QUARTERS_ATTESTED) as session:
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))

        verified = session.invoke_password(
            "app",
            "modelo",
            "work",
            "verify",
            calculation_revision_id,
        )

        assert verified.exit_code == 0, verified.output
        payload = _payload(verified.output)
        assert payload["granted_verificado_completo"] is True
        facts = _finding_facts(verified.output)
        assert facts["severity"] == "warning"
        assert facts["attested_periods"] == "1T|2T|3T|4T"


def test_the_refusal_renders_in_every_supported_locale(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Transport facts stay stable while the operator-facing prose is translated."""
    with _profile_session(tmp_path, authority_operation) as session:
        _add_received_professional_invoice(
            session, number="F-ASESOR-2022-001", invoice_date=_QUARTERLY_INVOICE_DATES[0]
        )
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))

        rendered: dict[str, str] = {}
        for language in ("en", "es", "ca", "hu"):
            verified = session.invoke_password(
                "--language",
                language,
                "app",
                "modelo",
                "work",
                "verify",
                calculation_revision_id,
            )
            assert verified.exit_code == 1, verified.output
            assert _payload(verified.output)["granted_verificado_completo"] is False
            facts = _finding_facts(verified.output)
            assert facts["severity"] == "blocking"
            assert facts["contradicting_invoice_count"] == "1"
            rendered[language] = verified.output

        assert len(set(rendered.values())) == 4
        for language, output in rendered.items():
            template = lookup_translation(_LEDGER_EVIDENCE_FINDING_KEY, locale=language)
            assert template is not None, language
            # The prose after the last fact is static, so the remedy reaches the operator verbatim.
            remedy = re.split(r"%\{[a-z_]+\}", template)[-1].strip()
            assert remedy, language
            assert remedy in output, (language, remedy)


def test_a_partially_attested_year_is_still_refused(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Three attested quarters leave the fourth's percepciones unaccounted for."""
    with _profile_session(tmp_path, authority_operation, attested_periods="2022:1T,2022:2T,2022:3T") as session:
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))

        verified = session.invoke_password(
            "app",
            "modelo",
            "work",
            "verify",
            calculation_revision_id,
        )

        assert verified.exit_code == 1, verified.output
        facts = _finding_facts(verified.output)
        assert facts["severity"] == "blocking"
        assert facts["attested_periods"] == "1T|2T|3T"
        assert facts["unattested_periods"] == "4T"


def test_the_refused_revision_cannot_be_filed_locally(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The gate closes the filing path, not only the verify report."""
    with _profile_session(tmp_path, authority_operation) as session:
        _add_received_professional_invoice(
            session, number="F-ASESOR-2022-001", invoice_date=_QUARTERLY_INVOICE_DATES[0]
        )
        calculation_revision_id = _calculate(session, _create_190_work_unit(session))
        refused = session.invoke_password(
            "app",
            "modelo",
            "work",
            "verify",
            calculation_revision_id,
        )
        assert refused.exit_code == 1, refused.output
        assert _payload(refused.output)["granted_verificado_completo"] is False
        assert _finding_facts(refused.output)["contradicting_invoice_count"] == "1"

        filed = session.invoke_password("app", "modelo", "work", "file", calculation_revision_id)

        assert filed.exit_code == 1, filed.output
        error = json.loads(filed.output)["error"]
        assert error["code"] == "ERROR_MODELO_CALCULATION_REVISION_STATE", filed.output
        assert error["context"]["calculation_revision_id"] == calculation_revision_id
        assert error["context"]["state"] == "borrador"
        with password_profile_session(session.profile_id, authority_operation):
            assert not ModeloRecordCatalogueRepository(bucket_id=str(session.profile_id)).load().records
