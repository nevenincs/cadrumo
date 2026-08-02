"""Seal, verify, and garbage-collect draft-release evidence transport.

The packaging workflows transport every inter-workflow payload — the sealed
release cohort archive, the per-OS python cohorts, and the flat
:class:`~dev.packaging.evidence.DistributionEvidence` rows — as assets on a
per-run **draft** GitHub release tagged ``evidence-<lane>-<run_id>``. A release
asset, unlike a run-scoped artifact, is not intrinsically bound to the run that
produced it, so each producing run finishes by sealing an
``evidence-manifest.json`` asset binding the run identity (workflow path,
run id, run attempt, head SHA, branch, event) to the sha256 and size of every
other asset. Consumers re-establish that binding with ``verify``: the Actions
API run record, the draft's ``target_commitish``, the manifest claims, and the
re-hashed downloaded bytes must all agree before a single byte is trusted.

Four subcommands:

* ``emit-manifest`` — download the draft's assets, hash them, and write the
  sealed manifest (uploaded by the workflow as the final asset).
* ``verify`` — download manifest + assets into a directory and fail loudly,
  naming every mismatching value, unless all layered checks pass. Because a
  draft reserves no tag ref, a concurrency bug can mint DUPLICATE drafts for
  one tag (cli/cli#4270 and siblings), so verify first asserts exactly one
  draft exists for the tag; transient download failures get a short bounded
  retry (the GoReleaser 422-retry precedent).
* ``leak-sweep`` — run the field-agnostic runner-metadata leak detector
  (:mod:`dev.packaging.evidence_scrub`) over a directory of assets about to
  be published and refuse on any hit, naming the asset and pattern. It never
  rewrites: rows are scrubbed at mint time inside the evidence builders (the
  reconciled D9); this is the fail-closed publication tripwire above them.
* ``gc`` — delete stale evidence drafts, keeping the newest K per producing
  lane plus explicitly protected tags. Only drafts whose tag matches the
  reserved ``evidence-*`` namespace are ever candidates, so real ``v*``
  releases are structurally out of reach. Dry-run is the default; deletion
  requires ``--apply``.

The ``gh`` CLI is the only transport; it is addressed by an explicit
executable path so tests exercise a real, non-mocked stub executable (the
same pattern as :func:`dev.release.readiness.check_no_open_release_blockers`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from dev.packaging._hashing import sha256_path

_UTF_8: Final[str] = "utf-8"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_RUN_NUMBER_PATTERN: Final[str] = r"^[1-9][0-9]*$"
_HEAD_SHA_PATTERN: Final[str] = r"^[0-9a-f]{40}$"

MANIFEST_SCHEMA: Final[Literal["cadrumo.packaging.evidence-release-manifest.v1"]] = (
    "cadrumo.packaging.evidence-release-manifest.v1"
)
MANIFEST_ASSET_NAME: Final[str] = "evidence-manifest.json"

# The reserved draft-tag namespace. Anything outside it — every real
# ``v<version>`` release above all — is structurally invisible to the GC and
# refused by the tag helpers.
EVIDENCE_TAG_RE: Final[re.Pattern[str]] = re.compile(r"^evidence-(smoke|scoop|homebrew|claude)-([0-9]+)$")

_GH_TIMEOUT_SECONDS: Final[int] = 600
_DOWNLOAD_ATTEMPTS: Final[int] = 3
_DOWNLOAD_RETRY_SECONDS: Final[float] = 5.0


class EvidenceLane(StrEnum):
    """Closed set of producing workflows that mint evidence drafts."""

    SMOKE = "smoke"
    SCOOP = "scoop"
    HOMEBREW = "homebrew"
    CLAUDE = "claude"


class EvidenceReleaseError(ValueError):
    """A sealing, verification, or GC invariant failed; the message names the mismatch."""


def evidence_tag(lane: EvidenceLane, run_id: str) -> str:
    """Return the draft tag for one producing run (``evidence-<lane>-<run_id>``)."""
    if re.fullmatch(_RUN_NUMBER_PATTERN, run_id) is None:
        raise EvidenceReleaseError(f"run id must be one positive workflow run id, got {run_id!r}")
    return f"evidence-{lane.value}-{run_id}"


def parse_evidence_tag(tag: str) -> tuple[EvidenceLane, str]:
    """Split a reserved-namespace tag into its lane and run id, refusing anything else."""
    match = EVIDENCE_TAG_RE.fullmatch(tag)
    if match is None:
        raise EvidenceReleaseError(
            f"tag {tag!r} is outside the reserved evidence namespace {EVIDENCE_TAG_RE.pattern!r}",
        )
    return EvidenceLane(match.group(1)), match.group(2)


class AssetDigest(BaseModel):
    """Byte identity of one sealed release asset."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sha256: str = Field(pattern=_SHA256_PATTERN)
    size_bytes: int = Field(ge=0)


