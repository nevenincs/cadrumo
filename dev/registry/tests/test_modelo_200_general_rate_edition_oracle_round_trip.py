"""The last Modelo 200 edition before the flat 23 % reduced rate calculates the manual's worked examples and files them.

Until Ley 31/2022 art. 39 gave LIS art. 29.1 a 23 % rate for an importe neto de
la cifra de negocios (INCN) of the preceding period below 1 millon de euros,
the cuota integra of an ordinary entity applied the tipo general to the base,
whatever its INCN. The exercise tested here is the newest bundled Manual
practico de Sociedades that prints the "Cuota liquida minima (casilla 00619)"
supuestos practicos below and does not yet print the reduced rate; it is read
from the bundled manuals and its Modelo 200 revision from the registry, so no
year is named.

Each scenario builds a draft from the figures one of the manual's worked
examples states through the canonical draft builder, compares the calculated
boxes with the values that example prints, exports the draft through the
edition's own fixed-width layout, parses the bytes back through the registry
codec and compares every oracle box again. An edition without its own
fixed-width layout fails at the export half: it calculates but does not file.

Oracle source: the manual's chapter 6, "Cuota liquida minima (casilla 00619)",
"Supuestos practicos" (printed pages 351-364; line numbers of
``corpus/manuals/sociedades/<edition>/source.pdf.extracted.md`` for the edition
selected). Each example is a sociedad whose INCN in the twelve months before
the period "supero los 20 millones de euros" and that "tributa al tipo general
de gravamen del 25 por ciento"; each prints its liquidacion box by box:

    Ejemplo 1, L14152-14287 (pp. 351-355): base imponible 2.000.000; deduccion
      doble imposicion internacional [00573] 150.000. Without the minimum
      (L14190-14211): [00588] 80.000, [00619] 0, [00582] 350.000, [00592]
      270.000, [01586] 270.000. With the minimum (L14262-14287): [00588]
      50.000, [00619] 300.000, [00592] 300.000, [01586] 300.000.
    Ejemplo 2, L14288-14394 (pp. 355-358), without the minimum (L14361-14394):
      base imponible 1.000.000; [00562] 250.000; bonificacion Ceuta y Melilla
      [00567] 20.000; [00573] 10.000; [00582] 220.000; [00588] 110.000;
      [02315] 90.000; [00082] 20.000; [00619] 0; [00592] 0; retenciones
      [01766] 20.000; [00599] -20.000; pagos fraccionados 10.000; [00611]
      -30.000.
    Ejemplo 2, with the minimum (L14395-14481, pp. 358-360): the cuota liquida
      minima "sera de 130.000 euros" (L14435, art. 30 bis.2.a: [00562]
      250.000 less the bonificacion 20.000, the art. 38 bis deduction [02315]
      90.000 and the doble imposicion 10.000), below the 150.000 of art. 30
      bis.1; the restantes deducciones get nothing ([00588] 0, 250.000
      pendiente), while the art. 39.2 I+D+i deduction "no se ve afectada por el
      importe de la cuota liquida minima" (L14441-14442) and is applied in full
      ([00082] 130.000). The final liquidacion (L14448-14481) prints [00582]
      220.000, [02315] 90.000, [00082] 130.000, [00592] 0, [01766] 20.000,
      [00599] -20.000, pagos fraccionados 10.000 and [00611] -30.000: the cuota
      liquida falls below the minimum. The same table prints the box [00619]
      as 0 although the text states the minimum as 130.000; the scenario
      consigns the 130.000 the text states, so a cuota liquida floored at
      [00619] reads 130.000 and fails, and every oracle box is the same with
      either value.
    Ejemplo 3, L14482-14622 (pp. 360-364), with the minimum (L14604-14622):
      base imponible 2.000.000; [00573] 45.000; [00582] 455.000; [00588]
      30.000; [00619] 300.000; [00592] 425.000, the cuota liquida exceeding the
      minimum it is compared with.

Each printed box is also the operation the same manual states for it:

    L6918 (p. 183) "[00550] = [00501] + ([00417] - [00418])".
    L12517 (p. 312) "[00552] = [00550] - [01032] - [00547]".
    L12974 (p. 323) "casilla [01330] = [00552] + [01033] - [01034]"; L22827-22828
      (p. 563) without [01033] and [01034] "el importe de la casilla [01330]
      coincidira con el de la casilla [00552]".
    L13043 (p. 325) "Tipo general 25 por 100" in the "Tipos de gravamen
      vigentes" table, which prints no rate keyed to the INCN.
    L13033 (p. 325) "[00562] = [00552] x [00558]/100"; L23136 (p. 572) "[00562]
      = [01330] x [00558] / 100"; L13035 positive or zero.
    L13155-13156 (p. 328) "[00582] = ([00562] + [01038]) - ([00567] + ... +
      [00573] + ...)"; L13158 a negative result is consigned as zero.
    L14639-14640 (p. 365) "[00592] = [00582] - (... + [00588] + ... + [02315] +
      ... + [00082] + ...)"; L14641 positive or zero. Its operands are the
      deducciones "aplicadas por el contribuyente en el periodo impositivo"
      (L14635-14637), so art. 30 bis enters through the amounts consigned, not
      as a floor: the restantes deducciones apply "hasta el importe de dicha
      cuota liquida minima" (L14138-14140), the Canarias deductions "aunque la
      cuota liquida resultante sea inferior a la mencionada cuota liquida
      minima" (L14141-14145), and the art. 39.2 deduction is not affected
      (L14441-14442).
    L18509 (p. 457) "[00599] = ([00625]/100]) x ([00592] - [01766] - [01784])".
    L18730 (p. 462) "[00611] = [00599] - ([00601] + [00603] + [00605])";
      L18748-18749 (p. 463) the three boxes carry the primer, segundo and tercer
      pago fraccionado.

What the examples leave unstated is supplied as the plainest fact consistent
with them, and no oracle box depends on it: the result is the base imponible
the example states, with no correcciones ([00417] = [00418] = 0), because
each prints [00550] equal to the resultado [00500]; no reserva de
capitalizacion, compensation or reserva de nivelacion, as each prints them as
0; a common-regime entity taxed by the State alone ([00625] = 100), as each
liquidacion is the State's; a sociedad anonima that is not of new creation, as
each applies the tipo general; no bases imponibles negativas pending, so the
twelve-month INCN the DA 15a limits read (stated as 25.000.000, above the 20
millones each example names) bounds nothing; Ejemplo 2's pagos fraccionados
as the first instalment, since [00611] reads only their sum; and retenciones
of 0 where an example prints none, as its [01586] equals its cuota liquida.

None of these values was read from a run of the registry formulas.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal

import pytest

from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.export import export_draft
from cadrumo.application.filing.export_verification import FilingExportValidatedPayload
from cadrumo.application.filing.runtime import ModeloOperatorProfile, schema_provider_from_authority
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_indexed_authority
from cadrumo.domain.calculations.registry.export_parse import parse_export_payload
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from cadrumo.domain.filing.protocols import ModeloInputs
from cadrumo.domain.submission.models import ModeloDraftStatus
from dev.registry.compiler.loader import modelo_fact_scope
from dev.registry.edition_export_scenarios import m200_export_scenario
from dev.registry.edition_round_trip import SYNTHETIC_TAX_ID

from .authored_edition_support import revision_covering
from .filing_reach_support import with_filing_reach

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M200 = "200"
_PERIOD_CODE = "0A"

# Editions whose Sociedades manual prints the flat reduced rate (Ley 31/2022 art. 39).
_REDUCED_RATE_EDITIONS = manual_editions_printing(
    "sociedades",
    "Entidades INCN < 1 millón de euros en el período impositivo inmediato anterior",
    "tributan al tipo de gravamen reducido del 23 por ciento",
)
assert _REDUCED_RATE_EDITIONS, "no bundled Sociedades manual prints the flat 23 per cent reduced rate"
# Editions whose Sociedades manual prints the cuota liquida minima worked examples
# this oracle reproduces, box by box.
_WORKED_EXAMPLE_EDITIONS = manual_editions_printing(
    "sociedades",
    "Cuota líquida [00592] 270.000",
    "Cuota líquida [00592] 425.000",
    "Cuota del ejercicio a ingresar o a devolver [00599] -20.000",
    "Cuota diferencial [00611] -30.000",
    "Tipo general 25 por 100",
)
_GENERAL_RATE_EDITIONS = tuple(edition for edition in _WORKED_EXAMPLE_EDITIONS if edition < min(_REDUCED_RATE_EDITIONS))
assert _GENERAL_RATE_EDITIONS, (
    "no bundled Sociedades manual before the reduced rate prints the cuota liquida minima worked examples"
)
_LAST_GENERAL_RATE_EXERCISE = max(_GENERAL_RATE_EDITIONS)


@dataclass(frozen=True, slots=True)
class _OracleScenario:
    """Draft facts and the boxes the manual's worked example prints for them (module docstring)."""

    inputs: ModeloInputs
    expected: Mapping[str, Decimal]


