"""A sign-in reads the profile without importing the typed tax registry.

Proving a password decodes the person's encrypted profile, and decoding needs
only the published generation pin and the profile schema. The worker once
reached both through the authority module, which imported the modelo schema,
binding providers, governed facts, temporal selection and their catalogues --
about 200 modules and more than a second of a person's wait -- before the
first profile byte was read. Those now load when an operation evaluates them.

This gate pins that PROPERTY: the module graph a worker holds once it has
decoded the profile or signed the person in. Like the worker startup gate
beside it, it asserts no wall-clock budget.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.hex_entrypoint]

_WORKER_MODULE = "cadrumo.entrypoints.runtime.worker"
_AUTHORITY_MODULE = "cadrumo.domain.calculations.registry.authority"

# A ready worker's host leases the published authority and decodes the
# profile schema, exactly as the human login asks it to before a candidate.
_DECODED = """
import {worker}
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost
host = ProfileWorkerOperationHost(object(), authorization=object())
context = host.profile_decode_context()
assert context.schema.id == "cadrumo.user_profile", context.schema.id
"""

# A real sign-in in a fresh worker interpreter: the installed composition, the
# worker's own custody and host, and the person's password proof.
_SIGNED_IN = """
import sys
from pathlib import Path
import {worker} as worker
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost
from cadrumo.entrypoints.runtime.profile_login import ProfileWorkerHumanLogin
root = Path(sys.argv[1])
identity = ProfileWorkerIdentity.model_validate_json(Path(sys.argv[2]).read_text(encoding="utf-8"))
with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(identity.binding.profile_id)):
    with worker.installed_profile_worker_composition():
        custody = ProfileWorkerCustody(identity, storage_root=root)
        host = ProfileWorkerOperationHost(custody, authorization=object())
        human = ProfileWorkerHumanLogin(custody, decode=host.profile_decode_context)
        try:
            human.authenticate(bytearray(sys.stdin.read().encode()))
        finally:
            human.close()
            custody.close()
"""

_FORBIDDEN_AFTER_SIGN_IN: tuple[str, ...] = (
    # The typed modelo registry and its validation.
    "cadrumo.domain.calculations.registry.schema",
    "cadrumo.domain.calculations.registry.snapshot",
    "cadrumo.domain.calculations.registry.static_inspection",
    "cadrumo.domain.calculations.registry.temporal",
    "cadrumo.domain.calculations.registry.schema_exports",
    # Bindings, applicability and formula evaluation.
    "cadrumo.domain.calculations.registry.binding_provider",
    "cadrumo.domain.calculations.registry.applicability",
    "cadrumo.domain.calculations.registry.formula_runtime",
    # Governed facts and the catalogues built from them.
    "cadrumo.domain.calculations.registry.facts.resolution",
    "cadrumo.domain.calculations.registry.governed_fact_scope",
    "cadrumo.domain.calculations.registry.identifier_evolutions",
    "cadrumo.domain.calculations.registry.renta_codes_catalogue",
    "cadrumo.domain.contribuyente.renta_codes",
    "cadrumo.domain.deadlines.models",
    "cadrumo.domain.iva.classification",
)


def _modules_after(source: str, *arguments: str, stdin: str | None = None, prelude: str = "") -> frozenset[str]:
    """Run ``source`` in a fresh isolated interpreter and report its module graph.

    A real subprocess, because the runtime launches the worker that way and it
    is the only clean module table. ``prelude`` runs first so a caller can
    prove the gate still bites.
    """
    program = (
        f"{prelude}\n{source.format(worker=_WORKER_MODULE)}\nimport json, sys\nprint(json.dumps(sorted(sys.modules)))"
    )
    completed = run_audited_process(
        [sys.executable, "-I", "-B", "-c", program, *arguments],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    )
    names = json.loads(completed.stdout.strip().splitlines()[-1])
    assert isinstance(names, list), "the worker child must print a JSON list of module names"
    assert all(isinstance(name, str) for name in names), "module names must be strings"
    return frozenset(str(name) for name in names)


def _assert_excludes_the_typed_registry(modules: frozenset[str], *, stage: str) -> None:
    assert _AUTHORITY_MODULE in modules, (
        f"the child never reached {_AUTHORITY_MODULE}; the probe observed no {stage}, "
        "so the exclusions below would pass vacuously"
    )
    present = sorted(target for target in _FORBIDDEN_AFTER_SIGN_IN if target in modules)
    assert present == [], (
        f"a worker that completed a {stage} imported {present}. Every sign-in pays for "
        "this import while the person waits. Import it inside the code that evaluates it."
    )


@pytest.mark.unit
def test_a_profile_decode_excludes_the_typed_registry() -> None:
    """Leasing the authority and decoding the profile schema loads no registry machinery."""
    _assert_excludes_the_typed_registry(_modules_after(_DECODED), stage="profile decode")


@pytest.mark.unit
@pytest.mark.parametrize(
    "prelude_target",
    ["cadrumo.domain.calculations.registry.schema", "cadrumo.domain.calculations.registry.binding_provider"],
)
def test_the_exclusion_probe_bites(prelude_target: str) -> None:
    """A registry import re-added on the decode path is reported.

    The prelude stands in for an authority or codec module that imports the
    target again at module level, the regression this gate exists to catch.
    """
    modules = _modules_after(_DECODED, prelude=f"import {prelude_target}")

    assert prelude_target in modules
    with pytest.raises(AssertionError, match="Import it inside the code that evaluates it"):
        _assert_excludes_the_typed_registry(modules, stage="profile decode")


@pytest.mark.unit
def test_every_forbidden_target_still_resolves() -> None:
    """A renamed module is absent from every graph, which would retire its entry silently."""
    unresolvable: list[str] = []
    for target in _FORBIDDEN_AFTER_SIGN_IN:
        try:
            importlib.import_module(target)
        except ImportError:
            unresolvable.append(target)

    assert not unresolvable, (
        f"these forbidden import targets no longer resolve: {unresolvable}. Re-point each "
        "at the module that now owns the subsystem, or drop it deliberately."
    )


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows profile custody")
def test_a_real_sign_in_excludes_the_typed_registry(tmp_path: Path) -> None:
    """A password sign-in in a fresh worker interpreter reads the profile without the registry."""
    from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, worker_profiles
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

    with profile_adapter_composition(), worker_profiles(tmp_path) as (root, ((identity, _), _)):
        identity_path = tmp_path / "identity.json"
        identity_path.write_text(identity.model_dump_json(), encoding="utf-8")
        modules = _modules_after(_SIGNED_IN, str(root), str(identity_path), stdin=PROFILE_INPUT)

    _assert_excludes_the_typed_registry(modules, stage="password sign-in")
