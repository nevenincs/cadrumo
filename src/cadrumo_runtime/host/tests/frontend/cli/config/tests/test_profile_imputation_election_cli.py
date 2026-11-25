"""Real-behaviour tests for the income imputation election on ``config profile create`` and ``edit``.

The RIRPF art. 7 criterion is stated per ejercicio, so the setup flow writes it,
and the Codigo de Comercio accounting answer beside it, as facts dated to the
whole stated year. These drive the shipped verbs through the real parser, the
real registration door and the native profile worker, then read the encrypted
record back.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.values import UserProfileRecord

from ...cli_runner import invoke_cached_cli
from .isolated_storage_fixture import (
    CREDENTIAL_INPUT,
    declare_operator_terminal,
    profile_cli,
    profile_persisted_record,
)
from .isolated_storage_fixture import live_cli_profile as live_cli_profile
from .isolated_storage_fixture import native_cli_profile_view as native_cli_profile_view

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]

_CRITERION_PATH = "irpf.activity_income_imputation_criterion"
_ACCOUNTING_PATH = "irpf.codigo_comercio_accounting"
_CRITERION_FLAG = "--irpf-activity-income-imputation-criterion"
_YEAR_FLAG = "--irpf-activity-income-imputation-year"
_EARLY = filing_year_envelope().floor
_LATE = filing_year_envelope().horizon


def _dated(record: UserProfileRecord, path: str) -> list[tuple[date | None, date | None, object]]:
    return sorted(
        ((fact.valid_from, fact.valid_to, fact.value) for fact in record.facts if fact.path == path),
        key=lambda item: item[0] or date.min,
    )


def _ejercicio(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _edit(*flags: str) -> Result:
    return profile_cli("edit", "--quiet", *flags)


def _refusal_code(result: Result) -> str:
    assert result.exit_code != 0, result.output
    # A refused command writes its error envelope to stderr.
    document = json.loads(result.stderr)
    assert document["status"] == "error", result.output
    return str(document["error"]["code"])


def _status(result: Result) -> str:
    assert result.exit_code == 0, result.output
    return str(json.loads(result.stdout)["result"]["status"])


def test_create_stores_the_election_dated_to_its_ejercicio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    declare_operator_terminal(monkeypatch)
    with override_settings(
        cadrumo_storage_root=tmp_path / "cadrumo-storage", cadrumo_secret_passphrase=CREDENTIAL_INPUT
    ):
        created = invoke_cached_cli(
            (
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "Elector",
                "--quiet",
                "--secrets-stdin",
                _CRITERION_FLAG,
                "cobros_y_pagos",
                _YEAR_FLAG,
                str(_LATE),
                "--no-irpf-codigo-comercio-accounting",
            ),
            input=json.dumps({"passphrase": CREDENTIAL_INPUT, "passphrase_confirmation": CREDENTIAL_INPUT}),
        )
        assert created.exit_code == 0, created.output
        assert json.loads(created.stdout)["result"]["status"] == "created"

        record = profile_persisted_record()

    assert _dated(record, _CRITERION_PATH) == [(*_ejercicio(_LATE), "cobros_y_pagos")]
    assert _dated(record, _ACCOUNTING_PATH) == [(*_ejercicio(_LATE), False)]


def test_create_refuses_a_criterion_without_its_ejercicio_and_creates_nothing(tmp_path: Path) -> None:
    with override_settings(
        cadrumo_storage_root=tmp_path / "cadrumo-storage", cadrumo_secret_passphrase=CREDENTIAL_INPUT
    ):
        refused = invoke_cached_cli(
            (
                "--format",
                "json",
                "config",
                "profile",
                "create",
                "Undated",
                "--quiet",
                "--secrets-stdin",
                _CRITERION_FLAG,
                "devengo",
            ),
            input=json.dumps({"passphrase": CREDENTIAL_INPUT, "passphrase_confirmation": CREDENTIAL_INPUT}),
        )
        assert _refusal_code(refused) == "REFUSED_WIZARD_MISSING_FLAG"
        assert _YEAR_FLAG in refused.output
        listed = invoke_cached_cli(("--format", "json", "config", "profile", "list"))

    assert "Undated" not in listed.output


@pytest.mark.usefixtures("native_cli_profile_view")
def test_edit_states_one_ejercicio_and_keeps_the_others_and_the_omitted_answers() -> None:
    assert (
        _status(_edit(_CRITERION_FLAG, "devengo", _YEAR_FLAG, str(_EARLY), "--irpf-codigo-comercio-accounting"))
        == "updated"
    )
    assert _status(_edit(_CRITERION_FLAG, "cobros_y_pagos", _YEAR_FLAG, str(_LATE))) == "updated"

    record = profile_persisted_record()
    assert _dated(record, _CRITERION_PATH) == [(*_ejercicio(_EARLY), "devengo"), (*_ejercicio(_LATE), "cobros_y_pagos")]
    # The later run named no accounting answer, so the earlier one is left as stored and none is stated for the later.
    assert _dated(record, _ACCOUNTING_PATH) == [(*_ejercicio(_EARLY), True)]

    # An edit naming none of the election flags leaves every dated election fact as stored.
    assert _status(_edit("--legal-name", "Elector")) == "updated"
    after = profile_persisted_record()
    assert _dated(after, _CRITERION_PATH) == _dated(record, _CRITERION_PATH)
    assert _dated(after, _ACCOUNTING_PATH) == _dated(record, _ACCOUNTING_PATH)


@pytest.mark.usefixtures("native_cli_profile_view")
def test_edit_refuses_a_criterion_outside_the_schema_vocabulary_and_writes_nothing() -> None:
    before = profile_persisted_record()

    refused = _edit(_CRITERION_FLAG, "mixto", _YEAR_FLAG, str(_LATE))

    assert _refusal_code(refused) == "REFUSED_WIZARD_VALIDATION"
    # The accepted tokens are the profile schema's own vocabulary for the field.
    assert json.loads(refused.stderr)["error"]["context"]["choices"] == "cobros_y_pagos, devengo"
    after = profile_persisted_record()
    assert after.record_revision == before.record_revision
    assert not _dated(after, _CRITERION_PATH)


@pytest.mark.usefixtures("native_cli_profile_view")
def test_edit_refuses_a_criterion_without_its_ejercicio_naming_the_flag() -> None:
    before = profile_persisted_record()

    refused = _edit(_CRITERION_FLAG, "devengo")

    assert _refusal_code(refused) == "REFUSED_WIZARD_MISSING_FLAG"
    assert _YEAR_FLAG in refused.output
    after = profile_persisted_record()
    assert after.record_revision == before.record_revision
    assert not _dated(after, _CRITERION_PATH)
