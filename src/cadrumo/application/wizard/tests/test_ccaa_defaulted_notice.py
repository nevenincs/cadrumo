"""Real-behavior tests for the defaulted-comunidad-autónoma disclosure notice.

The wizard descriptor defaults ``tax-residence-ccaa`` to Madrid for a
resident-IRPF profile. On the non-interactive create paths that default is
otherwise applied silently, so a taxpayer who never chose a comunidad has
their autonomic deductions and autonomic tax scale computed for Madrid
without any signal. These tests pin that the create flow surfaces a
``warning``-severity :class:`~cadrumo.core.json_contract.Notice`
(``config.profile.create.ccaa_defaulted``) exactly when the CCAA was
assumed, and stays silent when the operator explicitly names a comunidad —
including an explicit Madrid.

The behavioural tests drive the real ``create`` command through real
isolated secure storage (no mocks, no stubs); the message and severity are
derived from the locale authority and the :class:`Notice` model, never
hardcoded.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import click
import pytest
import typer

from ....core.i18n import tr
from ....core.json_contract import NoticeSeverity
from ....domain.contribuyente import CCAA
from ....tests.secure_sql import isolated_profile_storage_root
from .._catalogue import SETUP_FLOW
from .._commands import _emit_wizard_success, build_wizard_command
from .._persistence import WizardPersistMode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A resident-IRPF quiet create that omits ``--tax-residence-ccaa``. Fiscal
# residency defaults to RESIDENT_IRPF, so the CCAA question is visible and
# takes its Madrid default — the silent-default case this notice targets.
_RESIDENT_QUIET_ARGS: list[str] = [
    "--quiet",
    "--tax-id",
    "00000000T",
    "--entity-type",
    "natural_person",
    "--name",
    "Operator",
    "--surnames",
    "Tester",
    "--activity",
    "Servicios",
]

_CCAA_DEFAULTED_MESSAGE = tr("application.wizard.notices.ccaa_defaulted", ccaa=CCAA.MADRID.value)
_CCAA_DEFAULTED_CODE = "config.profile.create.ccaa_defaulted"


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _wizard_app(mode: WizardPersistMode) -> typer.Typer:
    app = typer.Typer()
    app.command()(build_wizard_command(SETUP_FLOW, mode=mode))
    return app


def _invoke_create(profile_name: str, extra_args: Sequence[str], capsys: pytest.CaptureFixture[str]) -> str:
    command = typer.main.get_command(_wizard_app("create"))
    command.main(args=[profile_name, *_RESIDENT_QUIET_ARGS, *extra_args], standalone_mode=False)
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def test_notice_fires_when_ccaa_is_defaulted_to_madrid(
    _isolated_backend: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A resident create that omits the CCAA flag discloses the Madrid assumption."""
    output = _invoke_create("operator-defaulted", (), capsys)
    assert _CCAA_DEFAULTED_MESSAGE in output


def test_notice_silent_when_operator_explicitly_chooses_madrid(
    _isolated_backend: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicitly choosing Madrid is a deliberate choice — no disclosure notice."""
    output = _invoke_create(
        "operator-explicit-madrid",
        ["--tax-residence-ccaa", CCAA.MADRID.value],
        capsys,
    )
    assert _CCAA_DEFAULTED_MESSAGE not in output


def test_notice_silent_when_operator_chooses_other_comunidad(
    _isolated_backend: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Naming a non-Madrid comunidad is an explicit choice — no disclosure notice."""
    output = _invoke_create(
        "operator-explicit-cataluna",
        ["--tax-residence-ccaa", CCAA.CATALUNA.value],
        capsys,
    )
    assert _CCAA_DEFAULTED_MESSAGE not in output


@pytest.fixture
def _json_context() -> Iterator[None]:
    """Activate a Click context that requests ``--format json`` output.

    Mirrors the probe the production root callback populates so
    ``_emit_wizard_success`` renders the real JSON envelope; a direct call
    keeps this contract assertion independent of the persistence stack.
    """
    with click.Context(click.Command("probe"), obj={"json": True}):
        yield


def test_json_envelope_carries_defaulted_ccaa_warning_notice(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """The disclosure rides the shared ``notices`` channel as a warning Notice."""
    _emit_wizard_success("create", "probe-profile", ccaa_defaulted=True)

    document = json.loads(capsys.readouterr().out)
    result = document["result"]
    assert "ccaa_defaulted" not in result
    assert not any(key.endswith("_advisory") for key in result)

    codes = {notice["code"]: notice for notice in document["notices"]}
    assert _CCAA_DEFAULTED_CODE in codes
    warning = codes[_CCAA_DEFAULTED_CODE]
    assert warning["severity"] == NoticeSeverity.WARNING.value
    assert warning["message"] == _CCAA_DEFAULTED_MESSAGE
    assert warning["context"] == {"assumed_ccaa": CCAA.MADRID.value}


def test_json_envelope_omits_notice_when_ccaa_not_defaulted(
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """No disclosure notice is emitted when the CCAA was not defaulted."""
    _emit_wizard_success("create", "probe-profile", ccaa_defaulted=False)

    document = json.loads(capsys.readouterr().out)
    codes = {notice["code"] for notice in document["notices"]}
    assert _CCAA_DEFAULTED_CODE not in codes
