"""The live CLI registry is a key source, not something a text scan infers.

Every other discovery path in this package reads source text, which works only
while a key is written at the site that uses it. A spec table builds an
option's help key from the option name::

    _key(f"cli.app.modelo.work.{help_name or name}_help")

so no literal exists anywhere for it. Fifty-eight live command and option help
keys were in exactly that position: shipped in all four catalogues, resolved by
the CLI on every run, and indistinguishable to a text scan from a key nothing
uses.
"""

from __future__ import annotations

import pytest

from .._command_spec_scanner import scan_command_spec_keys
from .._paths import DOCS_SRC_DIR, HARNESS_SRC_DIR, LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager
from .test_parity import _committed_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _manager() -> LocaleManager:
    return LocaleManager(SRC_DIR, LOCALES_DIR, extra_src_dirs=(DOCS_SRC_DIR, HARNESS_SRC_DIR))


def test_the_registry_declares_keys_and_names_no_command_paths() -> None:
    """What the registry yields must be keys, not everything it can reach.

    A first version of the scanner walked every dotted string reachable from
    the registry and collected command paths (``app.diagnostics.errors``) and
    module names as though they were translation keys -- several hundred
    phantom required keys. Reading only the ``TranslationKey``-annotated fields
    is what makes the result a key set, so the roots are pinned: the registry
    declares CLI help and refusal copy, and nothing rooted at a command path.
    """
    keys = scan_command_spec_keys()

    assert len(keys) > 500, f"the registry declares {len(keys)} keys, so it was not read"
    assert {key.split(".")[0] for key in keys} == {"cli", "wizard"}, (
        "a root outside cli/wizard means something that is not a translation key was collected"
    )
    assert not [key for key in keys if " " in key or not key.strip()], "a key is a dotted token, never prose"


def test_every_key_the_live_registry_declares_reaches_the_codebase_key_set() -> None:
    """The registry's keys must be visible to parity, however they were built."""
    declared = scan_command_spec_keys()

    unseen = sorted(declared - _manager().get_codebase_keys())

    assert not unseen, (
        "the live CLI declares these keys but the codebase key set does not carry them, so each "
        f"is a shipped translation that looks unused: {unseen[:20]}"
    )


def test_every_key_the_live_registry_declares_is_translated() -> None:
    """A key the CLI resolves on every run must exist in every catalogue.

    This is the direction the text scanners cannot check for a built key: it
    asks the REGISTRY what the CLI will ask for, then asks each catalogue
    whether it can answer.
    """
    declared = scan_command_spec_keys()
    manager = _manager()

    missing: dict[str, list[str]] = {}
    for code, source in _committed_catalogues(manager).items():
        absent = sorted(declared - manager.get_yaml_keys(manager.load_locale(source)))
        if absent:
            missing[code] = absent[:20]

    assert not missing, f"the live CLI declares keys these catalogues cannot answer: {missing}"