_ZERO = Decimal("0.00")

_SHARED_FACTS: Mapping[str, object] = {
    "modelo-200-profile-legal-entity-form": "sa",
    "modelo-200-profile-new-entity-flag": False,
    "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
    "modelo-200-profile-incn-prior-12-months": Decimal("25000000.00"),
    "modelo-200-bin-pendiente-ejercicios-anteriores": _ZERO,
    "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": _ZERO,
    "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": _ZERO,
    "modelo-200-pago-fraccionado-primero-40-3": _ZERO,
    "modelo-200-pago-fraccionado-segundo-40-2": _ZERO,
    "modelo-200-pago-fraccionado-segundo-40-3": _ZERO,
    "modelo-200-pago-fraccionado-tercero-40-2": _ZERO,
    "modelo-200-pago-fraccionado-tercero-40-3": _ZERO,
}

_BASE_2M: Mapping[str, Decimal] = {
    "DP200013:00550": Decimal("2000000.00"),
    "DP200013:00552": Decimal("2000000.00"),
    "DP200014:01330": Decimal("2000000.00"),
    "DP200014:00558": Decimal("25"),
    "DP200014:00562": Decimal("500000.00"),
}

_SCENARIOS: Mapping[str, _OracleScenario] = {
    "ejemplo-1-sin-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("2000000.00"),
            "DP200014:00573": Decimal("150000.00"),
            "DP200014:00588": Decimal("80000.00"),
            "DP200014:00619": _ZERO,
            "modelo-200-pago-fraccionado-primero-40-2": _ZERO,
        },
        expected={
            **_BASE_2M,
            "DP200014:00582": Decimal("350000.00"),
            "DP200014:00592": Decimal("270000.00"),
            "DP200014B:00599": Decimal("270000.00"),
            "DP200014B:00611": Decimal("270000.00"),
        },
    ),
    "ejemplo-1-con-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("2000000.00"),
            "DP200014:00573": Decimal("150000.00"),
            "DP200014:00588": Decimal("50000.00"),
            "DP200014:00619": Decimal("300000.00"),
            "modelo-200-pago-fraccionado-primero-40-2": _ZERO,
        },
        expected={
            **_BASE_2M,
            "DP200014:00582": Decimal("350000.00"),
            "DP200014:00592": Decimal("300000.00"),
            "DP200014B:00599": Decimal("300000.00"),
            "DP200014B:00611": Decimal("300000.00"),
        },
    ),
    "ejemplo-2-sin-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("1000000.00"),
            "DP200014:00567": Decimal("20000.00"),
            "DP200014:00573": Decimal("10000.00"),
            "DP200014:00588": Decimal("110000.00"),
            "DP200014:02315": Decimal("90000.00"),
            "DP200014:00082": Decimal("20000.00"),
            "DP200014:00619": _ZERO,
            "DP200014B:01766": Decimal("20000.00"),
            "modelo-200-pago-fraccionado-primero-40-2": Decimal("10000.00"),
        },
        expected={
            "DP200013:00550": Decimal("1000000.00"),
            "DP200013:00552": Decimal("1000000.00"),
            "DP200014:01330": Decimal("1000000.00"),
            "DP200014:00558": Decimal("25"),
            "DP200014:00562": Decimal("250000.00"),
            "DP200014:00582": Decimal("220000.00"),
            "DP200014:00592": _ZERO,
            "DP200014B:00599": Decimal("-20000.00"),
            "DP200014B:00611": Decimal("-30000.00"),
        },
    ),
    "ejemplo-2-con-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("1000000.00"),
            "DP200014:00567": Decimal("20000.00"),
            "DP200014:00573": Decimal("10000.00"),
            "DP200014:00588": _ZERO,
            "DP200014:02315": Decimal("90000.00"),
            "DP200014:00082": Decimal("130000.00"),
            "DP200014:00619": Decimal("130000.00"),
            "DP200014B:01766": Decimal("20000.00"),
            "modelo-200-pago-fraccionado-primero-40-2": Decimal("10000.00"),
        },
        expected={
            "DP200013:00550": Decimal("1000000.00"),
            "DP200013:00552": Decimal("1000000.00"),
            "DP200014:01330": Decimal("1000000.00"),
            "DP200014:00558": Decimal("25"),
            "DP200014:00562": Decimal("250000.00"),
            "DP200014:00582": Decimal("220000.00"),
            "DP200014:00592": _ZERO,
            "DP200014B:00599": Decimal("-20000.00"),
            "DP200014B:00611": Decimal("-30000.00"),
        },
    ),
    "ejemplo-3-con-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("2000000.00"),
            "DP200014:00573": Decimal("45000.00"),
            "DP200014:00588": Decimal("30000.00"),
            "DP200014:00619": Decimal("300000.00"),
            "modelo-200-pago-fraccionado-primero-40-2": _ZERO,
        },
        expected={
            **_BASE_2M,
            "DP200014:00582": Decimal("455000.00"),
            "DP200014:00592": Decimal("425000.00"),
            "DP200014B:00599": Decimal("425000.00"),
            "DP200014B:00611": Decimal("425000.00"),
        },
    ),
}


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


