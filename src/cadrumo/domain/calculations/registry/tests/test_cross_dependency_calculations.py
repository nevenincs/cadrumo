"""Cross-modelo relation and binding wiring tests.

WHAT THESE TESTS VERIFY: that the cross-modelo value channels are wired and
arithmetically closed — relation-source requirements resolve to observations,
observations fold into relation values, relation values reach the declared
target casilla, and previous-filing bindings sum the selector's casillas.

WHAT THEY DO NOT VERIFY: that any amount is the figure AEAT would print. The
monetary values these tests compare against come from the justificante PDF
fixtures, and those amounts are NOT an AEAT oracle:

* The M111/M190 fixtures are ``role = "parser_anchor"`` real-corpus specimens.
  Their amounts were replaced by the redaction pipeline with the uniform
  placeholder ``1000.00``; only their layout and labels survive sanitisation.
* The M180 fixture is ``role = "formula_verification"``,
  ``provenance = "synthetic_generated"`` — its amounts are hand-authored
  literals in ``tests/fixtures/justificantes/_generate_misc_a.py``, chosen to
  be internally consistent, not sourced from AEAT.

Both sides of every monetary assertion below are therefore derived from the
same fixture value, so the assertions are closure checks: replacing every
fixture amount with an arbitrary number leaves all of them passing. That is
the honest description of this module's power, and the coverage is still
worth having — it is what catches a broken fold, a dropped relation, a
mis-declared binding selector, or a resolution that silently returns zero.

WHERE A REAL ORACLE PLUGS IN: an AEAT-authoritative figure for these modelos
belongs in the bundled oracle corpora (``corpus/manual_oracles/`` or
``corpus/parity_replays/renta_web_open/``) keyed by
``expected_by_casilla_id``, with the casilla declared in the revision's
``externally_grounded_casilla_ids``. That route is cross-checked in both
directions by ``test_external_oracle_grounding_enrolled.py``. No modelo
exercised here (111, 180, 190) has such an oracle today.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pdfplumber
import pytest

from cadrumo.domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from cadrumo.domain.calculations.registry.bindings_previous_filing import resolve_previous_filing_binding_values
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from cadrumo.domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_values,
)

from .....core import CasillaId, Period, validated_casilla_id, validated_casilla_id_map
from .....core.aggregation import RetencionClave
from .....tests import FIXTURES_DIR
from ....period import calculation_filing_date
from ..authority import ValidatedRegistryAuthority
from ..binding_selector_utils import selector_as_dict
from ..relations import (
    RegistryFoldRequirement,
    materialize_relation_binding_values,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ..schema import ModeloRevision, RegistrySnapshot
from ._cross_dependency_calculation_support import (
    _casilla_inputs,
    _grounded_observations,
    _observations_from_requirements,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_BASE_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id(
    "06",
    surface="_M130_BASE_PAGO_FRACCIONADO_CASILLA",
)
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_RETENCIONES_CASILLA")
_M130_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_PAGOS_FRACCIONADOS_CASILLA")
_M130_A_DEDUCIR_CASILLA: CasillaId = validated_casilla_id("15", surface="_M130_A_DEDUCIR_CASILLA")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_RESULTADO_PREVIO_CASILLA")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_RESULTADO_CASILLA")
_M130_A_INGRESAR_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_A_INGRESAR_CASILLA")
_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA: CasillaId = validated_casilla_id(
    "0604",
    surface="_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA",
)
_M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING = "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count"
_M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING = "renta-2025-profile-unidad-familiar-otros-miembros-base"
_M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING = "renta-2025-profile-minimo-descendientes-estatal"
_M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING = "renta-2025-profile-minimo-descendientes-autonomico"
_M131_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id(
    "15",
    surface="_M131_PAGOS_FRACCIONADOS_CASILLA",
)
_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-perceptores",
    surface="_DECL_TOTAL_PERCEPTORES_CASILLA",
)
_DECL_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.base-total",
    surface="_DECL_BASE_TOTAL_CASILLA",
)
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_DECL_RETENCIONES_TOTAL_CASILLA",
)
_M190_TOTAL_PERCEPCIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_M190_TOTAL_PERCEPCIONES_CASILLA",
)
_M190_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_M190_PERCEPCIONES_TOTAL_CASILLA",
)
_M190_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_M190_RETENCIONES_TOTAL_CASILLA",
)
_M190_PERCEPCIONES_BINDING = "modelo-190-percepciones-anual"
_RETIRED_M190_M111_PERCEPCIONES_SOURCE_CASILLAS: frozenset[CasillaId] = frozenset(
    validated_casilla_id(value, surface="_RETIRED_M190_M111_PERCEPCIONES_SOURCE_CASILLAS")
    for value in ("01", "04", "07", "10", "13", "16", "19", "22", "25")
)
_SPANISH_AMOUNT_PATTERN = r"-?\d{1,3}(?:\.\d{3})*(?:,\d{2})?|-?\d+(?:,\d{2})?"
_ANNUAL_SUMMARY_FIXTURE_PATTERNS: dict[str, dict[CasillaId, str]] = {
    "180": {
        _DECL_TOTAL_PERCEPTORES_CASILLA: rf"N[uú]mero total de perceptores\s+(?P<amount>{_SPANISH_AMOUNT_PATTERN})",
        _DECL_BASE_TOTAL_CASILLA: (
            rf"Base (?:de )?retenciones e ingresos a cuenta total\s+(?P<amount>{_SPANISH_AMOUNT_PATTERN})"
        ),
        _DECL_RETENCIONES_TOTAL_CASILLA: (
            rf"Retenciones e ingresos a cuenta total\s+(?P<amount>{_SPANISH_AMOUNT_PATTERN})"
        ),
    },
    "190": {
        _M190_TOTAL_PERCEPCIONES_CASILLA: (
            rf"N[uú]mero total de percepciones relacionadas en la declaraci[oó]n.*?\b01\s+"
            rf"(?P<amount>{_SPANISH_AMOUNT_PATTERN})"
        ),
        _M190_PERCEPCIONES_TOTAL_CASILLA: (
            rf"Importe total de las percepciones relacionadas.*?\b02\s+(?P<amount>{_SPANISH_AMOUNT_PATTERN})"
        ),
        _M190_RETENCIONES_TOTAL_CASILLA: (
            rf"Importe total de las retenciones e ingresos a cuenta relacionados.*?\b03\s+"
            rf"(?P<amount>{_SPANISH_AMOUNT_PATTERN})"
        ),
    },
}
#: Quarterly probe amounts for the M111 -> M190 fold.
#:
#: PROBES, NOT AN ORACLE. These are chosen by this test and assert no tax fact.
#: They are DISTINCT and non-round on purpose: a fold tested with four equal
#: amounts cannot be told apart from a max, a first-element pick, or a
#: hardcoded constant, which is why the previous fixture-placeholder version of
#: this test survived having every amount replaced by an arbitrary number.
#: Their sums (12345.60 and 1740.73) are the expected annual totals, and no
#: individual probe equals a sum, so a partial fold is visible too.
_M190_PERCEPCIONES_PROBE_QUARTERS: tuple[Decimal, Decimal, Decimal, Decimal] = (
    Decimal("1234.56"),
    Decimal("2345.67"),
    Decimal("3456.78"),
    Decimal("5308.59"),
)
_M190_RETENCIONES_PROBE_QUARTERS: tuple[Decimal, Decimal, Decimal, Decimal] = (
    Decimal("185.18"),
    Decimal("351.85"),
    Decimal("518.52"),
    Decimal("685.18"),
)
#: A second clave for the same perceptor, so the count_distinct aggregation is
#: exercised against more than one (perceptor, clave) pair. "A" is trabajo
#: (empleados) against the fixture perceptor's "G" actividades profesionales.
_M190_SECOND_CLAVE = "A"
_M190_REL_111_ACTIVIDADES_DINERARIO = "modelo-190-rel-111-actividades-dinerario-importe-anual"
_M190_REL_111_RETENCIONES = "modelo-190-rel-111-retenciones-anual"
_M190_EXPECTED_RELATION_IDS = frozenset(
    {
        "modelo-190-rel-111-trabajo-dinerario-importe-anual",
        "modelo-190-rel-111-trabajo-especie-importe-anual",
        _M190_REL_111_ACTIVIDADES_DINERARIO,
        "modelo-190-rel-111-actividades-especie-importe-anual",
        "modelo-190-rel-111-premios-dinerario-importe-anual",
        "modelo-190-rel-111-premios-especie-importe-anual",
        "modelo-190-rel-111-ganancias-dinerario-importe-anual",
        "modelo-190-rel-111-ganancias-especie-importe-anual",
        "modelo-190-rel-111-derechos-imagen-importe-anual",
        _M190_REL_111_RETENCIONES,
    }
)


def _casilla_decimal_sequences(values: Mapping[object, tuple[Decimal, ...]]) -> dict[CasillaId, tuple[Decimal, ...]]:
    return validated_casilla_id_map(values, surface="cross-dependency relation source casillas")


#: The role each fixture this module reads is REQUIRED to declare.
#:
#: The two roles are not interchangeable. A ``parser_anchor`` is a real AEAT
#: render kept for parse fidelity, and the redaction pipeline replaced its
#: amounts with a uniform placeholder; a ``formula_verification`` specimen is
#: synthetic and its amounts are at least internally consistent. Asserting the
#: exact expected role per fixture -- rather than accepting either -- is what
#: keeps a placeholder-bearing render from being read as a calculation
#: expectation. The single-expected-role shape mirrors the manual-annex
#: provenance gate and the bilingual presentador parser test.
_EXPECTED_FIXTURE_ROLE: dict[str, str] = {
    "180": "formula_verification",
    "190": "parser_anchor",
}


@cache
def _fixture_pdf_text(modelo: str, fixture_stem: str = "2024-0A") -> str:
    pdf_path = FIXTURES_DIR / "justificantes" / modelo / f"{fixture_stem}.pdf"
    sidecar = json.loads(pdf_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar.get("provenance") in {"real_corpus", "synthetic_generated"}, (
        f"{pdf_path} fixture sidecar must declare real or synthetic provenance"
    )
    expected_role = _EXPECTED_FIXTURE_ROLE[modelo]
    assert sidecar.get("role") == expected_role, (
        f"{pdf_path} fixture sidecar declares role {sidecar.get('role')!r}, but this module "
        f"reads M{modelo} as {expected_role!r}. The two roles are not interchangeable: a "
        f"parser_anchor carries redaction placeholders where a formula_verification specimen "
        f"carries internally-consistent amounts, so swapping one for the other silently "
        f"changes what every assertion downstream is worth."
    )
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


@cache
def _annual_summary_fixture_values(modelo: str, fixture_stem: str = "2024-0A") -> dict[CasillaId, Decimal]:
    """Read the resumen-anual amounts a justificante fixture PRINTS.

    These are printed values, not AEAT-authoritative figures: the M190 fixture
    is a redacted ``parser_anchor`` whose amounts are the placeholder
    ``1000.00``, and the M180 fixture's amounts are generator literals. Tests
    use them as a self-consistent reference to close the fold arithmetic
    against — see the module docstring for what that does and does not prove.
    """
    text = _fixture_pdf_text(modelo, fixture_stem)
    values: dict[CasillaId, Decimal] = {}
    for casilla_id, pattern in _ANNUAL_SUMMARY_FIXTURE_PATTERNS[modelo].items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        assert match is not None, f"M{modelo}/{fixture_stem} fixture did not expose {casilla_id!r}"
        values[casilla_id] = _spanish_decimal(match.group("amount"))
    return values


def _spanish_decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(".", "").replace(",", "."))


def _split_total_across_quarters(total: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Split a fixture annual total into four non-uniform quarterly parts.

    The split is deliberately uneven (1/10, 2/10, 3/10, remainder) so a fold
    that copies one quarter, or sums only some periods, cannot accidentally
    reproduce the annual total.

    The total being split is a fixture-printed amount, NOT an AEAT figure (see
    the module docstring). Reassembling it therefore proves the fold arithmetic
    closes over the four periods; it proves nothing about the amount's
    correctness against AEAT.
    """
    if total == Decimal("0"):
        return (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
    unit = total / Decimal("10")
    return (unit, unit * Decimal("2"), unit * Decimal("3"), total - (unit * Decimal("6")))


def _m180_fixture_relation_source_values() -> dict[CasillaId, tuple[Decimal, ...]]:
    fixture_values = _annual_summary_fixture_values("180")
    return _casilla_decimal_sequences(
        {
            "02": _split_total_across_quarters(fixture_values[_DECL_BASE_TOTAL_CASILLA]),
            "03": _split_total_across_quarters(fixture_values[_DECL_RETENCIONES_TOTAL_CASILLA]),
        }
    )


@cache
def _m190_fixture_detail_observation() -> tuple[str, str, Decimal, Decimal]:
    text = _fixture_pdf_text("190")
    identity_match = re.search(
        r"\n(?P<nif>[A-Z0-9]{9})\s+[^\n]+\nDatos de la percepci[oó]n",
        text,
        flags=re.IGNORECASE,
    )
    clave_match = re.search(r"Clave:\s+(?P<clave>[A-Z])\s+Subclave:\s+01", text)
    amount_match = re.search(
        rf"incapacidad laboral:\s+(?P<percepcion>{_SPANISH_AMOUNT_PATTERN})\s+"
        rf"(?P<retencion>{_SPANISH_AMOUNT_PATTERN})",
        text,
        flags=re.IGNORECASE,
    )
    assert identity_match is not None, "M190 fixture detail page did not expose a perceptor identity row"
    assert clave_match is not None, "M190 fixture detail page did not expose clave G/01 grounding"
    assert amount_match is not None, "M190 fixture detail page did not expose the perception/retention amount row"
    return (
        str(identity_match.group("nif")),
        str(clave_match.group("clave")),
        _spanish_decimal(amount_match.group("percepcion")),
        _spanish_decimal(amount_match.group("retencion")),
    )


def _m190_fixture_relation_source_value(
    requirement: RegistryFoldRequirement,
    period_index: int,
    *,
    percepciones_quarterly: tuple[Decimal, Decimal, Decimal, Decimal],
    retenciones_quarterly: tuple[Decimal, Decimal, Decimal, Decimal],
) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == _M190_REL_111_ACTIVIDADES_DINERARIO:
        return percepciones_quarterly[period_index]
    if relation_id == _M190_REL_111_RETENCIONES:
        return retenciones_quarterly[period_index]
    return Decimal("0")


def _withholding_observation(
    source_id: str,
    nif: str,
    clave: str,
    *,
    percibido_dinerario: Decimal,
    retencion_practicada: Decimal,
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(2024, 6, 1),
        clave=RetencionClave(clave),
        percibido_dinerario=percibido_dinerario,
        retencion_practicada=retencion_practicada,
    )


def test_cross_model_relations_resolve_from_observations_for_revision_edge_years(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            if not revision.relations:
                continue
            relation_ids = {relation.id for relation in revision.relations}
            for filing_year, period in _full_relation_filing_year_periods(revision=revision, relation_ids=relation_ids):
                _assert_relations_resolve_from_observations(
                    target_modelo=modelo.id,
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                    relation_ids=relation_ids,
                    scope=f"{modelo.id}/{revision.id}/{filing_year}/{period}",
                )


def _full_relation_filing_year_periods(
    *,
    revision: ModeloRevision,
    relation_ids: set[str],
) -> Iterator[tuple[int, str]]:
    """Yield ``(filing_year, period)`` pairs where every relation is active.

    A relation is "active" for a period when it either has no
    target_periods declared (matches every period) or lists the
    period explicitly. The gate only exercises tuples where the
    active set equals the full relation set so partial-coverage
    periods do not pollute the resolution check.
    """
    for filing_year in _revision_edge_years(revision):
        for period in revision.period_selector.periods:
            active_relation_ids = {
                relation.id
                for relation in revision.relations
                if not relation.target_periods or period in relation.target_periods
            }
            if active_relation_ids == relation_ids:
                yield filing_year, period


def _assert_relations_resolve_from_observations(
    *,
    target_modelo: str,
    revision: ModeloRevision,
    filing_year: int,
    period: str,
    relation_ids: set[str],
    scope: str,
) -> None:
    """Drive the relation-source -> observation -> resolution roundtrip and assert closure."""
    requirements = relation_source_requirements(revision, filing_year=filing_year, period=period)
    observations = _observations_from_requirements(
        requirements,
        lambda _requirement, period_index: Decimal(period_index + 1),
        target_modelo=target_modelo,
        fallback_revision=revision,
    )
    resolved = resolve_relation_values_from_observations(revision, observations, filing_year=filing_year, period=period)
    assert set(resolved) == relation_ids, scope


_M193_RELATION_SOURCE_VALUES = _casilla_decimal_sequences(
    {
        "03": (Decimal("5"), Decimal("4"), Decimal("7"), Decimal("6")),
        "06": (Decimal("1201.00"), Decimal("800.25"), Decimal("999.75"), Decimal("500.00")),
        "09": (Decimal("228.19"), Decimal("152.05"), Decimal("189.95"), Decimal("95.00")),
    }
)


def _m193_relation_source_values() -> dict[CasillaId, tuple[Decimal, ...]]:
    return _M193_RELATION_SOURCE_VALUES


_ANNUAL_SUMMARY_RELATION_CASES = (
    pytest.param(
        "180",
        2022,
        "2019-2022",
        _m180_fixture_relation_source_values,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-rel-115-base-anual", "modelo-180-rel-115-retenciones-anual"}),
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
        id="modelo-180-historical",
    ),
    pytest.param(
        "180",
        2026,
        "2023-y-siguientes",
        _m180_fixture_relation_source_values,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-rel-115-base-anual", "modelo-180-rel-115-retenciones-anual"}),
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
        id="modelo-180-current",
    ),
    pytest.param(
        "180",
        2027,
        "2023-y-siguientes",
        _m180_fixture_relation_source_values,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-rel-115-base-anual", "modelo-180-rel-115-retenciones-anual"}),
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
        id="modelo-180-future",
    ),
    pytest.param(
        "193",
        2026,
        # Modelo 193's open-ended revision is `2025-y-siguientes`; the former
        # `2024-y-siguientes` was split into a closed `2024` plus this one, so
        # filing year 2026 resolves here. This value is ASSERTED against the
        # law-determined pick, never injected into resolution.
        "2025-y-siguientes",
        _m193_relation_source_values,
        "modelo-193-123-perceptores-anual",
        frozenset({"modelo-193-rel-123-base-anual", "modelo-193-rel-123-retenciones-anual"}),
        "modelo-193-rel-123-base-anual",
        "modelo-193-rel-123-retenciones-anual",
        id="modelo-193-current",
    ),
)


@pytest.mark.parametrize(
    (
        "modelo",
        "filing_year",
        "expected_revision",
        "source_values_factory",
        "perceptores_binding_id",
        "expected_relation_ids",
        "base_relation_id",
        "retenciones_relation_id",
    ),
    _ANNUAL_SUMMARY_RELATION_CASES,
)
def test_annual_summary_cross_dependency_calculation_resolves_quarterly_filings(
    modelo: str,
    filing_year: int,
    expected_revision: str,
    source_values_factory: Callable[[], dict[CasillaId, tuple[Decimal, ...]]],
    perceptores_binding_id: str,
    expected_relation_ids: frozenset[str],
    base_relation_id: str,
    retenciones_relation_id: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Quarterly source observations fold into the annual summary casillas.

    Closure check, not a grounding check: the quarterly parts are derived by
    splitting the fixture's own printed annual total, so reassembling that
    total proves the fold sums all four periods and routes through the declared
    relation. The total itself is a fixture amount, not an AEAT figure (module
    docstring).
    """
    snapshot = registry_snapshot(modelo, filing_year, "0A")
    source_values = source_values_factory()
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: source_values[requirement.source_casilla_ids[0]][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    fixture_values = _annual_summary_fixture_values("180") if modelo == "180" else {}
    perceptores_binding_value = fixture_values.get(_DECL_TOTAL_PERCEPTORES_CASILLA, Decimal("2"))
    binding_values = {perceptores_binding_id: perceptores_binding_value}
    if modelo == "180":
        assert relation_values[base_relation_id] == fixture_values[_DECL_BASE_TOTAL_CASILLA]
        assert relation_values[retenciones_relation_id] == fixture_values[_DECL_RETENCIONES_TOTAL_CASILLA]
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": _registry_filing_date(filing_year, "0A")},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    assert snapshot.revision.id == expected_revision
    assert set(relation_values) == expected_relation_ids
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "decl.total-perceptores" not in entries
    assert result.values["decl.total-perceptores"] == perceptores_binding_value
    assert entries["decl.base-total"].operand_refs == (base_relation_id,)
    assert entries["decl.retenciones-total"].operand_refs == (retenciones_relation_id,)
    if modelo == "180":
        assert result.values[_DECL_BASE_TOTAL_CASILLA] == fixture_values[_DECL_BASE_TOTAL_CASILLA]
        assert result.values[_DECL_RETENCIONES_TOTAL_CASILLA] == fixture_values[_DECL_RETENCIONES_TOTAL_CASILLA]


def test_modelo_190_calculation_resolves_modelo_111_quarterly_filings(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """M111 quarterly percepciones/retenciones fold into the M190 annual summary.

    WHAT IS ASSERTED, AND ON WHAT AUTHORITY. Two different claims, with two
    different grounds:

    * The M190 annual totals equal the sum of the four M111 quarters. This is a
      CONSISTENCY INVARIANT entailed by RIRPF art. 108: §1 obliges the retenedor
      to declare, each quarter, "las cantidades retenidas y de los ingresos a
      cuenta que correspondan por el trimestre natural inmediato anterior", and
      §2 obliges an annual declaration of "las retenciones e ingresos a cuenta
      efectuados". Both cover the same quantity and the four natural quarters
      partition the year, so a truthful pair must reconcile. It is NOT a
      computation M190 performs -- the M190 diseño defines its totals as sums
      over its own type-2 perceptor records -- and no stated reconciliation
      REQUIREMENT was located in the bundled corpus (a bounded negative over the
      material held, not a claim about what AEAT requires).
    * Everything else here is engine wiring: the ten M111->M190 relations
      resolve, the retired per-quarter perceptor source casillas stay retired,
      the withholding binding aggregates detail records, and the totals reach
      their targets through the declared operand refs.

    PROBE VALUES, NOT AN ORACLE. The quarterly amounts below are chosen by this
    test, and are deliberately DISTINCT and non-round. No tax fact is asserted
    by them and no filing is claimed: they exist to discriminate a genuine sum
    from a max, a first-element pick, a last-write-wins, or a hardcoded
    constant. Identical amounts cannot tell those apart, which is exactly why
    the earlier version of this test -- which folded the fixture's uniform
    ``1000.00`` redaction placeholder -- passed with every amount replaced by
    an arbitrary number.

    The M190 fixture is a ``parser_anchor``, so its printed amounts are
    placeholders and are NOT used as expected values here. It is still read,
    for the two things a parse anchor legitimately supplies: the perceptor
    identity row and the clave G/01 classification.
    """
    detail_nif, detail_clave, _placeholder_percepcion, _placeholder_retencion = _m190_fixture_detail_observation()
    assert detail_clave == "G"

    snapshot = registry_snapshot("190", 2024, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2024, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: _m190_fixture_relation_source_value(
            requirement,
            period_index,
            percepciones_quarterly=_M190_PERCEPCIONES_PROBE_QUARTERS,
            retenciones_quarterly=_M190_RETENCIONES_PROBE_QUARTERS,
        ),
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2024,
        period="0A",
    )
    observed_source_casillas = {requirement.source_casilla_ids[0] for requirement in requirements}
    assert not (observed_source_casillas & _RETIRED_M190_M111_PERCEPCIONES_SOURCE_CASILLAS)
    expected_percepciones_annual = sum(_M190_PERCEPCIONES_PROBE_QUARTERS, Decimal("0"))
    expected_retenciones_annual = sum(_M190_RETENCIONES_PROBE_QUARTERS, Decimal("0"))
    expected_relation_values = dict.fromkeys(_M190_EXPECTED_RELATION_IDS, Decimal("0"))
    expected_relation_values[_M190_REL_111_ACTIVIDADES_DINERARIO] = expected_percepciones_annual
    expected_relation_values[_M190_REL_111_RETENCIONES] = expected_retenciones_annual
    assert relation_values == expected_relation_values
    # Three records for ONE perceptor: the clave G percepcion appears twice (as
    # it would for a professional invoicing in two different quarters) and a
    # clave A percepcion once. The binding declares
    # `aggregation = { op = "count_distinct" }` over distinct
    # (perceptor, clave, subclave) type-2 records, so the annual "numero total
    # de percepciones" must be 2, not 3. A plain record count returns 3 here,
    # which is precisely the per-quarter double-count the dedicated withholding
    # binding replaced.
    withholding_observations = (
        _withholding_observation(
            "m190-2024-0A-detail-1",
            detail_nif,
            detail_clave,
            percibido_dinerario=_M190_PERCEPCIONES_PROBE_QUARTERS[0],
            retencion_practicada=_M190_RETENCIONES_PROBE_QUARTERS[0],
        ),
        _withholding_observation(
            "m190-2024-0A-detail-2",
            detail_nif,
            detail_clave,
            percibido_dinerario=_M190_PERCEPCIONES_PROBE_QUARTERS[1],
            retencion_practicada=_M190_RETENCIONES_PROBE_QUARTERS[1],
        ),
        _withholding_observation(
            "m190-2024-0A-detail-3",
            detail_nif,
            _M190_SECOND_CLAVE,
            percibido_dinerario=_M190_PERCEPCIONES_PROBE_QUARTERS[2],
            retencion_practicada=_M190_RETENCIONES_PROBE_QUARTERS[2],
        ),
    )
    binding_values = resolve_withholding_binding_values(snapshot.revision, withholding_observations)
    assert binding_values[_M190_PERCEPCIONES_BINDING] == Decimal("2"), (
        "modelo-190-percepciones-anual must count DISTINCT (perceptor, clave, subclave) "
        f"records, so two clave {detail_clave} rows plus one clave {_M190_SECOND_CLAVE} row "
        f"for one perceptor is 2, not 3; got {binding_values[_M190_PERCEPCIONES_BINDING]!r}"
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        date_context={"filing_period": _registry_filing_date(2024, "0A")},
        binding_values=binding_values,
        relation_values=relation_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert _M190_TOTAL_PERCEPCIONES_CASILLA not in entries
    assert result.values[_M190_TOTAL_PERCEPCIONES_CASILLA] == Decimal("2")
    assert result.values[_M190_PERCEPCIONES_TOTAL_CASILLA] == expected_percepciones_annual
    assert result.values[_M190_RETENCIONES_TOTAL_CASILLA] == expected_retenciones_annual
    assert len(entries[_M190_PERCEPCIONES_TOTAL_CASILLA].operand_refs) == 9
    assert entries[_M190_RETENCIONES_TOTAL_CASILLA].operand_refs == ("modelo-190-rel-111-retenciones-anual",)


def test_modelo_100_payment_calculation_resolves_cross_model_periodic_and_annual_observations(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("100", 2025, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observations = _observations_from_requirements(requirements, _renta_relation_observed_value)

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": _registry_filing_date(2025, "0A")},
        relation_values=relation_values,
        binding_values={
            # Production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories; scenario models a directa filer.
            "renta-2025-profile-has-economic-activity": Decimal("1"),
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            _M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING: Decimal("0"),
            _M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )

    assert set(relation_values) == {
        "renta-2025-rel-111-retenciones-trimestrales",
        "renta-2025-rel-111-retenciones-mensuales",
        "renta-2025-rel-123-retenciones-trimestrales",
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
        "renta-2025-rel-184-atribucion-actividades-economicas",
        "renta-2025-rel-190-retenciones-anuales",
        "renta-2025-rel-193-retenciones-anuales",
    }
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries[_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA].operand_refs == (
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
    )


def test_modelo_184_attribution_income_folds_into_modelo_100_casilla_1577(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Régimen de atribución de rentas fold-in (LIRPF art. 86).

    The entidad en régimen de atribución files Modelo 184 and the partner
    declares the attributed share in Modelo 100. The entidad's attributed
    economic-activity net income — Modelo 184 source casilla
    ``tipo2.renta-atribuible-importe`` — folds into the partner's Modelo 100
    casilla 1577 (``Rendimiento neto de actividad economica atribuido por
    entidades en regimen de atribucion de rentas``) through the canonical
    cross-modelo relation ``renta-2025-rel-184-atribucion-actividades-economicas``
    whose ``relation_prefill`` target binding materialises the value.

    The expected 1577 value is the SEEDED Modelo 184 observation, NOT a registry
    formula output: a distinct seed (``777.77``, unrelated to any registry
    formula) discriminates the live fold-in from a silent default-zero blank and
    proves the relation -> materialise -> bound-casilla chain carries the real
    attributed amount end to end.
    """
    attributed_income = Decimal("777.77")
    m184_relation = "renta-2025-rel-184-atribucion-actividades-economicas"
    m184_target_binding = "renta-2025-modelo-184-atribucion-actividades-economicas"
    casilla_1577 = validated_casilla_id("1577", surface="modelo-184 attribution fold-in target")

    snapshot = registry_snapshot("100", 2025, "0A")

    def _value_for(requirement: RegistryFoldRequirement, period_index: int) -> Decimal:
        if requirement.relation_ids[0] == m184_relation:
            return attributed_income
        return _renta_relation_observed_value(requirement, period_index)

    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observations = _observations_from_requirements(requirements, _value_for)
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )
    assert relation_values[m184_relation] == attributed_income

    # Materialise ONLY the M184 attribution relation into its declared
    # ``relation_prefill`` target binding. The retencion relations (111/123/...)
    # feed other casillas and are out of scope for this fold-in; restricting the
    # materialisation isolates the M184 -> 1577 path under test.
    materialized = materialize_relation_binding_values(
        snapshot.revision,
        {m184_relation: relation_values[m184_relation]},
        period="0A",
    )
    assert materialized[m184_target_binding] == attributed_income

    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": _registry_filing_date(2025, "0A")},
        relation_values=relation_values,
        binding_values={
            # Production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories; scenario models a directa filer.
            "renta-2025-profile-has-economic-activity": Decimal("1"),
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            **materialized,
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            _M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING: Decimal("0"),
            _M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )

    assert result.values[casilla_1577] == attributed_income


def test_modelo_100_payment_calculation_consumes_real_modelo_130_quarterly_registry_results(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    filing_year = 2025
    modelo_130_results = {}
    # Casilla 05 ("Pagos fraccionados anteriores") is now a bound carry, so the
    # cumulative prior-payment figure per quarter is supplied through the carry
    # binding_value (the source of truth) rather than as a manual casilla input.
    casilla_05_carry = {
        "1T": Decimal("0"),
        "2T": Decimal("500"),
        "3T": Decimal("1100"),
        "4T": Decimal("1800"),
    }
    for period, inputs in {
        "1T": _casilla_inputs({"01": Decimal("10000"), "02": Decimal("3000"), "06": Decimal("100")}),
        "2T": _casilla_inputs({"01": Decimal("16000"), "02": Decimal("6000"), "06": Decimal("250")}),
        "3T": _casilla_inputs({"01": Decimal("22000"), "02": Decimal("9000"), "06": Decimal("450")}),
        "4T": _casilla_inputs({"01": Decimal("28000"), "02": Decimal("12000"), "06": Decimal("650")}),
    }.items():
        modelo_130_results[period] = calculate_registry_snapshot(
            registry_snapshot("130", filing_year, period),
            inputs=inputs,
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-resultados-negativos-anteriores": Decimal("0"),
                "modelo-130-pagos-fraccionados-anteriores": casilla_05_carry[period],
            },
            date_context={"filing_period": _registry_filing_date(filing_year, period)},
        )

    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: _renta_relation_observed_value_from_modelo_130_results(
            requirement,
            period_index,
            modelo_130_results,
        ),
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": _registry_filing_date(filing_year, "0A")},
        relation_values=relation_values,
        binding_values={
            # Production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories; scenario models a directa filer.
            "renta-2025-profile-has-economic-activity": Decimal("1"),
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            _M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING: Decimal("0"),
            _M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "renta-2025-rel-130-pagos-fraccionados" in relation_values
    assert "renta-2025-rel-130-pagos-fraccionados" in entries[_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA].operand_refs


def test_modelo_100_2024_m131_pagos_fraccionados_cumulative_wires_to_casilla_0604(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """M100 2024: four quarterly M131 filings of €450 each aggregate to €1800 via relation resolution.

    Verifies the binding/relation wiring from M131 quarterly filings (casilla 15) into the
    M100 pagos-fraccionados-ingresados aggregation targeting casilla 0604.  Exercises the
    full relation-source → observation → resolution roundtrip without triggering the full
    settlement chain (which requires additional profile bindings not under test here).

    Anti-tautology: each quarterly amount is distinct for M130 (100, 200, 300, 400) so a
    summation error would produce a wrong total.  M131 uses 450 per quarter so the expected
    M131 aggregate is 1800 and M130 aggregate is 1000.
    """
    filing_year = 2024
    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")

    m131_quarterly_amounts = (Decimal("450"), Decimal("450"), Decimal("450"), Decimal("450"))
    m130_quarterly_amounts = (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))

    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: _renta_2024_relation_observed_value(
            requirement,
            period_index,
            m130_quarterly_amounts=m130_quarterly_amounts,
            m131_quarterly_amounts=m131_quarterly_amounts,
        ),
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )

    # Relations must be present and resolved to their correct sums.
    assert "renta-2024-rel-131-pagos-fraccionados" in relation_values
    assert "renta-2024-rel-130-pagos-fraccionados" in relation_values
    assert relation_values["renta-2024-rel-131-pagos-fraccionados"] == Decimal("1800")
    assert relation_values["renta-2024-rel-130-pagos-fraccionados"] == Decimal("1000")

    # The pagos-fraccionados-ingresados formula must target 0604 and reference both relations.
    formula = next(f for f in snapshot.revision.formulas if f.id == "renta-2024-pagos-fraccionados-ingresados")
    assert formula.target_casilla_id == _M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA
    assert formula.expression.op is not None
    relation_ids_in_formula = {arg.relation for arg in formula.expression.args if arg.relation is not None}
    assert relation_ids_in_formula == {
        "renta-2024-rel-130-pagos-fraccionados",
        "renta-2024-rel-131-pagos-fraccionados",
    }

    # The binding for M131 must declare the correct source_modelo and source_casilla_id.
    binding = next(b for b in snapshot.revision.bindings if b.id == "renta-2024-modelo-131-pagos-fraccionados")
    assert selector_as_dict(binding) == {
        "source_modelo": "131",
        "source_casilla_id": _M131_PAGOS_FRACCIONADOS_CASILLA,
    }


def test_modelo_100_2024_m131_pagos_fraccionados_anti_tautology_proportional_change(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Changing M131 quarterly amount from 300 to 450 causes the resolved relation value to increase by 600.

    This is the anti-tautology proof: the resolution is not a copy of the input but a real
    sum of four quarterly filings.  Any arithmetic error in the aggregation would break this.
    """
    filing_year = 2024
    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")

    def _resolve_0604_relations(m131_quarterly: Decimal) -> Decimal:
        obs = _observations_from_requirements(
            requirements,
            lambda requirement, period_index: _renta_2024_relation_observed_value(
                requirement,
                period_index,
                m130_quarterly_amounts=(Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")),
                m131_quarterly_amounts=(m131_quarterly, m131_quarterly, m131_quarterly, m131_quarterly),
            ),
        )
        rv = resolve_relation_values_from_observations(snapshot.revision, obs, filing_year=filing_year, period="0A")
        # 0604 = M130 sum + M131 sum = 4*100 + 4*m131_quarterly
        return rv["renta-2024-rel-130-pagos-fraccionados"] + rv["renta-2024-rel-131-pagos-fraccionados"]

    result_low = _resolve_0604_relations(Decimal("300"))
    result_high = _resolve_0604_relations(Decimal("450"))
    # Increase of 150 per quarter * 4 quarters = 600 total
    assert result_high - result_low == Decimal("600")


@pytest.mark.parametrize(
    ("filing_year", "source_year", "source_values", "expected_binding"),
    [
        (
            2022,
            2021,
            _casilla_inputs(
                {
                    "0224": Decimal("4000"),
                    "1479": Decimal("2000"),
                    "1553": Decimal("1500"),
                    "1577": Decimal("1000"),
                }
            ),
            Decimal("8500"),
        ),
        (
            2026,
            2025,
            _casilla_inputs(
                {
                    "0224": Decimal("5000"),
                    "1479": Decimal("2000"),
                    "1553": Decimal("1500"),
                    "1577": Decimal("1000"),
                }
            ),
            Decimal("9500"),
        ),
    ],
)
def test_modelo_130_resolves_previous_year_modelo_100_filed_casillas_into_binding(
    filing_year: int,
    source_year: int,
    source_values: dict[CasillaId, Decimal],
    expected_binding: Decimal,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Verifies the previous_filing binding resolves the source modelo's casillas
    into the expected value. The binding's ``expected_binding`` is the SUM of the
    source modelo's input casillas as the binding selector declares it — that sum
    is what the binding resolver must produce, NOT a registry formula output. This
    test exercises the binding closure, not formula arithmetic.
    """

    snapshot = registry_snapshot("130", filing_year, "1T")

    binding_values = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            RegistryModeloObservation(
                modelo="100",
                filing_year=source_year,
                period="0A",
                observations=_grounded_observations(
                    modelo="100",
                    filing_year=source_year,
                    period="0A",
                    casilla_values=source_values,
                ),
            ),
        ),
        filing_year=filing_year,
        period="1T",
    )

    assert binding_values["irpf.previous_year_economic_activity_net_income"] == expected_binding


def _revision_edge_years(revision: ModeloRevision) -> tuple[int, ...]:
    if revision.period_selector.years:
        years = sorted(revision.period_selector.years)
        return tuple(dict.fromkeys((years[0], years[-1])))
    year_from = revision.period_selector.year_from
    if year_from is None:
        raise AssertionError(f"revision {revision.id} has no filing-year selector")
    year_to = revision.period_selector.year_to
    if year_to is not None:
        if year_to == year_from:
            return (year_from,)
        midpoint = year_from + ((year_to - year_from) // 2)
        return tuple(dict.fromkeys((year_from, midpoint, year_to)))
    return (year_from, year_from + 1, year_from + 7)


def _renta_relation_observed_value(requirement: RegistryFoldRequirement, period_index: int) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-111-retenciones-trimestrales":
        return (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"))[period_index]
    if relation_id == "renta-2025-rel-111-retenciones-mensuales":
        return Decimal(period_index + 1)
    if relation_id == "renta-2025-rel-123-retenciones-trimestrales":
        return Decimal("20")
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        return (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))[period_index]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("5")
    if relation_id == "renta-2025-rel-190-retenciones-anuales":
        return Decimal("40")
    if relation_id == "renta-2025-rel-193-retenciones-anuales":
        return Decimal("50")
    if relation_id == "renta-2025-rel-184-atribucion-actividades-economicas":
        return Decimal("60")
    raise AssertionError(f"unhandled relation requirement {relation_id}")


def _renta_2024_relation_observed_value(
    requirement: RegistryFoldRequirement,
    period_index: int,
    *,
    m130_quarterly_amounts: tuple[Decimal, Decimal, Decimal, Decimal],
    m131_quarterly_amounts: tuple[Decimal, Decimal, Decimal, Decimal],
) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2024-rel-131-pagos-fraccionados":
        return m131_quarterly_amounts[period_index]
    if relation_id == "renta-2024-rel-130-pagos-fraccionados":
        return m130_quarterly_amounts[period_index]
    if relation_id == "renta-2024-rel-131-rendimiento-neto-modulos":
        return Decimal("0")
    if relation_id in {
        "renta-2024-rel-111-retenciones-trimestrales",
        "renta-2024-rel-111-retenciones-mensuales",
        "renta-2024-rel-123-retenciones-trimestrales",
        "renta-2024-rel-193-retenciones-anuales",
    }:
        return Decimal("0")
    raise AssertionError(f"unhandled 2024 relation requirement {relation_id}")


def _renta_relation_observed_value_from_modelo_130_results(
    requirement: RegistryFoldRequirement,
    period_index: int,
    modelo_130_results: dict[str, RegistryCalculationResult],
) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        period = ("1T", "2T", "3T", "4T")[period_index]
        return modelo_130_results[period].values[_M130_A_INGRESAR_CASILLA]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("0")
    return Decimal("0")


def _registry_filing_date(filing_year: int, period: str) -> date:
    """Resolve the calculation date context through the typed period authority.

    ``calculate_registry_snapshot`` documents ``date_context["filing_period"]``
    as the snapshot's typed calculation filing date, and defaults the key to
    ``calculation_filing_date(snapshot.filing_period)`` when a caller omits it.
    A test that supplies the key must therefore resolve it from the same
    authority, or a date-aware registry bracket is selected under a temporal
    context production would never produce.

    This is deliberately NOT the deadline authority's
    ``resolve_filing_closes_on``. Three distinct dates exist for one Modelo 130
    quarter and only one of them is this key's contract: the payment cutoff
    (the 20th of the following month), the plazo voluntario close
    (weekend-adjusted, and 30 January for 4T), and the calculation filing
    period (the quarter end). ``date_context["filing_period"]`` is the third.
    """
    return calculation_filing_date(Period.from_year_and_code(filing_year, period))


@pytest.mark.parametrize("period", ("1T", "2T", "3T", "4T"))
def test_registry_filing_date_matches_the_engine_default_date_context(
    period: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """The date context this module supplies must equal the engine's own default.

    DISCRIMINATING for all four quarters: restoring the retired
    twentieth-of-the-following-month map fails every parametrisation
    (2025-04-20 != 2025-03-31, and so on through 4T).

    ``calculate_registry_snapshot`` defaults ``date_context["filing_period"]``
    to ``calculation_filing_date(snapshot.filing_period)``. A test that supplies
    the key by hand therefore has exactly one correct value — the one the engine
    would have chosen — and any other value silently selects date-aware registry
    brackets under a temporal context no production call can produce.

    The expected value is read from the loaded snapshot, not restated here, so
    this asserts agreement with the authority rather than a copied literal.
    """
    filing_year = 2025
    snapshot = registry_snapshot("130", filing_year, period)
    assert snapshot.filing_period is not None, "M130 snapshot must carry a typed filing period"

    assert _registry_filing_date(filing_year, period) == calculation_filing_date(snapshot.filing_period)


@pytest.mark.parametrize("period", ("1T", "2T", "3T", "4T"))
def test_registry_filing_date_stays_inside_the_filing_year(period: str) -> None:
    """A quarterly context must never fall in the following calendar year.

    DISCRIMINATING for 4T only, and SUPPORTING for 1T/2T/3T: the retired map
    kept those three inside the filing year and failed only on 4T, whose
    2026-01-20 crossed into the next year. The three passing parametrisations
    are context, not proof.

    Modelo 130's 4T payment cutoff and plazo voluntario close both land in
    January of the FOLLOWING year. Supplying either as the calculation date
    context moves a year-keyed registry bracket onto the wrong year's law for
    every 4T filing, which is the drift this module's date routing exists to
    prevent.
    """
    filing_year = 2025

    assert _registry_filing_date(filing_year, period).year == filing_year
