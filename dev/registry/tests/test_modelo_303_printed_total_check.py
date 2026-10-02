"""Modelo 303 box [27] must equal the printed boxes its record design adds into it.

Every Modelo 303 record design defines "Total cuota devengada" [27] as a sum of
other printed boxes, and the list grew across the years. The registry computes
[27] by projecting the semantic ``iva.cuota-devengada-total``, so any amount
that total carries beyond the printed boxes yields a fichero whose [27] its own
boxes do not add up to. The ``equals(["27", "iva.cuota-devengada-total"])``
predicate cannot notice, because [27] is that total's projection.

The promotor's autoconsumo is the amount that once reached [27] that way. The
registry now states that base per rate row, so its cuota lands in the printed
rate boxes, and a base not stated per rate is refused rather than left out.

These gates run the compiled registry, the real formula engine and the real
predicate evaluator. The expected addends are read from each revision's own
bundled record design, not from the registry declaration under test, and the
expected amounts come from the statutory 21% rate (LIVA art. 90) applied to the
supplied base. Each mutation proof re-introduces a defect on an isolated
scratch copy of the registry, never the tracked tree.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.tests.verification_substance_fixtures import workflow_profile
from cadrumo.application.modelo.verification_predicates import evaluate_verification_predicates
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_verification import (
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind

from ..compiler.loader import load_registry_tree
from ._gate_support import mutate_declaration, scratch_registry_tree
from ._modelo_303_registry_support import load_modelo_303

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_TOTAL_BOX: CasillaId = validated_casilla_id("27")
_GENERAL_CUOTA_BOX: CasillaId = validated_casilla_id("09")
_AUTOCONSUMO_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"
_AUTOCONSUMO_GENERAL_BASE: CasillaId = validated_casilla_id("iva.autoconsumo.promotor.general.base")
_GENERAL_CUOTA_BINDING = "modelo-303-iva-repercutido-general-cuota"
_ATTRIBUTION_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"
_PRINTED_TOTAL_MISMATCH = "application.modelo.findings.printed_total_mismatch"
_RATE_SPLIT_PREDICATE = "modelo-303-iva-autoconsumo-promotor-base-equals-por-tipo"
_TOTAL_FORMULA = 'id = "modelo-303-iva-cuota-devengada-total"'

#: The [27] row of a Modelo 303 record design: "Total cuota devengada ( [152] + ... ) [27]".
_DESIGN_TOTAL_ROW = re.compile(r"Total cuota devengada\s*\((?P<addends>[^)]*)\)\s*\[27\]")
_DESIGN_BOX = re.compile(r"\[(\d+)\]")

#: One filing context per revision that carries the promotor's autoconsumo base.
_AUTOCONSUMO_CONTEXTS: tuple[tuple[int, str], ...] = (
    (2022, "1T"),
    (2023, "1T"),
    (2024, "1T"),
    (2024, "3T"),
    (2025, "1T"),
    (2026, "1T"),
)

#: The editions that state the printed-total predicate; every other edition inherits it.
_DECLARING_EDITIONS = ("2022", "2023", "2024-desde-09-y-3t")

_GENERAL_CUOTA = Decimal("2100.00")
_AUTOCONSUMO_BASE = Decimal("1000.00")
#: LIVA art. 90.Uno: the general rate applies to the autoconsumo base (art. 79.Cuatro).
_STATUTORY_GENERAL_RATE = Decimal("0.21")
_AUTOCONSUMO_CUOTA = _AUTOCONSUMO_BASE * _STATUTORY_GENERAL_RATE
#: An amount the mutated total adds outside every printed box.
_UNPRINTED_AMOUNT = Decimal("210.00")


def _design_addends(revision: ModeloRevision, catalogues: RegistryCatalogues) -> tuple[str, ...]:
    """Read [27]'s addends from the record design the revision's casillas are grounded in."""
    assert revision.casilla_source_refs is not None, f"{revision.id}: casillas cite no record design"
    (source_ref,) = revision.casilla_source_refs
    extracted = bundled_path() / f"{catalogues.sources[source_ref].corpus_path}.extracted.md"
    rows = [
        match
        for line in extracted.read_text(encoding="utf-8").splitlines()
        if (match := _DESIGN_TOTAL_ROW.search(line))
    ]
    assert len(rows) == 1, f"{source_ref}: expected one [27] total row in {extracted.name}, found {len(rows)}"
    addends = tuple(str(box) for box in _DESIGN_BOX.findall(rows[0].group("addends")))
    assert len(addends) >= 2, f"{source_ref}: the [27] row names no addends"
    return addends


def _printed_total_predicate(revision: ModeloRevision) -> VerificationPredicateDefinition | None:
    matches = []
    for predicate in revision.verification_predicates:
        parsed = parse_verification_predicate_expression(predicate.expression)
        if (
            parsed is not None
            and parsed.operator is VerificationPredicateOperator.EQUALS_SUM
            and parsed.casilla_ids[0] == _TOTAL_BOX
        ):
            matches.append(predicate)
    assert len(matches) <= 1, f"{revision.id}: more than one printed-total predicate for [27]"
    return matches[0] if matches else None


def _declared_addends(revision: ModeloRevision) -> tuple[str, ...] | None:
    predicate = _printed_total_predicate(revision)
    if predicate is None:
        return None
    parsed = parse_verification_predicate_expression(predicate.expression)
    assert parsed is not None
    return parsed.casilla_ids[1:]


def _design_parity_failures(modelo: ModeloDefinition, catalogues: RegistryCatalogues) -> list[str]:
    failures: list[str] = []
    for revision in modelo.revisions.values():
        declared = _declared_addends(revision)
        expected = _design_addends(revision, catalogues)
        if declared != expected:
            failures.append(f"{revision.id}: declares {declared!r}, its design adds {expected!r}")
            continue
        predicate = _printed_total_predicate(revision)
        assert predicate is not None
        if predicate.finding_kind != "BLOCKING_RULE":
            failures.append(f"{revision.id}: the printed-total predicate is {predicate.finding_kind}, not blocking")
        casillas = {casilla.id for casilla in revision.casillas}
        failures.extend(
            f"{revision.id}: [{box}] is not a casilla of the revision" for box in declared if box not in casillas
        )
    return failures


def _calculated_findings(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    filing_year: int,
    period: str,
    general_cuota: Decimal,
    autoconsumo_base: Decimal | None,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
) -> tuple[str, dict[CasillaId, Decimal], list[ModeloVerificationFinding]]:
    """Calculate one filing through the real engine and evaluate its revision's predicates."""
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period=period)
    revision = snapshot.revision
    # Every money binding states its fact, so an absent ledger contribution is a
    # stated zero rather than a missing input.
    binding_values: dict[str, Decimal] = {binding.id: Decimal("0") for binding in revision.bindings}
    binding_values[_ATTRIBUTION_RATIO_BINDING] = Decimal("100")
    binding_values[_GENERAL_CUOTA_BINDING] = general_cuota
    if autoconsumo_base is not None:
        binding_values[_AUTOCONSUMO_BASE_BINDING] = autoconsumo_base
    inputs = {**resolve_available_bound_inputs_by_casilla_id(revision, binding_values), **(casilla_inputs or {})}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 3, 31)},
    )
    values = dict(result.values)
    findings = evaluate_verification_predicates(tuple(revision.verification_predicates), values, workflow_profile())
    return revision.id, values, findings


