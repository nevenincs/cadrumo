"""End-to-end coverage for the #515 descendiente entry surface (Option A).

Commit ``092a4f263`` rebound Modelo 100 casillas 0513/0514 (mínimo por
descendientes) from manual to ``input_kind = computed`` across every 2020-2025
revision, deriving the Art. 58/61 LIRPF aggregate from the active profile's
``renta_family.descendiente.{n}.*`` facts. No live production surface wrote those
facts before this module: ``aeat config profile descendiente add`` closes that gap.

This module drives the real ``cadrumo`` CLI end to end against an isolated real-session
backend (``isolated_cli_runtime_profile``) — no mocks, no monkeypatched backend:

* ``test_descendiente_add_then_calculate_computes_the_registry_tranche`` declares one
  descendant via the new CLI command, calculates a Modelo 100 revision, and asserts
  casilla ``0513`` equals the registry's own first-tranche parameter (not a
  hand-duplicated literal — ``no-tautological-calculation-tests``).
* ``test_undeclared_descendientes_advisory_fires_when_0513_is_zero`` proves the
  companion non-blocking advisory (`no-silent-under-declaration`) surfaces when a
  profile with NO declared descendiente facts resolves 0513 to zero, and that it
  does NOT fire once a descendant has been declared (even if 0513 lands on the
  same zero for an ineligible child) — an explicit declaration is not a silent gap.
* ``test_descendiente_add_rejects_a_malformed_flag`` and
  ``test_descendiente_remove_rejects_an_out_of_range_index`` cover the CLI's
  input-validation refusals.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.user_profile import UserProfileLifecycleRepository
from ....domain.calculations.registry import FormulaExpression, RegistrySnapshot, resolve_parameter
from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from ....tests.cli_runner import invoke_cached_cli
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from .envelope_helpers import unwrap_envelope_notices
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-000000515001"
_ESTATAL_CASILLA_ID = "0513"

# Every profile/relation-sourced binding a minimal M100 2024 calculate needs
# besides the descendiente facts under test, mirroring the fixture in
# ``application/modelo/tests/test_actions.py``. Deliberately EXCLUDES
# ``renta-2024-profile-minimo-descendientes-estatal`` -- that binding is the
# exact aggregate this module's calculate engine derives from the declared
# descendiente facts; overriding it here would make the assertions tautological.
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


def _binding_flags_without(*binding_ids: str) -> tuple[str, ...]:
    """The required-binding flags with the named bindings' ``--binding`` PAIRS dropped.

    Pair-aware on purpose. The flags are a flat alternating tuple, so filtering
    by substring removes the ``id=value`` element and leaves its ``--binding``
    behind — which then swallows the NEXT pair's value and the one after it
    arrives as an unexpected positional argument.
    """
    kept: list[str] = []
    pairs = zip(_REQUIRED_2024_BINDING_FLAGS[::2], _REQUIRED_2024_BINDING_FLAGS[1::2], strict=True)
    for flag, assignment in pairs:
        if any(assignment.startswith(f"{binding_id}=") for binding_id in binding_ids):
            continue
        kept.extend((flag, assignment))
    return tuple(kept)


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="Descendiente entry surface test profile",
    ) as profile:
        yield profile


def _seed_natural_person_profile(runtime_profile: TestRuntimeProfile) -> None:
    """Seed the minimum facts an M100 work-unit applicability guard requires."""
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        schema_version=1,
        profile_id=_PROFILE_ID,
        display_name="Descendiente entry surface test profile",
        status=UserProfileStatus.ACTIVE,
        facts=(
            UserProfileFact(path="identity.name", value="Ana"),
            UserProfileFact(path="identity.surnames", value="Perez"),
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


def _registry_first_tranche(year: int) -> Decimal:
    from ....core.resources import resources

    snapshot: RegistrySnapshot = resources().modelos.authority.snapshot("100", filing_year=year, period="0A")
    by_id = {p.id: p for p in snapshot.revision.parameters}
    param = by_id[f"renta-{year}-minimo-descendientes-primer-hijo-{year}"]
    return resolve_parameter(param, {"filing_period": date(year, 12, 31)})


# ---------------------------------------------------------------------------
# End-to-end: declare via the new CLI surface -> calculate -> 0513 is correct.
# ---------------------------------------------------------------------------


def test_descendiente_add_then_calculate_computes_the_registry_tranche(
    runtime_profile: TestRuntimeProfile,
) -> None:
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2015-04-01",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output
    add_payload = _payload(add_result.output)
    assert add_payload["added"] == 1
    assert add_payload["total"] == 1

    list_result = invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "list"])
    assert list_result.exit_code == 0, list_result.output
    list_payload = _payload(list_result.output)
    assert list_payload["total"] == 1
    assert list_payload["descendientes"][0]["birth_date"] == "2015-04-01"

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_REQUIRED_2024_BINDING_FLAGS,
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output
    calc_payload = _payload(calc_result.output)

    expected = _registry_first_tranche(2024)
    actual = Decimal(str(calc_payload["casilla_values"][_ESTATAL_CASILLA_ID]))
    assert actual == expected, (
        f"casilla 0513 must equal the registry first-tranche parameter {expected}; got {actual}. "
        f"Full casilla_values keys sample: {list(calc_payload['casilla_values'])[:20]}"
    )

    # Advisory assertions are made per SOURCE KIND, not over every advisory
    # mentioning 0513. The broader form asserted that a declared descendant
    # raises NOTHING about that casilla, which was true only while one advisory
    # existed; a later, correct advisory on the same casilla then failed a test
    # whose own message names a different one.
    notices = unwrap_envelope_notices(calc_result.output)
    advisories = [n for n in notices if n["code"] == "modelo.work.calculate.source_advisory"]
    kinds = {n.get("context", {}).get("source_kind") for n in advisories}

    # The declared descendant is exactly what this advisory exists NOT to fire on.
    assert "minimo_descendientes_undeclared" not in kinds, (
        f"declared descendientes must not trigger the undeclared-facts advisory; got {advisories}"
    )

    # And the end-to-end proof that an advisory reaches an operator at all: this
    # descendant was entered with no RENTAS figure, so the Art. 58.1 / Art. 61
    # norma 2a disclosure must arrive through the real CLI envelope rather than
    # only through a collector call. Nothing else in the suite drives that path.
    assert "minimo_descendientes_rentas_undeclared" in kinds, (
        f"a descendant declared without a rentas figure must raise the disclosure; got {advisories}"
    )


# ---------------------------------------------------------------------------
# Advisory: no-silent-under-declaration when 0513 = 0 and nothing is declared.
# ---------------------------------------------------------------------------


def test_undeclared_descendientes_advisory_fires_when_0513_is_zero(
    runtime_profile: TestRuntimeProfile,
) -> None:
    _seed_natural_person_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")

    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_REQUIRED_2024_BINDING_FLAGS,
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output
    calc_payload = _payload(calc_result.output)
    assert Decimal(str(calc_payload["casilla_values"][_ESTATAL_CASILLA_ID])) == Decimal("0")

    notices = unwrap_envelope_notices(calc_result.output)
    fired = [
        n
        for n in notices
        if n["code"] == "modelo.work.calculate.source_advisory"
        and n.get("context", {}).get("source_kind") == "minimo_descendientes_undeclared"
    ]
    assert len(fired) == 1, f"expected exactly one undeclared-descendientes advisory; got notices={notices}"
    assert "descendiente add" in fired[0]["message"]


def test_declared_but_ineligible_descendant_does_not_fire_the_advisory(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A profile that declared a descendant who happens to be ineligible (age 30,
    no discapacidad) still resolves 0513 to zero -- but the declaration itself
    means this is not a silent gap, so the advisory must not fire."""
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=1990-01-01",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_REQUIRED_2024_BINDING_FLAGS,
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output
    calc_payload = _payload(calc_result.output)
    assert Decimal(str(calc_payload["casilla_values"][_ESTATAL_CASILLA_ID])) == Decimal("0")

    notices = unwrap_envelope_notices(calc_result.output)
    fired = [
        n
        for n in notices
        if n["code"] == "modelo.work.calculate.source_advisory"
        and n.get("context", {}).get("source_kind") == "minimo_descendientes_undeclared"
    ]
    assert fired == [], f"a declared (even if ineligible) descendant must not fire the advisory; got {fired}"


