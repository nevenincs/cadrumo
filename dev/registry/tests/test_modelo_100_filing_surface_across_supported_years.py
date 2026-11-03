"""Modelo 100 identity, ledger and settlement surface across every supported filing year.

The surface is authored once, at the earliest edition the official record
design carries it, and inherited forward. These tests read every year of the
registry's own support envelope, so a member re-keyed onto a later edition, or
a year dropped from the chain, fails here rather than in one pinned year.

The settlement formulas are checked against an oracle independent of the
engine: each edition's official AEAT input dictionary prints the arithmetic of
casillas 0587, 0595, 0598 and 0670 in their labels.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.binding_provider_registration import registration_for
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.export_xml_dictionary import decode_dictionary_text
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ids import BindingId, RelationId
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.tests.modelo_100_profile_binding_tables import (
    FAMILY_ROW_BINDINGS,
    PERSONAL_FAMILY_CASILLA_TO_BINDING,
)
from cadrumo.domain.calculations.registry.tests.modelo_100_registry_support import neutral_binding_values

from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


SUPPORTED_YEARS = _supported_years()


_LEDGER_CASILLA_BINDINGS: Mapping[str, str] = {
    "0171": "renta-ledger-income-0171",
    **{
        casilla: f"renta-ledger-expense-{casilla}-deductible"
        for casilla in (
            "0183",
            "0186",
            "0191",
            "0192",
            "0193",
            "0194",
            "0195",
            "0199",
            "0200",
            "0202",
            "0203",
            "0206",
            "0208",
            "0217",
        )
    },
    "1380": "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
    "1382": "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "1385": "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "1388": "renta-base-liquidable-negativa-general-anterior",
}

_SETTLEMENT_FORMULAS: Mapping[str, str] = {
    "0587": "renta-cuota-liquida-incrementada-total",
    "0595": "renta-cuota-resultante-autoliquidacion",
    "0598": "renta-retenciones-arrendamientos-urbanos",
    "0670": "renta-resultado-declaracion",
}

# A settlement formula may add a figure the form prints in no casilla of its own.
# Casilla 0598 credits urban-rental withholding whether or not the rental is an
# activity, but the label prints only the capital inmobiliario box 0153; the
# activity component comes from the payer records of the activity-rental class.
_UNPRINTED_FORMULA_OPERANDS: Mapping[str, frozenset[str]] = {
    "0598": frozenset({"binding:renta-retencion-soportada-arrendamiento-actividad"}),
}

# The official label of the resultado casilla signs these maternity-deduction
# carry-ins for earlier ejercicios as additions, while the AEAT manual treats
# them as increments of a deduction. An edition whose label names one of them
# withholds the resultado formula until that contradiction is ruled on.
_CONTESTED_RESULTADO_CARRY_INS = frozenset({"1912", "1913", "1915", "1916"})

_WORK_CERTIFICATE = "renta-retencion-soportada-trabajo"
_WORK_RETENCIONES_CASILLA = "0596"
_TOTAL_PAGOS_A_CUENTA = "0609"
_CUOTA_RESULTANTE = "0595"
_CUOTA_DIFERENCIAL = "0610"
_RESULTADO = "0670"


@pytest.fixture(scope="module")
def edition(registry_snapshot: Callable[..., RegistrySnapshot]) -> Callable[[int], RegistrySnapshot]:
    """The Modelo 100 annual edition the canonical resolver selects for one filing year."""

    def select(filing_year: int) -> RegistrySnapshot:
        return registry_snapshot("100", filing_year, "0A", grade=RegistryAuthorityGrade.CALCULATION)

    return select


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_identity_casillas_are_bound_to_their_profile_bindings(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    snapshot = edition(filing_year)
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for casilla_id, binding_id in PERSONAL_FAMILY_CASILLA_TO_BINDING.items():
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.BOUND, (filing_year, casilla_id)
        assert casilla.binding == binding_id, (filing_year, casilla_id)
        binding = bindings[binding_id]
        assert binding.source is BindingSourceKind.PROFILE
        assert binding.legal_refs
        assert binding.source_refs
        provider = binding.provider
        assert isinstance(provider, ProfileProvider)
        assert provider.dictionary_field in (None, casilla_id)


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_identity_evidence_cites_the_edition_that_governs_the_year(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    """An inherited identity binding still cites its own year's record design and manual."""
    snapshot = edition(filing_year)
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    authored_year = int(snapshot.revision.id)

    for binding_id in PERSONAL_FAMILY_CASILLA_TO_BINDING.values():
        cited = {str(ref) for ref in bindings[binding_id].source_refs}
        stale = {ref for ref in cited if re.search(r"-(20\d\d)-", ref) and f"-{authored_year}-" not in ref}
        assert not stale, (filing_year, binding_id, sorted(stale))


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_ledger_targets_are_bound_wherever_the_edition_declares_them(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    """Each ledger binding exists exactly in the editions whose design carries its casilla."""
    snapshot = edition(filing_year)
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings = {binding.id for binding in snapshot.revision.bindings}

    for casilla_id, binding_id in _LEDGER_CASILLA_BINDINGS.items():
        if casilla_id not in casillas:
            assert binding_id not in bindings, (filing_year, casilla_id, binding_id)
            continue
        assert casillas[casilla_id].input_kind is InputKind.BOUND, (filing_year, casilla_id)
        assert casillas[casilla_id].binding == binding_id, (filing_year, casilla_id)
        assert binding_id in bindings, (filing_year, binding_id)


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_work_certificate_is_the_only_source_of_suffered_work_retenciones(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    """Casilla 0596 is filled from the certificates the payers issued, and from nothing else.

    The retencion credited here is the one the declarant SUFFERED on its salary.
    Only the payers' certificates evidence that figure for this taxpayer, so the
    casilla names their payer-record family as its single source: an alternate
    would let a second, weaker source fill the same credit.
    """
    snapshot = edition(filing_year)
    casilla = next(item for item in snapshot.revision.casillas if item.id == _WORK_RETENCIONES_CASILLA)

    assert casilla.binding == _WORK_CERTIFICATE
    assert casilla.alternate_bindings == ()
    assert _WORK_CERTIFICATE in {binding.id for binding in snapshot.revision.bindings}


def _dictionary_labels(snapshot: RegistrySnapshot, catalogues: RegistryCatalogues) -> Mapping[str, str]:
    """Map each casilla number to its label in the edition's official input dictionary."""
    layout = next(item for item in snapshot.revision.export_layouts if item.dictionary_source_ref is not None)
    assert layout.dictionary_source_ref is not None
    source = catalogues.sources[str(layout.dictionary_source_ref)]
    text = decode_dictionary_text((bundled_path() / source.corpus_path).read_bytes())
    labels: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^[A-Za-z0-9_]+=\[[^\]]*\]\[[^\]]*\]\[(\d{4})\]\[(.*)\]\s*$", line.strip())
        if match is not None:
            labels.setdefault(match[1], match[2])
    return labels


