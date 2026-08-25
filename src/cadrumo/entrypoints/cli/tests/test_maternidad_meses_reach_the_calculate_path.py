"""The declared Art. 81.1 maternidad months must REACH casilla 0611, not merely persist.

``renta_family.descendiente.{n}.meses_madre_trabajo`` was written by three
surfaces -- the guided walk, ``descendiente add`` and the JSON payload --
declared in the user-profile schema, carried through the resume walk, and read by
nothing that calculates. Casilla 0611 was set only from a calculate-time flag
carrying a free-form hijo id that no descendant record answers to.

So an operator who declared the months through the documented entry surface got
nothing, while the surface said it recorded them. Declared-and-unconsumed is
worse than absent: absent reads as an omission, declared reads to any inspector
as wired.

These tests drive the real ``aeat`` CLI end to end against an isolated real
backend -- no mocks, no monkeypatched engine. The expected figures are the AEAT
Renta 2024 manual's own printed worked example for two mellizos under three whose
mother met the requirements all twelve months:

    numero de meses de cumplimiento de los requisitos: 12 meses
    importe de la deduccion: (12 meses x 100 euros) = 1.200
    limite de la deduccion por hijo (1.200 euros)
    importe total de la deduccion correspondiente a los mellizos
        = 1.200 x 2 hijos = 2.400 euros

Nothing here re-derives the arithmetic under test: 2.400 and 1.200 are the
figures the authority prints, and the same passage states the eligibility rule
this path applies -- the deduction runs "por cada hijo hasta que el menor alcance
los tres anos de edad" for women "que tengan derecho a la aplicacion del minimo
por descendientes".
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import STR_KEYED_MAPPING_ADAPTER
from ....core.config import override_settings
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000611001"

#: Modelo 100 casilla ``0611`` -- semantic role ``irpf_deduccion_maternidad``.
_MATERNIDAD_CASILLA_ID = "0611"

#: AEAT Renta 2024 manual, deduccion por maternidad worked example: two mellizos,
#: twelve qualifying months each, "1.200 x 2 hijos = 2.400 euros".
_ORACLE_TWO_MELLIZOS_TWELVE_MONTHS = Decimal("2400")

#: The same example's per-hijo figure, "(12 meses x 100 euros) = 1.200".
_ORACLE_ONE_HIJO_TWELVE_MONTHS = Decimal("1200")

#: Born mid-2022, so age two at the 2024 devengo: inside the Art. 81.1 population.
_MELLIZO_BIRTH = "NACIMIENTO=2022-06-01"

# Every profile/relation-sourced binding a minimal M100 2024 calculate needs
# besides the descendiente facts under test. Mirrors the fixture in
# ``test_modelo_100_descendiente_entry_surface.py``; no binding here touches
# 0611. Its 2024 registry formula reads the profile-derived scalar, so no
# command-line flag supplies its value.
_REQUIRED_2024_BINDING_FLAGS: tuple[str, ...] = (
    "--binding", "renta-2024-modelo-100-estimacion-directa-es-normal=1",
    "--binding", "renta-2024-modelo-111-retenciones-periodicas=0",
    "--binding", "renta-2024-modelo-123-retenciones-periodicas=0",
    "--binding", "renta-2024-modelo-193-retenciones-anuales=0",
    "--binding", "renta-2024-modelo-130-pagos-fraccionados=0",
    "--binding", "renta-2024-modelo-131-pagos-fraccionados=0",
    "--binding", "renta-2024-profile-family-minor-children-in-unit=0",
    "--binding", "renta-2024-profile-guarderia-gastos-reales=0",
    "--binding", "renta-2024-profile-cotizaciones-ss-madre=0",
    "--binding", "renta-2024-profile-marriage-full-year=0",
    "--binding", "renta-2024-profile-marriage-month-start=0",
    "--binding", "renta-2024-profile-marriage-month-end=0",
    "--binding", "renta-2024-base-liquidable-negativa-general-anterior=0",
)  # fmt: skip


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Maternidad meses arrival test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed the minimum facts an M100 work-unit applicability guard requires."""
    record = UserProfileRecord(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Marta"),
            UserProfileFact(path="identity.surnames", value="Diaz Ortega"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
        ),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label="Maternidad meses arrival test profile")