# ---------------------------------------------------------------------------
# CLI input validation
# ---------------------------------------------------------------------------


def test_descendiente_add_rejects_a_malformed_flag(runtime_profile: TestRuntimeProfile) -> None:
    _seed_natural_person_profile(runtime_profile)

    result = invoke_cached_cli(
        [
            "config", "profile", "descendiente", "add",
            "--descendiente", "DISCAPACIDAD=50",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "NACIMIENTO" in result.output


def test_descendiente_remove_rejects_an_out_of_range_index(runtime_profile: TestRuntimeProfile) -> None:
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2018-01-01",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    remove_result = invoke_cached_cli(["config", "profile", "descendiente", "remove", "5"])
    assert remove_result.exit_code != 0, remove_result.output


def test_descendiente_remove_drops_the_row_and_recomputes_to_zero(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """After removing the only declared descendant, 0513 reverts to zero.

    ``remove`` rewrites the profile's ``renta_family.descendientes_count`` fact to
    ``"0"`` (never leaves a stale higher-index row behind), which is itself an
    EXPLICIT declaration of zero descendants -- so the undeclared-facts advisory
    must NOT fire here, unlike the never-touched-the-surface case covered by
    ``test_undeclared_descendientes_advisory_fires_when_0513_is_zero``.
    """
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2015-04-01",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    remove_result = invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "remove", "0"])
    assert remove_result.exit_code == 0, remove_result.output
    remove_payload = _payload(remove_result.output)
    assert remove_payload["total"] == 0

    list_result = invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert _payload(list_result.output)["total"] == 0

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_REQUIRED_2024_BINDING_FLAGS,
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output
    calc_payload = _payload(calc_result.output)
    assert Decimal(str(calc_payload["casilla_values"][_ESTATAL_CASILLA_ID])) == Decimal("0")

    notices = unwrap_envelope_notices(calc_result.output)
    fired = [
        n
        for n in notices
        if n["code"] == "modelo.work.calculate.source_advisory"
        and n.get("context", {}).get("source_kind") == "minimo_descendientes_undeclared"
    ]
    assert fired == [], f"an explicit descendientes_count=0 (written by remove) must not fire the advisory; got {fired}"


# ---------------------------------------------------------------------------
# End-to-end: the Art. 81.2 monthly guardería map, declared to calculated.
# ---------------------------------------------------------------------------


def test_monthly_guarderia_map_declared_via_the_flag_reaches_casilla_0613(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The whole surface, operator-side: declare a month map, calculate, see 0613.

    Every layer below has its own test, and each of them could pass while the
    operator still got nothing — the domain rules landed first with no way to
    write the field, and the calculate path carried a second aggregation that
    read only the annual figure. This drives the real CLI end to end so the
    claim being made is the one an operator can check.

    The child turns three in April, so Art. 81.2 admits only the months after
    the birthday. The expected figure is the arithmetic of the declared months
    themselves (three months at 200), capped by the registry's own per-child
    ceiling — never a re-derivation of the 0613 formula, which is why the cap
    term and the cotización are pinned high enough not to bind.
    """
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA_MENSUAL=1-4:150;5-7:200",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    # The declared map round-trips through the JSON transport as typed rows,
    # expanded and month-sorted regardless of the ranges typed above.
    list_payload = _payload(invoke_cached_cli(["--format", "json", "config", "profile", "descendiente", "list"]).output)
    months = list_payload["descendientes"][0]["gastos_guarderia_mensuales"]
    assert [(row["month"], row["amount_euros"]) for row in months] == [
        (1, 150),
        (2, 150),
        (3, 150),
        (4, 150),
        (5, 200),
        (6, 200),
        (7, 200),
    ]

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            # The guardería spend binding is deliberately NOT overridden here:
            # it is the aggregate this test exists to prove the engine derives
            # from the declared months. The cotización is set well above the
            # post-birthday total so it cannot be what the min() picks.
            *_binding_flags_without(
                "renta-2024-profile-guarderia-gastos-reales",
                "renta-2024-profile-cotizaciones-ss-madre",
            ),
            "--binding", "renta-2024-profile-cotizaciones-ss-madre=5000",
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output
    calc_payload = _payload(calc_result.output)

    # Only May, June and July fall after the April birthday: 3 x 200.
    assert Decimal(str(calc_payload["casilla_values"]["0613"])) == Decimal("600.00")


def test_an_annual_only_figure_in_the_turning_three_period_is_disclosed_not_silent(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The zero an operator would otherwise have to explain to themselves.

    An annual total spans the birthday and cannot be apportioned, so it counts
    nothing — correctly. What makes that defensible rather than a silent
    under-declaration is the advisory arriving on the same calculate, naming the
    child and the key that states the months.
    """
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA=2400",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_binding_flags_without(
                "renta-2024-profile-guarderia-gastos-reales",
                "renta-2024-profile-cotizaciones-ss-madre",
            ),
            "--binding", "renta-2024-profile-cotizaciones-ss-madre=5000",
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output
    assert Decimal(str(_payload(calc_result.output)["casilla_values"]["0613"])) == Decimal("0.00")

    fired = [
        n
        for n in unwrap_envelope_notices(calc_result.output)
        if n.get("context", {}).get("source_kind") == "guarderia_spend_needs_monthly_detail"
    ]
    assert len(fired) == 1, f"the shape advisory must reach the operator; notices were {fired}"
    assert "GASTOS_GUARDERIA_MENSUAL" in fired[0]["message"]


def test_the_flag_refuses_both_spend_shapes_for_one_child(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """One spend authority per child, refused at the door the operator uses.

    Reconciling two figures would mean choosing one silently, and whichever was
    chosen the other would sit in the record contradicting it.
    """
    _seed_natural_person_profile(runtime_profile)

    result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA=2400,GASTOS_GUARDERIA_MENSUAL=5-7:200",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    assert "GASTOS_GUARDERIA_MENSUAL" in result.output


def test_the_cotizaciones_term_binds_the_0613_cap(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The mother's SS cotizaciones is a real term of the cap, and it must BIND.

    Art. 81.2 caps the increase at ``min(gastos_reales, hijos x 1.000,
    cotizaciones_ss_madre)``. A test that only ever lets the spend term win would
    pass against a formula that dropped the cotizaciones argument entirely, so
    this pins the case where cotizaciones is the smallest of the three and is
    therefore what the operator receives.

    This assertion previously existed only against a domain-layer method that
    duplicated the formula in Python and had no production consumer. Deleting
    that method without replacing this would have left a real term's behaviour
    asserted nowhere, while every gate stayed green — so the replacement lands in
    the same change as the deletion, never after it.

    The expected figure is the cotizaciones input itself, not a re-derivation of
    the formula: the whole claim is that the smallest term is what comes out.
    """
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            # Spend of 2.400 across a child under three all year, so the spend
            # term is 2400 and the population term is 1 x 1000 = 1000.
            "--descendiente", "NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=2400",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_binding_flags_without(
                "renta-2024-profile-guarderia-gastos-reales",
                "renta-2024-profile-cotizaciones-ss-madre",
            ),
            # The smallest of the three terms, so it is the one that must win.
            "--binding", "renta-2024-profile-cotizaciones-ss-madre=450",
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output

    assert Decimal(str(_payload(calc_result.output)["casilla_values"]["0613"])) == Decimal("450.00")


def test_the_population_term_binds_the_0613_cap(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The per-child ceiling is the other term that must be able to win.

    With spend and cotizaciones both above it, the result is the population
    count times the registry's own per-child ceiling. Pinned for the same reason
    as the cotizaciones case: a formula that dropped this argument would still
    satisfy every test in which the spend term happened to be smallest.
    """
    _seed_natural_person_profile(runtime_profile)

    add_result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2022-06-01,GASTOS_GUARDERIA=2400",
        ],
    )  # fmt: skip
    assert add_result.exit_code == 0, add_result.output

    work_unit_id = create_modelo_work_unit_via_cli(modelo="100", filing_year=2024, period="0A", revision="2024")
    calc_result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "calculate", work_unit_id,
            *_binding_flags_without(
                "renta-2024-profile-guarderia-gastos-reales",
                "renta-2024-profile-cotizaciones-ss-madre",
            ),
            "--binding", "renta-2024-profile-cotizaciones-ss-madre=5000",
        ],
    )  # fmt: skip
    assert calc_result.exit_code == 0, calc_result.output

    # One eligible child, so the population term is the registry's per-child
    # ceiling once. Read from the registry rather than restated here.
    assert Decimal(str(_payload(calc_result.output)["casilla_values"]["0613"])) == _registry_guarderia_per_child_cap()


def _registry_guarderia_per_child_cap() -> Decimal:
    """The Art. 81.2 per-child ceiling as the live 0613 formula carries it.

    Read off the formula rather than restated, so a revision that moved the
    ceiling moves this expectation with it instead of reddening a test that was
    right about the law and stale about the figure.
    """
    from ....core.resources import resources

    snapshot = resources().modelos.authority.snapshot("100", filing_year=2024, period="0A")
    formula = next(f for f in snapshot.revision.formulas if f.target_casilla_id == "0613")
    literals = _literals_in(formula.expression)
    assert len(literals) == 1, f"expected exactly one literal in the 0613 formula; found {literals}"
    return Decimal(literals[0])


def _literals_in(node: FormulaExpression) -> list[str]:
    """Collect every ``literal`` value in a compiled formula expression tree.

    Walks the typed :class:`FormulaExpression` the registry compiles to, not a
    raw mapping: reading the TOML shape instead would make this assert against
    the authoring form rather than the one the engine evaluates.
    """
    found = [] if node.literal is None else [str(node.literal)]
    for child in node.args:
        found.extend(_literals_in(child))
    return found


# ---------------------------------------------------------------------------
# Canonical-record refusals reach the operator translated, not as a traceback.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_a_record_level_refusal_is_translated_in_every_catalogue(
    runtime_profile: TestRuntimeProfile,
    locale: str,
) -> None:
    """The coherence rules this Phase shipped must reach the operator as themselves.

    The ``--descendiente`` flag has two families of guard. The parser's own
    pre-validations raise the typed answer error, which this verb has always
    translated. The canonical record's validators raise through pydantic, and
    that arm was unhandled.

    It did NOT produce a traceback — the boundary has a catch-all that projected
    it to a generic translated refusal. The defect is subtler and was measured
    rather than assumed: the operator got "validation failed" in their own
    language while the validator's sentence, which names the conflicting field
    and both ways out, was discarded on the way. Careful copy existed and nobody
    ever saw it.

    Driven through the real CLI rather than by calling the parser, because the
    parser was never the broken part: the gap was between what it raised and what
    the verb caught. Parametrised over all four catalogues because a refusal that
    resolves in one locale and not another is the same class one step out.
    """
    _seed_natural_person_profile(runtime_profile)

    result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            # A tutela guardian carrying an adoption anchor: entitling for the
            # tranches, excluded from the Art. 58.2 increase, and refused by the
            # record precisely so the excluded case cannot claim it.
            "--descendiente", "NACIMIENTO=2015-01-01,RELACION=tutela,INSCRIPCION=2020-01-01",
            # The language option belongs to the verb, not the root. Placed at
            # the root it is refused as an unknown option -- which this test
            # caught by failing loudly on the wrong refusal rather than passing.
            "--output-language", locale,
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    # The refusal, not a traceback: no exception class name and no pydantic
    # apparatus reaches the operator.
    assert "ValidationError" not in result.output
    assert "Traceback" not in result.output
    assert "For further information visit" not in result.output
    # And the validator's own sentence does, naming the field and the conflict.
    assert "inscripcion_registro_civil_date" in result.output
    assert "tutela" in result.output


def test_a_record_level_refusal_does_not_echo_the_operators_record(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The refusal must not repeat the record under construction back at the operator.

    A pydantic error carries an ``input`` echo of every field it was validating.
    On this surface those are a taxpayer's family facts, and the unhandled arm
    wrote them to the error log — birth date, relación and cohabitation in clear,
    with only the NIF redacted. Catching the refusal before the boundary is what
    stops that, so this pins the operator-facing half and the log line goes with
    it.
    """
    _seed_natural_person_profile(runtime_profile)

    result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2015-01-01,RELACION=tutela,INSCRIPCION=2020-01-01",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    assert "input_value" not in result.output
    assert "datetime.date" not in result.output


def test_the_parser_refusal_family_still_translates(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The arm that already worked must keep working.

    Widening the caught set is exactly the change that quietly reroutes an
    existing refusal through the new arm, so the original family is pinned too.
    """
    _seed_natural_person_profile(runtime_profile)

    result = invoke_cached_cli(
        [
            "--format", "json",
            "config", "profile", "descendiente", "add",
            "--descendiente", "NACIMIENTO=2015-01-01,DISCAPACIDAD=50",
        ],
    )  # fmt: skip

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "DISCAPACIDAD" in result.output