def _label_coefficients(label: str) -> dict[str, int]:
    """Read the signed casilla terms of the bracketed arithmetic an official label prints."""
    arithmetic = label[label.index("(") :] if "(" in label else label
    coefficients: dict[str, int] = {}
    for sign, casilla in re.findall(r"([+-]?)\s*\[(\d{4})\]", arithmetic):
        coefficients[casilla] = coefficients.get(casilla, 0) + (-1 if sign == "-" else 1)
    return coefficients


def _expression_coefficients(expression: FormulaExpression) -> dict[str, int]:
    """Linear coefficients of a sum/negate/subtract/copy expression, a binding keyed ``binding:<id>``."""
    if expression.casilla_id is not None:
        return {str(expression.casilla_id): 1}
    if expression.binding is not None:
        return {f"binding:{expression.binding}": 1}
    op = str(expression.op or "")
    children = [_expression_coefficients(arg) for arg in expression.args]
    total: dict[str, int] = {}
    if op == "negate":
        return {key: -value for key, value in children[0].items()}
    if op == "subtract":
        head, *tail = children
        children = [head, *({key: -value for key, value in child.items()} for child in tail)]
    elif op not in {"sum", "add", "copy"}:
        raise AssertionError(f"not a linear casilla expression: {op!r}")
    for child in children:
        for key, value in child.items():
            total[key] = total.get(key, 0) + value
    return {key: value for key, value in total.items() if value}


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_settlement_formulas_reproduce_the_official_label_arithmetic(
    edition: Callable[[int], RegistrySnapshot],
    registry_tree: tuple[tuple[object, ...], RegistryCatalogues],
    filing_year: int,
) -> None:
    snapshot = edition(filing_year)
    labels = _dictionary_labels(snapshot, registry_tree[1])
    formulas = {formula.target_casilla_id: formula for formula in snapshot.revision.formulas}

    for casilla_id, formula_id in _SETTLEMENT_FORMULAS.items():
        official = _label_coefficients(labels[casilla_id])
        assert official, (filing_year, casilla_id, labels[casilla_id])
        formula = formulas.get(casilla_id)
        if casilla_id == _RESULTADO and official.keys() & _CONTESTED_RESULTADO_CARRY_INS:
            assert formula is None, (filing_year, "resultado is authored over a contested label")
            continue
        assert formula is not None, (filing_year, casilla_id)
        assert formula.id == formula_id
        coefficients = _expression_coefficients(formula.expression)
        unprinted = {key for key in coefficients if key.startswith("binding:")}
        assert unprinted == _UNPRINTED_FORMULA_OPERANDS.get(casilla_id, frozenset()), (filing_year, casilla_id)
        assert all(coefficients[key] == 1 for key in unprinted), (filing_year, casilla_id)
        printed = {key: value for key, value in coefficients.items() if key not in unprinted}
        assert printed == official, (filing_year, casilla_id)


