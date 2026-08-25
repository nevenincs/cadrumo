"""The TUI may collect a secret the operator types; it must never paint one it mints.

Recovery-code enrollment and rotation generate a mnemonic that is displayed
exactly once, written past stdout to the controlling terminal device, and is
unrecoverable afterwards. A full-screen framework application cannot honour
that: a value composed into the widget tree is retained for the screen's
lifetime, repainted on every refresh, and reachable through screen export. So
the minting operations stay CLI-only, and this gate is what makes that
structural rather than a convention.

The gate is deliberately DIRECTIONAL. It fires on the generating entry points —
the ones that produce words the operator has never seen — and says nothing about
the collecting path, where the operator retypes a mnemonic they already hold
into an echo-suppressed field. Collecting is permitted; painting a minted secret
is not.

It is also a REACHABILITY gate, not a spelling gate. Asserting that no TUI
module contains the substring "mnemonic" would pass the moment somebody aliased
the import, and would fail on a docstring explaining the boundary. What is
asserted instead is that the generating callables are not reachable from the TUI
package's import graph at all.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from ....core import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The callables that MINT recovery words. Each returns only after the candidate
#: mnemonic has been shown, so a TUI module reaching any of them is a module
#: that either paints a minted secret or drives a terminal write out from under
#: the compositor. Both are the failure this gate exists to catch.
_MINTING_CALLABLES: tuple[tuple[str, str], ...] = (
    ("cadrumo.application.user_profile.custody_ports", "create_profile_recovery_enrollment_material"),
    ("cadrumo.application.user_profile", "mint_profile_creation_recovery"),
    # The primitive beneath both, and a SECOND reachable path: it is exported from
    # the storage facade in its own right, so a prohibition naming only
    # application-layer callables could be walked around by importing this
    # directly. The list this replaces did exactly that.
    ("cadrumo.adapters.persistence.storage", "generate_recovery_key"),
)

#: The collecting counterparts. They are NOT prohibited — they take a mnemonic
#: the operator already holds — and they are asserted importable here so the
#: gate cannot quietly become "no custody symbol is reachable", which would pass
#: vacuously if the whole custody facade were renamed away.
_COLLECTING_CALLABLES: tuple[tuple[str, str], ...] = (
    ("cadrumo.application.user_profile", "prove_profile_recovery_artifact"),
    ("cadrumo.application.user_profile", "restore_profile_from_recovery_artifact"),
)

_TUI_PACKAGE = Path(__file__).resolve().parents[3] / "entrypoints" / "tui"


def _tui_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in scan_directory(_TUI_PACKAGE, pattern="*.py", recursive=True)
        if path.name != "__init__.py" or path.parent == _TUI_PACKAGE
    )


def _imported_names(source: str) -> set[str]:
    """Return every name this module binds through an import, aliases resolved.

    Both ``from X import enroll_profile_recovery`` and
    ``from X import enroll_profile_recovery as _mint`` bind the minting callable,
    so the ORIGINAL name is what is collected: aliasing must not launder the
    reach past this gate.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


class TestTheMintingPathIsUnreachableFromTheTui:
    """No TUI module may reach a callable that generates recovery words."""

    def test_the_minting_callables_exist_and_are_named_correctly(self) -> None:
        """Anchor the gate's target set, so a rename cannot make it vacuous.

        A gate that pins symbol names passes trivially once those symbols are
        renamed. Resolving each one here means a rename reds this test rather
        than silently emptying the prohibition below.
        """
        for module_name, symbol in (*_MINTING_CALLABLES, *_COLLECTING_CALLABLES):
            module = importlib.import_module(module_name)
            assert callable(getattr(module, symbol)), f"{module_name}.{symbol}"

    def test_no_tui_module_imports_or_calls_a_minting_callable(self) -> None:
        modules = _tui_modules()
        assert modules, "the TUI package scan found no modules -- the gate would pass vacuously"
        prohibited = {symbol for _module, symbol in _MINTING_CALLABLES}
        offenders: list[str] = []
        for path in modules:
            reached = _imported_names(path.read_text(encoding="utf-8")) & prohibited
            offenders.extend(f"{path.name}:{symbol}" for symbol in sorted(reached))
        assert not offenders, (
            "a TUI module reaches a recovery-code MINTING callable. The candidate "
            "words are shown once on the controlling terminal device and cannot be "
            "shown again; a framework compositor retains, repaints and exports what "
            "it renders, so minting stays CLI-only. Offenders: " + ", ".join(offenders)
        )

    def test_the_scan_would_catch_a_reach_it_was_given(self) -> None:
        """Positive control: the detector fires on a module that does reach.

        Without this, a scan that silently parsed nothing — a changed package
        layout, an empty glob — would report a clean tree and read as proof.
        """
        source = "from cadrumo.application.user_profile.recovery_custody import mint_profile_creation_recovery\n"
        assert "mint_profile_creation_recovery" in _imported_names(source)
        aliased = "from cadrumo.application.user_profile.recovery_custody import mint_profile_creation_recovery as _mint\n"
        assert "mint_profile_creation_recovery" in _imported_names(aliased)
        attribute = "import cadrumo\ncadrumo.adapters.persistence.storage.generate_recovery_key()\n"
        assert "generate_recovery_key" in _imported_names(attribute)

        # The control must exercise names the prohibition ACTUALLY carries.
        # It once did not: the minting list was re-pointed at the live custody
        # symbols while this control kept probing the retired ones, so it went on
        # proving the parser works against names no rule named. A control
        # decoupled from the rule it controls is decoration.
        prohibited = {symbol for _module, symbol in _MINTING_CALLABLES}
        assert {"mint_profile_creation_recovery", "generate_recovery_key"} <= prohibited

    def test_the_scan_reads_the_real_tui_corpus(self) -> None:
        """Scope control: the scan resolves and parses the ACTUAL package.

        The prohibition above is a zero-result assertion, and a zero result is
        exactly what a broken instrument returns — a changed package layout, an
        unreadable file, a parse that yields nothing. Proving the scan finds a
        name it must find over the real files is what separates "no module
        reaches the minting path" from "the scan read nothing".
        """
        found: set[str] = set()
        for path in _tui_modules():
            found |= _imported_names(path.read_text(encoding="utf-8"))
        assert "push_screen" in found, "the scan did not see the TUI's own screen-push calls"
        assert "ModalScreen" in found, "the scan did not see the TUI's own modal primitive"

    def test_the_collecting_path_is_not_prohibited(self) -> None:
        """The ruling permits collection, so the gate must not forbid it.

        If this ever fails it means the prohibition has widened from "never
        paint a minted secret" to "never touch custody", which would block the
        verify and recover screens this decision explicitly allows.
        """
        prohibited = {symbol for _module, symbol in _MINTING_CALLABLES}
        collecting = {symbol for _module, symbol in _COLLECTING_CALLABLES}
        assert not (prohibited & collecting)
