"""M303 carry enters storage only with disposition-grounded evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede._declarations_observations import _observed_header_facts_from_submitted_file
from ....core import ObservedHeaderFact, Period, ResultDisposition
from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation, casillas_by_id
from ....domain.iva_compensation import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._iva_compensation_history import (
    IvaCompensationHistoryRepository,
    iva_compensation_state_from_observation_envelope,
    persist_observation_envelope_and_iva_history,
)
from .._m303_carry_ingress import M303CarryIngressError
from .._observations_repository import (
    CalculationObservationRepository,
    ObservationSourceKind,
    ResultDispositionProjection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WHEN = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)
_POSTERIOR = Decimal("7.00")
_CREDIT = Decimal("20.00")


def _exported_fichero(tmp_path: Path, *, declaration_type: str) -> bytes:
    """Produce the header evidence through the production M303 exporter."""
    from ....application.filing import (
        ModeloDraftStatus,
        ModeloOperatorProfile,
        build_draft,
        build_runtime_schema_provider,
        export_draft,
    )
    from ....domain.calculations.registry import validated_casilla_id

    period = Period.from_year_and_code(2025, "1T")
    provider = build_runtime_schema_provider(
        modelos=("303",),
        filing_year=period.filing_year,
        period=period,
    )
    draft = build_draft(
        modelo="303",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="M303 ingress probe"),
        inputs={
            validated_casilla_id("07", surface="M303 ingress probe"): Decimal("10000.00"),
            validated_casilla_id("iva.repercutido.general", surface="M303 ingress probe"): Decimal("2100.00"),
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        },
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output = tmp_path / f"m303-{declaration_type}.txt"
    export_draft(
        draft,
        output_path=output,
        headers={
            "declaration_type": declaration_type,
            "surnames": "GARCIA LOPEZ",
            "full_name": "GARCIA LOPEZ JUAN",
            "program_version": "A001",
            "presenter_nif": "12345678Z",
            "redeme": "N",
        },
        schema_provider=provider,
    )
    return output.read_bytes()


def _header(code: str) -> ObservedHeaderFact:
    return ObservedHeaderFact(
        header_key="declaration_type",
        value=code,
        source_artefact_kind="submitted_file",
        source_locator=f"modelo-303-fichero-boe:modelo-303-page-01:declaration-type:{code}",
    )


def _observation(
    *,
    filing_year: int,
    result: Decimal,
    generated: Decimal | None = None,
    available: Decimal | None = None,
) -> RegistryModeloObservation:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period="1T")
    casillas = casillas_by_id(snapshot.revision)

    def observed(casilla_id: object, value: Decimal) -> CasillaObservation:
        # All values are built from the actual registry definition, so the
        # ingress check sees the same legal/source provenance storage will
        # validate rather than a hand-waved shape.
        definition = casillas[casilla_id]  # type: ignore[index]
        return CasillaObservation(
            casilla_id=casilla_id,  # type: ignore[arg-type]
            value=value,
            legal_refs=tuple(definition.legal_refs),
            source_refs=tuple(definition.source_refs),
        )

    rows = [
        observed(M303_COMPENSATION_POSTERIOR_CASILLA, _POSTERIOR),
        observed(M303_COMPENSATION_RESULTADO_CASILLA, result),
    ]
    if generated is not None:
        rows.append(observed(M303_COMPENSATION_GENERADA_CASILLA, generated))
    if available is not None:
        rows.append(observed(M303_COMPENSATION_AVAILABLE_CASILLA, available))
    return RegistryModeloObservation(
        modelo="303",
        filing_year=filing_year,
        period="1T",
        observations=tuple(rows),
    )


@pytest.mark.parametrize(
    ("code", "result"),
    [
        ("C", Decimal("-20.00")),
        ("D", Decimal("-20.00")),
        ("V", Decimal("-20.00")),
        ("X", Decimal("-20.00")),
        ("I", Decimal("20.00")),
        ("N", Decimal("0")),
        ("U", Decimal("20.00")),
        ("G", Decimal("20.00")),
    ],
)
def test_exporter_header_facts_reach_official_persistence_and_typed_recovery(
    tmp_path: Path,
    code: str,
    result: Decimal,
) -> None:
    """One real exporter->parser->official-storage chain for every M303 code.

    The bundled exporter fixture is structural evidence of the header wire
    shape, not a real AEAT refund specimen. Its synthetic calculation is not
    disposition-complete, so the persisted source observation states the
    independently required result-sign operands while the header facts are
    recovered only from the exporter-produced bytes.
    """
    payload = _exported_fichero(tmp_path, declaration_type=code)
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2025, period="1T")
    headers = _observed_header_facts_from_submitted_file(snapshot=snapshot, body=payload)

    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        persisted = repository.save_observation(
            _observation(
                filing_year=2025,
                result=result,
                generated=_CREDIT if result < 0 else None,
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=headers,
            normalize_m303_carry=True,
        )
        recovered = repository.load_observation("303", Period.from_year_and_code(2025, "1T"))

    assert tuple(fact.value for fact in headers if fact.header_key == "declaration_type") == (code,)
    assert recovered == persisted
    assert recovered is not None and recovered.result_disposition is not None
    assert recovered.result_disposition.disposition.value == code
    assert recovered.result_disposition.provenance_kind == "source_header"


@pytest.mark.parametrize(
    ("code", "result", "expected_available", "expected_generated", "expected_basis"),
    [
        ("C", Decimal("-20.00"), Decimal("27.00"), Decimal("20.00"), "generated"),
        ("D", Decimal("-20.00"), Decimal("7.00"), Decimal("0"), "refunded"),
        ("V", Decimal("-20.00"), Decimal("7.00"), Decimal("0"), "refunded"),
        ("X", Decimal("-20.00"), Decimal("7.00"), Decimal("0"), "refunded"),
        ("I", Decimal("20.00"), Decimal("7.00"), Decimal("0"), "resultado"),
        ("U", Decimal("20.00"), Decimal("7.00"), Decimal("0"), "resultado"),
        ("G", Decimal("20.00"), Decimal("7.00"), Decimal("0"), "resultado"),
        ("N", Decimal("0"), Decimal("7.00"), Decimal("0"), "resultado"),
    ],
)
def test_each_official_disposition_persists_and_recovers_a_structural_carry_projection(
    tmp_path: Path,
    code: str,
    result: Decimal,
    expected_available: Decimal,
    expected_generated: Decimal,
    expected_basis: str,
) -> None:
    """All M303 diseño codes pass through evidence -> typed payload -> recovery."""
    observation = _observation(
        filing_year=2025,
        result=result,
        generated=_CREDIT if result < 0 else None,
    )
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        persisted = repository.save_observation(
            observation,
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header(code),),
            normalize_m303_carry=True,
        )
        recovered = repository.load_observation("303", Period.from_year_and_code(2025, "1T"))

    assert recovered == persisted
    assert recovered is not None
    assert recovered.result_disposition is not None
    assert recovered.result_disposition.disposition.value == code
    assert recovered.result_disposition.provenance_kind == "source_header"
    assert recovered.m303_compensation_basis == expected_basis
    assert recovered.observation.casilla_values[M303_COMPENSATION_AVAILABLE_CASILLA] == expected_available
    assert recovered.observation.casilla_values[M303_COMPENSATION_GENERADA_CASILLA] == expected_generated


def test_identical_negative_inputs_diverge_only_by_carry_vs_refund_disposition(tmp_path: Path) -> None:
    """C and D share operands but cannot yield the same available carry."""
    observation = _observation(filing_year=2025, result=-_CREDIT, generated=_CREDIT)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        carried = repository.save_observation(
            observation,
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("C"),),
            normalize_m303_carry=True,
        )
        refunded = repository.save_observation(
            _observation(filing_year=2026, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            normalize_m303_carry=True,
        )

    assert carried.observation.casilla_values[M303_COMPENSATION_AVAILABLE_CASILLA] == Decimal("27.00")
    assert refunded.observation.casilla_values[M303_COMPENSATION_AVAILABLE_CASILLA] == _POSTERIOR
    assert refunded.m303_compensation_basis == "refunded"


def test_local_and_official_refund_ingress_normalize_the_same_carry_pair(tmp_path: Path) -> None:
    """Provenance differs; the normalized D/V/X refund pair does not."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        official = repository.save_observation(
            _observation(filing_year=2025, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            normalize_m303_carry=True,
        )
        local = repository.save_observation(
            _observation(filing_year=2026, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.APP_FILING,
            captured_at=_WHEN,
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.DEVOLUCION,
                provenance_kind="app_filing",
                provenance_locator="local-filing:303-2026-1T",
            ),
            normalize_m303_carry=True,
        )

    for casilla_id in (M303_COMPENSATION_AVAILABLE_CASILLA, M303_COMPENSATION_GENERADA_CASILLA):
        assert official.observation.casilla_values[casilla_id] == local.observation.casilla_values[casilla_id]
    assert official.m303_compensation_basis == local.m303_compensation_basis == "refunded"
    assert official.result_disposition is not None and local.result_disposition is not None
    assert official.result_disposition.provenance_kind == "source_header"
    assert local.result_disposition.provenance_kind == "app_filing"
    for normalized in (official, local):
        available = next(
            row for row in normalized.observation.observations if row.casilla_id == M303_COMPENSATION_AVAILABLE_CASILLA
        )
        generated = next(
            row for row in normalized.observation.observations if row.casilla_id == M303_COMPENSATION_GENERADA_CASILLA
        )
        assert available.formula_id is None
        assert available.operand_refs == ()
        assert generated.formula_id is None
        assert generated.operand_refs == ()


