"""Live source resolver tests for ``prorrata_regularizacion``.

These tests exercise the source-mesh resolver without enrolling it in the mesh:
the resolver consumes current-year registry values supplied by the
materialisation seam, then sources the provisional percentage from the real
encrypted prorrata register or a stamped prior Modelo 303 observation.

See Also:
    :class:`~application.calculations._prorrata_regularizacion.ProrrataRegularizacionSourceResolver`
        Live resolver under test for the prorrata regularización source.
    :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
        Encrypted profile-scoped carry store used by the register-backed branch.
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Typed provisional-percentage carry record consumed by the resolver.
    :class:`~application.aggregation.CalculationSourceContext`
        Source-mesh context passed into resolver execution.
        The accepted carry model and implementation guardrails for this source.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core import BindingSourceKind, Modelo, Period, ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import CasillaId, RegistrySnapshot, validated_casilla_id
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .._observations_repository import CalculationObservationRepository
from .._prorrata_regularizacion import ProrrataRegularizacionSourceResolver

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORACLE_PATH = Path(
    bundled_path("corpus", "manual_oracles", "modelo-303-2025-prorrata-general-regularizacion.json"),
)
_BUCKET_ID = "prorrata-regularizacion-source-resolver"
_FILING_YEAR = 2025
_PRIOR_YEAR = _FILING_YEAR - 1
_CAPTURED_AT = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)

_CUOTA_DEDUCIBLE_TOTAL_ID: CasillaId = validated_casilla_id(
    "iva.cuota-deducible-total",
    surface="test casilla id",
)
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")

_FIRST_THREE_QUARTERS_INPUT_IVA = Decimal("1280.00")
_MANUAL_PROVISIONAL_PERCENTAGE = Decimal("73")
#: The manual's current-year 'n' operations (locales 25.000 con derecho,
#: viviendas 20.000 exentas, total 45.000) and the "Exceso de deduccion: 217,60"
#: it carries into Modelo 303 casilla 44 as a lower deduction. These are the
#: scenario's givens and a resolver-produced value, so they are named constants
#: quoting `corpus/manuals/iva/2025/source.pdf#Pag.137-138` rather than entries
#: in the payload's `expected_by_casilla_id`, which is reserved for casillas the
#: registry engine computes and a verification expectation reconciles.
_MANUAL_CURRENT_YEAR_CON_DERECHO = Decimal("25000.00")
_MANUAL_CURRENT_YEAR_TOTAL = Decimal("45000.00")
_MANUAL_CASILLA_44_REGULARIZACION = Decimal("-217.60")
_M303_BINDING_ID = "modelo-303-prorrata-regularizacion-casilla-44"
_M390_BINDING_ID = "modelo-390-prorrata-regularizacion-anual"


def _oracle_payload() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


def _oracle_expected(casilla_id: CasillaId) -> Decimal:
    raw = _oracle_payload()["expected_by_casilla_id"][str(casilla_id)]
    return Decimal(str(raw))


def _current_year_values() -> dict[CasillaId, Decimal]:
    return {
        _CUOTA_DEDUCIBLE_TOTAL_ID: _FIRST_THREE_QUARTERS_INPUT_IVA,
        _VOLUMEN_CON_DERECHO_ID: _MANUAL_CURRENT_YEAR_CON_DERECHO,
        _VOLUMEN_TOTAL_ID: _MANUAL_CURRENT_YEAR_TOTAL,
        _PORCENTAJE_ID: _oracle_expected(_PORCENTAJE_ID),
    }


def _snapshot(modelo: str, period: str) -> RegistrySnapshot:
    return resources().modelos.authority.snapshot(modelo, filing_year=_FILING_YEAR, period=period)


def _context(snapshot: RegistrySnapshot, *, modelo: str, period: str) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period),
        revision=snapshot.revision,
    )


def _register_with_carried_prior() -> ProrrataRegister:
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_FILING_YEAR,
                regime=ProrrataRegisterRegime.GENERAL,
                provisional_percentage=_MANUAL_PROVISIONAL_PERCENTAGE,
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref=f"{Modelo.M303.value}:{_PRIOR_YEAR}:4T",
            ),
        ),
    )


def _save_prior_observation(repository: CalculationObservationRepository) -> None:
    repository.save_observation(
        registry_grounded_modelo_observation(
            modelo=Modelo.M303.value,
            filing_year=_PRIOR_YEAR,
            period="4T",
            casilla_values={_PORCENTAJE_ID: _MANUAL_PROVISIONAL_PERCENTAGE},
        ),
        source_kind="app_filing",
        captured_at=_CAPTURED_AT,
    )


def test_resolver_projects_modelo_303_binding_from_prorrata_register(tmp_path: Path) -> None:
    """The register-backed resolver emits the AEAT manual casilla-44 value."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        register_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        register_repository.save(_register_with_carried_prior())
        snapshot = _snapshot(Modelo.M303.value, "4T")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=_current_year_values(),
            prorrata_register_repository=register_repository,
            registry_snapshot=snapshot,
        ).resolve(_context(snapshot, modelo=Modelo.M303.value, period="4T"))

    assert resolution.owned_sources == (BindingSourceKind.PRORRATA_REGULARIZACION,)
    assert resolution.binding_values[_M303_BINDING_ID] == _MANUAL_CASILLA_44_REGULARIZACION
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()
    assert {row.source_ref for row in resolution.provenance} == {
        "303:2025:1T,2T,3T,4T:prorrata-current-year-values",
        "prorrata-register:2025:carried_prior_definitiva:303:2024:4T",
    }