class EvidenceReleaseManifest(BaseModel):
    """Run-identity + per-asset digest binding sealed onto an evidence draft."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["cadrumo.packaging.evidence-release-manifest.v1"]
    workflow_path: str = Field(min_length=1)
    run_id: str = Field(pattern=_RUN_NUMBER_PATTERN)
    run_attempt: str = Field(pattern=_RUN_NUMBER_PATTERN)
    head_sha: str = Field(pattern=_HEAD_SHA_PATTERN)
    head_branch: str = Field(min_length=1)
    event: str = Field(min_length=1)
    assets: dict[str, AssetDigest] = Field(min_length=1)


def build_manifest(
    *,
    assets: dict[str, Path],
    workflow_path: str,
    run_id: str,
    run_attempt: str,
    head_sha: str,
    head_branch: str,
    event: str,
) -> EvidenceReleaseManifest:
    """Hash real asset files and bind them to the producing run identity."""
    if not assets:
        raise EvidenceReleaseError("an evidence draft must carry at least one asset to seal")
    if MANIFEST_ASSET_NAME in assets:
        raise EvidenceReleaseError(f"the manifest never seals itself: drop {MANIFEST_ASSET_NAME!r} from the asset set")
    return EvidenceReleaseManifest(
        schema_name=MANIFEST_SCHEMA,
        workflow_path=workflow_path,
        run_id=run_id,
        run_attempt=run_attempt,
        head_sha=head_sha,
        head_branch=head_branch,
        event=event,
        assets={
            name: AssetDigest(sha256=sha256_path(path), size_bytes=path.stat().st_size)
            for name, path in sorted(assets.items())
        },
    )


def write_manifest(manifest: EvidenceReleaseManifest, output: Path) -> Path:
    """Persist the manifest as canonical, human-diffable JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(manifest.model_dump_json(indent=2) + "\n", encoding=_UTF_8)
    return output


def load_manifest(path: Path) -> EvidenceReleaseManifest:
    """Load and strictly validate a downloaded manifest asset."""
    return EvidenceReleaseManifest.model_validate_json(path.read_text(encoding=_UTF_8))


def verify_downloaded_assets(
    *,
    manifest: EvidenceReleaseManifest,
    run_record: dict[str, object],
    release_record: dict[str, object],
    downloaded: dict[str, Path],
    expect_run_id: str,
    expect_workflow: str,
    repository: str,
    require_complete: bool,
) -> list[str]:
    """Return every layered-check mismatch (empty means fully verified).

    Layered checks, strictly stronger than run-scoped artifact trust:
    run identity against the Actions API, release↔run binding
    (``target_commitish`` and the manifest's identity claims), and byte
    integrity (every downloaded asset re-hashes to the sealed digest).
    """
    mismatches: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            mismatches.append(message)

    conclusion = run_record.get("conclusion")
    run_path = run_record.get("path")
    head_repository = run_record.get("head_repository")
    head_repo_name = head_repository.get("full_name") if isinstance(head_repository, dict) else None
    api_run_id = str(run_record.get("id"))
    api_head_sha = str(run_record.get("head_sha"))
    check(conclusion == "success", f"run conclusion is {conclusion!r}, expected 'success'")
    check(run_path == expect_workflow, f"run workflow path is {run_path!r}, expected {expect_workflow!r}")
    check(head_repo_name == repository, f"run head repository is {head_repo_name!r}, expected {repository!r}")
    check(api_run_id == expect_run_id, f"run id is {api_run_id!r}, expected {expect_run_id!r}")

    target_commitish = release_record.get("targetCommitish")
    is_draft = release_record.get("isDraft")
    check(is_draft is True, f"evidence release must be a draft, got isDraft={is_draft!r}")
    check(
        target_commitish == api_head_sha,
        f"release target_commitish {target_commitish!r} does not equal the run head_sha {api_head_sha!r}",
    )

    check(manifest.run_id == expect_run_id, f"manifest run_id {manifest.run_id!r} != expected {expect_run_id!r}")
    check(
        manifest.workflow_path == expect_workflow,
        f"manifest workflow_path {manifest.workflow_path!r} != expected {expect_workflow!r}",
    )
    check(
        manifest.head_sha == api_head_sha,
        f"manifest head_sha {manifest.head_sha!r} != API head_sha {api_head_sha!r}",
    )
    api_run_attempt = str(run_record.get("run_attempt"))
    check(
        manifest.run_attempt == api_run_attempt,
        f"manifest run_attempt {manifest.run_attempt!r} != API run_attempt {api_run_attempt!r}",
    )
    api_event = run_record.get("event")
    check(manifest.event == api_event, f"manifest event {manifest.event!r} != API event {api_event!r}")
    api_branch = run_record.get("head_branch")
    check(
        manifest.head_branch == api_branch,
        f"manifest head_branch {manifest.head_branch!r} != API head_branch {api_branch!r}",
    )

    if not downloaded:
        mismatches.append("no assets were downloaded to verify")
    for name, path in sorted(downloaded.items()):
        sealed = manifest.assets.get(name)
        if sealed is None:
            mismatches.append(f"downloaded asset {name!r} is not sealed in the manifest")
            continue
        actual_sha = sha256_path(path)
        actual_size = path.stat().st_size
        if actual_sha != sealed.sha256:
            mismatches.append(f"asset {name!r} sha256 {actual_sha} != sealed {sealed.sha256}")
        if actual_size != sealed.size_bytes:
            mismatches.append(f"asset {name!r} size {actual_size} != sealed {sealed.size_bytes}")
    if require_complete:
        missing = sorted(set(manifest.assets) - set(downloaded))
        if missing:
            mismatches.append(f"sealed assets absent from the download: {missing!r}")

    return mismatches


