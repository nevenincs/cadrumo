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
from cadrumo.domain.calculations.registry.binding_provider_registration import provider_model_for
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.export_parse import decode_dictionary_text
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ids import BindingId, RelationId
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema import RegistryCatalogues, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


SUPPORTED_YEARS = _supported_years()

_IDENTITY_CASILLA_BINDINGS: Mapping[str, str] = {
    "DPNIF_D": "renta-profile-tax-id",
    "DP_APENOM_D": "renta-profile-display-name",
    "ZCCAD": "renta-profile-tax-residence-ccaa",
    "TIPOTRIBUTACION": "renta-profile-declaration-type",
    "SEXO_D": "renta-profile-taxpayer-sex",
    "ECIVIL": "renta-profile-marital-status",
    "DPFNAC_D": "renta-profile-taxpayer-birth-date",
    "DPNIF_C": "renta-profile-spouse-tax-id",
    "DP_APENOM_C": "renta-profile-spouse-display-name",
    "DPFNAC_C": "renta-profile-spouse-birth-date",
    "SEXO_C": "renta-profile-spouse-sex",
    "DPGMIN_D": "renta-profile-taxpayer-disability-grade",
    "DECFAL": "renta-profile-taxpayer-death-date",
    "DPGMIN_C": "renta-profile-spouse-disability-grade",
    "NORESIDENTE": "renta-profile-spouse-non-resident-irpf",
    "RESIDENTEUE": "renta-profile-spouse-eu-eea-resident",
    "ZRUE2": "renta-profile-spouse-eu-eea-country",
    "HIJOSUE": "renta-profile-family-descendants-eu-eea-deduction",
    "PH18": "renta-profile-family-minor-children-in-unit",
    "NIFDLG": "renta-family-descendant-tax-id",
    "APENOMDLG": "renta-family-descendant-display-name",
    "FNACDLG": "renta-family-descendant-birth-date",
    "MINUSDLG": "renta-family-descendant-disability-grade",
    "FALLDLG": "renta-family-descendant-death-date",
    "DNIASDLG": "renta-family-ascendant-tax-id",
    "APENOMDLG_ASC": "renta-family-ascendant-display-name",
    "ANOASDLG": "renta-family-ascendant-birth-date",
    "PCTMINASDLG": "renta-family-ascendant-disability-grade",
    "CONVASDLG": "renta-family-ascendant-cohabiting-descendant-count",
    "FALLASDLG": "renta-family-ascendant-death-date",
}

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
    "1388": "renta-base-liquidable-negativa-general-anterior",
}

_SETTLEMENT_FORMULAS: Mapping[str, str] = {
    "0587": "renta-cuota-liquida-incrementada-total",
    "0595": "renta-cuota-resultante-autoliquidacion",
    "0598": "renta-retenciones-arrendamientos-urbanos",
    "0670": "renta-resultado-declaracion",
}

# The official label of the resultado casilla signs these maternity-deduction
# carry-ins for earlier ejercicios as additions, while the AEAT manual treats
# them as increments of a deduction. An edition whose label names one of them
# withholds the resultado formula until that contradiction is ruled on.
_CONTESTED_RESULTADO_CARRY_INS = frozenset({"1912", "1913", "1915", "1916"})

