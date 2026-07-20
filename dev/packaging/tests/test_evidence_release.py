"""Real-behavior tests for the draft-release evidence transport helper.

Every test uses real files, real hashing, and — for the CLI paths — a real,
non-mocked stub ``gh`` executable (the same discipline as the readiness gate's
probe ``gh``): the stub is an actual subprocess that copies real asset bytes
and serves real JSON records from a fixture directory baked into its script.
"""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from dev.packaging.evidence_release import (
    MANIFEST_ASSET_NAME,
    MANIFEST_SCHEMA,
    EvidenceLane,
    EvidenceReleaseError,
    EvidenceReleaseManifest,
    build_manifest,
    evidence_tag,
    load_manifest,
    main,
    parse_evidence_tag,
    plan_evidence_gc,
    sha256_path,
    verify_downloaded_assets,
    write_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_RUN_ID = "16123456789"
_HEAD_SHA = "22b642533d" + "0" * 30
_WORKFLOW = ".github/workflows/packaging-smoke.yml"
_REPO = "nevenincs/cadrumo"


def _write_assets(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    cohort = directory / "cadrumo-release-cohort.tar.gz"
    cohort.write_bytes(b"\x1f\x8b" + b"immutable cohort bytes " * 64)
    row = directory / ("python-linux-x86-64-" + "a" * 64 + ".json")
    row.write_text(json.dumps({"row_id": "python-linux-x86-64"}), encoding="utf-8")
    return {cohort.name: cohort, row.name: row}


def _manifest_for(assets: dict[str, Path]) -> EvidenceReleaseManifest:
    return build_manifest(
        assets=assets,
        workflow_path=_WORKFLOW,
        run_id=_RUN_ID,
        run_attempt="1",
        head_sha=_HEAD_SHA,
        head_branch="main",
        event="push",
    )


def _run_record() -> dict[str, object]:
    return {
        "id": int(_RUN_ID),
        "conclusion": "success",
        "path": _WORKFLOW,
        "event": "push",
        "head_branch": "main",
        "head_sha": _HEAD_SHA,
        "run_attempt": 1,
        "head_repository": {"full_name": _REPO},
    }


def _release_record() -> dict[str, object]:
    return {"targetCommitish": _HEAD_SHA, "isDraft": True, "tagName": f"evidence-smoke-{_RUN_ID}"}


class TestEvidenceTagNamespace:
    """Tag builders and the reserved-namespace refusal."""

    def test_tag_builds_and_roundtrips_per_lane(self) -> None:
        """Every lane builds a tag that parses back to (lane, run_id)."""
        for lane in EvidenceLane:
            tag = evidence_tag(lane, _RUN_ID)
            assert tag == f"evidence-{lane.value}-{_RUN_ID}"
            assert parse_evidence_tag(tag) == (lane, _RUN_ID)

    @pytest.mark.parametrize(
        "tag",
        (
            "v1.2.3",
            "v0.2.1",
            "evidence-smoke-",
            "evidence-smoke-abc",
            "evidence-unknown-123",
            "prefix-evidence-smoke-123",
            "evidence-smoke-123-suffix",
            "EVIDENCE-SMOKE-123",
        ),
    )
    def test_namespace_structurally_excludes_everything_else(self, tag: str) -> None:
        """v* and malformed tags are refused by the namespace regex."""
        with pytest.raises(EvidenceReleaseError, match="reserved evidence namespace"):
            parse_evidence_tag(tag)

    def test_tag_refuses_non_numeric_run_id(self) -> None:
        """A non-numeric run id cannot mint a tag."""
        with pytest.raises(EvidenceReleaseError, match="positive workflow run id"):
            evidence_tag(EvidenceLane.SMOKE, "0x123")


class TestManifest:
    """Real-file manifest sealing, roundtrip, and strict-shape refusals."""

    def test_build_hashes_real_bytes(self, tmp_path: Path) -> None:
        """Sealed digests equal independently computed sha256/size of the real files."""
        assets = _write_assets(tmp_path / "assets")
        manifest = _manifest_for(assets)
        assert manifest.schema_name == MANIFEST_SCHEMA
        for name, path in assets.items():
            sealed = manifest.assets[name]
            assert sealed.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
            assert sealed.size_bytes == path.stat().st_size

    def test_write_then_load_roundtrips_strict_equality(self, tmp_path: Path) -> None:
        """Write then load yields a strictly equal manifest model."""
        manifest = _manifest_for(_write_assets(tmp_path / "assets"))
        output = write_manifest(manifest, tmp_path / "out" / MANIFEST_ASSET_NAME)
        assert load_manifest(output) == manifest

    def test_build_refuses_empty_asset_set(self) -> None:
        """An empty draft cannot be sealed."""
        with pytest.raises(EvidenceReleaseError, match="at least one asset"):
            _manifest_for({})

    def test_build_refuses_sealing_the_manifest_itself(self, tmp_path: Path) -> None:
        """The manifest asset is never part of its own seal."""
        rogue = tmp_path / MANIFEST_ASSET_NAME
        rogue.write_text("{}", encoding="utf-8")
        with pytest.raises(EvidenceReleaseError, match="never seals itself"):
            _manifest_for({rogue.name: rogue})

    def test_load_refuses_unknown_fields_and_bad_shapes(self, tmp_path: Path) -> None:
        """extra=forbid rejects a manifest carrying an undeclared field."""
        manifest = _manifest_for(_write_assets(tmp_path / "assets"))
        payload = json.loads(manifest.model_dump_json())
        payload["runner_name"] = "gw-workstation"
        corrupted = tmp_path / "corrupted.json"
        corrupted.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValidationError):
            load_manifest(corrupted)


class TestVerifyDownloadedAssets:
    """Layered verification over real hashed files and API records."""

    def _verify(self, manifest: EvidenceReleaseManifest, downloaded: dict[str, Path], **overrides: object) -> list[str]:
        arguments: dict[str, object] = {
            "manifest": manifest,
            "run_record": _run_record(),
            "release_record": _release_record(),
            "downloaded": downloaded,
            "expect_run_id": _RUN_ID,
            "expect_workflow": _WORKFLOW,
            "repository": _REPO,
            "require_complete": True,
        }
        arguments.update(overrides)
        return verify_downloaded_assets(**arguments)  # type: ignore[arg-type]

    def test_untampered_download_fully_verifies(self, tmp_path: Path) -> None:
        """An untampered, complete download yields zero mismatches."""
        assets = _write_assets(tmp_path / "assets")
        assert self._verify(_manifest_for(assets), assets) == []

    def test_tampered_asset_byte_fails_at_hash_time(self, tmp_path: Path) -> None:
        """A single flipped byte is named as a sha256 mismatch."""
        assets = _write_assets(tmp_path / "assets")
        manifest = _manifest_for(assets)
        cohort = assets["cadrumo-release-cohort.tar.gz"]
        cohort.write_bytes(cohort.read_bytes() + b"\x00")
        mismatches = self._verify(manifest, assets)
        assert any("sha256" in line and "cadrumo-release-cohort.tar.gz" in line for line in mismatches)

    def test_substituted_unsealed_asset_is_refused(self, tmp_path: Path) -> None:
        """An asset absent from the manifest is refused by name."""
        assets = _write_assets(tmp_path / "assets")
        manifest = _manifest_for(assets)
        rogue = tmp_path / "assets" / "rogue.json"
        rogue.write_text("{}", encoding="utf-8")
        mismatches = self._verify(manifest, {**assets, rogue.name: rogue})
        assert any("not sealed in the manifest" in line for line in mismatches)

    def test_missing_sealed_asset_fails_completeness(self, tmp_path: Path) -> None:
        """A sealed asset missing from a complete download is named."""
        assets = _write_assets(tmp_path / "assets")
        manifest = _manifest_for(assets)
        partial = dict(assets)
        partial.pop("cadrumo-release-cohort.tar.gz")
        mismatches = self._verify(manifest, partial)
        assert any("absent from the download" in line for line in mismatches)

    def test_pattern_scoped_verification_tolerates_absent_siblings(self, tmp_path: Path) -> None:
        """Pattern-scoped verification skips the completeness check only."""
        assets = _write_assets(tmp_path / "assets")
        manifest = _manifest_for(assets)
        only_cohort = {"cadrumo-release-cohort.tar.gz": assets["cadrumo-release-cohort.tar.gz"]}
        assert self._verify(manifest, only_cohort, require_complete=False) == []

    @pytest.mark.parametrize(
        ("field", "value", "needle"),
        (
            ("conclusion", "failure", "conclusion"),
            ("path", ".github/workflows/other.yml", "workflow path"),
            ("head_sha", "f" * 40, "head_sha"),
            ("run_attempt", 2, "run_attempt"),
            ("event", "workflow_dispatch", "event"),
            ("head_branch", "feature", "head_branch"),
        ),
    )
    def test_manifest_api_disagreement_is_named(self, tmp_path: Path, field: str, value: object, needle: str) -> None:
        """Every manifest-vs-API field drift is surfaced with its field named."""
        assets = _write_assets(tmp_path / "assets")
        manifest = _manifest_for(assets)
        run_record = _run_record()
        run_record[field] = value
        release_record = _release_record()
        if field == "head_sha":
            release_record["targetCommitish"] = value
        mismatches = self._verify(manifest, assets, run_record=run_record, release_record=release_record)
        assert mismatches, field
        assert any(needle in line for line in mismatches), (field, mismatches)

    def test_release_not_bound_to_run_commit_is_refused(self, tmp_path: Path) -> None:
        """target_commitish must equal the run's head_sha."""
        assets = _write_assets(tmp_path / "assets")
        release_record = _release_record()
        release_record["targetCommitish"] = "e" * 40
        mismatches = self._verify(_manifest_for(assets), assets, release_record=release_record)
        assert any("target_commitish" in line for line in mismatches)

    def test_non_draft_evidence_release_is_refused(self, tmp_path: Path) -> None:
        """A published (non-draft) evidence release fails verification."""
        assets = _write_assets(tmp_path / "assets")
        release_record = _release_record()
        release_record["isDraft"] = False
        mismatches = self._verify(_manifest_for(assets), assets, release_record=release_record)
        assert any("must be a draft" in line for line in mismatches)


def _gc_release_listing() -> list[dict[str, object]]:
    drafts = [
        {"tag_name": f"evidence-smoke-{100 + n}", "draft": True, "created_at": f"2026-07-{n:02d}T00:00:00Z"}
        for n in range(1, 6)
    ]
    return [
        *drafts,
        {"tag_name": "evidence-scoop-900", "draft": True, "created_at": "2026-06-01T00:00:00Z"},
        {"tag_name": "v0.2.1", "draft": False, "created_at": "2026-07-10T00:00:00Z"},
        {"tag_name": "v9.9.9", "draft": True, "created_at": "2000-01-01T00:00:00Z"},
        {"tag_name": "evidence-smoke-999", "draft": False, "created_at": "2026-01-01T00:00:00Z"},
    ]


class TestGcPlan:
    """Deterministic retention planning over a mixed release listing."""

    def test_keeps_newest_three_per_lane_and_never_sees_real_releases(self) -> None:
        """K=3 per lane; v* and non-draft records are invisible to the plan."""
        plan = plan_evidence_gc(_gc_release_listing(), keep_per_lane=3)
        assert set(plan.delete) == {"evidence-smoke-101", "evidence-smoke-102"}
        assert "evidence-scoop-900" in plan.kept
        touched = set(plan.kept) | set(plan.delete)
        assert "v0.2.1" not in touched
        assert "v9.9.9" not in touched  # a draft outside the namespace is invisible
        assert "evidence-smoke-999" not in touched  # a published evidence-tag is not a draft candidate

    def test_promotion_referenced_tag_survives_beyond_the_keep_window(self) -> None:
        """A protected tag is kept even past the keep window."""
        plan = plan_evidence_gc(
            _gc_release_listing(),
            keep_per_lane=3,
            protected_tags=frozenset({"evidence-smoke-101"}),
        )
        assert "evidence-smoke-101" in plan.kept
        assert set(plan.delete) == {"evidence-smoke-102"}

    def test_refuses_a_zero_keep_window(self) -> None:
        """keep_per_lane below 1 is refused."""
        with pytest.raises(EvidenceReleaseError, match="at least 1"):
            plan_evidence_gc([], keep_per_lane=0)


def _write_stub_gh(bin_dir: Path, fixture: Path) -> Path:
    """Write a real executable ``gh`` stub driven by a baked-in fixture directory.

    ``api actions/runs/<id>`` serves ``run.json``; ``release view`` serves
    ``release.json``; ``release download`` copies real bytes from ``assets/``
    honoring ``--pattern``; ``api .../releases...`` serves ``releases.jsonl``;
    ``release delete`` appends the tag to ``deleted.log``. Everything is a real
    subprocess doing real file IO — nothing in the module under test is mocked.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    fixture.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "gh_stub.py"
    script.write_text(
        f"""
import fnmatch, json, shutil, sys
from pathlib import Path

fixture = Path({str(fixture)!r})
args = sys.argv[1:]
with (fixture / "calls.log").open("a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if args[0] == "api" and "actions/runs/" in args[1]:
    sys.stdout.write((fixture / "run.json").read_text(encoding="utf-8"))
elif args[:2] == ["release", "view"]:
    sys.stdout.write((fixture / "release.json").read_text(encoding="utf-8"))
elif args[:2] == ["release", "download"]:
    destination = Path(args[args.index("--dir") + 1])
    destination.mkdir(parents=True, exist_ok=True)
    pattern = args[args.index("--pattern") + 1] if "--pattern" in args else "*"
    copied = 0
    for path in sorted((fixture / "assets").iterdir()):
        if fnmatch.fnmatch(path.name, pattern):
            shutil.copy2(path, destination / path.name)
            copied += 1
    if copied == 0:
        sys.stderr.write("no assets match " + pattern)
        raise SystemExit(1)
elif args[:2] == ["release", "delete"]:
    with (fixture / "deleted.log").open("a", encoding="utf-8") as log:
        log.write(args[2] + "\\n")
elif args[0] == "api" and "releases" in args[1]:
    sys.stdout.write((fixture / "releases.jsonl").read_text(encoding="utf-8"))
else:
    sys.stderr.write("unexpected gh invocation: " + repr(args))
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    if sys.platform.startswith("win"):
        launcher = bin_dir / "gh.bat"
        launcher.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\nexit /b %errorlevel%\r\n',
            encoding="utf-8",
        )
    else:
        launcher = bin_dir / "gh"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return launcher


class TestCliEndToEnd:
    """CLI subcommands driven end to end through a real stub gh subprocess."""

    def _seed_fixture(self, tmp_path: Path) -> tuple[Path, Path]:
        fixture = tmp_path / "fixture"
        assets_dir = fixture / "assets"
        assets = _write_assets(assets_dir)
        manifest = _manifest_for(assets)
        write_manifest(manifest, assets_dir / MANIFEST_ASSET_NAME)
        (fixture / "run.json").write_text(json.dumps(_run_record()), encoding="utf-8")
        (fixture / "release.json").write_text(json.dumps(_release_record()), encoding="utf-8")
        # The release listing verify consults for the exactly-one-draft check.
        (fixture / "releases.jsonl").write_text(
            json.dumps(
                {"tag_name": f"evidence-smoke-{_RUN_ID}", "draft": True, "created_at": "2026-07-20T00:00:00Z"},
            )
            + "\n",
            encoding="utf-8",
        )
        gh = _write_stub_gh(tmp_path / "bin", fixture)
        return fixture, gh

    def test_verify_passes_on_untampered_draft(self, tmp_path: Path) -> None:
        """Verify exits 0 and lands the real asset bytes in the download dir."""
        fixture, gh = self._seed_fixture(tmp_path)
        del fixture
        exit_code = main(
            [
                "verify",
                "--tag",
                f"evidence-smoke-{_RUN_ID}",
                "--expect-run-id",
                _RUN_ID,
                "--expect-workflow",
                _WORKFLOW,
                "--download-dir",
                str(tmp_path / "download"),
                "--repo",
                _REPO,
                "--gh",
                str(gh),
            ],
        )
        assert exit_code == 0
        assert (tmp_path / "download" / "cadrumo-release-cohort.tar.gz").is_file()

    def test_verify_fails_hard_on_substituted_bytes(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify exits 1 naming the sha256 mismatch on substituted bytes."""
        fixture, gh = self._seed_fixture(tmp_path)
        tampered = fixture / "assets" / "cadrumo-release-cohort.tar.gz"
        tampered.write_bytes(b"substituted attacker bytes")
        exit_code = main(
            [
                "verify",
                "--tag",
                f"evidence-smoke-{_RUN_ID}",
                "--expect-run-id",
                _RUN_ID,
                "--expect-workflow",
                _WORKFLOW,
                "--download-dir",
                str(tmp_path / "download"),
                "--repo",
                _REPO,
                "--gh",
                str(gh),
            ],
        )
        assert exit_code == 1
        assert "sha256" in capsys.readouterr().err

    def test_verify_refuses_a_non_evidence_tag_before_any_download(self, tmp_path: Path) -> None:
        """A v* tag is refused before any transport happens."""
        _fixture, gh = self._seed_fixture(tmp_path)
        exit_code = main(
            [
                "verify",
                "--tag",
                "v0.2.1",
                "--expect-run-id",
                _RUN_ID,
                "--expect-workflow",
                _WORKFLOW,
                "--download-dir",
                str(tmp_path / "download"),
                "--repo",
                _REPO,
                "--gh",
                str(gh),
            ],
        )
        assert exit_code == 1

    def test_emit_manifest_seals_the_real_downloaded_bytes(self, tmp_path: Path) -> None:
        """emit-manifest hashes the stub-served bytes and excludes itself."""
        fixture, gh = self._seed_fixture(tmp_path)
        # The pre-seeded manifest asset must be excluded from its own seal.
        output = tmp_path / "sealed" / MANIFEST_ASSET_NAME
        exit_code = main(
            [
                "emit-manifest",
                "--tag",
                f"evidence-smoke-{_RUN_ID}",
                "--output",
                str(output),
                "--workflow-path",
                _WORKFLOW,
                "--run-id",
                _RUN_ID,
                "--run-attempt",
                "1",
                "--head-sha",
                _HEAD_SHA,
                "--head-branch",
                "main",
                "--event",
                "push",
                "--repo",
                _REPO,
                "--gh",
                str(gh),
            ],
        )
        assert exit_code == 0
        sealed = load_manifest(output)
        assert MANIFEST_ASSET_NAME not in sealed.assets
        for name, digest in sealed.assets.items():
            assert digest.sha256 == sha256_path(fixture / "assets" / name)

    def test_verify_refuses_duplicate_drafts_for_one_tag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Two drafts on one tag (the cli/cli#4270 race) refuse before any trust."""
        fixture, gh = self._seed_fixture(tmp_path)
        duplicate = {"tag_name": f"evidence-smoke-{_RUN_ID}", "draft": True, "created_at": "2026-07-20T01:00:00Z"}
        with (fixture / "releases.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(duplicate) + "\n")
        exit_code = main(
            [
                "verify",
                "--tag",
                f"evidence-smoke-{_RUN_ID}",
                "--expect-run-id",
                _RUN_ID,
                "--expect-workflow",
                _WORKFLOW,
                "--download-dir",
                str(tmp_path / "download"),
                "--repo",
                _REPO,
                "--gh",
                str(gh),
            ],
        )
        assert exit_code == 1
        assert "exactly one draft" in capsys.readouterr().err

    def test_gc_dry_run_deletes_nothing_and_apply_deletes_only_stale_drafts(self, tmp_path: Path) -> None:
        """Dry run deletes nothing; --apply deletes exactly the unprotected stale draft."""
        fixture, gh = self._seed_fixture(tmp_path)
        releases = _gc_release_listing()
        (fixture / "releases.jsonl").write_text(
            "\n".join(json.dumps(record) for record in releases) + "\n",
            encoding="utf-8",
        )
        base = ["gc", "--keep", "3", "--repo", _REPO, "--gh", str(gh)]

        assert main(base) == 0
        assert not (fixture / "deleted.log").exists()

        assert main([*base, "--apply", "--keep-tag", "evidence-smoke-101"]) == 0
        deleted = (fixture / "deleted.log").read_text(encoding="utf-8").split()
        assert deleted == ["evidence-smoke-102"]


class TestLeakSweep:
    """The fail-closed publication tripwire above the mint-time scrub."""

    def _attach_dir(self, tmp_path: Path) -> Path:
        directory = tmp_path / "attach"
        directory.mkdir()
        (directory / "python-linux-x86-64-row.json").write_text(
            json.dumps({"cwd": "C:\\Users\\scrubbed-user\\work", "status": "passed"}),
            encoding="utf-8",
        )
        (directory / "evidence-manifest-packaging.json").write_text(
            json.dumps({"workflow_path": ".github/workflows/packaging-smoke.yml"}),
            encoding="utf-8",
        )
        return directory

    def test_clean_publication_directory_passes(self, tmp_path: Path) -> None:
        """Scrubbed rows and manifests sweep clean and exit 0."""
        directory = self._attach_dir(tmp_path)
        assert main(["leak-sweep", "--directory", str(directory)]) == 0

    def test_leaking_json_field_refuses_naming_the_asset(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A home-dir username anywhere in a JSON asset refuses the publication."""
        directory = self._attach_dir(tmp_path)
        (directory / "rogue-row.json").write_text(
            json.dumps({"novel_field": {"deep": ["/home/gwuser/.local/state"]}}),
            encoding="utf-8",
        )
        assert main(["leak-sweep", "--directory", str(directory)]) == 1
        err = capsys.readouterr().err
        assert "rogue-row.json" in err
        assert "gwuser" in err

    def test_leaking_plain_text_asset_is_caught_too(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Non-JSON text assets (archived transcripts) are scanned line-wise."""
        directory = self._attach_dir(tmp_path)
        (directory / "transcript.log").write_text("ran under C:\\Users\\hiddenop\\workdir\n", encoding="utf-8")
        assert main(["leak-sweep", "--directory", str(directory)]) == 1
        assert "transcript.log" in capsys.readouterr().err

    def test_explicit_machine_token_is_refused(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A named hostname token anywhere in the payload refuses publication."""
        directory = self._attach_dir(tmp_path)
        (directory / "notes.txt").write_text("built on gw-workstation runner\n", encoding="utf-8")
        assert main(["leak-sweep", "--directory", str(directory), "--token", "gw-workstation"]) == 1
        assert "notes.txt" in capsys.readouterr().err

    def test_missing_directory_is_a_hard_error(self, tmp_path: Path) -> None:
        """Sweeping nothing is never success — an absent directory refuses."""
        assert main(["leak-sweep", "--directory", str(tmp_path / "absent")]) == 1