class GcPlan(BaseModel):
    """Deterministic evidence-draft retention decision for one GC pass."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kept: tuple[str, ...]
    delete: tuple[str, ...]


def plan_evidence_gc(
    releases: list[dict[str, object]],
    *,
    keep_per_lane: int,
    protected_tags: frozenset[str] = frozenset(),
) -> GcPlan:
    """Keep the newest K drafts per lane plus every protected tag; delete the rest.

    Only records that are drafts AND match the reserved evidence-tag namespace
    are ever candidates; every other release (published ``v*`` releases above
    all) is ignored entirely, never returned in either bucket.
    """
    if keep_per_lane < 1:
        raise EvidenceReleaseError(f"keep_per_lane must be at least 1, got {keep_per_lane}")
    candidates: list[tuple[str, EvidenceLane, str]] = []
    for record in releases:
        tag = str(record.get("tag_name", ""))
        if record.get("draft") is not True or EVIDENCE_TAG_RE.fullmatch(tag) is None:
            continue
        lane, _run_id = parse_evidence_tag(tag)
        candidates.append((str(record.get("created_at", "")), lane, tag))

    kept: list[str] = []
    delete: list[str] = []
    per_lane_seen: dict[EvidenceLane, int] = {}
    for created_at, lane, tag in sorted(candidates, key=lambda item: (item[0], item[2]), reverse=True):
        del created_at
        per_lane_seen[lane] = per_lane_seen.get(lane, 0) + 1
        if tag in protected_tags or per_lane_seen[lane] <= keep_per_lane:
            kept.append(tag)
        else:
            delete.append(tag)
    return GcPlan(kept=tuple(kept), delete=tuple(delete))


def _run_gh(gh: str, arguments: list[str]) -> str:
    """Run one real ``gh`` subprocess and return stdout, raising on failure."""
    completed = subprocess.run(
        [gh, *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=_GH_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise EvidenceReleaseError(
            f"gh {' '.join(arguments)} failed (rc={completed.returncode}): {completed.stderr.strip()[:500]}",
        )
    return completed.stdout


def resolve_gh(explicit: str | None) -> str:
    """Resolve the `gh` executable, honouring an explicit path for tests.

    Public because the release-candidate transport shares this exact boundary:
    the draft-release mechanism carries both evidence rows and sealed
    candidates, so promoting the primitive keeps ONE gh boundary rather than a
    second copy in the release package.
    """
    if explicit is not None:
        return explicit
    resolved = shutil.which("gh")
    if resolved is None:
        raise EvidenceReleaseError("gh is not on PATH; pass --gh with an explicit executable")
    return resolved


def run_gh_with_retry(gh: str, arguments: list[str]) -> str:
    """Run ``gh`` with a short bounded retry for transient API failures."""
    last_error: EvidenceReleaseError | None = None
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            return _run_gh(gh, arguments)
        except EvidenceReleaseError as error:
            last_error = error
            if attempt < _DOWNLOAD_ATTEMPTS:
                time.sleep(_DOWNLOAD_RETRY_SECONDS * attempt)
    raise EvidenceReleaseError(f"gh failed after {_DOWNLOAD_ATTEMPTS} attempts: {last_error}")


def download_release_assets(gh: str, *, repository: str, tag: str, patterns: list[str], directory: Path) -> None:
    """Download the tag's assets (all, or per pattern) into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    base = ["release", "download", tag, "--repo", repository, "--dir", str(directory), "--clobber"]
    if patterns:
        for pattern in patterns:
            run_gh_with_retry(gh, [*base, "--pattern", pattern])
    else:
        run_gh_with_retry(gh, base)