def _blocking(findings: list[ModeloVerificationFinding]) -> list[ModeloVerificationFinding]:
    return [finding for finding in findings if finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE]


def _transcribed_general_box(
    modelo: ModeloDefinition, catalogues: RegistryCatalogues, *, filing_year: int, period: str, amount: Decimal
) -> dict[CasillaId, Decimal]:
    """The filer's transcription of [09] in an edition that prints it as a manual box."""
    revision = build_snapshot(
        modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period=period
    ).revision
    (box,) = (casilla for casilla in revision.casillas if casilla.id == _GENERAL_CUOTA_BOX)
    return {_GENERAL_CUOTA_BOX: amount} if box.input_kind is InputKind.MANUAL else {}


def _add_unprinted_amount_to_total(modelo_directory: Path) -> None:
    """Make the devengado total add an amount no printed box shows.

    The amount is folded into the total's first addend, so every successor's
    sequence override of the addend list still applies and every edition
    inherits the defect.
    """
    mutate_declaration(
        modelo_directory,
        revision_id="2022",
        section="formulas",
        member=_TOTAL_FORMULA,
        find='[[revisions.2022.formulas.expression.args]]\ncasilla_id = "iva.cuota-devengada.general"\n',
        replace=(
            "[[revisions.2022.formulas.expression.args]]\n"
            'op = "add"\n'
            f'args = [{{ casilla_id = "iva.cuota-devengada.general" }}, {{ literal = "{_UNPRINTED_AMOUNT}" }}]\n'
        ),
    )


