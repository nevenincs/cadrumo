"""Regression tests for the modelo / bindings discovery defect cluster.

Drives the real ``cadrumo`` CLI against an isolated encrypted backend to
pin the modelo / bindings discovery findings reported by the persona
fleet:

* ``work calculate --casilla`` refuses registry ``number`` / BOE form
  metadata tokens and requires the canonical casilla id.
* ``bindings list --missing`` consults the active profile and drops
  the bindings it already resolves.
* ``bindings list --year`` (no ``--period``) resolves the revision
  covering that filing year, not the latest revision.
* ``modelo work create`` and the modelo introspection verbs accept the
  censo period tokens (``alta`` / ``modificacion`` / ``baja``) that
  Modelo 036 declares.
* ``bindings list`` reports an ``input_channel`` discriminator so a
  ``typed_enum`` binding consumed as a Decimal operand is not
  mis-advertised as an enum-channel input.
* ``work calculate`` / ``work revision`` lead with a headline result
  summary above the full casilla table.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    open_ended_revision,
    revision_covering,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.entrypoints.cli.tests.modelo_work_scenarios import (
    SCENARIO_FILING_YEAR,
    create_calculable_modelo_work_unit,
    create_m303_work_unit,
)
from cadrumo.entrypoints.cli.tests.ordinary_m303_scenarios import joint_return_options
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FLOOR = filing_year_envelope().floor
# The authored Modelo 210 revision just before the open-ended one: it covers no 3T instalment.
_M210_CLOSED_REVISION = revision_covering("210", open_ended_revision("210").valid_from.year - 1)
# Modelo 130 has one authored revision, so another modelo's revision id is certainly not its law-determined one.
_OTHER_MODELO_REVISION = str(open_ended_revision("180").id)
_HORIZON = filing_year_envelope().horizon


_OPERATOR_FACTS = {
    **native_general_iva_facts(),
    "identity.tax_id": "12345678Z",
    "identity.name": "Operator",
    "identity.surnames": "Operator",
    "activities.description": "design",
    "censo.activity_start_date": date(_FLOOR, 1, 1).isoformat(),
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "tax_residence.ccaa": "madrid",
    # Modelo 111 readiness requires the colegio concertado answer.
    "withholding.colegio_concertado": "false",
}

# The operator pays an employee with retencion, so Modelo 111 applies to the profile.
_EMPLOYER_FACTS = {**_OPERATOR_FACTS, "withholding.has_employees": "true"}

_LEGAL_ENTITY_FACTS = {
    "taxpayer_type.entity_type": "legal_entity",
    "taxpayer_type.legal_entity_form": "sl",
    "identity.tax_id": "B00015016",
    "identity.name": "Company",
    "identity.surnames": "Company SL",
    "identity.legal_name": "Company SL",
    "activities.description": "consulting",
    "taxpayer_type.incn_prior_12_months": "7500000.00",
    "taxpayer_type.new_entity_first_two_profit_periods": "false",
}


def _m303_filing_evidence_args() -> tuple[str, ...]:
    """Answer the 1T ordinary Modelo 303 question so the canonical-casilla gate is reached."""
    return joint_return_options()


# ---------------------------------------------------------------------------
# D1 - printed-number metadata tokens refused by work calculate
# ---------------------------------------------------------------------------


def test_work_calculate_rejects_registry_number_as_casilla_reference(
    seed_profile: ProfileSeeder,
) -> None:
    """``--casilla`` requires canonical ``casilla.id`` values."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    work_unit_id = create_m303_work_unit()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "regularizacion-inversiones=10.00",
            *_m303_filing_evidence_args(),
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    output = result.output.replace("\n", " ")
    assert "not a canonical casilla.id" in output
    assert "iva.regularizacion-inversiones" in output


def test_work_calculate_rejects_a_genuinely_unknown_numeric_casilla_id_candidate(
    seed_profile: ProfileSeeder,
) -> None:
    """A numeric token that resolves to no canonical casilla.id still refuses.

    The canonical-id gate must not turn a typo into a silent no-op.
    """

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    work_unit_id = create_m303_work_unit()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "9999=10.00",
            *_m303_filing_evidence_args(),
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "9999" in result.output.replace("\n", " ")


# ---------------------------------------------------------------------------
# D2 - bindings list --missing consults the active profile
# ---------------------------------------------------------------------------