def list_releases(gh: str, repository: str) -> list[dict[str, object]]:
    """Return every release record (drafts included), paginated past 100.

    Pagination matters: softprops/action-gh-release#602 documents duplicate
    draft creation precisely because a lookup stopped at the first page.
    """
    raw = _run_gh(
        gh,
        [
            "api",
            f"repos/{repository}/releases?per_page=100",
            "--paginate",
            "--jq",
            ".[] | {tag_name, draft, created_at}",
        ],
    )
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _assert_exactly_one_draft(gh: str, repository: str, tag: str) -> None:
    """Refuse unless exactly one DRAFT release carries the tag.

    Drafts reserve no tag ref, so concurrent creators can mint duplicates for
    one tag (cli/cli#4270 et al.); with two drafts, which assets ``gh release
    download`` resolves is undefined — never trust bytes from that state.
    """
    matches = [record for record in list_releases(gh, repository) if record.get("tag_name") == tag]
    drafts = [record for record in matches if record.get("draft") is True]
    if len(drafts) != 1 or len(matches) != len(drafts):
        raise EvidenceReleaseError(
            f"expected exactly one draft release for {tag!r}, found "
            f"{len(drafts)} draft(s) / {len(matches)} release(s) — refusing to trust any asset",
        )


def _downloaded_files(directory: Path) -> dict[str, Path]:
    """Return the directory's asset files by name, excluding the manifest itself."""
    return {
        path.name: path for path in sorted(directory.iterdir()) if path.is_file() and path.name != MANIFEST_ASSET_NAME
    }


def _workflow_path_from_env(environ: dict[str, str]) -> str | None:
    """Derive ``.github/workflows/<file>.yml`` from ``GITHUB_WORKFLOW_REF``."""
    workflow_ref = environ.get("GITHUB_WORKFLOW_REF", "")
    repository = environ.get("GITHUB_REPOSITORY", "")
    if not workflow_ref or not repository:
        return None
    path = workflow_ref.split("@", 1)[0]
    prefix = f"{repository}/"
    return path.removeprefix(prefix) if path.startswith(prefix) else path


def _required(value: str | None, name: str) -> str:
    if not value:
        raise EvidenceReleaseError(f"{name} is required (flag or GitHub Actions environment)")
    return value


