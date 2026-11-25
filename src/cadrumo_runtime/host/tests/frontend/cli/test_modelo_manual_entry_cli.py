"""A filer enters one value of a declaration by hand from the CLI, and it keeps every other value.

``set-value`` types a value into a box the filer fills; ``override`` states an
input in place of an earlier return that is not stored. Unconfirmed, each shows
the value as the box reads it and records nothing; with ``--yes`` it applies
through the guarded edit, and the next entry keeps the first. An address the
declaration does not let the filer type on is refused with words, before
anything is staged.

Real ``aeat`` CLI, real runtime supervisor and profile worker, real published
authority, a Modelo 130 of the support envelope's horizon year.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.cli_envelope import require_schema_envelope

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli as cli_runner_invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_LABEL = "Manual entry test profile"
#: The previous year's net income from the economic activity, read from the earlier Modelo 100 (box 13 of a 130).
_PRIOR_NET_INCOME = "irpf.previous_year_economic_activity_net_income"
#: A box of the Modelo 130 the filer fills.
_FILLED_BOX = "16"
#: A box the Modelo 130 calculates from other boxes.
_COMPUTED_BOX = "13"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
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
                "censo.activity_start_date": date(filing_year_envelope().horizon - 10, 1, 1).isoformat(),
                "tax_residence.ccaa": "madrid",
                "provenance.source": "manual_cli",
            },
        )
        yield profile


def _invoke(args: Sequence[str]) -> Result:
    """Run one verb against the registered profile in English, admitted by its password on the secret frame."""
    return cli_runner_invoke_cached_cli(
        ("--profile", _PROFILE_LABEL, "--profile-secrets-stdin", "--format", "json", *args, "--language", "en"),
        input=json.dumps({"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}),
    )


def _create_130() -> str:
    year = filing_year_envelope().horizon
    created = _invoke(("app", "modelo", "work", "create", "--modelo", "130", "--year", str(year), "--period", "1T"))
    assert created.exit_code == 0, created.output
    return str(require_schema_envelope(created.output)["work_unit_id"])


def _revision(revision_id: str) -> dict[str, Any]:
    stored = _invoke(("app", "modelo", "work", "revision", revision_id))
    assert stored.exit_code == 0, stored.output
    return require_schema_envelope(stored.output)


@pytest.mark.usefixtures("runtime_profile")
def test_an_override_and_a_typed_box_are_recorded_one_at_a_time_and_kept_together() -> None:
    work_unit_id = _create_130()

    # Unconfirmed, the command reads the value through the box's grammar and records nothing.
    shown = _invoke(("app", "modelo", "work", "override", work_unit_id, _PRIOR_NET_INCOME, "8,000.00"))
    assert shown.exit_code == 0, shown.output
    preview = require_schema_envelope(shown.output)
    assert preview["applied"] is False
    assert preview["intent"] == "set_override_value"
    assert preview["binding_id"] == _PRIOR_NET_INCOME
    assert preview["casilla_id"] is None
    assert preview["value_text"]
    assert preview["receipt_id"] is None

    overridden = _invoke(("app", "modelo", "work", "override", work_unit_id, _PRIOR_NET_INCOME, "8,000.00", "--yes"))
    assert overridden.exit_code == 0, overridden.output
    applied = require_schema_envelope(overridden.output)
    assert applied["applied"] is True
    assert applied["receipt_id"]
    revision = _revision(str(applied["calculation_revision_id"]))
    assert Decimal(str(revision["binding_overrides"][_PRIOR_NET_INCOME])) == Decimal("8000.00")
    # A previous-year net income of 9,000 euros or less reduces the payment by the full 100 euros.
    assert Decimal(str(revision["casilla_values"][_COMPUTED_BOX])) == Decimal("100")

    typed = _invoke(("app", "modelo", "work", "set-value", work_unit_id, _FILLED_BOX, "150.00", "--yes"))
    assert typed.exit_code == 0, typed.output
    entered = require_schema_envelope(typed.output)
    assert entered["applied"] is True
    assert entered["intent"] == "set_typed_value"
    assert entered["casilla_id"] == _FILLED_BOX
    both = _revision(str(entered["calculation_revision_id"]))
    assert Decimal(str(both["casilla_values"][_FILLED_BOX])) == Decimal("150.00")
    # The second entry kept the first.
    assert Decimal(str(both["binding_overrides"][_PRIOR_NET_INCOME])) == Decimal("8000.00")


@pytest.mark.usefixtures("runtime_profile")
def test_an_address_the_filer_cannot_type_on_or_a_value_that_cannot_be_read_is_refused_with_words() -> None:
    work_unit_id = _create_130()

    computed = _invoke(("app", "modelo", "work", "set-value", work_unit_id, _COMPUTED_BOX, "10.00", "--yes"))
    assert computed.exit_code == 2, computed.output
    assert computed.output.strip()

    unreadable = _invoke(
        ("app", "modelo", "work", "override", work_unit_id, _PRIOR_NET_INCOME, "eight thousand", "--yes")
    )
    assert unreadable.exit_code == 2, unreadable.output

    # The previous year's net income is a figure, never a carry the registry lets the filer state as nothing.
    not_attestable = _invoke(("app", "modelo", "work", "attest-no-amount", work_unit_id, _PRIOR_NET_INCOME, "--yes"))
    assert not_attestable.exit_code == 2, not_attestable.output

    revisions = _invoke(("app", "modelo", "work", "revisions", work_unit_id))
    assert revisions.exit_code == 0, revisions.output
    assert require_schema_envelope(revisions.output)["revision_count"] == 0


@pytest.mark.usefixtures("runtime_profile")
def test_a_prior_figure_whose_earlier_return_is_held_nowhere_is_stated_and_recorded_as_stated() -> None:
    work_unit_id = _create_130()

    # Unconfirmed, the statement is read through the input's grammar and nothing is recorded.
    shown = _invoke(("app", "modelo", "work", "attest-prior-value", work_unit_id, _PRIOR_NET_INCOME, "8,000.00"))
    assert shown.exit_code == 0, shown.output
    preview = require_schema_envelope(shown.output)
    assert preview["applied"] is False
    assert preview["intent"] == "attest_prior_value"
    assert preview["binding_id"] == _PRIOR_NET_INCOME
    assert preview["value_text"]
    assert preview["receipt_id"] is None

    stated = _invoke(
        ("app", "modelo", "work", "attest-prior-value", work_unit_id, _PRIOR_NET_INCOME, "8,000.00", "--yes")
    )
    assert stated.exit_code == 0, stated.output
    applied = require_schema_envelope(stated.output)
    assert applied["applied"] is True
    assert applied["receipt_id"]
    revision = _revision(str(applied["calculation_revision_id"]))
    assert Decimal(str(revision["binding_overrides"][_PRIOR_NET_INCOME])) == Decimal("8000.00")


@pytest.mark.usefixtures("runtime_profile")
def test_a_prior_figure_that_cannot_be_read_is_refused_with_words_before_anything_is_staged() -> None:
    work_unit_id = _create_130()

    unreadable = _invoke(
        ("app", "modelo", "work", "attest-prior-value", work_unit_id, _PRIOR_NET_INCOME, "eight thousand", "--yes")
    )
    assert unreadable.exit_code == 2, unreadable.output
    assert unreadable.output.strip()

    revisions = _invoke(("app", "modelo", "work", "revisions", work_unit_id))
    assert revisions.exit_code == 0, revisions.output
    assert require_schema_envelope(revisions.output)["revision_count"] == 0
