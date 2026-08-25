"""The ``allow-identical`` verb writes the translation-honesty allowlist.

No verb previously wrote ``_intentional_identical.json`` while the locale
rules forbid hand-editing it, so recording a legitimately-identical string
had no sanctioned path. These exercise the real manager against a real
catalogue and a real allowlist file — no test doubles.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ..errors import LocaleError
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ALLOWLIST = "_intentional_identical.json"


@pytest.fixture
def manager(tmp_path: Path) -> LocaleManager:
    """Build a manager over a throwaway two-key catalogue."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    for code in ("en", "ca"):
        (locales_dir / f"{code}.yml").write_text(
            yaml.dump({"brand": {"name": "Cadrumo"}}, allow_unicode=True),
            encoding="utf-8",
        )
    return LocaleManager(tmp_path, locales_dir)


def _allowlist(manager: LocaleManager) -> dict[str, dict[str, object]]:
    return json.loads((manager.locales_dir / _ALLOWLIST).read_text(encoding="utf-8"))


def test_records_the_key_with_its_reason(manager: LocaleManager) -> None:
    """A recorded exemption lands under its locale carrying the stated reason."""
    manager.allow_identical("ca", "brand.name", "Brand name is identical in Catalan")

    assert _allowlist(manager)["ca"]["brand.name"] == "Brand name is identical in Catalan"


def test_preserves_existing_entries_and_metadata(manager: LocaleManager) -> None:
    """Writing one exemption leaves other locales and ``_``-prefixed metadata intact."""
    (manager.locales_dir / _ALLOWLIST).write_text(
        json.dumps({"hu": {"untranslated_pending": "pending pass", "_untranslated_ceiling": 106}}),
        encoding="utf-8",
    )

    manager.allow_identical("ca", "brand.name", "Brand name is identical in Catalan")

    allowlist = _allowlist(manager)
    assert allowlist["hu"] == {"untranslated_pending": "pending pass", "_untranslated_ceiling": 106}
    assert allowlist["ca"]["brand.name"] == "Brand name is identical in Catalan"


def test_refuses_a_blank_reason(manager: LocaleManager) -> None:
    """The allowlist states why a string is identical; it is not a mute button."""
    with pytest.raises(LocaleError, match="non-empty reason"):
        manager.allow_identical("ca", "brand.name", "   ")

    assert not (manager.locales_dir / _ALLOWLIST).exists()


def test_refuses_a_key_absent_from_the_catalogue(manager: LocaleManager) -> None:
    """Exempting a key the locale does not carry would mask a real drift."""
    with pytest.raises(LocaleError, match="Locale key not found"):
        manager.allow_identical("ca", "brand.absent", "no such key")


def test_refuses_an_allowlist_metadata_key(manager: LocaleManager) -> None:
    """``_``-prefixed names are the allowlist's own metadata, not locale keys."""
    with pytest.raises(LocaleError, match="allowlist metadata"):
        manager.allow_identical("ca", "_untranslated_ceiling", "not a locale key")