def _declare(*descendiente_specs: str) -> None:
    """Declare each descendant through the real ``descendiente add`` verb."""
    flags: list[str] = []
    for spec in descendiente_specs:
        flags.extend(("--descendiente", spec))
    result = invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "add", *flags])
    assert result.exit_code == 0, result.output


def _calculate(*extra_flags: str) -> tuple[int, str]:
    """Calculate a fresh M100 2024 work unit, returning the exit code and output."""
    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_REQUIRED_2024_BINDING_FLAGS,
            *extra_flags,
        ],
    )  # fmt: skip
    return result.exit_code, result.output


def _casilla_0611(output: str) -> Decimal:
    return Decimal(str(_payload(output)["casilla_values"][_MATERNIDAD_CASILLA_ID]))


def _casilla_0611_observation(output: str) -> dict[str, object]:
    """Return 0611's persisted, registry-grounded calculation observation."""
    observations = _payload(output)["observations"]
    observation = next(
        observation for observation in observations if observation["casilla_id"] == _MATERNIDAD_CASILLA_ID
    )
    return STR_KEYED_MAPPING_ADAPTER.validate_python(observation)


def _advisory_kinds(output: str) -> set[str]:
    return {
        notice.get("context", {}).get("source_kind")
        for notice in unwrap_envelope_notices(output)
        if notice["code"] == "modelo.work.calculate.source_advisory"
    }


def _advisory_messages(output: str, *, source_kind: str) -> list[str]:
    """The rendered ``message`` text of every notice carrying *source_kind*."""
    return [
        str(notice["message"])
        for notice in unwrap_envelope_notices(output)
        if notice["code"] == "modelo.work.calculate.source_advisory"
        and notice.get("context", {}).get("source_kind") == source_kind
    ]


# ---------------------------------------------------------------------------
# Arrival: the regression this module exists for.
# ---------------------------------------------------------------------------


def test_declared_meses_reach_casilla_0611(runtime_profile: TestRuntimeProfile) -> None:
    """The AEAT worked example, driven through the surface an operator actually uses.

    Two mellizos under three, twelve qualifying months each. Before the connect
    landed this resolved to zero however many months were declared, because no
    consumer read the fact.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12",
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12",
    )

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == _ORACLE_TWO_MELLIZOS_TWELVE_MONTHS


def test_one_hijo_twelve_months_reaches_the_manual_per_hijo_figure(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The same example's per-hijo line, isolated: one child, twelve months, 1.200."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == _ORACLE_ONE_HIJO_TWELVE_MONTHS


def test_declaring_fewer_months_moves_the_casilla(runtime_profile: TestRuntimeProfile) -> None:
    """Anti-tautology: the casilla must TRACK the declared months, not merely be nonzero.

    A connect that wrote a constant, or that read some other fact, passes both
    assertions above. Six months at the authority's 100 euros per month is 600,
    and a path indifferent to the declared figure cannot produce it.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-6")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("600")


def test_alta_posterior_reaches_the_1350_per_hijo_cap(runtime_profile: TestRuntimeProfile) -> None:
    """The 2024 manual's Art. 81.1 cap rises to 1.350 after a qualifying alta.

    This child has twelve qualifying months and its declared alta is in the
    first working month. The authority's annual 1.350 cap, rather than an
    application-side reconstruction of the 150 increment, is the oracle.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2024-01-15,MESES_TRABAJO=1-12,ALTA_POSTERIOR_MES=1")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("1350")


def test_mixed_alta_cap_descendants_are_folded_per_child(runtime_profile: TestRuntimeProfile) -> None:
    """The 1.350 and 1.200 annual caps apply to their respective children.

    A premature aggregate cap would lose the child-specific alta entitlement.
    The manual's stated per-child caps make 2.550 the external oracle for this
    mixed pair.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(
        "NACIMIENTO=2024-01-15,MESES_TRABAJO=1-12,ALTA_POSTERIOR_MES=1",
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12",
    )

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("2550")


