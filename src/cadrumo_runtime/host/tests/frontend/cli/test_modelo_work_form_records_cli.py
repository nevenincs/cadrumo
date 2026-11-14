"""The CLI prints a declaration's saved repeating records from the served form, never assembling them itself.

A repeating record (a descendant, a let property) is stored per row, so the
calculation's casilla values cannot show it. ``aeat app modelo work form``
reads the declaration form through the registered read the workbench and the
window use, and prints each saved record with its row index, the casilla each
value fills and the typed value. A block whose records the form cannot read is
printed as unknown, never as empty, and a declaration the profile does not hold
is refused.

Real ``aeat`` CLI, real runtime supervisor and profile worker, real published
authority, the newest Modelo 100 year the registry's support envelope admits.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
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

_PROFILE_LABEL = "Form records test profile"
_DESCENDANT_BLOCK = "hijo-rows"
#: The casilla of the descendant records that holds the birth date.
_BIRTH_DATE_BOX = "FNACDLG"


def _newest_renta_year(operation: PinnedAuthorityOperation) -> int:
    """The newest Modelo 100 year the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    for year in sorted(support.years, reverse=True):
        try:
            operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        return year
    raise AssertionError("the support envelope admits no Modelo 100 year")


def _activity_start() -> date:
    """A start of activity before every year the support envelope admits, so the activity is under way in each."""
    support = published_supported_filing_years()
    assert support is not None
    return date(min(support.years) - 1, 1, 1)


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
                "censo.activity_start_date": _activity_start().isoformat(),
                "tax_residence.ccaa": "madrid",
                "provenance.source": "manual_cli",
                **{
                    fact.path: str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value)
                    for fact in renta_single_taxpayer_facts(birth_date=date.fromisoformat("1985-06-15"))
                },
            },
        )
        yield profile


def _invoke(args: Sequence[str], *, output_format: str = "json") -> Result:
    """Run one verb against the registered profile, admitted by its password on the secret frame."""
    return cli_runner_invoke_cached_cli(
        ("--profile", _PROFILE_LABEL, "--profile-secrets-stdin", "--format", output_format, *args),
        input=json.dumps({"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}),
    )


def _ok(args: Sequence[str], *, output_format: str = "json") -> Result:
    result = _invoke(args, output_format=output_format)
    assert result.exit_code == 0, (args, result.output)
    return result


def _create(year: int) -> str:
    created = _ok(("app", "modelo", "work", "create", "--modelo", "100", "--year", str(year), "--period", "0A"))
    return str(require_schema_envelope(created.output)["work_unit_id"])


def _state_no_prior_carries(work_unit_id: str) -> None:
    """State every carry family the declaration leaves open as nothing pending, through the door the refusal names."""
    refused = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id, "--yes"))
    assert refused.exit_code == 2, refused.output
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_CHOICE_REQUIRED", refused.output
    families = [family.strip() for family in str(error["context"]["families"]).split(",")]
    chosen = [item for family in families for item in ("--family", family)]
    stated = require_schema_envelope(
        _ok(("app", "modelo", "work", "attest-prior-carries", work_unit_id, *chosen, "--yes")).output
    )
    assert stated["applied"] is True


def _blocks(work_unit_id: str) -> dict[str, dict[str, Any]]:
    form = require_schema_envelope(_ok(("app", "modelo", "work", "form", work_unit_id)).output)
    assert form["work_unit_id"] == work_unit_id
    return {str(block["block_id"]): block for block in form["blocks"]}


def _lines(work_unit_id: str) -> list[list[str]]:
    text = _ok(("app", "modelo", "work", "form", work_unit_id), output_format="text").output
    return [line.split("	") for line in text.splitlines()]


@pytest.mark.usefixtures("runtime_profile")
def test_a_saved_descendant_record_is_printed_with_its_row_index_and_casilla(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = _newest_renta_year(authority_operation)
    birth = date(year - 10, 4, 2).isoformat()
    _ok(("config", "profile", "descendiente", "add", "--descendiente", f"NACIMIENTO={birth}"))
    work_unit_id = _create(year)
    _state_no_prior_carries(work_unit_id)

    lines = _lines(work_unit_id)

    assert ["block", _DESCENDANT_BLOCK, "known", "1"] in lines
    assert ["record", _DESCENDANT_BLOCK, "1", _BIRTH_DATE_BOX, birth] in lines
    block = _blocks(work_unit_id)[_DESCENDANT_BLOCK]
    assert block["rows_known"] is True
    assert block["rows_unknown_words"] is None
    (record,) = block["records"]
    assert record["index"] == 1
    birth_value = next(value for value in record["values"] if value["casilla_id"] == _BIRTH_DATE_BOX)
    assert (birth_value["kind"], birth_value["value"]) == ("string", birth), birth_value
    assert _BIRTH_DATE_BOX in {column["casilla_id"] for column in block["columns"]}


@pytest.mark.usefixtures("runtime_profile")
def test_a_declaration_not_yet_calculated_prints_every_block_as_unknown_never_as_empty(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit_id = _create(_newest_renta_year(authority_operation))

    lines = _lines(work_unit_id)

    blocks = _blocks(work_unit_id)
    assert _DESCENDANT_BLOCK in blocks
    for block_id, block in blocks.items():
        assert block["rows_known"] is False, block_id
        assert block["records"] == []
        assert block["rows_unknown_words"]
        assert ["block", block_id, "unknown", block["rows_unknown_words"]] in lines
    assert not any(line[0] in {"record", "record_column"} for line in lines)
    assert not any(line[:1] == ["block"] and line[2] == "known" for line in lines)


@pytest.mark.usefixtures("runtime_profile")
def test_a_declaration_the_profile_does_not_hold_is_a_registered_refusal(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    _create(_newest_renta_year(authority_operation))
    missing = "0" * 64

    refused = _invoke(("app", "modelo", "work", "form", missing))

    assert refused.exit_code == 2, refused.output
    error = require_error_document(refused.output)["error"]
    assert error["category"] == "REFUSED", error
    assert '"record' not in refused.output
