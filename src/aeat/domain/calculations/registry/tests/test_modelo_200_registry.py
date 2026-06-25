"""Modelo 200 registry behaviour backed by official source corpus."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from html import unescape

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator, build_snapshot, calculate_registry_snapshot, load_registry_tree, resolve_export_layout
from .._errors import RegistryValidationError
from .._runtime_graph import expression_casilla_refs
from .._schema import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


@lru_cache(maxsize=1)
def _load_modelo_200():
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "200")
    return modelo, catalogues


def test_modelo_200_validates_with_deadline_and_schedule_catalogue_refs() -> None:
    modelo, catalogues = _load_modelo_200()

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )
    construct = snapshot.revision.constructs[0]
    assert construct.filing_schedules == ("modelo-200-2024-anual",)
    assert construct.deadline_windows == ("modelo-200-2024-0a",)
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "review",
        "verification",
        "approval",
        "reconciliation",
        "deadline",
        "portal",
        "workflow",
    } <= linked_surfaces


def test_modelo_200_calendar_year_2024_deadline_matches_boe_order() -> None:
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    window = snapshot.revision.deadline_windows[0]
    source = catalogues.sources["boe-modelo-200-2025-form"]
    source_text = _normalized_text((bundled_path() / source.corpus_path).read_text(encoding="utf-8"))

    assert "modelo 200 de declaracion del impuesto sobre sociedades" in source_text
    assert "25 dias naturales siguientes a los seis meses posteriores" in source_text
    assert "desde el dia 1 de julio hasta el 22 de julio de 2025" in source_text
    assert window.opens_on == date(2025, 7, 1)
    assert window.closes_on == date(2025, 7, 25)
    assert window.payment_cutoff_on == date(2025, 7, 22)


def test_modelo_200_schedule_is_annual_for_calendar_year_entities() -> None:
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    schedule = snapshot.revision.filing_schedules[0]
    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert snapshot.revision.period_selector.periods == ("0A",)


def test_modelo_200_liquidacion_cuota_chain_casillas_resolve_under_their_segmento() -> None:
    """The Liquidación cuota-chain casillas resolve under their DP200014 / DP200014B segmento.

    The segment-scoped casilla identity model lets Modelo 200 declare its
    Liquidación III / IV cuota-chain casillas under the AEAT record
    segments that carry them, distinct from the ECPN occurrences of the
    same five-digit numbers. This test resolves each cuota-chain casilla
    by its composed `(segmento:number)` id on the built snapshot and
    asserts it carries the expected `segmento` and bare `number`:
    `00552`, `00558`, `00562` in the Liquidación III segment `DP200014`
    and `00592`, `00599`, `00611` in the Liquidación IV segment
    `DP200014B`. It also asserts each is grounded with `legal_refs` and
    `source_refs`, the calculation-grounding contract.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    casilla_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    expected = {
        "DP200014:00552": ("DP200014", "00552"),
        "DP200014:00558": ("DP200014", "00558"),
        "DP200014:00562": ("DP200014", "00562"),
        "DP200014:00582": ("DP200014", "00582"),
        "DP200014B:00592": ("DP200014B", "00592"),
        "DP200014B:00599": ("DP200014B", "00599"),
        "DP200014B:00611": ("DP200014B", "00611"),
        "DP200014B:00619": ("DP200014B", "00619"),
    }
    for casilla_id, (segmento, number) in expected.items():
        casilla = casilla_by_id.get(casilla_id)
        assert casilla is not None, (
            f"Liquidación cuota-chain casilla {casilla_id!r} must resolve on the "
            "Modelo 200 snapshot under its segment-scoped identity"
        )
        assert casilla.segmento == segmento
        assert casilla.number == number
        assert casilla.legal_refs, f"casilla {casilla_id!r} must carry legal_refs grounding"
        assert casilla.source_refs, f"casilla {casilla_id!r} must carry source_refs grounding"


