"""A plain CLI calculate keeps every statement recorded on the declaration; one given inputs names what it drops.

``modelo work calculate`` with no input of its own recalculates from the
declaration's current calculation, so a statement recorded earlier (a stated
absence of carries, a stated earlier-return figure, a typed box) stays in the
new calculation. Given inputs, or ``--inputs-only``, it calculates from exactly
what it is given, and the result warns, in text and JSON alike, of every
recorded statement it did not use. The wizard follows the same rule.

Real ``aeat`` CLI, real runtime supervisor and profile worker, real published
authority, the support envelope's horizon year.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.plain_text import PlainTextOutput

from cadrumo.application.flows import line_frontend
from cadrumo.application.flows.definition import FlowDefinition
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.cli import modelo_work_wizard_cli
from cadrumo.entrypoints.tests.profile_persistence.general_iva_profile_facts_support import renta_single_taxpayer_facts
from cadrumo.tests.cli_envelope import require_error_document, require_schema_envelope

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli as cli_runner_invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_LABEL = "Recorded statements test profile"
#: The Modelo 100 carries of the negative general bases pending from earlier ejercicios.
_PENDING_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: The previous year's net income from the economic activity, read from the earlier Modelo 100 (box 13 of a 130).
_PRIOR_NET_INCOME = "irpf.previous_year_economic_activity_net_income"
#: A box of the Modelo 130 the filer fills.
_FILLED_BOX = "16"
#: The Modelo 130 box the previous year's net income reduces.
_REDUCTION_BOX = "13"
_STATEMENT_NOTICE = "modelo.work.calculate.statement_not_carried"
_SUMMARY_NOTICE = "modelo.work.calculate.statements_not_carried"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    horizon = filing_year_envelope().horizon
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label=_PROFILE_LABEL,
            facts={
                **native_general_iva_facts(),
                "identity.name": "Marta",
                "identity.surnames": "Diaz Ortega",
                "identity.tax_id": "12345678Z",
                "taxpayer_type.irpf_income_categories": "actividad_economica",
                "irpf.estimation_regime": "directa_normal",
                "activities.description": "economic activity",
                # An activity started well before the year, so every carry it reads has a year to come from.
                "censo.activity_start_date": date(horizon - 10, 1, 1).isoformat(),
                "tax_residence.ccaa": "madrid",
                "provenance.source": "manual_cli",
                # A complete single filer, so the Modelo 100 has nothing left to answer once its carries are stated.
                **{
                    fact.path: str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value)
                    for fact in renta_single_taxpayer_facts(birth_date=date(horizon - 40, 6, 15))
                },
            },
        )
        yield profile


def _invoke(args: Sequence[str], *, output_format: str = "json", language_option: str = "--language") -> Result:
    """Run one verb against the registered profile in English, admitted by its password on the secret frame."""
    return cli_runner_invoke_cached_cli(
        (
            "--profile",
            _PROFILE_LABEL,
            "--profile-secrets-stdin",
            "--format",
            output_format,
            *args,
            language_option,
            "en",
        ),
        input=json.dumps({"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}),
    )


def _create(modelo: str, period: str) -> str:
    year = filing_year_envelope().horizon
    created = _invoke(("app", "modelo", "work", "create", "--modelo", modelo, "--year", str(year), "--period", period))
    assert created.exit_code == 0, created.output
    return str(require_schema_envelope(created.output)["work_unit_id"])


def _revision(revision_id: str) -> dict[str, Any]:
    stored = _invoke(("app", "modelo", "work", "revision", revision_id))
    assert stored.exit_code == 0, stored.output
    return require_schema_envelope(stored.output)


def _notices(output: str) -> list[dict[str, Any]]:
    document = json.loads(output)
    notices = document.get("notices") or []
    assert isinstance(notices, list)
    return notices


def _applied_revision(args: Sequence[str]) -> str:
    applied = _invoke(args)
    assert applied.exit_code == 0, applied.output
    envelope = require_schema_envelope(applied.output)
    assert envelope["applied"] is True
    return str(envelope["calculation_revision_id"])


@pytest.mark.usefixtures("runtime_profile")
def test_a_plain_calculate_keeps_the_stated_carries_and_inputs_only_drops_them() -> None:
    work_unit_id = _create("100", "0A")
    # One statement covers every family of earlier-year amounts the year keeps open. Asked
    # without a choice while several are open, the command refuses naming each of them.
    asked = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id))
    if asked.exit_code == 0:
        families = [statement["family"] for statement in require_schema_envelope(asked.output)["statements"]]
    else:
        refusal = require_error_document(asked.output)["error"]
        assert refusal["code"] == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_CHOICE_REQUIRED", asked.output
        families = [family.strip() for family in refusal["context"]["families"].split(",")]
    assert families
    _applied_revision(
        (
            "app",
            "modelo",
            "work",
            "attest-prior-carries",
            work_unit_id,
            *(flag for family in families for flag in ("--family", family)),
            "--yes",
        )
    )

    # No input of its own: the calculation replays the statement the declaration holds.
    recalculated = _invoke(("app", "modelo", "work", "calculate", work_unit_id))

    assert recalculated.exit_code == 0, recalculated.output
    payload = require_schema_envelope(recalculated.output)
    assert Decimal(str(payload["casilla_values"]["1380"])) == 0
    revision = _revision(str(payload["calculation_revision_id"]))
    assert {binding_id: Decimal(str(revision["binding_overrides"][binding_id])) for binding_id in _PENDING_CARRIES} == {
        binding_id: Decimal(0) for binding_id in _PENDING_CARRIES
    }
    assert not [notice for notice in _notices(recalculated.output) if notice["code"] == _STATEMENT_NOTICE]

    # --inputs-only calculates from nothing but what it is given, so the statement is not used
    # and the declaration is refused for it, exactly as before the statement was made.
    inputs_only = _invoke(("app", "modelo", "work", "calculate", work_unit_id, "--inputs-only"))

    assert inputs_only.exit_code == 2, inputs_only.output
    error = require_error_document(inputs_only.output)["error"]
    assert error["code"] == "REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED"
    assert error["context"]["effect"] == "none"


@pytest.mark.usefixtures("runtime_profile")
def test_a_calculate_given_inputs_names_each_recorded_statement_it_did_not_use() -> None:
    work_unit_id = _create("130", "1T")
    _applied_revision(("app", "modelo", "work", "set-value", work_unit_id, _FILLED_BOX, "150.00", "--yes"))
    _applied_revision(
        ("app", "modelo", "work", "attest-prior-value", work_unit_id, _PRIOR_NET_INCOME, "8,000.00", "--yes")
    )

    # A plain calculate keeps the typed box and the stated earlier-return figure.
    kept = _invoke(("app", "modelo", "work", "calculate", work_unit_id))
    assert kept.exit_code == 0, kept.output
    kept_payload = require_schema_envelope(kept.output)
    assert Decimal(str(kept_payload["casilla_values"][_FILLED_BOX])) == Decimal("150.00")
    # A previous-year net income of 9,000 euros or less reduces the payment by the full 100 euros.
    assert Decimal(str(kept_payload["casilla_values"][_REDUCTION_BOX])) == Decimal("100")
    kept_revision = _revision(str(kept_payload["calculation_revision_id"]))
    assert Decimal(str(kept_revision["binding_overrides"][_PRIOR_NET_INCOME])) == Decimal("8000.00")
    assert not [notice for notice in _notices(kept.output) if notice["code"] == _STATEMENT_NOTICE]

    # Given the carry as a plain value, the calculation uses only that: the typed box and the
    # statement that the figure stands for an earlier return are both left out, and named.
    given = _invoke(("app", "modelo", "work", "calculate", work_unit_id, "--binding", f"{_PRIOR_NET_INCOME}=8000.00"))

    assert given.exit_code == 0, given.output
    given_payload = require_schema_envelope(given.output)
    assert _FILLED_BOX not in given_payload["casilla_values"] or Decimal(
        str(given_payload["casilla_values"][_FILLED_BOX])
    ) != Decimal("150.00")
    notices = _notices(given.output)
    assert json.loads(given.output)["status"] == "warning"
    (summary,) = [notice for notice in notices if notice["code"] == _SUMMARY_NOTICE]
    assert summary["severity"] == "warning"
    assert summary["context"]["replaced_calculation_revision_id"] == kept_payload["calculation_revision_id"]
    assert summary["context"]["count"] == "2"
    statements = {
        (notice["context"]["kind"], notice["context"]["subject"]): notice
        for notice in notices
        if notice["code"] == _STATEMENT_NOTICE
    }
    assert set(statements) == {("casilla_value", _FILLED_BOX), ("value_attestation", _PRIOR_NET_INCOME)}
    typed_box = statements[("casilla_value", _FILLED_BOX)]
    assert Decimal(typed_box["context"]["value"]) == Decimal("150.00")
    assert typed_box["context"]["box"] == _FILLED_BOX
    assert typed_box["message"].startswith("Not used: ")
    assert Decimal(statements[("value_attestation", _PRIOR_NET_INCOME)]["context"]["value"]) == Decimal("8000.00")

    # The text output carries the same warnings, one line each.
    _applied_revision(("app", "modelo", "work", "set-value", work_unit_id, _FILLED_BOX, "150.00", "--yes"))
    as_text = _invoke(
        ("app", "modelo", "work", "calculate", work_unit_id, "--binding", f"{_PRIOR_NET_INCOME}=8000.00"),
        output_format="text",
    )
    assert as_text.exit_code == 0, as_text.output
    warnings = [line for line in as_text.output.splitlines() if line.startswith("warning\t")]
    assert any(line.startswith("warning\tNot used: ") and f"box {_FILLED_BOX}" in line for line in warnings), (
        as_text.output
    )


@pytest.mark.usefixtures("runtime_profile")
def test_a_wizard_that_prompts_answers_names_the_recorded_statements_it_did_not_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_unit_id = _create("130", "1T")
    _applied_revision(("app", "modelo", "work", "set-value", work_unit_id, _FILLED_BOX, "150.00", "--yes"))
    _applied_revision(
        ("app", "modelo", "work", "attest-prior-value", work_unit_id, _PRIOR_NET_INCOME, "8,000.00", "--yes")
    )

    # The four manual pages of the Modelo 130 are answered 0 and the review submitted; the
    # follow-up page for the earlier-return figure, which the answers alone do not carry,
    # takes the same figure as a plain value.
    keystrokes = "0\r" * 4 + "\r" + "8000\r\r"
    with create_pipe_input() as pipe:
        pipe.send_text(keystrokes)

        def _headless_line_frontend(definition: FlowDefinition) -> line_frontend.LineFlowFrontend:
            return line_frontend.LineFlowFrontend(definition, input=pipe, output=PlainTextOutput(StringIO()))

        # The wizard's real line frontend, bound to prompt-toolkit's headless terminal adapters.
        monkeypatch.setattr(modelo_work_wizard_cli, "LineFlowFrontend", _headless_line_frontend)
        result = _invoke(("app", "modelo", "work", "wizard", work_unit_id), language_option="--output-language")

    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    assert any(row["key"] == _FILLED_BOX for row in payload["prompted_casillas"])
    notices = _notices(result.output)
    statements = {
        (notice["context"]["kind"], notice["context"]["subject"]): notice
        for notice in notices
        if notice["code"] == "modelo.work.wizard.statement_not_carried"
    }
    assert ("casilla_value", _FILLED_BOX) in statements, notices
    assert Decimal(statements[("casilla_value", _FILLED_BOX)]["context"]["value"]) == Decimal("150.00")
