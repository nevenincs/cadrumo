"""Every catalogue verb addresses a key YAML quotes, not only the plain ones.

YAML writes a purely numeric mapping key quoted -- ``'1076':`` -- and every
casilla id in the modelo schema is exactly that shape. A line-oriented writer
that matches keys with ``[\\w-]+`` never sees such a line, so it reports the key
as absent from a file that plainly contains it.

That produced a verb pair which disagreed about the same key in the same file:
``set`` resolved it through the parsed mapping and landed, while ``remove``
validated it structurally and then deleted by scanning text, so it refused a
leaf it had itself just resolved. With hand-editing a catalogue forbidden, there
was no sanctioned way to return such a leaf to absent at all.

**The controls are the point of this module.** A test that only exercised the
quoted path could not tell "the verb works" from "the verb was never reached",
so every case here is paired with an unquoted one that must keep working. And
the quoted cases are nested under TWO quoted ancestors, because the original
scan failed on any quoted segment in the path rather than only on the leaf's own
parent -- a fixture quoting one level would have passed against the broken code.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from ..errors import LocaleError
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Two quoted ancestors (``'100'``, ``'1076'``) beside a fully unquoted branch.
_CATALOGUE = """cli:
  plain:
    help: something
    other: keep
modelo:
  schema:
    '100':
      casilla:
        '1076':
          help: modelo.x
          label: NIF
        '1077':
          only: solo
"""


@pytest.fixture
def manager(tmp_path: Path) -> LocaleManager:
    """Return a manager over a throwaway four-locale catalogue."""
    src = tmp_path / "src"
    src.mkdir()
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.yml").write_text(_CATALOGUE, encoding="utf-8")
    for other in ("es", "ca", "hu"):
        shutil.copy(locales / "en.yml", locales / f"{other}.yml")
    return LocaleManager(src, locales)


def _leaf(manager: LocaleManager, locale: str, dotted_key: str) -> object:
    """Return the on-disk leaf, or a sentinel string when it is absent."""
    node = yaml.safe_load((manager.locales_dir / f"{locale}.yml").read_text(encoding="utf-8")) or {}
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return "<absent>"
        node = node[part]
    return node


def test_remove_resolves_a_leaf_under_quoted_ancestors(manager: LocaleManager) -> None:
    """The reproduction: a casilla help leaf is removable, and its sibling survives.

    Asserting the sibling matters. A writer that removed the leaf by deleting
    more than it addressed would satisfy the absence check alone.
    """
    manager.remove_locale_value("en", "modelo.schema.100.casilla.1076.help")

    assert _leaf(manager, "en", "modelo.schema.100.casilla.1076.help") == "<absent>"
    assert _leaf(manager, "en", "modelo.schema.100.casilla.1076.label") == "NIF"


def test_remove_still_resolves_a_fully_unquoted_leaf(manager: LocaleManager) -> None:
    """The control. Without it, a passing quoted case cannot be distinguished
    from a verb that removes indiscriminately.
    """
    manager.remove_locale_value("es", "cli.plain.help")

    assert _leaf(manager, "es", "cli.plain.help") == "<absent>"
    assert _leaf(manager, "es", "cli.plain.other") == "keep"


def test_batch_remove_prunes_each_exact_leaf_without_deleting_siblings(manager: LocaleManager) -> None:
    """One guarded rewrite removes several exact keys beneath quoted segments."""
    manager.remove_locale_values(
        "en",
        (
            "modelo.schema.100.casilla.1076.help",
            "modelo.schema.100.casilla.1077.only",
        ),
    )

    assert _leaf(manager, "en", "modelo.schema.100.casilla.1076.help") == "<absent>"
    assert _leaf(manager, "en", "modelo.schema.100.casilla.1077") == "<absent>"
    assert _leaf(manager, "en", "modelo.schema.100.casilla.1076.label") == "NIF"


def test_set_appends_a_new_leaf_under_quoted_ancestors(manager: LocaleManager) -> None:
    """The other half of the same defect, which the row did not name.

    ``set`` only reached the parsed mapping when the leaf already existed; a
    NEW leaf went through the same line-oriented writer and was refused for the
    same reason. Both branches now go through the mapping.
    """
    manager.set_locale_value("ca", "modelo.schema.100.casilla.1076.brandnew", "hello")

    assert _leaf(manager, "ca", "modelo.schema.100.casilla.1076.brandnew") == "hello"


def test_set_still_appends_a_new_leaf_on_an_unquoted_path(manager: LocaleManager) -> None:
    """The control for the append branch."""
    manager.set_locale_value("hu", "cli.plain.brandnew", "hello")

    assert _leaf(manager, "hu", "cli.plain.brandnew") == "hello"
    assert _leaf(manager, "hu", "cli.plain.other") == "keep"


def test_removing_the_only_child_prunes_its_quoted_namespace(manager: LocaleManager) -> None:
    """An emptied namespace goes too, and a populated neighbour does not.

    The pruner walks the parsed mapping, so a namespace whose key YAML quotes
    is pruned like any other -- the line-oriented pruner it replaced could not
    match ``'1077':`` and would have left an empty mapping behind.
    """
    manager.remove_locale_value("hu", "modelo.schema.100.casilla.1077.only")

    assert _leaf(manager, "hu", "modelo.schema.100.casilla.1077") == "<absent>"
    assert _leaf(manager, "hu", "modelo.schema.100.casilla.1076.label") == "NIF"


def test_a_namespace_is_still_refused_rather_than_deleted_wholesale(manager: LocaleManager) -> None:
    """Addressing a namespace must refuse, not delete every leaf beneath it."""
    with pytest.raises(LocaleError, match="resolves to a namespace"):
        manager.remove_locale_value("en", "modelo.schema.100.casilla")

    assert _leaf(manager, "en", "modelo.schema.100.casilla.1076.label") == "NIF"


def test_an_absent_key_is_still_refused(manager: LocaleManager) -> None:
    """A key the catalogue does not carry refuses, and says so as a key rather
    than as a fact about YAML text.
    """
    with pytest.raises(LocaleError, match="Locale key not found"):
        manager.remove_locale_value("en", "modelo.schema.100.casilla.9999.help")
