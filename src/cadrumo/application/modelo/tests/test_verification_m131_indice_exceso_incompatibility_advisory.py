"""Modelo 131 2025 índice corrector de exceso (b.3) incompatibility advisory tests.

Covers the ``modelo-131-2025-modulos-indice-exceso-incompatible-*`` ADVISORY
guards shipped on the 2025 revision. Orden HAC/1347/2024, Anexo II,
instrucción 2.3 fixes two binding incompatibility rules the índice-exceso
formula (``m131_resolve_modulos_indice_exceso``,
``cmodulos-epigrafe__cmodulos-rendimiento-neto-actividad.toml``) applies unconditionally, without cross-checking
either:

- "En ningún caso será aplicable el índice corrector para empresas de pequeña
  dimensión (b.1) a las actividades para las que están previstos los índices
  correctores especiales enumerados en las letras a.2), a.3), a.4) y a.5)."
- "Cuando resulte aplicable el índice corrector para empresas de pequeña
  dimensión (b.1) no se aplicará el índice corrector de exceso (b.3)."

Two of the tabled epígrafes in ``m131-modulos-cuantia-exceso-2025`` carry a
documented índice especial: "721.2" (transporte por autotaxis, letra a.2) and
"722" (transporte de mercancías por carretera / servicios de mudanzas, letra
a.4). A preparer whose actividad qualifies for the especial índice — and
therefore, per the incompatibility chain, is excluded from b.1 and
consequently from b.3 too — silently gets an índice-exceso adjustment the
engine cannot itself rule out (no-silent-under-declaration). Both guards are
non-blocking ADVISORY findings: the índice-exceso chain feeds only the
internal-only ``modulos-rendimiento-neto-actividad`` reference casilla, never
the filed casilla 01, so the gate prompts a review rather than refusing the
draft.

See Also:
    :mod:`~domain.calculations.registry._formula_runtime_m131`
        M131 módulos runtime evaluator whose índice-exceso path this advisory
        guards.
    :func:`~application.modelo._verification_actions.evaluate_verification_predicates`
        Application verification entry point that emits the advisory finding.
    :func:`~application.modelo._verification_actions._evaluate_advisory_predicate_fires`
        Predicate helper exercised directly by the focused firing cases.
    ``src/cadrumo/_data/registry/aeat/modelos/131/revisions/2025/verification_expectations/0002-verification_predicates.toml``
        Registry-authored 2025 advisory predicate declarations under test.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.loader import load_modelo_path
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from .._verification_actions import _evaluate_advisory_predicate_fires, evaluate_verification_predicates

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CASILLA_EPIGRAFE: CasillaId = validated_casilla_id(
    "modulos-epigrafe",
    surface="test_verification_m131_indice_exceso_incompatibility_advisory",
)
_CASILLA_MINORADO: CasillaId = validated_casilla_id(
    "modulos-rendimiento-neto-minorado",
    surface="test_verification_m131_indice_exceso_incompatibility_advisory",
)
_CASILLA_MODULOS: CasillaId = validated_casilla_id(
    "modulos-rendimiento-neto-modulos",
    surface="test_verification_m131_indice_exceso_incompatibility_advisory",
)

_AUTOTAXI_PREDICATE_ID = "modelo-131-2025-modulos-indice-exceso-incompatible-autotaxi"
_MERCANCIAS_PREDICATE_ID = "modelo-131-2025-modulos-indice-exceso-incompatible-mercancias"
_ALL_PREDICATE_IDS = (_AUTOTAXI_PREDICATE_ID, _MERCANCIAS_PREDICATE_ID)

_AUTOTAXI_EXPRESSION = (
    'casilla_equals_implies_diverges(["modulos-epigrafe", "721.2", '
    '"modulos-rendimiento-neto-minorado", "modulos-rendimiento-neto-modulos"])'
)
_MERCANCIAS_EXPRESSION = (
    'casilla_equals_implies_diverges(["modulos-epigrafe", "722", '
    '"modulos-rendimiento-neto-minorado", "modulos-rendimiento-neto-modulos"])'
)
_INDICE_EXCESO_CASES = (
    (_AUTOTAXI_EXPRESSION, "721.2"),
    (_MERCANCIAS_EXPRESSION, "722"),
)


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


@lru_cache
def _m131_2025_revision() -> ModeloRevision:
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "131"))
    return modelo.revisions["2025"]


def _predicate(predicate_id: str) -> VerificationPredicateDefinition:
    revision = _m131_2025_revision()
    return next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)


def test_incompatibility_predicates_ship_on_2025_revision() -> None:
    """Both incompatibility predicates exist, are ADVISORY, and cite the Anexo II grounding."""
    revision = _m131_2025_revision()
    predicates_by_id = {p.predicate_id: p for p in revision.verification_predicates}

    for predicate_id in _ALL_PREDICATE_IDS:
        assert predicate_id in predicates_by_id, predicate_id
        predicate = predicates_by_id[predicate_id]
        assert predicate.finding_kind == "ADVISORY", predicate_id
        assert "orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades" in tuple(
            str(r) for r in predicate.legal_refs
        ), predicate_id


def test_advisory_fires_when_epigrafe_matches_and_indice_exceso_activated() -> None:
    """Índice-exceso adjustment on a tabled especial-índice epígrafe fires the advisory."""
    values: dict[CasillaId, Decimal] = {
        _CASILLA_MINORADO: Decimal("40000.00"),
        _CASILLA_MODULOS: Decimal("40858.12"),
    }

    for expression, epigrafe in _INDICE_EXCESO_CASES:
        text_values: dict[CasillaId, str] = {_CASILLA_EPIGRAFE: epigrafe}
        assert _evaluate_advisory_predicate_fires(expression, values, text_values) is True, epigrafe


def test_advisory_does_not_fire_when_indice_exceso_not_activated() -> None:
    """No divergence (minorado below the cuantía threshold) never fires, even on the flagged epígrafes."""
    values: dict[CasillaId, Decimal] = {
        _CASILLA_MINORADO: Decimal("10000.00"),
        _CASILLA_MODULOS: Decimal("10000.00"),
    }

    for expression, epigrafe in _INDICE_EXCESO_CASES:
        text_values: dict[CasillaId, str] = {_CASILLA_EPIGRAFE: epigrafe}
        assert _evaluate_advisory_predicate_fires(expression, values, text_values) is False, epigrafe


def test_advisory_does_not_fire_for_non_especial_epigrafe() -> None:
    """A tabled epígrafe with no documented índice especial (e.g. cafetería 672.1) never fires."""
    values: dict[CasillaId, Decimal] = {
        _CASILLA_MINORADO: Decimal("40000.00"),
        _CASILLA_MODULOS: Decimal("40858.12"),
    }
    text_values: dict[CasillaId, str] = {_CASILLA_EPIGRAFE: "672.1"}

    for expression, epigrafe in _INDICE_EXCESO_CASES:
        assert _evaluate_advisory_predicate_fires(expression, values, text_values) is False, epigrafe


def test_advisory_does_not_fire_when_epigrafe_absent() -> None:
    """An absent epígrafe text value never fires (no antecedent match)."""
    values: dict[CasillaId, Decimal] = {
        _CASILLA_MINORADO: Decimal("40000.00"),
        _CASILLA_MODULOS: Decimal("40858.12"),
    }

    for expression, epigrafe in _INDICE_EXCESO_CASES:
        assert _evaluate_advisory_predicate_fires(expression, values) is False, epigrafe


def test_autotaxi_and_mercancias_predicates_are_mutually_scoped() -> None:
    """The autotaxi predicate does not fire for the mercancías epígrafe and vice versa."""
    values: dict[CasillaId, Decimal] = {
        _CASILLA_MINORADO: Decimal("40000.00"),
        _CASILLA_MODULOS: Decimal("40858.12"),
    }
    assert _evaluate_advisory_predicate_fires(_AUTOTAXI_EXPRESSION, values, {_CASILLA_EPIGRAFE: "722"}) is False
    assert _evaluate_advisory_predicate_fires(_MERCANCIAS_EXPRESSION, values, {_CASILLA_EPIGRAFE: "721.2"}) is False


def test_emits_single_advisory_warning_finding_when_violated() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_MINORADO: Decimal("40000.00"),
        _CASILLA_MODULOS: Decimal("40858.12"),
    }
    predicate = _predicate(_AUTOTAXI_PREDICATE_ID)

    findings = evaluate_verification_predicates(
        (predicate,),
        values,
        _profile(),
        text_values={_CASILLA_EPIGRAFE: "721.2"},
    )

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades" in findings[0].legal_refs
    assert findings[0].message_locale_key == "application.modelo.findings.registry_advisory_predicate_fired"
    assert dict(findings[0].message_facts) == {"predicate_id": _AUTOTAXI_PREDICATE_ID}
