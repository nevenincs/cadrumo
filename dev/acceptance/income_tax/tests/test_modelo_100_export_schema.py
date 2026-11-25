"""Real Modelo 100 exports held to the bundled official XSD of their edition.

Calculate, verify and export run on the real store and registry against a synthetic
filer. The XSD oracle is independent of the exporter: libxml2 compiles the official
file with only its illegal regular-expression escapes removed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from lxml import etree

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.aggregation.tests.inventory_source_support import closed_no_stock_ledger
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import build_runtime_schema_provider
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.household_row_fact_gate import ModeloHouseholdRowFactUnstatedError
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.export_xml_dictionary import xml_dictionary_entries
from cadrumo.domain.contribuyente.descendant_facts import descendant_facts_from_list
from cadrumo.domain.contribuyente.inventory.records import InventoryLedgerDocument
from cadrumo.domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from cadrumo.domain.modelos.errors import ModeloExportError
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.tests.profile_persistence.eligible_descendants_support import eligible_descendants
from cadrumo.entrypoints.tests.profile_persistence.general_iva_profile_facts_support import renta_single_taxpayer_facts
from cadrumo.entrypoints.tests.profile_persistence.imputation_export_support import (
    CASH,
    DEVENGO,
    OFFICIAL_M130_C19,
    persist_ledger,
    register_refund_account,
    verify_and_export,
)
from cadrumo.entrypoints.tests.profile_persistence.m130_m100_annual_support import (
    BUCKET_ID,
    M100_ANNUAL_PERIOD,
    OPERATOR_SCOPE_PORTS,
    T0,
    TAX_ID,
    YEAR,
    autonomaworkflow_profile,
    calculate_revision_from_bucket_aggregation,
    export_revision_for_test,
    import_official_m130_result_observation,
    m100_non_relation_zero_bindings,
    seed_prior_year_m100,
    verify_revision_for_test,
)
from cadrumo.tests.env_scope import ready_clave_settings
from dev.registry.record_design_xsd_support import bundled_modelo_100_xsds, record_design_schema_violations

__all__ = ["secure_objects"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_ACTIVITY_KEY = "A05"
_DESCENDANT_NAME_FACT = "renta_family.descendiente.apellidos_nombre"
_ACTIVITY_BLOCK = "DatosEconomicos/TomaDatosAmpliada/RegEstimaDirecta/ActividadEstDirecta"


def _box(field_id: str) -> CasillaId:
    """Return the edition's box for a schema field, from the dictionary that maps them."""
    provider = build_runtime_schema_provider(
        filing_year=YEAR,
        period=Period.from_year_and_code(YEAR, M100_ANNUAL_PERIOD),
        modelos=("100",),
        operation=published_authority_operation(),
    )
    entries = xml_dictionary_entries(
        provider.get_snapshot("100").revision.export_layouts[0],
        sources=provider.sources,
        source_payloads=provider.source_payloads,
        casillas=provider.get_snapshot("100").revision.casillas,
    )
    casilla = next(entry.casilla_id for entry in entries if entry.field_id == field_id)
    assert casilla is not None
    return casilla


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _edition_xsd(year: int) -> Path:
    matches = [xsd for xsd in bundled_modelo_100_xsds() if f"ejercicio-{year}" in xsd.name]
    assert len(matches) == 1, matches
    return matches[0]


def _seed_filer(*, criterion: str, family: tuple[UserProfileFact, ...] = ()) -> None:
    stated = {fact.path for fact in family}
    dated = tuple(
        UserProfileFact.model_validate(
            {"path": path, "value": value, "valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
        )
        for year in (YEAR, YEAR + 1)
        for path, value in (
            ("irpf.activity_income_imputation_criterion", criterion),
            ("irpf.codigo_comercio_accounting", False),
        )
    )
    single = tuple(
        fact for fact in renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)) if fact.path not in stated
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=TAX_ID),
                    UserProfileFact(path="identity.name", value="Annual"),
                    UserProfileFact(path="identity.surnames", value="Renta Tester"),
                    UserProfileFact(path="activities.description", value="design services"),
                    # An epigraph outside group 861 proves the filer carries on no urban rental as an activity,
                    # so that credit class reads as a proven zero rather than as unknown.
                    UserProfileFact(path="activities.iae_epigraph", value="844"),
                    UserProfileFact(path="censo.activity_start_date", value=date(YEAR - 4, 1, 1)),
                    *single,
                    *family,
                    *dated,
                )
            ),
            created_at=T0,
            updated_at=T0,
        )
    )


