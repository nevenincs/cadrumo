"""The IVA-compensation casilla vocabulary has one declaration, not one per consumer.

The Modelo 303 compensation chain is read by the filed-history projection, by the
binding-prefill resolver, and by the domain carry-forward derivation policy. Each
used to declare its own private copy of the same tokens behind its own copy of the
same validating wrapper, so a casilla renamed on one side kept resolving on the
other and the surfaces could disagree about which value an operator's
compensation came from.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import ModuleType

import pytest

from .... import application, domain
from ....core import validated_casilla_id
from ....domain import iva_compensation as iva_compensation_policy
from .. import _iva_compensation_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SHARED_M303_CONSTANTS = (
    "M303_RESULTADO_CASILLA",
    "M303_GENERADA_CASILLA",
    "M303_POSTERIOR_CASILLA",
    "M303_DISPONIBLE_CASILLA",
    "M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA",
    "M303_COMPENSACION_APLICADA_CASILLA",
    "M303_RESULTADO_FINAL_CASILLA",
)

#: The packages swept for modules that name a compensation casilla token. Both
#: layers that model the compensation chain, production modules only: test
#: support legitimately types casilla ids into fixtures.
_SWEPT_PACKAGES = (application, domain)


def _authority_by_token() -> dict[str, str]:
    tokens: dict[str, str] = {}
    for name in _iva_compensation_casillas.__all__:
        value = getattr(_iva_compensation_casillas, name)
        if isinstance(value, str):
            tokens[value] = value
    return tokens


def _named_tokens(module: ModuleType, *, authority: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Every authority token the module's namespace holds, and where it holds it.

    A token reached through a module-level tuple or frozenset counts. The
    registry's binding validator held four twins inside one such tuple, and a
    scan looking only at string-valued attributes reported that module as naming
    nothing -- the shape hid the twins from the check that existed to find them.
    """
    found: list[tuple[str, str]] = []
    for attribute, value in vars(module).items():
        if isinstance(value, str):
            if value in authority:
                found.append((attribute, value))
            continue
        if isinstance(value, (tuple, list, frozenset, set)):
            found.extend(
                (f"{attribute}[{index}]", item)
                for index, item in enumerate(value)
                if isinstance(item, str) and item in authority
            )
    return tuple(found)


def _module_name_for(source: Path, *, package: ModuleType) -> str:
    root = Path(package.__file__).parent  # ty: ignore[invalid-argument-type]
    relative = source.relative_to(root).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join((package.__name__, *parts))


def _discover_token_naming_modules() -> tuple[ModuleType, ...]:
    """Discover every production module that names a compensation casilla token.

    Discovery is an AST sweep for the two ways a module can name a token -- a
    string literal equal to one, or an import of an authority constant -- and it
    replaces a hand-listed tuple of subjects. The list this supersedes named
    three modules while nine twin declarations stood outside it, one set of them
    on the live local filing path; a gate whose subjects are enumerated cannot
    see a tenth twin appear in a module nobody thought to add.

    The sweep parses rather than imports, so a module is discovered whether or
    not importing it is cheap, and only the discovered few are then imported for
    the identity verdict.
    """
    # A bare-numeric token is excluded from LITERAL discovery: "71" collides with
    # any unrelated module that happens to contain that string, and because
    # CPython interns it the identity verdict could not discriminate its twin
    # anyway. Including it manufactures subjects the check cannot rule on. It
    # stays in the authority set, so a module discovered for another reason is
    # still checked against it.
    literal_tokens = {token for token in _authority_by_token() if not token.isdigit()}
    # Both declaring authorities, because the vocabulary is declared across two
    # layers: the domain policy owns the tokens it decides figures from, and the
    # calculations authority binds those rather than re-typing them. A sweep that
    # knew only the calculations names missed every consumer that imports the
    # domain constants directly -- including the registry's binding validator.
    authority_names = {
        *_iva_compensation_casillas.__all__,
        *(name for name in dir(iva_compensation_policy) if name.startswith("M303_COMPENSATION_")),
    }
    discovered: dict[str, ModuleType] = {}
    for package in _SWEPT_PACKAGES:
        root = Path(package.__file__).parent
        for source in sorted(root.rglob("*.py")):
            if "tests" in source.parts:
                continue
            tree = ast.parse(source.read_text(encoding="utf-8"))
            literal = any(
                isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in literal_tokens
                for node in ast.walk(tree)
            )
            # Module-level imports only. A function-local import binds the
            # authority's own object when the call runs and cannot be a twin, and
            # it leaves nothing in the module namespace for the verdict to read.
            imported = any(
                isinstance(node, ast.ImportFrom) and any(alias.name in authority_names for alias in node.names)
                for node in tree.body
            )
            if not (literal or imported):
                continue
            name = _module_name_for(source, package=package)
            discovered[name] = importlib.import_module(name)
    return tuple(discovered.values())


