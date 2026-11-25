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
belongs in the bundled oracle corpora (``corpus/manual_oracles/``, or the Renta
WEB Open parity replay captures for Modelo 100) keyed by
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

from .....core.aggregation import RetencionClave
from .....core.casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from .....tests.inventory import FIXTURES_DIR
from ..binding_selector_utils import selector_as_dict
from ..binding_temporal import BindingTemporalKind
from ..bindings import RegistryModeloObservation, resolve_available_bound_inputs_by_casilla_id
from ..bindings_previous_filing import resolve_previous_filing_binding_values
from ..errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..relation_dependency import RelationDependencyRole, RelationKind
from ..relations import RegistryFoldRequirement, relation_prefill_bindings_for_period, relation_source_requirements
from ..runtime_graph import expression_binding_refs
from ..schema import ModeloDefinition, ModeloRevision, RegistrySnapshot
from ..schema_catalogues import RegistryCatalogues
from ..withholding_bindings import WithholdingObservation, resolve_withholding_binding_values
from .authored_editions import (
    authored_revisions,
    authored_revisions_where,
    filing_year_envelope,
    newest_authored_edition,
    revision_covering,
)
from .cross_dependency_calculation_support import (
    casilla_inputs,
    grounded_observations,
    observations_from_requirements,
    source_editions_calculate,
)
from .modelo_100_registry_support import M100_NO_DESCENDANT_MATERNIDAD_BINDINGS, M100_NO_LET_PROPERTY_BINDINGS
from .published_authority import PublishedGovernedFactSource, published_supported_filing_years
from .registry_filing_date_support import registry_filing_date
from .relation_fixture import resolve_relation_values_from_observations
from .withholding_observation_defaults import zero_incapacity_and_foral_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

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
_M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING = "renta-profile-madrid-nacimiento-adopcion-eligible-count"
_M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING = "renta-profile-unidad-familiar-otros-miembros-base"
_M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING = "renta-profile-minimo-descendientes-estatal"
_M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING = "renta-profile-minimo-descendientes-autonomico"
_M100_MINIMO_ASCENDIENTES_ESTATAL_BINDING = "renta-profile-minimo-ascendientes-estatal"
_M100_MINIMO_ASCENDIENTES_AUTONOMICO_BINDING = "renta-profile-minimo-ascendientes-autonomico"
_M100_MADRID_CUIDADO_ASCENDIENTES_COUNT_BINDING = "renta-profile-deduccion-madrid-cuidado-ascendientes-count"
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
#: Probe amounts for three Modelo 190 type-2 records.
#:
#: PROBES, NOT AN ORACLE. These are chosen by this test and assert no tax fact.
#: They are DISTINCT and non-round on purpose: a sum over records tested with
#: equal amounts cannot be told apart from a max, a first-record pick, or a
#: hardcoded constant, and no single probe equals the sum, so a partial sum is
#: visible too.
_M190_PERCEPCION_PROBES: tuple[Decimal, Decimal, Decimal] = (
    Decimal("1234.56"),
    Decimal("2345.67"),
    Decimal("3456.78"),
)
_M190_RETENCION_PROBES: tuple[Decimal, Decimal, Decimal] = (
    Decimal("185.18"),
    Decimal("351.85"),
    Decimal("518.52"),
)
#: A second clave for the same perceptor, so the count_distinct aggregation is
#: exercised against more than one (perceptor, clave) pair. "A" is trabajo
#: (empleados) against the fixture perceptor's "G" actividades profesionales.
_M190_SECOND_CLAVE = "A"
#: The per-position row sums the record design names for the two money totals:
#: positions 82-94, 109-121, 256-268 and 283-295 for the percepciones, and
#: 95-107, 122-134, 269-281 and 296-308 for the retenciones e ingresos a cuenta.
_M190_PERCEPCIONES_ROW_SUMS = (
    "modelo-190-perceptor-rows-percepcion-dineraria-total",
    "modelo-190-perceptor-rows-percepcion-especie-total",
    "modelo-190-perceptor-rows-incapacidad-dineraria-total",
    "modelo-190-perceptor-rows-incapacidad-especie-total",
)
_M190_RETENCIONES_ROW_SUMS = (
    "modelo-190-perceptor-rows-retencion-practicada-total",
    "modelo-190-perceptor-rows-ingreso-a-cuenta-total",
    "modelo-190-perceptor-rows-incapacidad-retencion-total",
    "modelo-190-perceptor-rows-incapacidad-ingreso-a-cuenta-total",
)
# The newest Modelo 100 edition the registry authors, which is filing grade.
_M100_YEAR = newest_authored_edition("100")


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
def _fixture_stem(modelo: str) -> str:
    """The stem of the one justificante fixture committed for ``modelo``."""
    (pdf_path,) = sorted((FIXTURES_DIR / "justificantes" / modelo).glob("*.pdf"))
    return pdf_path.stem