def test_modelo_200_page_014_export_binding_resolves_00562_to_liquidacion() -> None:
    """The page-014 export binding resolves casilla 00562 to the Liquidación occurrence.

    Modelo 200 reuses the five-digit number `00562` across record
    segments: it is the Liquidación III cuota íntegra in segment
    `DP200014` and a distribución-de-dividendos field in the ECPN
    segment. The page-014 fichero-BOE export field for `00562` must bind
    the Liquidación cuota íntegra, not the ECPN occurrence. This resolves
    the export layout on the built snapshot and asserts the
    `modelo-200-page-014-casilla-00562` field's bound casilla is the
    Liquidación `DP200014:00562` identity.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    layout = resolve_export_layout(snapshot, "modelo-200-fichero-boe")
    page_014_field = layout.fields_by_id.get("modelo-200-page-014-casilla-00562")

    assert page_014_field is not None, (
        "the Modelo 200 fichero-BOE layout must carry the page-014 export field for casilla 00562"
    )
    assert page_014_field.casilla == "DP200014:00562", (
        "the page-014 export binding for 00562 must resolve to the Liquidación "
        f"DP200014 occurrence, not the ECPN one; got {page_014_field.casilla!r}"
    )

    liquidacion_casilla = next((c for c in snapshot.revision.casillas if c.id == page_014_field.casilla), None)
    assert liquidacion_casilla is not None
    assert liquidacion_casilla.segmento == "DP200014"
    assert liquidacion_casilla.number == "00562"


def test_modelo_200_liquidacion_014_014b_formulas_and_exports_use_segment_identities() -> None:
    """Liquidación III/IV formulas and BOE fields cannot bind reused bare ECPN numbers."""
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    formulas_by_target = {formula.target: formula for formula in snapshot.revision.formulas}
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}

    assert casillas_by_id["DP200014:00582"].input_kind == InputKind.COMPUTED
    assert casillas_by_id["DP200014:00582"].formula == "modelo-200-cuota-integra-ajustada-positiva"
    assert casillas_by_id["DP200014B:00592"].input_kind == InputKind.COMPUTED
    assert casillas_by_id["DP200014B:00592"].formula == "modelo-200-cuota-liquida"

    ajustada_refs = set(expression_casilla_refs(formulas_by_target["DP200014:00582"].expression))
    assert {
        "DP200014:00562",
        "DP200014:00567",
        "DP200014:00568",
        "DP200014:00563",
        "DP200014:00566",
        "DP200014:00576",
        "DP200014:00569",
        "DP200014:00570",
        "DP200014:00572",
        "DP200014:00571",
        "DP200014:00575",
        "DP200014:00577",
        "DP200014:00581",
    } <= ajustada_refs
    assert not {
        "00567",
        "00568",
        "00563",
        "00566",
        "00576",
        "00569",
        "00570",
        "00572",
        "00571",
        "00575",
        "00577",
        "00581",
        "00582",
    } & ajustada_refs

    liquida_refs = set(expression_casilla_refs(formulas_by_target["DP200014B:00592"].expression))
    assert {
        "DP200014:00582",
        "DP200014B:00619",
        "DP200014B:00583",
        "DP200014B:00585",
        "DP200014B:00584",
        "DP200014B:00588",
        "DP200014B:00565",
        "DP200014B:00590",
        "DP200014B:00399",
        "DP200014B:00082",
    } <= liquida_refs
    assert not {
        "00582",
        "00619",
        "00583",
        "00585",
        "00584",
        "00588",
        "00565",
        "00590",
        "00399",
        "00082",
    } & liquida_refs

    layout = resolve_export_layout(snapshot, "modelo-200-fichero-boe")
    expected_exports = {
        "modelo-200-page-014-casilla-00567": "DP200014:00567",
        "modelo-200-page-014-casilla-00568": "DP200014:00568",
        "modelo-200-page-014-casilla-00563": "DP200014:00563",
        "modelo-200-page-014-casilla-00566": "DP200014:00566",
        "modelo-200-page-014-casilla-00576": "DP200014:00576",
        "modelo-200-page-014-casilla-00569": "DP200014:00569",
        "modelo-200-page-014-casilla-00570": "DP200014:00570",
        "modelo-200-page-014-casilla-00572": "DP200014:00572",
        "modelo-200-page-014-casilla-00571": "DP200014:00571",
        "modelo-200-page-014-casilla-00575": "DP200014:00575",
        "modelo-200-page-014-casilla-00577": "DP200014:00577",
        "modelo-200-page-014-casilla-00581": "DP200014:00581",
        "modelo-200-page-014-casilla-00582": "DP200014:00582",
        "modelo-200-page-014b-casilla-00583": "DP200014B:00583",
        "modelo-200-page-014b-casilla-00585": "DP200014B:00585",
        "modelo-200-page-014b-casilla-00584": "DP200014B:00584",
        "modelo-200-page-014b-casilla-00588": "DP200014B:00588",
        "modelo-200-page-014b-casilla-00565": "DP200014B:00565",
        "modelo-200-page-014b-casilla-00590": "DP200014B:00590",
        "modelo-200-page-014b-casilla-00399": "DP200014B:00399",
        "modelo-200-page-014b-casilla-00082": "DP200014B:00082",
        "modelo-200-page-014b-casilla-00619": "DP200014B:00619",
    }
    actual_exports = {field_id: layout.fields_by_id[field_id].casilla for field_id in expected_exports}
    assert actual_exports == expected_exports


def test_modelo_200_page_14_cuota_chain_matches_aeat_manual_worked_example() -> None:
    """The page-14 cuota chain evaluates to the AEAT manual's worked-example oracle.

    The Manual práctico de Sociedades 2024 carries a fully worked
    liquidación example ("Liquidación del IS 2024 sin tributación
    mínima", manual pages 399 and 401). For a company tributing
    exclusively to the Administración del Estado it publishes these
    figures on the cuota chain:

    - cuota líquida ``00592`` = 0
    - retenciones e ingresos a cuenta ``01766`` = 20.000
    - **cuota del ejercicio a ingresar o a devolver ``00599`` = -20.000**
    - pagos fraccionados (sum of ``00601`` / ``00603`` / ``00605``) = 10.000
    - **cuota diferencial ``00611`` = -30.000**

    The two bold figures are AEAT-published oracle values lifted
    verbatim from the manual table — they are *not* recomputed by the
    test author from the registry formula, so this satisfies the
    no-tautological-calculation-tests rule: the test fails if the
    registry formula diverges from the AEAT manual.

    The retenciones and pagos-fraccionados amounts hold their positive
    values; the manual table renders the subtracted items with a
    leading minus as a display convention. The registry formula
    ``00599 = (00625 / 100) x (00592 - 01766 - 01784)`` and
    ``00611 = 00599 - pagos_fraccionados`` produce the signed results.
    Pagos fraccionados ``(00601 + 00603 + 00605)`` are sourced from the
    company's Modelo 202 instalment filings and reach Modelo 200 through
    the ``modelo-200-2024-rel-202-pagos-fraccionados`` cross-model
    relation, which aggregates the 1P/2P/3P instalments; the worked
    example's 10.000 pagos fraccionados is supplied as that relation's
    resolved value.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "00501": Decimal("0"),
            "DP200014:01033": Decimal("0"),
            "DP200014:01034": Decimal("0"),
            "DP200014B:01766": Decimal("20000"),
            "DP200014B:01784": Decimal("0"),
        },
        enum_binding_values={"modelo-200-2024-profile-legal-entity-form": "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("10000"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
    )

    assert result.values["DP200014B:00599"] == Decimal("-20000.00"), (
        "cuota del ejercicio 00599 must equal the AEAT manual worked-example oracle of -20.000 (manual pages 399/401)"
    )
    assert result.values["DP200014B:00611"] == Decimal("-30000.00"), (
        "cuota diferencial 00611 must equal the AEAT manual worked-example oracle of -30.000 (manual pages 399/401)"
    )


