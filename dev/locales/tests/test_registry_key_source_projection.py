"""Focused contracts for binding-independent category locale discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.categories import registry as category_registry

from .. import _registry_scanner as scanner_module
from .._registry_scanner import LocaleRegistryEnumerationError, scan_registry_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _write_category_fact(root: Path, *, localized_value: str = "categories.registry.alpha.label") -> Path:
    source = root / "0064-categories-profile.toml"
    source.write_text(
        """[fact]
fact_id = "categories.profile"
family = "mapping"

[[fact.variants]]
[fact.variants.payload]
kind = "mapping"
entries = [
  { key = "display_label", value = "__DISPLAY_LABEL__" },
  { key = "notes", value = "categories.registry.alpha.notes" },
  { key = "statutory_cap_variant.general.label", value = "categories.registry.alpha.cap.general" },
  { key = "statutory_cap_variant.general.eur", value = 100 },
  { key = "citation.0.quote", value = "verbatim evidence" },
]
""".replace("__DISPLAY_LABEL__", localized_value),
        encoding="utf-8",
    )
    return source


def test_category_projection_reads_committed_fact_without_published_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _write_category_fact(tmp_path)
    monkeypatch.setattr(scanner_module, "bundled_path", lambda *_parts: source)

    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("locale discovery must not load the published category authority")

    monkeypatch.setattr(category_registry, "load_category_profiles", fail)

    assert scan_registry_keys() == {
        "categories.registry.alpha.label",
        "categories.registry.alpha.notes",
        "categories.registry.alpha.cap.general",
    }


def test_category_projection_fails_closed_on_ambiguous_localized_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _write_category_fact(tmp_path, localized_value="not-a-locale-key")
    monkeypatch.setattr(scanner_module, "bundled_path", lambda *_parts: source)

    with pytest.raises(LocaleRegistryEnumerationError, match="ambiguous locale key"):
        scan_registry_keys()


def test_category_projection_fails_closed_on_unknown_cap_variant_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _write_category_fact(tmp_path)
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "statutory_cap_variant.general.eur", "statutory_cap_variant.general.eur_per_week"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(scanner_module, "bundled_path", lambda *_parts: source)

    with pytest.raises(LocaleRegistryEnumerationError, match="ambiguous cap-variant shape"):
        scan_registry_keys()


def test_category_projection_fails_closed_on_unreadable_toml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "0064-categories-profile.toml"
    source.write_text("[fact\n", encoding="utf-8")
    monkeypatch.setattr(scanner_module, "bundled_path", lambda *_parts: source)

    with pytest.raises(LocaleRegistryEnumerationError, match="cannot enumerate category profile locale keys"):
        scan_registry_keys()
