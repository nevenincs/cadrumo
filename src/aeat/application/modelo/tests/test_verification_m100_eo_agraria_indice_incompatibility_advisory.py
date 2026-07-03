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
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    CasillaId,
    VerificationPredicateDefinition,
    load_modelo_path,
    validated_casilla_id,
)
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
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


def _m100_2025_revision():
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "100"))
    return modelo.revisions["2025"]


def _predicate(predicate_id: str) -> VerificationPredicateDefinition:
    revision = _m100_2025_revision()
    return next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)


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
    assert findings[0].message  # a non-empty operator-facing message is rendered


@pytest.mark.parametrize(
    "casilla_values",
    (
        {_CASILLA_1540_MEDIOS_AJENOS: Decimal("0.75"), _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0")},
        {_CASILLA_1540_MEDIOS_AJENOS: Decimal("0"), _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0.90")},
        {_CASILLA_1540_MEDIOS_AJENOS: Decimal("0"), _CASILLA_1541_PERSONAL_ASALARIADO: Decimal("0")},
        {},
    ),
    ids=("a-only", "b-only", "neither-declared-zero", "neither-declared-absent"),
)
def test_medios_ajenos_personal_asalariado_single_letra_holds(casilla_values: dict[CasillaId, Decimal]) -> None:
    """Declaring only letra a), only letra b), or neither, never fires the advisory."""
    predicate = _predicate(_AB_PREDICATE_ID)
    assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == []


@pytest.mark.parametrize(
    "other_letra_casilla",
    (
        _CASILLA_1540_MEDIOS_AJENOS,
        _CASILLA_1541_PERSONAL_ASALARIADO,
        _CASILLA_1542_TIERRAS_ARRENDADAS,
        _CASILLA_1544_ECOLOGICA,
        _CASILLA_1545_REGADIO_ELECTRICO,
        _CASILLA_1546_PEQUENA_EMPRESA,
    ),
)
def test_forestal_and_any_other_letra_both_positive_fires_advisory(other_letra_casilla: CasillaId) -> None:
    """Letra h) (forestal) excludes every other declared letra (a-c, e-g): both positive fires an advisory."""
    predicate_id = next(pid for pid in _FORESTAL_PREDICATE_IDS if other_letra_casilla in _predicate(pid).expression)
    predicate = _predicate(predicate_id)
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_1547_FORESTAL: Decimal("0.80"),
        other_letra_casilla: Decimal("0.75"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "orden-hac-1347-2024:anexo-i-instruccion-2-3" in findings[0].legal_refs


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
        other_id = next(
            cid
            for cid in (
                _CASILLA_1540_MEDIOS_AJENOS,
                _CASILLA_1541_PERSONAL_ASALARIADO,
                _CASILLA_1542_TIERRAS_ARRENDADAS,
                _CASILLA_1544_ECOLOGICA,
                _CASILLA_1545_REGADIO_ELECTRICO,
                _CASILLA_1546_PEQUENA_EMPRESA,
            )
            if cid in predicate.expression
        )
        casilla_values: dict[CasillaId, Decimal] = {other_id: Decimal("0.75")}
        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], predicate_id