_WORK_CERTIFICATE = "renta-certificado-trabajo-retenciones"
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

    for casilla_id, binding_id in _IDENTITY_CASILLA_BINDINGS.items():
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

    for binding_id in _IDENTITY_CASILLA_BINDINGS.values():
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
def test_work_certificate_is_an_alternate_source_of_suffered_work_retenciones(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    snapshot = edition(filing_year)
    casilla = next(item for item in snapshot.revision.casillas if item.id == _WORK_RETENCIONES_CASILLA)
    assert _WORK_CERTIFICATE in casilla.alternate_bindings
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
    """Linear casilla coefficients of a sum/negate/subtract/copy expression."""
    if expression.casilla_id is not None:
        return {str(expression.casilla_id): 1}
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
        assert _expression_coefficients(formula.expression) == official, (filing_year, casilla_id)


def _work_retencion_equivalents(snapshot: RegistrySnapshot) -> set[str]:
    """The sources of casilla 0596 other than the work certificate; equivalents must agree."""
    casilla = next(item for item in snapshot.revision.casillas if item.id == _WORK_RETENCIONES_CASILLA)
    return {str(casilla.binding), *(str(item) for item in casilla.alternate_bindings)} - {_WORK_CERTIFICATE}


def _binding_inputs(
    snapshot: RegistrySnapshot, *, work_certificate: Decimal
) -> tuple[dict[BindingId, Decimal], dict[BindingId, bool], dict[BindingId, date], dict[BindingId, str]]:
    """Neutral inputs for every scalar binding the edition declares, plus the work certificate.

    The other equivalent sources of casilla 0596 stay unsupplied: equivalent
    bindings must agree, so the certificate is the only source of that value.
    """
    decimals: dict[BindingId, Decimal] = {}
    booleans: dict[BindingId, bool] = {}
    dates: dict[BindingId, date] = {}
    enums: dict[BindingId, str] = {}
    equivalents = _work_retencion_equivalents(snapshot)
    for binding in snapshot.revision.bindings:
        if binding.id in equivalents:
            continue
        channel = binding.value.channel
        if channel in {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}:
            decimals[binding.id] = Decimal("0")
        elif channel is BindingValueChannel.BOOLEAN:
            booleans[binding.id] = False
        elif channel is BindingValueChannel.DATE:
            dates[binding.id] = date(1975, 6, 15)
        elif channel is BindingValueChannel.ENUM:
            enums[binding.id] = "madrid"
    decimals["renta-profile-declaration-type"] = Decimal("1")
    decimals[_WORK_CERTIFICATE] = work_certificate
    return decimals, booleans, dates, enums


def _settle(snapshot: RegistrySnapshot, filing_year: int, *, work_certificate: Decimal) -> Mapping[str, Decimal | None]:
    decimals, booleans, dates, enums = _binding_inputs(snapshot, work_certificate=work_certificate)
    equivalents = _work_retencion_equivalents(snapshot)
    relations: dict[RelationId, Decimal] = {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source is BindingSourceKind.RELATION_PREFILL and binding.id not in equivalents
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs={"0003": Decimal("30000.00")},
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


_REPEATING_FAMILY_ROWS: Mapping[str, tuple[str, str]] = {
    "renta-family-descendant-tax-id": ("descendants", "tax_id"),
    "renta-family-descendant-display-name": ("descendants", "display_name"),
    "renta-family-descendant-birth-date": ("descendants", "birth_date"),
    "renta-family-descendant-disability-grade": ("descendants", "disability_grade"),
    "renta-family-descendant-death-date": ("descendants", "death_date"),
    "renta-family-ascendant-tax-id": ("ascendants", "tax_id"),
    "renta-family-ascendant-display-name": ("ascendants", "display_name"),
    "renta-family-ascendant-birth-date": ("ascendants", "birth_date"),
    "renta-family-ascendant-disability-grade": ("ascendants", "disability_grade"),
    "renta-family-ascendant-cohabiting-descendant-count": ("ascendants", "cohabiting_descendant_count"),
    "renta-family-ascendant-death-date": ("ascendants", "death_date"),
}


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_profile_bindings_dispatch_through_the_single_profile_provider(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    assert provider_model_for(BindingSourceKind.PROFILE) is ProfileProvider
    profile = [b for b in edition(filing_year).revision.bindings if b.source is BindingSourceKind.PROFILE]
    assert profile
    assert all(isinstance(binding.provider, ProfileProvider) for binding in profile)


@pytest.mark.parametrize("filing_year", SUPPORTED_YEARS)
def test_family_rows_are_repeating_profile_collections(
    edition: Callable[[int], RegistrySnapshot], filing_year: int
) -> None:
    bindings = {binding.id: binding for binding in edition(filing_year).revision.bindings}
    for binding_id, (collection, field) in _REPEATING_FAMILY_ROWS.items():
        provider = bindings[binding_id].provider
        assert isinstance(provider, ProfileProvider)
        assert provider.profile_model == "RentaFamilyProfile"
        assert provider.collection == collection
        assert provider.field == field
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