def test_bindings_list_missing_drops_profile_resolved_bindings(seed_profile: ProfileSeeder) -> None:
    """``bindings list --missing`` excludes bindings the active profile
    already resolves, so it is a usable "what do I still owe" guide.

    Modelo 100 declares a ``source = "profile"`` binding for the
    tax-residence CCAA. The seeded profile declares its CCAA, so
    that binding is resolved and must not appear in the missing set,
    while the unsatisfied previous-filing bindings still do.
    """

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    full = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", str(_FLOOR)],
    )
    assert full.exit_code == 0, full.output
    missing = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", str(_FLOOR), "--missing"],
    )
    assert missing.exit_code == 0, missing.output

    full_ids = {line.split("\t")[3] for line in full.output.splitlines() if line.startswith("100\t")}
    missing_ids = {line.split("\t")[3] for line in missing.output.splitlines() if line.startswith("100\t")}
    # The profile-sourced CCAA binding is resolved and drops out.
    ccaa = next(bid for bid in full_ids if "tax-residence-ccaa" in bid)
    assert ccaa in full_ids
    assert ccaa not in missing_ids
    # The unsatisfied previous-filing bindings remain.
    assert missing_ids, missing.output
    assert missing_ids < full_ids


def test_bindings_list_missing_forwards_as_of_to_profile_readiness(seed_profile: ProfileSeeder) -> None:
    """The missing filter resolves profile readiness at the as-of date."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "100",
            "--year",
            str(_FLOOR),
            "--missing",
            "--as-of",
            date(_FLOOR, 6, 30).isoformat(),
        ],
    )

    assert result.exit_code == 0, result.output
    binding_ids = {line.split("\t")[3] for line in result.output.splitlines() if line.startswith("100\t")}
    assert all("tax-residence-ccaa" not in binding_id for binding_id in binding_ids)


def test_bindings_list_labels_profile_sourced_rows_as_profile_facts(seed_profile: ProfileSeeder) -> None:
    """``bindings list`` must not send operators to ledger work for
    profile-sourced Modelo 100 bindings.

    The registry uses ``source = "profile"`` for profile facts. The CLI
    readiness column should render those rows as ``profile fact``.
    """

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", str(_FLOOR)],
    )
    assert result.exit_code == 0, result.output
    profile_rows = [
        line for line in result.output.splitlines() if line.startswith("100\t") and line.split("\t")[4] == "profile"
    ]
    assert profile_rows, result.output
    assert all(line.split("\t")[5] == "profile fact" for line in profile_rows), profile_rows


# ---------------------------------------------------------------------------
# D3 - bindings list --year resolves the year-covering revision
# ---------------------------------------------------------------------------


def test_bindings_list_year_resolves_the_year_covering_revision(seed_profile: ProfileSeeder) -> None:
    """``bindings list --modelo 100 --year <floor>`` reports the revision the
    floor year's snapshot selects, not the newest authored revision.

    Modelo 100 carries one revision per renta year; resolving the newest
    would list bindings a work unit created for the floor year does not use.
    """

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", str(_FLOOR)],
    )
    assert result.exit_code == 0, result.output
    binding_ids = [line.split("\t")[3] for line in result.output.splitlines() if line.startswith("100\t")]
    assert binding_ids, result.output
    # Binding ids are year-free; the revision column names the covering revision.
    revisions = {line.split("\t")[1] for line in result.output.splitlines() if line.startswith("100\t")}
    assert revisions == {published_snapshot("100", filing_year=_FLOOR, period="0A").revision.id}, revisions


# ---------------------------------------------------------------------------
# D4 - censo registry tokens stay outside filing-period work units
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["alta", "modificacion", "baja"])
def test_work_create_rejects_censo_tokens_as_non_filing_periods(token: str, seed_profile: ProfileSeeder) -> None:
    """``modelo work create`` refuses censo registry tokens because work
    units carry typed filing periods, while Modelo 036 declares event tokens."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "036", "--year", str(_HORIZON), "--period", token,
            "--revision", str(open_ended_revision("036").id),
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    assert f"--period '{token}'" in flat
    assert "is not a valid period token" in flat
    assert "modelo 036" in flat
    assert "alta" in flat and "modificacion" in flat and "baja" in flat


