"""Import smoke for canonical layout buckets and named subpackages.

Walks the declared ``CANONICAL_LAYOUT_PACKAGES`` tuple and asserts
each one is importable. Catches accidental cross-bucket imports
that break the public-package surface (a misplaced relative import,
a deleted ``__init__.py``, or a renamed module breaking a symbol
export). Pairs with ``CANONICAL_PUBLIC_SYMBOLS`` which pins the
shape of the public re-exports the wider codebase consumes.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

SRC_CADRUMO = Path(__file__).resolve().parents[1]


CANONICAL_LAYOUT_PACKAGES: tuple[str, ...] = (
    "cadrumo.domain",
    "cadrumo.domain.modelos",
    "cadrumo.domain.manuals",
    "cadrumo.domain.portals",
    "cadrumo.domain.deadlines",
    "cadrumo.domain.contribuyente",
    "cadrumo.domain.fincas",
    "cadrumo.domain.filing",
    "cadrumo.domain.filing.reconciliation",
    "cadrumo.domain.justificante",
    "cadrumo.domain.submission",
    "cadrumo.domain.transactions",
    "cadrumo.domain.invoices",
    "cadrumo.domain.attachments",
    "cadrumo.domain.usage_ratios",
    "cadrumo.domain.categories",
    "cadrumo.domain.iva",
    "cadrumo.adapters",
    "cadrumo.adapters.inbound",
    "cadrumo.adapters.inbound.pdf",
    "cadrumo.adapters.inbound.borrador",
    "cadrumo.adapters.inbound.declaracion",
    "cadrumo.adapters.inbound.justificante",
    "cadrumo.adapters.inbound.financial",
    "cadrumo.adapters.inbound.financial.providers",
    "cadrumo.adapters.outbound",
    "cadrumo.adapters.outbound.aeat",
    "cadrumo.adapters.outbound.aeat.auth",
    "cadrumo.adapters.outbound.aeat.browser",
    "cadrumo.adapters.outbound.aeat.sede",
    "cadrumo.adapters.outbound.aeat.verify",
    "cadrumo.adapters.outbound.aeat.export",
    "cadrumo.adapters.outbound.google",
    "cadrumo.adapters.outbound.storage",
    "cadrumo.adapters.outbound.llm",
    "cadrumo.adapters.persistence",
    "cadrumo.adapters.persistence.storage",
    "cadrumo.application",
    "cadrumo.application.filing",
    "cadrumo.application.transactions",
    "cadrumo.application.invoices",
    "cadrumo.application.aggregation",
    "cadrumo.application.workflow",
    "cadrumo.application.review",
    "cadrumo.application.auth",
    "cadrumo.entrypoints",
    "cadrumo.entrypoints.cli",
    "cadrumo.core",
    "cadrumo.core.errors",
    "cadrumo.core.i18n",
    "cadrumo.core.access_gate",
    "cadrumo.core.file_permissions",
    "cadrumo.core.locks",
    "cadrumo.core.classification",
    "cadrumo.core.redaction",
    "cadrumo.core.corpus_manifest",
    "cadrumo.core.observability",
    "cadrumo.core.identity",
)

CANONICAL_PUBLIC_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("cadrumo.core.errors", "CadrumoError"),
    ("cadrumo.core.access_gate", "LiveSubmitForbiddenError"),
    ("cadrumo.adapters.outbound.aeat.auth", "AeatAuthenticator"),
    ("cadrumo.adapters.outbound.google", "OAuthClient"),
    ("cadrumo.adapters.outbound.google", "GoogleAuthError"),
    ("cadrumo.adapters.outbound.storage", "StorageProvider"),
    ("cadrumo.adapters.outbound.storage", "OutboundStorageError"),
    ("cadrumo.adapters.outbound.storage", "get_storage_provider"),
    ("cadrumo.application.auth", "select_provider"),
)

REQUIRED_RELOCATED_PATHS: tuple[str, ...] = (
    "application/auth/__init__.py",
    "adapters/inbound/justificante/parser.py",
    "adapters/inbound/justificante/_extract.py",
)


@pytest.mark.parametrize("module_name", CANONICAL_LAYOUT_PACKAGES)
def test_canonical_layout_package_import_smoke(module_name: str) -> None:
    """Every canonical layout import surface must be importable."""
    importlib.import_module(module_name)


@pytest.mark.parametrize(("module_name", "symbol_name"), CANONICAL_PUBLIC_SYMBOLS)
def test_canonical_public_symbols_are_exposed(module_name: str, symbol_name: str) -> None:
    """Representative public symbols remain available at canonical paths."""
    module = importlib.import_module(module_name)

    assert hasattr(module, symbol_name), f"{module_name} must expose {symbol_name}"


@pytest.mark.parametrize("relative_path", REQUIRED_RELOCATED_PATHS)
def test_relocated_surfaces_exist_at_canonical_paths(relative_path: str) -> None:
    """Moved implementation surfaces must exist at their canonical destinations."""
    assert (SRC_CADRUMO / relative_path).exists(), relative_path


def test_legacy_normatives_package_is_absent() -> None:
    """The retired JSON normative catalogue package must not be importable."""
    assert importlib.util.find_spec("cadrumo.domain.normatives") is None


def test_domain_justificante_does_not_export_parser_pipeline() -> None:
    module = importlib.import_module("cadrumo.domain.justificante")

    assert not hasattr(module, "parse_justificante")


@pytest.mark.parametrize(
    "symbol_name",
    [
        "ADC_LOGIN_SCOPE_CSV",
        "GoogleAuthPath",
        "build_drive_service",
        "get_credentials_for_scopes",
        "inspect_google_auth",
    ],
)
def test_aeat_auth_does_not_export_google_auth_pipeline(symbol_name: str) -> None:
    module = importlib.import_module("cadrumo.adapters.outbound.aeat.auth")

    assert not hasattr(module, symbol_name), symbol_name
