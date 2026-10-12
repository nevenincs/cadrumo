"""Only the runtime's sign-in owner mints, extends or deletes a human receipt.

The receipt module's writers are reachable through one chain: the storage
adapter behind the login-session port, the application login service that
the runtime drives, and the runtime's own profile host and sweep. Profile
deletion removes the receipt through the custody transaction, which fences
the sign-in generation first. Any other production module naming a writer,
the receipt's keychain service or its file is a second owner and fails here.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PACKAGE_ROOT = Path(__file__).resolve().parents[5]
"""``src/cadrumo``: the production modules the gate reads live below it and the harness."""

_HARNESS_ROOT = _PACKAGE_ROOT.parent / "cadrumo_harness"
"""``src/cadrumo_harness``: the shipped MCP harness, which owns no receipt mutation."""

_RECEIPT = "adapters/persistence/storage/custody/acceleration_receipt.py"
_ADAPTER = "adapters/persistence/storage/profile_login_session.py"
_PORT = "application/user_profile/login_session_port.py"
_LOGIN = "application/user_profile/login_session.py"
_CUSTODY = "application/user_profile/custody_service.py"
_RUNTIME_LOGIN = "entrypoints/runtime/profile_login.py"
_RUNTIME_HOST = "entrypoints/runtime/profile_host.py"
_RUNTIME_SWEEP = "entrypoints/runtime/sign_in_sweep.py"
_TAXONOMY = "core/storage_taxonomy_locations.py"

_RECEIPT_WRITERS: Mapping[str, frozenset[str]] = {
    # The receipt module's own writers and the keychain material they hold.
    "_write_acceleration_receipt": frozenset({_RECEIPT}),
    "_store_acceleration_secret": frozenset({_RECEIPT}),
    "_delete_acceleration_secret": frozenset({_RECEIPT}),
    "_delete_keychain_entry": frozenset({_RECEIPT}),
    "_delete_profile_session": frozenset({_RECEIPT}),
    "_delete_refused_receipt": frozenset({_RECEIPT}),
    "_clear_captured_receipt": frozenset({_RECEIPT}),
    "PROFILE_SESSION_KEYCHAIN_SERVICE": frozenset({_RECEIPT}),
    # Its public mutators, reached only through the storage adapter.
    "mint_profile_session": frozenset({_RECEIPT, _ADAPTER}),
    "delete_profile_session": frozenset({_RECEIPT, _ADAPTER}),
    "resume_profile_session_with_key": frozenset({_RECEIPT, _ADAPTER}),
    "profile_session_path": frozenset({_RECEIPT, _ADAPTER}),
    # The runtime's lock-down and sweep revoke directly, generation first.
    "revoke_profile_sign_in": frozenset({_RECEIPT, _RUNTIME_HOST, _RUNTIME_SWEEP}),
    # The port the application login service drives.
    "mint_acceleration_receipt": frozenset({_PORT, _ADAPTER, _LOGIN}),
    "delete_acceleration_receipt": frozenset({_PORT, _ADAPTER, _LOGIN}),
    "resume_acceleration_receipt_with_key": frozenset({_PORT, _ADAPTER, _LOGIN}),
    # The login service's own doors, opened only by the runtime and custody.
    "persist_acceleration_receipt": frozenset({_LOGIN, _RUNTIME_LOGIN}),
    "resume_profile_candidate": frozenset({_LOGIN, _RUNTIME_LOGIN}),
    "remove_profile_session_acceleration_for_custody_delete": frozenset({_LOGIN, _CUSTODY}),
}
"""Each name that mutates a receipt, and the only modules that may name it."""

_RECEIPT_LITERALS: Mapping[str, frozenset[str]] = {
    "profile-session:v2": frozenset({_RECEIPT}),
    "session.v2.json": frozenset({_RECEIPT, _TAXONOMY}),
    "session.v2.retirement.json": frozenset({_RECEIPT, _TAXONOMY}),
}
"""Spelling the receipt's keychain service or file reaches it without a writer."""


@dataclass(frozen=True, slots=True)
class ReceiptOwnershipFinding:
    """One production module naming receipt mutation it does not own."""

    module: str
    line: int
    name: str


def _production_modules(root: Path, harness_root: Path | None = None) -> Iterator[tuple[str, Path]]:
    """Yield ``root`` modules by relative path and harness modules as ``cadrumo_harness/...``.

    No owner path starts with ``cadrumo_harness``, so every harness reference is a finding.
    """
    for base, prefix in ((root, ""), (harness_root, "cadrumo_harness/")):
        if base is None:
            continue
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(base)
            if "tests" in relative.parts or "__pycache__" in relative.parts:
                continue
            yield prefix + relative.as_posix(), path


