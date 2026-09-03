"""Reusable recoverable cutover for a verified, narrow casilla-tree rewrite.

The caller supplies an already-rendered set of exact declaration replacements
and a verifier for the staged/live tree.  This module owns no legal or modelo
selection policy; it only makes a complete, link-free casilla tree replaceable
without exposing a partial set of declarations.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError


def publish_verified_casilla_tree(
    *,
    casillas_root: Path,
    rendered: Mapping[Path, str],
    verifier: Callable[[Path], None],
    journal_name: str,
    stage_prefix: str,
    backup_prefix: str,
    replace_tree: Callable[[Path, Path], None] | None = None,
) -> None:
    """Stage, verify, and atomically cut over one complete casilla tree.

    The replacement mapping is intentionally path-addressed: every path must
    already be a regular direct child of the canonical tree, so a caller cannot
    add declarations, escape the tree, or replace an unrelated nested member.
    A durable journal makes a crash observable and lets the owner recover it on
    its next locked invocation.
    """
    _require_regular_tree(casillas_root, subject="canonical casilla tree")
    replace = _replace_tree if replace_tree is None else replace_tree
    revision_root = casillas_root.parent
    _require_regular_directory(revision_root, subject="canonical revision root")
    journal_path = revision_root / journal_name
    if journal_path.exists() or is_link_like(journal_path):
        raise RegistryValidationError(f"casilla publication journal already exists: {journal_path}")
    if not rendered:
        raise RegistryValidationError("casilla publication has no compiler-owned replacement paths")
    for path, payload in rendered.items():
        _require_replacement_path(path, casillas_root)
        if not isinstance(payload, str):
            raise RegistryValidationError(f"casilla publication payload is not text: {path}")

    token = secrets.token_hex(16)
    stage = revision_root / f"{stage_prefix}{token}"
    backup = revision_root / f"{backup_prefix}{token}"
    journal = {"schema_version": 1, "state": "intent", "stage": stage.name, "backup": backup.name}
    _write_journal(journal_path, journal)
    try:
        shutil.copytree(casillas_root, stage)
        _require_regular_tree(stage, subject="staged casilla tree")
        for path, payload in rendered.items():
            staged_path = stage / path.relative_to(casillas_root)
            _require_replacement_path(staged_path, stage)
            atomic_write_text(staged_path, payload, encoding="utf-8")
        verifier(stage)
        replace(casillas_root, backup)
        journal["state"] = "backup_staged"
        _write_journal(journal_path, journal)
        replace(stage, casillas_root)
        journal["state"] = "candidate_live"
        _write_journal(journal_path, journal)
        verifier(casillas_root)
    except BaseException:
        _restore_backup(casillas_root, backup, stage_prefix=stage_prefix, replace_tree=replace)
        _remove_transaction_tree(stage, revision_root, (stage_prefix, backup_prefix))
        if casillas_root.exists():
            _delete_journal(journal_path)
        raise
    _remove_transaction_tree(backup, revision_root, (stage_prefix, backup_prefix))
    _delete_journal(journal_path)


def recover_verified_casilla_tree(
    *,
    casillas_root: Path,
    verifier: Callable[[Path], None],
    journal_name: str,
    stage_prefix: str,
    backup_prefix: str,
) -> bool:
    """Recover one interrupted transaction; return whether recovery changed state."""
    revision_root = casillas_root.parent
    journal_path = revision_root / journal_name
    if not journal_path.exists():
        return False
    if is_link_like(journal_path) or not journal_path.is_file():
        raise RegistryValidationError(f"casilla publication journal is unsafe: {journal_path}")
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        if (
            set(journal) != {"schema_version", "state", "stage", "backup"}
            or journal["schema_version"] != 1
            or journal["state"] not in {"intent", "backup_staged", "candidate_live"}
        ):
            raise ValueError("schema")
        stage = _transaction_child(revision_root, journal["stage"], stage_prefix)
        backup = _transaction_child(revision_root, journal["backup"], backup_prefix)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RegistryValidationError(f"casilla publication journal is invalid: {journal_path}") from exc
    if casillas_root.exists():
        _require_regular_tree(casillas_root, subject="casilla publication recovery canonical tree")
    if stage.exists():
        _require_regular_tree(stage, subject="casilla publication recovery staged tree")
    if backup.exists():
        _require_regular_tree(backup, subject="casilla publication recovery backup tree")
    if journal["state"] == "backup_staged" and not backup.exists():
        raise RegistryValidationError(f"casilla publication recovery backup is missing: {journal_path}")
    if journal["state"] == "candidate_live" and casillas_root.exists():
        try:
            verifier(casillas_root)
        except RegistryValidationError as candidate_error:
            if not backup.exists():
                raise RegistryValidationError(
                    f"casilla publication cannot recover an invalid candidate without backup: {journal_path}"
                ) from candidate_error
            _restore_backup(casillas_root, backup, stage_prefix=stage_prefix, replace_tree=_replace_tree)
        else:
            if backup.exists():
                _remove_transaction_tree(backup, revision_root, (stage_prefix, backup_prefix))
    elif backup.exists():
        _restore_backup(casillas_root, backup, stage_prefix=stage_prefix, replace_tree=_replace_tree)
    elif journal["state"] != "intent" and not casillas_root.exists():
        raise RegistryValidationError(f"casilla publication cannot recover missing canonical tree: {journal_path}")
    _remove_transaction_tree(stage, revision_root, (stage_prefix, backup_prefix))
    _delete_journal(journal_path)
    return True


def _require_replacement_path(path: Path, root: Path) -> None:
    if is_link_like(path) or not path.is_file() or path.parent.resolve() != root.resolve() or path.suffix != ".toml":
        raise RegistryValidationError(f"casilla publication replacement path is unsafe: {path}")
    if path.stat().st_nlink != 1:
        raise RegistryValidationError(f"casilla publication refuses hard-linked replacement: {path}")


def _transaction_child(root: Path, name: object, prefix: str) -> Path:
    if not isinstance(name, str) or not name.startswith(prefix) or Path(name).name != name:
        raise RegistryValidationError("casilla publication journal carries an unsafe transaction path")
    return root / name


def _require_regular_directory(path: Path, *, subject: str) -> None:
    if is_link_like(path) or not path.is_dir():
        raise RegistryValidationError(f"{subject} must be a non-linked directory: {path}")


def _require_regular_tree(path: Path, *, subject: str) -> None:
    _require_regular_directory(path, subject=subject)
    children = scan_directory(path)
    if not children:
        raise RegistryValidationError(f"{subject} must not be empty: {path}")
    for child in children:
        if is_link_like(child):
            raise RegistryValidationError(f"{subject} contains a symbolic link or junction: {child}")
        if child.is_dir():
            _require_regular_tree(child, subject=subject)
        elif not child.is_file() or child.stat().st_nlink != 1:
            raise RegistryValidationError(f"{subject} contains a non-regular or hard-linked member: {child}")


def _replace_tree(source: Path, destination: Path) -> None:
    os.replace(source, destination)
    fsync_parent_dir(destination)


def _restore_backup(
    casillas_root: Path,
    backup: Path,
    *,
    stage_prefix: str,
    replace_tree: Callable[[Path, Path], None],
) -> None:
    if not backup.exists():
        return
    if casillas_root.exists():
        discarded = casillas_root.parent / f"{stage_prefix}discard-{secrets.token_hex(16)}"
        replace_tree(casillas_root, discarded)
        _remove_transaction_tree(discarded, casillas_root.parent, (stage_prefix,))
    replace_tree(backup, casillas_root)


def _remove_transaction_tree(path: Path, root: Path, prefixes: tuple[str, ...]) -> None:
    if not path.exists():
        return
    if is_link_like(path) or path.parent.resolve() != root.resolve() or not path.name.startswith(prefixes):
        raise RegistryValidationError(f"unsafe casilla publication cleanup target: {path}")
    _require_regular_tree(path, subject="casilla publication cleanup tree")
    shutil.rmtree(path)
    fsync_parent_dir(path)


def _write_journal(path: Path, journal: Mapping[str, object]) -> None:
    atomic_write_text(path, json.dumps(journal, sort_keys=True) + "\n", encoding="utf-8")
    fsync_parent_dir(path)


def _delete_journal(path: Path) -> None:
    if is_link_like(path):
        raise RegistryValidationError(f"casilla publication journal is link-like: {path}")
    path.unlink(missing_ok=True)
    fsync_parent_dir(path)
