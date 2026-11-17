"""A first Modelo 100 with no earlier return and no statement is refused, never failed, and the CLI states it.

The carries of the negative general bases pending from the four previous
ejercicios (Ley 35/2006 art. 50.3) are unknown while no earlier return is held.
Calculating without the filer's statement that none is pending must settle as a
registered refusal with no effect, worded for the filer by the boxes the form
prints, never as an engine failure naming a raw binding. The refusal names the
command that makes the statement, which records nothing until it is confirmed.

Real ``aeat`` CLI, real runtime supervisor and profile worker, real published
authority, every Modelo 100 year the registry's support envelope admits.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.core.absence_attestation_family import AbsenceAttestationFamily
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

_PROFILE_LABEL = "Prior carry refusal test profile"
#: The carries of the negative general base pending from the four previous ejercicios.
_PENDING_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: Each statement family's carries, as the registry declares them, and the opening boxes the form
#: prints for them (Anexo C.3 for the savings balances, by origin year em1..em4).
_FAMILY_CARRIES: dict[AbsenceAttestationFamily, tuple[tuple[str, ...], tuple[str, ...]]] = {
    AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING: (_PENDING_CARRIES, ("1380", "1382", "1385", "1388")),
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING: (
        tuple(f"renta-saldo-negativo-rcm-ahorro-{origin}-pendiente-inicio" for origin in ("em1", "em2", "em3", "em4")),
        ("1272", "1274", "1277", "1280"),
    ),
    AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING: (
        tuple(f"renta-saldo-negativo-gyp-ahorro-{origin}-pendiente-inicio" for origin in ("em1", "em2", "em3", "em4")),
        ("1259", "1261", "1264", "1267"),
    ),
}
_EVERY_CARRY = tuple(sorted(carry for carries, _ in _FAMILY_CARRIES.values() for carry in carries))
#: Every open family named, each by its own ``--family``, as the command's family door prints them.
_EVERY_FAMILY = tuple(arg for family in sorted(_FAMILY_CARRIES) for arg in ("--family", family.value))


def _renta_years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    assert admitted
    return tuple(admitted)


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
                "censo.activity_start_date": "2015-01-01",
                "tax_residence.ccaa": "madrid",
                "provenance.source": "manual_cli",
                # A complete single filer with no dependants, so once the carries are stated
                # the declaration has nothing else left to answer.
                **{
                    fact.path: str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value)
                    for fact in renta_single_taxpayer_facts(birth_date=date.fromisoformat("1985-06-15"))
                },
            },
        )
        yield profile


def _invoke(args: Sequence[str]) -> Result:
    """Run one verb against the registered profile, admitted by its password on the secret frame."""
    return cli_runner_invoke_cached_cli(
        ("--profile", _PROFILE_LABEL, "--profile-secrets-stdin", "--format", "json", *args),
        input=json.dumps({"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}),
    )


@pytest.mark.usefixtures("runtime_profile")
def test_calculate_without_the_statement_is_a_refusal_naming_every_open_carry_for_every_year(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    for year in _renta_years(authority_operation):
        created = _invoke(("app", "modelo", "work", "create", "--modelo", "100", "--year", str(year), "--period", "0A"))
        assert created.exit_code == 0, created.output
        work_unit_id = require_schema_envelope(created.output)["work_unit_id"]

        refused = _invoke(("app", "modelo", "work", "calculate", work_unit_id))

        assert refused.exit_code == 2, (year, refused.output)
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED", (year, refused.output)
        context = error["context"]
        assert context["terminal_condition"] == "refused"
        assert context["effect"] == "none"
        # The refusal names one open family at a time: its boxes, from the carries it names.
        (evidence,) = error["action"]["evidence"]
        open_carries = tuple(evidence["values"]["open_carries"].split(","))
        (boxes,) = [boxes for carries, boxes in _FAMILY_CARRIES.values() if tuple(sorted(carries)) == open_carries]
        message = error["message"]
        assert str(year) in message
        assert all(box in message for box in boxes), message
        # The filer reads boxes, never the registry's binding identifiers.
        assert not any(binding_id in message for binding_id in _EVERY_CARRY), message
        assert "binding_id" not in context
        action = error["action"]
        assert action["failed_condition_id"] == "modelo.work.calculate.prior_carries.stated"
        assert action["action"]["action_id"] == "operator.modelo.work.attest_prior_carries"
        assert action["action"]["target_command_key"] == "modelo.work.attest_prior_carries"
        assert action["action"]["cli_path"] == ["aeat", "app", "modelo", "work", "attest-prior-carries"]
        bound = {item["argument_name"]: item["value"] for item in action["argument_bindings"]}
        assert bound == {"work_unit_id": work_unit_id}
        assert evidence["values"]["work_unit_id"] == work_unit_id


def _create(year: int) -> str:
    created = _invoke(("app", "modelo", "work", "create", "--modelo", "100", "--year", str(year), "--period", "0A"))
    assert created.exit_code == 0, created.output
    return str(require_schema_envelope(created.output)["work_unit_id"])


@pytest.mark.usefixtures("runtime_profile")
def test_the_statement_the_refusal_names_lets_the_declaration_calculate_for_every_year(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    for year in _renta_years(authority_operation):
        work_unit_id = _create(year)
        assert _invoke(("app", "modelo", "work", "calculate", work_unit_id)).exit_code == 2

        # Unconfirmed, the command shows the served statement and its check, and states nothing.
        # Several families are open, so the statement must name each of them.
        unnamed = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id))
        assert unnamed.exit_code == 2, (year, unnamed.output)
        unnamed_code = require_error_document(unnamed.output)["error"]["code"]
        assert unnamed_code == "REFUSED_MODELO_PRIOR_CARRY_FAMILY_CHOICE_REQUIRED", unnamed.output
        shown = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id, *_EVERY_FAMILY))
        assert shown.exit_code == 0, (year, shown.output)
        preview = require_schema_envelope(shown.output)
        assert preview["applied"] is False
        statements = {statement["family"]: statement for statement in preview["statements"]}
        assert set(statements) == {family.value for family in _FAMILY_CARRIES}
        for family, (carries, _) in _FAMILY_CARRIES.items():
            statement = statements[family.value]
            assert statement["binding_ids"] == sorted(carries)
            assert statement["statement_words"] and statement["effect_words"]
        still_refused = _invoke(("app", "modelo", "work", "calculate", work_unit_id))
        assert still_refused.exit_code == 2, still_refused.output

        stated = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id, *_EVERY_FAMILY, "--yes"))
        assert stated.exit_code == 0, (year, stated.output)
        applied = require_schema_envelope(stated.output)
        assert applied["applied"] is True
        assert applied["receipt_id"]

        # The guarded apply recalculates with the statement and stores that revision, so the
        # declaration the statement settled is read from the revision the apply stored.
        stored = _invoke(("app", "modelo", "work", "revision", applied["calculation_revision_id"]))
        assert stored.exit_code == 0, (year, stored.output)
        revision = require_schema_envelope(stored.output)
        assert revision["work_unit_id"] == work_unit_id
        assert Decimal(revision["casilla_values"]["1380"]) == 0
        assert {binding_id: Decimal(revision["binding_overrides"][binding_id]) for binding_id in _EVERY_CARRY} == {
            binding_id: Decimal(0) for binding_id in _EVERY_CARRY
        }

        # Stating it again has nothing left to answer.
        again = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id, "--yes"))
        assert again.exit_code == 2, again.output
        assert require_error_document(again.output)["error"]["code"] == "REFUSED_MODELO_PRIOR_CARRY_NOTHING_OPEN"


@pytest.mark.usefixtures("runtime_profile")
def test_a_declaration_with_no_carry_to_state_is_refused(authority_operation: PinnedAuthorityOperation) -> None:
    year = max(_renta_years(authority_operation))
    created = _invoke(("app", "modelo", "work", "create", "--modelo", "130", "--year", str(year), "--period", "1T"))
    assert created.exit_code == 0, created.output
    work_unit_id = require_schema_envelope(created.output)["work_unit_id"]

    refused = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id, "--yes"))

    assert refused.exit_code == 2, refused.output
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_MODELO_PRIOR_CARRY_NOTHING_OPEN"
    assert str(year) in error["message"]
