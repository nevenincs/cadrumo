"""``modelo work calculate`` must attribute a fault to whoever actually caused it.

Every pydantic ``ValidationError`` that escaped the calculate callback used to be
projected to one refusal — ``REFUSED_CLI_VALIDATION_BOUNDARY``, "the command
input failed validation, check the command's arguments" — with the pydantic
detail discarded from the envelope and written only to the error log. That is
wrong in two different directions at once, and both are exercised here through
the real CLI against real records rather than a raised-by-hand exception:

- An operator value that no CLI gate bounded reached a downstream contract and
  refused there, so the operator was told to check arguments without being told
  WHICH argument — and only after the calculation had run.
- A record the application built from its own state refused, so the operator was
  told to check arguments that were entirely correct, on a command line offering
  nothing to correct.

The discriminator is the region of the callback the fault was raised in, not an
inspection of the exception: everything below argument handling is application
state by construction.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....domain.buckets import BUCKET_ACTOR_LABEL_MAX_LENGTH
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ....tests.modelo_cli import create_modelo_work_unit_via_cli
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "0ac1e000-0000-4000-8000-0000000000f1"

#: A profile label that is legal for ``ProfileName`` (which permits 128
#: characters) and longer than ``BucketActorLabel`` permits. The default audit
#: actor is resolved FROM the profile label, so this is the shape that makes the
#: application refuse its own record on a command line carrying no ``--by`` at
#: all.
_OVERLONG_PROFILE_LABEL = "Calculate boundary probe profile " + ("x" * 80)

_SHORT_PROFILE_LABEL = "Calculate boundary probe profile"


def _runtime_profile(tmp_path: Path, label: str) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=label) as profile:
        yield profile


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    yield from _runtime_profile(tmp_path, _SHORT_PROFILE_LABEL)


def _rename_active_profile_to_overlong_label() -> None:
    """Rename the active profile to a legal-but-long label through the real CLI.

    The rename is the operator route into this state and it succeeds, which is
    the point: nothing in the profile surface refuses the label, so the operator
    has no signal that they have just broken every verb that records an audit
    event under it.
    """
    result = invoke_cached_cli(
        ["--format", "json", "config", "profile", "rename", _SHORT_PROFILE_LABEL, _OVERLONG_PROFILE_LABEL],
    )
    assert result.exit_code == 0, result.output


def _seed_legal_entity_profile(runtime_profile: TestRuntimeProfile, *, label: str) -> None:
    """Seed the legal-entity (IS) profile the Modelo 200 calculation needs."""
    record = UserProfileRecord(
        schema_id="cadrumo.user_profile",
        # Sourced from the schema, never pinned: a literal goes stale the moment
        # the profile schema is revised, and the record then refuses to validate
        # against its own canonical version.
        schema_version=load_user_profile_schema().version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.name", value="Probe IS Operator"),
            UserProfileFact(path="identity.legal_name", value="Probe IS Operator SL"),
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000.00")),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        ),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label=label)


def _calculate_args(work_unit_id: str) -> list[str]:
    """Return a Modelo 200 calculate invocation whose arguments are all correct.

    Mirrors the oracle fixture in ``test_modelo_calculation_through_real_cli``:
    every casilla, binding, and relation below is a value the verb accepts, so a
    refusal on this argument set is never about the arguments.
    """
    return [
        "--format", "json",
        "app", "modelo", "work", "calculate", work_unit_id,
        "--casilla", "00501=100000.00",
        "--casilla", "DP200013:00417=0.00",
        "--casilla", "DP200013:00418=0.00",
        "--casilla", "01032=0.00",
        "--casilla", "DP200014:00547=0.00",
        "--casilla", "DP200014:01033=0.00",
        "--casilla", "DP200014:01034=0.00",
        "--binding", "modelo-200-2024-profile-legal-entity-form=sl",
        "--binding", "modelo-200-2024-profile-new-entity-flag=0",
        "--binding", "modelo-200-2024-profile-incn-prior-12-months=500000",
        "--binding", "modelo-200-2024-profile-tributacion-estado-porcentaje=100",
        "--binding", "modelo-200-2024-bin-pendiente-ejercicios-anteriores=0",
        "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
        "--binding", "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
        "--relation", "modelo-200-2024-rel-202-pagos-fraccionados=0",
    ]  # fmt: skip


def _create_work_unit() -> str:
    return create_modelo_work_unit_via_cli(
        modelo="200",
        filing_year=2024,
        period="0A",
        revision="2024-y-siguientes",
    )


def _error(output: str) -> dict[str, Any]:
    payload = json.loads(output)
    assert payload["status"] == "error", payload
    error: dict[str, Any] = payload["error"]
    return error


def test_calculate_refuses_overlong_actor_naming_the_option_and_the_bound(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """An operator-supplied ``--by`` too long for the audit event refuses instructively.

    This is the argument direction, and it is the regression risk of the fix: a
    genuine bad-argument case must keep telling the operator it is theirs to
    correct. It must additionally name the option and the accepted bound. The
    option's help text does state the bound; the refusal did not say which option
    it was about, and arrived only after the calculation had already run.
    """
    _seed_legal_entity_profile(runtime_profile, label=_SHORT_PROFILE_LABEL)
    work_unit_id = _create_work_unit()

    overlong = "a" * (BUCKET_ACTOR_LABEL_MAX_LENGTH + 1)
    result = invoke_cached_cli([*_calculate_args(work_unit_id), "--by", overlong])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    message = semantic_cli_output(result)
    assert "--by" in message, message
    assert str(BUCKET_ACTOR_LABEL_MAX_LENGTH) in message, message
    assert str(len(overlong)) in message, message
    # The operator is NOT told this is an application defect: it is their value.
    assert "defect in Cadrumo" not in message, message


def test_calculate_accepts_an_actor_at_the_declared_bound(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The refusal is a bound, not a blanket ban.

    Without this, a guard that rejected every ``--by`` would look identical to
    one that rejects only the over-long ones.
    """
    _seed_legal_entity_profile(runtime_profile, label=_SHORT_PROFILE_LABEL)
    work_unit_id = _create_work_unit()

    at_bound = "a" * BUCKET_ACTOR_LABEL_MAX_LENGTH
    result = invoke_cached_cli([*_calculate_args(work_unit_id), "--by", at_bound])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["state"] == "borrador"


