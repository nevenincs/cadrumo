"""Calculation revision identity contract tests."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import TypedDict, cast

import pytest
from pydantic import ValidationError

from ....core import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    CasillaId,
    M210GrossIncomeSourceMode,
    Period,
    validated_casilla_id,
)
from ....core.directory_scan import (
    scan_directory,
)
from ....tests.filing_evidence import regimen_simplificado_filing_evidence
from ...calculations import RowSourceIdentity
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.ids import RelationId
from ...calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ...filing_evidence import FilingEvidenceReference
from ...iva.regimen_simplificado_rows import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision, RegimenSimplificadoFilingRows
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceRef,
    FilingInstanceEvidence,
    M303Exonerado390ActivityRowEvidence,
    M303Exonerado390EndpointEvidence,
    M303Exonerado390FilingEvidence,
    M303FilingInstanceEvidence,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    derive_calculation_revision_id,
)
from ..errors import ModeloValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_INPUT_CASILLA_001: CasillaId = validated_casilla_id("001")
_INPUT_CASILLA_002: CasillaId = validated_casilla_id("002")
_PIN_INPUT_CASILLA_01: CasillaId = validated_casilla_id("01")
_PIN_INPUT_CASILLA_02: CasillaId = validated_casilla_id("02")
_PIN_INPUT_CASILLA_03: CasillaId = validated_casilla_id("03")
_OUTPUT_CASILLA_002: CasillaId = validated_casilla_id("002")
_PIN_OUTPUT_CASILLA_04: CasillaId = validated_casilla_id("04")
_PIN_OUTPUT_CASILLA_07: CasillaId = validated_casilla_id("07")
_PIN_OUTPUT_CASILLA_19: CasillaId = validated_casilla_id("19")
_OBSERVATION_CASILLA_100: CasillaId = validated_casilla_id("100")
_OBSERVATION_CASILLA_200: CasillaId = validated_casilla_id("200")
_ORDERED_OUTPUT_CASILLA_010: CasillaId = validated_casilla_id("010")
_ORDERED_OUTPUT_CASILLA_020: CasillaId = validated_casilla_id("020")
_PAGOS_RELATION: RelationId = "renta-2024-rel-130-pagos-fraccionados"
_NONCANONICAL_CASILLA_KEY = "bad key"
_WHITESPACE_CASILLA_KEY = " 001 "
_TEST_LEGAL_REFS = ("ley-58-2003:art-93",)
_TEST_SOURCE_REFS = ("aeat-dr-303-2025",)


class _CommonRevisionIdArgs(TypedDict):
    """Shared typed keyword payload for source-provenance hash cases."""

    work_unit_id: str
    input_values_by_casilla_id: dict[CasillaId, str]
    binding_overrides: dict[str, str]
    casilla_values: dict[CasillaId, Decimal]


def _general_m303_filing_evidence(period: Period) -> M303FilingInstanceEvidence:
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=bundled_authority().snapshot(
            "303",
            filing_year=period.filing_year,
            period="1T",
        ),
        scope_decision=scope,
    )
    return M303FilingInstanceEvidence(
        period=period,
        joint_return_elected=True,
        annual_volume_nonzero=False,
        insolvency=None,
        exonerado_390=M303Exonerado390FilingEvidence(
            applicable=False,
            applicability_reference=FilingEvidenceReference(reference="test:exonerado-390:not-applicable"),
            endpoints=(),
            activity_rows=(),
            operaciones_terceros_declarables=None,
            operaciones_terceros_reference=None,
        ),
        regimen_simplificado=regimen_simplificado_filing_evidence(
            period=period,
            scope_decision=scope,
            rows=RegimenSimplificadoFilingRows(ejercicio=period.filing_year, activities=()),
            regimen_snapshot=snapshot,
            dana_2024_eligibility=None,
        ),
    )


def test_m303_filing_evidence_requires_an_explicit_nullable_insolvency_fact() -> None:
    evidence = _general_m303_filing_evidence(Period.from_year_and_code(2026, "1T"))
    payload = evidence.model_dump(mode="python")
    del payload["insolvency"]

    with pytest.raises(ValidationError, match="insolvency"):
        M303FilingInstanceEvidence.model_validate(payload)

    payload["insolvency"] = None
    assert M303FilingInstanceEvidence.model_validate(payload) == evidence


def test_m303_exonerado_390_evidence_preserves_shape_refusal_precedence() -> None:
    """Endpoint identity refuses before rows or applicability completeness."""
    reference = FilingEvidenceReference(reference="test:exonerado-390:precedence")
    duplicate_endpoint = M303Exonerado390EndpointEvidence(
        casilla_id=validated_casilla_id("79"),
        value=Decimal("0"),
        evidence_reference=reference,
    )

    with pytest.raises(ValidationError, match="duplicate endpoint casillas"):
        M303Exonerado390FilingEvidence(
            applicable=True,
            applicability_reference=reference,
            endpoints=(duplicate_endpoint, duplicate_endpoint),
            activity_rows=(
                M303Exonerado390ActivityRowEvidence(
                    slot=2,
                    codigo_actividad="A01",
                    epigrafe_iae="4191",
                    evidence_reference=reference,
                ),
            ),
            operaciones_terceros_declarables=False,
            operaciones_terceros_reference=reference,
        )


def _base_id() -> str:
    return derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )


def test_row_source_identity_is_hashed_redacted_and_coordinate_checked() -> None:
    created = datetime(2026, 8, 23, tzinfo=UTC)
    key = ("modelo-190-perceptor-row-nif", 1)
    identity = RowSourceIdentity(
        source_kind=BindingSourceKind.WITHHOLDING,
        source_row_identity="detalle:per_perceptor_clave:row-1",
        fingerprint="a" * 64,
        row_set_grouping="per_perceptor_clave",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={key[0]: {"1": "10.00"}},
        row_source_identities={key: identity},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id="a" * 64,
        state=CalculationRevisionState.BORRADOR,
        row_binding_values={key[0]: {"1": "10.00"}},
        row_source_identities={key: identity},
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=created,
        updated_at=created,
    )

    assert "detalle:per_perceptor_clave:row-1" not in revision.model_dump_json()
    secure_payload = revision.model_dump(mode="python", context={"secure_calculation_revision": True})
    assert secure_payload["row_source_identities"] == [
        {
            "binding_id": key[0],
            "row_index": 1,
            "source_kind": "withholding",
            "source_row_identity": "detalle:per_perceptor_clave:row-1",
            "fingerprint": "a" * 64,
            "row_set_grouping": "per_perceptor_clave",
        },
    ]
    rehydrated = CalculationRevision.model_validate(
        secure_payload,
        context={"secure_calculation_revision": True},
    )
    assert rehydrated.row_source_identities[key] == identity
    changed = identity.model_copy(update={"fingerprint": "b" * 64})
    assert (
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={key[0]: {"1": "10.00"}},
            row_source_identities={key: changed},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        != revision_id
    )
    changed_grouping = identity.model_copy(update={"row_set_grouping": "per_perceptor"})
    assert (
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={key[0]: {"1": "10.00"}},
            row_source_identities={key: changed_grouping},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        != revision_id
    )

    with pytest.raises(ValidationError, match="has no row binding value"):
        orphan_id = derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_source_identities={key: identity},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        CalculationRevision(
            calculation_revision_id=orphan_id,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            row_source_identities={key: identity},
            filing_instance_evidence=None,
            source_provenance=(),
            created_at=created,
            updated_at=created,
        )


def test_calculation_revision_requires_explicit_source_provenance_even_when_empty() -> None:
    created = datetime(2026, 8, 22, tzinfo=UTC)
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id="a" * 64,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=created,
        updated_at=created,
    )
    assert revision.source_provenance == ()

    payload = revision.model_dump(mode="python")
    del payload["source_provenance"]
    with pytest.raises(ValidationError, match="source_provenance"):
        CalculationRevision.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "state", "state_fields"),
    (
        ("created_at", CalculationRevisionState.BORRADOR, {}),
        ("updated_at", CalculationRevisionState.BORRADOR, {}),
        (
            "verified_at",
            CalculationRevisionState.VERIFICADO_COMPLETO,
            {"verified_at": datetime(2026, 5, 26, 11, 0, tzinfo=UTC), "verified_by": "operator"},
        ),
        (
            "filed_at",
            CalculationRevisionState.PRESENTADO,
            {
                "verified_at": datetime(2026, 5, 26, 11, 0, tzinfo=UTC),
                "verified_by": "operator",
                "filed_at": datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
                "filed_by": "operator",
            },
        ),
        (
            "superseded_at",
            CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
            {
                "verified_at": datetime(2026, 5, 26, 11, 0, tzinfo=UTC),
                "verified_by": "operator",
                "filed_at": datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
                "filed_by": "operator",
                "superseded_at": datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
            },
        ),
        (
            "discarded_at",
            CalculationRevisionState.DESCARTADO,
            {
                "discarded_at": datetime(2026, 5, 26, 11, 0, tzinfo=UTC),
                "discarded_by": "operator",
                "discard_reason": "operator discarded incomplete draft",
            },
        ),
    ),
    ids=("created", "updated", "verified", "filed", "superseded", "discarded"),
)
@pytest.mark.parametrize(
    "malformed_instant",
    (
        datetime(2026, 5, 26, 10, 0),
        datetime(2026, 5, 26, 11, 0, tzinfo=timezone(timedelta(hours=1))),
    ),
    ids=("naive", "non-utc"),
)
def test_calculation_revision_refuses_non_utc_lifecycle_instants(
    field: str,
    state: CalculationRevisionState,
    state_fields: dict[str, object],
    malformed_instant: datetime,
) -> None:
    """Every revision lifecycle instant is a UTC-only persistence invariant."""

    utc_created_at = datetime(2026, 5, 26, 10, 0, tzinfo=UTC)
    payload: dict[str, object] = {
        "calculation_revision_id": _base_id(),
        "work_unit_id": "a" * 64,
        "state": state,
        "input_values_by_casilla_id": {_INPUT_CASILLA_001: "10.00"},
        "binding_overrides": {},
        "casilla_values": {_OUTPUT_CASILLA_002: Decimal("15.00")},
        "created_at": utc_created_at,
        "updated_at": utc_created_at,
    }
    payload.update(state_fields)
    payload[field] = malformed_instant

    with pytest.raises(ValidationError, match="datetime must be"):
        CalculationRevision.model_validate(payload)


def test_revision_id_is_stable_across_equal_inputs() -> None:
    """Same inputs must always yield the same id (content-addressing contract)."""
    first = _base_id()
    second = _base_id()
    assert first == second
    assert len(first) == 64
    assert first == first.lower()


def test_revision_id_changes_with_immutable_m303_filing_instance_evidence() -> None:
    """Different filing-instance facts must create different revisions, never mutate one."""

    def revision_id_for(evidence: FilingInstanceEvidence) -> str:
        return derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=evidence,
            source_provenance=(),
        )

    period = Period.from_year_and_code(2026, "1T")
    joint_m303 = _general_m303_filing_evidence(period)
    joint = FilingInstanceEvidence(m303=joint_m303)
    insolvent = FilingInstanceEvidence(
        m303=joint_m303.model_copy(
            update={
                "insolvency": M303InsolvencyFilingFact(
                    judicial_order_date=date(2026, 2, 3),
                    subtype=M303InsolvencyFilingSubtype.POST_ORDER,
                ),
            },
        ),
    )

    assert revision_id_for(joint) != revision_id_for(insolvent)
    with pytest.raises(ValidationError, match="frozen"):
        joint.m303.joint_return_elected = False

    reference = FilingEvidenceReference(reference="test:revision-id:exonerado-activity")

    def annual_evidence(codigo_actividad: str) -> FilingInstanceEvidence:
        annual_m303 = _general_m303_filing_evidence(Period.from_year_and_code(2026, "4T"))
        return FilingInstanceEvidence(
            m303=annual_m303.model_copy(
                update={
                    "exonerado_390": M303Exonerado390FilingEvidence(
                        applicable=True,
                        applicability_reference=reference,
                        endpoints=(
                            M303Exonerado390EndpointEvidence(
                                casilla_id=validated_casilla_id("79"),
                                value=Decimal("0"),
                                evidence_reference=reference,
                            ),
                        ),
                        activity_rows=(
                            M303Exonerado390ActivityRowEvidence(
                                slot=1,
                                codigo_actividad=codigo_actividad,
                                epigrafe_iae="4101",
                                evidence_reference=reference,
                            ),
                            M303Exonerado390ActivityRowEvidence(
                                slot=2, codigo_actividad="A02", epigrafe_iae="4102", evidence_reference=reference
                            ),
                            M303Exonerado390ActivityRowEvidence(
                                slot=3, codigo_actividad="A03", epigrafe_iae="4103", evidence_reference=reference
                            ),
                            M303Exonerado390ActivityRowEvidence(
                                slot=4, codigo_actividad="A04", epigrafe_iae="4104", evidence_reference=reference
                            ),
                            M303Exonerado390ActivityRowEvidence(
                                slot=5, codigo_actividad="A05", epigrafe_iae="4105", evidence_reference=reference
                            ),
                            M303Exonerado390ActivityRowEvidence(
                                slot=6, codigo_actividad="A06", epigrafe_iae="4106", evidence_reference=reference
                            ),
                        ),
                        operaciones_terceros_declarables=False,
                        operaciones_terceros_reference=reference,
                    ),
                },
            ),
        )

    assert revision_id_for(annual_evidence("A01")) != revision_id_for(annual_evidence("B01"))


def test_exonerado_evidence_rejects_legacy_marker_surface() -> None:
    reference = FilingEvidenceReference(reference="test:no-s56-fields")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        M303Exonerado390FilingEvidence.model_validate(
            {
                "applicable": False,
                "applicability_reference": reference,
                "endpoints": (),
                "activity_rows": (),
                "operaciones_terceros_declarables": None,
                "operaciones_terceros_reference": None,
                "marker_reference": "legacy-marker",
            },
        )


@pytest.mark.parametrize(
    "missing_field",
    ("endpoints", "activity_rows", "operaciones_terceros_declarables", "operaciones_terceros_reference"),
)
def test_exonerado_evidence_requires_every_explicit_s56_field(missing_field: str) -> None:
    payload = {
        "applicable": False,
        "applicability_reference": FilingEvidenceReference(reference="test:explicit-s56-fields"),
        "endpoints": (),
        "activity_rows": (),
        "operaciones_terceros_declarables": None,
        "operaciones_terceros_reference": None,
    }
    del payload[missing_field]
    with pytest.raises(ValidationError, match=missing_field):
        M303Exonerado390FilingEvidence.model_validate(
            payload,
        )


def test_every_calculation_revision_constructor_declares_filing_evidence_explicitly() -> None:
    source_root = Path(__file__).parents[4]
    omissions: list[str] = []
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        if path.relative_to(source_root).as_posix() == "cadrumo/core/tests/test_period.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name != "CalculationRevision":
                continue
            if not any(keyword.arg == "filing_instance_evidence" for keyword in node.keywords):
                omissions.append(f"{path.relative_to(source_root).as_posix()}:{node.lineno}")
    assert omissions == []


def test_production_revision_id_derivations_name_the_single_annual_summary_input_axis() -> None:
    """Only the three creation boundaries may derive a revision id from fields.

    Existing revisions must use ``derive_calculation_revision_id_from_revision``
    instead.  Keeping that read-side projection singular prevents a new input
    (such as the immutable 303/4T -> 390/0A handoff) from being omitted by an
    independently maintained field list.
    """
    source_root = Path(__file__).parents[4]
    direct_derivations: dict[str, list[ast.Call]] = {}
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        relative = path.relative_to(source_root).as_posix()
        if "/tests/" in relative:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "derive_calculation_revision_id"
        ]
        if calls:
            direct_derivations[relative] = calls

    assert set(direct_derivations) == {
        "cadrumo/application/modelo/_amendment_actions.py",
        "cadrumo/application/modelo/external_import_actions.py",
        "cadrumo/application/modelo/_revision_persistence.py",
    }
    omissions = [
        f"{path}:{call.lineno}"
        for path, calls in direct_derivations.items()
        for call in calls
        if not any(keyword.arg == "m303_regimen_simplificado_annual_summary_handoff" for keyword in call.keywords)
    ]
    assert omissions == []


def test_portable_revision_json_missing_filing_evidence_is_rejected() -> None:
    payload = {
        "calculation_revision_id": "a" * 64,
        "work_unit_id": "b" * 64,
        "state": "borrador",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with pytest.raises(ValidationError, match="filing_instance_evidence"):
        CalculationRevision.model_validate(payload)


def test_revision_id_pinned_against_fully_populated_fixture() -> None:
    """Anti-tautology proof: pin the exact SHA-256 for a fully-populated
    derivation against a known-good hex string.

    Staged for linkage cleanup (the planned collapse of
    ``CalculationRevision.casilla_values`` into a derived ``@property``
    over the typed ``observations`` envelope). The collapse must
    preserve the hash domain — every already-persisted revision id
    must still derive identically after the field-shape change, or
    every catalogue row gets a phantom mismatch and the
    content-addressing contract breaks.

    The fixture sets every defaultable parameter to a non-default
    value so the pin exercises every branch of the hash payload:
    inputs, overrides, outputs, source_transaction_ids,
    borrador_snapshot_id, and bindings_sourced_from_borrador.

    Update procedure: if a future change to the hash domain is
    explicitly intended (e.g. a migration-bumping schema rev), update
    the pinned hex in tandem with the change and document the
    migration. If this test fails without an explicit hash-domain
    change, the regression is in the hash derivation itself.
    """
    pinned = "0f5194a5f8b91ae2c7d611b9877b656640c7ede87b686d9ede56df858a92a1fb"
    derived = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={
            _PIN_INPUT_CASILLA_01: "1000.00",
            _PIN_INPUT_CASILLA_02: "250.00",
            _PIN_INPUT_CASILLA_03: "50.00",
        },
        binding_overrides={
            "previous_year_net_income": "13000.00",
            "profile.iva_regime": "GENERAL",
        },
        casilla_values={
            _PIN_OUTPUT_CASILLA_04: Decimal("1300.00"),
            _PIN_OUTPUT_CASILLA_07: Decimal("-50.50"),
            _PIN_OUTPUT_CASILLA_19: Decimal("200.25"),
        },
        source_transaction_ids=("a" * 64, "c" * 64),
        borrador_snapshot_id="borrador-2026-q1-snapshot",
        bindings_sourced_from_borrador=(
            "iva.aggregation",
            "renta.expense.aggregation",
        ),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert derived == pinned, (
        f"Hash domain shifted — derive_calculation_revision_id returned "
        f"{derived!r} for a fully-populated fixture but the pinned value "
        f"is {pinned!r}. Every persisted CalculationRevision id now mismatches "
        f"its derived form; either revert the hash change or run a migration "
        f"and update the pin."
    )


def test_revision_id_pinned_across_every_optional_branch() -> None:
    """Anti-tautology proof for the optional payload branches.

    The base pin in :func:`test_revision_id_pinned_against_fully_populated_fixture`
    omits relation_overrides, the Modelo 210 code/mode, and row_binding_values.
    This pin populates those optional branches too, so the
    canonicalisation-pipeline restructure of
    :func:`derive_calculation_revision_id` (folding the payload into ordered
    ``_*_revision_id_payload`` helpers) is locked byte-for-byte. If the hash
    domain changes without an explicit, migration-backed intent, this fails.
    """
    pinned = "a89816076156be2dd3f09fa8146c4a1f4f56751959b88e9807cd4e762dd50f9e"
    derived = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={
            _PIN_INPUT_CASILLA_01: "1000.00",
            _PIN_INPUT_CASILLA_02: "250.00",
        },
        binding_overrides={
            "previous_year_net_income": "13000.00",
            "profile.iva_regime": "GENERAL",
        },
        casilla_values={
            _PIN_OUTPUT_CASILLA_04: Decimal("1300.00"),
            _PIN_OUTPUT_CASILLA_19: Decimal("200.25"),
        },
        row_binding_values={"iva.aggregation": {"2": "5.00", "1": "3.00"}},
        relation_overrides={_PAGOS_RELATION: "42.00"},
        source_transaction_ids=("a" * 64, "c" * 64),
        m210_official_tipo_renta_code="01",
        m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
        borrador_snapshot_id="borrador-2026-q1-snapshot",
        bindings_sourced_from_borrador=(
            "iva.aggregation",
            "renta.expense.aggregation",
        ),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert derived == pinned, (
        f"Hash domain shifted for the optional payload branches — "
        f"derive_calculation_revision_id returned {derived!r} but the pinned "
        f"value is {pinned!r}."
    )


def test_revision_id_changes_when_input_casilla_value_changes() -> None:
    """A different input_values_by_casilla_id must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "99.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_changes_when_output_casilla_value_changes() -> None:
    """A different casilla_values mapping must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("16.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_changes_when_work_unit_id_changes() -> None:
    """A different parent work_unit_id must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_canonicalizes_complete_source_provenance_and_refuses_identity_collisions() -> None:
    first = CalculationSourceRef(
        resolver_id="invoice_catalogue",
        resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        contributor_source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
        contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="collectible_invoice:inv-0001",
        parent_source_ref=None,
        fingerprint="sha256:" + "a" * 64,
        dependency_treatment="factual_evidence",
    )
    second = CalculationSourceRef(
        resolver_id="foreign_assets_aggregation",
        resolved_binding_source=BindingSourceKind.FOREIGN_ASSET,
        contributor_source_kind=BindingSourceKind.FOREIGN_ASSET.value,
        contributor_binding_source=BindingSourceKind.FOREIGN_ASSET,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref="foreign_asset:asset-0001",
        parent_source_ref=None,
        fingerprint="sha256:" + "b" * 64,
    )
    common: _CommonRevisionIdArgs = {
        "work_unit_id": "a" * 64,
        "input_values_by_casilla_id": {},
        "binding_overrides": {},
        "casilla_values": {},
    }
    canonical = derive_calculation_revision_id(
        **common, source_provenance=(first, second), filing_instance_evidence=None
    )
    assert canonical == derive_calculation_revision_id(
        **common, source_provenance=(second, first), filing_instance_evidence=None
    )
    assert canonical != derive_calculation_revision_id(
        **common,
        source_provenance=(first.model_copy(update={"resolver_id": "rival-resolver"}), second),
        filing_instance_evidence=None,
    )
    assert canonical != derive_calculation_revision_id(
        **common,
        source_provenance=(first.model_copy(update={"fingerprint": "sha256:" + "c" * 64}), second),
        filing_instance_evidence=None,
    )
    for update in (
        {"resolved_binding_source": BindingSourceKind.PAYABLE_INVOICE},
        {"contributor_source_kind": "invoice_catalogue_record"},
        {"contributor_binding_source": BindingSourceKind.PAYABLE_INVOICE},
        {"lineage_role": CalculationSourceLineageRole.CONTRIBUTOR},
        {"parent_source_ref": second.source_ref},
    ):
        assert canonical != derive_calculation_revision_id(
            **common,
            source_provenance=(first.model_copy(update=update), second),
            filing_instance_evidence=None,
        )


