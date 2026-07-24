"""Real-behaviour proof that the no-echo secret prompt refuses rather than echoes.

:func:`getpass.getpass` silently degrades to an *echoing* read whenever it
cannot control the terminal. These tests drive real interpreter subprocesses —
no mocks, stubs, monkeypatches, skips, or expected-fail markers — to prove
three things in order:

1. the echo fallback is genuinely reachable in this interpreter (the
   vulnerability is real, not theoretical);
2. the real production
   :func:`~cadrumo.entrypoints.cli._config._secure_input.prompt_secret_no_echo`
   refuses under that same condition and never returns a value;
3. the refusal carries a resolvable operator-facing locale key.

The precondition is constructed the way it arises in the wild: an upstream
layer rebinds ``sys.stdin`` inside its own process before the CLI runs. The
subprocess rebinds *its own* stdin — the code under test is never patched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from .....core.i18n import tr

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ECHO_KEY = "cli.config.custody.errors.echo_suppression_unavailable"
_NON_INTERACTIVE_KEY = "cli.config.custody.errors.non_interactive_secret_required"
_PLANTED_SECRET = "correct-horse-battery-staple"  # noqa: S105 - probe input, not a credential


def _run_probe(body: str) -> dict[str, object]:
    """Run ``body`` in a real interpreter and return its JSON verdict."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    stdout = completed.stdout.strip()
    assert stdout, (
        f"probe produced no verdict (exit {completed.returncode})\n"
        f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"
    )
    return json.loads(stdout.splitlines()[-1])


def test_stdlib_getpass_really_falls_back_to_an_echoing_read() -> None:
    """The unguarded stdlib path returns the secret via the echoing fallback.

    This is the anti-tautology anchor for the guard below: it proves the
    degradation is reachable in this exact interpreter, so a passing refusal
    test cannot be passing vacuously.
    """
    verdict = _run_probe(
        f"""
        import io, json, sys, warnings
        # An upstream layer rebinds stdin - the precondition win_getpass uses
        # to choose fallback_getpass. Nothing in the app is patched.
        sys.stdin = io.StringIO({_PLANTED_SECRET!r} + chr(10))
        import getpass
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = getpass.getpass("secret: ")
        print(json.dumps({{
            "returned": value,
            "warned_about_echo": any(
                issubclass(w.category, getpass.GetPassWarning) for w in caught
            ),
            "stdin_rebound": sys.stdin is not sys.__stdin__,
        }}))
        """,
    )

    assert verdict["stdin_rebound"] is True, "probe failed to construct the precondition"
    assert verdict["returned"] == _PLANTED_SECRET, (
        f"expected the unguarded stdlib to read the secret through the echoing fallback; got {verdict['returned']!r}"
    )
    assert verdict["warned_about_echo"] is True, (
        "expected GetPassWarning from fallback_getpass; the stdlib contract the production guard relies on has changed"
    )


def test_prompt_secret_no_echo_refuses_when_echo_cannot_be_suppressed() -> None:
    """The production prompt refuses and returns nothing when echo is unguaranteed.

    ``os.devnull`` is a real OS device, not a double. On Windows it reports
    ``isatty() == True`` (so the prompt reaches the echo-suppression guards);
    on POSIX it reports ``False`` (so the pre-existing non-interactive guard
    refuses first). Either way the security property is identical and is what
    this asserts: refuse, never return a value.
    """
    verdict = _run_probe(
        """
        import json, os, sys
        sys.stdin = open(os.devnull)
        from cadrumo.entrypoints.cli._config._secure_input import prompt_secret_no_echo
        from cadrumo.entrypoints.cli._errors import CliRefusedBoundaryError
        try:
            value = prompt_secret_no_echo("secret: ")
            verdict = {"outcome": "returned", "value_length": len(value)}
        except CliRefusedBoundaryError as exc:
            verdict = {"outcome": "refused", "key": exc.translated_message}
        except BaseException as exc:
            verdict = {"outcome": "escaped", "error_type": type(exc).__name__}
        verdict["platform"] = sys.platform
        verdict["isatty"] = sys.stdin.isatty()
        print(json.dumps(verdict))
        """,
    )

    assert verdict["outcome"] == "refused", (
        f"the no-echo prompt must refuse when echo suppression is unguaranteed; got {verdict!r}"
    )
    assert verdict["key"] in {_ECHO_KEY, _NON_INTERACTIVE_KEY}, (
        f"refusal must carry a custody refusal key, got {verdict['key']!r}"
    )
    if verdict["platform"] == "win32" and verdict["isatty"] is True:
        # Past the non-interactive guard, so the echo-suppression guard is the
        # one that must have fired - the High finding's exact condition.
        assert verdict["key"] == _ECHO_KEY, (
            "a Windows stdin that is a character device but not sys.__stdin__ is the "
            f"echo-fallback precondition; expected {_ECHO_KEY!r}, got {verdict['key']!r}"
        )


def test_prompt_secret_no_echo_refuses_a_plain_redirected_pipe() -> None:
    """A redirected (non-tty) stdin refuses without consuming the planted secret."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import json, sys
                from cadrumo.entrypoints.cli._config._secure_input import prompt_secret_no_echo
                from cadrumo.entrypoints.cli._errors import CliRefusedBoundaryError
                try:
                    value = prompt_secret_no_echo("secret: ")
                    verdict = {"outcome": "returned", "value_length": len(value)}
                except CliRefusedBoundaryError as exc:
                    verdict = {"outcome": "refused", "key": exc.translated_message}
                except BaseException as exc:
                    verdict = {"outcome": "escaped", "error_type": type(exc).__name__}
                print(json.dumps(verdict))
                """,
            ),
        ],
        input=f"{_PLANTED_SECRET}\n",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    verdict = json.loads(completed.stdout.strip().splitlines()[-1])

    assert verdict["outcome"] == "refused", f"expected a refusal on redirected stdin; got {verdict!r}"
    assert verdict["key"] == _NON_INTERACTIVE_KEY
    assert _PLANTED_SECRET not in completed.stdout, "the planted secret must never be echoed to stdout"
    assert _PLANTED_SECRET not in completed.stderr, "the planted secret must never be echoed to stderr"


def test_echo_suppression_refusal_key_resolves_to_operator_copy() -> None:
    """The new refusal key resolves to real copy in the active catalogue."""
    resolved = tr(_ECHO_KEY)

    assert _ECHO_KEY not in resolved, f"key {_ECHO_KEY!r} was not substituted; got {resolved!r}"
    assert len(resolved) > 10, f"key {_ECHO_KEY!r} resolved to suspiciously short copy: {resolved!r}"
