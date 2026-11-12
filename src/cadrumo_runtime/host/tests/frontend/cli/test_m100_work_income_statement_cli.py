"""The work-income statement has its own command, apart from the carry statement.

A return resting on a work-income payer record needs the employer's contributions and the
protected-estate contribution stated by the filer. That statement is its own command
(``attest-work-income``), because those boxes are income and not an amount carried from an
earlier ejercicio. With no payer record on the return there is no box to state, and the command
refuses before staging anything, in the words of the work-income family.

Real ``aeat`` CLI, real runtime supervisor and profile worker, real published authority.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
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

_PROFILE_LABEL = "Work income statement test profile"
#: The carries the registry declares the statement of absence for.
_PENDING_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
#: The boxes the form prints for those carries.
_CARRY_BOXES = ("1380", "1382", "1385", "1388")


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


_WORK_INCOME_BINDINGS = (
    "renta-trabajo-contribucion-empresarial-prevision",
    "renta-trabajo-contribucion-empresarial-seguro-dependencia",
    "renta-trabajo-aportacion-patrimonio-protegido",
    "renta-trabajo-aportacion-empresa-decision-trabajador",
)


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
                "censo.activity_start_date": date(filing_year_envelope().floor, 1, 1).isoformat(),
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
        ("--language", "en", "--profile", _PROFILE_LABEL, "--profile-secrets-stdin", "--format", "json", *args),
        input=json.dumps({"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}),
    )


def _create(year: int) -> str:
    created = _invoke(("app", "modelo", "work", "create", "--modelo", "100", "--year", str(year), "--period", "0A"))
    assert created.exit_code == 0, created.output
    return str(require_schema_envelope(created.output)["work_unit_id"])


@pytest.mark.usefixtures("runtime_profile")
def test_the_work_income_statement_refuses_when_no_payer_record_leaves_a_box_to_state(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = max(_renta_years(authority_operation))
    work_unit_id = _create(year)
    carries = _invoke(("app", "modelo", "work", "attest-prior-carries", work_unit_id, "--yes"))
    assert carries.exit_code == 0, carries.output
    revision_id = str(require_schema_envelope(carries.output)["calculation_revision_id"])

    refused = _invoke(("app", "modelo", "work", "attest-work-income", work_unit_id, "--yes"))

    assert refused.exit_code == 2, refused.output
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_MODELO_PRIOR_CARRY_NOTHING_OPEN"
    assert str(year) in error["message"]
    assert "work-income" in error["message"] or "work income" in error["message"]
    # The carry statement keeps its own words.
    assert "earlier years" not in error["message"]
    stored = _invoke(("app", "modelo", "work", "revision", revision_id))
    assert stored.exit_code == 0, stored.output
    assert not set(require_schema_envelope(stored.output)["binding_overrides"]) & set(_WORK_INCOME_BINDINGS)
