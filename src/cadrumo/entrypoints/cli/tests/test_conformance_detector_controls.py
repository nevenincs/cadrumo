"""Positive controls for the CLI conformance detectors that lacked one.

Three standards gate the CLI surface: the pull/``--file`` naming standard, the
envelope/notice channel, and documented-command coverage. Each has a shipped
gate, but a gate only earns trust once it has been shown to return a NON-empty
answer: a detector that reports nothing is indistinguishable from a surface with
nothing to report, and every conformance assertion built on it then passes for
the wrong reason.

The suggestion-citation gate already carries its own controls
(``test_scanner_flags_a_dead_citation`` and siblings), and the JSON-schema gate
controls its secret-field scan with a planted secret. Two detectors had none:

- ``_validate_command``, the documented-command gate's high-signal option
  validity and dead-subcommand check -- the one that catches a doc citing a real
  verb with an option it does not have; and
- ``_is_forbidden_notice_field``, the check that no result schema regrows a
  bespoke ``advisory`` / ``next`` / ``suggestion`` field beside the envelope's
  one diagnostic channel.

Both are driven here through their real producers rather than by hand-building
their inputs: the doc controls feed ``_cited_commands`` the fenced text a doc
page actually contains and let it emit the citation, so a parser change that
stopped producing citations reds these controls instead of quietly narrowing
what the gate sees.

The over-fire direction is controlled too, and deliberately. Primary structured
result data a command exists to produce -- verify ``findings``, calendar
``warnings``, a ``next_due`` date, a per-finding ``next_action`` -- is output,
not an incidental diagnostic, and a detector that flagged it would push authors
to hide legitimate result fields from their own schemas. A control proving only
that the detector fires would be satisfied by one that fires on everything.
"""

from __future__ import annotations

import pytest

from .test_documented_command_conformance import _cited_commands, _validate_command
from .test_json_schema_conformance import _is_forbidden_notice_field

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: A real leaf verb with real options, used as the clean control. Chosen because
#: it is a live command whose parameters the detector resolves from the tree, so
#: the "clean" reading below is a statement about the real CLI rather than about
#: a fixture.
_LIVE_VERB = "aeat app ledger evidence batch"
_LIVE_GROUP = "aeat app ledger evidence"


def _fenced(command: str) -> str:
    """Return the fenced console block a documentation page would actually carry."""
    return f"```console\n$ {command}\n```\n"


def _violations_for(command: str) -> list[str]:
    """Return the documented-command gate's verdict on one cited invocation."""
    cited = _cited_commands(_fenced(command))
    assert cited, (
        f"the citation producer emitted nothing for {command!r}, so the control below would assert over an "
        "empty list and hold vacuously. The doc parser, not the detector, is what broke."
    )
    return [violation for entry in cited for violation in _validate_command(entry)]


def test_the_option_validity_detector_flags_an_option_the_command_does_not_have() -> None:
    """A doc citing a live verb with a fabricated option must be reported.

    This is the defect class the verb-only sibling gate cannot see: the command
    path resolves, so a check that stopped at resolution stays green while the
    operator is handed an invocation that fails on parse.
    """
    violations = _violations_for(f"{_LIVE_VERB} --kind received --not-a-real-option x")
    assert violations, (
        "the option-validity detector reported nothing for a deliberately fabricated option; every "
        "documented-command assertion resting on it would pass without checking anything"
    )
    assert any("--not-a-real-option" in violation for violation in violations), (
        f"the detector fired but did not name the offending option: {violations}"
    )


def test_the_option_validity_detector_stays_silent_on_the_real_options() -> None:
    """The same verb cited with its real options must be clean.

    Without this, the control above is satisfied by a detector that flags every
    option it sees, which would red the gate on correct documentation and train
    authors to stop citing options at all.
    """
    assert _violations_for(f"{_LIVE_VERB} --kind received --file statement.pdf") == []


def test_the_dead_subcommand_detector_flags_a_verb_the_group_does_not_expose() -> None:
    """A leftover token under a live GROUP can only be a subcommand that does not exist.

    This is the shape that let a renamed verb stay cited in the docs while being
    uninvokable: longest-prefix resolution stops at the group and treats the dead
    token as a positional, which a group never takes.
    """
    violations = _violations_for(f"{_LIVE_GROUP} not-a-subcommand")
    assert violations, "the dead-subcommand detector reported nothing for a verb the group does not expose"
    assert any("not-a-subcommand" in violation for violation in violations), (
        f"the detector fired but did not name the dead token: {violations}"
    )


@pytest.mark.parametrize(
    "field_name",
    ["next", "suggestion", "suggestions", "hint", "advisory", "advisories", "source_advisories"],
)
def test_the_bespoke_notice_detector_flags_a_smuggled_diagnostic_field(field_name: str) -> None:
    """Each name the standard forbids on a result schema must be reported."""
    assert _is_forbidden_notice_field(field_name), (
        f"{field_name!r} is a bespoke diagnostic field the notice standard forbids on a result schema, "
        "but the detector does not report it, so a schema regrowing it would pass the conformance gate"
    )


@pytest.mark.parametrize("field_name", ["authorization_advisory", "source_advisories", "stale_draft_advisories"])
def test_the_bespoke_notice_detector_flags_the_suffix_smuggling_shape(field_name: str) -> None:
    """The ``*_advisory`` / ``*_advisories`` suffix is the shape a per-command name hides behind.

    A literal-name set alone would be defeated by prefixing: ``advisory`` is
    caught, ``authorization_advisory`` is the same field wearing a command's
    name. The suffix rule is what makes the check general, so it is controlled
    separately from the literal set above.
    """
    assert _is_forbidden_notice_field(field_name)


@pytest.mark.parametrize("field_name", ["findings", "warnings", "next_due", "next_action", "notices", "result"])
def test_the_bespoke_notice_detector_leaves_primary_result_data_alone(field_name: str) -> None:
    """Primary structured output a command exists to produce is not a diagnostic.

    Verify ``findings``, calendar ``warnings``, a ``next_due`` date and a
    per-finding ``next_action`` are the command's result, not incidental
    advisories smuggled beside the notice channel. A detector that flagged them
    would be over-firing on exactly the payloads the standard permits, and the
    firing controls above cannot distinguish that from a correct detector.
    """
    assert not _is_forbidden_notice_field(field_name), (
        f"{field_name!r} is primary result data the notice standard explicitly allows, but the detector "
        "reports it as a bespoke diagnostic; the conformance gate would red on a conformant schema"
    )
