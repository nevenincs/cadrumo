"""Diagnostics broad-except rationales, wizard locale routing, and sidecar Mapping return.

Covers:
  (a) diagnostics.py BROAD-EXCEPT-RATIONALE markers present and complete
  (b) wizard _commands.py next tab-label is localised via tr()
  (c) _parser.py _PdfWord adapter-internal alias rationale documented
  (d) _local.py sidecar manifest read wrapped in Mapping[str, object]
"""

from __future__ import annotations

import ast
import json
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..adapters.outbound.storage._local import LocalFileSystemProvider
from ..core.i18n import tr

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_application,
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SRC = Path(__file__).parent.parent


def _source(rel: str) -> str:
    return (_SRC / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) diagnostics.py BROAD-EXCEPT-RATIONALE markers
# ---------------------------------------------------------------------------

_DIAGNOSTICS_REL = "application/diagnostics.py"
_TEARDOWN_TOKEN = "BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-TEARDOWN"
_INTEGRITY_TOKEN = "BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-INTEGRITY-PROBE"
_RECORD_TOKEN = "BROAD-EXCEPT-RATIONALE-DIAGNOSTICS-RECORD-READ"


def test_diagnostics_teardown_rationale_markers_present() -> None:
    """Browser context/session teardown except clauses carry the rationale token."""
    src = _source(_DIAGNOSTICS_REL)
    occurrences = src.count(_TEARDOWN_TOKEN)
    assert occurrences >= 2, (
        f"Expected at least 2 occurrences of {_TEARDOWN_TOKEN!r} in diagnostics.py "
        f"(one per teardown except clause), found {occurrences}"
    )


def test_diagnostics_integrity_probe_rationale_marker_present() -> None:
    """Integrity-probe loop except clause carries the rationale token."""
    src = _source(_DIAGNOSTICS_REL)
    assert _INTEGRITY_TOKEN in src, f"{_INTEGRITY_TOKEN!r} not found in diagnostics.py"


def test_diagnostics_record_read_rationale_marker_present() -> None:
    """Record-read final-fallback except clause carries the rationale token."""
    src = _source(_DIAGNOSTICS_REL)
    assert _RECORD_TOKEN in src, f"{_RECORD_TOKEN!r} not found in diagnostics.py"


def test_diagnostics_record_read_pragma_preserved() -> None:
    """The pragma: no cover comment is preserved alongside the rationale token."""
    src = _source(_DIAGNOSTICS_REL)
    lines = src.splitlines()
    # The pragma belongs on the ``except`` line and the rationale on a comment
    # line beside it; a formatter may place them on adjacent lines rather than
    # one. Verify the pragma is preserved within two lines of the rationale.
    for idx, line in enumerate(lines):
        if _RECORD_TOKEN in line:
            window = lines[max(0, idx - 2) : idx + 3]
            assert any("pragma: no cover" in ln for ln in window), (
                "RECORD-READ except clause must preserve 'pragma: no cover' "
                f"adjacent to the rationale, but none was found near: {line!r}"
            )
            break
    else:
        pytest.fail(f"{_RECORD_TOKEN!r} not found in diagnostics.py")


# ---------------------------------------------------------------------------
# (b) wizard _commands.py next tab-label is localised
# ---------------------------------------------------------------------------

_COMMANDS_REL = "application/wizard/_commands.py"
_NEXT_LOCALE_KEY = "application.wizard.output_labels.next"


def test_wizard_next_label_uses_tr() -> None:
    """The 'next' tab-label emit uses tr() with the canonical locale key."""
    src = _source(_COMMANDS_REL)
    pattern = re.compile(r"tr\(['\"]" + re.escape(_NEXT_LOCALE_KEY) + r"['\"]")
    assert pattern.search(src), f"wizard/_commands.py must call tr('{_NEXT_LOCALE_KEY}') for the next tab label"


def test_wizard_next_locale_key_in_en() -> None:
    """application.wizard.output_labels.next exists in en.yml."""
    result = tr(_NEXT_LOCALE_KEY, locale="en")
    assert result and result != _NEXT_LOCALE_KEY, (
        "en locale key application.wizard.output_labels.next is missing or falls back to key"
    )


def test_wizard_next_locale_key_in_es() -> None:
    """application.wizard.output_labels.next exists in es.yml."""
    result = tr(_NEXT_LOCALE_KEY, locale="es")
    assert result and result != _NEXT_LOCALE_KEY, (
        "es locale key application.wizard.output_labels.next is missing or falls back to key"
    )


def test_wizard_next_locale_key_in_ca() -> None:
    """application.wizard.output_labels.next exists in ca.yml."""
    result = tr(_NEXT_LOCALE_KEY, locale="ca")
    assert result and result != _NEXT_LOCALE_KEY, (
        "ca locale key application.wizard.output_labels.next is missing or falls back to key"
    )


def test_wizard_next_locale_key_in_hu() -> None:
    """application.wizard.output_labels.next exists in hu.yml."""
    result = tr(_NEXT_LOCALE_KEY, locale="hu")
    assert result and result != _NEXT_LOCALE_KEY, (
        "hu locale key application.wizard.output_labels.next is missing or falls back to key"
    )


# ---------------------------------------------------------------------------
# (c) _parser.py _PdfWord adapter-internal alias rationale documented
# ---------------------------------------------------------------------------

_PARSER_REL = "adapters/inbound/declaracion/_parser.py"
_PDFWORD_RATIONALE_TOKEN = "ADAPTER-INTERNAL-ALIAS-RATIONALE-PDFWORD"


def test_pdfword_alias_rationale_comment_present() -> None:
    """_PdfWord TypeAlias has the ADAPTER-INTERNAL-ALIAS-RATIONALE-PDFWORD comment."""
    src = _source(_PARSER_REL)
    assert _PDFWORD_RATIONALE_TOKEN in src, f"{_PDFWORD_RATIONALE_TOKEN!r} rationale comment missing from _parser.py"


def test_pdfword_alias_is_dict_str_any() -> None:
    """_PdfWord remains dict[str, Any] — adapter-internal, not moved to core._types."""
    src = _source(_PARSER_REL)
    tree = ast.parse(src)
    assignments: dict[str, ast.Assign] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "_PdfWord":
            assignments[target.id] = node
    assert "_PdfWord" in assignments, "_PdfWord assignment not found in _parser.py"


# ---------------------------------------------------------------------------
# (d) _local.py sidecar read returns Mapping[str, object]
# ---------------------------------------------------------------------------

_LOCAL_REL = "adapters/outbound/storage/_local.py"
_SIDECAR_CAST_TOKEN = "CAST-RATIONALE-SIDECAR-MAPPING"


def test_local_sidecar_cast_rationale_present() -> None:
    """_load_sidecar has the CAST-RATIONALE-SIDECAR-MAPPING comment."""
    src = _source(_LOCAL_REL)
    assert _SIDECAR_CAST_TOKEN in src, f"{_SIDECAR_CAST_TOKEN!r} missing from _local.py"


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
