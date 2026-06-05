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
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

SRC_AEAT = Path(__file__).resolve().parents[1]


CANONICAL_LAYOUT_PACKAGES: tuple[str, ...] = (
    "aeat.domain",
    "aeat.domain.modelos",
    "aeat.domain.manuals",
    "aeat.domain.normatives",
    "aeat.domain.portals",
    "aeat.domain.deadlines",
    "aeat.domain.contribuyente",
    "aeat.domain.fincas",
    "aeat.domain.filing",
    "aeat.domain.filing.reconciliation",
    "aeat.domain.justificante",
    "aeat.domain.submission",
    "aeat.domain.transactions",
    "aeat.domain.invoices",
    "aeat.domain.attachments",
    "aeat.domain.usage_ratios",
    "aeat.domain.categories",
    "aeat.domain.iva",
    "aeat.adapters",
    "aeat.adapters.inbound",
    "aeat.adapters.inbound.pdf",
    "aeat.adapters.inbound.borrador",
    "aeat.adapters.inbound.declaracion",
    "aeat.adapters.inbound.justificante",
    "aeat.adapters.inbound.sanitizer",
    "aeat.adapters.inbound.financial",
    "aeat.adapters.inbound.financial.providers",
    "aeat.adapters.outbound",
    "aeat.adapters.outbound.aeat",
    "aeat.adapters.outbound.aeat.auth",
    "aeat.adapters.outbound.aeat.browser",
    "aeat.adapters.outbound.aeat.sede",
    "aeat.adapters.outbound.aeat.verify",
    "aeat.adapters.outbound.aeat.export",
    "aeat.adapters.outbound.google",
    "aeat.adapters.outbound.storage",
    "aeat.adapters.outbound.llm",
    "aeat.adapters.persistence",
    "aeat.adapters.persistence.storage",
    "aeat.application",
    "aeat.application.filing",
    "aeat.application.transactions",
    "aeat.application.invoices",
    "aeat.application.aggregation",
    "aeat.application.workflow",
    "aeat.application.setup",
    "aeat.application.review",
    "aeat.application.verification",
    "aeat.application.auth",
    "aeat.entrypoints",
    "aeat.entrypoints.cli",
    "aeat.core",
    "aeat.core.errors",
    "aeat.core.i18n",
    "aeat.core.access_gate",
    "aeat.core.file_permissions",
    "aeat.core.locks",
    "aeat.core.classification",
    "aeat.core.redaction",
    "aeat.core.corpus_manifest",
    "aeat.core.observability",
    "aeat.core.identity",
)

CANONICAL_PUBLIC_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("aeat.core.errors", "AeatError"),
    ("aeat.core.access_gate", "LiveSubmitForbiddenError"),
    ("aeat.adapters.outbound.aeat.auth", "AeatAuthenticator"),
    ("aeat.adapters.outbound.google", "OAuthClient"),
    ("aeat.adapters.outbound.google", "GoogleAuthError"),
    ("aeat.adapters.outbound.storage", "StorageProvider"),
    ("aeat.adapters.outbound.storage", "OutboundStorageError"),
    ("aeat.adapters.outbound.storage", "get_storage_provider"),
    ("aeat.application.auth", "select_provider"),
)

REQUIRED_RELOCATED_PATHS: tuple[str, ...] = (
    "application/auth/__init__.py",
    "application/filing/testing.py",
    "adapters/inbound/justificante/_parser.py",
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
    assert (SRC_AEAT / relative_path).exists()


def test_domain_justificante_does_not_export_parser_pipeline() -> None:
    module = importlib.import_module("aeat.domain.justificante")

    assert not hasattr(module, "parse_justificante")


def test_aeat_auth_does_not_export_google_auth_pipeline() -> None:
    module = importlib.import_module("aeat.adapters.outbound.aeat.auth")

    for symbol_name in (
        "ADC_LOGIN_SCOPE_CSV",
        "GoogleAuthPath",
        "build_drive_service",
        "get_credentials_for_scopes",
        "inspect_google_auth",
    ):
        assert not hasattr(module, symbol_name), symbol_name
