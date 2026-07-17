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
from ....domain.calculations.registry import RegistrySnapshot, resolve_parameter
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

    # No undeclared-descendientes advisory: the profile explicitly declared one.
    notices = unwrap_envelope_notices(calc_result.output)
    undeclared = [
        n for n in notices if n["code"] == "modelo.work.calculate.source_advisory" and "0513" in n.get("message", "")
    ]
    assert undeclared == [], f"declared descendientes must not trigger the undeclared-facts advisory; got {undeclared}"


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
