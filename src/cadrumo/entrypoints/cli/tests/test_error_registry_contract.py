"""Contract tests for the CLI-facing error registry.

Asserts that representative exceptions render with the grep-stable prefix
expected by operators, and that every
:class:`cadrumo.core.errors.ErrorCategory` (other than the generic
``ERROR``) is exercised by a probe.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.auth.errors import AeatSessionExpiredError
from ....adapters.outbound.aeat.browser.session import BrowserError
from ....application.operator_actions import lookup_action
from ....application.review.errors import ReviewKindReservedError
from ....core import ActionArgumentStatus
from ....core.access_gate import LiveSubmitForbiddenError
from ....core.config import override_settings
from ....core.errors.error_codes import ERROR_REGISTRY, ErrorCategory, ErrorEnvelope, render_error_text
from ....core.errors.hierarchy import DecimalFormatError
from ....core.i18n import tr
from ....core.json_contract import ENVELOPE_SCHEMA_VERSION, EnvelopeStatus, ResolvedPreconditionAction
from ....core.observability.errors import RunContextMissingError
from ....domain.portals.errors import PortalIntegrityError
from ....tests.cli_envelope import require_error_document
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .._verb_input_schema import build_verb_input_schemas, cli_argv_for

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("error_factory", "category"),
    [
        (DecimalFormatError, ErrorCategory.ERROR),
        (LiveSubmitForbiddenError, ErrorCategory.LOCKED),
        (lambda: ReviewKindReservedError("queue", "tracked separately"), ErrorCategory.REFUSED),
        (AeatSessionExpiredError, ErrorCategory.AUTH),
        (PortalIntegrityError, ErrorCategory.INTEGRITY),
        (BrowserError, ErrorCategory.FAIL),
        (RunContextMissingError, ErrorCategory.INTERNAL),
    ],
)
@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_rendered_prefixes_are_catalogue_derived(
    error_factory: Callable[[], Exception],
    category: ErrorCategory,
    locale: str,
) -> None:
    """Each registered category renders from its selected locale key."""
    with override_settings(cadrumo_output_language=locale):
        rendered = render_error_text(error_factory())
    first_line = rendered.splitlines()[0]
    prefix = tr(f"errors.prefix.{category.value.lower()}", locale=locale)
    assert prefix != f"errors.prefix.{category.value.lower()}"
    assert first_line.startswith(f"{prefix} ")


def test_every_error_category_has_a_cli_prefix_probe() -> None:
    """Every :class:`~cadrumo.core.errors.ErrorCategory` member except ``ERROR`` is exercised above."""
    probed = {
        ErrorCategory.LOCKED,
        ErrorCategory.REFUSED,
        ErrorCategory.AUTH,
        ErrorCategory.INTEGRITY,
        ErrorCategory.FAIL,
        ErrorCategory.INTERNAL,
    }
    assert probed == set(ErrorCategory) - {ErrorCategory.ERROR}


def _object_member(document: dict[str, object], key: str) -> dict[str, object]:
    value = document[key]
    assert isinstance(value, dict), f"{key!r} is not a JSON object: {value!r}"
    return {str(member_key): member_value for member_key, member_value in value.items()}


def test_registered_refusal_action_resolves_to_its_live_input_surface(tmp_path: Path) -> None:
    """A real refusal carries only an action target and inputs Click currently exposes."""
    source_schema = build_verb_input_schemas(("ledger.list",))["ledger.list"]
    with isolated_profile_storage_root(tmp_path=tmp_path):
        result = invoke_cached_cli(cli_argv_for(source_schema, {}), catch_exceptions=False)

    assert result.exit_code != 0, result.output
    document = require_error_document(result.stderr)
    assert set(document) == {"schema_version", "command", "active_profile", "status", "error", "notices"}
    assert document["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert document["command"] == source_schema.command_key
    assert document["active_profile"] is None
    assert document["status"] == EnvelopeStatus.ERROR.value
    assert document["notices"] == []
    error = _object_member(document, "error")
    error_code = error["code"]
    assert isinstance(error_code, str)
    assert error_code in ERROR_REGISTRY

    action_payload = error["action"]
    assert isinstance(action_payload, dict)
    action = ResolvedPreconditionAction.model_validate_json(json.dumps(action_payload))
    error["action"] = action
    ErrorEnvelope.model_validate(error)
    assert action.action is not None

    declaration = lookup_action(action.action.action_id)
    assert action.action.target_command_key == declaration.target_command_key
    target_schema = build_verb_input_schemas((declaration.target_command_key,))[declaration.target_command_key]
    assert action.action.cli_path == target_schema.cli_path

    declared_names = {specification.argument_name for specification in declaration.argument_specifications}
    binding_names = {binding.argument_name for binding in action.argument_bindings}
    assert binding_names == declared_names
    missing_names = {
        binding.argument_name for binding in action.argument_bindings if binding.status is ActionArgumentStatus.MISSING
    }
    assert set(action.missing_argument_names) == missing_names
    target_parameters = {parameter.name: parameter for parameter in target_schema.parameters}
    assert declared_names <= target_parameters.keys()
    assert missing_names
    assert missing_names <= target_parameters.keys()
    assert all(not target_parameters[name].required for name in missing_names)
