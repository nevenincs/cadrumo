"""Real-behaviour proof that the no-echo secret prompt refuses rather than echoes.

:func:`getpass.getpass` silently degrades to an *echoing* read whenever it
cannot control the terminal. These tests drive real interpreter subprocesses —
no mocks, stubs, monkeypatches, skips, or expected-fail markers — to prove
three things in order:

1. the echo fallback is genuinely reachable in this interpreter (the
   vulnerability is real, not theoretical);
2. the real production
   :func:`~cadrumo.entrypoints.cli._config.secure_input.prompt_secret_no_echo`
   refuses under that same condition and never returns a value;
3. the refusal carries a resolvable operator-facing locale key.

The precondition is constructed the way it arises in the wild: an upstream
layer rebinds ``sys.stdin`` inside its own process before the CLI runs. The
subprocess rebinds *its own* stdin — the code under test is never patched.
"""

from __future__ import annotations

import json
import pathlib
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
    parsed = json.loads(stdout.splitlines()[-1])
    assert isinstance(parsed, dict), stdout
    verdict: dict[str, object] = {}
    for key, value in parsed.items():
        assert isinstance(key, str), stdout
        verdict[key] = value
    return verdict


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


def test_prompt_secret_no_echo_refuses_a_character_device_with_no_console() -> None:
    """A promptable-looking channel that cannot be typed into refuses, never returns.

    ``os.devnull`` is a real OS device, not a double, and on Windows it is the
    exact false positive this guard exists to catch: it reports
    ``isatty() == True`` while no console input queue exists behind it, so the
    older isatty()-only guard would have admitted it and the prompt would then
    have blocked forever.
    """
    verdict = _run_probe(
        """
        import json, os, sys
        sys.stdin = open(os.devnull)
        from cadrumo.entrypoints.cli._config._secure_input import prompt_secret_no_echo
        from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
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
    assert verdict["key"] == _NON_INTERACTIVE_KEY, (
        "a character device with no console behind it is not a promptable terminal, "
        f"so the interactive guard must be the one that fires; got {verdict['key']!r}"
    )
    if verdict["platform"] == "win32":
        # The precise trap: Windows calls this stdin a TTY, and the older
        # isatty()-only guard would have let it through to a blocking prompt.
        assert verdict["isatty"] is True, (
            "expected the Windows NUL device to report isatty() True - the false "
            "positive the real-console precondition exists to catch"
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
                from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
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


def test_console_less_host_refuses_instead_of_blocking_forever(tmp_path: pathlib.Path) -> None:
    """A console-less host refuses promptly rather than hanging on the prompt.

    This is the regression for the hang, and it is why the guard checks for a
    real console rather than trusting ``isatty()``. Windows reports
    ``isatty() == True`` for a character device with no console behind it, and
    ``getpass`` then calls ``msvcrt.getwch()``, which BLOCKS FOREVER instead of
    returning or raising — a prompt an operator can never satisfy and cannot
    diagnose.

    The condition is constructed for real, with no patching: a genuine
    ``DETACHED_PROCESS`` spawn. The test fails on timeout, so a regression that
    re-introduces the block cannot pass by hanging. On non-win32 the same spawn
    yields a non-tty ``/dev/null`` stdin, which refuses on the same key, so the
    assertions hold everywhere without a skip.
    """
    verdict_path = tmp_path / "verdict.json"
    probe = textwrap.dedent(
        f"""
        import json, sys
        from cadrumo.entrypoints.cli._config._secure_input import prompt_secret_no_echo
        from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
        try:
            value = prompt_secret_no_echo("secret: ")
            verdict = {{"outcome": "returned", "value_length": len(value)}}
        except CliRefusedBoundaryError as exc:
            verdict = {{"outcome": "refused", "key": exc.translated_message}}
        except BaseException as exc:
            verdict = {{"outcome": "escaped", "error_type": type(exc).__name__}}
        verdict["isatty"] = sys.stdin.isatty()
        open({str(verdict_path)!r}, "w", encoding="utf-8").write(json.dumps(verdict))
        """,
    )

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [sys.executable, "-c", probe],
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        pytest.fail(
            "the no-echo prompt BLOCKED on a console-less host instead of refusing; "
            "the real-console precondition has regressed",
        )

    assert verdict_path.exists(), "the console-less probe produced no verdict"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert verdict["outcome"] == "refused", (
        f"a console-less host must refuse, not proceed to a blocking prompt; got {verdict!r}"
    )
    assert verdict["key"] == _NON_INTERACTIVE_KEY, (
        f"a channel with no console behind it is not an interactive terminal; got {verdict['key']!r}"
    )


def test_real_console_with_rebound_stdin_refuses_the_echo_fallback(tmp_path: pathlib.Path) -> None:
    """On a GENUINE console, a rebound stdin still refuses rather than echoing.

    The real-console precondition now fires first, so a fake-console stdin can
    no longer reach the echo-suppression guard. This isolates that guard on the
    one channel where it is the deciding check: a true console (so the
    interactive and real-console preconditions both pass) whose ``sys.stdin``
    an upstream layer has rebound (so ``win_getpass`` would pick the echoing
    fallback). ``CONIN$`` is a second genuine handle to the same console — a
    real OS object, not a double.

    On non-win32 the identity guard is deliberately absent, because
    ``unix_getpass`` opens the terminal device itself and suppresses echo
    regardless; that branch asserts precisely that documented contract instead.
    """
    if sys.platform != "win32":
        from ..secure_input import _stdin_is_a_real_console

        assert _stdin_is_a_real_console() is True, (
            "on POSIX the console probe defers to isatty(), because unix_getpass "
            "opens the terminal device itself rather than blocking on a fake one"
        )
        return

    verdict_path = tmp_path / "verdict.json"
    probe = textwrap.dedent(
        f"""
        import json, sys
        sys.stdin = open("CONIN$")
        from cadrumo.entrypoints.cli._config._secure_input import (
            _stdin_is_a_real_console,
            prompt_secret_no_echo,
        )
        from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
        verdict = {{
            "is_dunder": sys.stdin is sys.__stdin__,
            "isatty": sys.stdin.isatty(),
            "real_console": _stdin_is_a_real_console(),
        }}
        try:
            value = prompt_secret_no_echo("secret: ")
            verdict["outcome"] = "returned"
            verdict["value_length"] = len(value)
        except CliRefusedBoundaryError as exc:
            verdict["outcome"] = "refused"
            verdict["key"] = exc.translated_message
        except BaseException as exc:
            verdict["outcome"] = "escaped"
            verdict["error_type"] = type(exc).__name__
        open({str(verdict_path)!r}, "w", encoding="utf-8").write(json.dumps(verdict))
        """,
    )

    process = subprocess.Popen(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [sys.executable, "-c", probe],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    try:
        process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        pytest.fail("the prompt blocked on a real console with rebound stdin instead of refusing")

    assert verdict_path.exists(), "the console probe produced no verdict"
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))

    # Preconditions: this really is the isolating channel, not a repeat of the
    # non-interactive case. Without these the refusal below proves nothing.
    assert verdict["real_console"] is True, f"probe did not obtain a real console: {verdict!r}"
    assert verdict["isatty"] is True, f"probe stdin is not a tty: {verdict!r}"
    assert verdict["is_dunder"] is False, f"probe failed to rebind stdin: {verdict!r}"

    assert verdict["outcome"] == "refused", (
        f"a rebound stdin must refuse rather than read through the echoing fallback; got {verdict!r}"
    )
    assert verdict["key"] == _ECHO_KEY, (
        f"the echo-suppression guard must be the one that fires here; got {verdict['key']!r}"
    )


def test_echo_suppression_refusal_key_resolves_to_operator_copy() -> None:
    """The new refusal key resolves to real copy in the active catalogue."""
    resolved = tr(_ECHO_KEY)

    assert _ECHO_KEY not in resolved, f"key {_ECHO_KEY!r} was not substituted; got {resolved!r}"
    assert len(resolved) > 10, f"key {_ECHO_KEY!r} resolved to suspiciously short copy: {resolved!r}"


def test_the_predicate_predicts_the_refusal_it_names() -> None:
    """``terminal_can_prompt_for_secrets`` answers False exactly where the prompt refuses.

    ``config login`` routes on this predicate to decide whether to supply
    the hardened prompt at all, keeping the substrate's own refusal and
    exit code on a channel that could not have been prompted anyway. That
    routing is only correct while the predicate and the prompt agree, and
    they can only be trusted to agree while they share one implementation
    — this is the test that extracting the predicate did not fork them.

    Driven through a subprocess on a redirected pipe rather than the
    suite's own stdin, so the non-console condition is created rather than
    hoped for: the answer is then the same on a CI runner and on a
    developer's console, and the test never has to opt out of running.
    Both halves are asserted from the one probe, which is what makes this
    a claim about their agreement rather than two separate facts.
    """
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import json
                from cadrumo.entrypoints.cli._config._secure_input import (
                    prompt_secret_no_echo,
                    terminal_can_prompt_for_secrets,
                )
                from cadrumo.entrypoints.cli.errors import CliRefusedBoundaryError
                verdict = {"predicate": terminal_can_prompt_for_secrets()}
                try:
                    value = prompt_secret_no_echo("secret: ")
                    verdict |= {"outcome": "returned", "value_length": len(value)}
                except CliRefusedBoundaryError as exc:
                    verdict |= {"outcome": "refused", "key": exc.translated_message}
                except BaseException as exc:
                    verdict |= {"outcome": "escaped", "error_type": type(exc).__name__}
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

    assert verdict["predicate"] is False, f"a redirected pipe must not be reported as promptable; got {verdict!r}"
    assert verdict["outcome"] == "refused", (
        f"the predicate said this channel cannot be prompted, so the prompt must refuse; got {verdict!r}"
    )
    assert verdict["key"] == _NON_INTERACTIVE_KEY, (
        f"the non-interactive refusal must be the one that fires here; got {verdict['key']!r}"
    )
