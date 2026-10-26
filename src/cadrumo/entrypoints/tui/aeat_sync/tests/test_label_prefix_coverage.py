"""Every enum the AEAT Sync screens render can be labelled, in every locale.

``_label`` looks a rendered enum up in ``_LABEL_PREFIXES`` and RAISES when it
finds nothing. It is reached from ``on_mount``, so an unmapped enum does not
degrade to a blank cell -- it takes the whole workspace down on open.

The map used to be keyed by class-name strings, which is what made that
reachable: nothing referenced the classes, so a rename would leave the key
pointing at a name no longer in the tree and the first symptom would be the
crash. It is keyed by the class itself now, so a rename updates the key and a
deletion fails the import. This module covers the half that a class key cannot:
that each mapped prefix actually has authored copy for every member, in all
four catalogues.

That half matters because ``tr`` does not raise on a missing key -- it
humanises the last dotted segment -- so a member with no wording renders
English-looking text everywhere and nothing fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ..screens import _LABEL_PREFIXES

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[4] / "locales"


def _catalogue(locale: str) -> dict[str, object]:
    loaded = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    return {str(key): value for key, value in loaded.items()}


def _resolve(catalogue: dict[str, object], dotted: str) -> str | None:
    """Walk the FULL dotted key, because member values contain dots themselves.

    ``AeatSyncWorkspaceSource`` has members like ``local.profile``, so the key
    is not "prefix plus one leaf" -- splitting only the prefix and treating the
    value as a single key reports seven false gaps.
    """
    node: object = catalogue
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, str) else None


def _expected_keys() -> tuple[str, ...]:
    return tuple(f"{prefix}.{member.value}" for enum_type, prefix in _LABEL_PREFIXES.items() for member in enum_type)


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_rendered_enum_member_is_worded_in_this_locale(locale: str) -> None:
    """A member with no copy renders a humanised token, not a translation."""
    catalogue = _catalogue(locale)

    missing = [key for key in _expected_keys() if _resolve(catalogue, key) is None]

    assert not missing, f"{locale} has no wording for: {missing}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_rendered_label_is_blank(locale: str) -> None:
    """Blank copy is indistinguishable from an empty cell at the terminal."""
    catalogue = _catalogue(locale)

    blank = [key for key in _expected_keys() if (_resolve(catalogue, key) or "").strip() == ""]

    assert not blank


def test_the_map_covers_a_plausible_population_of_screens() -> None:
    """Anti-tautology: an emptied map would satisfy every coverage test above.

    Pinned loosely -- a floor, not the exact count -- so adding a rendered enum
    does not fail this while still catching a map that collapsed.
    """
    assert len(_LABEL_PREFIXES) >= 15
    assert len(_expected_keys()) >= 70


def test_each_prefix_names_exactly_one_enum() -> None:
    """Two enums behind one prefix would collide member-for-member.

    Both would resolve the same catalogue key for equal member values, so one
    enum's wording would silently describe the other's state.
    """
    prefixes = list(_LABEL_PREFIXES.values())

    assert len(set(prefixes)) == len(prefixes)