def _emit_manifest(args: argparse.Namespace) -> int:
    gh = resolve_gh(args.gh)
    environ = dict(os.environ)
    repository = _required(args.repo or environ.get("GITHUB_REPOSITORY"), "--repo")
    parse_evidence_tag(args.tag)
    manifest_inputs = {
        "workflow_path": _required(args.workflow_path or _workflow_path_from_env(environ), "--workflow-path"),
        "run_id": _required(args.run_id or environ.get("GITHUB_RUN_ID"), "--run-id"),
        "run_attempt": _required(args.run_attempt or environ.get("GITHUB_RUN_ATTEMPT"), "--run-attempt"),
        "head_sha": _required(args.head_sha or environ.get("GITHUB_SHA"), "--head-sha"),
        "head_branch": _required(args.head_branch or environ.get("GITHUB_REF_NAME"), "--head-branch"),
        "event": _required(args.event or environ.get("GITHUB_EVENT_NAME"), "--event"),
    }
    with tempfile.TemporaryDirectory(prefix="cadrumo-evidence-seal-") as scratch:
        directory = Path(scratch)
        download_release_assets(gh, repository=repository, tag=args.tag, patterns=[], directory=directory)
        manifest = build_manifest(assets=_downloaded_files(directory), **manifest_inputs)
        write_manifest(manifest, args.output)
    print(f"sealed {len(manifest.assets)} asset(s) of {args.tag} into {args.output}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    gh = resolve_gh(args.gh)
    repository = _required(args.repo or os.environ.get("GITHUB_REPOSITORY"), "--repo")
    parse_evidence_tag(args.tag)
    _assert_exactly_one_draft(gh, repository, args.tag)
    run_record = json.loads(_run_gh(gh, ["api", f"repos/{repository}/actions/runs/{args.expect_run_id}"]))
    release_record = json.loads(
        _run_gh(
            gh,
            ["release", "view", args.tag, "--repo", repository, "--json", "targetCommitish,isDraft,tagName"],
        ),
    )
    download_dir: Path = args.download_dir
    requested_patterns: list[str] = args.pattern or []
    # A narrowing --pattern still always downloads the manifest; no pattern
    # downloads (and later requires) the complete sealed asset set.
    patterns = [MANIFEST_ASSET_NAME, *requested_patterns] if requested_patterns else []
    download_release_assets(gh, repository=repository, tag=args.tag, patterns=patterns, directory=download_dir)
    manifest_path = download_dir / MANIFEST_ASSET_NAME
    if not manifest_path.is_file():
        raise EvidenceReleaseError(f"evidence draft {args.tag} carries no sealed {MANIFEST_ASSET_NAME}")
    manifest = load_manifest(manifest_path)
    downloaded = _downloaded_files(download_dir)
    mismatches = verify_downloaded_assets(
        manifest=manifest,
        run_record=run_record,
        release_record=release_record,
        downloaded=downloaded,
        expect_run_id=args.expect_run_id,
        expect_workflow=args.expect_workflow,
        repository=repository,
        require_complete=not requested_patterns,
    )
    if mismatches:
        raise EvidenceReleaseError(
            f"evidence draft {args.tag} failed verification:\n" + "\n".join(f"  - {line}" for line in mismatches),
        )
    print(f"verified {len(downloaded)} asset(s) of {args.tag} against run {args.expect_run_id}")
    return 0


def sweep_directory_for_leaks(directory: Path, *, tokens: tuple[str, ...] = ()) -> list[str]:
    """Return every runner-metadata leak signature across a publication directory.

    JSON files are walked structurally (field-agnostic, exactly the mint-time
    detector); every other file is scanned as text — latin-1 decoded when not
    UTF-8, so plain strings inside uncompressed binaries are still seen. This
    NEVER rewrites anything: rows are scrubbed at mint time inside the
    evidence builders; this sweep is the fail-closed tripwire for payloads the
    builders did not mint (manifests, archived transcripts) and for any new
    leak class that slips past them.
    """
    from dev.packaging.evidence_scrub import find_residual_leaks

    if not directory.is_dir():
        raise EvidenceReleaseError(f"leak-sweep directory does not exist: {directory}")
    leaks: list[str] = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        label = path.relative_to(directory).as_posix()
        document: dict[str, object]
        if path.suffix == ".json":
            try:
                document = {"document": json.loads(path.read_text(encoding=_UTF_8))}
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                leaks.append(f"{label}: unparseable JSON refused ({error})")
                continue
        else:
            try:
                text = path.read_text(encoding=_UTF_8)
            except UnicodeDecodeError:
                text = path.read_bytes().decode("latin-1")
            document = {"lines": text.splitlines()}
        leaks.extend(f"{label}{leak}" for leak in find_residual_leaks(document, tokens))
    return leaks


def _leak_sweep(args: argparse.Namespace) -> int:
    directories: list[Path] = args.directory
    tokens = tuple(args.token or ())
    leaks = [
        f"{directory}: {leak}"
        for directory in directories
        for leak in sweep_directory_for_leaks(directory, tokens=tokens)
    ]
    if leaks:
        raise EvidenceReleaseError(
            "publication leak sweep failed:\n" + "\n".join(f"  - {leak}" for leak in leaks),
        )
    files = sum(1 for directory in directories for path in directory.rglob("*") if path.is_file())
    print(f"leak sweep clean: {files} file(s) under {len(directories)} directory(ies)")
    return 0


def _gc(args: argparse.Namespace) -> int:
    gh = resolve_gh(args.gh)
    repository = _required(args.repo or os.environ.get("GITHUB_REPOSITORY"), "--repo")
    releases = list_releases(gh, repository)
    plan = plan_evidence_gc(
        releases,
        keep_per_lane=args.keep,
        protected_tags=frozenset(args.keep_tag or ()),
    )
    for tag in plan.kept:
        print(f"keep {tag}")
    for tag in plan.delete:
        # Structural refusal re-check immediately before every deletion: only a
        # reserved-namespace draft tag from this plan is ever deleted.
        parse_evidence_tag(tag)
        if not args.apply:
            print(f"would delete {tag} (dry run)")
            continue
        _run_gh(gh, ["release", "delete", tag, "--repo", repository, "--yes"])
        print(f"deleted {tag}")
    if not args.apply:
        print(f"dry run: {len(plan.delete)} stale draft(s); pass --apply to delete")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seal, verify, and GC draft-release evidence transport.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--gh", default=None, help="Explicit gh executable (default: resolve on PATH).")
        sub.add_argument("--repo", default=None, help="owner/name slug (default: GITHUB_REPOSITORY).")

    emit = subparsers.add_parser("emit-manifest", help="Seal the draft's assets into evidence-manifest.json.")
    emit.add_argument("--tag", required=True, help="Evidence draft tag (evidence-<lane>-<run_id>).")
    emit.add_argument("--output", required=True, type=Path, help="Where the sealed manifest is written.")
    emit.add_argument("--workflow-path", default=None, help="Producing workflow path (default: env).")
    emit.add_argument("--run-id", default=None, help="Producing run id (default: GITHUB_RUN_ID).")
    emit.add_argument("--run-attempt", default=None, help="Producing run attempt (default: GITHUB_RUN_ATTEMPT).")
    emit.add_argument("--head-sha", default=None, help="Producing head SHA (default: GITHUB_SHA).")
    emit.add_argument("--head-branch", default=None, help="Producing branch (default: GITHUB_REF_NAME).")
    emit.add_argument("--event", default=None, help="Producing event (default: GITHUB_EVENT_NAME).")
    common(emit)
    emit.set_defaults(handler=_emit_manifest)

    verify = subparsers.add_parser("verify", help="Download and verify an evidence draft end to end.")
    verify.add_argument("--tag", required=True, help="Evidence draft tag to verify.")
    verify.add_argument("--expect-run-id", required=True, help="Actions run id the draft must bind.")
    verify.add_argument("--expect-workflow", required=True, help="Workflow path the run must belong to.")
    verify.add_argument("--download-dir", required=True, type=Path, help="Where verified assets land.")
    verify.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Verify only assets matching this pattern (repeatable; default: the complete sealed set).",
    )
    common(verify)
    verify.set_defaults(handler=_verify)

    sweep = subparsers.add_parser(
        "leak-sweep",
        help="Refuse publication when any asset in a directory carries runner metadata.",
    )
    sweep.add_argument(
        "--directory",
        required=True,
        action="append",
        type=Path,
        help="Directory of assets about to be published (repeatable; every root must sweep clean).",
    )
    sweep.add_argument(
        "--token",
        action="append",
        default=None,
        help="Additional machine-identifying token to refuse (repeatable).",
    )
    sweep.set_defaults(handler=_leak_sweep)

    gc = subparsers.add_parser("gc", help="Delete stale evidence drafts (dry run unless --apply).")
    gc.add_argument("--keep", type=int, default=3, help="Newest drafts kept per producing lane (default 3).")
    gc.add_argument(
        "--keep-tag",
        action="append",
        default=None,
        help="Evidence tag protected from deletion regardless of age (repeatable).",
    )
    gc.add_argument("--apply", action="store_true", help="Actually delete; the default is a dry run.")
    common(gc)
    gc.set_defaults(handler=_gc)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one evidence-release subcommand, translating invariant failures to exit 1."""
    args = _parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except EvidenceReleaseError as error:
        print(str(error), file=sys.stderr, flush=True)
        return 1


__all__ = [
    "EVIDENCE_TAG_RE",
    "MANIFEST_ASSET_NAME",
    "MANIFEST_SCHEMA",
    "AssetDigest",
    "EvidenceLane",
    "EvidenceReleaseError",
    "EvidenceReleaseManifest",
    "GcPlan",
    "build_manifest",
    "download_release_assets",
    "evidence_tag",
    "list_releases",
    "load_manifest",
    "main",
    "parse_evidence_tag",
    "plan_evidence_gc",
    "resolve_gh",
    "run_gh_with_retry",
    "sweep_directory_for_leaks",
    "verify_downloaded_assets",
    "write_manifest",
]


if __name__ == "__main__":
    raise SystemExit(main())
