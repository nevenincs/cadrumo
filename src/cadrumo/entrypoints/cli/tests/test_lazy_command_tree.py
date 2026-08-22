"""The state-free CLI surfaces must not pay the registry cost.

Two docstrings assert that this gate exists. ``application.user_profile``'s
package docstring says the boundary's laziness is enforced by "the
:mod:`entrypoints.cli.tests.test_lazy_command_tree` gate and the producer-side
probe in :mod:`application.user_profile.tests.test_lazy_boundary`", and the
producer-side probe says the same in reverse: "The CLI-side gate ... enforces
that the state-free CLI surfaces do not transitively load the registry. This
module pins the same contract at the *producer* boundary."

Only the producer-side half existed. This module is the CLI-side half those
sentences describe, restored under the name they cite so the references resolve
again.

The two halves are not redundant. The producer probe imports
``cadrumo.application.user_profile`` alone; this one drives the real command
tree, which reaches the boundary through Typer registration, group callbacks
and Click's help rendering. An eager import re-introduced anywhere along THAT
path -- in a command module, a callback default, a help string built at import
time -- is invisible to the producer probe and lands here.

The property was measured before this gate was written, and it holds: building
the command tree and rendering ``--help`` and ``--version`` loads zero registry
modules. So this pins behaviour that is currently correct rather than
documenting a defect.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Emitted by the probe so a run that never reached the assertion is visible.
_COMPLETED = "PROBE-COMPLETED"

#: Substituted into a probe AFTER dedent, so it carries no indentation of its own.
_LEAK_SCAN_MARKER = "# <leak-scan>"
_LEAK_SCAN = 'leaked = sorted(\n    name\n    for name in sys.modules\n    if name == "cadrumo.domain.calculations.registry"\n    or name.startswith("cadrumo.domain.calculations.registry.")\n)'


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run ``code`` in a FRESH interpreter.

    A fresh process is the whole method: this test's own session has already
    imported the registry many times over, so an in-process check of
    ``sys.modules`` would read another test's imports and pass or fail for
    reasons unrelated to the CLI.
    """
    script = textwrap.dedent(code).replace(_LEAK_SCAN_MARKER, _LEAK_SCAN)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_rendering_the_command_tree_does_not_load_the_registry() -> None:
    """DISCRIMINATING: ``aeat --help`` and ``--version`` must stay registry-free.

    These are the surfaces an operator reaches before any profile exists, and
    the ones a shell completion or a packaging smoke test hits repeatedly.
    """
    completed = _run_python(
        f"""
        import sys
        import typer.main
        from click.testing import CliRunner
        from cadrumo.entrypoints.cli import app

        command = typer.main.get_command(app)
        runner = CliRunner()
        for args in (["--help"], ["--version"]):
            result = runner.invoke(command, args)
            # A crashed invocation would import nothing and pass vacuously.
            assert result.exit_code == 0, f"{{args}} exited {{result.exit_code}}: {{result.output}}"
            assert result.output.strip(), f"{{args}} produced no output"
        {_LEAK_SCAN_MARKER}
        print("\\n".join(leaked))
        print({_COMPLETED!r})
        """,
    )

    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert _COMPLETED in lines, f"the probe did not reach its assertion: {completed.stdout}{completed.stderr}"

    leaked = [line for line in lines if line != _COMPLETED]
    assert leaked == [], (
        "rendering the state-free CLI surfaces dragged the registry into sys.modules:\n  "
        + "\n  ".join(leaked)
        + "\nSomething on the command-tree path gained an eager import. The producer-side "
        "probe in application/user_profile/tests/test_lazy_boundary.py will still be green: "
        "it imports that boundary alone and cannot see an import added on the CLI path."
    )


def test_the_probe_detects_a_registry_import() -> None:
    """ANTI-TAUTOLOGY: the scan must be able to say yes.

    If the module names ever change -- a registry relocation, a package rename
    -- the scan above would find nothing and report a clean tree forever. This
    imports the registry deliberately and requires the same scan to see it.
    """
    completed = _run_python(
        f"""
        import sys
        import cadrumo.domain.calculations.registry  # noqa: F401
        {_LEAK_SCAN_MARKER}
        print("\\n".join(leaked))
        """,
    )

    assert completed.returncode == 0, completed.stderr
    leaked = [line for line in completed.stdout.splitlines() if line.strip()]
    assert leaked, "the scan cannot see a registry import; its module names have drifted"