@cache
def _fixture_pdf_text(modelo: str, fixture_stem: str | None = None) -> str:
    pdf_path = FIXTURES_DIR / "justificantes" / modelo / f"{fixture_stem or _fixture_stem(modelo)}.pdf"
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
def _annual_summary_fixture_values(modelo: str, fixture_stem: str | None = None) -> dict[CasillaId, Decimal]:
    """Read the resumen-anual amounts a justificante fixture PRINTS.

    These are printed values, not AEAT-authoritative figures: the M190 fixture
    is a redacted ``parser_anchor`` whose amounts are the placeholder
    ``1000.00``, and the M180 fixture's amounts are generator literals. Tests
    use them as a self-consistent reference to close the fold arithmetic
    against — see the module docstring for what that does and does not prove.
    """
    fixture_stem = fixture_stem or _fixture_stem(modelo)
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


def _withholding_observation(
    source_id: str,
    nif: str,
    clave: str,
    *,
    exercise: int,
    percibido_dinerario: Decimal,
    retencion_practicada: Decimal,
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(exercise, 6, 1),
        clave=RetencionClave.from_registry(clave),
        percibido_dinerario=percibido_dinerario,
        retencion_practicada=retencion_practicada,
        **zero_incapacity_and_foral_fields(),
    )


def test_cross_model_relations_resolve_from_observations_for_revision_edge_years(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    # Filing selection refuses years below the published floor, so each
    # revision's edges are taken inside the supported envelope; a revision
    # authored wholly below the floor has no selectable year to exercise.
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    exercised = 0
    modelos, _catalogues = registry_tree
    for modelo in modelos:
        for revision in modelo.revisions.values():
            relation_ids = {binding.id for binding, _ in relation_prefill_bindings_for_period(revision)}
            if not relation_ids:
                continue
            for filing_year, period in _full_relation_filing_year_periods(
                revision=revision, relation_ids=relation_ids, floor=supported_years.floor
            ):
                if not source_editions_calculate(
                    relation_source_requirements(revision, filing_year=filing_year, period=period)
                ):
                    continue
                exercised += 1
                _assert_relations_resolve_from_observations(
                    target_modelo=modelo.id,
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                    relation_ids=relation_ids,
                    floor=supported_years.floor,
                    scope=f"{modelo.id}/{revision.id}/{filing_year}/{period}",
                )
    assert exercised, "no relation-bearing revision reached a supported filing year"


def _full_relation_filing_year_periods(
    *,
    revision: ModeloRevision,
    relation_ids: set[str],
    floor: int,
) -> Iterator[tuple[int, str]]:
    """Yield ``(filing_year, period)`` pairs where every relation is active.

    A relation is "active" for a period when it either has no
    target_periods declared (matches every period) or lists the
    period explicitly. The gate only exercises tuples where the
    active set equals the full relation set so partial-coverage
    periods do not pollute the resolution check.
    """
    for filing_year in _revision_edge_years(revision, floor=floor):
        for period in revision.period_selector.periods:
            active_relation_ids = {
                binding.id for binding, _ in relation_prefill_bindings_for_period(revision, period=period)
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
    floor: int,
    scope: str,
) -> None:
    """Drive the relation-source -> observation -> resolution roundtrip and assert closure.

    A source filing whose year lies below the support floor cannot be held, so
    it is never observed, and resolution refuses on the relation it feeds rather
    than resolving it below the floor; that relation stays for the filer to state.
    """
    requirements = relation_source_requirements(revision, filing_year=filing_year, period=period)
    held = tuple(requirement for requirement in requirements if requirement.filing_year >= floor)
    below_floor = {
        str(binding_id)
        for requirement in requirements
        if requirement.filing_year < floor
        for binding_id in requirement.target_bindings
    }
    observations = observations_from_requirements(
        held,
        lambda _requirement, period_index: Decimal(period_index + 1),
        target_modelo=target_modelo,
        fallback_revision=revision,
    )
    if below_floor:
        with pytest.raises(RegistryValidationError) as refusal:
            resolve_relation_values_from_observations(revision, observations, filing_year=filing_year, period=period)
        assert any(binding_id in str(refusal.value) for binding_id in below_floor), scope
        return
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


def _annual_summary_relation_cases() -> tuple[object, ...]:
    """Modelo 180 across its closed edition, the current one and a projected year, and Modelo 193's closed edition."""
    envelope = filing_year_envelope()
    m180_closed, m180_current = authored_revisions("180")[-2:]
    assert m180_closed.valid_to is not None, "the Modelo 180 edition before the newest must be closed"
    historical_year = m180_closed.valid_to.year
    assert historical_year >= envelope.floor, "the closed Modelo 180 edition must reach the support floor"
    assert str(revision_covering("180", envelope.horizon).id) == str(m180_current.id)
    # The closed edition just before the newest Modelo 193 edition is the last whose annual totals
    # resolve from the quarterly modelo 123 filings (its perceptor count already counts the type-2
    # records); the newest edition also sums the type-2 records and keeps 123 as a reconciliation
    # check. This value is ASSERTED against the law-determined pick, never injected into resolution.
    m193_closed = authored_revisions("193")[-2]
    m180_relations = (
        _m180_fixture_relation_source_values,
        "modelo-180-115-perceptores-anual",
        frozenset({"modelo-180-115-base-anual", "modelo-180-115-retenciones-anual"}),
        "modelo-180-115-base-anual",
        "modelo-180-115-retenciones-anual",
    )
    return (
        pytest.param("180", historical_year, str(m180_closed.id), *m180_relations, id="modelo-180-historical"),
        pytest.param("180", envelope.horizon, str(m180_current.id), *m180_relations, id="modelo-180-current"),
        pytest.param("180", envelope.horizon + 1, str(m180_current.id), *m180_relations, id="modelo-180-future"),
        pytest.param(
            "193",
            m193_closed.valid_from.year,
            str(m193_closed.id),
            _m193_relation_source_values,
            "modelo-193-perceptores-anual",
            frozenset({"modelo-193-123-base-anual", "modelo-193-123-retenciones-anual"}),
            "modelo-193-123-base-anual",
            "modelo-193-123-retenciones-anual",
            id="modelo-193-quarterly-aggregate-edition",
        ),
    )


_ANNUAL_SUMMARY_RELATION_CASES = _annual_summary_relation_cases()


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
    observations = observations_from_requirements(
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
        date_context={"filing_period": registry_filing_date(filing_year, "0A")},
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


@pytest.mark.parametrize("exercise", filing_year_envelope().years)
def test_modelo_190_declarante_totals_sum_the_declarations_own_perceptor_records(
    exercise: int,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Every supported exercise totals the Modelo 190 resumen over its own type-2 records.

    WHAT IS ASSERTED, AND ON WHAT AUTHORITY. Each record design from the 2020
    edition onward, and the 2025 instrucciones for casillas 01 to 03, define the
    three declarante totals over the type-2 perceptor records of the same
    declaration: the number of records, the sum of the percepciones integras and
    valoraciones, and the sum of the retenciones and ingresos a cuenta. No
    official text defines them from Modelo 111, so no exercise takes a Modelo
    111 relation, and every exercise reaches the totals through the same
    per-position row sums.

    PROBE VALUES, NOT AN ORACLE. The record amounts are chosen by this test and
    are DISTINCT and non-round so a genuine sum is told apart from a max, a
    first-record pick or a hardcoded constant. The M190 fixture is a
    ``parser_anchor`` whose printed amounts are redaction placeholders, so it
    supplies only the perceptor identity row and the clave G/01 classification.
    """
    detail_nif, detail_clave, _placeholder_percepcion, _placeholder_retencion = _m190_fixture_detail_observation()
    assert detail_clave == "G"

    snapshot = registry_snapshot("190", exercise, "0A")
    assert not relation_prefill_bindings_for_period(snapshot.revision)
    assert not snapshot.revision.dependency_classifications
    # Three records for ONE perceptor: the clave G percepcion appears twice (as
    # it would for a professional invoicing in two different quarters) and a
    # clave A percepcion once. The binding declares
    # `aggregation = { op = "count_distinct" }` over distinct
    # (perceptor, clave, subclave) type-2 records, so the annual "numero total
    # de percepciones" must be 2, not 3.
    claves = (detail_clave, detail_clave, _M190_SECOND_CLAVE)
    withholding_observations = tuple(
        _withholding_observation(
            f"m190-{exercise}-0A-detail-{index}",
            detail_nif,
            clave,
            exercise=exercise,
            percibido_dinerario=percepcion,
            retencion_practicada=retencion,
        )
        for index, (clave, percepcion, retencion) in enumerate(
            zip(claves, _M190_PERCEPCION_PROBES, _M190_RETENCION_PROBES, strict=True), start=1
        )
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
        date_context={"filing_period": registry_filing_date(exercise, "0A")},
        binding_values=binding_values,
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert _M190_TOTAL_PERCEPCIONES_CASILLA not in entries
    assert result.values[_M190_TOTAL_PERCEPCIONES_CASILLA] == Decimal("2")
    assert result.values[_M190_PERCEPCIONES_TOTAL_CASILLA] == Decimal("7037.01")
    assert result.values[_M190_RETENCIONES_TOTAL_CASILLA] == Decimal("1055.55")
    assert entries[_M190_PERCEPCIONES_TOTAL_CASILLA].operand_refs == _M190_PERCEPCIONES_ROW_SUMS
    assert entries[_M190_RETENCIONES_TOTAL_CASILLA].operand_refs == _M190_RETENCIONES_ROW_SUMS


def test_modelo_100_payment_calculation_resolves_cross_model_periodic_and_annual_observations(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("100", _M100_YEAR, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=_M100_YEAR, period="0A")
    observations = observations_from_requirements(requirements, _renta_relation_observed_value)

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=_M100_YEAR,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": registry_filing_date(_M100_YEAR, "0A")},
        relation_values=relation_values,
        binding_values={
            # Production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories; scenario models a directa filer.
            "renta-profile-has-economic-activity": Decimal("1"),
            "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
            "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
            **M100_NO_LET_PROPERTY_BINDINGS,
            "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
            "renta-profile-estimacion-directa": Decimal("1"),
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-profile-declaration-type": Decimal("1"),
            "renta-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-profile-marriage-full-year": Decimal("0"),
            "renta-profile-marriage-month-start": Decimal("0"),
            "renta-profile-marriage-month-end": Decimal("0"),
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
            "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
            "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
            "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
            "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
            _M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING: Decimal("0"),
            _M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
            # No ascendant rows: the mínimo por ascendientes aggregates and the Madrid count are zero.
            _M100_MINIMO_ASCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_ASCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
            _M100_MADRID_CUIDADO_ASCENDIENTES_COUNT_BINDING: Decimal("0"),
            "renta-maritime-gross-navigation-income": Decimal("0"),
            "renta-maritime-annual-salary": Decimal("0"),
            "renta-maritime-qualifying-days": Decimal("0"),
            # The Art. 81.2 guarderia increment is declared year-free in every edition;
            # neutral zero for a filer with no childcare spend.
            "renta-profile-incremento-guarderia": Decimal("0"),
            # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
            # neutral zero for a scenario with no descendants.
            **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        },
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 1, 1)},
        # Art. 75 Ley 19/1994 maritime-worker exemption path; neutral false
        # when the chain under test is unrelated.
        boolean_binding_values={"renta-maritime-path-rebeca": False},
    )

    assert set(relation_values) == {
        "renta-modelo-130-pagos-fraccionados",
        "renta-modelo-131-pagos-fraccionados",
    }
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert entries[_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA].operand_refs == (
        "renta-modelo-130-pagos-fraccionados",
        "renta-modelo-131-pagos-fraccionados",
    )


def test_a_filed_modelo_184_does_not_fill_the_member_share_casilla_1577(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Casilla 1577 is the member's share, which no Modelo 184 total supplies (LIRPF art. 89).

    The newest manual's comunidad de bienes example has comunero Y declare a
    rendimiento neto atribuido of 15.000, half the entity's 30.000. Modelo 184
    files the entity's type-2 attribution records for every member and income
    class, and a relation prefill sums them with no member or class filter, so a
    fold into 1577 would report the entity's aggregate as the member's share.
    The edition declares no Modelo 184 fold, a filed Modelo 184 moves no
    relation value, and the member's own figure reaches 1577 unchanged.
    """
    member_share = Decimal("15000")
    casilla_1577 = validated_casilla_id("1577", surface="modelo-100 member attributed activity yield")
    snapshot = registry_snapshot("100", _M100_YEAR, "0A")

    requirements = relation_source_requirements(snapshot.revision, filing_year=_M100_YEAR, period="0A")
    assert all(requirement.source_modelo != "184" for requirement in requirements)
    observations = observations_from_requirements(requirements, _renta_relation_observed_value)
    m184_entity_filing = RegistryModeloObservation(
        modelo="184",
        filing_year=_M100_YEAR,
        period="0A",
        observations=grounded_observations(
            modelo="184",
            filing_year=_M100_YEAR,
            period="0A",
            casilla_values={
                validated_casilla_id("tipo2.renta-atribuible-importe", surface="modelo-184 entity total"): Decimal(
                    "30000"
                ),
            },
        ),
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=_M100_YEAR,
        period="0A",
    )
    assert (
        resolve_relation_values_from_observations(
            snapshot.revision,
            (*observations, m184_entity_filing),
            filing_year=_M100_YEAR,
            period="0A",
        )
        == relation_values
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={casilla_1577: member_share},
        date_context={"filing_period": registry_filing_date(_M100_YEAR, "0A")},
        relation_values=relation_values,
        binding_values={
            # Production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories; scenario models a directa filer.
            "renta-profile-has-economic-activity": Decimal("1"),
            "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
            "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
            **M100_NO_LET_PROPERTY_BINDINGS,
            "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
            "renta-profile-estimacion-directa": Decimal("1"),
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-profile-declaration-type": Decimal("1"),
            "renta-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-profile-marriage-full-year": Decimal("0"),
            "renta-profile-marriage-month-start": Decimal("0"),
            "renta-profile-marriage-month-end": Decimal("0"),
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
            "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
            "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
            "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
            "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
            _M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING: Decimal("0"),
            _M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
            # No ascendant rows: the mínimo por ascendientes aggregates and the Madrid count are zero.
            _M100_MINIMO_ASCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_ASCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
            _M100_MADRID_CUIDADO_ASCENDIENTES_COUNT_BINDING: Decimal("0"),
            "renta-maritime-gross-navigation-income": Decimal("0"),
            "renta-maritime-annual-salary": Decimal("0"),
            "renta-maritime-qualifying-days": Decimal("0"),
            # The Art. 81.2 guarderia increment is declared year-free in every edition;
            # neutral zero for a filer with no childcare spend.
            "renta-profile-incremento-guarderia": Decimal("0"),
            # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
            # neutral zero for a scenario with no descendants.
            **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        },
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 1, 1)},
        boolean_binding_values={"renta-maritime-path-rebeca": False},
    )

    assert result.values[casilla_1577] == member_share


def test_modelo_100_payment_calculation_consumes_real_modelo_130_quarterly_registry_results(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    filing_year = _M100_YEAR
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
        "1T": casilla_inputs(
            {"01": Decimal("10000"), "gastos-deducibles-previos": Decimal("3000"), "06": Decimal("100")}
        ),
        "2T": casilla_inputs(
            {"01": Decimal("16000"), "gastos-deducibles-previos": Decimal("6000"), "06": Decimal("250")}
        ),
        "3T": casilla_inputs(
            {"01": Decimal("22000"), "gastos-deducibles-previos": Decimal("9000"), "06": Decimal("450")}
        ),
        "4T": casilla_inputs(
            {"01": Decimal("28000"), "gastos-deducibles-previos": Decimal("12000"), "06": Decimal("650")}
        ),
    }.items():
        modelo_130_results[period] = calculate_registry_snapshot(
            registry_snapshot("130", filing_year, period),
            inputs=inputs,
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-resultados-negativos-anteriores": Decimal("0"),
                "modelo-130-pagos-fraccionados-anteriores": casilla_05_carry[period],
            },
            date_context={"filing_period": registry_filing_date(filing_year, period)},
            # The M100 side models a normal-modality filer, so box 02 carries no art. 30.2.ª provision.
            enum_binding_values={"modelo-130-estimacion-directa-modalidad": "directa_normal"},
        )

    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = observations_from_requirements(
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
        date_context={"filing_period": registry_filing_date(filing_year, "0A")},
        relation_values=relation_values,
        binding_values={
            # Production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories; scenario models a directa filer.
            "renta-profile-has-economic-activity": Decimal("1"),
            "renta-profile-income-family-excluded-capital-mobiliario": Decimal("0"),
            "renta-profile-income-family-excluded-capital-inmobiliario": Decimal("0"),
            **M100_NO_LET_PROPERTY_BINDINGS,
            "renta-profile-income-family-excluded-ganancias-patrimoniales": Decimal("0"),
            "renta-profile-estimacion-directa": Decimal("1"),
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-profile-declaration-type": Decimal("1"),
            "renta-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-profile-marriage-full-year": Decimal("0"),
            "renta-profile-marriage-month-start": Decimal("0"),
            "renta-profile-marriage-month-end": Decimal("0"),
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
            "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
            "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
            "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
            "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
            "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
            _M100_MADRID_NACIMIENTO_ADOPCION_ELIGIBLE_COUNT_BINDING: Decimal("0"),
            _M100_UNIDAD_FAMILIAR_OTROS_MIEMBROS_BASE_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_DESCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
            # No ascendant rows: the mínimo por ascendientes aggregates and the Madrid count are zero.
            _M100_MINIMO_ASCENDIENTES_ESTATAL_BINDING: Decimal("0"),
            _M100_MINIMO_ASCENDIENTES_AUTONOMICO_BINDING: Decimal("0"),
            _M100_MADRID_CUIDADO_ASCENDIENTES_COUNT_BINDING: Decimal("0"),
            # Maritime-worker exemption operands stay neutral: the path itself is false.
            "renta-maritime-gross-navigation-income": Decimal("0"),
            "renta-maritime-annual-salary": Decimal("0"),
            "renta-maritime-qualifying-days": Decimal("0"),
            # The Art. 81.2 guarderia increment is declared year-free in every edition;
            # neutral zero for a filer with no childcare spend.
            "renta-profile-incremento-guarderia": Decimal("0"),
            # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
            # neutral zero for a scenario with no descendants.
            **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
        },
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 1, 1)},
        boolean_binding_values={"renta-maritime-path-rebeca": False},
    )

    entries = {entry.target_casilla_id: entry for entry in result.entries}
    assert "renta-modelo-130-pagos-fraccionados" in relation_values
    assert "renta-modelo-130-pagos-fraccionados" in entries[_M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA].operand_refs