@pytest.mark.parametrize("token", ["alta", "modificacion", "baja"])
def test_describe_and_casillas_accept_censo_period_tokens(token: str) -> None:
    """``describe`` and ``casillas`` accept the censo period tokens."""

    described = invoke_cached_cli(["app", "modelo", "describe", "036", "--period", token])
    assert described.exit_code == 0, described.output
    casillas = invoke_cached_cli(["app", "modelo", "casillas", "036", "--period", token])
    assert casillas.exit_code == 0, casillas.output


def test_work_create_still_rejects_an_undeclared_censo_token(seed_profile: ProfileSeeder) -> None:
    """An undeclared censo token is still refused with a clear error."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "036", "--year", str(_HORIZON), "--period", "bogus",
            "--revision", str(open_ended_revision("036").id),
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    assert "alta" in flat and "modificacion" in flat and "baja" in flat


def test_work_create_still_accepts_quarterly_tokens(seed_profile: ProfileSeeder) -> None:
    """The censo-token path does not regress quarterly period tokens."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303", "--year", str(_FLOOR), "--period", "1T",
            "--revision", str(published_snapshot("303", filing_year=_FLOOR, period="1T").revision.id),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert unwrap_schema_envelope(result.output)["period"] == {"filing_year": _FLOOR, "code": "1T"}


# ---------------------------------------------------------------------------
# D5 - bindings list advertises the engine input channel
# ---------------------------------------------------------------------------


def test_bindings_list_names_the_estimation_modality_as_derived_from_the_profile(
    seed_profile: ProfileSeeder,
) -> None:
    """The Modelo 100 modality binding is read from the profile, so it advertises no decimal encoding to type."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", str(_FLOOR)],
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    row = next(line for line in lines if line.startswith("100	") and "estimacion-directa-es-normal" in line)
    assert row.split("	")[4:6] == ["profile", "profile fact"], row
    assert not any(
        line.startswith("encoded_option	") and "estimacion-directa-es-normal" in line for line in lines
    ), result.output


def test_modelo_readiness_names_preflight_scope(seed_profile: ProfileSeeder) -> None:
    """``readiness`` must not read like filing completeness for manual
    casilla modelos. It reports profile/source preflight readiness.
    """

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "111",
            "--revision-id",
            str(open_ended_revision("111").id),
            "--year",
            str(_HORIZON),
            "--period",
            "1T",
        ],
    )
    assert "readiness_scope\tprofile_and_source_preflight_not_manual_casilla_completeness" in result.output
    # A not-ready scope is reported, and says so through its exit status.
    assert (result.exit_code == 0) == ("ready\tTrue" in result.output.splitlines()), result.output


def test_modelo_readiness_refuses_revision_mismatch(seed_profile: ProfileSeeder) -> None:
    """Readiness resolves the requested revision, not only the modelo/year."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "130",
            "--revision-id",
            _OTHER_MODELO_REVISION,
            "--year",
            str(_HORIZON),
            "--period",
            "1T",
        ],
    )
    # Refused outright, naming both the requested and the law-determined revision.
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = " ".join(result.output.split())
    assert _OTHER_MODELO_REVISION in flat
    assert str(open_ended_revision("130").id) in flat


def test_modelo_readiness_refuses_period_without_registry_coverage(seed_profile: ProfileSeeder) -> None:
    """M210 readiness must fail closed when the requested period is not covered."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "210",
            "--revision-id",
            str(_M210_CLOSED_REVISION.id),
            "--year",
            str(_M210_CLOSED_REVISION.valid_from.year),
            "--period",
            "3T",
        ],
    )
    # Refused outright, naming the uncovered period and the revisions that exist.
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = " ".join(result.output.split())
    assert "3T" in flat
    assert str(open_ended_revision("210").id) in flat


def test_describe_m210_accepts_numbered_event_token_with_year_scope() -> None:
    """M210 describe accepts concrete EVENT-N period instances."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "describe",
            "210",
            "--year",
            str(_HORIZON),
            "--period",
            "EVENT-1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Invalid value" not in result.output
    assert "Modelo\t210" in result.output
    expected_revision = published_snapshot("210", filing_year=_HORIZON, period="EVENT-1").revision.id
    assert f"Revision\t{expected_revision}" in result.output
    assert "Periods\tEVENT-N" in result.output


