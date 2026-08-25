"""Verify that non-NoActiveProfileError exceptions propagate unchanged.

contract assertion: after contract narrows the broad ``except Exception`` catch in
``_ratios_bucket_id``, ``_ratios_bucket_and_profile``, and
``_rule_bucket_id`` to ``except NoActiveProfileError``, any unexpected
exception (e.g. a corrupt active-profile pointer file producing a
``pydantic.ValidationError``) must NOT be swallowed as the "no active
profile" refusal.  Instead it must propagate to the top-level error
boundary and surface as a categorically different typed envelope.

Real-behavior test: uses a genuinely corrupt ``active-profile`` pointer
file on disk to trigger the unexpected-exception path through the real
production call stack.  No monkeypatching, no test doubles.

The call chain under test:
  ``aeat app ledger ratios list``
    → ``_ratios_bucket_and_profile()``
      → ``require_active_bucket_id()``
        → ``resolve_active_bucket_id()``
          → ``read_pointer(storage_root)``
            → ``BucketPointer.from_toml(corrupt_text)``
              → ``pydantic.ValidationError`` (not CadrumoError)

Before contract the broad ``except Exception`` erased this distinction. After
contract only ``NoActiveProfileError`` is caught and the
``pydantic.ValidationError`` reaches the typed CLI validation boundary.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.bucket_pointer import pointer_path
from ....tests.cli_envelope import require_error_document
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root
from .sessionless_root_fixtures import _sessionless_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _object_member(document: dict[str, object], key: str) -> dict[str, object]:
    member = document[key]
    assert isinstance(member, dict)
    return {str(name): value for name, value in member.items()}


__all__ = ["_sessionless_root"]


@pytest.fixture
def _corrupt_pointer_root(tmp_path: Path) -> Iterator[Path]:
    """Storage root whose active-profile pointer file contains a partial TOML payload.

    The file is valid TOML but is missing the required ``bucket_id`` field, so
    ``BucketPointer.model_validate`` raises a ``pydantic.ValidationError`` — which
    is NOT an ``CadrumoError`` subclass.

    Before contract this exception was silently reclassified as the "no active
    profile" refusal by the broad ``except Exception`` clause.  After contract
    only ``NoActiveProfileError`` is caught; the ``pydantic.ValidationError``
    propagates to the top-level CLI error boundary and surfaces as the
    validation-boundary envelope.
    """
    with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
        pointer_file = pointer_path(storage_root)
        pointer_file.parent.mkdir(parents=True, exist_ok=True)
        # Valid TOML syntax, but missing ``bucket_id`` — triggers ValidationError.
        pointer_file.write_text("schema_version = 1\n", encoding="utf-8")
        yield storage_root


# ---------------------------------------------------------------------------
# Baseline: NoActiveProfileError still maps to the profile-create refusal
# ---------------------------------------------------------------------------


def test_no_pointer_projects_the_canonical_profile_action(_sessionless_root: Path) -> None:
    """With no pointer file the expected NoActiveProfileError surfaces as the
    profile-create guidance — the narrow except still catches it correctly."""
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "ratios", "list"])

    assert result.exit_code != 0
    error = _object_member(require_error_document(result.output), "error")
    action = _object_member(error, "action")
    assert action["failed_condition_id"] == "profile.active.available"
    reference = _object_member(action, "action")
    assert reference["action_id"] == "operator.profile.create"
    assert reference["target_command_key"] == "config.profile.create"
    assert action["conditionality"] == "requires_arguments"
    assert action["missing_argument_names"] == ["profile_name"]
    assert action["no_recovery_outcome"] is None


# ---------------------------------------------------------------------------
# Core assertion: unexpected exception must NOT become the no-profile refusal
# ---------------------------------------------------------------------------


def test_corrupt_pointer_projects_the_validation_boundary(
    _corrupt_pointer_root: Path,
) -> None:
    """A corrupt pointer file raises a non-CadrumoError that must NOT be swallowed
    as the 'no active profile' refusal.

    Before contract the broad ``except Exception`` caught every exception and
    converted it to the same profile-create guidance, hiding the real error.
    After contract only ``NoActiveProfileError`` is caught; the
    ``pydantic.ValidationError`` from the corrupt pointer propagates to the
    top-level CLI error boundary and surfaces as a validation-boundary
    envelope with its own condition evidence and terminal outcome.
    """
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "ratios", "list"])

    assert result.exit_code != 0
    error = _object_member(require_error_document(result.output), "error")
    assert error["code"] == "REFUSED_CLI_VALIDATION_BOUNDARY"
    action = _object_member(error, "action")
    assert action["failed_condition_id"] == "cli.validation.boundary_clean"
    assert action["evidence"] == [
        {
            "condition_id": "cli.validation.boundary_clean",
            "evidence_id": "cli.validation.boundary_clean.observation",
            "provenance": "runtime_observation",
            "values": {"boundary_error_type": "CliValidationBoundaryError"},
        }
    ]
    assert action["action"] is None
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"
