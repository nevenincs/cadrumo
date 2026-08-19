"""Strict roundtrip across the CLI ``--json`` envelope boundary.

Every ``--json`` response from the CLI is rendered through
:class:`SchemaEnvelope` so external consumers (operator tooling, the
audit pipeline, monitoring) can rely on a stable outer shape regardless
of the inner command result. This file asserts that the envelope shape
itself survives the emit / parse cycle: a SchemaEnvelope wrapping a
populated :class:`OutputSchema` instance, written through
:func:`emit_json_success`, must re-parse into a SchemaEnvelope of the
same inner type with strict pydantic equality.

A regression that drops the ``notices`` list, mis-serialises a typed
tuple field on the inner payload, or breaks the envelope's pinned
``schema_version`` surfaces as a strict equality failure.
"""

from __future__ import annotations

import io
import json
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from .. import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    CasillaId,
    NoRecoveryOutcome,
    validated_casilla_id,
)
from ..json_contract import (
    ENVELOPE_SCHEMA_VERSION,
    ActionConditionEvidence,
    EnvelopeStatus,
    Notice,
    NoticeSeverity,
    OutputSchema,
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedNoticeAction,
    ResolvedPreconditionAction,
    SchemaEnvelope,
    emit_json_document,
    emit_json_success,
)
from ..redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_OBJECT_KEY_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILE_ID = "986c0dc9-56dc-422b-9d8f-698661b9eb1e"  # was '123e4567-e89b-12d3-a456-426614174000'
_NIF = "12345678Z"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
_URL = "https://example.test/private/path?token=secret"
_OBJECT_KEY = "wallet:2026-secret"
_OTHER_OBJECT_KEY = "wallet:2026-other"


_IVA_DEVENGADO_CASILLA: CasillaId = validated_casilla_id("iva.devengado")
_IVA_DEDUCIBLE_CASILLA: CasillaId = validated_casilla_id("iva.deducible")
_IVA_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("rendimiento_neto")
_INGRESOS_CASILLA: CasillaId = validated_casilla_id("ingresos")
_GASTOS_DEDUCIBLES_CASILLA: CasillaId = validated_casilla_id("gastos_deducibles")
_SIMPLE_CASILLA: CasillaId = validated_casilla_id("01")
_IVA_RESULTADO_OPERANDS = (_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA)
_RENDIMIENTO_NETO_OPERANDS = (_INGRESOS_CASILLA, _GASTOS_DEDUCIBLES_CASILLA)


