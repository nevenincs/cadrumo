"""Real-behavior proofs for the public locale-catalogue capture contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ..locale_catalogue import (
    LocaleCatalogueCapture,
    LocaleCatalogueCaptureError,
    LocaleCatalogueCurrentCoordinate,
    capture_locale_catalogue,
    read_locale_catalogue_current_coordinate,
)
from ..render import lookup_translation_entry, override_locales_root

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_KEY = "cli.common.label.total"


def _write_catalogue(root: Path, *, locale: str, value: str) -> None:
    """Write one real shard directory the catalogue reader can load."""
    shard_dir = root / locale
    shard_dir.mkdir(parents=True, exist_ok=True)
    (shard_dir / "cli.yml").write_text(
        f'cli:\n  common:\n    label:\n      total: "{value}"\n',
        encoding="utf-8",
    )


def test_capture_republishes_the_reader_entry_without_a_second_lookup(tmp_path: Path) -> None:
    """The capture carries exactly what the sole catalogue reader returned."""
    _write_catalogue(tmp_path, locale="es", value="Total")

    with override_locales_root(tmp_path):
        captured = capture_locale_catalogue(_KEY, locale="es")
        present, value = lookup_translation_entry(_KEY, locale="es")

    assert (captured.present, captured.value) == (present, value)
    assert captured.value == "Total"
    assert captured.locale == "es"
    assert captured.translation_key == _KEY


def test_capture_is_singleflight_and_refuses_a_superseded_catalogue(tmp_path: Path) -> None:
    """An unchanged catalogue shares a generation; a rewrite supersedes the capture."""
    _write_catalogue(tmp_path, locale="es", value="Total")

    with override_locales_root(tmp_path):
        first = capture_locale_catalogue(_KEY, locale="es")
        second = capture_locale_catalogue(_KEY, locale="es")

        assert first.generation == second.generation
        assert first.comparison_domain == second.comparison_domain

        current = read_locale_catalogue_current_coordinate(locale="es")
        assert first.require_current(current) is first

        _write_catalogue(tmp_path, locale="es", value="Suma total")
        advanced = read_locale_catalogue_current_coordinate(locale="es")

    assert advanced.generation > first.generation
    with pytest.raises(LocaleCatalogueCaptureError):
        first.require_current(advanced)


def test_a_capture_from_another_locale_scope_is_not_current(tmp_path: Path) -> None:
    """Two locales are distinct owner scopes and never validate each other."""
    _write_catalogue(tmp_path, locale="es", value="Total")
    _write_catalogue(tmp_path, locale="en", value="Total")

    with override_locales_root(tmp_path):
        spanish = capture_locale_catalogue(_KEY, locale="es")
        english_coordinate = read_locale_catalogue_current_coordinate(locale="en")

    assert spanish.comparison_domain != english_coordinate.comparison_domain
    with pytest.raises(LocaleCatalogueCaptureError):
        spanish.require_current(english_coordinate)


def test_an_unsupported_locale_refuses_rather_than_capturing_nothing(tmp_path: Path) -> None:
    """A locale outside the supported set fails closed instead of reading blank."""
    _write_catalogue(tmp_path, locale="es", value="Total")

    with override_locales_root(tmp_path), pytest.raises(LocaleCatalogueCaptureError):
        capture_locale_catalogue(_KEY, locale="de")


def test_the_published_digest_is_the_catalogue_it_was_read_under(tmp_path: Path) -> None:
    """The digest names the exact shard set, and changes only when the shards do."""
    _write_catalogue(tmp_path, locale="es", value="Total")

    with override_locales_root(tmp_path):
        first = capture_locale_catalogue(_KEY, locale="es")
        unchanged = capture_locale_catalogue(_KEY, locale="es")

        assert first.catalogue_digest == unchanged.catalogue_digest

        _write_catalogue(tmp_path, locale="es", value="Suma total")
        rewritten = capture_locale_catalogue(_KEY, locale="es")

    assert rewritten.catalogue_digest != first.catalogue_digest
    assert rewritten.value == "Suma total"


def test_capture_exposes_no_catalogue_internals_and_no_parallel_reader() -> None:
    """The capture adds a coordinate only; it derives no second catalogue shape."""
    from dataclasses import fields

    assert {field.name for field in fields(LocaleCatalogueCapture)} == {
        "locale",
        "translation_key",
        "present",
        "value",
        "catalogue_digest",
        "comparison_domain",
        "generation",
    }
    assert {field.name for field in fields(LocaleCatalogueCurrentCoordinate)} == {
        "comparison_domain",
        "generation",
    }


def test_locale_catalogue_capture_is_owned_by_its_defining_module() -> None:
    """Every capture symbol is defined here and bound nowhere in the package namespace."""
    from ... import i18n as i18n_namespace

    for owned in (
        LocaleCatalogueCapture,
        LocaleCatalogueCurrentCoordinate,
        LocaleCatalogueCaptureError,
        capture_locale_catalogue,
        read_locale_catalogue_current_coordinate,
    ):
        assert owned.__module__ == "cadrumo.core.i18n.locale_catalogue"
        assert not hasattr(i18n_namespace, owned.__name__)