_TOKEN_NAMING_MODULES = _discover_token_naming_modules()


def test_the_sweep_finds_the_declaring_authority_itself() -> None:
    """Discovery is non-vacuous, proven by the one module it cannot fail to find.

    The authority declares the vocabulary as literals, so a sweep that returns
    it is reaching real source. A sweep that silently matched nothing -- a wrong
    package root, a changed layout -- would otherwise leave every parametrised
    identity check with no cases and the gate green over nine twins.
    """
    assert _authority_by_token(), "the authority exports no tokens, so every check below is vacuous"
    assert _iva_compensation_casillas in _TOKEN_NAMING_MODULES


@pytest.mark.parametrize("module", _TOKEN_NAMING_MODULES, ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_no_module_declares_a_second_object_for_an_authority_token(module: ModuleType) -> None:
    """A module naming a compensation casilla holds the authority's object, not a twin.

    Identity, not equality: two independently declared constants comparing equal
    today is exactly the state that drifted, because a rename applies to one and
    silently leaves the other resolving. The consequence is not cosmetic -- the
    local filing path re-stamps the end-of-period available casilla for a
    refunded period, so a module resolving a stale literal stops finding the row
    it must correct and a refunded period carries its full generated credit into
    the next quarter.

    This checks the drift property rather than an inventory, in both directions
    now. An inventory of which module imports which constant asserts something
    the code is free to change for good reasons -- a consumer that stops reading
    a casilla directly because a policy now derives it for them -- and it went
    stale for exactly that reason. An inventory of which modules to WATCH has
    the same defect one level up, and had it: it named three while the domain
    policy held its own twin of four tokens and three further modules held nine
    between them. The subjects are now discovered, so a module that does not
    name a token is absent rather than passing, and a new one is watched the
    moment it names one.

    One blind spot, stated rather than papered over: CPython interns short
    string literals, so a twin declaration of the bare-numeric token
    ``M303_RESULTADO_FINAL_CASILLA`` ("71") is the SAME object as the
    authority's and passes this check. Discovery does not close that -- it finds
    such a module, and the identity verdict then cannot discriminate its twin.
    Only the dotted registry ids are covered.
    """
    authority = _authority_by_token()
    named = _named_tokens(module, authority=authority)

    assert named, "the module names no compensation casilla, so this parametrisation is vacuous"
    for attribute, value in named:
        assert value is authority[value], f"{module.__name__}.{attribute} is a second object for {value!r}"


@pytest.mark.parametrize("name", (*_SHARED_M303_CONSTANTS, "M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA"))
def test_every_declared_constant_is_a_validated_casilla_id(name: str) -> None:
    """Each constant passes the canonical casilla-id validator."""
    value = getattr(_iva_compensation_casillas, name)

    assert validated_casilla_id(value, surface="test") == value


@pytest.mark.parametrize("malformed", ["", "   ", "x" * 200])
def test_malformed_tokens_are_refused_at_declaration(malformed: str) -> None:
    """A token that is not a casilla id fails loudly rather than resolving to nothing.

    The declaration helper runs at import time, so a malformed constant can
    never reach a compensation calculation.
    """
    with pytest.raises(RuntimeError):
        _iva_compensation_casillas.iva_compensation_casilla_id(malformed)


def test_authority_exports_exactly_the_shared_vocabulary() -> None:
    """The module's public surface is the compensation vocabulary and its validator."""
    assert set(_iva_compensation_casillas.__all__) == {
        *_SHARED_M303_CONSTANTS,
        "M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA",
        "M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA",
        "iva_compensation_casilla_id",
    }