@pytest.mark.parametrize(
    ("headers", "result", "projection"),
    [
        ((), Decimal("-20.00"), None),
        ((_header("C"), _header("C")), Decimal("-20.00"), None),
        ((_header("Z"),), Decimal("-20.00"), None),
        ((_header("B"),), Decimal("-20.00"), None),
        ((_header("D"),), Decimal("20.00"), None),
        (
            (_header("D"),),
            Decimal("-20.00"),
            ResultDispositionProjection(
                disposition=ResultDisposition.COMPENSACION,
                provenance_kind="source_header",
                provenance_locator="conflicting-projection",
            ),
        ),
    ],
)
def test_official_ingress_refuses_missing_ambiguous_invalid_sign_incompatible_or_conflicting_evidence(
    tmp_path: Path,
    headers: tuple[ObservedHeaderFact, ...],
    result: Decimal,
    projection: ResultDispositionProjection | None,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(M303CarryIngressError):
        CalculationObservationRepository().save_observation(
            _observation(filing_year=2025, result=result, generated=_CREDIT if result < 0 else None),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=headers,
            result_disposition=projection,
            normalize_m303_carry=True,
        )


def test_ingress_refuses_an_explicit_available_value_that_contradicts_its_disposition(tmp_path: Path) -> None:
    """A semantic available value does not override a contradictory carry policy."""
    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(M303CarryIngressError):
        CalculationObservationRepository().save_observation(
            _observation(
                filing_year=2025,
                result=-_CREDIT,
                generated=_CREDIT,
                available=Decimal("999.00"),
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            normalize_m303_carry=True,
        )


def test_ingress_refuses_a_preexisting_available_generated_pair_that_conflicts_with_refund(tmp_path: Path) -> None:
    """A normalized-looking available value cannot mask a still-carried credit."""
    with isolated_runtime_profile(tmp_path=tmp_path), pytest.raises(M303CarryIngressError):
        CalculationObservationRepository().save_observation(
            _observation(
                filing_year=2025,
                result=-_CREDIT,
                generated=_CREDIT,
                available=_POSTERIOR,
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            normalize_m303_carry=True,
        )


def _persist_history_projection(
    repository: CalculationObservationRepository,
    payload: object,
    *,
    filing_ref: str,
):
    from .._observations_repository import ObservationEnvelopePayload

    if not isinstance(payload, ObservationEnvelopePayload):
        raise AssertionError("history projection requires an observation envelope")
    history_repository = IvaCompensationHistoryRepository(objects=repository.secure_object_repository)
    return persist_observation_envelope_and_iva_history(
        observation_repository=repository,
        history_repository=history_repository,
        envelope=payload,
        taxpayer_nif="12345678Z",
        expediente_id=filing_ref,
        status="ALTA",
        source_observation_key=f"303:{payload.observation.filing_year}:1T:{filing_ref}",
    )


def test_history_refuses_a_direct_available_generated_pair_mismatch_before_either_row_is_written(
    tmp_path: Path,
) -> None:
    """A semantic available does not get a second chance to win in history."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        payload = repository.prepare_observation_envelope(
            _observation(
                filing_year=2025,
                result=-_CREDIT,
                generated=_CREDIT,
                available=Decimal("999.00"),
            ),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.DEVOLUCION,
                provenance_kind="source_header",
                provenance_locator="test:decl-type:D",
            ),
        ).model_copy(update={"m303_compensation_basis": "refunded"})

        with pytest.raises(M303CarryIngressError):
            _persist_history_projection(repository, payload, filing_ref="EXP-MISMATCH")

        assert repository.load_observation("303", Period.from_year_and_code(2025, "1T")) is None
        assert (
            IvaCompensationHistoryRepository(objects=repository.secure_object_repository).load_period(
                Period.from_year_and_code(2025, "1T")
            )
            is None
        )


def test_generic_storage_admits_undisposed_official_m303_and_only_carry_refuses(tmp_path: Path) -> None:
    """Generic storage persists official M303 evidence with no resolved disposition.

    This records a KNOWN OPEN GAP, not a designed tolerance. An official Modelo
    303 observation that resolves no result disposition is stored and reloads
    equal; nothing refuses it until a downstream reader tries to treat it as
    carry evidence. Until then the row sits in the store looking like every
    other official observation.

    A refusal was attempted at this write boundary twice and removed both
    times. The reason it was removed is worth more than the attempts: the
    discriminating fact is not present in the payload. Keying on a resolved
    disposition refused callers whose disposition was fully evidenced by the
    submitted-file declaration-type header; keying additionally on that header
    still refused a large legitimate population that carries no header at all,
    because the casilla that makes a row look carry-capable is the ordinary
    statutory result box every M303 observation declares. So the condition
    separating an under-declared row from a legitimate one cannot be read from
    what the envelope carries at the moment it is written.

    The gap is carried as tracked work rather than closed here. This test is
    the honest statement of the current behaviour, so a later reader finds the
    hole described rather than finding silence and inferring intent.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        undisposed = repository.save_observation(
            _observation(filing_year=2025, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("C"),),
        )

        assert repository.load_observation("303", Period.from_year_and_code(2025, "1T")) == undisposed
        with pytest.raises(M303CarryIngressError):
            iva_compensation_state_from_observation_envelope(
                undisposed,
                taxpayer_nif="12345678Z",
                expediente_id="EXP-UNDISPOSED",
                status="ALTA",
                source_observation_key="303:2025:1T:EXP-UNDISPOSED",
            )


def test_history_refuses_typed_disposition_that_conflicts_with_the_official_header(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        conflicting = repository.prepare_observation_envelope(
            _observation(filing_year=2025, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.COMPENSACION,
                provenance_kind="source_header",
                provenance_locator="test:conflicting-typed-projection",
            ),
        )

        with pytest.raises(M303CarryIngressError):
            _persist_history_projection(repository, conflicting, filing_ref="EXP-TYPED-CONFLICT")

        assert repository.load_observation("303", Period.from_year_and_code(2025, "1T")) is None
        assert (
            IvaCompensationHistoryRepository(objects=repository.secure_object_repository).load_period(
                Period.from_year_and_code(2025, "1T")
            )
            is None
        )


def test_official_and_local_history_projections_share_the_refunded_pair(tmp_path: Path) -> None:
    """The two ingress provenances produce one D disposition-aware history state."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        official = repository.prepare_observation_envelope(
            _observation(filing_year=2025, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            normalize_m303_carry=True,
        )
        local = repository.prepare_observation_envelope(
            _observation(filing_year=2026, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.APP_FILING,
            captured_at=_WHEN,
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.DEVOLUCION,
                provenance_kind="app_filing",
                provenance_locator="local-filing:303-2026-1T",
            ),
            normalize_m303_carry=True,
        )

        official_state = _persist_history_projection(repository, official, filing_ref="EXP-OFFICIAL")
        local_state = _persist_history_projection(repository, local, filing_ref="EXP-LOCAL")

    assert official_state.generated_amount == local_state.generated_amount == Decimal("0")
    assert official_state.available_end_amount == local_state.available_end_amount == _POSTERIOR


def test_identical_negative_casillas_produce_distinct_compensation_and_refund_history_states(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        carried = repository.prepare_observation_envelope(
            _observation(filing_year=2025, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("C"),),
            normalize_m303_carry=True,
        )
        refunded = repository.prepare_observation_envelope(
            _observation(filing_year=2026, result=-_CREDIT, generated=_CREDIT),
            source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            captured_at=_WHEN,
            source_headers=(_header("D"),),
            normalize_m303_carry=True,
        )

        carried_state = _persist_history_projection(repository, carried, filing_ref="EXP-C")
        refunded_state = _persist_history_projection(repository, refunded, filing_ref="EXP-D")

    assert carried_state.generated_amount == _CREDIT
    assert carried_state.available_end_amount == _POSTERIOR + _CREDIT
    assert refunded_state.generated_amount == Decimal("0")
    assert refunded_state.available_end_amount == _POSTERIOR
