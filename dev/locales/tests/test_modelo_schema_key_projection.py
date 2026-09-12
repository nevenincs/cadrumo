"""Focused contracts for the binding-independent Modelo locale projection."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import (
    casilla_alias_locale_key,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
    construct_locale_key,
    modelo_locale_key,
    revision_locale_key,
)
from dev.registry.compiler import loader as loader_module
from dev.registry.compiler.loader import load_modelo_locale_key_projection

from .. import _registry_scanner as scanner_module
from .._registry_scanner import LocaleRegistryEnumerationError, scan_modelo_schema_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _write_structural_modelo(root: Path, *, casilla: str = "valid", malformed_binding: bool = False) -> Path:
    modelo = root / "modelos" / "999"
    revision = modelo / "revisions" / "2024"
    (revision / "constructs").mkdir(parents=True)
    (revision / "casillas").mkdir()
    (modelo / "manifest.toml").write_text('[modelo]\nid = "999"\n', encoding="utf-8")
    (revision / "revision.toml").write_text('[revisions."2024"]\n', encoding="utf-8")
    (revision / "constructs" / "0001-construct.toml").write_text(
        '[[revisions."2024".constructs]]\nid = "construct-1"\n',
        encoding="utf-8",
    )
    if malformed_binding:
        (revision / "bindings").mkdir()
        (revision / "bindings" / "0001-binding.toml").write_text(
            '[[revisions."2024".bindings]]\n'
            'id = "binding-1"\n'
            'provider = "not-a-provider"\n'
            "value = { not_a_contract = true }\n",
            encoding="utf-8",
        )
    if casilla == "valid":
        casilla_source = (
            '[[revisions."2024".casillas]]\n'
            'id = "c1"\n'
            'continuidad_id = "chain-1"\n'
            'aliases = [{ legal_refs = ["law-1"], source_refs = ["source-1"] }]\n'
        )
    elif casilla == "malformed-alias":
        casilla_source = '[[revisions."2024".casillas]]\nid = "c1"\naliases = ["not-a-table"]\n'
    else:
        raise AssertionError(f"unknown fixture variant: {casilla}")
    (revision / "casillas" / "0001-casilla.toml").write_text(casilla_source, encoding="utf-8")
    return root


def test_structural_projection_matches_every_modelo_identity_ignoring_binding_shape(tmp_path: Path) -> None:
    keys = load_modelo_locale_key_projection(_write_structural_modelo(tmp_path, malformed_binding=True))

    occurrence = casilla_occurrence_locale_key("999", "2024", "c1", "label")
    continuity = casilla_continuity_locale_key("999", "chain-1", "label")
    assert keys == {
        modelo_locale_key("999", "title"),
        modelo_locale_key("999", "official_name"),
        revision_locale_key("999", "2024"),
        construct_locale_key("999", "2024", "construct-1"),
        occurrence,
        f"{occurrence.removesuffix('.label')}.help",
        continuity,
        f"{continuity.removesuffix('.label')}.help",
        casilla_alias_locale_key("999", "2024", "c1", "0"),
    }


def test_structural_projection_fails_closed_on_malformed_alias_structure(tmp_path: Path) -> None:
    with pytest.raises(RegistryLoadError, match=r"alias\[0\].*table"):
        load_modelo_locale_key_projection(_write_structural_modelo(tmp_path, casilla="malformed-alias"))


def test_scanner_does_not_call_typed_registry_tree_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("typed registry tree loader must not be used for locale discovery")

    monkeypatch.setattr(loader_module, "load_registry_tree", fail)
    scan_modelo_schema_keys.cache_clear()
    try:
        keys = scan_modelo_schema_keys()
    finally:
        scan_modelo_schema_keys.cache_clear()

    assert len(keys) == 64550


def test_scanner_wraps_projection_failures_as_blocking_discovery_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_root: Path) -> frozenset[str]:
        raise OSError("registry source disappeared")

    monkeypatch.setattr(scanner_module, "load_modelo_locale_key_projection", fail)
    scan_modelo_schema_keys.cache_clear()
    try:
        with pytest.raises(LocaleRegistryEnumerationError, match="cannot enumerate Modelo schema locale keys"):
            scan_modelo_schema_keys()
    finally:
        scan_modelo_schema_keys.cache_clear()
