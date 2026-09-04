"""Tripwire tests for the release-please LOCAL-only workflow.

These tests validate the project-meta files that drive `just release`:

- ``release-please-config.json``
- ``.release-please-manifest.json``
- ``CHANGELOG.md``
- the three version surfaces (``pyproject.toml``,
  ``src/cadrumo/__init__.py``, ``.release-please-manifest.json``)
  agree.

The test lives in ``src/cadrumo/tests/`` rather than alongside any
``cadrumo.*`` runtime subpackage because it validates project-meta
files that do not belong to a runtime module.

Per the project pydantic mandate, the JSON payloads are parsed into
strict pydantic v2 models so typos in either config file are caught
as test failures rather than silent drift.

See Also:
    :func:`~tests._inventory.repo_path`
        Resolves repository-root release metadata without depending on the
        current working directory.
    ``RELEASING.md``
        Human release procedure that cites the same checklist, soak, and
        rollback surfaces validated here.
    ``docs/_release_checklist.yaml``
        Machine-readable release-readiness contract parsed into strict models
        by this module.
    ``docs/_release_notes_template.md``
        Human release-body template required by the checklist.
"""

from __future__ import annotations

import json
import re
import tomllib

import pytest
import yaml
from pydantic import BaseModel, ConfigDict, Field

from .inventory import repo_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

CONFIG_PATH = repo_path("release-please-config.json")
MANIFEST_PATH = repo_path(".release-please-manifest.json")
CHANGELOG_PATH = repo_path("CHANGELOG.md")
PYPROJECT_PATH = repo_path("pyproject.toml")
INIT_PATH = repo_path("src/cadrumo/__init__.py")
RELEASE_CHECKLIST_PATH = repo_path("docs/_release_checklist.yaml")
RELEASE_NOTES_TEMPLATE_PATH = repo_path("docs/_release_notes_template.md")
RELEASING_PATH = repo_path("RELEASING.md")


class ChangelogSection(BaseModel):
    """One entry in ``release-please-config.json``'s changelog-sections list."""

    model_config = ConfigDict(extra="forbid")

    type: str
    section: str
    hidden: bool = False


class ReleasePleasePackage(BaseModel):
    """Per-package block under ``packages`` in the release-please config."""

    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(alias="package-name")
    release_type: str = Field(alias="release-type")
    changelog_path: str = Field(alias="changelog-path")
    extra_files: list[str] = Field(default_factory=list, alias="extra-files")


class ReleasePleaseConfig(BaseModel):
    """Full shape of ``release-please-config.json``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_url: str | None = Field(default=None, alias="$schema")
    #: Caps how far back release-please walks commit history on its very
    #: first run against this repo (no release pull request it generated has
    #: ever merged): full 40-char commit SHA only, top-level-only per
    #: release-please's own docs. Release-please ignores this key once a
    #: release pull request it generated has merged, so it is safe to remove
    #: after that point rather than something this schema must keep forever.
    bootstrap_sha: str | None = Field(default=None, alias="bootstrap-sha")
    release_type: str = Field(alias="release-type")
    include_component_in_tag: bool = Field(alias="include-component-in-tag")
    separate_pull_requests: bool = Field(alias="separate-pull-requests")
    draft: bool
    prerelease: bool
    #: Whether a BREAKING CHANGE below 1.0.0 bumps the minor rather than
    #: jumping to a major. Declared explicitly because leaving it unset is not
    #: a neutral position: release-please defaults it to false, under which a
    #: breaking commit takes 0.x straight to 1.0.0 - and 1.0.0 is coupled by a
    #: tripwire to flipping COMPATIBILITY_REGIME to RELEASED, which freezes the
    #: per-format durability floors one way. The default would therefore decide
    #: a data-durability question on the evidence of a renamed CLI flag.
    bump_minor_pre_major: bool = Field(alias="bump-minor-pre-major")
    changelog_path: str = Field(alias="changelog-path")
    packages: dict[str, ReleasePleasePackage]
    changelog_sections: list[ChangelogSection] = Field(alias="changelog-sections")


class ReleasePleaseManifest(BaseModel):
    """Full shape of ``.release-please-manifest.json``."""

    model_config = ConfigDict(extra="forbid")

    root: str = Field(alias=".")


class SoakChecklist(BaseModel):
    """The RC-soak section of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    applies_to: str
    minimum_hours: int
    maximum_hours: int
    vehicle: str
    exit_gates: list[str]


