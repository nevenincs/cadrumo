"""A profile worker reaches readiness without importing the operation graph.

A person's sign-in starts a fresh profile worker. It once imported the whole
registered-operation composition, every handler and the pinned tax authority
before it could answer its parent -- about 3000 modules -- and then composed
the registry again before the sign-in reply. The worker now serves its
channels from the transport, its custody and the profile worker protocol; the
registry, its handlers and the authority load when an operation first needs
them.

This gate pins that PROPERTY: the module graph a worker holds once it can
serve. It deliberately asserts no wall-clock budget -- a timing threshold on a
contended machine is flaky and fails for reasons unrelated to the graph.
"""

from __future__ import annotations

import importlib
import json
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORKER_MODULE = "cadrumo.entrypoints.runtime.worker"

# Readiness: the entry module imports its whole service loop, and the loop's
# operation host and human login are constructed before the first request.
_READY = """
import {worker}
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost
from cadrumo.entrypoints.runtime.profile_login import ProfileWorkerHumanLogin
host = ProfileWorkerOperationHost(object(), authorization=object())
ProfileWorkerHumanLogin(object(), decode=host.profile_decode_context)
"""

_FORBIDDEN_AT_READY: tuple[str, ...] = (
    # The registered-operation composition and its supervisor.
    "cadrumo.entrypoints.operation_composition",
    "cadrumo.entrypoints.workbench_generation_composition",
    "cadrumo.entrypoints.runtime.operation_authority",
    "cadrumo.application.operations.composition",
    "cadrumo.application.operations.supervisor",
    # Operation definitions and the handlers behind them.
    "cadrumo.application.auth.operation_definitions",
    "cadrumo.application.workbench_generation_contracts",
    "cadrumo.application.overview.home",
    "cadrumo.application.ledger.invoice_draft_extraction_ports",
    "cadrumo.application.ledger.establishment_ladder",
    "cadrumo.application.filing.export_envelope",
    "cadrumo.application.local_reader_contracts",
    "cadrumo.application.provider_settings.resolution",
    "cadrumo.domain.provider_settings.catalog",
    # The pinned tax authority and its typed registry.
    "cadrumo.domain.calculations.registry.authority",
    "cadrumo.domain.calculations.registry.schema",
    "cadrumo.domain.calculations.registry.binding_provider",
    "cadrumo.domain.deadlines.models",
    "cadrumo.domain.modelos.filing_record",
    # Third-party stacks only operations use.
    "httpx",
    "sqlalchemy",
)

# The ready graph is about 680 modules where the eager worker held about 3000.
# The ceiling leaves room for small protocol growth and fails on a subtree.
_READY_MODULE_CEILING = 760


def _ready_modules(prelude: str = "") -> frozenset[str]:
    """Bring a worker to readiness in a fresh interpreter and report its module graph.

    A real isolated subprocess, because the runtime launches the worker that
    way and it is the only clean module table. ``prelude`` runs first so a
    caller can prove the gate still bites.
    """
    source = (
        f"{prelude}\n{_READY.format(worker=_WORKER_MODULE)}\nimport json, sys\nprint(json.dumps(sorted(sys.modules)))"
    )
    completed = run_audited_process(
        [sys.executable, "-I", "-B", "-c", source],
        capture_output=True,
        text=True,
        check=True,
    )
    names = json.loads(completed.stdout)
    assert isinstance(names, list), "the worker child must print a JSON list of module names"
    assert all(isinstance(name, str) for name in names), "module names must be strings"
    return frozenset(str(name) for name in names)


def test_a_ready_worker_excludes_the_operation_graph() -> None:
    """Readiness imports no registry, handler, authority or operation-only stack."""
    modules = _ready_modules()

    assert _WORKER_MODULE in modules, (
        f"the child did not import {_WORKER_MODULE}; the probe observed nothing, "
        "so the exclusions below would pass vacuously"
    )
    present = sorted(target for target in _FORBIDDEN_AT_READY if target in modules)
    assert present == [], (
        f"a ready profile worker imported {present}. Every sign-in starts this "
        "process, so an eager import on its path is paid by the person waiting. "
        "Import it inside the operation that uses it."
    )
    assert len(modules) <= _READY_MODULE_CEILING, (
        f"a ready profile worker holds {len(modules)} modules, above {_READY_MODULE_CEILING}; "
        "find the subtree that joined its startup path"
    )


@pytest.mark.parametrize(
    "prelude_target",
    ["cadrumo.entrypoints.operation_composition", "cadrumo.domain.calculations.registry.schema"],
)
def test_the_exclusion_probe_bites(prelude_target: str) -> None:
    """A heavy import re-added ahead of readiness is reported by both checks.

    The prelude stands in for a worker module that imports the target again,
    which is the regression this gate exists to catch.
    """
    modules = _ready_modules(prelude=f"import {prelude_target}")

    assert prelude_target in modules
    assert any(target in modules for target in _FORBIDDEN_AT_READY)
    assert len(modules) > _READY_MODULE_CEILING, "the ceiling no longer separates a ready worker from the eager graph"


def test_every_forbidden_target_still_resolves() -> None:
    """A renamed module is absent from every graph, which would retire its entry silently."""
    unresolvable: list[str] = []
    for target in _FORBIDDEN_AT_READY:
        try:
            importlib.import_module(target)
        except ImportError:
            unresolvable.append(target)

    assert not unresolvable, (
        f"these forbidden import targets no longer resolve: {unresolvable}. Re-point each "
        "at the module that now owns the subsystem, or drop it deliberately."
    )