def test_0611_is_a_provenance_carrying_registry_formula(runtime_profile: TestRuntimeProfile) -> None:
    """The calculated record retains formula and legal/source provenance for 0611."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    observation = _casilla_0611_observation(output)
    assert observation["formula_id"] == "renta-2024-deduccion-maternidad-0611"
    assert observation["legal_refs"] == ["ley-35-2006:art-81"]
    source_refs = observation["source_refs"]
    assert isinstance(source_refs, list)
    assert set(source_refs) == {
        "aeat-renta-2024-manual-parte1",
        "aeat-dr-100-2024-dictionary",
    }


# ---------------------------------------------------------------------------
# Eligibility: the engine's half of the hybrid.
# ---------------------------------------------------------------------------


def test_months_declared_for_a_child_over_three_are_withheld_and_disclosed(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Art. 81.1 runs only "hasta que el menor alcance los tres anos de edad".

    Withholding is correct; withholding SILENTLY is not. An operator who typed a
    real figure and received nothing must be told which descendant was excluded
    and why, or the entry surface is lying again in the opposite direction.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2015-04-01,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("0")
    assert "maternidad_meses_withheld" in _advisory_kinds(output), (
        f"withheld maternidad months must be disclosed; got {_advisory_kinds(output)}"
    )

    messages = _advisory_messages(output, source_kind="maternidad_meses_withheld")
    assert messages, "the withheld advisory must carry a rendered message"
    # The advisory names the entry-date window as a second route to the
    # deducción, and must not steer every withheld filer toward altering their
    # birth date -- an over-three adopción/acogimiento is withheld for a
    # missing INSCRIPCION/ACOGIMIENTO date, not for being the wrong age.
    assert "INSCRIPCION" in messages[0] or "ACOGIMIENTO" in messages[0]
    assert "reaches only a descendant under three" not in messages[0]
    # The remedy must name an editing route the paged door refuses on a piped
    # host and `descendiente add` (append-only) cannot perform: removing the
    # row and re-adding it.
    # The advisory names the record to restate, not the command that does it:
    # Notice reserves executable command identity for the typed action
    # projection and refuses a message carrying raw `aeat ...` prose.
    assert "descendiente record" in messages[0]


def test_an_eligible_child_does_not_raise_the_withheld_advisory(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The advisory must fire on the state it names and not on the healthy one."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert "maternidad_meses_withheld" not in _advisory_kinds(output)


def test_a_child_turning_three_mid_year_contributes_its_months_before_the_birthday(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The under-grant the month window closes, proven through the real CLI.

    Born April 2021, so three years old by the 2024 devengo. A year-end age test
    excludes the child entirely and the mother receives nothing for a year in
    which she qualified for three months. Art. 81.1 runs "hasta que el menor
    alcance los tres anos de edad", so January to March count and the birthday
    month does not: three months at the authority's 100 euros is 300.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2021-04-15,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("300")


def test_the_art_81_1_entry_window_reaches_the_casilla_for_a_child_over_three(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The adopcion limb, driven through the surface an operator uses.

    Art. 81.1 grants the deduccion "con independencia de la edad del menor,
    durante los tres anos siguientes a la fecha de la inscripcion en el Registro
    Civil". This child was five at inscription, so the under-three limb grants
    nothing and every month reaching the casilla came from the entry window.

    Inscribed 15 November 2021, so the window runs to October 2024 inclusive:
    ten months of the 2024 period at the authority's 100 euros is 1.000. The
    Art. 58.2 window, which counts whole tax PERIODS from the entry period, has
    already closed on 2023 -- which is the divergence this case exists to show.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2016-03-02,RELACION=adoptado,INSCRIPCION=2021-11-15,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("1000")


def test_no_month_before_the_adoption_reaches_the_casilla(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The over-grant this test removes, driven through the surface an operator uses.

    Born January 2024 and adopted in October. The under-three limb runs from the
    BIRTH month for every relacion, so unioning the two limbs granted January to
    September -- months before the child was hers -- and the casilla resolved to
    1.200 where 300 is due. Three eligible months at the authority's 100 euros.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2024-01-10,RELACION=adoptado,INSCRIPCION=2024-10-05,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("300")


def test_a_child_over_the_rentas_ceiling_contributes_nothing(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The deduction reaches only a child who holds the minimo por descendientes.

    Art. 58.1 excludes a descendant whose own annual rentas exceed the ceiling,
    and the authority defines the qualifying child for this deduction as one
    "con derecho a la aplicacion del minimo por descendientes". A bare
    age-and-cohabitation test cannot express that, so this case is the one that
    distinguishes the mininmo predicate from a bespoke one.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12,RENTAS=99999")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("0")
    assert "maternidad_meses_withheld" in _advisory_kinds(output)


# ---------------------------------------------------------------------------
# One authority, permanently -- the calculate-time flag is retired.
# ---------------------------------------------------------------------------


def test_the_calculate_time_flag_no_longer_exists(runtime_profile: TestRuntimeProfile) -> None:
    """``--meses-trabajo-con-hijo-menor-3`` is retired outright, not merely reconciled.

    The flag was a second, unvalidated authority over casilla 0611: a
    free-form hijo id no descendant record answered to, never checked against
    cohabitation, the rentas ceiling, or the Art. 61 norma 2ª own-return rule
    the profile path applies. An earlier guard made the two channels mutually
    refuse each other; this one removes the second channel, because a
    refusal still CONTAINS a two-authority hazard rather than eliminating it.
    Supplying the retired flag must fail Click's own option parsing -- an
    unrecognised option -- before the command body, and the profile-declared
    figure must be completely unaffected by its presence on the command line
    once Click has rejected the invocation.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    exit_code, output = _calculate("--meses-trabajo-con-hijo-menor-3", "0=12")

    assert exit_code != 0, output
    assert "meses-trabajo-con-hijo-menor-3" in output.lower()


