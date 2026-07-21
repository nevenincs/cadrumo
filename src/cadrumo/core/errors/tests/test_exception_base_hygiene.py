"""Static guard for production exception base classes.

User/application-facing Cadrumo exceptions must derive from
:class:`cadrumo.core.errors.CadrumoError` so they bind to the central error
registry. A tiny allowlist remains for private implementation sentinels
and structural mixin bases that are not raised directly.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest

from .... import __path__ as _cadrumo_package_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BARE_EXCEPTION_BASES = (Exception, ValueError, RuntimeError, KeyError, TypeError)
_ALLOWLIST = {
    "cadrumo.core.errors.CadrumoError": "central root of the registry-bound exception hierarchy",
    "cadrumo.application.live._snapshot_base.SnapshotNotFoundError": (
        "structural KeyError mixin; concrete snapshot errors also inherit CadrumoError"
    ),
    "cadrumo.adapters.outbound.aeat._playwright.PlaywrightError": (
        "optional-extra fallback alias for playwright.async_api.Error; it must match the third-party "
        "exception shape when Playwright is absent and is only caught/wrapped by adapter boundaries"
    ),
    "cadrumo.agent._skill_metadata.SkillMetadataError": (
        "agent-harness skill-frontmatter/applies_when validation error; intentionally a plain "
        "ValueError (a malformed-input signal at the harness boundary), not an operator-facing "
        "registry-bound filing/calculation error"
    ),
    "cadrumo.agent.eval._live_harness.LiveHarnessError": (
        "agent-harness live-eval scaffolding runtime error; intentionally a plain RuntimeError "
        "(a harness-boundary execution signal), not an operator-facing registry-bound filing error"
    ),
    "cadrumo.entrypoints.mcp._input_schema.SchemaResolutionError": (
        "MCP input-schema build-coverage error; intentionally a plain RuntimeError (a loud "
        "build-time signal that a command's CLI subtree failed to materialise, which would "
        "otherwise ship a silent argument-free schema), not an operator-facing registry-bound "
        "filing error"
    ),
    "cadrumo.application.auth._certificate_sources.CertificateSourceNoActiveBucketError": (
        "certificate-source mutation precondition signal for an uninitialised local profile bucket"
    ),
    "cadrumo.application.auth._certificate_sources.CertificateSourceNotFoundError": (
        "mapping-style certificate-source lookup miss; inherits KeyError so callers can preserve key semantics"
    ),
    "cadrumo.application.bucket_maintenance._sandbox.SandboxAlreadyExistsError": (
        "sandbox lifecycle application-service refusal; CLI boundary renders it as an operator action refusal"
    ),
    "cadrumo.application.bucket_maintenance._sandbox.SandboxDiscardRefusedError": (
        "sandbox destructive-action gate refusal; intentionally local to sandbox lifecycle orchestration"
    ),
    "cadrumo.application.bucket_maintenance._sandbox.SandboxMergeRefusedError": (
        "sandbox merge confirmation/scope refusal; intentionally local to sandbox lifecycle orchestration"
    ),
    "cadrumo.application.bucket_maintenance._sandbox.SandboxNotArchivedError": (
        "sandbox restore precondition refusal; intentionally local to sandbox lifecycle orchestration"
    ),
    "cadrumo.application.bucket_maintenance._sandbox.SandboxNotFoundError": (
        "sandbox bucket lookup miss; intentionally local to sandbox lifecycle orchestration"
    ),
    "cadrumo.application.bucket_maintenance._sandbox.SandboxSourceNotFoundError": (
        "sandbox seed-source lookup miss; intentionally local to sandbox lifecycle orchestration"
    ),
    "cadrumo.application.invoices._bulk_import._RowParseError": (
        "private row parser control-flow carrier; converted to BulkInvoiceImportRowFailure before leaving the module"
    ),
    "cadrumo.application.invoices._wizard._WizardFieldError": (
        "private wizard field-validation carrier; converted to InvoiceValidationError before leaving the module"
    ),
    "cadrumo.core._config_state_root.FormerProductStateError": (
        "raised from inside Settings/pydantic validation during bootstrap, before the CadrumoError "
        "registry can be relied upon; the CLI boundary explicitly catches it ahead of the CadrumoError "
        "arm and translates it into a registered CliRefusedBoundaryError"
    ),
}


def _iter_imported_cadrumo_modules() -> list[ModuleType]:
    modules: list[ModuleType] = []
    for info in pkgutil.walk_packages(_cadrumo_package_path, prefix="cadrumo."):
        name = info.name
        if ".tests." in name or ".test_" in name or "._test_" in name:
            continue
        modules.append(importlib.import_module(name))
    return modules


def _module_exception_classes(module: ModuleType) -> list[type[BaseException]]:
    module_name = module.__name__
    return [
        error_type
        for _, error_type in inspect.getmembers(module, inspect.isclass)
        if error_type.__module__ == module_name and issubclass(error_type, BaseException)
    ]


def test_production_exception_classes_do_not_introduce_unregistered_builtin_roots() -> None:
    violations: list[str] = []
    for module in _iter_imported_cadrumo_modules():
        for error_type in _module_exception_classes(module):
            qualname = f"{error_type.__module__}.{error_type.__qualname__}"
            if qualname in _ALLOWLIST:
                continue
            bare_bases = tuple(base.__name__ for base in error_type.__bases__ if base in _BARE_EXCEPTION_BASES)
            if bare_bases and len(bare_bases) == len(error_type.__bases__):
                violations.append(
                    f"{error_type.__module__}.{error_type.__qualname__}({', '.join(sorted(bare_bases))})",
                )

    assert violations == []


def test_exception_base_hygiene_allowlist_carries_review_rationales() -> None:
    assert all(reason.strip() for reason in _ALLOWLIST.values())
