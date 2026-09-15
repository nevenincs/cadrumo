"""Semantic-role resolver guards for canonical casilla.id emission."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from importlib import import_module

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.errors import ModeloError
from ..semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
    casilla_id_for_unique_semantic_role,
)

binding_resolution = import_module("..binding_resolution", package=__package__)
calculate_input = import_module("..calculate_input", package=__package__)
dt12_advisory = import_module("..dt12_advisory", package=__package__)
taxation_comparison = import_module("..taxation_comparison", package=__package__)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_M100_RESULTADO_CASILLA: CasillaId = validated_casilla_id("0610", surface="_M100_RESULTADO_CASILLA")
# The Art. 20 mapping fact carries these role tokens.  The advisory module now
# resolves that mapping rather than exporting a second role vocabulary.
_ART20_RNT_ROLE = "irpf_rendimiento_trabajo_rendimiento_neto"
_ART20_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion_gastos_generales"


@pytest.fixture(scope="module")
def snapshot_2025() -> RegistrySnapshot:
    """Real Modelo 100 2025 registry snapshot."""
    return compiled_bundled_authority().snapshot("100", filing_year=2025, period="0A")


def test_unique_semantic_role_resolves_canonical_casilla_id(snapshot_2025: RegistrySnapshot) -> None:
    casilla_id = casilla_id_for_unique_semantic_role(
        snapshot_2025,
        taxation_comparison._RESULTADO_ROLE,
    )

    assert casilla_id == _M100_RESULTADO_CASILLA
    assert casilla_id in {casilla.id for casilla in snapshot_2025.revision.casillas}


def test_missing_semantic_role_returns_none(snapshot_2025: RegistrySnapshot) -> None:
    assert casilla_id_for_unique_semantic_role(snapshot_2025, "not_a_declared_semantic_role") is None


def test_ambiguous_semantic_role_refuses_before_choosing_a_casilla(snapshot_2025: RegistrySnapshot) -> None:
    snapshot, casilla_ids = _snapshot_with_duplicate_role(snapshot_2025, taxation_comparison._RESULTADO_ROLE)

    with pytest.raises(AmbiguousSemanticRoleCasillaError) as raised:
        casilla_id_for_unique_semantic_role(snapshot, taxation_comparison._RESULTADO_ROLE)

    assert raised.value.ambiguity.modelo_id == "100"
    assert raised.value.ambiguity.revision_id == "2025"
    assert raised.value.ambiguity.casilla_ids == casilla_ids


def test_application_single_casilla_resolver_roles_are_unambiguous_in_bundled_registry() -> None:
    modelos = compiled_bundled_authority().modelos
    offences: list[str] = []

    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            for role in _application_single_casilla_roles():
                try:
                    casilla_id_for_unique_revision_semantic_role(revision, role, modelo_id=modelo.id)
                except AmbiguousSemanticRoleCasillaError as exc:
                    offences.append(
                        f"modelo {modelo.id} revision {revision_id} role {role!r} "
                        f"matches {exc.ambiguity.casilla_ids!r}",
                    )

    assert not offences, "application semantic-role casilla references are ambiguous:\n  " + "\n  ".join(offences)


def test_declaration_period_inputs_refuse_ambiguous_semantic_role() -> None:
    snapshot = compiled_bundled_authority().snapshot("303", filing_year=2025, period="1T")
    original = next(casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == "filing_year")
    duplicate = original.model_copy(update={"id": f"ambiguous-{original.id}"})
    revision = snapshot.revision.model_copy(update={"casillas": (*snapshot.revision.casillas, duplicate)})

    with pytest.raises(ModeloError, match="multiple casillas"):
        binding_resolution._resolve_declaration_period_inputs(
            revision,
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
        )


@pytest.mark.parametrize(
    ("period_code", "expected_token"),
    [("1T", "1T"), ("3T", "3T")],
)
def test_declaration_period_inputs_project_real_registry_period_token(
    period_code: str,
    expected_token: str,
) -> None:
    """The ``filing_period`` role lands on the string channel as the AEAT token.

    The casilla declares ``data_type = "period_code"``, so its value belongs on
    the typed text-scalar channel; the Decimal channel carries only the
    int-family ``filing_year`` role.
    """
    snapshot = compiled_bundled_authority().snapshot("303", filing_year=2025, period=period_code)
    filing_period = next(casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == "filing_period")
    filing_year = next(casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == "filing_year")

    resolved = binding_resolution.resolve_declaration_period_inputs(
        snapshot.revision,
        filing_year=2025,
        period=Period.from_year_and_code(2025, period_code),
    )

    assert resolved.text_casilla_inputs[filing_period.id] == expected_token
    assert filing_period.id not in resolved.casilla_inputs
    assert resolved.casilla_inputs[filing_year.id] == Decimal("2025")


def test_declaration_period_inputs_express_an_extended_oss_period() -> None:
    """An ``EXT-`` quarter is expressible; the retired ordinal projection was not.

    The retired ``declaration_period_ordinal`` projection returned ``None`` for
    every extended OSS/IOSS token, so the previous ordinal fill raised for
    Modelo 369 rather than producing a value. The token is total over every
    declared period form, which is what makes this case expressible at all.
    """
    snapshot = compiled_bundled_authority().snapshot("369", filing_year=2025, period="EXT-1T")
    filing_period = next(casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == "filing_period")
    period = Period.from_year_and_code(2025, "EXT-1T")

    resolved = binding_resolution.resolve_declaration_period_inputs(
        snapshot.revision,
        filing_year=2025,
        period=period,
    )

    assert resolved.text_casilla_inputs[filing_period.id] == "EXT-1T"


def _snapshot_with_duplicate_role(
    snapshot: RegistrySnapshot,
    semantic_role: str,
) -> tuple[RegistrySnapshot, tuple[CasillaId, CasillaId]]:
    original = next(casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == semantic_role)
    duplicate_id: CasillaId = validated_casilla_id(
        f"ambiguous-{original.id}",
        surface="_snapshot_with_duplicate_role duplicate casilla.id",
    )
    duplicate = original.model_copy(update={"id": duplicate_id})
    revision = snapshot.revision.model_copy(update={"casillas": (*snapshot.revision.casillas, duplicate)})
    return snapshot.model_copy(update={"revision": revision}), (original.id, duplicate_id)


def _application_single_casilla_roles() -> Iterable[str]:
    return frozenset(
        {
            _ART20_RNT_ROLE,
            _ART20_REDUCCION_ROLE,
            "irpf_deduccion_maternidad",
            "irpf_rendimiento_trabajo_prestacion_inss_maternidad_paternidad_exenta",
            "irpf_rendimiento_trabajo_reduccion",
            "is_sal_reserva_especial_dotacion",
            "irpf_rendimiento_trabajo_importe_integro_dinerario",
            "filing_period",
            "filing_year",
            _require_semantic_role(taxation_comparison._CUOTA_RESULTANTE_ROLE),
            _require_semantic_role(taxation_comparison._RESULTADO_ROLE),
        },
    )


def _require_semantic_role(value: object) -> str:
    """Narrow dynamically imported module attributes to the role contract."""
    if not isinstance(value, str):
        raise TypeError(f"semantic role must be a string, got {type(value).__name__}")
    return value
