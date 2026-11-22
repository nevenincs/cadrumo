"""The first Modelo 200 edition of the flat 23 % reduced rate calculates its hand-worked oracle and files it.

Ley 31/2022 art. 39 gave LIS art. 29.1 a 23 % rate for an entity whose importe
neto de la cifra de negocios (INCN) of the immediately preceding period is below
1 millon de euros, for periods starting from 1 January of the first exercise
whose Manual practico de Sociedades prints it. That exercise is read here from
the bundled manuals (the oldest edition printing the rate and the casilla 00088
wording), and its Modelo 200 revision from the registry, so no year is named.

Each scenario builds a draft from its facts through the canonical draft builder,
compares the calculated boxes with values derived by hand from that edition's
manual and record design, exports the draft through the edition's own
fixed-width layout, parses the bytes back through the registry codec and
compares every oracle box again. An edition without its own fixed-width layout
fails at the export half: it calculates but does not file.

Sources (line numbers of ``corpus/manuals/sociedades/<edition>/
source.pdf.extracted.md`` for the edition selected; the record design is the
``aeat-dr-200`` workbook the edition's layout cites):

    L327-L330: "Con efectos para los periodos impositivos que se inicien a
      partir de 1 de enero de [the edition], la Ley 31/2022 ... introduce en el
      articulo 29 de la LIS un tipo de gravamen reducido del 23 por ciento para
      las entidades cuyo importe neto de la cifra de negocios del periodo
      impositivo inmediato anterior sea inferior a 1 millon de euros."
    L13575 "Tipo general 25 por 100"; L13587-13588 "Entidades INCN < 1 millon
      de euros en el periodo impositivo inmediato anterior (no siendo aplicable
      a aquellas entidades que tengan la consideracion de entidad patrimonial)
      23 por 100".
    L7103 "[00550] = [00501] + ([00417] - [00418])".
    L13026 "[00552] = [00550] - [01032] - [00547]".
    L13273-13277, L13287-13288 BIN compensation: limit 70 por ciento of the base previa, "en
      todo caso ... hasta el importe de 1 millon de euros" (LIS art. 26.1).
    L13515 "[01330] = [00552] + [01033] - [01034]"; L23767 "el importe de la
      casilla [01330] coincidira con el de la casilla [00552]".
    L13559 "[00562] = [00552] x [00558]/100"; L13561 positive or zero.
    L13702 "[00582] = ([00562] + [01038]) - (...)".
    L14611-14626 cuota liquida minima [00619]: art. 30 bis applies only to an
      INCN "al menos de 20 millones" or consolidacion fiscal.
    L15177 "[00592] = [00582] - (...)"; L15179 positive or zero. Its operands are
      the deducciones "aplicadas por el contribuyente en el periodo impositivo"
      (L15174-15175), so the cuota liquida minima of art. 30 bis enters through
      the amounts consigned, not as a floor: the restantes deducciones apply
      "hasta el importe de dicha cuota liquida minima" (L14692-14694), the
      Canarias deductions "aunque la cuota liquida resultante sea inferior a la
      mencionada cuota liquida minima" (L14695-14704), and the art. 39.2 I+D+i
      deduction "no se ve afectada por el importe de la cuota liquida minima"
      (L14984-14986).
    L19199 "[00599] = ([00625]/100]) x ([00592] - [01766] - [01784])".
    L19441 "[00611] = [00599] - ([00601] + [00603] + [00605])".
    LIS art. 40.2 (BOE-A-2014-12328, consolidated text): each instalment is
      18 % of the cuota of the last period whose plazo had ended.

The edition reads no twelve-month INCN. Earlier and later editions declare the
binding modelo-200-profile-incn-prior-12-months (profile fact
incn_prior_12_months, legal ref LIS DA 15a) only for the DA 15a limits on the
compensation of bases imponibles negativas: 50 % from 20 millones and 25 % from
60 millones of INCN in the twelve months before the period (the preceding
manual's DA 15a passage; the following manual's restored DA 15a). This
edition's manual records at L576-L586 that the Tribunal Constitucional, in the
judgment it dates there, annulled DA 15a and DT 16a.3 LIS, and at
L13273-13277 prints the 70 % limit alone, so its revision removes the binding
and the DA 15a parameters and the oracle supplies no such input. The same
manual still asks for the twelve-month INCN on page 1 for the art. 30 bis
minimum (L13403-13405) and the art. 11.12 limits (L9466-9469); neither is read
through that binding. The cuota liquida minima [00619] is supplied as 0 in the
``persona`` and ``general`` scenarios, which art. 30 bis does not reach.

Scenario ``persona``: the sociedad-limitada persona's return for the exercise
(dev/fixtures/personas/sociedad-limitada). Resultado contable 25400.00, no
correction; pending BIN 16300.00, all compensated (min(16300.00, max(1000000.00,
70 % x 25400.00))); INCN of the preceding period 28500.00, not an entidad
patrimonial, third period with a positive base so not nueva creacion; State 100 %;
first instalment 54.00 (18 % x 300.00), the others 0.00.

    00550 = 25400.00 + 0 - 0                       = 25400.00
    00552 = 25400.00 - 0 - 16300.00                = 9100.00
    01330 = 9100.00 + 0 - 0                        = 9100.00
    00558 = 23 (INCN 28500.00 < 1000000)
    00562 = 9100.00 x 23 / 100                     = 2093.00
    00582 = 2093.00 + 0 - 0                        = 2093.00
    00592 = 2093.00 - 0                            = 2093.00
    00599 = 100 / 100 x (2093.00 - 0 - 0)          = 2093.00
    00611 = 2093.00 - (54.00 + 0 + 0)              = 2039.00

Scenario ``general``: the public mechanism vector's figures (resultado 100000.00,
INCN of the preceding period 12000000.00, no BIN, no instalment). The INCN is
not below 1 millon, so the general rate applies; it is below 20 millones, so
art. 30 bis does not.

    00550 = 00552 = 01330 = 100000.00; 00558 = 25;
    00562 = 00582 = 00592 = 00599 = 00611 = 100000.00 x 25 / 100 = 25000.00

Scenarios ``ejemplo-*``: the same manual's "Cuota liquida minima (casilla
00619)" supuestos practicos (pp. 364-376), each a sociedad whose INCN in the
twelve months before the period "supero los 20 millones de euros" and that
"tributa al tipo general de gravamen del 25 por ciento" (L14714, L14843,
L15034); the preceding-period INCN the rate reads is supplied as 25.000.000,
consistent with that rate. Each prints its final liquidacion box by box:

    Ejemplo 1 (L14816-14834): base imponible 2.000.000; [00562] 500.000;
      [00573] 150.000; [00582] 350.000; the I+D+i deduction limited to the
      minimum, [00588] 50.000 with 30.000 pendiente; [00619] 300.000; [00592]
      300.000; [01586] 300.000.
    Ejemplo 2 (L14937-15030): base imponible 1.000.000; [00562] 250.000;
      bonificacion Ceuta y Melilla [00567] 20.000; [00573] 10.000; [00582]
      220.000; [00588] 0 with 250.000 pendiente; [02315] 90.000; [00082]
      130.000; [00592] 0; [01766] 20.000; [00599] -20.000; pagos fraccionados
      10.000; [00611] -30.000. The text states the cuota liquida minima as
      "130.000 euros" (L14978-14979) while the table prints the box [00619] as
      0; the scenario consigns the 130.000 the text states, so a cuota liquida
      floored at [00619] reads 130.000 and fails, and every oracle box is the
      same with either value.
    Ejemplo 3 (L15139-15160): base imponible 2.000.000; [00562] 500.000;
      [00573] 45.000; [00582] 455.000; [00588] 30.000; [00619] 300.000; [00592]
      425.000, above the minimum.

Ejemplos 1 and 3 print no retenciones or pagos and a [01586] equal to the cuota
liquida, so [00599] and [00611] equal [00592] with the State at 100 %.

None of these values was read from a run of the registry formulas.
"""