class _PayloadSink:
    """Keeps the validated payload in memory; no plaintext export touches disk."""

    payload: bytes = b""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        self.payload = payload.payload


def _fixed_width_layouts(revision: ModeloRevision) -> tuple[ExportLayoutDefinition, ...]:
    return tuple(layout for layout in revision.export_layouts if layout.format is ExportLayoutFormat.FIXED_WIDTH)


@pytest.mark.parametrize("scenario_id", sorted(_SCENARIOS))
def test_modelo_200_last_general_rate_edition_calculates_and_exports_the_manual_worked_examples(
    registry_authority: ValidatedRegistryAuthority, scenario_id: str
) -> None:
    scenario = _SCENARIOS[scenario_id]
    revision_id = str(revision_covering(_M200, _LAST_GENERAL_RATE_EXERCISE).id)
    period = Period.from_year_and_code(_LAST_GENERAL_RATE_EXERCISE, _PERIOD_CODE)
    export_scenario = m200_export_scenario(period)
    identity_factory = export_scenario.product_software_identity_factory
    assert identity_factory is not None
    staged = with_filing_reach(registry_authority, _M200, revision_id)

    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", _M200)), validating_governed_facts(staged):
        provider = schema_provider_from_authority(
            staged, modelos=(_M200,), filing_year=period.filing_year, period=period
        )
        draft = build_draft(
            modelo=_M200,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 general-rate oracle"),
            inputs=scenario.inputs,
            schema_provider=provider,
        ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
        assert str(draft.snapshot_ref.revision_id) == revision_id

        calculated = {str(value.casilla_id): value.value for value in draft.values}
        assert {casilla_id: calculated.get(casilla_id) for casilla_id in scenario.expected} == dict(scenario.expected)

        layouts = _fixed_width_layouts(staged.modelo(_M200).revisions[revision_id])
        assert len(layouts) == 1, (
            f"Modelo 200 revision {revision_id} carries {len(layouts)} fixed-width export layouts; "
            "its own design's layout is required to file it"
        )
        (layout,) = layouts
        sink = _PayloadSink()
        export_draft(
            draft,
            payload_consumer=sink,
            producer_snapshot=export_scenario.producer_snapshot(),
            prior_domiciliation_election=export_scenario.prior_domiciliation_election,
            product_software_identity=identity_factory(),
            schema_provider=provider,
        )

    parsed = parse_export_payload(
        layout, sink.payload, sources=provider.sources, source_payloads=provider.source_payloads
    )
    parsed_by_casilla = {
        str(value.casilla_id): value.value for value in parsed.casillas if value.casilla_id is not None
    }
    assert {casilla_id: parsed_by_casilla.get(casilla_id) for casilla_id in scenario.expected} == dict(
        scenario.expected
    )
