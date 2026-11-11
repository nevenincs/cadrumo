"""Installed ascendant and stated-empty household CLI mutations through the verified profile worker."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import load_settings
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from ...cli_runner import invoke_cached_cli
from .isolated_storage_fixture import native_profile_view_server, profile_persisted_facts

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_NIF = "12345678Z"
_REFUSED_NIF = "99999999A"


def _household_cli(family: str, *args: str, label: str, passphrase: str):
    return invoke_cached_cli(
        ("--format", "json", "--profile", label, "--profile-secrets-stdin", "config", "profile", family, *args),
        input=json.dumps({"profile_passphrase": passphrase}),
    )


def _list(run: Callable[..., Any]) -> dict[str, Any]:
    listed = run("list")
    assert listed.exit_code == 0, listed.output
    return unwrap_schema_envelope(listed.output)


def _assert_unknown_then_stated_empty(run: Callable[..., Any], label: str) -> None:
    never_asked = _list(run)
    assert (never_asked["state"], never_asked["total"], never_asked["ascendientes"]) == ("unknown", 0, [])

    stated = run("add", "--none")
    assert stated.exit_code == 0, stated.output
    assert unwrap_schema_envelope(stated.output) == {"profile": label, "added": 0, "total": 0, "none_declared": True}
    stated_empty = _list(run)
    assert (stated_empty["state"], stated_empty["stated_count"], stated_empty["total"]) == ("none_declared", "0", 0)
    assert profile_persisted_facts()["renta_family.ascendientes_count"] == "0"


def _assert_refusals_change_nothing(run: Callable[..., Any]) -> None:
    for refused in (
        run("add"),
        run("add", "--none", "--ascendiente", "NACIMIENTO=1948-03-04"),
        run("add", "--ascendiente", f"NIF={_NIF}"),
        run("add", "--ascendiente", "NACIMIENTO=1948-03-04,NOMBRE=Ana"),
        run("add", "--ascendiente", f"NACIMIENTO=1948-03-04,NIF={_REFUSED_NIF}"),
    ):
        assert refused.exit_code != 0, refused.output
        assert _REFUSED_NIF not in refused.output
    assert _list(run)["state"] == "none_declared"


def _assert_rows_round_trip(run: Callable[..., Any], label: str) -> None:
    added = run(
        "add",
        "--ascendiente",
        f"NACIMIENTO=1948-03-04,NIF={_NIF},CONVIVIENTES=1",
        "--ascendiente",
        "NACIMIENTO=1951-11-30,FALLECIMIENTO=2025-02-01",
    )
    assert added.exit_code == 0, added.output
    assert unwrap_schema_envelope(added.output) == {"profile": label, "added": 2, "total": 2, "none_declared": False}
    listed = _list(run)
    assert (listed["state"], listed["total"]) == ("rows", 2)
    first, second = listed["ascendientes"]
    assert [first["birth_date"], second["birth_date"]] == ["1948-03-04", "1951-11-30"]
    # Output redaction pseudonymises a tax identifier; the stored value is checked from the facts.
    assert first["nif"].startswith("sha256:") and _NIF not in first["nif"]
    assert (first["convivientes"], second["death_date"]) == (1, "2025-02-01")
    assert profile_persisted_facts()["renta_family.ascendiente.0.nif"] == _NIF

    # Appending rewrites the whole set, so the stored identifier must survive the round trip.
    third = run("add", "--ascendiente", "NACIMIENTO=1940-01-01")
    assert third.exit_code == 0, third.output
    assert unwrap_schema_envelope(third.output)["total"] == 3
    assert profile_persisted_facts()["renta_family.ascendiente.0.nif"] == _NIF
    assert run("remove", "2").exit_code == 0


def _assert_none_closed_then_removal_restates_empty(run: Callable[..., Any], label: str) -> None:
    assert run("add", "--none").exit_code == 2
    assert _list(run)["total"] == 2

    assert run("remove", "5").exit_code == 2
    removed = run("remove", "0")
    assert removed.exit_code == 0, removed.output
    assert unwrap_schema_envelope(removed.output) == {"profile": label, "removed_index": 0, "total": 1}
    assert run("remove", "0").exit_code == 0
    emptied = _list(run)
    assert (emptied["state"], emptied["total"]) == ("none_declared", 0)


def test_ascendants_are_added_listed_and_removed_with_a_stated_empty_state(tmp_path: Path) -> None:
    """A never-asked household is unknown, `--none` states it empty, rows close it, and removal restates it."""
    label = "Ascendant operator"
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        register_cli_profile(label=label, log_in=False)
        passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()

        def run(*args: str):
            return _household_cli("ascendiente", *args, label=label, passphrase=passphrase)

        with native_profile_view_server(root):
            _assert_unknown_then_stated_empty(run, label)
            _assert_refusals_change_nothing(run)
            _assert_rows_round_trip(run, label)
            _assert_none_closed_then_removal_restates_empty(run, label)

        facts = profile_persisted_facts()
        assert facts["renta_family.ascendientes_count"] == "0"
        assert not any(path.startswith("renta_family.ascendiente.") for path in facts)


def test_descendants_can_be_stated_empty_without_touching_the_ascendants(tmp_path: Path) -> None:
    """`--none` on descendiente stores the descendant zero only, and never overwrites a stored child."""
    label = "Descendant none operator"
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        register_cli_profile(label=label, log_in=False)
        passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()

        def run(*args: str):
            return _household_cli("descendiente", *args, label=label, passphrase=passphrase)

        with native_profile_view_server(root):
            before = unwrap_schema_envelope(run("list").output)
            assert before["state"] == "unknown"

            stated = run("add", "--none")
            assert stated.exit_code == 0, stated.output
            assert unwrap_schema_envelope(stated.output)["none_declared"] is True
            assert unwrap_schema_envelope(run("list").output)["state"] == "none_declared"
            assert run("add").exit_code != 0
            assert run("add", "--none", "--descendiente", "NACIMIENTO=2015-04-01").exit_code != 0

            assert run("add", "--descendiente", "NACIMIENTO=2015-04-01").exit_code == 0
            assert run("add", "--none").exit_code == 2
            assert unwrap_schema_envelope(run("list").output)["state"] == "rows"

        facts = profile_persisted_facts()
        assert facts["renta_family.descendientes_count"] == "1"
        assert "renta_family.ascendientes_count" not in facts
