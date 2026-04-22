"""Lock the live-submit deferral guarantee at Kent's first-contact surface (wave 133).

The 2026-04-18 live-submit-cli-excision ADR and charter #116
(live-write safety, six non-negotiable rules) require that no
default CLI path can invoke a live AEAT submission — the capability
is deferred to milestone 1.0.0 behind stricter gates.

Existing coverage (wave-80c ``test_no_submit_command.py``) locks:
- The ``submit`` command is not registered under the submission
  sub-app.
- The ``submission --help`` text says "no default CLI live-submit
  command".
- The submit-button CSS selector doesn't leak into the CLI tree.

Wave 133 extends the lock TWO layers outward so Kent's first-
contact surface (``aeat --help``) surfaces the same guarantee:

1. The top-level ``aeat --help`` lists the ``submission`` sub-app
   with the "no default CLI live-submit command" disclaimer.
2. The ``SubmissionEngine`` default for ``live_transport_supported``
   is ``False``. A programmatic caller must explicitly opt in —
   this matches the project mandates' "the engine default is False
   (opt-in only)" rule.
"""

from __future__ import annotations

import inspect

import pytest
from typer.testing import CliRunner

from ...cli import app as root_app
from ...submission import SubmissionEngine

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]

_RUNNER = CliRunner()


def test_top_level_help_advertises_submission_with_deferral_disclaimer() -> None:
    """``aeat --help`` must list the ``submission`` sub-app and must say
    live submit is not on the default CLI — so Kent, reading the tool's
    opening page, immediately sees the safety posture.

    Checks the typer app's stored sub-app metadata directly rather than
    the rich-wrapped stdout so narrow test terminals can't truncate the
    assertion target."""
    # Look up the submission group in the root app's registered groups.
    submission_group = next(
        (g for g in root_app.registered_groups if g.name == "submission"),
        None,
    )
    assert submission_group is not None, "root app missing `submission` sub-app"
    help_text = submission_group.help
    if help_text is None and submission_group.typer_instance is not None:
        help_text = submission_group.typer_instance.info.help
    flat = " ".join((help_text or "").split())
    assert "no default CLI live-submit command" in flat, (
        f"submission sub-app's help string (shown under `aeat --help`) must carry the "
        f"live-submit deferral disclaimer. Got: {flat!r}"
    )


def test_submission_engine_live_transport_defaults_to_false() -> None:
    """Any programmatic caller that forgets to pass ``live_transport_supported=True``
    gets a SubmissionEngine that refuses live submit — matches the project
    mandates' "engine default is False (opt-in only)" rule."""
    sig = inspect.signature(SubmissionEngine)
    param = sig.parameters.get("live_transport_supported")
    assert param is not None, "SubmissionEngine lost its live_transport_supported parameter"
    assert param.default is False, (
        f"SubmissionEngine.live_transport_supported default is {param.default!r}; "
        "must stay False per 2026-04-18 live-submit-cli-excision-adr + .claude/rules/"
        "aeat-project-mandates.md ('the engine default is False')."
    )


def test_submission_engine_accepts_explicit_opt_in() -> None:
    """The engine must still accept ``live_transport_supported=True`` for test
    fixtures and future 1.0.0 callers — the default stays False, but the
    parameter itself is part of the contract."""
    sig = inspect.signature(SubmissionEngine)
    assert "live_transport_supported" in sig.parameters
