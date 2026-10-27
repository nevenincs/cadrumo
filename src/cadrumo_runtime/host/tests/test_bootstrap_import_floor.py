"""The runtime process bootstrap defers application imports to isolated dispatch."""

from __future__ import annotations

import pytest

from cadrumo.tests.entry_import_floor_support import denied_imports, imported_modules, unlisted_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_runtime_process_bootstrap_import_loads_only_its_shell() -> None:
    module = "cadrumo_runtime.host.bootstrap"
    names = imported_modules(module)

    assert denied_imports(names) == [], (
        f"importing {module} loaded subtrees that belong to isolated first use. Find the eager import "
        "with `python -X importtime -c 'import <module>'` and move it behind isolated dispatch."
    )
    assert unlisted_modules(names, frozenset()) == [], (
        f"importing {module} gained lower tax modules outside its launch shell. Defer the import "
        "until after the bootstrap has entered isolated dispatch."
    )


def test_runtime_server_import_excludes_mutation_services() -> None:
    """Serving login and status must not compose provider edits or capsule deletion."""
    names = imported_modules("cadrumo_runtime.host.main")
    mutation_services = {
        "cadrumo.application.auth.operator",
        "cadrumo.application.user_profile.fact_write",
        "cadrumo.application.user_profile.lifecycle",
        "sqlalchemy",
    }

    assert mutation_services.isdisjoint(names), sorted(mutation_services.intersection(names))