class VersioningChecklist(BaseModel):
    """The versioning-discipline section of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    scheme: str
    pre_1_0_discipline: str
    post_1_0_discipline: str


class ChangelogChecklist(BaseModel):
    """The changelog-automation section of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    automation: str
    template: str


class HotfixCycleTimes(BaseModel):
    """Emergency hotfix cycle-time targets, in hours, by trigger category."""

    model_config = ConfigDict(extra="forbid")

    security_or_data_loss: int
    portal_drift: int
    other_critical: int


class HotfixChecklist(BaseModel):
    """The hotfix section of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    cycle_times_hours: HotfixCycleTimes


class RollbackChecklist(BaseModel):
    """The rollback section of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    triggers: list[str]
    procedure_ref: str
    mechanism: str


class AuditStateGateChecklist(BaseModel):
    """The audit-state-gate section of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    description: str
    checks: list[str]


class ReleaseChecklist(BaseModel):
    """Full shape of ``docs/_release_checklist.yaml``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    soak: SoakChecklist
    versioning: VersioningChecklist
    changelog: ChangelogChecklist
    hotfix: HotfixChecklist
    rollback: RollbackChecklist
    audit_state_gate: AuditStateGateChecklist


_VERSION_RE: re.Pattern[str] = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


def _read_pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _read_init_version() -> str:
    match = _VERSION_RE.search(INIT_PATH.read_text(encoding="utf-8"))
    assert match, f"__version__ not found in {INIT_PATH}"
    version = match.group(1)
    if not isinstance(version, str):
        raise AssertionError("version regex returned a non-string value")
    return version


@pytest.fixture(scope="module")
def release_checklist() -> ReleaseChecklist:
    """Return the strict release checklist model once for this module."""
    payload = yaml.safe_load(RELEASE_CHECKLIST_PATH.read_text(encoding="utf-8"))
    return ReleaseChecklist.model_validate(payload)


def test_release_please_config_is_well_formed() -> None:
    """``release-please-config.json`` parses as the strict pydantic model."""
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config = ReleasePleaseConfig.model_validate(payload)

    assert config.release_type == "python"
    assert config.changelog_path == "CHANGELOG.md"
    # Pinned, not merely declared. release-please defaults this to false, under
    # which a BREAKING CHANGE takes 0.x straight to 1.0.0 - and the compatibility
    # tripwire couples 1.0.0 to flipping COMPATIBILITY_REGIME to RELEASED, which
    # freezes the per-format durability floors one way with no rollback in code.
    # Accepting the key without pinning its value would let a silent flip back to
    # false re-arm that path, so the decision is asserted here rather than left to
    # whatever the tool defaults to.
    assert config.bump_minor_pre_major is True, (
        "bump-minor-pre-major must stay true while COMPATIBILITY_REGIME is PRE_RELEASE: "
        "flipping it lets a breaking commit cut 1.0.0, which the compatibility tripwire "
        "treats as a released-data durability commitment"
    )
    # No release-please-generated release has ever merged on this repo (its
    # very first automated bump has not run yet), so bootstrap-sha must be
    # present and a full 40-char commit SHA -- without it, release-please
    # finds no GitHub Release matching the manifest's recorded version and
    # falls back to walking the entire commit history one commit at a time,
    # which measurably times out against this repo's real history.
    assert config.bootstrap_sha is not None, (
        "bootstrap-sha must stay set until release-please's first generated release pull request merges"
    )
    assert re.fullmatch(r"[0-9a-f]{40}", config.bootstrap_sha), "bootstrap-sha must be a full 40-char commit SHA"

    assert "." in config.packages
    root_pkg = config.packages["."]
    assert root_pkg.package_name == "cadrumo"
    assert root_pkg.release_type == "python"
    assert "src/cadrumo/__init__.py" in root_pkg.extra_files

    types = {section.type for section in config.changelog_sections}
    # The project-relevant commit types must all have a rendering decision
    # (visible or hidden), never absent.
    required_types = {
        "feat",
        "fix",
        "perf",
        "revert",
        "docs",
        "refactor",
        "chore",
        "test",
        "build",
        "ci",
        "style",
    }
    missing = required_types - types
    assert not missing, f"changelog-sections missing types: {sorted(missing)}"


