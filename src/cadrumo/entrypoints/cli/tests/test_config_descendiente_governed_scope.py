"""The descendiente verbs run inside the authority scope that dispatch opens.

Parsing a ``--descendiente`` row reads the registry's disability grades and the
relación default, and the stored rows are validated against the same
authority. Every other descendiente test runs under a test-level authority
lease, which lent the command a scope the command never opened, so a real
invocation refused with the catch-all "must declare NACIMIENTO" text on a row
that declared it.

These tests invoke the real CLI with no enclosing governed-fact scope, so the
scope the command runs under is proven to come from the CLI itself.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import load_settings
from ....domain.calculations.registry.governed_fact_scope import outside_governed_fact_validation
from ....tests.cli_envelope import require_error_document, unwrap_schema_envelope
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="CLI descendant mutation requires native Windows workers"),
]

_PROFILE_LABEL = "Descendiente governed scope test profile"
_ROW = "NACIMIENTO=2018-04-01,DISCAPACIDAD=0,CONVIVENCIA=true"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    with native_cli_profile_scope(tmp_path) as profile:
        yield profile


def _seed_profile(runtime_profile: NativeCliProfileFixture) -> None:
    """Seed a natural-person profile; the seed itself may lease the authority."""
    runtime_profile.register(
        label=_PROFILE_LABEL,
        facts={
            "identity.name": "Ana",
            "identity.surnames": "Perez",
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "provenance.source": "manual_cli",
        },
    )


def _cli(*args: str) -> tuple[int, str]:
    with outside_governed_fact_validation():
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "--profile",
                _PROFILE_LABEL,
                "--profile-secrets-stdin",
                "config",
                "profile",
                "descendiente",
                *args,
            ],
            input=json.dumps(
                {"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}
            ),
        )
    return result.exit_code, result.output


def test_add_and_remove_open_their_own_authority_scope(runtime_profile: NativeCliProfileFixture) -> None:
    """A well-formed row is accepted and removed with no borrowed scope."""
    _seed_profile(runtime_profile)

    added_code, added = _cli("add", "--descendiente", _ROW)
    assert added_code == 0, added
    assert unwrap_schema_envelope(added)["total"] == 1

    removed_code, removed = _cli("remove", "0")
    assert removed_code == 0, removed
    assert unwrap_schema_envelope(removed)["total"] == 0


def test_a_row_missing_its_birth_date_still_refuses_without_a_borrowed_scope(
    runtime_profile: NativeCliProfileFixture,
) -> None:
    """Opening the scope must not loosen the parser: NACIMIENTO stays required."""
    _seed_profile(runtime_profile)

    code, output = _cli("add", "--descendiente", "DISCAPACIDAD=0")

    assert code == 2, output
    assert "NACIMIENTO" in output


def test_a_refusal_about_another_key_does_not_claim_the_birth_date_is_missing(
    runtime_profile: NativeCliProfileFixture,
) -> None:
    """A row that declares NACIMIENTO is refused for the key that is actually wrong."""
    _seed_profile(runtime_profile)

    code, output = _cli("add", "--descendiente", "NACIMIENTO=2018-04-01,DISCAPACIDAD=bogus")

    assert code == 2, output
    assert "NACIMIENTO=YYYY" not in output
    assert require_error_document(output)["error"]["context"]["key"] == "DISCAPACIDAD"