def _calculate(objects: SecureObjectRepository, *, activity_key: str | None) -> CalculationRevision:
    # The filer's result is a refund, so the export's account page needs the designated account.
    register_refund_account(objects)
    # The activity states it held no existencias, so the stock variation and purchase casillas read zero.
    InventoryLedgerRepository(objects=objects).save(InventoryLedgerDocument(ledgers=(closed_no_stock_ledger(YEAR),)))
    persist_ledger(objects)
    seed_prior_year_m100(objects)
    for period, result in OFFICIAL_M130_C19.items():
        import_official_m130_result_observation(objects, period=period, c19_value=result)
    units = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=YEAR, period=M100_ANNUAL_PERIOD)
        unit = create_work_unit(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, M100_ANNUAL_PERIOD),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=units,
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            operation=operation,
            clock=T0,
        )
    stated_activity_key = activity_key is not None and activity_key != ""
    return calculate_revision_from_bucket_aggregation(
        unit.work_unit_id,
        binding_values=m100_non_relation_zero_bindings(),
        text_casilla_inputs={_box("TACT"): activity_key} if stated_activity_key else None,
        work_unit_repository=units,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=objects),
        clock=T0,
    ).revision


def _family_facts(*, minor_children: bool) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="renta_family.minor_children_in_unit", value=minor_children),
        *(
            UserProfileFact(path=path, value=value)
            for path, value in descendant_facts_from_list(eligible_descendants())
        ),
    )


@pytest.mark.parametrize("criterion", [DEVENGO, CASH])
def test_a_direct_estimation_export_stating_its_activity_key_is_valid(
    secure_objects: SecureObjectRepository, tmp_path: Path, criterion: str
) -> None:
    _seed_filer(criterion=criterion)
    revision = _calculate(secure_objects, activity_key=_ACTIVITY_KEY)

    payload = verify_and_export(revision, secure_objects, tmp_path / "modelo-100.xml")

    assert record_design_schema_violations(payload, xsd=_edition_xsd(YEAR)) == ()
    document = etree.fromstring(payload)
    assert document.findtext(f"{_ACTIVITY_BLOCK}/TACT") == _ACTIVITY_KEY
    # Independent reading of the schema's tipo_Titular: 2 is DECLARANTE.
    block = document.find("DatosEconomicos/TomaDatosAmpliada")
    assert block is not None
    assert block.get("titular") == "2"
    assert document.find("DatosIdentificativos/Hijos") is None
    assert (document.findtext(f"{_ACTIVITY_BLOCK}/E1ITEMP") == "1") is (criterion == CASH)


def test_the_oracle_read_the_real_schema_and_fails_on_a_planted_missing_element(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    _seed_filer(criterion=DEVENGO)
    payload = verify_and_export(
        _calculate(secure_objects, activity_key=_ACTIVITY_KEY), secure_objects, tmp_path / "modelo-100.xml"
    )
    document = etree.fromstring(payload)
    block = document.find(_ACTIVITY_BLOCK)
    assert block is not None
    planted = block.find("TACT")
    assert planted is not None
    block.remove(planted)

    violations = record_design_schema_violations(etree.tostring(document), xsd=_edition_xsd(YEAR))

    assert len(violations) == 1, violations
    assert "TACT" in violations[0]


_REQUIRED_CONTENT_FINDING = "application.modelo.findings.xml_required_content_missing"


class _CollectingPayloadConsumer:
    """Stand in for the review package, which archives the bytes it is handed."""

    def __init__(self) -> None:
        self.payloads: list[FilingExportValidatedPayload] = []

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payloads.append(payload)


def _verify(revision: CalculationRevision) -> VerificationReport:
    """Verify on the real path."""
    report = verify_revision_for_test(
        revision.calculation_revision_id,
        actor="schema-acceptance",
        workflow_profile=autonomaworkflow_profile(),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    assert isinstance(report, VerificationReport)
    return report


def _refused_by_verification(revision: CalculationRevision) -> tuple[ModeloVerificationFinding, ...]:
    """Verify on the real path and return the content findings of a report that must not grant."""
    report = _verify(revision)
    assert report.granted_verificado_completo is False
    return tuple(finding for finding in report.findings if finding.message_locale_key == _REQUIRED_CONTENT_FINDING)


def _sealed(revision: CalculationRevision, objects: SecureObjectRepository) -> None:
    """Hold a revision sealed before this check existed, which export must still judge on its own."""
    repository = CalculationRevisionCatalogueRepository(objects=objects)
    with bundled_indexed_authority().operation() as operation:
        catalogue = repository.load(operation=operation)
    sealed = revision.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": T0,
            "verified_by": "schema-acceptance",
        }
    )
    repository.save(
        catalogue.model_copy(
            update={"revisions": {**catalogue.revisions, revision.calculation_revision_id: sealed}},
        )
    )