def test_release_please_manifest_is_well_formed() -> None:
    """``.release-please-manifest.json`` parses as the strict model."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # Single-key manifest — no extra packages allowed.
    assert list(payload.keys()) == ["."], f"manifest must have exactly one key '.', got {list(payload.keys())!r}"
    manifest = ReleasePleaseManifest.model_validate(payload)
    assert manifest.root  # non-empty


def test_changelog_exists_and_non_empty() -> None:
    """``CHANGELOG.md`` exists at the repo root and is non-empty."""
    assert CHANGELOG_PATH.is_file(), f"{CHANGELOG_PATH} is missing"
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert text.strip(), "CHANGELOG.md is empty"
    assert "# Changelog" in text


def test_version_surfaces_agree() -> None:
    """pyproject.toml, ``__init__.py``, and the manifest agree on one version."""
    pyproject_version = _read_pyproject_version()
    init_version = _read_init_version()
    manifest_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_version = manifest_payload["."]

    assert pyproject_version == init_version == manifest_version, (
        f"version drift: pyproject={pyproject_version!r}, __init__={init_version!r}, manifest={manifest_version!r}"
    )


def test_the_release_path_workflows_exist() -> None:
    """The release path runs on the forge, and both halves of it must be present.

    A release is cut by merging the release pull request: `release-please.yml`
    computes the version, writes the changelog, tags, creates the release and
    dispatches `publish.yml`, which builds the distributions from that tag and
    uploads them. Neither half is optional, and a missing one does not fail a
    step — it removes the trigger, so nothing runs and nothing reports.
    """
    for relative in (".github/workflows/release-please.yml", ".github/workflows/publish.yml"):
        workflow = repo_path(relative)
        assert workflow.is_file(), f"{workflow} is missing; the release path cannot run without it"


def test_release_checklist_is_well_formed(release_checklist: ReleaseChecklist) -> None:
    """``docs/_release_checklist.yaml`` parses as the strict pydantic model.

    Machine-validates the RC-soak window, versioning discipline, hotfix
    cycle times, and rollback triggers the audit-state gate and RELEASING.md
    both cite — a typo or dropped section here silently breaks the gate's
    contract with the printed rollback/soak procedure.
    """
    assert release_checklist.schema_version == 1
    assert 0 < release_checklist.soak.minimum_hours <= release_checklist.soak.maximum_hours
    assert release_checklist.rollback.triggers, "rollback.triggers must not be empty"
    assert release_checklist.audit_state_gate.checks, "audit_state_gate.checks must not be empty"
    # The hotfix cycle times must be a strictly increasing severity ladder:
    # security/data-loss is the fastest, other-critical the slowest.
    times = release_checklist.hotfix.cycle_times_hours
    assert times.security_or_data_loss <= times.portal_drift <= times.other_critical


def test_release_notes_template_exists_and_is_referenced(release_checklist: ReleaseChecklist) -> None:
    """The release-notes template exists and the checklist points at it."""
    assert RELEASE_NOTES_TEMPLATE_PATH.is_file(), f"{RELEASE_NOTES_TEMPLATE_PATH} is missing"
    text = RELEASE_NOTES_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert text.strip()

    assert release_checklist.changelog.template == "docs/_release_notes_template.md"


def test_releasing_doc_matches_the_executable_release_entry_and_recovery() -> None:
    """The operator guide must describe the executable path, not retired ceremony.

    Every string below names a surface that exists: a workflow the forge runs, a
    recipe the justfile defines, or a declaration file the readiness gate reads.
    The guide is the only place an operator learns the order they run in, so a
    live surface missing from it is as much a defect as a retired one left in.
    """
    text = RELEASING_PATH.read_text(encoding="utf-8")

    # The executable path: merge the release PR, then the two workflows it drives.
    assert "release PR" in text
    assert "release-please.yml" in text
    assert "publish.yml" in text

    # Evidence is minted by a dispatched campaign, and only ever off the release
    # branch — the readiness gate binds each evidence row to the checked-out
    # commit and to `v<VERSION>`, which a campaign run on the default branch
    # cannot satisfy.
    assert "packaging-smoke.yml" in text

    # Live local surfaces the guide must still route the operator to.
    assert "## Diagnose and recover" in text
    assert "just release-readiness" in text
    assert "just release-rollback" in text
    assert "docs/_release_checklist.yaml" in text

    # Retired ceremony. The orchestrator workflow, its dry-run flag and its
    # resume argument were removed with the workflow itself; a guide still
    # naming them sends an operator to a command that does not exist.
    for retired in ("release-orchestrator.yml", "dry_run", "resume_packaging_run_id", "release-candidate soak"):
        assert retired not in text.lower(), f"the guide still describes retired ceremony: {retired}"
