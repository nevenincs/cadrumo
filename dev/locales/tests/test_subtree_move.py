"""Behaviour of the value-preserving subtree move, over real catalogue files.

Every case here builds a real four-locale catalogue tree on disk, drives the
real :class:`~dev.locales.manager.LocaleManager` against it, and reads the
result back off disk. Nothing is patched: the point of the verb is what it
leaves in the files, and a stubbed writer would prove only that the plan was
computed.

The revision rename that motivates the verb is used as the worked example
throughout, because the catalogue shape it produces -- a Modelo shard, keys
whose leaf may be an explicit null, four locales that must not diverge -- is
where the operation is load-bearing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from .. import (
    LocaleManager,
    LocaleMoveConflict,
    LocaleNode,
)
from ..errors import LocaleError
from ..manager import _flatten_leaf_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_MODELO = "322"
_SOURCE = f"modelo.schema.{_MODELO}.revision.2008-2023"
_DESTINATION = f"modelo.schema.{_MODELO}.revision.2023"
_SECOND_DESTINATION = f"modelo.schema.{_MODELO}.revision.2008-2022"


def _shard_path(locales_dir: Path, locale: str) -> Path:
    """Return the Modelo shard the worked example writes in one locale."""
    return locales_dir / locale / "modelo" / "schema" / f"{_MODELO}.yml"


def _write_catalogue(locales_dir: Path, locale: str, leaves: dict[str, LocaleNode]) -> Path:
    """Materialise one locale's Modelo shard from dotted leaves."""
    nested: dict[str, LocaleNode] = {}
    for dotted_key, value in leaves.items():
        cursor = nested
        parts = dotted_key.split(".")
        for part in parts[:-1]:
            child = cursor.setdefault(part, {})
            assert isinstance(child, dict)
            cursor = child
        cursor[parts[-1]] = value
    path = _shard_path(locales_dir, locale)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(nested, allow_unicode=True, sort_keys=True), encoding="utf-8")
    return path


def _read_leaves(manager: LocaleManager, locales_dir: Path, locale: str) -> dict[str, str | None]:
    """Return one locale catalogue's flattened leaves, read back from disk."""
    return _flatten_leaf_values(manager.load_locale(locales_dir / locale))


def _digests(locales_dir: Path) -> dict[Path, str]:
    """Fingerprint every catalogue file, so an unwritten tree is provable."""
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(locales_dir.rglob("*.yml"))}


@pytest.fixture
def catalogue_tree(tmp_path: Path) -> tuple[LocaleManager, Path]:
    """Build a four-locale catalogue carrying one revision's casilla keys."""
    locales_dir = tmp_path / "locales"
    for locale in _LOCALES:
        _write_catalogue(
            locales_dir,
            locale,
            {
                f"{_SOURCE}.casilla.01.label": f"{locale} label 01",
                f"{_SOURCE}.casilla.01.help": f"{locale} help 01",
                f"{_SOURCE}.casilla.02.label": f"{locale} label 02",
                f"{_SOURCE}.casilla.02.help": None,
            },
        )
    return LocaleManager(tmp_path / "src", locales_dir), locales_dir


