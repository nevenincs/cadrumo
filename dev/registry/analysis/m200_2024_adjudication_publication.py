"""Check and transactionally publish the compiler-owned M200/2024 S14/S15 cohort.

This is deliberately narrower than the source-rebind authoring transaction:
the only authored declaration bytes it may replace are the 116 adjudications
rendered by the target-year blocker compiler.  Everything else is fingerprinted
as an input and must survive byte-for-byte.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ..pipeline.casilla_tree_transaction import publish_verified_casilla_tree, recover_verified_casilla_tree
from .m200_2024_blocker_adjudications import (
    S14_S15_EXPECTED_COUNT,
    render_canonical_declaration,
)
from .m200_2024_blocker_adjudications import (
    verify_canonical_declarations as verify_blocker_canonical_declarations,
)
from .m200_2024_reviewed_promotions import (
    M200ReviewedPromotionSnapshot,
    _receipt_candidate_ids,
    build_m200_2024_reviewed_promotion_snapshot,
)
from .m200_2024_template_adjudications import verify_canonical_declarations as verify_template_canonical_declarations
from .m200_2024_unique_adjudications import verify_canonical_declarations as verify_unique_canonical_declarations

_LOCK = ".m200-2024-adjudication.lock"
_JOURNAL = ".m200-2024-adjudication.journal.json"
_STAGE_PREFIX = ".m200-2024-adjudication-stage-"
_BACKUP_PREFIX = ".m200-2024-adjudication-backup-"


@dataclass(frozen=True, slots=True)
class M200AdjudicationPublicationReceipt:
    """One check-time target/receipt observation that publication must replay."""

    compiler_sha256: str
    target_tree: tuple[tuple[str, str], ...]
    output_paths: tuple[str, ...]


def check_m200_2024_s14_s15(*, registry_root: Path | None = None) -> M200AdjudicationPublicationReceipt:
    """Compile all 116 declarations and prove their staged authority load.

    Unlike a generic equality check this reports a stale canonical cohort as
    publishable evidence; it never changes the live tree.
    """
    root = _registry_root(registry_root)
    snapshot = build_m200_2024_reviewed_promotion_snapshot()
    if len(_receipt_candidate_ids(snapshot)) != 156:
        raise RegistryValidationError("M200/2024 adjudication receipt union is incomplete")
    _verify_unaffected_receipts(snapshot, _casillas_root(root))
    rendered = _rendered(snapshot, root)
    before = _tree_fingerprint(_casillas_root(root))
    _verify_candidate(root, rendered, before, snapshot)
    return M200AdjudicationPublicationReceipt(
        compiler_sha256=_compiler_digest(snapshot, rendered),
        target_tree=before,
        output_paths=tuple(sorted(path.name for path in rendered)),
    )


def publish_m200_2024_s14_s15(
    receipt: M200AdjudicationPublicationReceipt,
    *,
    registry_root: Path | None = None,
) -> None:
    """Replay a checked receipt under one exclusive lock and cut over atomically."""
    root = _registry_root(registry_root)
    with exclusive_file_lock(root / _LOCK):
        snapshot = build_m200_2024_reviewed_promotion_snapshot()
        recovered_rendered = _rendered(snapshot, root)
        if recover_verified_casilla_tree(
            casillas_root=_casillas_root(root),
            verifier=lambda staged: _verify_staged_tree(
                root, staged, recovered_rendered, dict(receipt.target_tree), snapshot
            ),
            journal_name=_JOURNAL,
            stage_prefix=_STAGE_PREFIX,
            backup_prefix=_BACKUP_PREFIX,
            journal_root=root,
        ):
            raise RegistryValidationError(
                "M200/2024 adjudication recovered an interrupted publication; run check again"
            )
        live = check_m200_2024_s14_s15(registry_root=root)
        if live.compiler_sha256 != receipt.compiler_sha256:
            raise RegistryValidationError("M200/2024 adjudication compiler receipt changed after check")
        if live.target_tree != receipt.target_tree:
            raise RegistryValidationError("M200/2024 adjudication target changed after check")
        snapshot = build_m200_2024_reviewed_promotion_snapshot()
        rendered = _rendered(snapshot, root)
        if _compiler_digest(snapshot, rendered) != receipt.compiler_sha256:
            raise RegistryValidationError("M200/2024 adjudication compiler inputs changed after check")
        if tuple(sorted(path.name for path in rendered)) != receipt.output_paths:
            raise RegistryValidationError("M200/2024 adjudication output membership changed after check")
        if _tree_fingerprint(_casillas_root(root)) != receipt.target_tree:
            raise RegistryValidationError("M200/2024 adjudication target drifted before cutover")
        original = dict(receipt.target_tree)
        publish_verified_casilla_tree(
            casillas_root=_casillas_root(root),
            rendered=rendered,
            verifier=lambda staged: _verify_staged_tree(root, staged, rendered, original, snapshot),
            journal_name=_JOURNAL,
            stage_prefix=_STAGE_PREFIX,
            backup_prefix=_BACKUP_PREFIX,
            journal_root=root,
        )


def _registry_root(registry_root: Path | None) -> Path:
    root = bundled_path("registry", "aeat") if registry_root is None else registry_root
    if not root.is_dir() or is_link_like(root):
        raise RegistryValidationError(f"M200/2024 adjudication registry root is unsafe: {root}")
    return root.resolve()


def _casillas_root(registry_root: Path) -> Path:
    root = registry_root.resolve()
    target = root
    for component in ("modelos", "200", "revisions", "2024", "casillas"):
        target = target / component
        if not target.exists() or is_link_like(target):
            raise RegistryValidationError(f"M200/2024 adjudication casilla path is unsafe: {target}")
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RegistryValidationError(f"M200/2024 adjudication casilla root escaped registry root: {target}") from exc
    if not resolved.is_dir():
        raise RegistryValidationError(f"M200/2024 adjudication casilla root is not a directory: {target}")
    return resolved


def _rendered(snapshot: M200ReviewedPromotionSnapshot, registry_root: Path) -> dict[Path, str]:
    authority = snapshot.blocker_authority
    if len(authority.adjudications) != S14_S15_EXPECTED_COUNT:
        raise RegistryValidationError("M200/2024 adjudication compiler output count drifted")
    root = _casillas_root(registry_root)
    rendered = {
        root / f"c{row.casilla_id}.toml": render_canonical_declaration(authority, row.casilla_id)
        for row in authority.adjudications
    }
    if len(rendered) != S14_S15_EXPECTED_COUNT or (root / "c00093.toml") not in rendered:
        raise RegistryValidationError("M200/2024 adjudication compiler membership is not the exact S14/S15 cohort")
    return rendered


def _compiler_digest(snapshot: M200ReviewedPromotionSnapshot, rendered: Mapping[Path, str]) -> str:
    digest = sha256(snapshot.receipt_sha256.encode("ascii"))
    for path, payload in sorted(rendered.items()):
        digest.update(path.name.encode("ascii"))
        digest.update(payload.encode("utf-8"))
    return digest.hexdigest()


def _tree_fingerprint(root: Path) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for path in scan_directory(root, recursive=True):
        if path.is_dir():
            if is_link_like(path):
                raise RegistryValidationError(f"M200/2024 adjudication refuses linked input: {path}")
            continue
        if is_link_like(path) or not path.is_file() or path.stat().st_nlink != 1:
            raise RegistryValidationError(f"M200/2024 adjudication refuses linked input: {path}")
        rows.append((path.relative_to(root).as_posix(), sha256(path.read_bytes()).hexdigest()))
    if not rows:
        raise RegistryValidationError("M200/2024 adjudication found an empty casilla tree")
    return tuple(sorted(rows))


def _verify_candidate(
    registry_root: Path,
    rendered: Mapping[Path, str],
    original: tuple[tuple[str, str], ...],
    snapshot: M200ReviewedPromotionSnapshot,
) -> None:
    with tempfile.TemporaryDirectory(prefix="cadrumo-m200-2024-adjudication-") as temporary:
        copied_root = Path(temporary) / "registry" / "aeat"
        shutil.copytree(registry_root, copied_root)
        copied_casillas = _casillas_root(copied_root)
        for source, payload in rendered.items():
            target = copied_casillas / source.name
            target.write_bytes(payload.encode("utf-8"))
        _verify_staged_tree(registry_root, copied_casillas, rendered, dict(original), snapshot)


def _verify_staged_tree(
    registry_root: Path,
    staged: Path,
    rendered: Mapping[Path, str],
    original: Mapping[str, str],
    snapshot: M200ReviewedPromotionSnapshot,
) -> None:
    expected = {path.name: payload.encode("utf-8") for path, payload in rendered.items()}
    fingerprint = dict(_tree_fingerprint(staged))
    if set(fingerprint) != set(original):
        raise RegistryValidationError("M200/2024 adjudication changed casilla-tree membership")
    for name, expected_bytes in expected.items():
        if (staged / name).read_bytes() != expected_bytes:
            raise RegistryValidationError(f"M200/2024 adjudication staged compiler bytes drifted: {name}")
    for name, digest in original.items():
        if name not in expected and fingerprint[name] != digest:
            raise RegistryValidationError(f"M200/2024 adjudication changed a non-cohort declaration: {name}")
    verify_blocker_canonical_declarations(snapshot.blocker_authority, casillas_root=staged)
    _verify_unaffected_receipts(snapshot, staged)
    _verify_isolated_authority_load(registry_root, staged)


def _verify_unaffected_receipts(snapshot: M200ReviewedPromotionSnapshot, casillas_root: Path) -> None:
    """Byte-verify the reviewed cohorts this publisher is not allowed to repair."""
    verify_template_canonical_declarations(snapshot.template_authority, casillas_root=casillas_root)
    verify_unique_canonical_declarations(snapshot.unique_authority, casillas_root=casillas_root)


def _verify_isolated_authority_load(registry_root: Path, casillas_root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="cadrumo-m200-2024-adjudication-load-") as temporary:
        copied_root = Path(temporary) / "registry" / "aeat"
        shutil.copytree(registry_root, copied_root)
        target = _casillas_root(copied_root)
        shutil.rmtree(target)
        shutil.copytree(casillas_root, target)
        authority = ValidatedRegistryAuthority.load(copied_root, source_root=bundled_path())
        authority.snapshot(
            "200",
            filing_year=2024,
            period="0A",
            revision_id="2024",
            grade=RegistryAuthorityGrade.CALCULATION,
        )


def main(argv: list[str] | None = None) -> int:
    """Run the explicit check or publish developer command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "publish"))
    parser.add_argument("--registry-root", type=Path, default=bundled_path("registry", "aeat"))
    parser.add_argument("--dry-run", action="store_true", help="run publish preflight without replacing declarations")
    args = parser.parse_args(argv)
    receipt = check_m200_2024_s14_s15(registry_root=args.registry_root)
    if args.dry_run and args.action != "publish":
        parser.error("--dry-run requires publish")
    if args.action == "publish" and not args.dry_run:
        publish_m200_2024_s14_s15(receipt, registry_root=args.registry_root)
    print(f"cohort={len(receipt.output_paths)}")
    print(f"action={args.action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
