"""Regression tests for the modelo / bindings discovery defect cluster.

Drives the real ``aeat`` CLI against an isolated encrypted backend to
pin the modelo / bindings discovery findings reported by the persona
fleet:

* ``work calculate --casilla`` accepts the registry ``number`` and the
  BOE form number shown in the ``casillas`` output, not only the
  canonical dot-path id.
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

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _create_profile() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_303_work_unit() -> str:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303", "--year", "2025", "--period", "1T",
            "--revision", "2023-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


def _create_111_work_unit() -> str:
    """Create a Modelo 111 work unit — fully calculable without any binding."""

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "111", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return _payload(result.output)["work_unit_id"]


# ---------------------------------------------------------------------------
# D1 - numeric / short casilla ids accepted by work calculate
# ---------------------------------------------------------------------------


def test_work_calculate_accepts_registry_number_as_casilla_alias() -> None:
    """``--casilla`` accepts the registry ``number`` shown in the
    ``casillas`` output, not only the canonical dot-path id.

    Modelo 303 casilla ``iva.regularizacion-inversiones`` carries the
    registry number ``regularizacion-inversiones`` (the short form without
    the namespace prefix). Supplying that number resolves to the canonical
    id: the engine does not reject it as an unknown casilla.

    Alias resolution is the pre-engine step under test. The calculation
    succeeds because compensacion-pendiente-anteriores defaults to zero
    for fresh-filer scenarios; the alias resolution surface is
    confirmed by the calculation completing with a draft revision.
    """

    _create_profile()
    work_unit_id = _create_303_work_unit()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "regularizacion-inversiones=10.00",
        ],
    )  # fmt: skip
    # The alias was resolved: the calculation succeeded with a draft revision.
    # An alias-rejection regression would produce "unknown casilla" before reaching the engine.
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert "unknown casilla" not in result.output.lower(), result.output
    assert "borrador" in result.output


def test_work_calculate_rejects_a_genuinely_unknown_casilla_number() -> None:
    """A casilla number that resolves to no casilla still refuses.

    The alias resolution must not turn a typo into a silent no-op: an
    unresolvable key passes through and the engine raises its
    unknown-casilla refusal.
    """

    _create_profile()
    work_unit_id = _create_303_work_unit()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", "9999=10.00",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "9999" in result.output.replace("\n", " ")


# ---------------------------------------------------------------------------
# D2 - bindings list --missing consults the active profile
# ---------------------------------------------------------------------------


def test_bindings_list_missing_drops_profile_resolved_bindings() -> None:
    """``bindings list --missing`` excludes bindings the active profile
    already resolves, so it is a usable "what do I still owe" guide.

    Modelo 100 declares a ``source = "profile"`` binding for the
    tax-residence CCAA. The created profile carries a default CCAA, so
    that binding is resolved and must not appear in the missing set,
    while the unsatisfied previous-filing bindings still do.
    """

    _create_profile()
    full = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", "2024"],
    )
    assert full.exit_code == 0, full.output
    missing = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", "2024", "--missing"],
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


def test_bindings_list_labels_profile_sourced_rows_as_profile_facts() -> None:
    """``bindings list`` must not send operators to ledger work for
    profile-sourced Modelo 100 bindings.

    The registry uses ``source = "profile"`` for profile facts. The CLI
    readiness column should render those rows as ``profile fact``.
    """

    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", "2024"],
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


def test_bindings_list_year_resolves_the_year_covering_revision() -> None:
    """``bindings list --modelo 100 --year 2024`` reports binding ids
    for the 2024 revision, not the latest (2025) revision.

    Modelo 100 carries one revision per renta year; resolving the
    latest revision would emit ``renta-2025-*`` ids that a work unit
    created with ``--year 2024`` then rejects.
    """

    _create_profile()
    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", "2024"],
    )
    assert result.exit_code == 0, result.output
    binding_ids = [line.split("\t")[3] for line in result.output.splitlines() if line.startswith("100\t")]
    assert binding_ids, result.output
    assert all(bid.startswith("renta-2024-") for bid in binding_ids), binding_ids


# ---------------------------------------------------------------------------
# D4 - censo period tokens accepted by every modelo surface
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["alta", "modificacion", "baja"])
def test_work_create_accepts_censo_period_tokens(token: str) -> None:
    """``modelo work create --modelo 036`` accepts every censo period
    token Modelo 036 declares as valid."""

    _create_profile()
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "036", "--year", "2025", "--period", token,
            "--revision", "2025-02-03-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert _payload(result.output)["period"] == token


@pytest.mark.parametrize("token", ["alta", "modificacion", "baja"])
def test_describe_and_casillas_accept_censo_period_tokens(token: str) -> None:
    """``describe`` and ``casillas`` accept the censo period tokens."""

    described = invoke_cached_cli(["app", "modelo", "describe", "036", "--period", token])
    assert described.exit_code == 0, described.output
    casillas = invoke_cached_cli(["app", "modelo", "casillas", "036", "--period", token])
    assert casillas.exit_code == 0, casillas.output


def test_work_create_still_rejects_an_undeclared_censo_token() -> None:
    """An undeclared censo token is still refused with a clear error."""

    _create_profile()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "036", "--year", "2025", "--period", "bogus",
            "--revision", "2025-02-03-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    assert "alta" in flat and "modificacion" in flat and "baja" in flat


def test_work_create_still_accepts_quarterly_tokens() -> None:
    """The censo-token path does not regress quarterly period tokens."""

    _create_profile()
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "303", "--year", "2024", "--period", "1T",
            "--revision", "2023-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert _payload(result.output)["period"] == "1T"


# ---------------------------------------------------------------------------
# D5 - bindings list advertises the engine input channel
# ---------------------------------------------------------------------------


def test_bindings_list_marks_decimal_consumed_typed_enum_binding() -> None:
    """The Modelo 100 estimación-directa binding carries ``typed_enum``
    yet is consumed as a Decimal operand. ``bindings list`` must report
    its ``input_channel`` as ``decimal`` so the operator is not misled
    into supplying an enum value through the binding channel.
    """

    _create_profile()
    result = invoke_cached_cli(
        ["app", "modelo", "bindings", "list", "--modelo", "100", "--year", "2024"],
    )
    assert result.exit_code == 0, result.output
    row = next(line for line in result.output.splitlines() if "estimacion-directa-es-normal" in line)
    columns = row.split("\t")
    # typed_enum column still names the enum; input_channel says decimal.
    assert "EstimacionDirectaModalidad" in columns
    assert columns[-2] == "decimal", row


def test_modelo_readiness_names_preflight_scope() -> None:
    """``readiness`` must not read like filing completeness for manual
    casilla modelos. It reports profile/source preflight readiness.
    """

    _create_profile()
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "111",
            "--revision-id",
            "2019-y-siguientes",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "readiness_scope\tprofile_and_source_preflight_not_manual_casilla_completeness" in result.output


# ---------------------------------------------------------------------------
# F1 - work calculate / work revision lead with a result summary
# ---------------------------------------------------------------------------


def test_work_calculate_leads_with_a_result_summary() -> None:
    """``work calculate`` emits a headline result summary above the
    full casilla table, surfacing the modelo's key computed figures.

    Uses Modelo 111 which is fully calculable without any binding or
    prior-period data — so the test focuses on summary rendering, not
    on calculation inputs.
    """

    _create_profile()
    work_unit_id = _create_111_work_unit()
    result = invoke_cached_cli(
        ["app", "modelo", "work", "calculate", work_unit_id],
    )
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    summary_header_index = next(i for i, line in enumerate(lines) if line.startswith("role\tcasilla\tvalue\tlabel"))
    first_casilla_index = next(i for i, line in enumerate(lines) if line.startswith("casilla\t"))
    # The summary block precedes the full casilla table.
    assert summary_header_index < first_casilla_index
    # The summary surfaces the headline IRPF result casilla.
    assert any(line.startswith("result_ingresar\t30\t") for line in lines), result.output


def test_work_calculate_json_carries_the_result_summary() -> None:
    """The ``work calculate`` JSON payload carries the result summary
    as a typed list of headline rows.

    Uses Modelo 111 which is fully calculable without any binding or
    prior-period data.
    """

    _create_profile()
    work_unit_id = _create_111_work_unit()
    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert result.exit_code == 0, result.output
    summary = _payload(result.output)["result_summary"]
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
            "--modelo", "202", "--year", "2026", "--period", period,
            "--revision", "2025-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["period"] == period
    return payload["work_unit_id"]


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_work_calculate_accepts_modelo_202_pago_fraccionado_periods(period: str) -> None:
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

    _create_profile()
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
            "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores=0",
            "--binding",
            "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior=0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "invalid registry period" not in result.output
    payload = _payload(result.output)
    # The engine ran and persisted a draft calculation revision —
    # the same end stage Modelo 200 / 303 reach.
    assert payload["state"] == "borrador"
    assert payload["calculation_revision_id"]
    assert payload["saved"] is True
    assert payload["casilla_values"], result.output


def test_modelo_202_describe_create_calculate_agree_on_period_tokens() -> None:
    """``describe``, ``work create`` and ``work calculate`` agree on the
    Modelo 202 period tokens.

    Every clave ``describe 202`` lists under ``Periods`` must be
    accepted by both ``work create`` and ``work calculate``; no surface
    may advertise a period the others reject.
    """

    _create_profile()
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
                "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores=0",
                "--binding",
                "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior=0",
            ],
        )
        assert calculated.exit_code == 0, (period, calculated.output)
        assert _payload(calculated.output)["state"] == "borrador"
