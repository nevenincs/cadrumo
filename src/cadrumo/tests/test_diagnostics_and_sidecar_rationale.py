"""Wizard locale routing, parser alias shape, and sidecar Mapping return.

Covers:
  (a) wizard next tab-label locale keys exist
  (b) _parser.py _PdfWord remains the expected adapter-internal alias
  (c) _local.py sidecar manifest read returns Mapping[str, object]

See Also:
    :func:`~core.i18n.tr`
        Locale lookup surface used to verify the wizard output-label key.
    :mod:`~adapters.inbound.declaracion._parser`
        Adapter parser module that intentionally owns the ``_PdfWord`` alias.
    :class:`~adapters.outbound.storage._local.LocalFileSystemProvider`
        Local storage provider whose sidecar loader keeps the Mapping return
        contract.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from ..adapters.inbound.declaracion import _parser
from ..adapters.outbound.storage._local import LocalFileSystemProvider
from ..core.i18n import tr

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_application,
]

# ---------------------------------------------------------------------------
# (a) wizard next tab-label locale keys exist
# ---------------------------------------------------------------------------

_NEXT_LOCALE_KEY = "application.wizard.output_labels.next"


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_wizard_next_locale_key_resolves(locale: str) -> None:
    """application.wizard.output_labels.next exists in every shipped locale."""
    result = tr(_NEXT_LOCALE_KEY, locale=locale)
    assert result and result != _NEXT_LOCALE_KEY, (
        f"{locale} locale key application.wizard.output_labels.next is missing or falls back to key"
    )


# ---------------------------------------------------------------------------
# (b) _parser.py _PdfWord adapter-internal alias shape
# ---------------------------------------------------------------------------


def test_pdfword_alias_is_dict_str_any() -> None:
    """_PdfWord remains dict[str, Any] — adapter-internal, not moved to core._types."""
    assert _parser._PdfWord == dict[str, Any]


# ---------------------------------------------------------------------------
# (c) _local.py sidecar read returns Mapping[str, object]
# ---------------------------------------------------------------------------


def test_local_sidecar_return_type_is_mapping() -> None:
    """_load_sidecar return annotation is Mapping[str, object], not plain dict."""
    hints = LocalFileSystemProvider._load_sidecar.__annotations__
    return_hint = hints.get("return")
    hint_str = str(return_hint)
    assert "Mapping" in hint_str, f"_load_sidecar return annotation should be Mapping[str, object], got {hint_str!r}"


def test_local_sidecar_runtime_returns_mapping() -> None:
    """_load_sidecar actually returns a Mapping at runtime given a well-formed file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sidecar = Path(tmpdir) / "test.meta.json"
        payload: dict[str, object] = {"content_hash": "abc123", "byte_length": 42}
        sidecar.write_text(json.dumps(payload), encoding="utf-8")

        provider = LocalFileSystemProvider(root=Path(tmpdir))
        result = provider._load_sidecar(sidecar)

        assert isinstance(result, Mapping)
        assert result["content_hash"] == "abc123"
        assert result["byte_length"] == 42
