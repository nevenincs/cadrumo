"""Semantic-role resolver guards for canonical casilla.id emission."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from ....core import Period
from ....core.resources import bundled_path, resources
from ....domain.calculations.registry import CasillaId, RegistrySnapshot, load_registry_tree, validated_casilla_id
from ....domain.modelos._errors import ModeloError
from .. import _art20_advisory as art20_advisory
from .. import _binding_resolution as binding_resolution
from .. import _calculate_input as calculate_input
from .. import _dt12_advisory as dt12_advisory
from .. import _taxation_comparison as taxation_comparison
from .._semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
    casilla_id_for_unique_semantic_role,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_M100_RESULTADO_CASILLA: CasillaId = validated_casilla_id("0610", surface="_M100_RESULTADO_CASILLA")


@pytest.fixture(scope="module")
def snapshot_2025() -> RegistrySnapshot:
    """Real Modelo 100 2025 registry snapshot."""
    return resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")


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
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
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
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2025, period="1T")
    original = next(casilla for casilla in snapshot.revision.casillas if casilla.semantic_role == "filing_year")
    duplicate = original.model_copy(update={"id": f"ambiguous-{original.id}"})
    revision = snapshot.revision.model_copy(update={"casillas": (*snapshot.revision.casillas, duplicate)})

    with pytest.raises(ModeloError, match="multiple casillas"):
        binding_resolution._resolve_declaration_period_inputs(
            revision,
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
        )


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
            art20_advisory._ART20_RNT_ROLE,
            art20_advisory._ART20_REDUCCION_ROLE,
            calculate_input._DEDUCCION_MATERNIDAD_SEMANTIC_ROLE,
            calculate_input._INSS_EXENTA_SEMANTIC_ROLE,
            calculate_input._REDUCCION_TRABAJO_SEMANTIC_ROLE,
            calculate_input._SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE,
            dt12_advisory._DT12_TRABAJO_INGRESO_ROLE,
            dt12_advisory._DT12_TRABAJO_REDUCCION_ROLE,
            "filing_period",
            "filing_year",
            taxation_comparison._CUOTA_RESULTANTE_ROLE,
            taxation_comparison._RESULTADO_ROLE,
        },
    )
