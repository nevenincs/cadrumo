"""Periodic perceptor counts against the annual summary's distinct perceptors, over real encrypted stores.

Expected outcomes are worked by hand from the definitions the gate implements:
a box counts persons paid in its own quarter, and the summary names each person
at least once. Only a single box above the distinct-person total is impossible.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests.percepcion_observation_authoring import (
    replace_percepcion_observations,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.preconditions import ModeloPreconditionFailure
from cadrumo.application.modelo.verification_model_findings import append_readable_model_findings
from cadrumo.application.modelo.withholding_count_reconciliation import (
    append_withholding_count_reconciliation_findings,
)
from cadrumo.core.aggregation import AggregationCaptureKind, RetencionClave
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_verification_repository_bundle,
)
from cadrumo.tests.withholding_zero_blocks import zeroed_withholding_blocks

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "19019019-0190-4190-8190-000000005555"
_YEAR = 2022
_NOW = datetime(_YEAR + 1, 1, 15, 9, 0, tzinfo=UTC)
_WORK_BOX = "01"
_ACTIVITY_BOX = "07"
_EXCEEDS_KEY = "application.modelo.findings.withholding_count_exceeds_summary_perceptors"
_UNCHECKED_KEY = "application.modelo.findings.withholding_count_not_cross_checked"
_PERSON_A = "00000000T"
_PERSON_B = "00001005Q"
_PERSON_C = "00001000B"


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@dataclass(frozen=True, slots=True)
class _Stores:
    objects: SecureObjectRepository
    observation: CalculationObservationRepository
    percepcion: PercepcionObservationRepositoryAdapter


@pytest.fixture
def stores(tmp_path: Path) -> Generator[_Stores]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects: SecureObjectRepository = profile.repository
        yield _Stores(
            objects=objects,
            observation=CalculationObservationRepository(objects=objects),
            percepcion=PercepcionObservationRepositoryAdapter(objects=objects),
        )


def _declare_counts(
    stores: _Stores,
    operation: PinnedAuthorityOperation,
    period: str,
    boxes: Mapping[str, str],
) -> None:
    observation = RegistryModeloObservation(
        modelo="111",
        filing_year=_YEAR,
        period=period,
        observations=tuple(
            CasillaObservation(
                casilla_id=validated_casilla_id(box, surface="count reconciliation test"),
                value=Decimal(count),
                legal_refs=("synthetic-legal",),
                source_refs=("synthetic-source",),
            )
            for box, count in boxes.items()
        ),
    )
    stores.observation.save(
        stores.observation.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=_NOW,
            stamped_revision_id=operation.snapshot("111", filing_year=_YEAR, period=period).revision.id,
        )
    )


def _declare_summary_rows(stores: _Stores, period: str, rows: tuple[tuple[str, str], ...]) -> None:
    replace_percepcion_observations(
        stores.percepcion,
        modelo="111",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        observations=tuple(
            WithholdingObservation(
                source_id=f"synthetic-{index}",
                perceptor_tax_id=person,
                transaction_date=date(_YEAR, 1, 15),
                clave=RetencionClave.from_registry(clave),
                percibido_dinerario=Decimal("1000.00"),
                retencion_practicada=Decimal("150.00"),
                base_retenciones=Decimal("1000.00"),
                **zeroed_withholding_blocks(),
            )
            for index, (person, clave) in enumerate(rows)
        ),
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def _summary_work_unit(operation: PinnedAuthorityOperation, *, modelo: str = "190") -> WorkUnit:
    period = Period.from_year_and_code(_YEAR, "0A")
    snapshot = operation.snapshot(modelo, filing_year=_YEAR, period="0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=_YEAR,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"{modelo}-synthetic",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _reconcile(
    stores: _Stores,
    operation: PinnedAuthorityOperation,
    *,
    modelo: str = "190",
) -> tuple[list[ModeloVerificationFinding], dict[int, ModeloPreconditionFailure]]:
    work_unit = _summary_work_unit(operation, modelo=modelo)
    snapshot = operation.snapshot(modelo, filing_year=_YEAR, period="0A")
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    append_withholding_count_reconciliation_findings(
        work_unit=work_unit,
        target_calculation_revision_id="synthetic-revision",
        target_work_unit_id=work_unit.work_unit_id,
        snapshot=snapshot,
        observation_repository=stores.observation,
        percepcion_repository=stores.percepcion,
        operation=operation,
        findings=findings,
        failures_by_finding_id=failures,
    )
    return findings, failures


def _all_quarters(stores: _Stores, operation: PinnedAuthorityOperation, count: str) -> None:
    for period in ("1T", "2T", "3T", "4T"):
        _declare_counts(stores, operation, period, {_WORK_BOX: count})


def test_one_employee_paid_all_year_is_one_perceptor_not_four(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The sum of the quarters is 4 and the summary names 1 person: correct, so no finding."""
    _all_quarters(stores, authority_operation, "1")
    _declare_summary_rows(stores, "1T", ((_PERSON_A, "A"),))

    findings, _ = _reconcile(stores, authority_operation)

    assert findings == []


