"""Localization gate for the substrate's operator-visible failure surface.

Every failure string a frontend renders comes from a
:class:`~cadrumo.application.flows.validators.ValidationVerdict` message key or a
frontend translation key resolved through the locale catalogues. A key
missing from a catalogue does not fail loudly at render time — ``tr``
falls back to a humanised English form of the key — so English prose
silently bleeds into localized runs. This gate makes that leak a test
failure instead: it sweeps every ``flows.*`` key referenced by the
substrate and TUI modules and asserts each resolves in all four
catalogues, then proves a real engine validation failure renders
localized.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from ....application.flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from ....application.flows.engine import answer, start_flow
from ....core import STRICT_FROZEN_CONFIG
from ....core.directory_scan import scan_directory
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....core.i18n import tr
from ....tests.locale_catalogue import flatten_catalogue, shard_keys, shard_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_SENTINEL = "\x00flows-localization-unresolved\x00"
_KEY_PATTERN = re.compile(r"[\"'](flows\.[a-z0-9_.]+)[\"']")

_SRC = Path(__file__).resolve().parents[4]
_FLOW_MODULE_DIRS = (
    _SRC / "cadrumo" / "application" / "flows",
    _SRC / "cadrumo" / "entrypoints" / "tui",
)


def _referenced_flow_keys() -> tuple[frozenset[str], frozenset[str]]:
    """Split the swept literals into whole keys and dynamic-key prefixes.

    A literal ending in ``.`` is a prefix a call site concatenates a runtime
    value onto, so it is not itself a key and can never resolve. Dropping it
    would silence the whole family it names, so it is returned separately and
    held to the strongest claim its shape can support: the family exists.
    """
    keys: set[str] = set()
    for directory in _FLOW_MODULE_DIRS:
        # A directory that is not there yields nothing rather than failing, and
        # the sweep's non-vacuity guard only fires when EVERY root comes back
        # empty -- so one live root masks a dead one indefinitely.
        assert directory.is_dir(), f"flow module root {directory} does not exist, so its keys are never swept"
        for module in scan_directory(directory, pattern="*.py", recursive=True):
            # The TUI keeps its keys in subpackages, so the sweep recurses; its
            # test modules carry synthetic flows.test.* keys that name no
            # catalogue entry by design and would be read as real references.
            if "tests" in module.parts or module.name.startswith("test_") or module.name == "conftest.py":
                continue
            keys |= set(_KEY_PATTERN.findall(module.read_text(encoding="utf-8")))
    prefixes = {key for key in keys if key.endswith(".")}
    return frozenset(keys - prefixes), frozenset(prefixes)


def test_every_referenced_flow_key_resolves_in_all_locales() -> None:
    """No substrate/TUI translation key may fall back to humanised English."""
    keys, _ = _referenced_flow_keys()
    assert keys, "key sweep found nothing - the pattern or module set drifted"
    missing = [
        f"{locale}:{key}"
        for key in sorted(keys)
        for locale in _LOCALES
        if tr(key, locale=locale, default=_SENTINEL) == _SENTINEL
    ]
    assert not missing, "flow keys missing from locale catalogues:\n" + "\n".join(missing)


def test_every_dynamic_flow_key_family_is_populated_in_all_locales() -> None:
    """A concatenated key prefix must name a family every language declares.

    The runtime half of such a key is not knowable statically, so this cannot
    assert every member resolves. It asserts the strongest claim that is
    checkable: an empty family in any language means every value routed through
    that prefix falls back to humanised English in that language.
    """
    _, prefixes = _referenced_flow_keys()
    empty = [
        f"{locale}:{prefix}*"
        for prefix in sorted(prefixes)
        for locale in _LOCALES
        if not any(key.startswith(prefix) for key in shard_keys(locale, prefix))
    ]
    assert not empty, "dynamic flow-key families with no members:\n" + "\n".join(empty)


def test_no_flows_leaf_is_a_self_referencing_placeholder() -> None:
    """A leaf whose value equals its own key is a scaffold echo, not a translation.

    The catalogue lookup treats key==value as a miss and falls back to
    humanised English, and the ``flows`` dynamic-root registration means
    no scaffold reconciles these leaves — this gate replaces the
    coverage that registration removed.
    """

    echoes: list[str] = []
    for locale in _LOCALES:
        for key, value in flatten_catalogue(shard_payload(locale, "flows.")):
            if key.startswith("flows.") and value == key:
                echoes.append(f"{locale}:{key}")
    assert not echoes, "self-referencing flows leaves (scaffold echoes):\n" + "\n".join(echoes)


class _Answers(BaseModel):
    model_config = STRICT_FROZEN_CONFIG


def _single_required_text_flow() -> FlowDefinition:
    ref = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="flows.progress.required")
    return FlowDefinition(
        id="loc-gate",
        title=ref,
        description=ref,
        sections=(
            FlowSection(
                id="s",
                title=ref,
                items=(FlowPage(id="p1", widget=FlowWidgetKind.TEXT, prompt=ref, answer_type=str),),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def test_engine_validation_failure_renders_localized() -> None:
    """A real invalid commit produces a verdict whose key resolves per locale.

    The assertion is structural: the verdict carries a message KEY, the
    key resolves in every catalogue (no sentinel fallback), and the
    non-English renderings differ from the English one — proving the
    rendered line tracks the locale rather than pinning any prose.
    """
    definition = _single_required_text_flow()
    state = start_flow(definition, mode=FlowMode.CREATE)
    state = answer(definition, state, "p1", "")
    verdicts = state.verdicts.get("p1")
    assert verdicts, "blank answer on a required page must record a failing verdict"
    key = verdicts[0].message_key
    assert key is not None
    rendered = {locale: tr(key, locale=locale, default=_SENTINEL, **verdicts[0].context) for locale in _LOCALES}
    assert _SENTINEL not in rendered.values(), f"verdict key {key!r} unresolved in a catalogue"
    assert rendered["es"] != rendered["en"], "Spanish rendering must not fall back to English"
    assert rendered["hu"] != rendered["en"], "Hungarian rendering must not fall back to English"