def test_modelo_200_carries_manual_handoff_under_declaration_advisory_predicates() -> None:
    """The M200 2024 revision guards the remaining manual handoffs in the IS result chain.

    The IS determination flows through operator-entered manual casillas at two
    stages where a positive upstream value can silently produce a zero downstream
    one (`no-silent-under-declaration`):

    - ``00500`` (resultado contable, after-tax) → ``00501`` (resultado antes de IS)
    - ``00501`` (resultado antes de IS) → ``DP200014:00552`` (base imponible)

    Each remaining manual transition is guarded by an ADVISORY
    ``implies_nonzero`` predicate so a positive accounting profit cannot silently
    grant VERIFICADO_COMPLETO with a zero fiscal base. The earliest guard
    (00500→00501) is what catches the
    operator who declares a profit but leaves the fiscal-base starting point at
    zero — a case the 00501→00552 advisory cannot catch because 00501 is *its*
    antecedent. The cuota stage is now formula-owned, so a stale advisory there
    would be a false green signal and must not reappear.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    predicates = {p.predicate_id: p.expression for p in snapshot.revision.verification_predicates}
    expected = {
        "modelo-200-resultado-antes-impuesto-determinado-cuando-resultado-contable-positivo": (
            'implies_nonzero(["00500", "00501"])'
        ),
        "modelo-200-base-imponible-determinada-cuando-resultado-positivo": (
            'implies_nonzero(["00501", "DP200014:00552"])'
        ),
    }
    for predicate_id, expression in expected.items():
        assert predicates.get(predicate_id) == expression, (
            f"M200 2024 must guard the IS-chain handoff {predicate_id!r} with {expression!r} "
            "(no-silent-under-declaration): a positive upstream value with a zero downstream "
            "one must surface an operator-facing advisory"
        )
    for predicate_id in expected:
        guard = next(p for p in snapshot.revision.verification_predicates if p.predicate_id == predicate_id)
        assert guard.finding_kind == "ADVISORY", (
            f"{predicate_id} must stay non-blocking: a legitimately zero downstream "
            "(losses, full deductions) must not refuse the draft"
        )
    assert "modelo-200-cuota-liquida-determinada-cuando-cuota-integra-positiva" not in predicates


def test_modelo_200_cuota_liquida_is_computed_and_rejects_direct_input() -> None:
    """DP200014B:00592 is formula-owned; direct operator input fails fast."""
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    assert casillas_by_id["DP200014:00582"].input_kind == InputKind.COMPUTED
    assert casillas_by_id["DP200014B:00592"].input_kind == InputKind.COMPUTED

    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied as inputs"):
        calculate_registry_snapshot(
            snapshot,
            inputs={"DP200014B:00592": Decimal("0")},
            enum_binding_values={"modelo-200-2024-profile-legal-entity-form": "sl"},
            binding_values={
                "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
                "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
                "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            },
            relation_values={
                "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
                "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
            },
            date_context={"filing_period": date(2024, 12, 31)},
        )


def test_modelo_200_cuota_integra_chain_applies_dispatched_rate_to_post_nivelacion_base() -> None:
    """The cuota íntegra chain applies the entity-type-dispatched rate to the post-nivelación base.

    The Manual práctico de Sociedades 2024 worked example (page 401)
    carries a base imponible después de la reserva de nivelación
    ``01330`` of 1.000.000 at a 25% tipo de gravamen yielding a cuota
    íntegra ``00562`` of 250.000. This exercises three cuota-chain
    formulas — ``01330 = 00552 + 01033 - 01034`` (manual page 361),
    ``00558`` selected from the LIS Art. 29 tipo de gravamen by the
    taxpayer's legal form via the ``modelo-200-tipo-gravamen-por-forma-
    juridica`` dispatch, and ``00562 = 01330 x 00558 / 100`` (manual
    page 362) — against those published figures.

    The ``legal_entity_form`` enum binding is supplied as ``sl`` (a
    sociedad de responsabilidad limitada). A sociedad de capital is
    taxed at the LIS Art. 29 general rate, so the dispatch resolves
    ``00558`` to the registry's ``is.modelo-200.tipo-gravamen-general``
    value (25); the cuota íntegra then matches the manual oracle.

    The expected outputs are read from the manual table, not recomputed
    by the test author, so the test fails if the registry formula or the
    rate dispatch diverges from the AEAT manual.
    """
    modelo, catalogues = _load_modelo_200()
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2024,
        period="0A",
    )

    # The base imponible 00552 is now COMPUTED from the base-determination
    # chain, so it is no longer supplied directly. Feeding the resultado
    # contable 00501 = 1.000.000 with zero correcciones, zero reserva de
    # capitalización and zero compensación BIN makes the chain compute
    # 00550 = 1.000.000 and 00552 = 1.000.000, reproducing the manual
    # worked-example base that the post-nivelación and cuota chain consume.
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "00501": Decimal("1000000"),
            "DP200014:01033": Decimal("0"),
            "DP200014:01034": Decimal("0"),
            "DP200014B:01766": Decimal("0"),
            "DP200014B:01784": Decimal("0"),
        },
        enum_binding_values={"modelo-200-2024-profile-legal-entity-form": "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
    )

    assert result.values["DP200014:00558"] == Decimal("25"), (
        "tipo de gravamen 00558 must be dispatched to the LIS Art. 29 general rate (25) for a sociedad limitada"
    )
    assert result.values["DP200014:01330"] == Decimal("1000000.00"), (
        "base imponible después de la reserva de nivelación 01330 must equal "
        "the AEAT manual worked-example figure of 1.000.000 (manual page 401)"
    )
    assert result.values["DP200014:00562"] == Decimal("250000.00"), (
        "cuota íntegra 00562 must equal the AEAT manual worked-example figure of 250.000 (manual page 401)"
    )


def _normalized_text(value: str) -> str:
    return (
        unescape(value)
        .replace("\xa0", " ")
        .replace("\u2003", " ")
        .casefold()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