def test_describe_m210_rejects_legacy_evento_token_with_year_scope() -> None:
    """M210 describe refuses the retired ``evento`` token."""

    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "describe",
            "210",
            "--year",
            str(_HORIZON),
            "--period",
            "evento",
        ],
    )

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "Traceback" not in flat
    assert "EVENT-N" in flat
    assert "Valid tokens: evento" not in flat


def test_bindings_list_m210_legacy_event_token_reports_current_guidance(seed_profile: ProfileSeeder) -> None:
    """The retired M210 ``evento`` token must not be advertised as valid."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "bindings",
            "list",
            "--modelo",
            "210",
            "--year",
            str(_HORIZON),
            "--period",
            "evento",
            "--missing",
        ],
    )

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "EVENT-N" in flat
    assert "Valid tokens: evento" not in flat
    assert "Traceback" not in flat


def test_modelo_readiness_m210_legacy_event_token_reports_current_guidance(seed_profile: ProfileSeeder) -> None:
    """Readiness must not route retired ``evento`` through the M210 work boundary."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "210",
            "--revision-id",
            str(revision_covering("210", _HORIZON).id),
            "--year",
            str(_HORIZON),
            "--period",
            "evento",
        ],
    )

    assert result.exit_code != 0, result.output
    flat = result.output.replace("\n", " ")
    assert "EVENT-N" in flat
    assert "Valid tokens: evento" not in flat
    assert "REFUSED_CLI_BOUNDARY" not in flat
    assert "Traceback" not in flat


def test_modelo_readiness_reports_missing_calculation_bindings(seed_profile: ProfileSeeder) -> None:
    """Blank company facts must keep M200 readiness false before calculate."""

    seed_profile(label="operator", facts=_OPERATOR_FACTS)
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "200",
            "--revision-id",
            str(published_snapshot("200", filing_year=_HORIZON, period="0A").revision.id),
            "--year",
            str(_HORIZON),
            "--period",
            "0A",
        ],
    )
    payload = unwrap_schema_envelope(result.output)
    assert payload["ready"] is False
    # A not-ready scope still reports its payload and says so through its exit status.
    assert result.exit_code != 0, result.output
    assert payload["registry_ready"] is True
    assert payload["binding_ready"] is False
    missing_binding_ids = {row["binding_id"] for row in payload["missing_bindings"]}
    assert {
        "modelo-200-profile-legal-entity-form",
        "modelo-200-profile-new-entity-flag",
        "modelo-200-profile-incn-prior-12-months",
    } <= missing_binding_ids
    missing_sources = {row["source"] for row in payload["missing_bindings"]}
    assert "profile" in missing_sources
    assert "relation_prefill" in missing_sources


def test_modelo_200_legal_entity_readiness_does_not_request_retired_objective_boolean(
    seed_profile: ProfileSeeder,
) -> None:
    """A legal-entity M200 profile must not ask for the retired IRPF objective flag."""

    seed_profile(label="company", facts=_LEGAL_ENTITY_FACTS)
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "200",
            "--revision-id",
            str(published_snapshot("200", filing_year=_HORIZON, period="0A").revision.id),
            "--year",
            str(_HORIZON),
            "--period",
            "0A",
        ],
    )

    # Overall readiness also waits on calculation bindings; the profile half is the subject here.
    payload = unwrap_schema_envelope(result.output)
    assert payload["profile_ready"] is True
    assert "irpf.uses_objective_estimation" not in result.output
    assert "uses_objective_estimation_irpf" not in result.output


# ---------------------------------------------------------------------------
# F1 - work calculate / work revision lead with a result summary
# ---------------------------------------------------------------------------