@pytest.fixture(scope="module")
def unprinted_amount_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A scratch registry whose devengado total adds an amount no printed box shows."""
    scratch_root = scratch_registry_tree(tmp_path_factory.mktemp("unprinted"), "303")
    _add_unprinted_amount_to_total(scratch_root / "modelos" / "303")
    return scratch_root


def _loaded_303(registry_root: Path) -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(registry_root)
    return next(modelo for modelo in modelos if modelo.id == "303"), catalogues


def test_every_revision_checks_its_own_design_addends_at_blocking_severity() -> None:
    modelo, catalogues = load_modelo_303()

    assert len(modelo.revisions) >= 2
    assert _design_parity_failures(modelo, catalogues) == []


def test_the_autoconsumo_contexts_cover_every_revision_that_carries_the_autoconsumo_base() -> None:
    modelo, catalogues = load_modelo_303()
    carrying = {
        revision.id
        for revision in modelo.revisions.values()
        if any(binding.id == _AUTOCONSUMO_BASE_BINDING for binding in revision.bindings)
    }
    selected = {
        build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=year, period=period).revision.id
        for year, period in _AUTOCONSUMO_CONTEXTS
    }

    assert carrying
    assert selected == carrying


@pytest.mark.parametrize(("filing_year", "period"), _AUTOCONSUMO_CONTEXTS)
def test_an_autoconsumo_base_stated_at_the_general_rate_lands_in_the_printed_boxes(
    filing_year: int, period: str
) -> None:
    modelo, catalogues = load_modelo_303()
    printed_general = _GENERAL_CUOTA + _AUTOCONSUMO_CUOTA
    revision_id, values, findings = _calculated_findings(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        general_cuota=_GENERAL_CUOTA,
        autoconsumo_base=_AUTOCONSUMO_BASE,
        casilla_inputs={
            _AUTOCONSUMO_GENERAL_BASE: _AUTOCONSUMO_BASE,
            **_transcribed_general_box(
                modelo, catalogues, filing_year=filing_year, period=period, amount=printed_general
            ),
        },
    )

    assert values[_GENERAL_CUOTA_BOX] == printed_general, revision_id
    assert values[_TOTAL_BOX] == printed_general, revision_id
    assert _blocking(findings) == [], revision_id


@pytest.mark.parametrize(("filing_year", "period"), _AUTOCONSUMO_CONTEXTS)
def test_an_autoconsumo_base_not_stated_per_rate_is_refused_not_left_out(filing_year: int, period: str) -> None:
    modelo, catalogues = load_modelo_303()
    revision_id, values, findings = _calculated_findings(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        general_cuota=_GENERAL_CUOTA,
        autoconsumo_base=_AUTOCONSUMO_BASE,
        casilla_inputs=_transcribed_general_box(
            modelo, catalogues, filing_year=filing_year, period=period, amount=_GENERAL_CUOTA
        ),
    )

    # The rate-less base reaches no rate row, so [27] still adds up to its printed boxes ...
    assert values[_TOTAL_BOX] == _GENERAL_CUOTA, revision_id
    # ... and the declaration is refused rather than filed without the autoconsumo cuota.
    assert [finding.message_facts["predicate_id"] for finding in _blocking(findings)] == [_RATE_SPLIT_PREDICATE], (
        revision_id
    )


@pytest.mark.parametrize(("filing_year", "period"), _AUTOCONSUMO_CONTEXTS)
def test_an_amount_the_total_adds_outside_the_printed_boxes_refuses_with_the_printed_sum(
    unprinted_amount_tree: Path, filing_year: int, period: str
) -> None:
    mutant, catalogues = _loaded_303(unprinted_amount_tree)
    revision_id, values, findings = _calculated_findings(
        mutant,
        catalogues,
        filing_year=filing_year,
        period=period,
        general_cuota=_GENERAL_CUOTA,
        autoconsumo_base=Decimal("0"),
        casilla_inputs=_transcribed_general_box(
            mutant, catalogues, filing_year=filing_year, period=period, amount=_GENERAL_CUOTA
        ),
    )

    assert values[_GENERAL_CUOTA_BOX] == _GENERAL_CUOTA, revision_id
    assert values[_TOTAL_BOX] == _GENERAL_CUOTA + _UNPRINTED_AMOUNT, revision_id

    blocking = _blocking(findings)
    assert len(blocking) == 1, (revision_id, findings)
    (finding,) = blocking
    assert finding.message_locale_key == _PRINTED_TOTAL_MISMATCH
    assert finding.casilla_id == _TOTAL_BOX
    assert finding.message_facts["box"] == "27"
    # [09] is the only printed box carrying an amount, so it is the printed sum.
    assert finding.message_facts["printed_sum"] == _GENERAL_CUOTA


@pytest.mark.parametrize(("filing_year", "period"), _AUTOCONSUMO_CONTEXTS)
def test_the_same_declaration_without_autoconsumo_raises_no_blocking_finding(filing_year: int, period: str) -> None:
    modelo, catalogues = load_modelo_303()
    revision_id, values, findings = _calculated_findings(
        modelo,
        catalogues,
        filing_year=filing_year,
        period=period,
        general_cuota=_GENERAL_CUOTA,
        autoconsumo_base=Decimal("0"),
        casilla_inputs=_transcribed_general_box(
            modelo, catalogues, filing_year=filing_year, period=period, amount=_GENERAL_CUOTA
        ),
    )

    assert values[_TOTAL_BOX] == _GENERAL_CUOTA, revision_id
    assert _blocking(findings) == [], revision_id


def test_the_check_is_general_and_refuses_an_untranscribed_2022_box() -> None:
    """2022 prints [09] as a manual box, so a ledger cuota left untranscribed is unprinted too."""
    modelo, catalogues = load_modelo_303()

    revision_id, values, findings = _calculated_findings(
        modelo, catalogues, filing_year=2022, period="1T", general_cuota=_GENERAL_CUOTA, autoconsumo_base=None
    )
    assert revision_id == "2022"
    assert values[_TOTAL_BOX] == _GENERAL_CUOTA
    assert [(f.message_locale_key, f.message_facts["printed_sum"]) for f in _blocking(findings)] == [
        (_PRINTED_TOTAL_MISMATCH, Decimal("0")),
    ]

    _, _, transcribed = _calculated_findings(
        modelo,
        catalogues,
        filing_year=2022,
        period="1T",
        general_cuota=_GENERAL_CUOTA,
        autoconsumo_base=None,
        casilla_inputs={_GENERAL_CUOTA_BOX: _GENERAL_CUOTA},
    )
    assert _blocking(transcribed) == []


def _remove_declaration(modelo_directory: Path, edition: str, predicate: VerificationPredicateDefinition) -> None:
    refs = ", ".join(f'"{ref}"' for ref in predicate.legal_refs)
    fragment = mutate_declaration(
        modelo_directory,
        revision_id=edition,
        section="verification_predicates",
        find=(
            f"[[revisions.{edition}.verification_predicates]]\n"
            f'id = "{predicate.id}"\n'
            f'predicate_id = "{predicate.predicate_id}"\n'
            f"expression = '{predicate.expression}'\n"
            f"legal_refs = [{refs}]\n"
        ),
        replace="",
    )
    # An edition whose only declaration this was had no section before it; the
    # loader refuses both a fragment declaring no revision table and an empty
    # section directory.
    if not tomllib.loads(fragment.path.read_text(encoding="utf-8")):
        fragment.path.unlink()
        if not any(fragment.path.parent.iterdir()):
            fragment.path.parent.rmdir()


def test_mutation_removing_the_predicate_lets_the_unprinted_total_through(tmp_path: Path) -> None:
    bundled, _ = load_modelo_303()
    scratch_root = scratch_registry_tree(tmp_path, "303")
    _add_unprinted_amount_to_total(scratch_root / "modelos" / "303")
    for edition in _DECLARING_EDITIONS:
        predicate = _printed_total_predicate(bundled.revisions[edition])
        assert predicate is not None
        _remove_declaration(scratch_root / "modelos" / "303", edition, predicate)

    mutant, catalogues = _loaded_303(scratch_root)
    assert all(_printed_total_predicate(revision) is None for revision in mutant.revisions.values())

    revision_id, values, findings = _calculated_findings(
        mutant,
        catalogues,
        filing_year=2025,
        period="1T",
        general_cuota=_GENERAL_CUOTA,
        autoconsumo_base=Decimal("0"),
    )
    # The defect is still there, and with the predicate gone nothing refuses it:
    # the binary [27] == iva.cuota-devengada-total predicate holds by construction.
    assert revision_id == "2025"
    assert values[_TOTAL_BOX] == _GENERAL_CUOTA + _UNPRINTED_AMOUNT
    assert values[_GENERAL_CUOTA_BOX] == _GENERAL_CUOTA
    assert _blocking(findings) == []


def test_mutation_dropping_a_design_addend_breaks_design_parity(tmp_path: Path) -> None:
    scratch_root = scratch_registry_tree(tmp_path, "303")
    mutate_declaration(
        scratch_root / "modelos" / "303",
        revision_id="2024-desde-09-y-3t",
        section="verification_predicates",
        member='id = "equals-sum:dr303-27-equals-printed-summands"',
        find='"24", "26"])',
        replace='"24"])',
    )

    modelos, catalogues = load_registry_tree(scratch_root)
    mutant = next(modelo for modelo in modelos if modelo.id == "303")
    failures = _design_parity_failures(mutant, catalogues)

    # The edition stating the list and the two that inherit it all diverge from their designs.
    assert sorted(failure.split(":", 1)[0] for failure in failures) == [
        "2024-desde-09-y-3t",
        "2025",
        "2026-y-siguientes",
    ]
