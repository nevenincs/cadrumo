"""Shared vocabulary for the command-group lazy-import guards.

The loader's import-failure classification is covered from two lanes that must
agree on the same incident: ``test_command_group_import_classification``
exercises the pure in-process classifier, and
``test_command_group_import_failure_surface`` drives the rendered operator
surface end to end. Both name the same blocked package, the same affected
group, and the same registered error code, so those three constants live here
rather than being restated per module where they could silently drift apart.

The subprocess runner lives here for the same reason: it encodes the one way
this project makes a package genuinely unimportable before
:mod:`cadrumo.entrypoints.cli` is first imported.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

#: A required ``[project]`` dependency that the ``app modelo`` subtree imports
#: transitively. This is the exact package whose absence produced the silent
#: degradation the guarded modules describe.
REQUIRED_DEPENDENCY = "textual"

#: The command group whose subtree imports :data:`REQUIRED_DEPENDENCY`.
AFFECTED_GROUP = "modelo"

#: The registered error code a required-dependency refusal must carry.
EXPECTED_ERROR_CODE = "FAIL_CLI_COMMAND_GROUP_UNAVAILABLE"


def run_cli_with_blocked_package(
    package: str,
    argv: list[str],
    *,
    language: str = "en",
) -> subprocess.CompletedProcess[str]:
    """Run the real ``aeat`` entry point with ``package`` made unimportable.

    The meta-path finder is installed before :mod:`cadrumo.entrypoints.cli` is
    imported, so the blocked package is absent for the whole run — the same
    state an incomplete install presents. It raises rather than returning
    ``None`` so a deep ``from package import name`` fails identically to a
    genuinely absent distribution.

    A subprocess is required because the blocked package must be unimportable
    *before* the command module is first imported, and the in-process test
    session has already imported it.
    """
    code = textwrap.dedent(
        f"""
        import os, sys
        os.environ["CADRUMO_OUTPUT_LANGUAGE"] = {language!r}

        class _Blocked:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == {package!r}:
                    raise ModuleNotFoundError(f"No module named {{fullname!r}}", name=fullname)
                return None

        sys.meta_path.insert(0, _Blocked())
        sys.argv = ["aeat", *{argv!r}]
        from cadrumo.entrypoints.cli import main
        main()
        """,
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        # The CLI forces UTF-8 stdio; the default locale decoder is cp1252 on
        # Windows and chokes on an accented refusal from the child process.
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
