"""No portal-registry error builds its own sentence; each renders as its key.

This module guards the hardest shape of the authored-prose defect: prose that is
neither passed positionally nor passed as ``message=`` at a call site, but
assembled *inside* the exception class's own ``__init__``. Every call site then
reads clean -- ``UnknownPortalError(portal)`` supplies only an identifier -- while
``exc.args`` still carries an English sentence into tracebacks, structured logs
and every boundary that renders the exception directly, in all four locales. No
raise-site scan can see it, so switching those call sites to keyword form would
clear a scanner while leaving the sentence exactly where it was.

Two independent proofs, because either alone is escapable.

The runtime proof constructs each class the way production does -- with no
message argument of any kind -- and asserts the *absence* directly: ``str(exc)``
equals the registered locale key, and the rejected identifier reaches the caller
as a machine fact rather than as prose.

The structural proof parses the error module and refuses, in any ``__init__``
defined there, a positional argument to ``super().__init__`` or an interpolated
string anywhere in the module. That is the exact construction that produced the
defect, and it is refused by shape rather than by matching a known sentence.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.errors.error_codes import get_registered_error_code
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n import tr
from ..errors import (
    PortalIntegrityError,
    PortalRegistryError,
    PortalValidationError,
    UnknownPortalError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ERRORS_MODULE = Path(__file__).resolve().parent.parent / "errors.py"

#: The registered locale key for the unknown-portal refusal, written out rather
#: than read back from the registry the constructor itself consults. Deriving it
#: from that registry would make the assertion true by construction; spelled
#: here, it is an independent claim about what the operator-facing surface is.
_UNKNOWN_PORTAL_MESSAGE_KEY = "errors.error.error_portals_unknown_portal"

#: Every locale the catalogues ship. The key is only an improvement over an
#: English sentence if each of these resolves it to real prose.
_SHIPPED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")

#: Classes this module's structural roster covers. Named explicitly so a rename
#: cannot silently shrink the guard's reach and let it pass vacuously.
_PORTAL_ERROR_CLASSES: tuple[type[CadrumoError], ...] = (
    PortalRegistryError,
    UnknownPortalError,
    PortalIntegrityError,
    PortalValidationError,
)


def _errors_module_tree() -> ast.Module:
    return ast.parse(_ERRORS_MODULE.read_text(encoding="utf-8"), filename=str(_ERRORS_MODULE))


class TestRosterAnchor:
    """The roster still names live classes in the module it claims to guard."""

    def test_every_rostered_class_is_declared_in_the_guarded_module(self) -> None:
        declared = {node.name for node in ast.walk(_errors_module_tree()) if isinstance(node, ast.ClassDef)}
        for error_class in _PORTAL_ERROR_CLASSES:
            assert error_class.__name__ in declared, (
                f"{error_class.__name__} is no longer declared in {_ERRORS_MODULE.name}; "
                "the roster is stale and this guard would pass vacuously"
            )

    def test_every_rostered_class_is_a_registered_cadrumo_error(self) -> None:
        for error_class in _PORTAL_ERROR_CLASSES:
            assert issubclass(error_class, CadrumoError)
            assert get_registered_error_code(error_class).message_key


class TestUnknownPortalRendersItsKey:
    """The class carries a key and a machine fact, never a built sentence."""

    def test_direct_construction_with_no_message_renders_the_key(self) -> None:
        # Production's only construction shape: the offending identifier and
        # nothing else. Before migration this rendered "unknown portal: '...'".
        error = UnknownPortalError("portal_that_does_not_exist")

        assert str(error) == _UNKNOWN_PORTAL_MESSAGE_KEY

    def test_registered_code_agrees_with_the_rendered_key(self) -> None:
        # Pins the spelled-out key above to the central registry declaration, so
        # the two cannot drift apart without one of these two tests failing.
        assert get_registered_error_code(UnknownPortalError).message_key == _UNKNOWN_PORTAL_MESSAGE_KEY

    def test_rejected_identifier_travels_as_a_fact_not_as_prose(self) -> None:
        error = UnknownPortalError("portal_that_does_not_exist")

        assert error.context == {"portal": "portal_that_does_not_exist", "portal_registered": False}
        assert error.portal == "portal_that_does_not_exist"
        assert "portal_that_does_not_exist" not in str(error)

    def test_translated_message_is_the_key_itself_not_resolved_prose(self) -> None:
        # Resolving at raise time would freeze whichever locale happened to be
        # configured when the failure occurred into the persisted refusal.
        error = UnknownPortalError("portal_that_does_not_exist")

        assert error.translated_message == _UNKNOWN_PORTAL_MESSAGE_KEY

    @pytest.mark.parametrize("locale", _SHIPPED_LOCALES)
    def test_key_resolves_to_real_prose_in_every_shipped_locale(self, locale: str) -> None:
        resolved = tr(_UNKNOWN_PORTAL_MESSAGE_KEY, locale=locale)

        assert resolved != _UNKNOWN_PORTAL_MESSAGE_KEY
        assert resolved.strip()


class TestNoConstructorBuildsProse:
    """No ``__init__`` in the module can assemble operator-facing text."""

    def test_no_init_passes_a_positional_argument_to_super(self) -> None:
        offenders: list[str] = []
        for class_node in ast.walk(_errors_module_tree()):
            if not isinstance(class_node, ast.ClassDef):
                continue
            for node in ast.walk(class_node):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                if not (isinstance(function, ast.Attribute) and function.attr == "__init__"):
                    continue
                is_super = isinstance(function.value, ast.Call) and getattr(function.value.func, "id", None) == "super"
                if is_super and node.args:
                    offenders.append(f"{class_node.name}:{node.lineno}")
        assert offenders == [], (
            "an exception constructor passes a positional argument to super().__init__, "
            f"which becomes args[0] and renders instead of the registered key: {offenders}"
        )

    def test_module_interpolates_no_string(self) -> None:
        interpolations = [node.lineno for node in ast.walk(_errors_module_tree()) if isinstance(node, ast.JoinedStr)]
        assert interpolations == [], (
            "an interpolated string in the error module is how constructor-built prose "
            f"re-enters; lines: {interpolations}"
        )

    def test_module_names_no_operator_command(self) -> None:
        commands = [
            node.value
            for node in ast.walk(_errors_module_tree())
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "aeat " in node.value
        ]
        assert commands == [], f"an error module must not spell a CLI command: {commands}"
