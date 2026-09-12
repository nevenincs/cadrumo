"""Precedence-chain tests for the active-profile resolver.

The resolver lives at `cadrumo.core.bucket_pointer.resolve_active_bucket_id`. It consults
two precedence rungs in order:

1. `Settings.cadrumo_active_profile` (`CADRUMO_ACTIVE_PROFILE` env var, or
   an `override_settings(cadrumo_active_profile=...)` context manager).
2. The plaintext `<cadrumo-root>/active-profile` pointer file written
   by `register_active_profile` / `select_profile`.

A missing pointer + missing env override returns `None` so callers
that surface it to the operator can refuse with a typed
`NoActiveProfileError`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from .....application.wizard import compiler as _wizard  # noqa: F401
from .....application.workflow.active_profile import resolve_active_profile_record
from .....application.workflow.state_models import WorkflowState
from .....core.bucket_pointer import BucketPointer, resolve_active_bucket_id, write_pointer
from .....core.config import override_settings
from .....core.errors.error_codes import get_registered_error_code
from .....core.errors.hierarchy import NoActiveProfileError
from .....core.profile_session import ProfileRecordUnavailability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_workflow_models_do_not_expose_active_bucket_resolver_shims() -> None:
    """Workflow models must not be an alternate import path for core resolvers."""

    source = Path(__file__).parents[1].joinpath("state_models.py").read_text(encoding="utf-8")
    assert "resolve_active_bucket_id" not in source
    assert "require_active_bucket_id" not in source


def test_resolver_uses_active_profile_precedence_chain(tmp_path: Path) -> None:
    """Settings override wins over the active-profile pointer; blank settings fall through."""
    cases = (
        (None, None, None),
        (None, "catering", "catering"),
        ("translation", "catering", "translation"),
        ("   ", "catering", "catering"),
    )

    for index, (settings_profile, pointer_bucket_id, expected_bucket_id) in enumerate(cases):
        case_root = tmp_path / f"precedence-{index}"
        case_root.mkdir()
        if pointer_bucket_id is not None:
            write_pointer(case_root, BucketPointer.selected(bucket_id=pointer_bucket_id, transition_revision=1))

        with override_settings(cadrumo_active_profile=settings_profile, cadrumo_local_storage_root=case_root):
            assert resolve_active_bucket_id() == expected_bucket_id


def test_no_active_profile_error_has_registered_error_code() -> None:
    """The workflow no-active-profile export must bind to the relocated core error."""

    code = get_registered_error_code(NoActiveProfileError)
    assert code.code == "REFUSED_NO_ACTIVE_PROFILE"
    assert code.message_key == "errors.refused.refused_no_active_profile"


def test_active_profile_record_names_an_absent_capsule_as_the_reason(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pointer without a current capsule returns no record, and says which absence it is.

    The convenience accessor still collapses to ``None``; the resolution beside
    it carries the reason, which is what a projection reporting the absence to
    an operator must read. A selector with no committed capsule is the one
    absence that genuinely means the record is not there.
    """

    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    write_pointer(tmp_path, BucketPointer.selected(bucket_id=bucket_id, transition_revision=1))
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        caplog.set_level(logging.DEBUG, logger="cadrumo.application.workflow.active_profile")

        state = WorkflowState()
        assert state.active_profile_record() is None
        resolution = resolve_active_profile_record()

    assert resolution.record is None
    assert resolution.unavailability is ProfileRecordUnavailability.NO_LIVE_CAPSULE
    assert "active profile record resolution found no live bucket for the selected profile" in caplog.text
    # The reason-erasing framing this replaced must not return unnoticed.
    assert "returned no profile record" not in caplog.text
    assert bucket_id not in caplog.text