from __future__ import annotations

import dataclasses
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
from cadrumo.core.revision_review import RevisionReviewStatus
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

# The oldest bundled Sociedades manual that prints the flat reduced rate and the
# casilla 00088 wording is the first exercise Ley 31/2022 art. 39 governs.
_REDUCED_RATE_EDITIONS = manual_editions_printing(
    "sociedades",
    "Entidades INCN < 1 millón de euros en el período impositivo inmediato anterior",
    "tributan al tipo de gravamen reducido del 23 por ciento",
)
assert _REDUCED_RATE_EDITIONS, "no bundled Sociedades manual prints the flat 23 per cent reduced rate"
_FIRST_REDUCED_RATE_EXERCISE = min(_REDUCED_RATE_EDITIONS)


@dataclass(frozen=True, slots=True)
class _OracleScenario:
    """Draft facts and the boxes derived by hand from them (module docstring)."""

    inputs: ModeloInputs
    expected: Mapping[str, Decimal]


_ZERO = Decimal("0.00")

_SHARED_FACTS: Mapping[str, object] = {
    "modelo-200-profile-legal-entity-form": "sl",
    "modelo-200-profile-new-entity-flag": False,
    "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
    "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": _ZERO,
    "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": _ZERO,
    "modelo-200-pago-fraccionado-primero-40-3": _ZERO,
    "modelo-200-pago-fraccionado-segundo-40-2": _ZERO,
    "modelo-200-pago-fraccionado-segundo-40-3": _ZERO,
    "modelo-200-pago-fraccionado-tercero-40-2": _ZERO,
    "modelo-200-pago-fraccionado-tercero-40-3": _ZERO,
    # Art. 30 bis reaches neither scenario (INCN below 20 millones, no consolidacion).
    "DP200014B:00619": _ZERO,
}