def test_work_calculate_leads_with_a_result_summary(seed_profile: ProfileSeeder) -> None:
    """``work calculate`` emits a headline result summary above the
    full casilla table, surfacing the modelo's key computed figures.

    Uses Modelo 111 which is fully calculable without any binding or
    prior-period data — so the test focuses on summary rendering, not
    on calculation inputs.
    """

    seed_profile(label="operator", facts=_EMPLOYER_FACTS)
    work_unit_id = create_calculable_modelo_work_unit()
    result = invoke_cached_cli(
        ["app", "modelo", "work", "calculate", work_unit_id],
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    headline = f"result summary Modelo 111 1T {SCENARIO_FILING_YEAR}"
    assert any(line == headline for line in lines), result.output
    assert f"{headline} {SCENARIO_FILING_YEAR}" not in result.output
    summary_header_index = next(i for i, line in enumerate(lines) if line.startswith("role\tcasilla\tvalue\tlabel"))
    first_casilla_index = next(i for i, line in enumerate(lines) if line.startswith("casilla\t"))
    # The summary block precedes the full casilla table.
    assert summary_header_index < first_casilla_index
    # The summary surfaces the headline IRPF result casilla.
    assert any(line.startswith("result_ingresar\t30\t") for line in lines), result.output


def test_work_calculate_json_carries_the_result_summary(seed_profile: ProfileSeeder) -> None:
    """The ``work calculate`` JSON payload carries the result summary
    as a typed list of headline rows.

    Uses Modelo 111 which is fully calculable without any binding or
    prior-period data.
    """

    seed_profile(label="operator", facts=_EMPLOYER_FACTS)
    work_unit_id = create_calculable_modelo_work_unit()
    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert result.exit_code == 0, result.output
    summary = unwrap_schema_envelope(result.output)["result_summary"]
    assert summary, result.output
    assert all({"role", "casilla_id", "value", "label"} <= set(row) for row in summary)
    assert any(row["casilla_id"] == "30" for row in summary)


# ---------------------------------------------------------------------------
# Modelo 202 pago-fraccionado periods calculate end-to-end
# ---------------------------------------------------------------------------


def _create_202_work_unit(period: str) -> str:
    """Create a Modelo 202 work unit for one pago-fraccionado clave."""

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", str(_HORIZON), "--period", period,
            "--revision", str(revision_covering("202", _HORIZON).id),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    assert payload["period"] == {"filing_year": _HORIZON, "code": period}
    work_unit_id = payload["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_work_calculate_accepts_modelo_202_pago_fraccionado_periods(period: str, seed_profile: ProfileSeeder) -> None:
    """``work calculate`` accepts every pago-fraccionado clave Modelo 202
    advertises (``1P`` / ``2P`` / ``3P``).

    ``describe 202`` advertises ``1P``/``2P``/``3P`` and ``work create``
    accepts them, but ``work calculate`` used to reject every one with
    ``invalid registry period '1P'`` — the calculate path's
    period-boundary resolution never learned the IS instalment claves.
    The period token must now resolve end-to-end: the calculation runs
    the registry engine and persists a draft revision, exactly as the
    quarterly and annual modelos already do.
    """

    seed_profile(label="company", facts=_LEGAL_ENTITY_FACTS)
    work_unit_id = _create_202_work_unit(period)
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--binding",
            "modelo-202-pagos-fraccionados-anteriores=0",
            "--binding",
            "modelo-202-cuota-base-ejercicio-anterior=0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "invalid registry period" not in result.output
    payload = unwrap_schema_envelope(result.output)
    # The engine ran and persisted a draft calculation revision —
    # the same end stage Modelo 200 / 303 reach.
    assert payload["state"] == "borrador"
    assert payload["calculation_revision_id"]
    assert payload["saved"] is True
    assert payload["casilla_values"], result.output


def test_modelo_202_describe_create_calculate_agree_on_period_tokens(seed_profile: ProfileSeeder) -> None:
    """``describe``, ``work create`` and ``work calculate`` agree on the
    Modelo 202 period tokens.

    Every clave ``describe 202`` lists under ``Periods`` must be
    accepted by both ``work create`` and ``work calculate``; no surface
    may advertise a period the others reject.
    """

    seed_profile(label="company", facts=_LEGAL_ENTITY_FACTS)
    described = invoke_cached_cli(["app", "modelo", "describe", "202"])
    assert described.exit_code == 0, described.output
    periods_line = next(line for line in described.output.splitlines() if line.startswith("Periods\t"))
    advertised = {token.strip() for token in periods_line.split("\t", 1)[1].split(",")}
    assert advertised == {"1P", "2P", "3P"}, described.output

    for period in sorted(advertised):
        work_unit_id = _create_202_work_unit(period)
        calculated = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                "--binding",
                "modelo-202-pagos-fraccionados-anteriores=0",
                "--binding",
                "modelo-202-cuota-base-ejercicio-anterior=0",
            ],
        )
        assert calculated.exit_code == 0, (period, calculated.output)
        assert unwrap_schema_envelope(calculated.output)["state"] == "borrador"