def test_move_carries_every_value_to_the_destination_in_every_locale(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """A rename relocates the subtree in all four catalogues with values intact."""
    manager, locales_dir = catalogue_tree
    before = {locale: _read_leaves(manager, locales_dir, locale) for locale in _LOCALES}

    result = manager.move_locale_subtree(_SOURCE, [_DESTINATION])

    assert not result.dry_run
    assert len(result.written_paths) == len(_LOCALES)
    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert not [key for key in after if key.startswith(f"{_SOURCE}.")]
        for source_key, value in before[locale].items():
            destination_key = f"{_DESTINATION}{source_key[len(_SOURCE) :]}"
            assert after[destination_key] == value


def test_an_absent_modelo_leaf_moves_as_an_absent_leaf(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """An explicitly absent Modelo value is carried, never coerced to a string.

    The catalogues encode "declared, not yet translated" as a null leaf, and a
    move that turned one into the string ``None`` would ship that text to an
    operator while every presence check stayed green.
    """
    manager, locales_dir = catalogue_tree

    manager.move_locale_subtree(_SOURCE, [_DESTINATION])

    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert after[f"{_DESTINATION}.casilla.02.help"] is None


def test_dry_run_reports_the_plan_and_writes_nothing(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """A previewed move leaves every catalogue byte-identical."""
    manager, locales_dir = catalogue_tree
    before = _digests(locales_dir)

    result = manager.move_locale_subtree(_SOURCE, [_DESTINATION], dry_run=True)

    assert result.dry_run
    assert result.written_paths == ()
    assert len(result.plan.writes) == len(_LOCALES) * 4
    assert _digests(locales_dir) == before


def test_copy_leaves_the_source_subtree_in_place(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """A copy is what a split needs: the source survives the first destination."""
    manager, locales_dir = catalogue_tree

    manager.move_locale_subtree(_SOURCE, [_DESTINATION], keep_source=True)

    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert after[f"{_SOURCE}.casilla.01.label"] == f"{locale} label 01"
        assert after[f"{_DESTINATION}.casilla.01.label"] == f"{locale} label 01"


def test_a_destination_value_conflict_is_refused_and_nothing_is_written(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """The default refuses to clobber authored prose, and refuses before writing."""
    manager, locales_dir = catalogue_tree
    for locale in _LOCALES:
        manager.set_locale_value(locale, f"{_DESTINATION}.casilla.01.label", f"{locale} authored destination")
    before = _digests(locales_dir)

    with pytest.raises(LocaleError, match="already carry a different value"):
        manager.move_locale_subtree(_SOURCE, [_DESTINATION])

    assert _digests(locales_dir) == before


def test_skip_keeps_the_destination_value_and_still_releases_the_source(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """``skip`` resolves a conflict in favour of the value already authored."""
    manager, locales_dir = catalogue_tree
    for locale in _LOCALES:
        manager.set_locale_value(locale, f"{_DESTINATION}.casilla.01.label", f"{locale} authored destination")

    manager.move_locale_subtree(_SOURCE, [_DESTINATION], on_conflict=LocaleMoveConflict.SKIP)

    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert after[f"{_DESTINATION}.casilla.01.label"] == f"{locale} authored destination"
        assert after[f"{_DESTINATION}.casilla.02.label"] == f"{locale} label 02"
        assert not [key for key in after if key.startswith(f"{_SOURCE}.")]


def test_overwrite_replaces_the_destination_value(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """``overwrite`` resolves a conflict in favour of the value being carried."""
    manager, locales_dir = catalogue_tree
    for locale in _LOCALES:
        manager.set_locale_value(locale, f"{_DESTINATION}.casilla.01.label", f"{locale} authored destination")

    manager.move_locale_subtree(_SOURCE, [_DESTINATION], on_conflict=LocaleMoveConflict.OVERWRITE)

    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert after[f"{_DESTINATION}.casilla.01.label"] == f"{locale} label 01"


def test_a_split_routes_each_leaf_to_the_revision_that_declares_it(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """Two destinations each take the casillas their own revision declares.

    This is the shape a registry split produces, and the reason the verb takes
    an allowlist rather than duplicating the whole subtree into both halves:
    casilla 01 survives into the new revision, casilla 02 stays with the old
    span, and neither destination acquires a key its revision never declared.
    """
    manager, locales_dir = catalogue_tree
    permitted = {
        _DESTINATION: frozenset({f"{_DESTINATION}.casilla.01.label", f"{_DESTINATION}.casilla.01.help"}),
        _SECOND_DESTINATION: frozenset(
            {f"{_SECOND_DESTINATION}.casilla.02.label", f"{_SECOND_DESTINATION}.casilla.02.help"},
        ),
    }

    manager.move_locale_subtree(
        _SOURCE,
        [_DESTINATION, _SECOND_DESTINATION],
        permitted_destination_keys=permitted,
    )

    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert after[f"{_DESTINATION}.casilla.01.label"] == f"{locale} label 01"
        assert f"{_DESTINATION}.casilla.02.label" not in after
        assert after[f"{_SECOND_DESTINATION}.casilla.02.label"] == f"{locale} label 02"
        assert f"{_SECOND_DESTINATION}.casilla.01.label" not in after
        assert not [key for key in after if key.startswith(f"{_SOURCE}.")]


def test_a_leaf_no_destination_declares_blocks_the_release_until_it_is_dropped(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """A value nothing would carry is never released silently."""
    manager, locales_dir = catalogue_tree
    permitted = {
        _DESTINATION: frozenset({f"{_DESTINATION}.casilla.01.label", f"{_DESTINATION}.casilla.01.help"}),
    }
    before = _digests(locales_dir)

    with pytest.raises(LocaleError, match="match no destination"):
        manager.move_locale_subtree(_SOURCE, [_DESTINATION], permitted_destination_keys=permitted)
    assert _digests(locales_dir) == before

    manager.move_locale_subtree(
        _SOURCE,
        [_DESTINATION],
        permitted_destination_keys=permitted,
        drop_undistributed=True,
    )
    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert after[f"{_DESTINATION}.casilla.01.label"] == f"{locale} label 01"
        assert not [key for key in after if key.startswith(f"{_SOURCE}.")]


def test_a_move_never_fabricates_a_value(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """No moved leaf echoes its own key.

    The verb exists because ``scaffold`` answers a rename with a placeholder
    the honesty ratchet refuses. A move that reintroduced one would have
    replaced that failure with itself.
    """
    manager, locales_dir = catalogue_tree

    manager.move_locale_subtree(_SOURCE, [_DESTINATION])

    for locale in _LOCALES:
        after = _read_leaves(manager, locales_dir, locale)
        assert not [key for key, value in after.items() if value == key]


def test_an_empty_source_subtree_is_refused(
    catalogue_tree: tuple[LocaleManager, Path],
) -> None:
    """Naming a namespace no catalogue carries is a mistake, not a no-op.

    A silent no-op reads as success, so a typo'd revision id would report a
    completed move over catalogues nothing touched.
    """
    manager, _locales_dir = catalogue_tree

    with pytest.raises(LocaleError, match="No locale keys found"):
        manager.move_locale_subtree(f"modelo.schema.{_MODELO}.revision.1999-2000", [_DESTINATION])


@pytest.mark.parametrize(
    ("source", "destinations", "expected"),
    [
        (_SOURCE, [_SOURCE], "onto itself"),
        (_SOURCE, [f"{_SOURCE}.casilla"], "its own subtree"),
        (_SOURCE, [_DESTINATION, _DESTINATION], "Duplicate destination"),
        ("modelo..revision", [_DESTINATION], "Invalid locale key prefix"),
    ],
)
def test_malformed_prefixes_are_refused(
    catalogue_tree: tuple[LocaleManager, Path],
    source: str,
    destinations: list[str],
    expected: str,
) -> None:
    """Every prefix relationship that cannot be a move is named, not attempted."""
    manager, _locales_dir = catalogue_tree

    with pytest.raises(LocaleError, match=expected):
        manager.move_locale_subtree(source, destinations)