def test_persisted_source_ref_requires_a_coherent_explicit_binding_axis() -> None:
    payload = {
        "resolver_id": "invoice_catalogue",
        "resolved_binding_source": BindingSourceKind.COLLECTIBLE_INVOICE,
        "contributor_source_kind": BindingSourceKind.COLLECTIBLE_INVOICE.value,
        "lineage_role": CalculationSourceLineageRole.PRIMARY,
        "source_ref": "collectible_invoice:inv-0001",
        "parent_source_ref": None,
    }
    with pytest.raises(ValidationError):
        CalculationSourceRef.model_validate(payload)
    with pytest.raises(ValidationError, match="must equal contributor_source_kind"):
        CalculationSourceRef.model_validate(
            {**payload, "contributor_binding_source": BindingSourceKind.PAYABLE_INVOICE},
        )


def test_revision_id_changes_when_row_binding_value_changes() -> None:
    """A different row-indexed binding value must produce a different id."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={"modelo-720-asset-row-valuation": {"1": "60000"}},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={"modelo-720-asset-row-valuation": {"1": "65000"}},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_normalises_row_binding_order() -> None:
    id_ordered = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={
            "modelo-720-asset-row-class": {"1": "C", "2": "V"},
            "modelo-720-asset-row-valuation": {"1": "60000", "2": "55000"},
        },
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_reversed = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values={
            "modelo-720-asset-row-valuation": {"2": "55000", "1": "60000"},
            "modelo-720-asset-row-class": {"2": "V", "1": "C"},
        },
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_ordered == id_reversed


def test_revision_id_changes_when_relation_override_changes() -> None:
    """Relation replay values are part of the immutable calculation attempt."""
    id_a = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        relation_overrides={_PAGOS_RELATION: "725.75"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_b = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        relation_overrides={_PAGOS_RELATION: "725.76"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_a != id_b


def test_revision_id_derivation_rejects_non_canonical_casilla_keys() -> None:
    """Bad casilla keys must fail before a content-addressed revision id is minted."""
    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_NONCANONICAL_CASILLA_KEY: "10.00"},
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"casilla_values contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values={_NONCANONICAL_CASILLA_KEY: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_WHITESPACE_CASILLA_KEY: "10.00"},
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"input_values_by_casilla_id contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id=cast("dict[CasillaId, str]", {1: "10.00"}),
            binding_overrides={},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match=r"casilla_values contains non-canonical casilla\.id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            casilla_values=cast("dict[CasillaId, Decimal]", {1: Decimal("15.00")}),
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="binding_overrides contains non-canonical binding id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={"Bad Binding": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="relation_overrides contains non-canonical relation id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
            binding_overrides={},
            relation_overrides={"Bad Relation": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="row_binding_values contains non-canonical binding id"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={"Bad Binding": {"1": "C"}},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ModeloValidationError, match="non-positive row index"):
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={"modelo-720-asset-row-class": {"0": "C"}},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_calculation_revision_rejects_persisted_non_canonical_casilla_keys() -> None:
    """A stored revision with malformed casilla keys must not construct."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevision(
            calculation_revision_id="0" * 64,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id={_NONCANONICAL_CASILLA_KEY: "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_calculation_revision_rejects_legacy_inputs_snapshot_key() -> None:
    """Persisted revisions must use input_values_by_casilla_id, not inputs_snapshot."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    output_values = {_OUTPUT_CASILLA_002: Decimal("15.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values=output_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with pytest.raises(ValidationError) as exc_info:
        CalculationRevision.model_validate(
            {
                "calculation_revision_id": revision_id,
                "work_unit_id": "a" * 64,
                "state": CalculationRevisionState.BORRADOR,
                "input_values_by_casilla_id": {_INPUT_CASILLA_001: "10.00"},
                "inputs_snapshot": {_INPUT_CASILLA_001: "10.00"},
                "casilla_values": output_values,
                "source_provenance": (),
                "created_at": created,
                "updated_at": created,
            },
        )

    message = str(exc_info.value)
    assert "inputs_snapshot" in message
    assert "Extra inputs are not permitted" in message


def test_calculation_revision_rejects_persisted_non_canonical_binding_keys() -> None:
    """A stored revision with malformed binding ids must not construct."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevision(
            calculation_revision_id="0" * 64,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            binding_overrides={"Bad Binding": "10.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )

    with pytest.raises(ValidationError, match="String should match pattern"):
        CalculationRevision(
            calculation_revision_id="0" * 64,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            bindings_sourced_from_borrador=("Bad Binding",),
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_calculation_revision_normalises_row_binding_values() -> None:
    from datetime import UTC, datetime

    created = datetime(2026, 7, 5, 10, 0, 0, tzinfo=UTC)
    row_binding_values = {"modelo-720-asset-row-class": {"2": "V", "1": "C"}}
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values=row_binding_values,
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id="a" * 64,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        row_binding_values=row_binding_values,
        casilla_values={},
        created_at=created,
        updated_at=created,
        filing_instance_evidence=None,
        source_provenance=(),
    )

    assert revision.row_binding_values == {"modelo-720-asset-row-class": {"1": "C", "2": "V"}}


def test_calculation_revision_rejects_overlapping_binding_and_relation_replay_ids() -> None:
    """A replay id must belong to exactly one engine channel."""
    from datetime import UTC, datetime

    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    replay_id = "renta-2024-rel-130-pagos-fraccionados"
    revision_id = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={replay_id: "1.00"},
        relation_overrides={replay_id: "1.00"},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with pytest.raises(ValidationError, match="replay ids must be channel-unique"):
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id="a" * 64,
            state=CalculationRevisionState.BORRADOR,
            binding_overrides={replay_id: "1.00"},
            relation_overrides={replay_id: "1.00"},
            casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_observations_consistency_validator_accepts_matching_projection() -> None:
    """Stage one of the staged consistency check: when observations is populated, casilla_values
    must equal the projection of observations. Matching pair validates clean."""
    from datetime import UTC, datetime

    from ...calculations.registry.bindings import CasillaObservation
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "d" * 64
    casilla_values = {
        _OBSERVATION_CASILLA_100: Decimal("250.00"),
        _OBSERVATION_CASILLA_200: Decimal("-75.50"),
    }
    observations = (
        CasillaObservation(
            casilla_id=_OBSERVATION_CASILLA_100,
            value=Decimal("250.00"),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        ),
        CasillaObservation(
            casilla_id=_OBSERVATION_CASILLA_200,
            value=Decimal("-75.50"),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        ),
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    rev = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=observations,
        created_at=created,
        updated_at=created,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert rev.observations == observations
    assert dict(rev.casilla_values) == casilla_values


def test_observations_consistency_validator_rejects_drift() -> None:
    """Stage one of the staged consistency check: when observations diverges from casilla_values,
    construction must raise ModeloValidationError — save/load drift surfaces at
    load time rather than at a downstream hash mismatch."""
    from datetime import UTC, datetime

    import pydantic

    from ...calculations.registry.bindings import CasillaObservation
    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "e" * 64
    casilla_values = {_OBSERVATION_CASILLA_100: Decimal("250.00")}
    # observations encodes a DIFFERENT value for the same casilla — the
    # validator must refuse to construct.
    observations = (
        CasillaObservation(
            casilla_id=_OBSERVATION_CASILLA_100,
            value=Decimal("999.99"),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        ),
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(pydantic.ValidationError, match="inconsistent with the typed observations envelope"):
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            casilla_values=casilla_values,
            observations=observations,
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_observations_consistency_validator_rejects_non_empty_values_without_observations() -> None:
    """A non-empty flat value map without typed observations is an incomplete revision."""
    from datetime import UTC, datetime

    import pydantic

    from ..calculation_revision import CalculationRevision, CalculationRevisionState

    work_unit_id = "f" * 64
    casilla_values = {_OBSERVATION_CASILLA_100: Decimal("250.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    created = datetime(2026, 5, 26, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(pydantic.ValidationError, match="must carry typed observations"):
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            casilla_values=casilla_values,
            created_at=created,
            updated_at=created,
            filing_instance_evidence=None,
            source_provenance=(),
        )


def test_revision_id_is_insensitive_to_dict_key_insertion_order() -> None:
    """Dict key ordering must not affect the derived id (sort_keys guarantee)."""
    id_ordered = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "1.00", _INPUT_CASILLA_002: "2.00"},
        binding_overrides={},
        casilla_values={
            _ORDERED_OUTPUT_CASILLA_010: Decimal("5.00"),
            _ORDERED_OUTPUT_CASILLA_020: Decimal("6.00"),
        },
        filing_instance_evidence=None,
        source_provenance=(),
    )
    id_reversed = derive_calculation_revision_id(
        work_unit_id="c" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_002: "2.00", _INPUT_CASILLA_001: "1.00"},
        binding_overrides={},
        casilla_values={
            _ORDERED_OUTPUT_CASILLA_020: Decimal("6.00"),
            _ORDERED_OUTPUT_CASILLA_010: Decimal("5.00"),
        },
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id_ordered == id_reversed


def test_revision_id_includes_present_borrador_metadata() -> None:
    """Adding borrador metadata to otherwise-identical inputs must change the id."""
    base = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    with_borrador = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        input_values_by_casilla_id={_INPUT_CASILLA_001: "10.00"},
        binding_overrides={},
        casilla_values={_OUTPUT_CASILLA_002: Decimal("15.00")},
        borrador_snapshot_id="snapshot-100-2025",
        bindings_sourced_from_borrador=("casilla_001",),
        filing_instance_evidence=None,
        source_provenance=(),
    )

    assert with_borrador != base


def test_detail_rows_sort_key_handles_all_four_row_types() -> None:
    """Regression: sort key must work for all four row types (M184/M232 use nif,
    M349 uses nif_comunitario, M347 uses nif). This test verifies the sort key
    accessor correctly extracts the identifier field for each row type."""
    from ..row_models import (
        Modelo184MemberRow,
        Modelo232VinculadaRow,
        Modelo347ContraparteRow,
        Modelo349OperadorRow,
    )

    # Create one row of each type with distinct nif/nif_comunitario values.
    m184_row = Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("50.00"), importe=Decimal("100.00"), clave="D")
    m232_row = Modelo232VinculadaRow(pais="ES", nif="87654321B", importe=Decimal("200.00"))
    m349_row = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="DE123456789",
        razon_social="Deutschland GmbH",
        clave_operacion="E",
        importe=Decimal("300.00"),
    )
    m347_row = Modelo347ContraparteRow(nif="11223344C", importe_Q1=Decimal("400.00"))

    # All four rows must flow through the hash derivation without AttributeError.
    # The sort should succeed and the hash should be deterministic.
    id1 = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(m184_row, m232_row, m349_row, m347_row),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    # Same rows in reverse order must produce the same id (sort-insensitive).
    id2 = derive_calculation_revision_id(
        work_unit_id="a" * 64,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        detail_rows=(m347_row, m349_row, m232_row, m184_row),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    assert id1 == id2, "Row sort key must handle all four row types consistently"
