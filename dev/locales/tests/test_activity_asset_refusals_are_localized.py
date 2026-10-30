"""Activity-asset refusals reach operators through the locale catalogues.

``resolve_error_message`` returns an error's first positional argument verbatim
when no ``translated_message`` key is set, so an English literal raised from
the activity-asset code surfaced untranslated in every frontend. The gate walks
the activity-asset sources and requires every refusal to carry a catalogue key
that resolves in all four supported locales.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ERROR_CLASS = re.compile(r"^ActividadAsset\w*Error$")
_KEY_PREFIX = "ledger.actividad_asset.errors."
_PACKAGES = (
    SRC_DIR / "domain" / "renta" / "actividad_asset",
    SRC_DIR / "application" / "actividad_asset",
)
_SINGLE_FILES = (SRC_DIR / "domain" / "calculations" / "registry" / "actividad_asset_bindings.py",)

# These modules convert next; the exemption leaves with them.
_NOT_YET_CONVERTED = frozenset(
    {
        "schedule.py",
        "claims.py",
        "history.py",
    },
)


def _class_name(node: ast.expr) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        name = target.id
    elif isinstance(target, ast.Attribute):
        name = target.attr
    else:
        return None
    return name if _ERROR_CLASS.match(name) else None


def _scan(source: str, filename: str) -> tuple[list[str], list[tuple[int, str]]]:
    """Return the unlocalized refusals and every literal catalogue key a module names."""
    tree = ast.parse(source, filename=filename)
    raised_calls = {id(node.exc) for node in ast.walk(tree) if isinstance(node, ast.Raise) and node.exc is not None}
    violations: list[str] = []
    keys: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(_KEY_PREFIX):
            keys.append((node.lineno, node.value))
        bare = isinstance(node, ast.Raise) and isinstance(node.exc, ast.Name | ast.Attribute)
        if bare and _class_name(node.exc) is not None:
            violations.append(f"{filename}:{node.lineno} raises the bare class without a catalogue key")
        if not isinstance(node, ast.Call) or _class_name(node) is None:
            continue
        if any(keyword.arg == "translated_message" for keyword in node.keywords):
            continue
        if id(node) in raised_calls or node.args:
            violations.append(f"{filename}:{node.lineno} builds a refusal without translated_message")
    return violations, keys


def _owned_sources() -> list[Path]:
    """Derive the module list from the filesystem, never from a hand-kept list."""
    found: list[Path] = []
    for package in _PACKAGES:
        found.extend(path for path in package.rglob("*.py") if "tests" not in path.relative_to(package).parts)
    found.extend(_SINGLE_FILES)
    return sorted(path for path in found if path.name not in _NOT_YET_CONVERTED)


def test_the_gate_detects_a_literal_refusal_and_a_missing_key() -> None:
    source = (
        "def f(x):\n"
        "    if x:\n"
        '        raise ActividadAssetUnsupportedError("An English literal")\n'
        "    if x > 1:\n"
        '        raise ActividadAssetValidationError(f"value {x}", context={"x": x})\n'
        "    raise ActividadAssetIncompleteError\n"
        "def g():\n"
        '    return ActividadAssetValidationError("literal")\n'
    )
    violations, _ = _scan(source, "fixture.py")
    assert {item.split(" ", 1)[0] for item in violations} == {
        "fixture.py:3",
        "fixture.py:5",
        "fixture.py:6",
        "fixture.py:8",
    }


def test_the_gate_accepts_keyed_refusals_and_collects_their_keys() -> None:
    source = (
        "def f(x):\n"
        f'    raise ActividadAssetUnsupportedError(context={{"x": x}}, translated_message="{_KEY_PREFIX}some_key")\n'
        "def g(error):\n"
        "    raise error\n"
        "def h(context):\n"
        "    return ActividadAssetValidationError(context=context)\n"
    )
    violations, keys = _scan(source, "fixture.py")
    assert violations == []
    assert keys == [(2, f"{_KEY_PREFIX}some_key")]


def test_the_owned_sources_were_found() -> None:
    names = {path.name for path in _owned_sources()}
    assert {"actividad_asset_bindings.py", "workforce.py", "vehicle_affectation.py", "modality.py"} <= names


def test_every_activity_asset_refusal_carries_a_catalogue_key() -> None:
    violations: list[str] = []
    for path in _owned_sources():
        found, _ = _scan(path.read_text(encoding="utf-8"), str(path.relative_to(SRC_DIR)))
        violations.extend(found)
    assert not violations, "\n".join(violations)


def test_every_named_refusal_key_resolves_in_every_locale() -> None:
    manager = LocaleManager(SRC_DIR, LOCALES_DIR)
    catalogues = {locale: manager.locale_catalogue_keys(locale) for locale in SUPPORTED_OUTPUT_LANGUAGES}
    assert set(catalogues) >= {"en", "es", "ca", "hu"}
    named: dict[str, str] = {}
    for path in _owned_sources():
        _, keys = _scan(path.read_text(encoding="utf-8"), str(path.relative_to(SRC_DIR)))
        for line, key in keys:
            named.setdefault(key, f"{path.name}:{line}")
    assert named, "no refusal key was found; the scan would be vacuous"
    missing = sorted(
        f"{locale}: {key} ({where})"
        for key, where in named.items()
        for locale, keys in catalogues.items()
        if key not in keys
    )
    assert not missing, "\n".join(missing)
