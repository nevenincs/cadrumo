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

from ....application.user_profile import UserProfileLifecycleRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from .envelope_helpers import unwrap_envelope_notices
from .envelope_helpers import unwrap_schema_envelope as _payload

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
# 0611, which has no formula and is written by the shortcut layer alone.
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
        schema_id="cadrumo.user_profile",
        schema_version=1,
        profile_id=_PROFILE_ID,
        display_name="Maternidad meses arrival test profile",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(path="identity.name", value="Marta"),
            UserProfileFact(path="identity.surnames", value="Diaz Ortega"),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="provenance.source", value="manual_cli"),
            UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
            UserProfileFact(path="filing_export.declaration_type", value="1"),
        ),
    )
    UserProfileLifecycleRepository(bucket_id=_PROFILE_ID, objects=runtime_profile.repository).save(record)


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
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=12",
        f"{_MELLIZO_BIRTH},MESES_TRABAJO=12",
    )

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == _ORACLE_TWO_MELLIZOS_TWELVE_MONTHS


def test_one_hijo_twelve_months_reaches_the_manual_per_hijo_figure(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The same example's per-hijo line, isolated: one child, twelve months, 1.200."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=12")

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
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=6")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("600")


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
    _declare("NACIMIENTO=2015-04-01,MESES_TRABAJO=12")

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


def test_an_eligible_child_does_not_raise_the_withheld_advisory(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The advisory must fire on the state it names and not on the healthy one."""
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=12")

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
    _declare("NACIMIENTO=2021-04-15,MESES_TRABAJO=12")

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
    _declare("NACIMIENTO=2016-03-02,RELACION=adoptado,INSCRIPCION=2021-11-15,MESES_TRABAJO=12")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("1000")


def test_no_month_before_the_adoption_reaches_the_casilla(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The over-grant this Step removes, driven through the surface an operator uses.

    Born January 2024 and adopted in October. The under-three limb runs from the
    BIRTH month for every relacion, so unioning the two limbs granted January to
    September -- months before the child was hers -- and the casilla resolved to
    1.200 where 300 is due. Three eligible months at the authority's 100 euros.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2024-01-10,RELACION=adoptado,INSCRIPCION=2024-10-05,MESES_TRABAJO=12")

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
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=12,RENTAS=99999")

    exit_code, output = _calculate()

    assert exit_code == 0, output
    assert _casilla_0611(output) == Decimal("0")
    assert "maternidad_meses_withheld" in _advisory_kinds(output)


# ---------------------------------------------------------------------------
# One authority per filing.
# ---------------------------------------------------------------------------


def test_the_flag_and_the_declared_records_together_are_refused(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Two channels for one figure is the defect this campaign spent its length removing.

    The calculate-time flag carries a free-form hijo id that no descendant record
    answers to, so the two cannot be reconciled -- and silently preferring either
    would substitute one operator's number for the other's without saying so.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare(f"{_MELLIZO_BIRTH},MESES_TRABAJO=12")

    exit_code, output = _calculate("--meses-trabajo-con-hijo-menor-3", "0=12")

    assert exit_code != 0, output
    assert "meses_madre_trabajo" in output


def test_the_flag_alone_still_reaches_the_casilla(runtime_profile: TestRuntimeProfile) -> None:
    """A profile declaring no months leaves the flag as the sole authority, unchanged."""
    _seed_natural_person_profile(runtime_profile)
    _declare(_MELLIZO_BIRTH)

    exit_code, output = _calculate("--meses-trabajo-con-hijo-menor-3", "0=12")

    assert exit_code == 0, output
    assert _casilla_0611(output) == _ORACLE_ONE_HIJO_TWELVE_MONTHS


def test_a_withheld_declaration_and_the_flag_together_are_also_refused(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The silent branch: a wholly-withheld profile declaration must not let the flag win quietly.

    This descendant is over three, so every one of its declared months is
    withheld (``pairs`` is empty) -- but the profile still DECLARES real
    months. Keying the refusal on the post-eligibility-filter ``pairs``
    instead of the pre-filter ``declares_meses`` let this exact case fall
    through: no refusal (``pairs`` was falsy) and no advisory (the flag's
    presence suppressed it), so the operator's declared record silently lost
    to the flag with nothing said. Same shape as
    ``test_the_flag_and_the_declared_records_together_are_refused`` above, one
    limb over.
    """
    _seed_natural_person_profile(runtime_profile)
    _declare("NACIMIENTO=2015-04-01,MESES_TRABAJO=12")

    exit_code, output = _calculate("--meses-trabajo-con-hijo-menor-3", "0=12")

    assert exit_code != 0, output
    assert "meses_madre_trabajo" in output
