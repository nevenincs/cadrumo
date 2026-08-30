"""Unit tests for the JSON error envelope."""

from __future__ import annotations

import ast
import inspect
import json
import textwrap

import pytest
from pydantic import ValidationError

from ...operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ...config import override_settings
from ...json_contract import (
    ActionConditionEvidence,
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedPreconditionAction,
)
from ...locks_errors import LockAcquisitionError
from ..error_codes import ErrorEnvelope, build_error_envelope, render_error_json, render_error_text
from ..hierarchy import ActiveProfilePointerError, CadrumoError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _output_language(language: str):
    """Pin ``cadrumo_output_language`` via the canonical Settings override."""
    return override_settings(cadrumo_output_language=language)


def _resolved_recovery_action() -> ResolvedPreconditionAction:
    return ResolvedPreconditionAction(
        failed_condition_id="profile.active.missing",
        evidence=(
            ActionConditionEvidence(
                condition_id="profile.active.missing",
                evidence_id="profile.active.state",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"profile_name": "example", "profile_count": 0, "required": True},
            ),
        ),
        action=ResolvedActionReference(
            action_id="operator.profile.create",
            target_command_key="config.profile.create",
        ),
        argument_bindings=(
            ResolvedActionArgument(
                argument_name="profile_name",
                status=ActionArgumentStatus.RESOLVED,
                value="example",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="profile_name",
                source_evidence_id="profile.active.state",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def test_public_error_envelope_schema_is_complete_before_any_build_call() -> None:
    schema = ErrorEnvelope.model_json_schema()

    assert ErrorEnvelope.__pydantic_complete__
    assert "$defs" in schema
    assert "ResolvedPreconditionAction" in schema["$defs"]
    assert schema["properties"]["action"]["anyOf"][0]["$ref"].endswith("/$defs/ResolvedPreconditionAction")


def test_error_json_serializes_deterministically_with_shared_spine() -> None:
    from ...json_contract import ENVELOPE_SCHEMA_VERSION, EnvelopeStatus

    error = LockAcquisitionError(context={"z_key": "last", "a_key": "first"})
    first = render_error_json(error)
    second = render_error_json(error)
    payload = json.loads(first)

    assert first == second
    assert first.index('"category"') < first.index('"code"') < first.index('"context"')
    # The error document shares the success-envelope outer spine.
    assert payload["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert payload["status"] == EnvelopeStatus.ERROR.value
    assert payload["command"] is None
    assert payload["notices"] == []
    # The error detail is nested under ``error``; the spine owns the version.
    assert "schema_version" not in payload["error"]
    assert payload["error"]["code"]


def test_error_envelope_carries_resolved_precondition_action_through_json() -> None:
    action = _resolved_recovery_action()

    envelope = build_error_envelope(LockAcquisitionError(), action=action)
    payload = json.loads(render_error_json(LockAcquisitionError(), action=action))

    assert envelope.action == action
    assert payload["error"]["action"] == action.model_dump(mode="json")
    assert payload["error"]["action"]["action"]["target_command_key"] == "config.profile.create"
    assert payload["error"]["action"]["argument_bindings"] == [
        {
            "argument_name": "profile_name",
            "source": "operator_action.condition_evidence",
            "source_evidence_id": "profile.active.state",
            "source_key": "profile_name",
            "status": "resolved",
            "value": "example",
        },
    ]


def test_active_profile_pointer_error_carries_only_keyed_facts_before_application_projection() -> None:
    error = ActiveProfilePointerError(path="broken-pointer.json")
    registered = error.code

    assert registered is not None
    assert error.args == ("errors.integrity.integrity_active_profile_pointer",)
    assert error.context == {
        "path": "broken-pointer.json",
        "pointer_corrupt": True,
        "root_fallback_refused": True,
    }
    assert not hasattr(error, "suggestion")
    envelope = build_error_envelope(error)
    rendered = render_error_text(error)

    assert envelope.action is None
    assert envelope.context == {
        "path": "broken-pointer.json",
        "pointer_corrupt": "true",
        "root_fallback_refused": "true",
    }
    assert "suggestion" not in envelope.model_dump()
    assert "aeat config repair" not in rendered


def test_active_profile_pointer_error_does_not_redeclare_action_or_recovery_prose() -> None:
    """Core carries only the observation; the outer boundary owns its action verdict."""
    source = textwrap.dedent(inspect.getsource(ActiveProfilePointerError))
    tree = ast.parse(source)

    assert "aeat config repair" not in source
    assert "suggestion" not in source
    assert {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }.isdisjoint({"ActionReference", "ConditionEvidence", "PreconditionVerdict", "no_action_precondition_verdict"})


def test_cadrumo_error_does_not_expose_retired_suggestion_parameter() -> None:
    assert "suggestion" not in inspect.signature(CadrumoError).parameters


def test_error_envelope_rejects_retired_suggestion_field() -> None:
    envelope = build_error_envelope(LockAcquisitionError())
    legacy_payload = envelope.model_dump(mode="json") | {"suggestion": "aeat config repair"}

    with pytest.raises(ValidationError, match="suggestion"):
        ErrorEnvelope.model_validate(legacy_payload)


def test_secret_scrubbing_redacts_sensitive_fields_in_json_and_text() -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
    error = LockAcquisitionError(
        context={
            "api_token": "top-secret",
            "cookie": "session-cookie",
            "cert_password": "hunter2",
            "profile_tax_id": "X1234567L",
            "callback": "https://example.test/private/path?token=secret",
            "session_detail": f"bearer {jwt}",
        },
    )

    rendered_json = render_error_json(error)
    rendered_text = render_error_text(error)

    assert "<redacted>" in rendered_json
    assert "<redacted>" in rendered_text
    assert "top-secret" not in rendered_json
    assert "session-cookie" not in rendered_json
    assert "hunter2" not in rendered_json
    assert "top-secret" not in rendered_text
    assert "session-cookie" not in rendered_text
    assert "hunter2" not in rendered_text
    assert "X1234567L" not in rendered_json
    assert "X1234567L" not in rendered_text
    assert "sha256:2a000539" in rendered_json
    assert "https://example.test/private/path?token=secret" not in rendered_json
    assert "https://example.test" in rendered_json
    assert "private/path" not in rendered_json
    assert jwt not in rendered_json
    assert "token:sha256:0a2c77ea" in rendered_json


def test_envelope_message_renders_under_every_supported_language() -> None:
    """Every supported locale must produce a non-empty rendered message.

    A locale that produced ``None`` or an empty string would mean the
    i18n routing collapsed for that language.
    """
    languages = ("es", "en", "hu", "ca")
    rendered_per_language: dict[str, str] = {}
    for language in languages:
        with _output_language(language):
            envelope = build_error_envelope(LockAcquisitionError())
            assert envelope.message, f"empty envelope.message for locale {language!r}"
            rendered_per_language[language] = envelope.message
    # Pin that EVERY supported locale rendered SOMETHING — the original
    # `assert envelope.message` inside the loop catches per-locale empty,
    # this catches a silent loop-skip where the iterator yielded zero
    # languages.
    assert set(rendered_per_language) == set(languages), (
        f"expected every locale to render, got {sorted(rendered_per_language)}"
    )


def test_scrub_error_context_strips_internal_keys_from_rendered_output() -> None:
    """``prompt_key`` and ``question_id`` are internal implementation
    details of the wizard widget layer.  They must not appear in either
    the text or JSON error output the operator sees.

    The keys must remain accessible on the exception's ``.context``
    attribute so internal diagnostics and existing tests can still
    inspect them.
    """

    from ..error_codes import _INTERNAL_CONTEXT_KEYS

    error = LockAcquisitionError(
        context={
            "prompt_key": "wizard.setup.profile.tax-id.prompt",
            "question_id": "tax-id",
            "raw": "INVALID_NIF",
            "detail": "not a valid NIF shape",
        },
    )

    rendered_json = render_error_json(error)
    rendered_text = render_error_text(error)

    # Internal keys must NOT appear in rendered output.
    assert "prompt_key" not in rendered_json
    assert "question_id" not in rendered_json
    assert "prompt_key" not in rendered_text
    assert "question_id" not in rendered_text

    # User-facing context keys must still appear.
    assert "detail" in rendered_json
    assert "raw" in rendered_json

    # The keys must remain accessible on the original exception context
    # (they are stripped only from the RENDERED output, not from the object).
    assert error.context is not None
    assert "prompt_key" in error.context
    assert "question_id" in error.context

    # The internal key set is a frozenset containing exactly these two names.
    assert "prompt_key" in _INTERNAL_CONTEXT_KEYS
    assert "question_id" in _INTERNAL_CONTEXT_KEYS