# The manual's worked examples state an INCN above 20 millones and the tipo general; the
# preceding-period INCN the rate reads is supplied consistently with both (module docstring).
_WORKED_EXAMPLE_PRIOR_INCN = Decimal("25000000.00")

_WORKED_EXAMPLE_BASE_2M: Mapping[str, Decimal] = {
    "DP200014:00550": Decimal("2000000.00"),
    "DP200014:00552": Decimal("2000000.00"),
    "DP200014:01330": Decimal("2000000.00"),
    "DP200014:00558": Decimal("25"),
    "DP200014:00562": Decimal("500000.00"),
}

_SCENARIOS: Mapping[str, _OracleScenario] = {
    "persona": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("25400.00"),
            "DP200014:00547": Decimal("16300.00"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": Decimal("16300.00"),
            "modelo-200-incn-periodo-impositivo-anterior": Decimal("28500.00"),
            "modelo-200-pago-fraccionado-primero-40-2": Decimal("54.00"),
        },
        expected={
            "DP200014:00550": Decimal("25400.00"),
            "DP200014:00552": Decimal("9100.00"),
            "DP200014:01330": Decimal("9100.00"),
            "DP200014:00558": Decimal("23"),
            "DP200014:00562": Decimal("2093.00"),
            "DP200014:00582": Decimal("2093.00"),
            "DP200014B:00592": Decimal("2093.00"),
            "DP200014B:00599": Decimal("2093.00"),
            "DP200014B:00601": Decimal("54.00"),
            "DP200014B:00611": Decimal("2039.00"),
        },
    ),
    "general": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("100000.00"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": _ZERO,
            "modelo-200-incn-periodo-impositivo-anterior": Decimal("12000000"),
            "modelo-200-pago-fraccionado-primero-40-2": _ZERO,
        },
        expected={
            "DP200014:00550": Decimal("100000.00"),
            "DP200014:00552": Decimal("100000.00"),
            "DP200014:01330": Decimal("100000.00"),
            "DP200014:00558": Decimal("25"),
            "DP200014:00562": Decimal("25000.00"),
            "DP200014:00582": Decimal("25000.00"),
            "DP200014B:00592": Decimal("25000.00"),
            "DP200014B:00599": Decimal("25000.00"),
            "DP200014B:00611": Decimal("25000.00"),
        },
    ),
    "ejemplo-1-con-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("2000000.00"),
            "DP200014:00573": Decimal("150000.00"),
            "DP200014B:00588": Decimal("50000.00"),
            "DP200014B:00619": Decimal("300000.00"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": _ZERO,
            "modelo-200-incn-periodo-impositivo-anterior": _WORKED_EXAMPLE_PRIOR_INCN,
            "modelo-200-pago-fraccionado-primero-40-2": _ZERO,
        },
        expected={
            **_WORKED_EXAMPLE_BASE_2M,
            "DP200014:00582": Decimal("350000.00"),
            "DP200014B:00592": Decimal("300000.00"),
            "DP200014B:00599": Decimal("300000.00"),
            "DP200014B:00611": Decimal("300000.00"),
        },
    ),
    "ejemplo-2-con-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("1000000.00"),
            "DP200014:00567": Decimal("20000.00"),
            "DP200014:00573": Decimal("10000.00"),
            "DP200014B:00588": _ZERO,
            "DP200014B:02315": Decimal("90000.00"),
            "DP200014B:00082": Decimal("130000.00"),
            "DP200014B:00619": Decimal("130000.00"),
            "DP200014B:01766": Decimal("20000.00"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": _ZERO,
            "modelo-200-incn-periodo-impositivo-anterior": _WORKED_EXAMPLE_PRIOR_INCN,
            "modelo-200-pago-fraccionado-primero-40-2": Decimal("10000.00"),
        },
        expected={
            "DP200014:00550": Decimal("1000000.00"),
            "DP200014:00552": Decimal("1000000.00"),
            "DP200014:01330": Decimal("1000000.00"),
            "DP200014:00558": Decimal("25"),
            "DP200014:00562": Decimal("250000.00"),
            "DP200014:00582": Decimal("220000.00"),
            "DP200014B:00592": _ZERO,
            "DP200014B:00599": Decimal("-20000.00"),
            "DP200014B:00611": Decimal("-30000.00"),
        },
    ),
    "ejemplo-3-con-tributacion-minima": _OracleScenario(
        inputs={
            **_SHARED_FACTS,
            "DP200012:00501": Decimal("2000000.00"),
            "DP200014:00573": Decimal("45000.00"),
            "DP200014B:00588": Decimal("30000.00"),
            "DP200014B:00619": Decimal("300000.00"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": _ZERO,
            "modelo-200-incn-periodo-impositivo-anterior": _WORKED_EXAMPLE_PRIOR_INCN,
            "modelo-200-pago-fraccionado-primero-40-2": _ZERO,
        },
        expected={
            **_WORKED_EXAMPLE_BASE_2M,
            "DP200014:00582": Decimal("455000.00"),
            "DP200014B:00592": Decimal("425000.00"),
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


def _with_filing_reach_and_review(
    authority: ValidatedRegistryAuthority, revision_id: str
) -> ValidatedRegistryAuthority:
    """Return an in-memory copy in which the revision reaches filing grade and reads as reviewed.

    The writer serves a filing-grade snapshot of a reviewed revision only. This
    test is about the edition's calculation and bytes, which hold before the
    edition's grade and review stamp are raised, so both are lifted in a copy
    that lives for the test alone; the registry's declared grade and stamp are
    neither read as earned nor changed.
    """
    staged = with_filing_reach(authority, _M200, revision_id)
    modelo = staged.modelo(_M200)
    revision = modelo.revisions[revision_id]
    if revision.review_status is not RevisionReviewStatus.PENDING_REVIEW:
        return staged
    reviewed = modelo.model_copy(
        update={
            "revisions": {
                **modelo.revisions,
                revision_id: revision.model_copy(update={"review_status": RevisionReviewStatus.AUTOMATION_REVIEWED}),
            }
        }
    )
    modelos = tuple(reviewed if candidate.id == _M200 else candidate for candidate in staged.modelos)
    return dataclasses.replace(
        staged, modelos=modelos, modelos_by_id={candidate.id: candidate for candidate in modelos}, snapshots={}
    )


def _fixed_width_layouts(revision: ModeloRevision) -> tuple[ExportLayoutDefinition, ...]:
    return tuple(layout for layout in revision.export_layouts if layout.format is ExportLayoutFormat.FIXED_WIDTH)


@pytest.mark.parametrize("scenario_id", sorted(_SCENARIOS))
def test_modelo_200_first_reduced_rate_edition_calculates_and_exports_its_oracle(
    registry_authority: ValidatedRegistryAuthority, scenario_id: str
) -> None:
    scenario = _SCENARIOS[scenario_id]
    revision_id = str(revision_covering(_M200, _FIRST_REDUCED_RATE_EXERCISE).id)
    period = Period.from_year_and_code(_FIRST_REDUCED_RATE_EXERCISE, _PERIOD_CODE)
    export_scenario = m200_export_scenario(period)
    identity_factory = export_scenario.product_software_identity_factory
    assert identity_factory is not None
    staged = _with_filing_reach_and_review(registry_authority, revision_id)

    with modelo_fact_scope(bundled_path("registry", "aeat", "modelos", _M200)), validating_governed_facts(staged):
        provider = schema_provider_from_authority(
            staged, modelos=(_M200,), filing_year=period.filing_year, period=period
        )
        draft = build_draft(
            modelo=_M200,
            period=period,
            profile=ModeloOperatorProfile(tax_id=SYNTHETIC_TAX_ID, display_name="Modelo 200 reduced-rate oracle"),
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
