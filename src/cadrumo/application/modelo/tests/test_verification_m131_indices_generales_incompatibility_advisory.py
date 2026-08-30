"""Modelo 131 2025 índices correctores generales (b.1, b.2, b.4) incompatibility advisory tests.

Covers the ``modelo-131-2025-modulos-pequena-dimension-ignorado-especial`` and
``modelo-131-2025-modulos-temporada-inicio-actividad-incompatibles`` ADVISORY
guards shipped on the 2025 revision. Orden HAC/1347/2024, Anexo II,
instrucción 2.3 fixes two exclusivity rules the Fase 3ª índices correctores
generales cascade (``m131_resolve_modulos_indices_generales``,
``cmodulos-epigrafe__cmodulos-rendimiento-neto-actividad.toml``) enforces STRUCTURALLY (never applies both
sides of an incompatible pair):

- "En ningún caso será aplicable el índice corrector para empresas de
  pequeña dimensión (b.1) a las actividades para las que están previstos
  los índices correctores especiales enumerados en las letras a.2), a.3),
  a.4) y a.5)."
- "Cuando resulte aplicable el índice corrector de temporada (b.2) no se
  aplicará el índice corrector por inicio de nuevas actividades (b.4)."

Because the engine already resolves the correct (non-ignored) figure, these
two ADVISORY findings are not "the engine might be wrong" prompts — they are
non-blocking confirmations that the operator's own declaration was not
silently dropped, per no-silent-under-declaration. Two internal advisory-
support flag casillas (``modulos-pequena-dimension-ignorado-flag``,
``modulos-temporada-inicio-actividad-conflicto-flag``) carry the 1/0 signal
the ``advisory_when_positive`` operator reads.

See Also:
    :func:`~domain.calculations.registry._formula_runtime_m131.evaluate_m131_resolve_modulos_indices_generales`
        Formula op whose structural incompatibility handling feeds these flags.
    :data:`~domain.calculations.registry._formula_runtime_m131._M131_EPIGRAFES_INDICE_ESPECIAL`
        Epígrafe set that makes the b.1 pequeña-dimensión índice ignored.
    :func:`~application.modelo._verification_actions._evaluate_advisory_predicate_fires`
        Verification DSL evaluator for the ``advisory_when_positive`` checks.
    :func:`~application.modelo._verification_actions.evaluate_verification_predicates`
        Converts fired advisory predicates into warning findings.
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
        Registry predicate model loaded from the bundled M131 revision.
    :mod:`~domain.calculations.registry.tests._modelo_131_modulos_engine_support`
        Independent expected-value support for the same índices-correctores cascade.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.resources import bundled_path
from ....domain.calculations.registry.loader import load_modelo_path
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from .._verification_actions import _evaluate_advisory_predicate_fires, evaluate_verification_predicates

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CASILLA_PEQUENA_DIMENSION_FLAG: CasillaId = validated_casilla_id(
    "modulos-pequena-dimension-ignorado-flag",
    surface="test_verification_m131_indices_generales_incompatibility_advisory",
)
_CASILLA_TEMPORADA_INICIO_FLAG: CasillaId = validated_casilla_id(
    "modulos-temporada-inicio-actividad-conflicto-flag",
    surface="test_verification_m131_indices_generales_incompatibility_advisory",
)

_PEQUENA_DIMENSION_PREDICATE_ID = "modelo-131-2025-modulos-pequena-dimension-ignorado-especial"
_TEMPORADA_INICIO_PREDICATE_ID = "modelo-131-2025-modulos-temporada-inicio-actividad-incompatibles"
_ALL_PREDICATE_IDS = (_PEQUENA_DIMENSION_PREDICATE_ID, _TEMPORADA_INICIO_PREDICATE_ID)

_PEQUENA_DIMENSION_EXPRESSION = 'advisory_when_positive(["modulos-pequena-dimension-ignorado-flag"])'
_TEMPORADA_INICIO_EXPRESSION = 'advisory_when_positive(["modulos-temporada-inicio-actividad-conflicto-flag"])'


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


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


def test_pequena_dimension_advisory_fires_when_flag_positive() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_PEQUENA_DIMENSION_FLAG: Decimal("1")}
    assert _evaluate_advisory_predicate_fires(_PEQUENA_DIMENSION_EXPRESSION, values) is True


def test_pequena_dimension_advisory_does_not_fire_when_flag_zero() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_PEQUENA_DIMENSION_FLAG: Decimal("0")}
    assert _evaluate_advisory_predicate_fires(_PEQUENA_DIMENSION_EXPRESSION, values) is False


def test_pequena_dimension_advisory_does_not_fire_when_flag_absent() -> None:
    assert _evaluate_advisory_predicate_fires(_PEQUENA_DIMENSION_EXPRESSION, {}) is False


def test_temporada_inicio_advisory_fires_when_flag_positive() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_TEMPORADA_INICIO_FLAG: Decimal("1")}
    assert _evaluate_advisory_predicate_fires(_TEMPORADA_INICIO_EXPRESSION, values) is True


def test_temporada_inicio_advisory_does_not_fire_when_flag_zero() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_TEMPORADA_INICIO_FLAG: Decimal("0")}
    assert _evaluate_advisory_predicate_fires(_TEMPORADA_INICIO_EXPRESSION, values) is False


def test_emits_single_advisory_warning_finding_when_pequena_dimension_ignored() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_PEQUENA_DIMENSION_FLAG: Decimal("1")}
    predicate = _predicate(_PEQUENA_DIMENSION_PREDICATE_ID)

    findings = evaluate_verification_predicates((predicate,), values, _profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert findings[0].casilla_id == _CASILLA_PEQUENA_DIMENSION_FLAG
    assert "orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades" in findings[0].legal_refs
    assert findings[0].message_locale_key == "application.modelo.findings.registry_advisory_predicate_fired"
    assert dict(findings[0].message_facts) == {"predicate_id": _PEQUENA_DIMENSION_PREDICATE_ID}


def test_emits_single_advisory_warning_finding_when_temporada_inicio_conflict() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_TEMPORADA_INICIO_FLAG: Decimal("1")}
    predicate = _predicate(_TEMPORADA_INICIO_PREDICATE_ID)

    findings = evaluate_verification_predicates((predicate,), values, _profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert findings[0].casilla_id == _CASILLA_TEMPORADA_INICIO_FLAG
    assert "orden-hac-1347-2024:anexo-ii-instruccion-2-3-incompatibilidades" in findings[0].legal_refs
    assert findings[0].message_locale_key == "application.modelo.findings.registry_advisory_predicate_fired"
    assert dict(findings[0].message_facts) == {"predicate_id": _TEMPORADA_INICIO_PREDICATE_ID}


def test_no_findings_when_neither_flag_fires() -> None:
    revision = _m131_2025_revision()
    predicates = tuple(p for p in revision.verification_predicates if p.predicate_id in _ALL_PREDICATE_IDS)
    values: dict[CasillaId, Decimal] = {
        _CASILLA_PEQUENA_DIMENSION_FLAG: Decimal("0"),
        _CASILLA_TEMPORADA_INICIO_FLAG: Decimal("0"),
    }

    findings = evaluate_verification_predicates(predicates, values, _profile())

    assert findings == []
