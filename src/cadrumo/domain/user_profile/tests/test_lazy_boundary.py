"""Producer-side lazy-import boundary probe for ``aeat.domain.user_profile``.

The CLI-side gate at
:mod:`aeat.entrypoints.cli.test_lazy_command_tree` enforces that the
state-free CLI surfaces do not transitively load the calculation
registry. The application-side mirror at
:mod:`aeat.application.user_profile.test_lazy_boundary` pins the same
contract one layer up. This module pins it at the *domain*-package
boundary: importing :mod:`aeat.domain.user_profile` alone, in a fresh
interpreter, MUST NOT place any ``aeat.domain.calculations.registry*``
module in ``sys.modules``.

The domain package's only registry-coupled re-export is
:class:`UserProfilePortableExport`, which composes four heavy domain
records (calculation revision, work unit, transaction, modelo record)
whose transitive imports cascade into the registry. The boundary
resolves the symbol through PEP 562 ``__getattr__`` so the cost is
paid only at first reference, never at module import. A regression
that re-introduces an eager re-export of the portable-export bundle
(or of any future registry-coupled symbol) reds here before it reds
the CLI-level gate, so the diagnosis points at the boundary rather
than at one of its downstream consumers.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_importing_domain_user_profile_does_not_load_registry() -> None:
    """``import aeat.domain.user_profile`` must not pull the registry.

    The domain package re-exports :class:`UserProfilePortableExport`
    whose field types pull the calculation registry through
    ``aeat.domain.modelos._calculation_revision``. Re-exporting it
    eagerly drags the full ~69-submodule registry into every consumer
    that touches the boundary, including the state-free CLI surfaces.
    The boundary MUST therefore route the portable-export symbol
    (and any future registry-coupled symbol) through PEP 562
    ``__getattr__``.
    """

    completed = _run_python(
        """
        import sys
        import aeat.domain.user_profile  # noqa: F401

        leaked = sorted(
            name
            for name in sys.modules
            if name == "aeat.domain.calculations.registry"
            or name.startswith("aeat.domain.calculations.registry.")
        )
        print("\\n".join(leaked))
        """,
    )

    assert completed.returncode == 0, completed.stderr
    leaked = [line for line in completed.stdout.splitlines() if line.strip()]
    assert leaked == [], f"import aeat.domain.user_profile leaked registry submodules into sys.modules: {leaked}"


def test_portable_export_resolves_on_demand_via_getattr() -> None:
    """First access to ``UserProfilePortableExport`` triggers the lazy import.

    The boundary's lazy dispatch is structural: the symbol is in the
    package's ``__all__`` and resolves through ``__getattr__``. This
    test guarantees the on-demand resolution path is wired (the symbol
    is reachable) without altering the producer-side probe above, which
    must continue to assert zero registry leak on bare import.
    """

    completed = _run_python(
        """
        import sys
        import aeat.domain.user_profile as pkg

        before = sum(
            1 for n in sys.modules
            if n == "aeat.domain.calculations.registry"
            or n.startswith("aeat.domain.calculations.registry.")
        )
        cls = pkg.UserProfilePortableExport
        after = sum(
            1 for n in sys.modules
            if n == "aeat.domain.calculations.registry"
            or n.startswith("aeat.domain.calculations.registry.")
        )
        print(cls.__name__, before, after)
        """,
    )

    assert completed.returncode == 0, completed.stderr
    name, before_s, after_s = completed.stdout.strip().split()
    assert name == "UserProfilePortableExport"
    assert int(before_s) == 0
    assert int(after_s) > 0, "first attribute access did not trigger the lazy import"