# The relations the observation helper below knows how to observe. The test runs on
# every supported Modelo 100 edition the registry authors whose relation set stays
# inside them; a newer edition adding attribution or annual-summary relations drops out.
_OBSERVED_RENTA_RELATIONS = frozenset(
    {
        "renta-modelo-131-pagos-fraccionados",
        "renta-modelo-130-pagos-fraccionados",
    }
)
_RELATION_SET_EDITIONS = tuple(
    revision.valid_from.year
    for revision in authored_revisions_where(
        "100",
        lambda revision: (
            revision.valid_from.year in PublishedGovernedFactSource().supported_filing_years().years
            and {binding.id for binding, _ in relation_prefill_bindings_for_period(revision)}
            <= _OBSERVED_RENTA_RELATIONS
        ),
    )
)
assert _RELATION_SET_EDITIONS, "no supported Modelo 100 edition keeps to the observed relation set"


@pytest.mark.parametrize("filing_year", _RELATION_SET_EDITIONS)
def test_modelo_100_m131_pagos_fraccionados_cumulative_wires_to_casilla_0604(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
    filing_year: int,
) -> None:
    """M100: four quarterly M131 filings of €450 each aggregate to €1800 via relation resolution.

    Verifies the binding/relation wiring from M131 quarterly filings (casilla 15) into the
    M100 pagos-fraccionados-ingresados aggregation targeting casilla 0604.  Exercises the
    full relation-source → observation → resolution roundtrip without triggering the full
    settlement chain (which requires additional profile bindings not under test here).

    Anti-tautology: each quarterly amount is distinct for M130 (100, 200, 300, 400) so a
    summation error would produce a wrong total.  M131 uses 450 per quarter so the expected
    M131 aggregate is 1800 and M130 aggregate is 1000.
    """
    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")

    m131_quarterly_amounts = (Decimal("450"), Decimal("450"), Decimal("450"), Decimal("450"))
    m130_quarterly_amounts = (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))

    observations = observations_from_requirements(
        requirements,
        lambda requirement, period_index: _renta_quarterly_relation_observed_value(
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
    assert "renta-modelo-131-pagos-fraccionados" in relation_values
    assert "renta-modelo-130-pagos-fraccionados" in relation_values
    assert relation_values["renta-modelo-131-pagos-fraccionados"] == Decimal("1800")
    assert relation_values["renta-modelo-130-pagos-fraccionados"] == Decimal("1000")

    # The pagos-fraccionados-ingresados formula must target 0604 and reference both relations.
    formula = next(f for f in snapshot.revision.formulas if f.id == "renta-pagos-fraccionados-ingresados")
    assert formula.target_casilla_id == _M100_PAGOS_FRACCIONADOS_INGRESADOS_CASILLA
    assert formula.expression.op is not None
    relation_ids_in_formula = set(expression_binding_refs(formula.expression))
    assert relation_ids_in_formula == {
        "renta-modelo-130-pagos-fraccionados",
        "renta-modelo-131-pagos-fraccionados",
    }

    # The binding for M131 must declare the correct source_modelo and its result pair:
    # casilla 15 (resultado) then casilla 14 (resultado a ingresar de las anteriores).
    binding = next(b for b in snapshot.revision.bindings if b.id == "renta-modelo-131-pagos-fraccionados")
    assert selector_as_dict(binding) == {
        "source_modelo": "131",
        "source_casilla_ids": (_M131_PAGOS_FRACCIONADOS_CASILLA, "14"),
        "relation_kind": RelationKind.CROSS_MODEL_OUTPUT,
        "dependency_role": RelationDependencyRole.INSTALMENT_TO_FINAL_SETTLEMENT,
        "temporal": {
            "kind": BindingTemporalKind.SAME_FILING_YEAR_PERIODS,
            "source_periods": ("1T", "2T", "3T", "4T"),
        },
    }


@pytest.mark.parametrize("filing_year", _RELATION_SET_EDITIONS)
def test_modelo_100_m131_pagos_fraccionados_anti_tautology_proportional_change(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
    filing_year: int,
) -> None:
    """Changing M131 quarterly amount from 300 to 450 causes the resolved relation value to increase by 600.

    This is the anti-tautology proof: the resolution is not a copy of the input but a real
    sum of four quarterly filings.  Any arithmetic error in the aggregation would break this.
    """
    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")

    def _resolve_0604_relations(m131_quarterly: Decimal) -> Decimal:
        obs = observations_from_requirements(
            requirements,
            lambda requirement, period_index: _renta_quarterly_relation_observed_value(
                requirement,
                period_index,
                m130_quarterly_amounts=(Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")),
                m131_quarterly_amounts=(m131_quarterly, m131_quarterly, m131_quarterly, m131_quarterly),
            ),
        )
        rv = resolve_relation_values_from_observations(snapshot.revision, obs, filing_year=filing_year, period="0A")
        # 0604 = M130 sum + M131 sum = 4*100 + 4*m131_quarterly
        return rv["renta-modelo-130-pagos-fraccionados"] + rv["renta-modelo-131-pagos-fraccionados"]

    result_low = _resolve_0604_relations(Decimal("300"))
    result_high = _resolve_0604_relations(Decimal("450"))
    # Increase of 150 per quarter * 4 quarters = 600 total
    assert result_high - result_low == Decimal("600")


# Carry coordinates follow the published envelope rather than pinned years, so
# the cases move with the floor and horizon.
_SUPPORTED_YEARS = published_supported_filing_years()
assert _SUPPORTED_YEARS is not None


@pytest.mark.parametrize(
    ("filing_year", "source_year", "source_values", "expected_binding"),
    [
        (
            _SUPPORTED_YEARS.floor + 1,
            _SUPPORTED_YEARS.floor,
            casilla_inputs(
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
            _SUPPORTED_YEARS.horizon,
            _SUPPORTED_YEARS.horizon - 1,
            casilla_inputs(
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
                observations=grounded_observations(
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


def test_modelo_100_source_below_the_supported_floor_cannot_be_grounded_for_carry() -> None:
    """The floor year's prior-year M100 source has no admissible revision to stamp."""
    support = published_supported_filing_years()
    assert support is not None
    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        grounded_observations(
            modelo="100",
            filing_year=support.floor - 1,
            period="0A",
            casilla_values=casilla_inputs({"0224": Decimal("4000")}),
        )


def _revision_edge_years(revision: ModeloRevision, *, floor: int) -> tuple[int, ...]:
    """Return the edge filing years of the revision's span inside the supported envelope."""
    if revision.period_selector.years:
        years = sorted(year for year in revision.period_selector.years if year >= floor)
        return tuple(dict.fromkeys((years[0], years[-1]))) if years else ()
    authored_from = revision.period_selector.year_from
    if authored_from is None:
        raise AssertionError(f"revision {revision.id} has no filing-year selector")
    year_from = max(authored_from, floor)
    year_to = revision.period_selector.year_to
    if year_to is not None and year_to < floor:
        return ()
    if year_to is not None:
        if year_to == year_from:
            return (year_from,)
        midpoint = year_from + ((year_to - year_from) // 2)
        return tuple(dict.fromkeys((year_from, midpoint, year_to)))
    return (year_from, year_from + 1, year_from + 7)


def _renta_relation_observed_value(requirement: RegistryFoldRequirement, period_index: int) -> Decimal:
    relation_id = requirement.target_bindings[0]
    if relation_id == "renta-modelo-130-pagos-fraccionados":
        return (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))[period_index]
    if relation_id == "renta-modelo-131-pagos-fraccionados":
        return Decimal("5")
    raise AssertionError(f"unhandled relation requirement {relation_id}")


def _renta_quarterly_relation_observed_value(
    requirement: RegistryFoldRequirement,
    period_index: int,
    *,
    m130_quarterly_amounts: tuple[Decimal, Decimal, Decimal, Decimal],
    m131_quarterly_amounts: tuple[Decimal, Decimal, Decimal, Decimal],
) -> Decimal:
    relation_id = requirement.target_bindings[0]
    if relation_id == "renta-modelo-131-pagos-fraccionados":
        return m131_quarterly_amounts[period_index]
    if relation_id == "renta-modelo-130-pagos-fraccionados":
        return m130_quarterly_amounts[period_index]
    raise AssertionError(f"unhandled relation requirement {relation_id}")


def _renta_relation_observed_value_from_modelo_130_results(
    requirement: RegistryFoldRequirement,
    period_index: int,
    modelo_130_results: dict[str, RegistryCalculationResult],
) -> Decimal:
    relation_id = requirement.target_bindings[0]
    if relation_id == "renta-modelo-130-pagos-fraccionados":
        period = ("1T", "2T", "3T", "4T")[period_index]
        return modelo_130_results[period].values[_M130_A_INGRESAR_CASILLA]
    if relation_id == "renta-modelo-131-pagos-fraccionados":
        return Decimal("0")
    return Decimal("0")