def test_calculate_reports_an_application_built_record_as_an_internal_defect(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """A record the application built from its own state is not the operator's fault.

    The command line carries no ``--by``, so the audit actor is resolved from the
    active profile label. ``ProfileName`` permits 128 characters while the bucket
    event's actor permits 64, so a legal profile label makes the application
    refuse its own record with nothing wrong in the invocation.

    Before the fix this reported ``REFUSED_CLI_VALIDATION_BOUNDARY`` — "check the
    command's arguments" — against an argument set that is entirely correct, with
    the failing contract reaching only the error log.
    """
    _seed_legal_entity_profile(runtime_profile, label=_SHORT_PROFILE_LABEL)
    work_unit_id = _create_work_unit()
    _rename_active_profile_to_overlong_label()

    result = invoke_cached_cli(_calculate_args(work_unit_id))

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    error = _error(result.output)
    assert error["code"] == "INTERNAL_CLI_OUTBOUND_PAYLOAD_BOUNDARY", error
    assert error["category"] == "INTERNAL", error
    assert "arguments" not in error["message"], error

    # The real cause reaches the operator rather than only the error log.
    context = error["context"]
    assert context is not None, error
    assert context["failing_record"] == "BucketEvent", context
    assert "actor" in context["violations"], context
    assert str(BUCKET_ACTOR_LABEL_MAX_LENGTH) in context["violations"], context


def test_internal_fault_context_carries_no_taxpayer_value(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The named fault must not become an exfiltration path for the failing value.

    The value that breached a constraint is exactly the value that must not cross
    an output boundary. The field and the rule it broke are what make the defect
    reportable; the input is not, so the projection carries the pydantic ``loc``
    and ``msg`` and never ``input``.
    """
    _seed_legal_entity_profile(runtime_profile, label=_SHORT_PROFILE_LABEL)
    work_unit_id = _create_work_unit()
    _rename_active_profile_to_overlong_label()

    result = invoke_cached_cli(_calculate_args(work_unit_id))

    assert result.exit_code != 0, result.output
    rendered = json.dumps(_error(result.output)["context"])
    assert _OVERLONG_PROFILE_LABEL not in rendered, rendered
    # The distinctive tail of the offending value must not appear either.
    assert "x" * 80 not in rendered, rendered