def _export(
    revision: CalculationRevision,
    objects: SecureObjectRepository,
    output: Path,
    *,
    payload_consumer: _CollectingPayloadConsumer | None = None,
) -> None:
    export_revision_for_test(
        ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id, output_path=output, actor="schema-acceptance"
        ),
        workflow_profile=autonomaworkflow_profile(),
        export_ports=modelo_export_ports_for_test(bucket_id=BUCKET_ID, taxpayer_tax_id=TAX_ID, secure_objects=objects),
        payload_consumer=payload_consumer,
    )


def test_income_with_no_stated_activity_key_blocks_verification_and_the_export_refuses_the_same_box(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    _seed_filer(criterion=DEVENGO)
    revision = _calculate(secure_objects, activity_key=None)
    output = tmp_path / "modelo-100.xml"

    (finding,) = _refused_by_verification(revision)
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.casilla_id == _box("TACT")
    assert finding.message_facts["box"] == str(_box("TACT"))

    _sealed(revision, secure_objects)
    with pytest.raises(ModeloExportError) as refused:
        _export(revision, secure_objects, output)

    assert str(refused.value.translated_message).endswith("xml_value_required_missing")
    assert (refused.value.context or {})["box"] == finding.message_facts["box"]
    assert not output.exists()


def test_a_review_package_payload_is_refused_before_it_is_handed_over(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    _seed_filer(criterion=DEVENGO)
    revision = _calculate(secure_objects, activity_key=None)
    _sealed(revision, secure_objects)
    consumer = _CollectingPayloadConsumer()

    with pytest.raises(ModeloExportError) as refused:
        _export(revision, secure_objects, tmp_path / "package.zip", payload_consumer=consumer)

    assert str(refused.value.translated_message).endswith("xml_value_required_missing")
    assert (refused.value.context or {})["box"] == str(_box("TACT"))
    assert consumer.payloads == []
    events = BucketEventHistoryRepository(objects=secure_objects).load()
    assert BucketEventType.MODELO_EXPORTED not in {event.event_type for event in events.events.values()}


def test_a_complete_return_reaches_the_review_package_consumer(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    _seed_filer(criterion=DEVENGO)
    revision = _calculate(secure_objects, activity_key=_ACTIVITY_KEY)
    _sealed(revision, secure_objects)
    consumer = _CollectingPayloadConsumer()

    _export(revision, secure_objects, tmp_path / "package.zip", payload_consumer=consumer)

    (delivered,) = consumer.payloads
    assert record_design_schema_violations(delivered.payload, xsd=_edition_xsd(YEAR)) == ()


@pytest.mark.parametrize("minor_children", [False, True])
def test_a_claimed_descendant_minimum_with_no_identifying_row_blocks_verification_and_refuses_export(
    secure_objects: SecureObjectRepository, tmp_path: Path, minor_children: bool
) -> None:
    _seed_filer(criterion=DEVENGO, family=_family_facts(minor_children=minor_children))
    revision = _calculate(secure_objects, activity_key=_ACTIVITY_KEY)
    assert Decimal(revision.casilla_values[_box("MDES")]) > 0
    output = tmp_path / "modelo-100.xml"

    # The design requires the surnames and name on every Hijo, so the unstated fact is refused with its own
    # typed reason before any XML is built.
    with pytest.raises(ModeloHouseholdRowFactUnstatedError) as unverified:
        _verify(revision)
    assert (unverified.value.context or {})["field"] == _DESCENDANT_NAME_FACT
    assert (unverified.value.context or {})["action"] == "verify"

    _sealed(revision, secure_objects)
    with pytest.raises(ModeloHouseholdRowFactUnstatedError) as refused:
        _export(revision, secure_objects, output)

    assert (refused.value.context or {})["field"] == _DESCENDANT_NAME_FACT
    assert (refused.value.context or {})["action"] == "export"
    assert not output.exists()