def test_four_recipients_in_one_quarter_against_one_summary_person_blocks(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Four persons paid in 2T cannot fit on a summary naming one: excess 4 against 1, keyed to 2T box 01."""
    _all_quarters(stores, authority_operation, "1")
    _declare_counts(stores, authority_operation, "2T", {_WORK_BOX: "4"})
    _declare_summary_rows(stores, "1T", ((_PERSON_A, "A"),))

    findings, failures = _reconcile(stores, authority_operation)

    assert [finding.message_locale_key for finding in findings] == [_EXCEEDS_KEY]
    finding = findings[0]
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["period"] == "2T"
    assert finding.message_facts["casilla_id"] == _WORK_BOX
    assert Decimal(str(finding.message_facts["declared_perceptors"])) == Decimal(4)
    assert finding.message_facts["summary_perceptors"] == 1
    assert failures[id(finding)].scenario_id == "modelo.work.verify.withholding_count.exceeded"
    assert _PERSON_A not in str(finding.message_facts)


def test_several_records_of_one_person_do_not_satisfy_a_count_of_persons(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Three records under three claves are one person, so a box of 2 still exceeds the summary."""
    _all_quarters(stores, authority_operation, "2")
    _declare_summary_rows(stores, "1T", ((_PERSON_A, "A"), (_PERSON_A, "E"), (_PERSON_A, "G")))

    findings, _ = _reconcile(stores, authority_operation)

    assert {finding.message_locale_key for finding in findings} == {_EXCEEDS_KEY}
    assert len(findings) == 4


def test_boxes_are_not_added_because_one_person_can_sit_in_two(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Work 3 and activity 2 total 5, yet three persons can fill both boxes, so no finding."""
    for period in ("1T", "2T", "3T", "4T"):
        _declare_counts(stores, authority_operation, period, {_WORK_BOX: "3", _ACTIVITY_BOX: "2"})
    _declare_summary_rows(
        stores,
        "1T",
        ((_PERSON_A, "A"), (_PERSON_B, "A"), (_PERSON_C, "A"), (_PERSON_A, "G"), (_PERSON_B, "G")),
    )

    findings, _ = _reconcile(stores, authority_operation)

    assert findings == []


def test_a_summary_naming_more_persons_than_any_box_is_not_a_disagreement(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Exempt income reaches the summary but no box, so 1 against 3 proves nothing."""
    _all_quarters(stores, authority_operation, "1")
    _declare_summary_rows(stores, "1T", ((_PERSON_A, "A"), (_PERSON_B, "L"), (_PERSON_C, "L")))

    findings, _ = _reconcile(stores, authority_operation)

    assert findings == []


def test_declared_recipients_contradict_a_summary_with_no_rows(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An empty summary names nobody, so a filed count of 2 exceeds it in the one quarter observed."""
    _declare_counts(stores, authority_operation, "1T", {_WORK_BOX: "2"})

    findings, _ = _reconcile(stores, authority_operation)

    assert [finding.message_locale_key for finding in findings] == [_EXCEEDS_KEY, _UNCHECKED_KEY]


def test_an_unobserved_quarter_stays_unknown_and_never_reads_as_zero(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Three quarters agree and 4T has no observation: a note naming 4T, and nothing blocks."""
    for period in ("1T", "2T", "3T"):
        _declare_counts(stores, authority_operation, period, {_WORK_BOX: "1"})
    _declare_summary_rows(stores, "1T", ((_PERSON_A, "A"),))

    findings, failures = _reconcile(stores, authority_operation)

    assert [finding.message_locale_key for finding in findings] == [_UNCHECKED_KEY]
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert findings[0].message_facts["checked_periods"] == "1T|2T|3T"
    assert findings[0].message_facts["unchecked_periods"] == "4T"
    assert failures == {}


def test_a_summary_folding_no_periodic_percepciones_is_out_of_scope(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 180 reads its own store, so filed Modelo 111 counts say nothing about it."""
    _all_quarters(stores, authority_operation, "9")

    findings, _ = _reconcile(stores, authority_operation, modelo="180")

    assert findings == []


def test_verification_reaches_the_comparison_through_its_real_repository_bundle(
    stores: _Stores,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The verify seam reads both stores from the composed bundle, and the excess blocks there."""
    _all_quarters(stores, authority_operation, "1")
    _declare_counts(stores, authority_operation, "3T", {_WORK_BOX: "4"})
    _declare_summary_rows(stores, "1T", ((_PERSON_A, "A"),))
    work_unit = _summary_work_unit(authority_operation)
    snapshot = authority_operation.snapshot("190", filing_year=_YEAR, period="0A")
    target = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_transaction_ids=(),
            source_issues=(),
            source_provenance=(),
            filing_instance_evidence=None,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="190",
            revision_id=snapshot.revision.id,
            modelo_year=_YEAR,
            period="0A",
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        observations=(),
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}

    append_readable_model_findings(
        findings,
        failures,
        work_unit,
        target,
        build_test_verification_repository_bundle(),
        authority_operation,
    )

    excess = [finding for finding in findings if finding.message_locale_key == _EXCEEDS_KEY]
    assert [finding.message_facts["period"] for finding in excess] == ["3T"]
    assert excess[0].severity is ModeloVerificationFindingSeverity.BLOCKING
    assert id(excess[0]) in failures
