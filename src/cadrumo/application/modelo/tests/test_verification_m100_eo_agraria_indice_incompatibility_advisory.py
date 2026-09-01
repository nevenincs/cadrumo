"""Modelo 100 2025 EO agraria índices correctores incompatibility advisory tests.

Covers the ``modelo-100-2025-eo-agraria-indice-*`` ADVISORY guards shipped on
the 2025 revision. Orden HAC/1347/2024, Anexo I, instrucción 2.3 fixes two
binding exclusivity rules the índice-cascade formula
(``m100_resolve_eo_agraria_indices_correctores``,
``0293-renta-2025-eo-agraria-rendimiento-base.toml``) applies each declared
índice unconditionally, without cross-checking either rule:

- letra a)/b): "Cuando resulte aplicable el índice corrector de la letra a)
  anterior no podrá aplicarse el contenido en esta letra b)" — medios de
  producción ajenos (casilla 1540) and personal asalariado (casilla 1541)
  are mutually exclusive.
- letra h): "A las actividades forestales únicamente le será aplicable el
  índice señalado en la letra h) anterior" — forestal (casilla 1547)
  excludes every other letra (a to g) for that activity.

A preparer declaring incompatible índices silently compounds a correction
the Anexo I only permits once (no-silent-under-declaration). Both guards are
non-blocking ADVISORY findings: a preparer may hold several unrelated
actividades within the same casilla set, so the gate prompts a review
rather than refusing the draft.

See Also:
    :func:`~domain.calculations.registry.formula_runtime_m100.evaluate_m100_resolve_eo_agraria_indices_correctores`
        Registry runtime evaluator whose índice cascade this advisory guards.
    :func:`~application.modelo._verification_actions.evaluate_verification_predicates`
        Application verification entry point that emits the advisory findings.
    :mod:`~application.modelo._verification_predicates`
        Implements the ``at_most_one_positive`` predicate form used by these
        incompatibility guards.
    ``src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/verification_expectations/0002-verification_predicates.toml``
        Registry-authored 2025 EO agraria incompatibility predicate declarations
        under test.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.loader import load_modelo_path
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos.verification_report import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from ..verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CASILLA_1540_MEDIOS_AJENOS: CasillaId = validated_casilla_id(
    "1540",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)
_CASILLA_1541_PERSONAL_ASALARIADO: CasillaId = validated_casilla_id(
    "1541",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)
_CASILLA_1542_TIERRAS_ARRENDADAS: CasillaId = validated_casilla_id(
    "1542",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)
_CASILLA_1544_ECOLOGICA: CasillaId = validated_casilla_id(
    "1544",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)
_CASILLA_1545_REGADIO_ELECTRICO: CasillaId = validated_casilla_id(
    "1545",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)
_CASILLA_1546_PEQUENA_EMPRESA: CasillaId = validated_casilla_id(
    "1546",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)
_CASILLA_1547_FORESTAL: CasillaId = validated_casilla_id(
    "1547",
    surface="test_verification_m100_eo_agraria_indice_incompatibility_advisory",
)

_AB_PREDICATE_ID = "modelo-100-2025-eo-agraria-indice-medios-ajenos-personal-asalariado-incompatibles"

# The forestal-exclusion predicate ids, one per excluded letra a-g pair
# (letra d / casilla 1543 is text-typed and cannot be expressed with the
# numeric at_most_one_positive operator — see the registry TOML comment).
_FORESTAL_PREDICATE_IDS = (
    "modelo-100-2025-eo-agraria-indice-forestal-excluye-medios-ajenos",
    "modelo-100-2025-eo-agraria-indice-forestal-excluye-personal-asalariado",
    "modelo-100-2025-eo-agraria-indice-forestal-excluye-tierras-arrendadas",
    "modelo-100-2025-eo-agraria-indice-forestal-excluye-agricultura-ecologica",
    "modelo-100-2025-eo-agraria-indice-forestal-excluye-regadio-electrico",
    "modelo-100-2025-eo-agraria-indice-forestal-excluye-pequena-empresa",
)

_ALL_PREDICATE_IDS = (_AB_PREDICATE_ID, *_FORESTAL_PREDICATE_IDS)
_AB_SINGLE_LETRA_CASES: tuple[tuple[str, dict[CasillaId, Decimal]], ...] = (
    (
        "a-only",
        {_CASILLA_1540_MEDIOS_AJENOS: Decimal("0.75"), _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0")},
    ),
    (
        "b-only",
        {_CASILLA_1540_MEDIOS_AJENOS: Decimal("0"), _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0.90")},
    ),
    (
        "neither-declared-zero",
        {_CASILLA_1540_MEDIOS_AJENOS: Decimal("0"), _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0")},
    ),
    ("neither-declared-absent", {}),
)
_FORESTAL_OTHER_LETRA_CASILLAS = (
    _CASILLA_1540_MEDIOS_AJENOS,
    _CASILLA_1541_PERSONAL_ASALARIADO,
    _CASILLA_1542_TIERRAS_ARRENDADAS,
    _CASILLA_1544_ECOLOGICA,
    _CASILLA_1545_REGADIO_ELECTRICO,
    _CASILLA_1546_PEQUENA_EMPRESA,
)


@cache
def _m100_2025_revision() -> ModeloRevision:
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "100"))
    return modelo.revisions["2025"]


@cache
def _predicate(predicate_id: str) -> VerificationPredicateDefinition:
    revision = _m100_2025_revision()
    return next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)


def _forestal_predicate_for(other_letra_casilla: CasillaId) -> VerificationPredicateDefinition:
    predicate_id = next(pid for pid in _FORESTAL_PREDICATE_IDS if other_letra_casilla in _predicate(pid).expression)
    return _predicate(predicate_id)


def test_incompatibility_predicates_ship_on_2025_revision() -> None:
    """Every declared incompatibility predicate exists, is ADVISORY, and cites the Anexo I instrucción."""
    revision = _m100_2025_revision()
    predicates_by_id = {p.predicate_id: p for p in revision.verification_predicates}

    for predicate_id in _ALL_PREDICATE_IDS:
        assert predicate_id in predicates_by_id, predicate_id
        predicate = predicates_by_id[predicate_id]
        assert predicate.finding_kind == "ADVISORY", predicate_id
        assert "orden-hac-1347-2024:anexo-i-instruccion-2-3" in tuple(str(r) for r in predicate.legal_refs), (
            predicate_id
        )


def test_medios_ajenos_personal_asalariado_both_positive_fires_advisory() -> None:
    """Letra a) and letra b) are mutually exclusive: declaring both fires a non-blocking advisory."""
    predicate = _predicate(_AB_PREDICATE_ID)
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_1540_MEDIOS_AJENOS: Decimal("0.75"),
        _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0.90"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "orden-hac-1347-2024:anexo-i-instruccion-2-3" in findings[0].legal_refs
    assert findings[0].message_locale_key == "application.modelo.findings.registry_advisory_predicate_fired"
    assert dict(findings[0].message_facts) == {"predicate_id": _AB_PREDICATE_ID}


def test_medios_ajenos_personal_asalariado_single_letra_holds() -> None:
    """Declaring only letra a), only letra b), or neither, never fires the advisory."""
    predicate = _predicate(_AB_PREDICATE_ID)
    for case_label, casilla_values in _AB_SINGLE_LETRA_CASES:
        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], case_label


def test_forestal_and_any_other_letra_both_positive_fires_advisory() -> None:
    """Letra h) (forestal) excludes every other declared letra (a-c, e-g): both positive fires an advisory."""
    for other_letra_casilla in _FORESTAL_OTHER_LETRA_CASILLAS:
        predicate = _forestal_predicate_for(other_letra_casilla)
        casilla_values: dict[CasillaId, Decimal] = {
            _CASILLA_1547_FORESTAL: Decimal("0.80"),
            other_letra_casilla: Decimal("0.75"),
        }

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

        assert len(findings) == 1, other_letra_casilla
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, other_letra_casilla
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, other_letra_casilla
        assert "orden-hac-1347-2024:anexo-i-instruccion-2-3" in findings[0].legal_refs, other_letra_casilla


def test_forestal_alone_holds_for_every_pairing() -> None:
    """A forestal-only declaration (no other letra) never fires any forestal-exclusion advisory."""
    casilla_values: dict[CasillaId, Decimal] = {_CASILLA_1547_FORESTAL: Decimal("0.80")}
    for predicate_id in _FORESTAL_PREDICATE_IDS:
        predicate = _predicate(predicate_id)
        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], predicate_id


def test_other_letra_alone_holds_for_every_pairing() -> None:
    """A non-forestal letra declared alone (forestal absent) never fires the forestal-exclusion advisory."""
    for predicate_id in _FORESTAL_PREDICATE_IDS:
        predicate = _predicate(predicate_id)
        # Recover the "other" casilla id from the predicate expression to build a
        # single-casilla-positive case for exactly that pairing.
        other_id = next(cid for cid in _FORESTAL_OTHER_LETRA_CASILLAS if cid in predicate.expression)
        casilla_values: dict[CasillaId, Decimal] = {other_id: Decimal("0.75")}
        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], predicate_id