def _binding_inputs(
    snapshot: RegistrySnapshot,
) -> tuple[dict[BindingId, Decimal], dict[BindingId, bool], dict[BindingId, date], dict[BindingId, str]]:
    """Neutral inputs for every scalar binding the edition declares.

    The work certificates' family is excluded here and supplied by the caller,
    so the figure under test is the only one on that binding.
    """
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.id != _WORK_CERTIFICATE
    )
    decimals["renta-profile-declaration-type"] = Decimal("1")
    return decimals, booleans, dates, enums


def _settle(snapshot: RegistrySnapshot, filing_year: int, *, work_certificate: Decimal) -> Mapping[str, Decimal | None]:
    decimals, booleans, dates, enums = _binding_inputs(snapshot)
    # The value the calculation's source mesh resolves from the payer records reaches the engine on the binding.
    decimals[_WORK_CERTIFICATE] = work_certificate
    relations: dict[RelationId, Decimal] = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.RELATION_PREFILL
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "0003": Decimal("30000.00"),
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, {_WORK_CERTIFICATE: work_certificate}),
        },
        date_context={"filing_period": date(filing_year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values=relations,
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )
    return {str(key): value for key, value in result.values.items()}


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_settlement_chain_credits_the_work_certificate_against_the_cuota(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    """A certificate retencion reaches 0596, 0609 and lowers the cuota diferencial by its amount."""
    snapshot = edition(filing_year)
    retencion = Decimal("1000.00")
    baseline = _settle(snapshot, filing_year, work_certificate=Decimal("0"))
    credited = _settle(snapshot, filing_year, work_certificate=retencion)

    assert credited[_WORK_RETENCIONES_CASILLA] == retencion
    assert credited[_TOTAL_PAGOS_A_CUENTA] == retencion
    resultante = baseline[_CUOTA_RESULTANTE]
    assert resultante is not None and resultante > Decimal("0"), filing_year
    assert baseline[_CUOTA_DIFERENCIAL] == resultante
    assert credited[_CUOTA_RESULTANTE] == resultante
    assert credited[_CUOTA_DIFERENCIAL] == resultante - retencion

    formulas = {formula.target_casilla_id for formula in snapshot.revision.formulas}
    if _RESULTADO in formulas:
        assert credited[_RESULTADO] == credited[_CUOTA_DIFERENCIAL]
    else:
        # Withheld over a contested label, the resultado stays a manual box the
        # filer must state; the engine never derives it.
        resultado = next(item for item in snapshot.revision.casillas if item.id == _RESULTADO)
        assert resultado.input_kind is InputKind.MANUAL, filing_year


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_profile_bindings_dispatch_through_the_single_profile_provider(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    assert registration_for(BindingSourceKind.PROFILE).provider_model is ProfileProvider
    profile = [b for b in edition(filing_year).revision.bindings if b.source is BindingSourceKind.PROFILE]
    assert profile
    assert all(isinstance(binding.provider, ProfileProvider) for binding in profile)


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_family_rows_read_the_canonical_stored_row_objects(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    bindings = {binding.id: binding for binding in edition(filing_year).revision.bindings}
    for binding_id, (object_path, leaf, count_path) in FAMILY_ROW_BINDINGS.items():
        provider = bindings[binding_id].provider
        assert isinstance(provider, ProfileProvider)
        assert provider.rows is not None
        assert (provider.rows.object_path, provider.rows.leaf, provider.rows.count_path) == (
            object_path,
            leaf,
            count_path,
        )
        assert provider.repeating is True


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_taxpayer_birth_date_reads_the_official_design_field(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    provider = next(
        b for b in edition(filing_year).revision.bindings if b.id == "renta-profile-taxpayer-birth-date"
    ).provider
    assert isinstance(provider, ProfileProvider)
    assert provider.profile_key == "renta_taxpayer.birth_date"
    assert provider.xsd_path == "/DatosIdentificativos/Declarante/DPFNAC_D"
    assert provider.dictionary_field == "DPFNAC_D"
    assert provider.format == "date"


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_descendientes_minimos_aggregate_is_keyed_to_the_selected_edition(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    """The derived aggregate is a live binding feeding the computed 0513/0514 minimos.

    Its profile key is scoped to the edition the year selects, so a projected
    year reads the key of the edition it projects from.
    """
    snapshot = edition(filing_year)
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    provider = bindings["renta-profile-minimo-descendientes-estatal"].provider
    assert isinstance(provider, ProfileProvider)
    assert provider.profile_key == f"renta_family.descendientes_minimos_aggregate_{snapshot.revision.id}"

    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    formulas = {formula.id: formula for formula in snapshot.revision.formulas}
    for casilla_id in ("0513", "0514"):
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.COMPUTED
        assert casilla.formula is not None
        assert formulas[casilla.formula].target_casilla_id == casilla_id