def test_the_profile_declaration_alone_is_now_the_only_route(runtime_profile: TestRuntimeProfile) -> None:
    """With the flag gone, the descendiente-declared figure reaches 0611 unaided."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == _ORACLE_ONE_HIJO_TWELVE_MONTHS


@pytest.mark.parametrize("attempted_value", ("0", "9999"))
def test_direct_casilla_0611_cannot_bypass_or_overwrite_the_profile_producer(
    runtime_profile: TestRuntimeProfile,
    attempted_value: str,
) -> None:
    """A caller may neither manufacture nor overwrite the Art. 81.1 result.

    ``0`` would erase the profile's genuine 1.200 result, while ``9999`` would
    manufacture one. Both must be refused because 0611 is now a computed
    registry casilla, with the profile fold as its sole producer.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    # The word asserted below is catalogue text and the default output language
    # is Spanish, so the language is pinned rather than assumed: the refusal
    # otherwise says "casillas calculadas" and the assertion fails on a
    # correctly-rendered envelope.
    with override_settings(cadrumo_output_language="en"):
        exit_code, output = _calculate("--casilla", f"{_MATERNIDAD_CASILLA_ID}={attempted_value}")

    assert exit_code != 0, output
    assert _MATERNIDAD_CASILLA_ID in output
    assert "computed" in output.lower()


# ---------------------------------------------------------------------------
# The relación axis has no member for a grandchild or a judicial-guarda
# minor, so a contributing descendant recorded under the default relación is
# disclosed rather than silently trusted.
# ---------------------------------------------------------------------------


