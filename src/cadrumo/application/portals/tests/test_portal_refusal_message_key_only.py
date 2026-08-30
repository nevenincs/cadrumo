"""No portals refusal authors its own sentence; it renders as its registered key.

Two independent proofs, because either alone is escapable.

The runtime proof drives the real service into its refusal and asserts the
*absence* directly: ``str(exc)`` equals the registered locale key. This is the
only assertion shape that catches the defect, because an authored sentence
passed *alongside* a registered key hides from every key-and-context assertion --
resolution prefers the key -- while ``str(exc)`` prefers the positional argument
and carries the English into tracebacks, structured logs and every direct
rendering, in all four locales.

The structural proof walks every module in the package and refuses any
construction of a package-owned error that supplies message text at all:
positionally, through ``message=``, or by resolving a locale key to prose at the
raise site. It walks calls rather than raises, so a refusal that is *built and
returned* instead of raised is covered too. It also refuses a CLI command
spelled anywhere in the package's runtime strings: a recovery command is a
catalogue action resolved at the operator boundary, never prose a producer
carries.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....core.errors.error_codes import get_registered_error_code
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n import tr
from ....domain.portals.registry import PORTAL_REGISTRY
from ..service import PortalNotFoundError, PortalsService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PORTALS_PACKAGE = Path(__file__).resolve().parent.parent

#: The registered locale key for the portal-not-found refusal, spelled out
#: rather than read back from the registry the producer itself consults, so the
#: assertion is an independent claim and not true by construction.
_PORTAL_NOT_FOUND_MESSAGE_KEY = "errors.refused.refused_live_portal_not_found"

#: Every locale the catalogues ship.
_SHIPPED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")

#: Errors this package owns and constructs. Errors owned elsewhere are governed
#: by their own package's guard, so policing them from here would reach across a
#: boundary this module has no authority over.
_PACKAGE_OWNED_ERRORS: frozenset[str] = frozenset({"PortalNotFoundError"})

#: Callables that turn a locale key into prose. A producer that calls one of
#: these freezes whichever locale happened to be configured at failure time into
#: the refusal it hands on.
_RESOLVING_CALLABLES: frozenset[str] = frozenset({"tr", "gettext", "resolve_error_message"})


def _package_modules() -> tuple[Path, ...]:
    return scan_directory(_PORTALS_PACKAGE, pattern="*.py")


def _parsed_package_modules() -> tuple[tuple[Path, ast.Module], ...]:
    return tuple((path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))) for path in _package_modules())


class TestRosterAnchor:
    """The roster still names a live, registered error in this package."""

    def test_owned_errors_are_declared_in_the_package(self) -> None:
        declared: set[str] = set()
        for _path, tree in _parsed_package_modules():
            declared.update(node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        missing = sorted(_PACKAGE_OWNED_ERRORS - declared)
        assert missing == [], (
            f"{missing} are no longer declared in this package; the roster is stale "
            "and the structural proof would pass vacuously"
        )

    def test_owned_errors_are_registered_cadrumo_errors(self) -> None:
        assert issubclass(PortalNotFoundError, CadrumoError)
        assert get_registered_error_code(PortalNotFoundError).message_key == _PORTAL_NOT_FOUND_MESSAGE_KEY

    def test_the_package_actually_has_modules_to_walk(self) -> None:
        assert len(_package_modules()) >= 2


class TestRefusalRendersItsKey:
    """The live refusal path carries the key and machine facts, never a sentence."""

    def test_show_refusal_renders_exactly_the_key(self) -> None:
        # An empty registry guarantees a miss for any catalogued portal, so this
        # is the production refusal path and not a synthetic construction.
        service = PortalsService(registry={})
        portal = next(iter(PORTAL_REGISTRY))

        with pytest.raises(PortalNotFoundError) as raised:
            service.show(portal)

        assert str(raised.value) == _PORTAL_NOT_FOUND_MESSAGE_KEY

    def test_direct_construction_with_no_message_renders_the_key(self) -> None:
        error = PortalNotFoundError(portal="portal_that_does_not_exist")

        assert str(error) == _PORTAL_NOT_FOUND_MESSAGE_KEY

    def test_refusal_carries_the_rejected_identifier_as_a_fact(self) -> None:
        service = PortalsService(registry={})
        portal = next(iter(PORTAL_REGISTRY))

        with pytest.raises(PortalNotFoundError) as raised:
            service.show(portal)

        assert raised.value.context == {"portal": portal.value}
        assert raised.value.portal == portal.value
        assert portal.value not in str(raised.value)

    def test_translated_message_is_the_key_itself_not_resolved_prose(self) -> None:
        service = PortalsService(registry={})
        portal = next(iter(PORTAL_REGISTRY))

        with pytest.raises(PortalNotFoundError) as raised:
            service.show(portal)

        assert raised.value.translated_message == _PORTAL_NOT_FOUND_MESSAGE_KEY

    @pytest.mark.parametrize("locale", _SHIPPED_LOCALES)
    def test_key_resolves_to_real_prose_in_every_shipped_locale(self, locale: str) -> None:
        resolved = tr(_PORTAL_NOT_FOUND_MESSAGE_KEY, locale=locale)

        assert resolved != _PORTAL_NOT_FOUND_MESSAGE_KEY
        assert resolved.strip()


class TestNoProducerAuthorsText:
    """No construction of a package-owned error supplies message text."""

    def test_no_owned_error_is_constructed_with_message_text(self) -> None:
        offenders: list[str] = []
        for path, tree in _parsed_package_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if getattr(node.func, "id", None) not in _PACKAGE_OWNED_ERRORS:
                    continue
                if node.args:
                    offenders.append(f"{path.name}:{node.lineno}:positional")
                if any(keyword.arg == "message" for keyword in node.keywords):
                    offenders.append(f"{path.name}:{node.lineno}:message=")
        assert offenders == [], (
            "a refusal supplies its own message text, which becomes args[0] and "
            f"renders instead of the registered key: {offenders}"
        )

    def test_no_producer_resolves_a_locale_key_to_prose(self) -> None:
        offenders: list[str] = []
        for path, tree in _parsed_package_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if getattr(node.func, "id", None) in _RESOLVING_CALLABLES:
                    offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == [], (
            "a producer resolves a locale key to prose, freezing the failure-time "
            f"locale into the refusal it hands on: {offenders}"
        )

    def test_no_runtime_string_spells_a_cli_command(self) -> None:
        offenders: list[str] = []
        for path, tree in _parsed_package_modules():
            documentation = {id(node) for node in _docstring_nodes(tree)}
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if id(node) in documentation:
                    continue
                if "aeat " in node.value:
                    offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == [], (
            "a runtime string spells a CLI command; a recovery command is a catalogue "
            f"action resolved at the operator boundary, never producer prose: {offenders}"
        )


def _docstring_nodes(tree: ast.Module) -> tuple[ast.Constant, ...]:
    """Return the docstring constants of a module and every definition inside it."""
    collected: list[ast.Constant] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            collected.append(first.value)
    return tuple(collected)