def test_resolver_falls_back_to_stamped_prior_observation_for_modelo_390(tmp_path: Path) -> None:
    """A stamped prior M303 settlement observation can source the annual M390 binding."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        _save_prior_observation(observation_repository)
        register_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        snapshot = _snapshot(Modelo.M390.value, "0A")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=_current_year_values(),
            prorrata_register_repository=register_repository,
            observation_repository=observation_repository,
            registry_snapshot=snapshot,
        ).resolve(_context(snapshot, modelo=Modelo.M390.value, period="0A"))

    assert resolution.binding_values == {_M390_BINDING_ID: _MANUAL_CASILLA_44_REGULARIZACION}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()
    assert "303:2024:4T:iva.prorrata-porcentaje" in {row.source_ref for row in resolution.provenance}


def test_resolver_marks_binding_unresolved_when_no_provisional_source_exists(tmp_path: Path) -> None:
    """No register value and no stamped prior observation produce an unresolved binding diagnostic."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        register_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        snapshot = _snapshot(Modelo.M303.value, "4T")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=_current_year_values(),
            prorrata_register_repository=register_repository,
            registry_snapshot=snapshot,
        ).resolve(_context(snapshot, modelo=Modelo.M303.value, period="4T"))

    assert resolution.binding_values == {}
    assert resolution.unresolved_binding_ids == (_M303_BINDING_ID,)
    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "unresolved_binding"
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert diagnostic.binding_id == _M303_BINDING_ID
    assert "stamped prior-year Modelo 303" in diagnostic.message


def test_resolver_marks_binding_unresolved_when_current_year_values_are_missing(tmp_path: Path) -> None:
    """Missing current-year registry values block resolution before any zero can be inferred."""
    current_year_values = _current_year_values()
    del current_year_values[_PORCENTAJE_ID]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        register_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        register_repository.save(_register_with_carried_prior())
        snapshot = _snapshot(Modelo.M303.value, "4T")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=current_year_values,
            prorrata_register_repository=register_repository,
            registry_snapshot=snapshot,
        ).resolve(_context(snapshot, modelo=Modelo.M303.value, period="4T"))

    assert resolution.binding_values == {}
    assert resolution.unresolved_binding_ids == (_M303_BINDING_ID,)
    assert len(resolution.diagnostics) == 1
    diagnostic = resolution.diagnostics[0]
    assert diagnostic.reason == "unresolved_binding"
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert diagnostic.binding_id == _M303_BINDING_ID
    assert str(_PORCENTAJE_ID) in diagnostic.message
