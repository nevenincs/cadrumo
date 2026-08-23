"""Every key the source WRAPS must be a key the scanner FINDS.

The CLI command-spec tables never write a bare translation key. Every command,
group, option and argument help string is declared as
``help_key=TranslationKey("cli...")``, ``_key("cli...")``, or the same wrapper passed
positionally into a local spec factory. The scanner used to read only bare
``ast.Constant`` values, so it saw none of them: 690 live keys were reported as
catalogue-only "extra" entries, indistinguishable from dead data. The obvious
remedy for a long extra list is to strip it, and doing that would have deleted the
entire ledger and live CLI help surface while every gate stayed green.

WHY A DEDICATED GATE RATHER THAN TRUSTING THE PARITY COUNT. The parity check reports
a NUMBER. A scanner that goes blind to a wrapper form makes that number go UP, which
reads exactly like ordinary catalogue drift, and the recorded fix for drift is
deletion. Nothing in the parity check distinguishes "the catalogue has keys nobody
uses" from "the scanner stopped seeing how they are used" -- and those two have
opposite remedies. This module states the second directly.

WHAT IS PINNED. Not a count, and not a list of keys. The property: for the wrapper
forms this repository actually uses, a key written in the source is a key the scanner
returns. It is measured against the real tree, so a new spec table or a renamed
factory is covered the day it lands.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .._ast_scanner import scan_source_tree
from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: ``TranslationKey("x")`` / ``_key("x")`` written anywhere in the source. Deliberately
#: a text match rather than an AST walk: this module must fail when the SCANNER's own
#: AST reading misses a form, so re-using that reading to build the expectation would
#: make the comparison agree with itself no matter how blind it became.
_WRAPPED = re.compile(r"""\b(?:TranslationKey|_key)\(\s*["']([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)["']\s*\)""")

#: ``help_key="x"`` written without a wrapper.
_HELP_KWARG = re.compile(r"""\bhelp_key\s*=\s*["']([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)["']""")

#: A bare dotted literal on its own line inside a command-spec table. The spec
#: factories take the key POSITIONALLY and often unwrapped -- ``_leaf("check",
#: "cli.app.modelo.audit.check_help", ...)`` -- which no wrapper rule can see.
#: Matched only inside ``*_command_specs.py`` so an ordinary dotted string
#: elsewhere in the tree is never demanded of the scanner.
_BARE_POSITIONAL = re.compile(r"""^\s+["']([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)["'],\s*$""", re.MULTILINE)

#: Roots the catalogue actually owns. A wrapper around a dotted string outside these --
#: the AEAT session store's own ``_key(path)`` helper is the live example -- is not a
#: translation key and must not be demanded of the scanner.
_CATALOGUE_ROOTS = frozenset(
    {"application", "cli", "docs", "errors", "flows", "modelo", "profile", "sheets", "topic", "wizard"},
)


#: Roots a BARE positional literal in a spec table may carry. Narrower than
#: :data:`_CATALOGUE_ROOTS` on purpose: spec tables also pass command paths and handler
#: ids positionally -- ``"modelo.work.amend"``, ``"modelo.history"`` -- which are dotted,
#: are rooted in a namespace the catalogue does own (via ``modelo.schema.*``), and are
#: not translation keys at all. Demanding those of the scanner would invent four phantom
#: keys, which is the same defect as missing a real one wearing the opposite sign.
_BARE_POSITIONAL_ROOTS = frozenset({"cli", "docs", "flows"})


def _written_keys() -> dict[str, list[str]]:
    """``key -> the files that write it in a wrapper or help_key form``."""
    written: dict[str, list[str]] = {}
    for path in sorted(Path(SRC_DIR).rglob("*.py")):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, roots in (
            (_WRAPPED, _CATALOGUE_ROOTS),
            (_HELP_KWARG, _CATALOGUE_ROOTS),
            (_BARE_POSITIONAL, _BARE_POSITIONAL_ROOTS if path.name.endswith("_command_specs.py") else frozenset()),
        ):
            for key in pattern.findall(text):
                if key.split(".", 1)[0] in roots:
                    written.setdefault(key, []).append(path.name)
    return written


def test_the_source_actually_uses_the_wrapper_forms() -> None:
    """Guard against a vacuous pass if the CLI stops writing keys this way.

    If the spec tables were rewritten to pass bare strings, the assertion below would
    hold over an empty set and silently stop protecting anything. Kept as its own
    test so that outcome is reported as the cause rather than as success.
    """
    written = _written_keys()
    assert len(written) > 100, (
        "the source barely uses the wrapped key forms this module exists to protect "
        f"({len(written)} found); re-ground it before trusting it"
    )


def test_every_wrapped_key_is_discovered_by_the_scanner() -> None:
    """The scanner must return every key the source writes in a wrapper form."""
    written = _written_keys()
    found = scan_source_tree(Path(SRC_DIR))

    missed = sorted(key for key in written if key not in found)
    assert not missed, (
        "the scanner does not see these keys even though the source writes them, so they "
        "will be reported as unused catalogue entries and are one strip away from deletion "
        f"({len(missed)} key(s), first five with the file that writes them): "
        + "; ".join(f"{key} [{written[key][0]}]" for key in missed[:5])
    )
