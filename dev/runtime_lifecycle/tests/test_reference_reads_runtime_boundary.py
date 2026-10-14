"""Each reference read answers with exactly the JSON its command prints for the same coordinates.

The command line is run as its own process, the way a person runs it, and its
``result`` is compared with what the terminal interface's read returns. Both
call one application service, so a difference here is a difference in the
coordinates one of them passed.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.type_guards import is_str_keyed_dict
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.command_program import CommandProgram
from cadrumo.entrypoints.tui.reference.filters import ReferenceFilterError, filters_of, query_from_form
from cadrumo.entrypoints.tui.reference.reads import (
    ReferenceQuery,
    ReferenceRead,
    ReferenceReadRefusedError,
    read_reference,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REPOSITORY = Path(__file__).resolve().parents[3]
_COMMAND_LINES: Final = {
    CommandProgram.AEAT: "from cadrumo.entrypoints.cli.bootstrap import main; main()",
    CommandProgram.AUTHENTICATION: "from cadrumo_runtime.host.bootstrap import main; main()",
}
_AUTHENTICATION_CASES: Final = frozenset({"auth-providers", "apoderado-scopes"})

_CASES: Final[Mapping[str, tuple[tuple[str, ...], ReferenceQuery]]] = {
    "modelos": (("app", "modelo", "list"), ReferenceQuery(ReferenceRead.MODELOS)),
    "modelos-of-a-year": (
        ("app", "modelo", "list", "--year", "2024"),
        ReferenceQuery(ReferenceRead.MODELOS, year=2024),
    ),
    "modelos-of-a-family": (
        ("app", "modelo", "list", "--domain", "iva"),
        ReferenceQuery(ReferenceRead.MODELOS, domain="iva"),
    ),
    "support-matrix": (("app", "modelo", "support-matrix"), ReferenceQuery(ReferenceRead.SUPPORT_MATRIX)),
    "describe-latest": (("app", "modelo", "describe", "303"), ReferenceQuery(ReferenceRead.DESCRIBE, modelo="303")),
    "describe-by-period": (
        ("app", "modelo", "describe", "036", "--period", "alta"),
        ReferenceQuery(ReferenceRead.DESCRIBE, modelo="036", period="alta"),
    ),
    "describe-scoped": (
        ("app", "modelo", "describe", "303", "--year", "2024", "--period", "1T", "--as-of", "2024-06-30"),
        ReferenceQuery(ReferenceRead.DESCRIBE, modelo="303", year=2024, period="1T", as_of=date(2024, 6, 30)),
    ),
    "casillas-filtered": (
        ("app", "modelo", "casillas", "130", "--input-kind", "bound", "--required"),
        ReferenceQuery(ReferenceRead.CASILLAS, modelo="130", input_kind="bound", required=True),
    ),
    "casillas-scoped": (
        ("app", "modelo", "casillas", "130", "--year", "2024", "--period", "1T", "--number", "01"),
        ReferenceQuery(ReferenceRead.CASILLAS, modelo="130", year=2024, period="1T", casilla_number="01"),
    ),
    "casilla": (
        ("app", "modelo", "casilla", "130", "01", "--year", "2024", "--period", "1T"),
        ReferenceQuery(ReferenceRead.CASILLA, modelo="130", casilla="01", year=2024, period="1T"),
    ),
    "formulas": (
        ("app", "modelo", "formulas", "130", "--year", "2024", "--period", "1T"),
        ReferenceQuery(ReferenceRead.FORMULAS, modelo="130", year=2024, period="1T"),
    ),
    "categories": (("app", "ledger", "categories"), ReferenceQuery(ReferenceRead.CATEGORIES)),
    "portals": (("app", "live", "portals", "list"), ReferenceQuery(ReferenceRead.PORTALS)),
    "portals-of-a-category": (
        ("app", "live", "portals", "list", "--category", "auth"),
        ReferenceQuery(ReferenceRead.PORTALS, category="auth"),
    ),
    "portals-of-a-modelo": (
        ("app", "live", "portals", "list", "--modelo", "303"),
        ReferenceQuery(ReferenceRead.PORTALS, modelo="303"),
    ),
    "portal": (
        ("app", "live", "portals", "view", "portal_sede_root"),
        ReferenceQuery(ReferenceRead.PORTAL, portal="portal_sede_root"),
    ),
    "auth-providers": (("config", "auth", "providers"), ReferenceQuery(ReferenceRead.AUTH_PROVIDERS)),
    "apoderado-scopes": (
        ("config", "auth", "apoderado", "scopes", "list"),
        ReferenceQuery(ReferenceRead.APODERADO_SCOPES),
    ),
}


def _command_envelope(case: str, arguments: tuple[str, ...]) -> dict[str, object]:
    """Run one command as its own process and return the envelope it printed."""
    completed = run_audited_process(
        [
            sys.executable,
            "-c",
            _COMMAND_LINES[CommandProgram.AUTHENTICATION if case in _AUTHENTICATION_CASES else CommandProgram.AEAT],
            "--format",
            "json",
            *arguments,
        ],
        cwd=_REPOSITORY,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=180,
    )
    assert isinstance(completed.stdout, str) and completed.stdout.strip(), (arguments, completed.returncode)
    envelope: object = json.loads(completed.stdout)
    assert is_str_keyed_dict(envelope), arguments
    return envelope


@pytest.fixture(scope="module")
def command_envelopes() -> dict[str, dict[str, object]]:
    """Every case's command, run once for the module."""
    return {case: _command_envelope(case, arguments) for case, (arguments, _query) in _CASES.items()}


