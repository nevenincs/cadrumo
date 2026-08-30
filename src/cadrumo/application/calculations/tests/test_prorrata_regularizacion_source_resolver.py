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

import ast
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast, override

import pytest

from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....core import Modelo, ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.aggregation import BindingSourceKind
from ....core.directory_scan import (
    scan_directory,
)
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....tests.registry_observations import registry_grounded_modelo_observation
from ....tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from ...aggregation import CalculationSourceContext
from .._prorrata_regularizacion import ProrrataRegularizacionSourceResolver
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORACLE_PATH = Path(
    bundled_path("corpus", "manual_oracles", "modelo-303-2025-prorrata-general-regularizacion.json"),
)
_BUCKET_ID = "ca06894b-1eb7-4f25-b325-531f43bc0e48"  # was 'prorrata-regularizacion-source-resolver'
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


def _called_name(node: ast.Call) -> str | None:
    """Return a direct callee name, including an ``Any``-cast target."""
    match node.func:
        case ast.Name(id=name):
            return name
        case ast.Call(
            func=ast.Name(id="cast") | ast.Attribute(value=ast.Name(id="typing"), attr="cast"),
            args=[
                ast.Name(id="Any") | ast.Attribute(value=ast.Name(id="typing"), attr="Any"),
                ast.Name(id=name),
            ],
        ):
            return name
        case _:
            return None


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
    return bundled_authority().snapshot(modelo, filing_year=_FILING_YEAR, period=period)


def _context(
    snapshot: RegistrySnapshot,
    *,
    modelo: str,
    period: str,
    bucket_id: str = _BUCKET_ID,
) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period),
        revision=snapshot.revision,
    )


def _register_with_carried_prior(
    *,
    provisional_percentage: Decimal = _MANUAL_PROVISIONAL_PERCENTAGE,
) -> ProrrataRegister:
    return ProrrataRegister(
        entries=(
            ProrrataRegisterEntry(
                ejercicio=_FILING_YEAR,
                regime=ProrrataRegisterRegime.GENERAL,
                especial_transition=None,
                provisional_percentage=provisional_percentage,
                provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                source_observation_ref=f"{Modelo.M303.value}:{_PRIOR_YEAR}:4T",
            ),
        ),
    )


def _save_prior_observation(
    repository: CalculationObservationRepository,
    *,
    percentage: Decimal = _MANUAL_PROVISIONAL_PERCENTAGE,
) -> None:
    repository.save(
        repository.prepare_observation_envelope(
            registry_grounded_modelo_observation(
                modelo=Modelo.M303.value,
                filing_year=_PRIOR_YEAR,
                period="4T",
                casilla_values={_PORCENTAJE_ID: percentage},
            ),
            source_kind="app_filing",
            captured_at=_CAPTURED_AT,
        )
    )


def test_resolver_projects_modelo_303_binding_from_prorrata_register(tmp_path: Path) -> None:
    """The register-backed resolver emits the AEAT manual casilla-44 value."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        register_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        register_repository.save(_register_with_carried_prior())
        snapshot = _snapshot(Modelo.M303.value, "4T")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=_current_year_values(),
            prorrata_register_repository=register_repository,
            observation_repository=observation_repository,
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


def test_resolver_uses_the_explicit_secondary_prorrata_store_while_primary_is_active(tmp_path: Path) -> None:
    """An explicitly injected secondary register cannot be shadowed by the active primary store."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        primary_repository = ProrrataRegisterRepository(
            bucket_id=runtime.primary.bucket_id,
            objects=runtime.primary.repository,
        )
        with runtime.switch_to_secondary():
            secondary_repository = ProrrataRegisterRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            secondary_observation_repository = CalculationObservationRepository(objects=runtime.secondary.repository)
            secondary_repository.save(_register_with_carried_prior(provisional_percentage=Decimal("80")))
            snapshot = _snapshot(Modelo.M303.value, "4T")

            resolution = ProrrataRegularizacionSourceResolver(
                current_year_values=_current_year_values(),
                prorrata_register_repository=secondary_repository,
                observation_repository=secondary_observation_repository,
                registry_snapshot=snapshot,
            ).resolve(
                _context(
                    snapshot,
                    modelo=Modelo.M303.value,
                    period="4T",
                    bucket_id=runtime.secondary.bucket_id,
                )
            )

        assert primary_repository.load().entries == ()

    assert resolution.binding_values == {_M303_BINDING_ID: Decimal("-307.20")}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()