def _named(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.alias):
        return node.name.rsplit(".", 1)[-1]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    return None


def receipt_ownership_findings(root: Path, harness_root: Path | None = None) -> list[ReceiptOwnershipFinding]:
    """Return every reference to receipt mutation outside its owners under the roots."""
    findings: list[ReceiptOwnershipFinding] = []
    for module, path in _production_modules(root, harness_root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = _named(node)
            owners = _RECEIPT_WRITERS.get(name) if name is not None else None
            if name is not None and owners is not None and module not in owners:
                findings.append(ReceiptOwnershipFinding(module, getattr(node, "lineno", 0), name))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for literal, literal_owners in _RECEIPT_LITERALS.items():
                    if literal in node.value and module not in literal_owners:
                        findings.append(ReceiptOwnershipFinding(module, node.lineno, literal))
    return findings


def test_no_production_module_outside_the_owner_mutates_a_receipt() -> None:
    assert (_PACKAGE_ROOT / _RECEIPT).is_file()
    assert any(_HARNESS_ROOT.rglob("*.py")), "the harness the gate scans must exist"
    assert receipt_ownership_findings(_PACKAGE_ROOT, _HARNESS_ROOT) == []


def test_every_declared_owner_still_names_what_it_owns() -> None:
    """A stale allowance would let a future second owner in unnoticed."""
    named: dict[str, set[str]] = {}
    for module, path in _production_modules(_PACKAGE_ROOT, _HARNESS_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            name = _named(node)
            if name is not None and name in _RECEIPT_WRITERS:
                named.setdefault(name, set()).add(module)
    for name, owners in _RECEIPT_WRITERS.items():
        assert named.get(name, set()) == set(owners), name


_PLANTED = {
    "mint": (
        "from ..storage.custody.acceleration_receipt import mint_profile_session\n"
        "def resume(**kwargs):\n    return mint_profile_session(**kwargs)\n",
        "mint_profile_session",
    ),
    "port_delete": (
        "def sign_out(port, root, profile):\n"
        "    port.delete_acceleration_receipt(storage_root=root, profile_id=profile)\n",
        "delete_acceleration_receipt",
    ),
    "keychain": (
        "import keyring\ndef forget(account):\n    keyring.delete_password('cadrumo:profile-session:v2', account)\n",
        "profile-session:v2",
    ),
    "file": (
        "from pathlib import Path\ndef forget(root: Path):\n    (root / 'session.v2.json').unlink()\n",
        "session.v2.json",
    ),
}


@pytest.mark.parametrize("planted", sorted(_PLANTED))
def test_the_gate_reports_a_planted_second_owner(tmp_path: Path, planted: str) -> None:
    source, name = _PLANTED[planted]
    owner = tmp_path / _RECEIPT
    owner.parent.mkdir(parents=True)
    owner.write_text("def mint_profile_session(**kwargs):\n    return None\n", encoding="utf-8")
    intruder = tmp_path / "entrypoints" / "cli" / "resume_shortcut.py"
    intruder.parent.mkdir(parents=True)
    intruder.write_text(source, encoding="utf-8")
    test_copy = tmp_path / "entrypoints" / "cli" / "tests" / "test_resume_shortcut.py"
    test_copy.parent.mkdir(parents=True)
    test_copy.write_text(source, encoding="utf-8")

    findings = receipt_ownership_findings(tmp_path)

    assert {(finding.module, finding.name) for finding in findings} == {("entrypoints/cli/resume_shortcut.py", name)}


@pytest.mark.parametrize("planted", sorted(_PLANTED))
def test_the_gate_reports_a_second_owner_planted_in_the_harness(tmp_path: Path, planted: str) -> None:
    source, name = _PLANTED[planted]
    package = tmp_path / "cadrumo"
    owner = package / _RECEIPT
    owner.parent.mkdir(parents=True)
    owner.write_text("def mint_profile_session(**kwargs):\n    return None\n", encoding="utf-8")
    harness = tmp_path / "cadrumo_harness"
    intruder = harness / "mcp" / "sign_in_shortcut.py"
    intruder.parent.mkdir(parents=True)
    intruder.write_text(source, encoding="utf-8")
    harness_test = harness / "mcp" / "tests" / "test_sign_in_shortcut.py"
    harness_test.parent.mkdir(parents=True)
    harness_test.write_text(source, encoding="utf-8")

    findings = receipt_ownership_findings(package, harness)

    assert {(finding.module, finding.name) for finding in findings} == {
        ("cadrumo_harness/mcp/sign_in_shortcut.py", name)
    }
    assert receipt_ownership_findings(package) == []
