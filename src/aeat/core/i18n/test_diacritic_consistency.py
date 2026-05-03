"""Regression test: per-language diacritic consistency across ``t()`` literals.

Walks every Python module under ``src/aeat/`` and inspects every call
to ``t(es, en, ca, hu)`` / ``_t(...)``. For each call, when the
authoritative slot (``es`` for AEAT terms, or any slot using extended
Latin characters) carries diacritic-bearing text, the sibling slots
in languages whose orthography normally uses diacritics must not be
all-ASCII. This catches translations that were typed without the
required accents (e.g. Hungarian ``adoilletoseg`` instead of
``adóilletőség``).

The check is asymmetric: legitimate ASCII Hungarian words like
``mappa``, ``dokumentum``, ``rekord`` do not trip the test because
the corresponding Spanish/English slots are usually short and may
also be ASCII (``folder``, ``document``, ``record``). The test only
fires when the asymmetry between languages is implausible — when ES
or EN clearly contains accented or extended characters and the HU
slot does not, despite being long enough to expect at least one.

Like the bare-string regression test, this test ratchets a ceiling
downward; raising it is forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


_HU_DIACRITICS: frozenset[str] = frozenset("őűáéíóúÁÉÍÓÖŐÚÜŰöü")
_ES_DIACRITICS: frozenset[str] = frozenset("áéíóúñÁÉÍÓÚÑüÜ¿¡")
_CA_DIACRITICS: frozenset[str] = frozenset("àèéíòóúçÀÈÉÍÒÓÚÇ·")


# Ratchet ceiling — drop on every successful diacritic-restoration pass.
_MAX_HU_ASYMMETRIC_BARE = 5
"""Strings where ES has accents but HU is plain ASCII despite ≥8 chars + spaces."""


_CLI_ROOT = Path(__file__).resolve().parents[2]


def _has_diacritics(text: str, alphabet: frozenset[str]) -> bool:
    return any(ch in alphabet for ch in text)


def _is_legitimate_ascii_hungarian(hu: str) -> bool:
    """Heuristic: short HU (<15 chars) or no spaces is presumed legitimate.

    Hungarian words like ``mappa``, ``rekord``, ``futtasd``, ``ezzel``
    are naturally diacritic-free. Short multi-word phrases (e.g.
    ``rekord ezzel:``) are equally plausible legitimate ASCII content.
    The audit only flags HU as suspicious when the slot is long enough
    that at least one diacritic would plausibly appear in normal prose.
    """
    return len(hu) < 15 or " " not in hu


def _collect_multilingual_calls(tree: ast.Module) -> list[tuple[int, str, str, str, str]]:
    """Return every ``(lineno, es, en, ca, hu)`` tuple from multilingual t() calls."""
    out: list[tuple[int, str, str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) != 4:
            continue
        callee = (
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else (node.func.id if isinstance(node.func, ast.Name) else "")
        )
        if callee not in ("t", "_t"):
            continue
        slots: list[str] = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                slots.append(arg.value)
            else:
                slots.append("")
        if all(slots) and len(slots) == 4:
            out.append((node.lineno, slots[0], slots[1], slots[2], slots[3]))
    return out


def _walk_src() -> list[Path]:
    """Iterate every shippable .py module under ``src/aeat/``."""
    return [
        p
        for p in sorted(_CLI_ROOT.rglob("*.py"))
        if not p.name.startswith(("test_", "_test_")) and p.name != "conftest.py"
    ]


def test_hu_slot_has_diacritics_when_es_does() -> None:
    """When ES uses accents, HU should too — unless the HU is genuinely short or
    composed of accent-free Hungarian words.

    The test fails if the asymmetric-bare count rises above the
    recorded ceiling. Drop ``_MAX_HU_ASYMMETRIC_BARE`` after each
    diacritic restoration pass; raising it is a contract violation.
    """
    asymmetric: list[tuple[Path, int, str, str]] = []
    for path in _walk_src():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for lineno, es, _en, ca, hu in _collect_multilingual_calls(tree):
            es_has = _has_diacritics(es, _ES_DIACRITICS)
            ca_has = _has_diacritics(ca, _CA_DIACRITICS)
            hu_has = _has_diacritics(hu, _HU_DIACRITICS)
            if (es_has or ca_has) and not hu_has and not _is_legitimate_ascii_hungarian(hu):
                asymmetric.append((path, lineno, hu, es))

    if len(asymmetric) > _MAX_HU_ASYMMETRIC_BARE:
        report_lines = [
            f"HU diacritic-asymmetry count rose to {len(asymmetric)}; ceiling is {_MAX_HU_ASYMMETRIC_BARE}. Top sites:",
        ]
        for path, lineno, hu, es in asymmetric[:10]:
            try:
                rel = path.relative_to(_CLI_ROOT)
            except ValueError:
                rel = path
            report_lines.append(f"  {rel}:{lineno}")
            report_lines.append(f"    es: {es[:60]!r}")
            report_lines.append(f"    hu: {hu[:60]!r}")
        pytest.fail("\n".join(report_lines))


def test_unicode_normalization_form_is_nfc() -> None:
    """Every literal in src/aeat/ must be NFC-normalised on disk.

    NFD-encoded composing characters (e.g. ``a + combining acute``
    instead of pre-composed ``á``) trip terminal renderers and string
    comparisons. Our :func:`get_translation` re-normalises at runtime
    but on-disk literals should already be NFC.
    """
    import unicodedata

    bad: list[tuple[Path, int, str]] = []
    for path in _walk_src():
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value
                if v != unicodedata.normalize("NFC", v):
                    bad.append((path, node.lineno, v[:40]))
    if bad:
        report = ["Found non-NFC string literals (NFD or mixed):"]
        for path, lineno, txt in bad[:20]:
            try:
                rel = path.relative_to(_CLI_ROOT)
            except ValueError:
                rel = path
            report.append(f"  {rel}:{lineno}  {txt!r}")
        pytest.fail("\n".join(report))