def test_resolver_uses_the_explicit_secondary_observation_store_while_primary_is_active(tmp_path: Path) -> None:
    """A prior-period percentage can only arrive from the explicitly injected target store."""
    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        primary_observations = CalculationObservationRepository(objects=runtime.primary.repository)
        _save_prior_observation(primary_observations, percentage=Decimal("60"))
        with runtime.switch_to_secondary():
            secondary_observations = CalculationObservationRepository(objects=runtime.secondary.repository)
            _save_prior_observation(secondary_observations, percentage=Decimal("80"))
            secondary_register = ProrrataRegisterRepository(
                bucket_id=runtime.secondary.bucket_id,
                objects=runtime.secondary.repository,
            )
            snapshot = _snapshot(Modelo.M390.value, "0A")
            resolution = ProrrataRegularizacionSourceResolver(
                current_year_values=_current_year_values(),
                prorrata_register_repository=secondary_register,
                observation_repository=secondary_observations,
                registry_snapshot=snapshot,
            ).resolve(
                _context(
                    snapshot,
                    modelo=Modelo.M390.value,
                    period="0A",
                    bucket_id=runtime.secondary.bucket_id,
                ),
            )

        primary_prior = primary_observations.load_observation(
            Modelo.M303.value,
            Period.from_year_and_code(_PRIOR_YEAR, "4T"),
        )

    assert primary_prior is not None
    assert primary_prior.observation.casilla_values[_PORCENTAJE_ID] == Decimal("60")
    assert resolution.binding_values == {_M390_BINDING_ID: Decimal("-307.20")}
    assert "303:2024:4T:iva.prorrata-porcentaje" in {row.source_ref for row in resolution.provenance}


def test_resolver_refuses_construction_without_an_explicit_prorrata_repository() -> None:
    """The dependency is mandatory; callers cannot re-enter a hidden default path."""
    with pytest.raises(TypeError, match="prorrata_register_repository"):
        cast(Any, ProrrataRegularizacionSourceResolver)(current_year_values=_current_year_values())