def test_a_contributing_descendant_under_the_default_relacion_is_disclosed(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The representability gap the research identified, reaching every already-stored record.

    The relación axis cannot express a grandchild/other-consanguinidad
    descendant or a minor under judicial guarda y custodia -- both mínimo-
    eligible under Art. 58.1 and excluded from Art. 81.1 by the same manual --
    so a filer with either child has no truthful value but the ordinary
    default, indistinguishable at the stored fact from a true hijo. This case
    IS a true hijo, and the advisory still fires: the application cannot tell
    the difference from the fact alone, which is the whole point.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == _ORACLE_ONE_HIJO_TWELVE_MONTHS
    assert "maternidad_ambiguous_relacion" in _advisory_kinds(output)

    messages = _advisory_messages(output, source_kind="maternidad_ambiguous_relacion")
    assert messages, "the ambiguous-relación advisory must carry a rendered message"
    assert "grandchild" in messages[0] or "consanguinidad" in messages[0]
    assert "guarda y custodia" in messages[0]
    # The advisory names the record to restate, not the command that does it:
    # Notice reserves executable command identity for the typed action
    # projection and refuses a message carrying raw `aeat ...` prose.
    assert "descendiente record" in messages[0]


def test_the_advisory_names_every_contributing_descendant_under_the_default(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Both mellizos are under the default relación and both are named."""
    _seed_natural_person_profile(runtime_profile)
    _declare(
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12",
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12",
    )

    exit_code, output = _calculate()

    assert exit_code == 0, output
    messages = _advisory_messages(output, source_kind="maternidad_ambiguous_relacion")
    assert messages
    assert "0" in messages[0] and "1" in messages[0]


def test_an_adopted_contributing_descendant_is_not_disclosed(runtime_profile: TestRuntimeProfile) -> None:
    """An explicitly-stated relación never triggers the advisory, whether entitling or not.

    Art. 81.1 admits ``ADOPTADO`` outright, but the advisory's scope is
    narrower than "is this relación entitled": it is "is this relación
    STATED", because an explicit adopción record already answers the
    hijo-or-not question the ordinary default cannot. Asking it anyway would
    be noise for an operator who already resolved the ambiguity.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},RELACION=adoptado,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert "maternidad_ambiguous_relacion" not in _advisory_kinds(output)


def test_a_tutela_contributing_descendant_is_not_disclosed(runtime_profile: TestRuntimeProfile) -> None:
    """Tutela is likewise explicitly stated, so it is unambiguous even though entitled."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},RELACION=tutela,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert "maternidad_ambiguous_relacion" not in _advisory_kinds(output)


def test_a_withheld_descendant_under_the_default_relacion_is_not_disclosed(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The advisory names a contributing figure at risk, not every default-relación row.

    An over-three descendant contributes nothing regardless of relación, so
    there is no money at risk for the ambiguity to threaten. Asking here would
    be noise on top of the withheld advisory this case already raises.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2015-04-01,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert "maternidad_meses_withheld" in _advisory_kinds(output)
    assert "maternidad_ambiguous_relacion" not in _advisory_kinds(output)


def test_a_temporal_acogimiento_contributing_nothing_is_not_disclosed(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A stated, non-entitling relación is unambiguous even though it also contributes nothing."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},RELACION=acogimiento_temporal,MESES_TRABAJO=1-12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("0")
    assert "maternidad_ambiguous_relacion" not in _advisory_kinds(output)


# ---------------------------------------------------------------------------
# The other half: the same disclosure at the point the operator declares
# the row, not only at calculate time.
# ---------------------------------------------------------------------------


def _descendiente_add_result(*specs: str):
    flags: list[str] = []
    for spec in specs:
        flags.extend(("--descendiente", spec))
    return invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "add", *flags])


def test_declaring_working_months_under_the_default_relacion_is_disclosed_immediately(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An operator actively declaring the row is told at that moment, not only on the next calculate."""
    _seed_natural_person_profile(runtime_profile)

    result = _descendiente_add_result(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    assert result.exit_code == 0, result.output
    notices = unwrap_envelope_notices(result.output)
    matching = [n for n in notices if n["code"] == "config.profile.descendiente.ambiguous_relacion"]
    assert matching, f"expected the ambiguous-relación notice; got {notices}"
    assert "guarda y custodia" in matching[0]["message"]
    assert matching[0]["context"] == {"indices": "0"}


def test_declaring_working_months_with_an_explicit_relacion_is_not_disclosed(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A stated relación resolves the ambiguity at declaration, same as at calculate time."""
    _seed_natural_person_profile(runtime_profile)

    result = _descendiente_add_result(f"{_MELLIZO_BIRTH},RELACION=tutela,MESES_TRABAJO=1-12")

    assert result.exit_code == 0, result.output
    notices = unwrap_envelope_notices(result.output)
    assert not [n for n in notices if n["code"] == "config.profile.descendiente.ambiguous_relacion"]


def test_declaring_no_working_months_is_not_disclosed(runtime_profile: TestRuntimeProfile) -> None:
    """The default relación alone is not the trigger; nothing is at risk without declared months."""
    _seed_natural_person_profile(runtime_profile)

    result = _descendiente_add_result(_MELLIZO_BIRTH)

    assert result.exit_code == 0, result.output
    notices = unwrap_envelope_notices(result.output)
    assert not [n for n in notices if n["code"] == "config.profile.descendiente.ambiguous_relacion"]


def test_only_the_newly_added_ambiguous_rows_are_named(runtime_profile: TestRuntimeProfile) -> None:
    """A later `add` call does not re-disclose an earlier row it did not touch."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},RELACION=tutela,MESES_TRABAJO=1-12")

    result = _descendiente_add_result(f"{_MELLIZO_BIRTH},MESES_TRABAJO=1-12")

    assert result.exit_code == 0, result.output
    notices = unwrap_envelope_notices(result.output)
    matching = [n for n in notices if n["code"] == "config.profile.descendiente.ambiguous_relacion"]
    assert matching
    assert matching[0]["context"] == {"indices": "1"}
