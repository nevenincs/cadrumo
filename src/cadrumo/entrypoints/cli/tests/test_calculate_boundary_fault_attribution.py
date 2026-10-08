"""``modelo work calculate`` must attribute a fault to whoever actually caused it.

Every pydantic ``ValidationError`` that escaped the calculate callback used to be
projected to one refusal — ``REFUSED_CLI_VALIDATION_BOUNDARY``, "the command
input failed validation, check the command's arguments" — with the pydantic
detail discarded from the envelope and written only to the error log. That is
wrong in two different directions at once, and both are exercised here through
the real CLI and the profile's native worker against real records rather than
a raised-by-hand exception:

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
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....domain.buckets.event import BUCKET_ACTOR_LABEL_MAX_LENGTH
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope
from .. import _modelo_cli_support
from .cli_runner import semantic_cli_output
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

#: A profile label that is legal for the canonical ``ProfileLabel`` contract
#: and longer than ``BucketActorLabel`` permits. The default audit
#: actor is resolved FROM the profile label, so this is the shape that makes the
#: application refuse its own record on a command line carrying no ``--by`` at
#: all.
_OVERLONG_PROFILE_LABEL = "Calculate boundary probe profile " + ("x" * 80)

_SHORT_PROFILE_LABEL = "Calculate boundary probe profile"


_LEGAL_ENTITY_FACTS = (
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
)

_OPERATIONS = frozenset(
    {
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
    }
)


def _scope(client_id: UUID) -> AccessScope:
    """Grant the Modelo 200 work lifecycle these commands submit."""
    return AccessScope(
        operations=_OPERATIONS,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in _OPERATIONS
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


@contextmanager
def _legal_entity_session(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> Iterator[NativeApiCliSession[None]]:
    """Enrol the legal-entity (IS) profile the Modelo 200 calculation needs, served by its worker."""

    def prepare(profile_id: UUID, root: Path) -> None:
        facts = complete_profile_facts(authority_operation.profile_schema(), _LEGAL_ENTITY_FACTS)
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE

    with native_api_cli_session(
        tmp_path, scope_for_destination=_scope, prepare_profile=prepare, profile_label=_SHORT_PROFILE_LABEL
    ) as session:
        yield session


def _calculate_args(work_unit_id: str) -> list[str]:
    """Return a Modelo 200 calculate invocation whose arguments are all correct.

    Mirrors the oracle fixture in ``test_modelo_calculation_through_real_cli``:
    every casilla, binding, and relation below is a value the verb accepts, so a
    refusal on this argument set is never about the arguments.
    """
    return [
        "app", "modelo", "work", "calculate", work_unit_id,
        "--casilla", "DP200012:00501=100000.00",
        "--casilla", "DP200013:00417=0.00",
        "--casilla", "DP200013:00418=0.00",
        "--casilla", "01032=0.00",
        "--casilla", "DP200014:00547=0.00",
        "--casilla", "DP200014:01033=0.00",
        "--casilla", "DP200014:01034=0.00",
        "--binding", "modelo-200-profile-legal-entity-form=sl",
        "--binding", "modelo-200-profile-incn-prior-12-months=500000",
        "--binding", "modelo-200-profile-tributacion-estado-porcentaje=100",
        "--binding", "modelo-200-bin-pendiente-ejercicios-anteriores=0",
        "--binding", "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores=0",
        "--binding", "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores=0",
        "--relation", "modelo-200-pagos-fraccionados-anuales=0",
    ]  # fmt: skip


def _create_work_unit(session: NativeApiCliSession[None]) -> str:
    created = session.invoke_password(
        "app", "modelo", "work", "create",
        "--modelo", "200", "--year", "2024", "--period", "0A", "--revision", "2024",
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str) and work_unit_id, created.output
    return work_unit_id


def _error(output: str) -> dict[str, Any]:
    payload = json.loads(output)
    assert payload["status"] == "error", payload
    error: dict[str, Any] = payload["error"]
    return error


def test_calculate_refuses_overlong_actor_naming_the_option_and_the_bound(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """An operator-supplied ``--by`` too long for the audit event refuses instructively.

    This is the argument direction, and it is the regression risk of the fix: a
    genuine bad-argument case must keep telling the operator it is theirs to
    correct. It must additionally name the option and the accepted bound. The
    option's help text does state the bound; the refusal did not say which option
    it was about, and arrived only after the calculation had already run.
    """
    overlong = "a" * (BUCKET_ACTOR_LABEL_MAX_LENGTH + 1)
    with _legal_entity_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session)
        result = session.invoke_password(*_calculate_args(work_unit_id), "--by", overlong)

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    message = semantic_cli_output(result)
    assert "--by" in message, message
    assert str(BUCKET_ACTOR_LABEL_MAX_LENGTH) in message, message
    assert str(len(overlong)) in message, message
    # The operator is NOT told this is an application defect: it is their value.
    assert "defect in Cadrumo" not in message, message


def test_calculate_accepts_an_actor_at_the_declared_bound(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """The refusal is a bound, not a blanket ban.

    Without this, a guard that rejected every ``--by`` would look identical to
    one that rejects only the over-long ones.
    """
    at_bound = "a" * BUCKET_ACTOR_LABEL_MAX_LENGTH
    with _legal_entity_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session)
        result = session.invoke_password(*_calculate_args(work_unit_id), "--by", at_bound)

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["state"] == "borrador"


def test_calculate_reports_an_application_built_record_as_an_internal_defect(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A record the application built from its own state is not the operator's fault.

    The command line carries no ``--by``. After creating the work unit with a
    valid short label, inject the legal-but-long default actor that an active
    profile can supply. The bucket event's actor permits only 64 characters,
    so the application refuses its own record with nothing wrong in the
    calculation invocation.

    Before the fix this reported ``REFUSED_CLI_VALIDATION_BOUNDARY`` — "check the
    command's arguments" — against an argument set that is entirely correct, with
    the failing contract reaching only the error log.
    """
    with _legal_entity_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session)
        # The CLI resolves the default actor before submitting, so the long label travels to the worker.
        monkeypatch.setattr(_modelo_cli_support, "resolve_default_actor", lambda: _OVERLONG_PROFILE_LABEL)
        result = session.invoke_password(*_calculate_args(work_unit_id))

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
    assert "String should have at most" in context["violations"], context
    assert str(BUCKET_ACTOR_LABEL_MAX_LENGTH) in context["violations"], context


def test_internal_fault_context_carries_no_taxpayer_value(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The named fault must not become an exfiltration path for the failing value.

    The value that breached a constraint is exactly the value that must not cross
    an output boundary. The field and the rule it broke are what make the defect
    reportable; the input is not, so the projection carries the pydantic ``loc``
    and ``msg`` and never ``input``.
    """
    with _legal_entity_session(tmp_path, authority_operation) as session:
        work_unit_id = _create_work_unit(session)
        # The CLI resolves the default actor before submitting, so the long label travels to the worker.
        monkeypatch.setattr(_modelo_cli_support, "resolve_default_actor", lambda: _OVERLONG_PROFILE_LABEL)
        result = session.invoke_password(*_calculate_args(work_unit_id))

    assert result.exit_code != 0, result.output
    rendered = json.dumps(_error(result.output)["context"])
    assert _OVERLONG_PROFILE_LABEL not in rendered, rendered
    # The distinctive tail of the offending value must not appear either.
    assert "x" * 80 not in rendered, rendered