def test_every_read_has_a_case() -> None:
    # Bindings have no profile-free command; they are held to the casillas command below.
    assert {query.read for _arguments, query in _CASES.values()} == set(ReferenceRead) - {ReferenceRead.BINDINGS}


@pytest.mark.parametrize("case", sorted(_CASES))
def test_a_read_returns_the_json_its_command_prints(case: str, command_envelopes: dict[str, dict[str, object]]) -> None:
    envelope = command_envelopes[case]
    assert envelope["status"] == "success", envelope

    answer = read_reference(_CASES[case][1])

    assert json.loads(answer.model_dump_json()) == envelope["result"]


def test_the_bindings_read_names_every_source_the_casillas_command_reports(
    command_envelopes: dict[str, dict[str, object]],
) -> None:
    printed = command_envelopes["casillas-filtered"]["result"]
    assert isinstance(printed, dict)
    bound = {row["binding"] for row in printed["rows"] if row["binding"]}
    assert bound

    answer = read_reference(ReferenceQuery(ReferenceRead.BINDINGS, modelo="130"))
    document = json.loads(answer.model_dump_json())

    assert document["code"] == printed["code"] and document["revision"] == printed["revision"]
    assert bound <= {row["binding_id"] for row in document["rows"]}
    scoped = json.loads(
        read_reference(ReferenceQuery(ReferenceRead.BINDINGS, modelo="130", year=2024, period="1T")).model_dump_json()
    )
    assert scoped["filing_year"] == 2024 and scoped["period"] == "1T"
    assert bound <= {row["binding_id"] for row in scoped["rows"]}


@pytest.mark.parametrize(
    "query",
    [
        ReferenceQuery(ReferenceRead.DESCRIBE, modelo="600"),
        ReferenceQuery(ReferenceRead.DESCRIBE, modelo="999"),
        ReferenceQuery(ReferenceRead.DESCRIBE, modelo="130", year=2024, period="9Z"),
        ReferenceQuery(ReferenceRead.PORTAL, portal="portal_that_is_not_catalogued"),
        ReferenceQuery(ReferenceRead.PORTALS, category="auth", modelo="303"),
        ReferenceQuery(ReferenceRead.MODELOS, domain="NOT A FAMILY"),
    ],
)
def test_coordinates_that_name_nothing_are_refused_with_words(query: ReferenceQuery) -> None:
    with pytest.raises(ReferenceReadRefusedError) as refused:
        read_reference(query)

    assert str(refused.value).strip()


def test_a_form_takes_exactly_the_coordinates_its_command_takes() -> None:
    assert [item.name for item in filters_of(ReferenceRead.CASILLAS)] == [
        "modelo",
        "year",
        "period",
        "as_of",
        "input_kind",
        "required",
        "form_number",
        "casilla_number",
    ]
    assert [item.name for item in filters_of(ReferenceRead.MODELOS)] == ["year", "domain"]
    assert [item.name for item in filters_of(ReferenceRead.PORTALS)] == ["category", "modelo"]

    query = query_from_form(
        ReferenceRead.CASILLAS,
        {
            "modelo": " 130 ",
            "year": "2024",
            "period": "1T",
            "as_of": "2024-06-30",
            "input_kind": "bound",
            "required": True,
        },
    )
    assert query == ReferenceQuery(
        ReferenceRead.CASILLAS,
        modelo="130",
        year=2024,
        period="1T",
        as_of=date(2024, 6, 30),
        input_kind="bound",
        required=True,
    )
    assert query_from_form(ReferenceRead.MODELOS, {"year": "", "domain": ""}) == ReferenceQuery(ReferenceRead.MODELOS)


@pytest.mark.parametrize(
    ("read", "values", "faulty"),
    [
        (ReferenceRead.DESCRIBE, {"modelo": ""}, ("modelo",)),
        (ReferenceRead.DESCRIBE, {"modelo": "130", "year": "2024"}, ("period",)),
        (ReferenceRead.DESCRIBE, {"modelo": "130", "year": "next"}, ("year",)),
        (ReferenceRead.DESCRIBE, {"modelo": "130", "as_of": "30/06/2024"}, ("as_of",)),
        (ReferenceRead.CASILLAS, {"modelo": "130", "input_kind": "guessed"}, ("input_kind",)),
        (ReferenceRead.CASILLA, {"modelo": "130"}, ("casilla",)),
        (ReferenceRead.PORTAL, {}, ("portal",)),
    ],
)
def test_a_form_that_does_not_make_a_query_names_the_coordinates_at_fault(
    read: ReferenceRead, values: dict[str, object], faulty: tuple[str, ...]
) -> None:
    with pytest.raises(ReferenceFilterError) as refused:
        query_from_form(read, values)

    assert refused.value.fields == faulty