class _ProvenancePayload(OutputSchema):
    """Inline OutputSchema with deep-data tuple fields.

    Avoids coupling the test to a specific command's evolving payload
    shape while still exercising the kinds of fields that surface
    cross-domain data: tuple-of-str provenance, optional nullable
    str, and a non-empty default tuple field.
    """

    casilla_id: CasillaId
    value: str
    formula_id: str | None = None
    operand_refs: tuple[CasillaId, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    legal_refs: tuple[str, ...] = ()


class _SensitivePayload(OutputSchema):
    profile_id: str
    bucket_id: str
    object_key: str
    tax_id: str
    callback: str
    authorization: str
    keyed_lookup: dict[str, str]


def test_schema_envelope_full_roundtrip_via_json_dump_and_load() -> None:
    """A SchemaEnvelope wrapping a populated OutputSchema round-trips strictly.

    Uses ``model_dump_json`` / ``model_validate_json`` rather than
    ``emit_json_success`` so the test asserts the pydantic round-trip
    independently of the stdout-flush behaviour.
    """

    result = _ProvenancePayload(
        casilla_id=_IVA_RESULTADO_CASILLA,
        value="12345.67",
        formula_id="iva.formula.resultado",
        operand_refs=_IVA_RESULTADO_OPERANDS,
        operand_casilla_refs=_IVA_RESULTADO_OPERANDS,
        legal_refs=("ley-37-1992:art-94",),
    )
    original = SchemaEnvelope[_ProvenancePayload](
        command="app modelo formulas",
        status=EnvelopeStatus.WARNING,
        result=result,
        notices=[
            Notice(
                severity=NoticeSeverity.WARNING,
                code="modelo.formulas.deprecated_format",
                message="deprecated: --format text",
            ),
        ],
    )

    roundtripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(
        original.model_dump_json(),
    )

    assert roundtripped == original
    assert roundtripped.schema_version == ENVELOPE_SCHEMA_VERSION
    assert roundtripped.command == "app modelo formulas"
    assert roundtripped.status is EnvelopeStatus.WARNING
    assert roundtripped.result.operand_refs == _IVA_RESULTADO_OPERANDS
    assert roundtripped.result.operand_casilla_refs == _IVA_RESULTADO_OPERANDS
    assert roundtripped.result.legal_refs == ("ley-37-1992:art-94",)
    assert roundtripped.notices[0].message == "deprecated: --format text"


def test_emit_json_success_emits_parseable_envelope_to_stream() -> None:
    """The bytes emit_json_success writes to stdout re-parse into a SchemaEnvelope.

    Captures the emitted text into an :class:`io.StringIO` stream so
    the test exercises the real :func:`emit_json_document` write path
    without touching stdout. The captured JSON must:

    * decode as a valid JSON document
    * carry the pinned schema_version and supplied command
    * round-trip back into the same SchemaEnvelope through pydantic
      validation
    """

    result = _ProvenancePayload(
        casilla_id=_RENDIMIENTO_NETO_CASILLA,
        value="40000.00",
        operand_refs=_RENDIMIENTO_NETO_OPERANDS,
        operand_casilla_refs=_RENDIMIENTO_NETO_OPERANDS,
    )
    buffer = io.StringIO()
    emit_json_success(
        "app modelo work calculate",
        result,
        notices=[],
        stream=buffer,
    )

    raw = buffer.getvalue()
    assert raw, "emit_json_success wrote nothing to the stream"

    decoded = json.loads(raw)
    assert decoded["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert decoded["command"] == "app modelo work calculate"
    assert decoded["status"] == EnvelopeStatus.SUCCESS.value
    assert decoded["notices"] == []

    # The emitted bytes re-parse cleanly through SchemaEnvelope's
    # typed JSON validator. Using ``model_validate_json`` rather than
    # ``model_validate(json.loads(...))`` is intentional: the typed
    # boundary is the JSON bytes, not a pre-parsed dict, and pydantic
    # only knows to coerce list -> tuple when it owns the parse.
    roundtripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(raw)
    assert roundtripped.result == result
    assert roundtripped.result.operand_refs == _RENDIMIENTO_NETO_OPERANDS
    assert roundtripped.result.operand_casilla_refs == _RENDIMIENTO_NETO_OPERANDS


def test_json_document_uses_the_canonical_scalar_normalizer() -> None:
    """Envelope-independent JSON output preserves CLI scalar wire contracts."""
    buffer = io.StringIO()

    emit_json_document(
        {
            "destination": Path("C:/evidence/result.json"),
            "amount": Decimal("1E+3"),
            "as_of": "2026-08-01",
        },
        stream=buffer,
    )

    assert json.loads(buffer.getvalue()) == {
        "amount": "1000",
        "as_of": "2026-08-01",
        "destination": "C:/evidence/result.json",
    }


def test_emit_json_success_redacts_sensitive_values_without_breaking_envelope_shape() -> None:
    result = _SensitivePayload(
        profile_id=_PROFILE_ID,
        bucket_id="bucket-alpha",
        object_key=_OBJECT_KEY,
        tax_id=_NIF,
        callback=_URL,
        authorization=f"bearer {_JWT}",
        keyed_lookup={
            _OBJECT_KEY: "first object",
            _OTHER_OBJECT_KEY: "second object",
        },
    )
    buffer = io.StringIO()
    emit_json_success(
        "app secure audit",
        result,
        notices=[
            Notice(severity=NoticeSeverity.WARNING, code="secure.audit.callback", message=f"callback {_URL}"),
            Notice(severity=NoticeSeverity.WARNING, code="secure.audit.bearer", message=f"bearer {_JWT}"),
        ],
        stream=buffer,
    )

    raw = buffer.getvalue()
    decoded = json.loads(raw)

    assert set(decoded) == {"schema_version", "command", "active_profile", "status", "result", "notices"}
    # No active profile injected on this direct emit, so the identity anchor is null.
    assert decoded["active_profile"] is None
    assert decoded["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert decoded["status"] == EnvelopeStatus.WARNING.value
    assert decoded["command"] == "app secure audit"
    assert decoded["result"] == {
        "profile_id": CLI_PROFILE_ID_PLACEHOLDER,
        "bucket_id": CLI_BUCKET_ID_PLACEHOLDER,
        "object_key": CLI_OBJECT_KEY_PLACEHOLDER,
        "tax_id": "sha256:1c9f9632",
        "callback": "https://example.test",
        "authorization": "token:sha256:0a2c77ea",
        "keyed_lookup": {
            CLI_OBJECT_KEY_PLACEHOLDER: "first object",
            f"{CLI_OBJECT_KEY_PLACEHOLDER}#2": "second object",
        },
    }
    assert decoded["notices"][0]["message"] == "callback https://example.test"
    assert decoded["notices"][1]["message"] == "token:sha256:0a2c77ea"
    assert _PROFILE_ID not in raw
    assert _NIF not in raw
    assert _JWT not in raw
    assert _URL not in raw
    assert _OBJECT_KEY not in raw
    assert _OTHER_OBJECT_KEY not in raw

    roundtripped = SchemaEnvelope[_SensitivePayload].model_validate_json(raw)
    assert roundtripped.result.profile_id == CLI_PROFILE_ID_PLACEHOLDER
    assert roundtripped.result.keyed_lookup[f"{CLI_OBJECT_KEY_PLACEHOLDER}#2"] == "second object"


def test_schema_envelope_rejects_unknown_outer_keys() -> None:
    """Extra keys on the envelope must be rejected at validate time.

    Guards the strict ``extra='forbid'`` contract. Without this,
    a producer drift that adds a top-level key would silently land
    in caller payloads instead of failing fast at the contract
    boundary.
    """

    from pydantic import ValidationError as _PydValidationError

    with pytest.raises(_PydValidationError):
        SchemaEnvelope[_ProvenancePayload].model_validate(
            {
                "schema_version": ENVELOPE_SCHEMA_VERSION,
                "command": "app modelo formulas",
                "status": EnvelopeStatus.SUCCESS.value,
                "result": {
                    "casilla_id": _SIMPLE_CASILLA,
                    "value": "100.00",
                },
                "notices": [],
                "metadata": {"hidden": "extra"},  # not in the envelope schema
            },
        )


def test_notice_projects_fully_materialised_success_action_canonically() -> None:
    """A success notice carries a concrete next action, not a failed-precondition record."""
    notice = Notice(
        severity=NoticeSeverity.WARNING,
        code="profile.setup.complete",
        message="The profile setup is complete.",
        context={"source_kind": "profile_store", "reason": "setup_complete"},
        action=ResolvedNoticeAction(
            action=ResolvedActionReference(
                action_id="operator.profile.create",
                target_command_key="config.profile.create",
            ),
            argument_bindings=(
                ResolvedActionArgument(
                    argument_name="profile_name",
                    status=ActionArgumentStatus.RESOLVED,
                    value="Ada",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="profile_name",
                    source_evidence_id="profile.setup.state",
                ),
            ),
        ),
    )

    rendered = notice.model_dump(mode="json")

    assert [item["argument_name"] for item in rendered["action"]["argument_bindings"]] == [
        "profile_name",
    ]
    assert rendered["context"] == {"reason": "setup_complete", "source_kind": "profile_store"}
    assert rendered["action"]["action"] == {
        "action_id": "operator.profile.create",
        "target_command_key": "config.profile.create",
    }
    assert "failed_condition_id" not in rendered["action"]
    assert "suggestion" not in rendered


def test_notice_rejects_hidden_free_form_action_authority() -> None:
    """Commands cannot re-enter a notice as suggestion, prose, or context."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        Notice.model_validate(
            {
                "severity": "info",
                "code": "profile.active.required",
                "message": "An active profile is required.",
                "suggestion": "aeat config profile create Ada",
            },
        )
    with pytest.raises(PydanticValidationError):
        Notice(
            severity=NoticeSeverity.INFO,
            code="profile.active.required",
            message="Run aeat config profile create Ada",
        )
    with pytest.raises(PydanticValidationError):
        Notice(
            severity=NoticeSeverity.INFO,
            code="profile.active.required",
            message="An active profile is required.",
            context={"next_command": "config.profile.create"},
        )


def test_notice_allows_aeat_authority_name_without_a_command_path() -> None:
    """Ordinary references to the tax authority are not executable guidance."""
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code="overview.no_aeat_history",
        message="This profile has no filing history that AEAT holds for it.",
    )

    assert notice.message.endswith("AEAT holds for it.")


def test_precondition_projection_remains_available_only_for_failure_envelopes() -> None:
    """Failure records retain their own typed closure semantics outside Notice.action."""
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        ActionConditionEvidence(
            condition_id="profile.active.required",
            evidence_id="profile.state",
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            values={"action.message": "create a profile"},
        )

    failure_action = ResolvedPreconditionAction(
        failed_condition_id="submission.period.closed",
        evidence=(
            ActionConditionEvidence(
                condition_id="submission.period.closed",
                evidence_id="submission.period",
                provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
                values={"period_status": "closed"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    )

    rendered = failure_action.model_dump(mode="json")
    assert rendered["action"] is None
    assert rendered["no_recovery_outcome"] == NoRecoveryOutcome.TERMINAL.value
    assert rendered["conditionality"] == ActionConditionality.NOT_APPLICABLE.value


def _profile_state_evidence(*, condition_id: str = "profile.active.required") -> ActionConditionEvidence:
    """One real typed fact row used to construct action-envelope inputs."""
    return ActionConditionEvidence(
        condition_id=condition_id,
        evidence_id="profile.state",
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        values={"profile_name": "Ada", "profile_status": "absent"},
    )


def _profile_name_binding(*, value: str | int = "Ada") -> ResolvedActionArgument:
    """One condition-evidence binding for the action projection."""
    return ResolvedActionArgument(
        argument_name="profile_name",
        status=ActionArgumentStatus.RESOLVED,
        value=value,
        source=ActionArgumentSource.CONDITION_EVIDENCE,
        source_key="profile_name",
        source_evidence_id="profile.state",
    )


def _profile_create_action(
    *,
    evidence: tuple[ActionConditionEvidence, ...] | None = None,
    argument_bindings: tuple[ResolvedActionArgument, ...] | None = None,
) -> ResolvedPreconditionAction:
    """Construct a fully resolved action using only production DTOs."""
    return ResolvedPreconditionAction(
        failed_condition_id="profile.active.required",
        evidence=(_profile_state_evidence(),) if evidence is None else evidence,
        action=ResolvedActionReference(
            action_id="profile.create",
            target_command_key="config.profile.create",
        ),
        argument_bindings=(_profile_name_binding(),) if argument_bindings is None else argument_bindings,
        conditionality=ActionConditionality.IMMEDIATE,
    )


def test_resolved_precondition_action_rejects_identity_and_evidence_join_defects() -> None:
    """Wire identities, failed conditions, and evidence sources cannot drift apart."""
    with pytest.raises(ValidationError):
        _profile_create_action(evidence=(_profile_state_evidence(), _profile_state_evidence()))
    with pytest.raises(ValidationError):
        _profile_create_action(evidence=(_profile_state_evidence(condition_id="profile.exists.required"),))
    with pytest.raises(ValidationError):
        _profile_create_action(
            argument_bindings=(
                _profile_name_binding(),
                ResolvedActionArgument(
                    argument_name="profile_name",
                    status=ActionArgumentStatus.RESOLVED,
                    value="Ada",
                    source=ActionArgumentSource.REQUEST_CONTEXT,
                    source_key="profile_name",
                ),
            ),
        )
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            action=ResolvedActionReference(
                action_id="profile.create",
                target_command_key="config.profile.create",
            ),
            argument_bindings=(
                ResolvedActionArgument(
                    argument_name="profile_name",
                    status=ActionArgumentStatus.RESOLVED,
                    value="Ada",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="profile_name",
                    source_evidence_id="profile.unknown",
                ),
            ),
            conditionality=ActionConditionality.IMMEDIATE,
        )
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            action=ResolvedActionReference(
                action_id="profile.create",
                target_command_key="config.profile.create",
            ),
            argument_bindings=(
                ResolvedActionArgument(
                    argument_name="profile_name",
                    status=ActionArgumentStatus.RESOLVED,
                    value="Ada",
                    source=ActionArgumentSource.CONDITION_EVIDENCE,
                    source_key="profile_identifier",
                    source_evidence_id="profile.state",
                ),
            ),
            conditionality=ActionConditionality.IMMEDIATE,
        )
    with pytest.raises(ValidationError):
        _profile_create_action(argument_bindings=(_profile_name_binding(value=1),))
    with pytest.raises(ValidationError):
        _profile_create_action(argument_bindings=(_profile_name_binding(value="Bea"),))


def test_resolved_precondition_action_rejects_resolution_and_outcome_defects() -> None:
    """The DTO makes missing inputs and closed outcomes structurally explicit."""
    with pytest.raises(ValidationError):
        ResolvedActionArgument(
            argument_name="profile_name",
            status=ActionArgumentStatus.RESOLVED,
            value="Ada",
            source=ActionArgumentSource.CONDITION_EVIDENCE,
            source_key="profile_name",
        )
    with pytest.raises(ValidationError):
        ResolvedActionArgument(
            argument_name="profile_name",
            status=ActionArgumentStatus.MISSING,
            value="Ada",
        )
    missing_name = ResolvedActionArgument(argument_name="profile_name", status=ActionArgumentStatus.MISSING)
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            action=ResolvedActionReference(
                action_id="profile.create",
                target_command_key="config.profile.create",
            ),
            argument_bindings=(missing_name,),
            missing_argument_names=("profile_name", "profile_name"),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        )
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            action=ResolvedActionReference(
                action_id="profile.create",
                target_command_key="config.profile.create",
            ),
            argument_bindings=(missing_name,),
            missing_argument_names=("profile_name",),
            conditionality=ActionConditionality.IMMEDIATE,
        )
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            action=ResolvedActionReference(
                action_id="profile.create",
                target_command_key="config.profile.create",
            ),
            conditionality=ActionConditionality.NOT_APPLICABLE,
        )
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            conditionality=ActionConditionality.IMMEDIATE,
            no_recovery_outcome=NoRecoveryOutcome.SAFETY,
        )
    with pytest.raises(ValidationError):
        ResolvedPreconditionAction(
            failed_condition_id="profile.active.required",
            evidence=(_profile_state_evidence(),),
            action=ResolvedActionReference(
                action_id="profile.create",
                target_command_key="config.profile.create",
            ),
            conditionality=ActionConditionality.IMMEDIATE,
            no_recovery_outcome=NoRecoveryOutcome.SAFETY,
        )


@pytest.mark.parametrize(
    "reserved_key",
    (
        "action",
        "command",
        "fix_command",
        "next_action",
        "next_command",
        "recovery",
        "recovery_hint",
        "remediation",
        "suggestion",
    ),
)
def test_notice_rejects_every_reserved_action_context_key(reserved_key: str) -> None:
    """Context remains usable for facts but cannot become an action side channel."""
    with pytest.raises(ValidationError):
        Notice(
            severity=NoticeSeverity.INFO,
            code="profile.active.required",
            message="An active profile is required.",
            context={reserved_key: "profile.create"},
        )


def test_precondition_projection_canonicalizes_and_deep_freezes_wire_facts() -> None:
    """Equivalent input order produces one immutable, deterministic wire record."""
    request = ActionConditionEvidence(
        condition_id="profile.active.required",
        evidence_id="profile.request",
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        values={"profile_name": "Ada"},
    )
    display_name = ResolvedActionArgument(
        argument_name="display_name",
        status=ActionArgumentStatus.RESOLVED,
        value="Ada",
        source=ActionArgumentSource.REQUEST_CONTEXT,
        source_key="profile_name",
    )
    ordered = _profile_create_action(
        evidence=(request, _profile_state_evidence()),
        argument_bindings=(display_name, _profile_name_binding()),
    )
    reversed_input = _profile_create_action(
        evidence=(_profile_state_evidence(), request),
        argument_bindings=(_profile_name_binding(), display_name),
    )

    assert ordered.model_dump_json() == reversed_input.model_dump_json()
    assert isinstance(ordered.evidence[0].values, MappingProxyType)
    assert not hasattr(ordered.evidence[0].values, "__setitem__")
    action = ordered.action
    assert action is not None
    action_field = "action_id"
    with pytest.raises(ValidationError):
        setattr(action, action_field, "profile.reset")


def test_action_bearing_envelope_json_round_trip_preserves_resolved_target_and_bindings() -> None:
    """The full envelope carries a schema-resolved action without prose authority."""
    original = SchemaEnvelope[_ProvenancePayload](
        command="config profile status",
        status=EnvelopeStatus.WARNING,
        result=_ProvenancePayload(casilla_id=_SIMPLE_CASILLA, value="0"),
        notices=[
            Notice(
                severity=NoticeSeverity.WARNING,
                code="profile.active.required",
                message="An active profile is required.",
                action=ResolvedNoticeAction(
                    action=ResolvedActionReference(
                        action_id="operator.profile.create",
                        target_command_key="config.profile.create",
                    ),
                    argument_bindings=(_profile_name_binding(),),
                ),
            ),
        ],
    )

    round_tripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(original.model_dump_json())

    assert round_tripped == original
    action = round_tripped.notices[0].action
    assert action is not None
    assert action.action is not None
    assert action.action.target_command_key == "config.profile.create"
    assert action.argument_bindings[0].argument_name == "profile_name"


def test_success_notice_action_rejects_unresolved_argument() -> None:
    """A successful notice can never serialise a partial next action."""
    with pytest.raises(ValidationError, match="fully resolved"):
        ResolvedNoticeAction(
            action=ResolvedActionReference(
                action_id="operator.profile.create",
                target_command_key="config.profile.create",
            ),
            argument_bindings=(
                ResolvedActionArgument(
                    argument_name="profile_name",
                    status=ActionArgumentStatus.MISSING,
                ),
            ),
        )
