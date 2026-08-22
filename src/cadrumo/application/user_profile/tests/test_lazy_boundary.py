"""Producer-side lazy-import boundary probe for ``cadrumo.application.user_profile``.

The CLI-side gate at
:mod:`cadrumo.entrypoints.cli.tests.test_lazy_command_tree` enforces that the
state-free CLI surfaces do not transitively load the registry. This
module pins the same contract at the *producer* boundary: importing
:mod:`cadrumo.application.user_profile` alone, in a fresh interpreter,
MUST NOT place any ``cadrumo.domain.calculations.registry*`` module in
``sys.modules``. A regression that re-introduces an eager
domain-record import at the package boundary reds here before it reds
the CLI-level gate, so the diagnosis points at the boundary rather
than at one of its downstream consumers.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_importing_application_user_profile_does_not_load_registry() -> None:
    """``import cadrumo.application.user_profile`` must not pull the registry.

    The application-layer boundary aggregates Pydantic command and
    result records whose field types are domain records. Those domain
    records pull the registry eagerly through their
    ``_registry_contract`` companion. A boundary that imports them at
    module-init time drags the full ~69-submodule registry into every
    consumer that touches the boundary, including the state-free CLI
    surfaces. The boundary MUST therefore lazy-resolve every
    registry-coupled name through PEP 562 ``__getattr__``.
    """

    completed = _run_python(
        """
        import sys
        import cadrumo.application.user_profile  # noqa: F401

        leaked = sorted(
            name
            for name in sys.modules
            if name == "cadrumo.domain.calculations.registry"
            or name.startswith("cadrumo.domain.calculations.registry.")
        )
        print("\\n".join(leaked))
        """,
    )

    assert completed.returncode == 0, completed.stderr
    leaked = [line for line in completed.stdout.splitlines() if line.strip()]
    assert leaked == [], (
        f"import cadrumo.application.user_profile leaked registry submodules into sys.modules: {leaked}"
    )
