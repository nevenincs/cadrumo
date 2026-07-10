"""Static guard for production exception base classes.

User/application-facing AEAT exceptions must derive from
:class:`aeat.core.errors.AeatError` so they bind to the central error
registry. A tiny allowlist remains for private implementation sentinels
and structural mixin bases that are not raised directly.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest

from .... import __path__ as _aeat_package_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BARE_EXCEPTION_BASES = (Exception, ValueError, RuntimeError, KeyError, TypeError)
_ALLOWLIST = {
    "aeat.core.errors.AeatError": "central root of the registry-bound exception hierarchy",
    "aeat.application.live._snapshot_base.SnapshotNotFoundError": (
        "structural KeyError mixin; concrete snapshot errors also inherit AeatError"
    ),
    "aeat.adapters.outbound.aeat._playwright.PlaywrightError": (
        "optional-extra fallback alias for playwright.async_api.Error; it must match the third-party "
        "exception shape when Playwright is absent and is only caught/wrapped by adapter boundaries"
    ),
    "aeat.agent._skill_metadata.SkillMetadataError": (
        "agent-harness skill-frontmatter/applies_when validation error; intentionally a plain "
        "ValueError (a malformed-input signal at the harness boundary), not an operator-facing "
        "registry-bound filing/calculation error"
    ),
    "aeat.agent.eval._live_harness.LiveHarnessError": (
        "agent-harness live-eval scaffolding runtime error; intentionally a plain RuntimeError "
        "(a harness-boundary execution signal), not an operator-facing registry-bound filing error"
    ),
    "aeat.entrypoints.mcp._input_schema.SchemaResolutionError": (
        "MCP input-schema build-coverage error; intentionally a plain RuntimeError (a loud "
        "build-time signal that a command's CLI subtree failed to materialise, which would "
        "otherwise ship a silent argument-free schema), not an operator-facing registry-bound "
        "filing error"
    ),
    "aeat.application.auth._certificate_secret_backend.CertificateSecretBackendUnavailableError": (
        "certificate-secret backend boundary error; translated by the auth command/service layer, not raised as a "
        "registry-bound calculation or filing error"
    ),
    "aeat.application.auth._certificate_secret_backend.CertificateSecretNotFoundError": (
        "certificate-secret backend absence signal; callers collapse it to optional secret state"
    ),
    "aeat.application.auth._certificate_sources.CertificateSourceNoActiveBucketError": (
        "certificate-source mutation precondition signal for an uninitialised local profile bucket"
    ),
    "aeat.application.auth._certificate_sources.CertificateSourceNotFoundError": (
        "mapping-style certificate-source lookup miss; inherits KeyError so callers can preserve key semantics"
    ),
    "aeat.application.bucket_maintenance._sandbox.SandboxAlreadyExistsError": (
        "sandbox lifecycle application-service refusal; CLI boundary renders it as an operator action refusal"
    ),
    "aeat.application.bucket_maintenance._sandbox.SandboxDiscardRefusedError": (
        "sandbox destructive-action gate refusal; intentionally local to sandbox lifecycle orchestration"
    ),
    "aeat.application.bucket_maintenance._sandbox.SandboxMergeRefusedError": (
        "sandbox merge confirmation/scope refusal; intentionally local to sandbox lifecycle orchestration"
    ),
    "aeat.application.bucket_maintenance._sandbox.SandboxNotArchivedError": (
        "sandbox restore precondition refusal; intentionally local to sandbox lifecycle orchestration"
    ),
    "aeat.application.bucket_maintenance._sandbox.SandboxNotFoundError": (
        "sandbox bucket lookup miss; intentionally local to sandbox lifecycle orchestration"
    ),
    "aeat.application.bucket_maintenance._sandbox.SandboxSourceNotFoundError": (
        "sandbox seed-source lookup miss; intentionally local to sandbox lifecycle orchestration"
    ),
    "aeat.application.invoices._bulk_import._RowParseError": (
        "private row parser control-flow carrier; converted to BulkInvoiceImportRowFailure before leaving the module"
    ),
    "aeat.application.invoices._wizard._WizardFieldError": (
        "private wizard field-validation carrier; converted to InvoiceValidationError before leaving the module"
    ),
}


def _iter_imported_aeat_modules() -> list[ModuleType]:
    modules: list[ModuleType] = []
    for info in pkgutil.walk_packages(_aeat_package_path, prefix="aeat."):
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
    for module in _iter_imported_aeat_modules():
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