def test_resolver_refuses_construction_without_an_explicit_observation_repository(tmp_path: Path) -> None:
    """The cross-period evidence dependency cannot re-enter through an active-store default."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        register_repository = ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        with pytest.raises(TypeError, match="observation_repository"):
            cast(Any, ProrrataRegularizacionSourceResolver)(
                current_year_values=_current_year_values(),
                prorrata_register_repository=register_repository,
            )


def test_prorrata_repository_caller_ast_census_has_only_explicit_dependencies() -> None:
    """Every production/test consumer names its store; only two contract-refusal probes omit it."""
    target_calls = {
        "ProrrataRegularizacionSourceResolver",
        "_resolve_iva_deduction_ratio",
        "_resolve_prorrata_regularizacion_sources",
        "resolve_prorrata_regularizacion_sources",
        "aggregate_renta_ledger_expenses_from_repositories",
        "aggregate_renta_gasto_ledger_from_repositories",
        "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
        "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
    }
    intentional_refusals = {
        (
            "application/aggregation/tests/test_renta_ledger.py",
            "test_repository_wrapper_refuses_an_implicit_prorrata_repository",
            "aggregate_renta_ledger_expenses_from_repositories",
        ),
        (
            "application/calculations/tests/test_prorrata_regularizacion_source_resolver.py",
            "test_resolver_refuses_construction_without_an_explicit_prorrata_repository",
            "ProrrataRegularizacionSourceResolver",
        ),
    }
    source_root = Path(__file__).parents[3]
    omitted: set[tuple[str, str, str]] = set()
    direct_constructor_calls: list[tuple[Path, int]] = []

    class _CallerCensus(ast.NodeVisitor):
        def __init__(self, source_path: Path) -> None:
            self._source_path = source_path
            self._current_function = "<module>"

        @override
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self._current_function
            self._current_function = node.name
            self.generic_visit(node)
            self._current_function = previous

        @override
        def visit_Call(self, node: ast.Call) -> None:
            called_name = _called_name(node)
            if called_name in target_calls and not any(
                keyword.arg == "prorrata_register_repository" for keyword in node.keywords
            ):
                omitted.add(
                    (
                        self._source_path.relative_to(source_root).as_posix(),
                        self._current_function,
                        called_name,
                    )
                )
            if called_name == "ProrrataRegisterRepository":
                direct_constructor_calls.append((self._source_path, node.lineno))
            self.generic_visit(node)

    for source_path in scan_directory(source_root, pattern="*.py", recursive=True):
        census = _CallerCensus(source_path)
        census.visit(ast.parse(source_path.read_text(encoding="utf-8")))

    assert omitted == intentional_refusals
    fallback_modules = {
        source_root / "application" / "calculations" / "_prorrata_regularizacion.py",
        source_root / "application" / "aggregation" / "_renta_ledger.py",
    }
    assert not [
        (source_path, line_number)
        for source_path, line_number in direct_constructor_calls
        if source_path in fallback_modules
    ]


def test_prorrata_observation_repository_caller_ast_census_has_only_explicit_dependencies() -> None:
    """Every prorrata source consumer names its observation store; defaults cannot return."""
    target_calls = {
        "ProrrataRegularizacionSourceResolver",
        "resolve_prorrata_regularizacion_sources",
    }
    intentional_refusals = {
        (
            "application/calculations/tests/test_prorrata_regularizacion_source_resolver.py",
            "test_resolver_refuses_construction_without_an_explicit_prorrata_repository",
        ),
        (
            "application/calculations/tests/test_prorrata_regularizacion_source_resolver.py",
            "test_resolver_refuses_construction_without_an_explicit_observation_repository",
        ),
    }
    source_root = Path(__file__).parents[3]
    omitted: set[tuple[str, str]] = set()

    class _CallerCensus(ast.NodeVisitor):
        def __init__(self, source_path: Path) -> None:
            self._source_path = source_path
            self._current_function = "<module>"

        @override
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self._current_function
            self._current_function = node.name
            self.generic_visit(node)
            self._current_function = previous

        @override
        def visit_Call(self, node: ast.Call) -> None:
            called_name = _called_name(node)
            if called_name in target_calls and not any(
                keyword.arg == "observation_repository" for keyword in node.keywords
            ):
                omitted.add((self._source_path.relative_to(source_root).as_posix(), self._current_function))
            self.generic_visit(node)

    for source_path in scan_directory(source_root, pattern="*.py", recursive=True):
        source = source_path.read_text(encoding="utf-8")
        if not any(target_call in source for target_call in target_calls):
            continue
        census = _CallerCensus(source_path)
        census.visit(ast.parse(source))

    assert omitted == intentional_refusals
    fallback_module = source_root / "application" / "calculations" / "_prorrata_regularizacion.py"
    assert not [
        node.lineno
        for node in ast.walk(ast.parse(fallback_module.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CalculationObservationRepository"
    ]
    action_module = source_root / "application" / "modelo" / "_calculation_actions.py"
    action_repository_calls = [
        node
        for node in ast.walk(ast.parse(action_module.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CalculationObservationRepository"
    ]
    assert len(action_repository_calls) == 1
    action_keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in action_repository_calls[0].keywords}
    assert action_keywords == {"bucket_id": "work_unit.bucket_id"}


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
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        snapshot = _snapshot(Modelo.M303.value, "4T")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=_current_year_values(),
            prorrata_register_repository=register_repository,
            observation_repository=observation_repository,
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
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        register_repository.save(_register_with_carried_prior())
        snapshot = _snapshot(Modelo.M303.value, "4T")

        resolution = ProrrataRegularizacionSourceResolver(
            current_year_values=current_year_values,
            prorrata_register_repository=register_repository,
            observation_repository=observation_repository,
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
