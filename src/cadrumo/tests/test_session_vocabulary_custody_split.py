"""Vocabulary gate: the two custody classes may not borrow each other's noun.

Two unrelated artefacts were both called "session". The profile acceleration
receipt is a keyring key plus a keystore sidecar record OUTSIDE the encrypted
store, wrapping an already-unlocked DEK, revocable with no unlocked profile.
The AEAT authority session is an encrypted row INSIDE the bucket, revocable
only with the key. One word for both let a correct measurement of one be
carried onto the other, and the resulting premise survived three readers.

The collision was never in the qualified names -- ``PersistedProfileSession``
and ``PersistedBrowserSession`` were always distinct. It was in the BARE
phrase ``persisted session``, which both sides used, and in module filenames
that carried no owner at all.

This gate is deliberately bidirectional. A one-directional rule would let the
collision reform from the other side, which is how it started: it is not that
one package misbehaved, but that neither package's vocabulary excluded the
other's. So a bare session noun is refused under the acceleration-receipt
paths, and receipt naming is refused under the authority paths.

It gates on the property, never on a tally: there is no expected count to
update, so a new module inherits the rule instead of a constant going stale.
Exemptions are keyed by ``(path suffix, symbol)`` and each must state why.
"""

from __future__ import annotations

import ast
import re

import pytest

from ._inventory import production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

ACCELERATION_RECEIPT_PATHS: tuple[str, ...] = (
    "adapters/persistence/storage/custody/_acceleration_receipt.py",
    "application/user_profile/login_session.py",
)
"""Modules owning the keystore-resident acceleration receipt."""

AUTHORITY_SESSION_PATHS: tuple[str, ...] = (
    "adapters/outbound/aeat/auth/session_store.py",
    "adapters/outbound/aeat/auth/_session_probe.py",
    "application/auth/_sessions.py",
)
"""Modules owning the bucket-resident AEAT authority session."""

_BARE_SESSION = re.compile(r"(?:^|_)sessions?(?:_|$)|(?<![A-Za-z])Sessions?(?![a-z])", re.ASCII)
"""A session noun carrying no owner word to tell the two artefacts apart."""

_RECEIPT = re.compile(r"(?:^|_)receipts?(?:_|$)|Receipts?", re.ASCII)
"""Receipt vocabulary, which belongs to the acceleration artefact alone."""

_QUALIFIERS: tuple[str, ...] = ("profile", "bucket", "auth", "browser", "aeat", "provider")
"""Owner words that make a session noun unambiguous on sight."""

RECEIPT_SIDE_EXEMPTIONS: dict[tuple[str, str], str] = {
    (
        "adapters/persistence/storage/custody/_acceleration_receipt.py",
        "PROFILE_SESSION_KEYCHAIN_SERVICE",
    ): (
        "OS-credential-store wire identifier. Renaming it orphans entries outside the "
        "storage root that nothing can reap, and deleting under the old token first "
        "would be a migration path. The token lags the concept name by decision."
    ),
    (
        "adapters/persistence/storage/custody/_acceleration_receipt.py",
        "PROFILE_SESSION_SCHEMA_VERSION",
    ): "Versions the wire record the keychain service addresses; moves only with that token.",
}
"""Bare session nouns allowed on the receipt side, each with its reason."""

AUTHORITY_SIDE_EXEMPTIONS: dict[tuple[str, str], str] = {}
"""Receipt nouns allowed on the authority side, each with its reason."""


def _defined_names(tree: ast.AST) -> tuple[str, ...]:
    """Return the module-level named surface: top-level definitions and constants.

    Scoped to module level on purpose. A local variable cannot be mistaken for
    another package's concept because it is never read from outside its own
    function body, and a pydantic field name is wire format bound into the
    record's AEAD associated data rather than a name a reader navigates by.
    The collision this gate exists to refuse lived in what other modules
    import and what a reader sees in a traceback.
    """
    if not isinstance(tree, ast.Module):
        return ()
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, ast.Assign):
            names.extend(target.id for target in node.targets if isinstance(target, ast.Name))
    return tuple(names)


def _matching_modules(paths: tuple[str, ...]) -> tuple[tuple[str, ast.AST], ...]:
    """Return ``(suffix, AST)`` for every declared module found in the tree."""
    found: list[tuple[str, ast.AST]] = []
    for path, tree in production_ast_items():
        posix = path.as_posix()
        for suffix in paths:
            if posix.endswith(suffix):
                found.append((suffix, tree))
    return tuple(found)


@pytest.mark.parametrize("declared", ACCELERATION_RECEIPT_PATHS + AUTHORITY_SESSION_PATHS)
def test_every_declared_custody_module_exists(declared: str) -> None:
    """Refuse a rename that leaves this gate pointing at nothing.

    Without this, moving a module makes the gate pass vacuously rather than
    fail, which is the exact failure mode the vocabulary rule exists to stop.
    """
    assert _matching_modules((declared,)), f"{declared} no longer exists; repoint this gate with the rename"


def test_the_acceleration_receipt_side_uses_no_bare_session_noun() -> None:
    """The receipt is not a session, so its own names must not say otherwise."""
    violations: list[str] = []
    for suffix, tree in _matching_modules(ACCELERATION_RECEIPT_PATHS):
        for name in _defined_names(tree):
            if (suffix, name) in RECEIPT_SIDE_EXEMPTIONS:
                continue
            lowered = name.lower()
            if _BARE_SESSION.search(name) and not any(q in lowered for q in _QUALIFIERS):
                violations.append(f"{suffix}::{name}")
    assert not violations, (
        "bare session nouns on the acceleration-receipt side, where 'session' means the "
        f"live bucket session and nothing else: {sorted(violations)}"
    )


def test_the_authority_session_side_uses_no_receipt_noun() -> None:
    """Receipt vocabulary names the keystore artefact, not the authority session."""
    violations: list[str] = []
    for suffix, tree in _matching_modules(AUTHORITY_SESSION_PATHS):
        for name in _defined_names(tree):
            if (suffix, name) in AUTHORITY_SIDE_EXEMPTIONS:
                continue
            if _RECEIPT.search(name):
                violations.append(f"{suffix}::{name}")
    assert not violations, (
        "receipt nouns on the authority-session side, which names the bucket-resident "
        f"encrypted row: {sorted(violations)}"
    )


def test_every_exemption_states_a_reason() -> None:
    """An allowlist entry without a stated reason is an unreviewed exception."""
    for key, reason in (*RECEIPT_SIDE_EXEMPTIONS.items(), *AUTHORITY_SIDE_EXEMPTIONS.items()):
        assert reason.strip(), f"exemption {key} carries no reason"


@pytest.mark.parametrize(
    ("suffix", "symbol"),
    tuple(RECEIPT_SIDE_EXEMPTIONS) + tuple(AUTHORITY_SIDE_EXEMPTIONS),
)
def test_every_exemption_still_names_a_real_symbol(suffix: str, symbol: str) -> None:
    """A stale exemption silently widens the gate, so it must fail instead."""
    defined = {name for declared, tree in _matching_modules((suffix,)) for name in _defined_names(tree)}
    assert symbol in defined, f"exempted symbol {suffix}::{symbol} no longer exists; drop the entry"
