"""The TUI shows a recovery code the application hands it; it never mints one itself.

Recovery enrolment generates a code that is shown exactly once and is
unrecoverable afterwards. Who generates it matters: the application's
enrolment door mints the code, bounds its lifetime, wipes it, and installs
the wrapper only after the operator has proved possession by typing the
code back. A TUI module that reached the minting primitives directly could
generate a code outside that lifecycle — retained for a screen's lifetime,
repainted on every refresh, reachable through screen export, and never
proven before something is installed. So minting stays behind the
application door, and this gate is what makes that structural rather than
a convention.

The gate is deliberately DIRECTIONAL. It fires on the generating primitives —
the callables that produce a code the operator has never seen — and says
nothing about the sanctioned doors: the enrolling door, which hands the
minted code to a handover the TUI implements and requires exact proof back,
and the collecting door, where the operator retypes a code they already
hold. Enrolling and collecting are permitted; minting is not.

It is also a REACHABILITY gate, not a spelling gate. Asserting that no TUI
module contains the substring "recovery" would fail on the offer screen and
on this docstring, and would pass the moment somebody aliased the import.
What is asserted instead is that the generating primitives are not reachable
from the TUI package's import graph at all.
"""

from __future__ import annotations

import ast
import importlib
from importlib.util import resolve_name
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The primitives that MINT a recovery code. A TUI module reaching either of
#: them holds a code the application never bounded, so it is a module that
#: could paint a secret without the proof-of-possession step that guards
#: installation. Both are the failure this gate exists to catch.
_MINTING_CALLABLES: tuple[tuple[str, str], ...] = (
    ("....application.user_profile.custody_ports", "create_profile_recovery_enrollment_material"),
    # The primitive beneath the application port is a second reachable path:
    # naming only the application-layer callable would permit a direct
    # primitive import. The prohibition scans for the symbol name from its
    # defining module.
    ("....adapters.persistence.storage.recovery_key", "generate_recovery_key"),
)

#: The sanctioned doors. They are NOT prohibited — enrolment hands the minted
#: code to a handover and installs nothing until the exact code comes back,
#: and reset takes a code the operator already holds — and they are asserted
#: importable here so the gate cannot quietly become "no custody symbol is
#: reachable", which would pass vacuously if the whole custody facade were
#: renamed away.
_SANCTIONED_DOORS: tuple[tuple[str, str], ...] = (
    ("....application.user_profile.recovery_custody", "enroll_profile_recovery"),
    ("....application.user_profile.recovery_custody", "reset_profile_passphrase_with_recovery"),
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

    Both ``from X import generate_recovery_key`` and
    ``from X import generate_recovery_key as _mint`` bind the minting
    primitive, so the ORIGINAL name is what is collected: aliasing must not
    launder the reach past this gate.
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
    """No TUI module may reach a primitive that generates a recovery code."""

    def test_the_minting_callables_exist_and_are_named_correctly(self) -> None:
        """Anchor the gate's target set, so a rename cannot make it vacuous.

        A gate that pins symbol names passes trivially once those symbols are
        renamed. Resolving each one here means a rename reds this test rather
        than silently emptying the prohibition below.
        """
        for module_name, symbol in (*_MINTING_CALLABLES, *_SANCTIONED_DOORS):
            module = importlib.import_module(module_name, package=__package__)
            resolved_name = resolve_name(module_name, __package__)
            assert callable(getattr(module, symbol)), f"{resolved_name}.{symbol}"

    def test_no_tui_module_imports_or_calls_a_minting_callable(self) -> None:
        modules = _tui_modules()
        assert modules, "the TUI package scan found no modules -- the gate would pass vacuously"
        prohibited = {symbol for _module, symbol in _MINTING_CALLABLES}
        offenders: list[str] = []
        for path in modules:
            reached = _imported_names(path.read_text(encoding="utf-8")) & prohibited
            offenders.extend(f"{path.name}:{symbol}" for symbol in sorted(reached))
        assert not offenders, (
            "a TUI module reaches a recovery-code MINTING primitive. A code minted "
            "outside the application's enrolment door has no bounded lifetime and no "
            "proof-of-possession step before installation; a framework compositor "
            "retains, repaints and exports what it renders, so minting stays behind "
            "the application door. Offenders: " + ", ".join(offenders)
        )

    def test_the_scan_would_catch_a_reach_it_was_given(self) -> None:
        """Positive control: the detector fires on a module that does reach.

        Without this, a scan that silently parsed nothing — a changed package
        layout, an empty glob — would report a clean tree and read as proof.
        """
        source = "from cadrumo.adapters.persistence.storage.recovery_key import generate_recovery_key\n"
        assert "generate_recovery_key" in _imported_names(source)
        aliased = "from cadrumo.adapters.persistence.storage.recovery_key import generate_recovery_key as _mint\n"
        assert "generate_recovery_key" in _imported_names(aliased)
        attribute = (
            "import cadrumo\n"
            "cadrumo.application.user_profile.custody_ports.create_profile_recovery_enrollment_material()\n"
        )
        assert "create_profile_recovery_enrollment_material" in _imported_names(attribute)

        # The control must exercise names the prohibition ACTUALLY carries.
        # It once did not: the minting list was re-pointed at the live custody
        # symbols while this control kept probing the retired ones, so it went on
        # proving the parser works against names no rule named. A control
        # decoupled from the rule it controls is decoration.
        prohibited = {symbol for _module, symbol in _MINTING_CALLABLES}
        assert {"create_profile_recovery_enrollment_material", "generate_recovery_key"} <= prohibited

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
        assert "enroll_profile_recovery" in found, "the scan did not see the registration screen's enrolment door"

    def test_the_sanctioned_doors_are_not_prohibited(self) -> None:
        """The ruling permits enrolling and collecting, so the gate must not forbid them.

        If this ever fails it means the prohibition has widened from "never
        mint a code" to "never touch custody", which would block the offer,
        code and reset screens this boundary explicitly allows.
        """
        prohibited = {symbol for _module, symbol in _MINTING_CALLABLES}
        sanctioned = {symbol for _module, symbol in _SANCTIONED_DOORS}
        assert not (prohibited & sanctioned)
