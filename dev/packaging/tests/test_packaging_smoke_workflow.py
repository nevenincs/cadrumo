"""Structural gate for the Cadrumo packaging-smoke GitHub workflow."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "packaging-smoke.yml"
_SHELL_COMMAND_BOUNDARY = r"(?:^|[\r\n]|&&|\|\||[;|])"
_ENVIRONMENT_PREFIX = r"(?:(?:env\s+)?(?:[A-Za-z_]\w*=(?:[^\s;&|]+|\"[^\"]*\"|'[^']*')\s+)+)"
_UV_RUN_PREFIX = r"(?:uv\s+run(?:\s+--[a-z][\w-]*(?:=(?:[^\s;&|]+|\"[^\"]*\"|'[^']*'))?)*\s+)?"
_PROHIBITED_CADRUMO_HUMAN_COMMAND = re.compile(
    rf"(?im){_SHELL_COMMAND_BOUNDARY}[ \t]*(?:{_ENVIRONMENT_PREFIX})?{_UV_RUN_PREFIX}cadrumo(?=\s|$|[;&|])",
)
_PROHIBITED_AEAT_PRODUCT_FORMS = (
    (
        "python-import",
        re.compile(
            r"""(?i)\b(?:from\s+aeat(?:\.|\s+import\b)|import\s+(?:[a-z_]\w*(?:\.[a-z_]\w*)*\s*,\s*)*aeat(?:\.|(?=\s|$|[;"'])))""",
        ),
    ),
    (
        "python-module",
        re.compile(r"(?i)\bpython(?:\d+(?:\.\d+)*)?\s+-m\s+aeat(?:\.[a-z_]\w*)*(?=\s|$)"),
    ),
    (
        "distribution-install",
        re.compile(
            r"""(?i)\b(?:(?:uv\s+)?pip\s+install|uv\s+add)\b[^&|;\r\n]*?(?<![\w-])aeat(?=\[|\s|$|[<>=!~@;"'])""",
        ),
    ),
    (
        "former-distribution",
        re.compile(r"(?i)(?<![\w-])aeat(?:-cli|-data(?:-[\w-]+)?|_data(?:_[\w-]+)?)(?![\w-])"),
    ),
    (
        "former-source-path",
        re.compile(r"(?i)(?<![\w])(?:src|packaging)[/\\]aeat(?:[/\\_.-]|$)"),
    ),
)


def _prohibited_aeat_product_forms(surface: str) -> tuple[str, ...]:
    """Return prohibited former-product form families present in ``surface``."""
    return tuple(label for label, pattern in _PROHIBITED_AEAT_PRODUCT_FORMS if pattern.search(surface))


# The Windows and macOS legs prove the python-windows-x86-64 and
# python-macos-arm64 distribution rows on native SELF-HOSTED runners (operator
# cost directive 2026-07-19: hosted minutes bill, the operator's own machines
# are free; the label sets are the runner registration contract). Each runs the
# host-portable `packaging-smoke` aggregate (no Docker, no host package-manager
# lanes) and publishes per-OS evidence-draft assets so names never collide with
# the Ubuntu leg (release-asset transport, not Actions artifact storage).
_PORTABLE_LEGS: dict[str, dict[str, object]] = {
    "cadrumo-packaging-smoke-windows": {
        "name": "Cadrumo / Windows / Python 3.13 / wheel artifacts",
        "runs_on": ["self-hosted", "Windows", "X64"],
        "cohort_asset": "cadrumo-python-cohort-windows.tar.gz",
        "evidence_asset": "packaging-smoke-evidence-windows.tar.gz",
    },
    "cadrumo-packaging-smoke-macos": {
        "name": "Cadrumo / macOS / Python 3.13 / wheel artifacts",
        "runs_on": ["self-hosted", "macOS", "ARM64"],
        "cohort_asset": "cadrumo-python-cohort-macos.tar.gz",
        "evidence_asset": "packaging-smoke-evidence-macos.tar.gz",
    },
}
_COHORT_PUBLISH_STEP: Final = "Archive the tested Cadrumo Python cohort"
_EVIDENCE_PUBLISH_STEP: Final = "Stage Cadrumo packaging smoke evidence"


def _run_command_lines(job: dict[str, object]) -> set[str]:
    """Return every non-empty command line across the job's run scripts.

    A step's ``run`` may be a multi-line script (the campaign step wraps the
    canonical aggregate invocation with a resource sampler), so the canonical
    command contract is asserted line-wise rather than against whole scripts.
    """
    steps = job["steps"]
    assert isinstance(steps, list)
    return {
        line.strip()
        for step in steps
        if isinstance(step, dict)
        for line in str(step.get("run", "")).splitlines()
        if line.strip()
    }


def _assert_single_release_cohort_builder(document: dict[str, object]) -> None:
    """Require exactly one protected release-cohort construction job."""
    jobs = document["jobs"]
    assert isinstance(jobs, dict)
    builders = [
        (name, job)
        for name, job in jobs.items()
        if isinstance(job, dict)
        and "uv run --no-sync python -m dev.packaging.release_cohort build --output var/release-cohort"
        in _run_command_lines(job)
    ]
    assert len(builders) == 1, f"expected exactly one release-cohort builder, found {len(builders)}"
    name, builder = builders[0]
    assert name == "build-release-cohort"
    assert "strategy" not in builder


def test_immutable_cohort_is_built_once_and_every_python_row_binds_it() -> None:
    """One build-release-cohort job; three per-OS oracle+emit legs bind that cohort."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    jobs = document["jobs"]
    _assert_single_release_cohort_builder(document)

    # One dedicated cohort build that publishes the single immutable archive to
    # the run's own Actions artifacts.
    build = jobs["build-release-cohort"]
    assert build["runs-on"] == ["self-hosted", "Linux", "X64"]
    checkout = next(step for step in build["steps"] if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0
    build_commands = _run_command_lines(build)
    assert "uv run --no-sync python -m dev.packaging.release_cohort build --output var/release-cohort" in build_commands
    build_surface = "\n".join(str(step.get("run", "")) for step in build["steps"] if "run" in step)
    assert "cadrumo-release-cohort.tar.gz" in build_surface
    build_uses = "\n".join(str(step.get("uses", "")) for step in build["steps"])
    assert "actions/upload-artifact@" in build_uses
    # Deterministic archive per the ratified transport decision.
    assert "--sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner" in build_surface

    # Each OS leg needs the ONE build (so all rows bind one cohort id),
    # downloads that cohort archive from the run's artifacts, and emits its
    # exact python-<os> row via the emitter tool as its own artifact.
    legs = {
        "oracle-emit-linux": ("python-linux-x86-64", ["self-hosted", "Linux", "X64"]),
        "oracle-emit-windows": ("python-windows-x86-64", ["self-hosted", "Windows", "X64"]),
        "oracle-emit-macos": ("python-macos-arm64", ["self-hosted", "macOS", "ARM64"]),
    }
    for job_name, (row_id, runs_on) in legs.items():
        leg = jobs[job_name]
        assert leg["needs"] == "build-release-cohort"
        assert leg["runs-on"] == runs_on
        surface = "\n".join(str(step.get("run", "")) for step in leg["steps"] if "run" in step)
        assert "dev.packaging.oracle_emit_cohort" in surface
        assert f"--row-id {row_id}" in surface
        assert "--release-cohort-dir var/release-cohort" in surface
        assert "cadrumo-release-cohort.tar.gz" in surface
        assert "gh release" not in surface
        leg_uses = "\n".join(str(step.get("uses", "")) for step in leg["steps"])
        assert "actions/download-artifact@" in leg_uses
        assert "actions/upload-artifact@" in leg_uses


def test_protected_cohort_builder_gate_has_detector_teeth() -> None:
    """A second release-cohort builder cannot hide behind the protected lane."""
    document = deepcopy(yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8")))
    document["jobs"]["duplicate-builder"] = deepcopy(document["jobs"]["build-release-cohort"])
    with pytest.raises(AssertionError, match="exactly one"):
        _assert_single_release_cohort_builder(document)


def test_workflow_runs_canonical_cadrumo_packaging_gates() -> None:
    """One Ubuntu aggregate plus native Windows/macOS host-portable legs."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo Packaging Smoke"
    assert set(document["jobs"]) == {
        "cadrumo-packaging-smoke",
        *_PORTABLE_LEGS,
        "build-release-cohort",
        "oracle-emit-linux",
        "oracle-emit-windows",
        "oracle-emit-macos",
        # Not a campaign leg: it fails the run fast when a native leg's runner
        # is offline, which would otherwise queue rather than go red.
        "runner-queue-watchdog",
    }

    job = document["jobs"]["cadrumo-packaging-smoke"]
    assert job["name"] == "Cadrumo / Ubuntu / Python 3.13 / wheel artifacts"
    assert job["runs-on"] == ["self-hosted", "Linux", "X64"]
    commands = _run_command_lines(job)
    # The Ubuntu leg captures the aggregate's exit status (`|| status=$?`) so the
    # evidence checkpoint still runs when the gate fails, so the canonical gate is
    # asserted as a line prefix rather than an exact match.
    assert any(line == "just packaging-smoke-ci" or line.startswith("just packaging-smoke-ci ") for line in commands)
    assert "uv run --no-sync python -m dev.packaging.evidence" in commands
    assert "just packaging-smoke-linux" not in commands
    assert "just packaging-smoke-split" not in commands
    assert "just packaging-smoke-docker" not in commands

    for key, spec in _PORTABLE_LEGS.items():
        leg = document["jobs"][key]
        assert leg["name"] == spec["name"]
        assert leg["runs-on"] == spec["runs_on"]
        leg_commands = _run_command_lines(leg)
        # The portable legs run the host-portable aggregate and the same
        # evidence checkpoint, and never the Ubuntu-only CI / Docker / Linux
        # lanes (Docker is ubuntu-only; the browser-linux lane installs host
        # system deps). `just packaging-smoke` is an exact run line here, not a
        # prefix of `just packaging-smoke-ci`.
        assert {
            "just packaging-smoke",
            "uv run --no-sync python -m dev.packaging.evidence",
        } <= leg_commands
        assert "just packaging-smoke-ci" not in leg_commands
        assert "just packaging-smoke-linux" not in leg_commands
        assert "just packaging-smoke-docker" not in leg_commands
        # The Linux-only disk reclamation and bash resource sampler never run on
        # the portable legs.
        assert not any(step.get("name") == "Reclaim runner disk space" for step in leg["steps"])


def test_workflow_evidence_and_product_identity_follow_the_binding_tuple() -> None:
    """Labels use Cadrumo, assets use cadrumo, and commands keep the aeat boundary."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["cadrumo-packaging-smoke"]
    cohort_publish = next(step for step in job["steps"] if step.get("name") == _COHORT_PUBLISH_STEP)
    evidence_publish = next(step for step in job["steps"] if step.get("name") == _EVIDENCE_PUBLISH_STEP)
    campaign = next(step for step in job["steps"] if "just packaging-smoke-ci" in str(step.get("run", "")))
    checkpoint = next(
        step for step in job["steps"] if step.get("run") == "uv run --no-sync python -m dev.packaging.evidence"
    )

    assert "cadrumo-python-cohort-linux.tar.gz" in cohort_publish["run"]
    assert "var/packaging-smoke-cohort/python" in cohort_publish["run"]
    assert "packaging-smoke-evidence-linux.tar.gz" in evidence_publish["run"]
    assert "var/packaging-smoke-evidence" in evidence_publish["run"]
    assert "installed-cohorts" in evidence_publish["run"]
    assert checkpoint["if"] == "always()"
    assert evidence_publish["if"] == "always()"
    assert job["steps"].index(campaign) < job["steps"].index(checkpoint)
    assert job["steps"].index(checkpoint) < job["steps"].index(cohort_publish)
    assert job["steps"].index(cohort_publish) < job["steps"].index(evidence_publish)

    # Each portable leg carries its own campaign, evidence checkpoint, and
    # per-OS draft publishes in the same campaign -> checkpoint -> cohort ->
    # evidence order, with per-OS asset names that never collide.
    for key, spec in _PORTABLE_LEGS.items():
        leg = document["jobs"][key]
        leg_cohort = next(s for s in leg["steps"] if s.get("name") == _COHORT_PUBLISH_STEP)
        leg_evidence = next(s for s in leg["steps"] if s.get("name") == _EVIDENCE_PUBLISH_STEP)
        leg_campaign = next(s for s in leg["steps"] if s.get("run") == "just packaging-smoke")
        leg_checkpoint = next(
            s for s in leg["steps"] if s.get("run") == "uv run --no-sync python -m dev.packaging.evidence"
        )
        assert str(spec["cohort_asset"]) in leg_cohort["run"]
        assert str(spec["evidence_asset"]) in leg_evidence["run"]
        assert leg_checkpoint["if"] == "always()"
        assert leg_evidence["if"] == "always()"
        assert leg["steps"].index(leg_campaign) < leg["steps"].index(leg_checkpoint)
        assert leg["steps"].index(leg_checkpoint) < leg["steps"].index(leg_cohort)
        assert leg["steps"].index(leg_cohort) < leg["steps"].index(leg_evidence)

    # Every published asset name across the parallel jobs is unique on the ONE
    # shared draft: a collision would silently --clobber a sibling's asset.
    asset_names = re.findall(
        r"(?:cadrumo-python-cohort|packaging-smoke-evidence)-(?:linux|windows|macos)\.tar\.gz",
        _WORKFLOW.read_text(encoding="utf-8"),
    )
    per_leg_assets = {name for name in asset_names}
    assert len(per_leg_assets) == 6, sorted(per_leg_assets)

    # The identity boundary holds across every job: labels use Cadrumo/cadrumo
    # and no command turns cadrumo into a human executable or revives an aeat
    # product form.
    label_lines = [document["name"]]
    command_lines = []
    for one_job in document["jobs"].values():
        label_lines.append(str(one_job["name"]))
        for step in one_job["steps"]:
            label_lines.append(str(step.get("name", "")))
            if "run" in step:
                command_lines.append(str(step["run"]))
    assert "aeat" not in "\n".join(label_lines).casefold()
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search("\n".join(command_lines)) is None

    assert _prohibited_aeat_product_forms(_WORKFLOW.read_text(encoding="utf-8")) == ()


@pytest.mark.parametrize(
    "surface",
    (
        "aeat --version",
        "uv run --no-sync aeat app registry verify",
        "echo 'AEAT is the Spanish tax authority'",
        "pip install cadrumo && aeat --version",
    ),
)
def test_binding_cli_and_authority_forms_are_allowed(surface: str) -> None:
    """The human CLI and Spanish-authority referent remain valid contexts."""
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search(surface) is None
    assert _prohibited_aeat_product_forms(surface) == ()


@pytest.mark.parametrize(
    "surface",
    (
        "echo preflight\ncadrumo --version",
        "uv run --frozen cadrumo app registry verify",
        "env MODE=ci cadrumo --version",
        "MODE=ci cadrumo --version",
        "echo preflight && cadrumo --version",
    ),
)
def test_cadrumo_human_command_forms_are_rejected(surface: str) -> None:
    """Cadrumo cannot become a human executable through shell prefixes."""
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search(surface) is not None


@pytest.mark.parametrize(
    ("surface", "expected_family"),
    (
        ("from aeat import core", "python-import"),
        ('python -c "import os, aeat"', "python-import"),
        ("python -m aeat config check", "python-module"),
        ("pip install aeat", "distribution-install"),
        ("pip install aeat-data-official", "former-distribution"),
        ("uv add aeat-data-manuals", "former-distribution"),
        ("ruff check src/aeat/", "former-source-path"),
        ("uv build packaging/aeat_data_official", "former-distribution"),
    ),
)
def test_former_aeat_product_forms_are_rejected(surface: str, expected_family: str) -> None:
    """Former imports, modules, distributions, and paths remain prohibited."""
    assert expected_family in _prohibited_aeat_product_forms(surface)


def _cohort_build_job() -> dict[str, Any]:
    """Return the job that seals the cohort."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return document["jobs"]["build-release-cohort"]


def _executed_lines(job: dict[str, Any]) -> list[str]:
    """Return the job's run lines with comments stripped.

    Comment lines are excluded deliberately. The first version of this gate
    matched the whole run surface, and passed against a mutated workflow because
    the explanatory COMMENT above the invocation contains the very string it
    asserted. A gate satisfied by its own prose proves nothing.
    """
    return [
        line.strip()
        for step in job["steps"]
        if "run" in step
        for line in str(step["run"]).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_the_version_identity_guard_runs_before_the_cohort_is_built() -> None:
    """A cohort must not be sealed under a version no release may ever mint.

    Ordering is the assertion that matters: a guard placed after the build would
    let a cohort carrying a burned number exist, and the artefacts are what get
    promoted later.
    """
    build = _cohort_build_job()
    names = [str(step.get("name", "")) for step in build["steps"]]
    surface = "\n".join(str(step.get("run", "")) for step in build["steps"] if "run" in step)

    assert "dev.release.version_identity" in surface, "seal time must ask the identity authority"
    guard = next(i for i, name in enumerate(names) if "Refuse to seal" in name)
    cohort_build = next(i for i, name in enumerate(names) if "Build the immutable full release cohort" in name)
    assert guard < cohort_build, "the guard must refuse before the cohort exists, not after"


def test_the_seal_guard_uses_the_seal_scope_not_the_publication_scope() -> None:
    """Sealing is not shipping, and conflating them stopped every build.

    The publication scope refuses every destination that already owns the
    version. A seal uploads nothing, so between releases - when the declared
    version is legitimately the one already shipped, because the bump has not
    happened yet - that scope refused every packaging run in exactly the
    interval this lane works in.
    """
    commands = _executed_lines(_cohort_build_job())
    assert "dev.release.version_identity" in "\n".join(commands)
    assert "--scope seal" in commands, "the seal lane must not apply the publication collision set"
    assert "--scope publish" not in commands, "the publication scope refuses every build between releases"


def test_the_seal_guard_asks_no_destination_anything() -> None:
    """The seal reaches no index and no forge, and its arguments must show it.

    A destination argument here is not harmless noise: it is the readable sign
    that the build is being asked a question about an upload it does not
    perform. The two forge arguments and the token that reaches the forge all
    belong to the publication gate.
    """
    build = _cohort_build_job()
    guard = next(step for step in build["steps"] if "Refuse to seal" in str(step.get("name", "")))
    invocation = "\n".join(line.strip() for line in str(guard["run"]).splitlines() if not line.strip().startswith("#"))
    for argument in ("--repository", "--own-source-commit"):
        assert argument not in invocation, f"the seal asks the forge nothing, so {argument} has no meaning here"
    assert "GH_TOKEN" not in str(guard.get("env", {})), "the seal step needs no forge credential"
