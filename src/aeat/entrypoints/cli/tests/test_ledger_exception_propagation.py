"""Verify that non-NoActiveProfileError exceptions propagate unchanged.

contract assertion: after contract narrows the broad ``except Exception`` catch in
``_ratios_bucket_id``, ``_ratios_bucket_and_profile``, and
``_rule_bucket_id`` to ``except NoActiveProfileError``, any unexpected
exception (e.g. a corrupt active-profile pointer file producing a
``pydantic.ValidationError``) must NOT be swallowed as the "no active
profile" refusal.  Instead it must propagate to the top-level error
boundary and surface as a categorically different response — a
validation-boundary or unexpected-internal-error envelope, never the
profile-create guidance.

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
              → ``pydantic.ValidationError`` (not AeatError)

Before contract: the broad ``except Exception`` caught this and produced the
profile-create guidance — masking the real error.
After contract: only ``NoActiveProfileError`` is caught; the
``pydantic.ValidationError`` propagates to the CLI boundary and surfaces
as a ``CliValidationBoundaryError`` ("validation" / "repair").
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Text that the "no active profile" refusal always contains — used as the
# anti-marker to confirm a response is NOT the profile-create guidance.
_PROFILE_CREATE_GUIDANCE = "profile create"


@pytest.fixture(autouse=True)
def _english_output() -> Iterator[None]:
    with override_settings(aeat_output_language="en"):
        yield


@pytest.fixture
def _no_pointer_root(tmp_path: Path) -> Iterator[Path]:
    """Storage root with no active-profile pointer — clean cold-start state."""
    with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


@pytest.fixture
def _corrupt_pointer_root(tmp_path: Path) -> Iterator[Path]:
    """Storage root whose active-profile pointer file contains a partial TOML payload.

    The file is valid TOML but is missing the required ``bucket_id`` field, so
    ``BucketPointer.model_validate`` raises a ``pydantic.ValidationError`` — which
    is NOT an ``AeatError`` subclass.

    Before contract this exception was silently reclassified as the "no active
    profile" refusal by the broad ``except Exception`` clause.  After contract
    only ``NoActiveProfileError`` is caught; the ``pydantic.ValidationError``
    propagates to the top-level CLI error boundary and surfaces as the
    validation-boundary envelope.
    """
    with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
        pointer_path = storage_root / "active-profile"
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        # Valid TOML syntax, but missing ``bucket_id`` — triggers ValidationError.
        pointer_path.write_text("schema_version = 1\n", encoding="utf-8")
        yield storage_root


# ---------------------------------------------------------------------------
# Baseline: NoActiveProfileError still maps to the profile-create refusal
# ---------------------------------------------------------------------------


def test_no_pointer_produces_profile_create_guidance(_no_pointer_root: Path) -> None:
    """With no pointer file the expected NoActiveProfileError surfaces as the
    profile-create guidance — the narrow except still catches it correctly."""
    result = invoke_cached_cli(["app", "ledger", "ratios", "list"])

    assert result.exit_code != 0, f"Expected non-zero exit but got 0: {result.output}"
    assert _PROFILE_CREATE_GUIDANCE in result.output, (
        f"Expected profile-create guidance in output; got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Core assertion: unexpected exception must NOT become the no-profile refusal
# ---------------------------------------------------------------------------


def test_corrupt_pointer_does_not_produce_profile_create_guidance(
    _corrupt_pointer_root: Path,
) -> None:
    """A corrupt pointer file raises a non-AeatError that must NOT be swallowed
    as the 'no active profile' refusal.

    Before contract the broad ``except Exception`` caught every exception and
    converted it to the same profile-create guidance, hiding the real error.
    After contract only ``NoActiveProfileError`` is caught; the
    ``pydantic.ValidationError`` from the corrupt pointer propagates to the
    top-level CLI error boundary and surfaces as a validation-boundary
    envelope — a categorically different response that mentions "repair" or
    "validation", never "profile create".
    """
    result = invoke_cached_cli(["app", "ledger", "ratios", "list"])

    assert result.exit_code != 0, f"Expected non-zero exit but got 0: {result.output}"
    assert _PROFILE_CREATE_GUIDANCE not in result.output, (
        "Corrupt-pointer error was silently reclassified as 'no active profile' — "
        "the broad except Exception catch is still in place.\n"
        f"Output:\n{result.output}"
    )
    # The pydantic.ValidationError propagates to the CLI boundary and is
    # wrapped as CliValidationBoundaryError, which renders a "validation" /
    # "repair" message — confirming the error was not swallowed.
    output_lower = result.output.lower()
    assert "validation" in output_lower or "repair" in output_lower, (
        "Expected validation-boundary or repair-hint in output; "
        f"the non-AeatError may not have propagated correctly.\n"
        f"Output:\n{result.output}"
    )
