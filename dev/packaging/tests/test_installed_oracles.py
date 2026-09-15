"""Bind the installed CLI and MCP tax oracles to one real wheel cohort.

The test builds one closed-world cohort, installs it once into a single
environment, records the installed metadata origins and hashes, then runs both
public tax-work oracles from that same environment. This closes the gap where
independently passing probes could accidentally exercise different virtual
environments, rebuilt wheels, or ambient commands.

Both console scripts come from the one ``cadrumo`` distribution. The wheel
target packs the ``cadrumo`` and ``cadrumo_harness`` source packages together,
so ``cadrumo-mcp`` is a root-distribution entry point and there is no separate
harness wheel to build, install, or attest.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import re
import shutil
import sqlite3
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from dev._paths import REPO_ROOT
from dev.source_tree import repository_files, snapshot

from .._distribution_names import normalise_distribution_name
from ..hashing import sha256_path
from ..installed_mcp_oracle import InstalledMcpOracleError, run_installed_mcp_oracle
from ..installed_tax_oracle import InstalledTaxOracleError, run_installed_tax_oracle
from ..lane_verification_core import (
    create_pip_venv,
    installed_product_env,
    run_checked,
    venv_bin_dir,
    venv_python_path,
)
from ..python_cohort import PythonCohort, build_python_cohort

# The module-scoped cohort fixture snapshots and ZIPs the complete tracked
# source corpus before building three distributions. On Windows that legitimate
# setup can exceed the repository's ordinary five-minute per-test ceiling while
# CRC-compressing the binary evidence corpus; keep a finite ceiling for hangs.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial, pytest.mark.timeout(900)]

_REPO_ROOT = REPO_ROOT
_AUTHORITY_CANDIDATE_ENV = "CADRUMO_AUTHORITY_CANDIDATE_DIR"
_DISTRIBUTIONS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)
_REQUIREMENT_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_COHORT_PROBE = """
import json
import sysconfig
from importlib.metadata import distribution
from pathlib import Path

names = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
distributions = {name: distribution(name) for name in names}
root = distributions["cadrumo"]
print(json.dumps({
    "scripts_dir": str(Path(sysconfig.get_path("scripts")).resolve()),
    "versions": {name: item.version for name, item in distributions.items()},
    "site_roots": {
        name: str(Path(item.locate_file("")).resolve())
        for name, item in distributions.items()
    },
    "direct_urls": {
        name: json.loads(item.read_text("direct_url.json") or "null")
        for name, item in distributions.items()
    },
    "root_requirements": list(root.requires or ()),
    "console_scripts": {
        entry.name: entry.value
        for entry in root.entry_points
        if entry.group == "console_scripts"
    },
    "root_top_level": sorted({
        Path(entry).parts[0]
        for entry in (root.files or ())
        if Path(entry).suffix in (".py", ".pyi")
    }),
}, sort_keys=True))
"""
_AUTHORITY_RESOURCE_PROBE = """
import hashlib
import json
from importlib.resources import files
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityComponentKind,
    EvidenceComponentQuery,
    ModeloRevisionComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, SQLiteAuthorityReader

registry = files("cadrumo").joinpath("_data", "registry")
descriptor = registry.joinpath("authority", "authority.current.json")
descriptor_path = Path(str(descriptor)).resolve(strict=True)
selected = AuthorityDescriptor.read(descriptor_path)
database = descriptor_path.with_name(selected.database)
database_raw = database.read_bytes()
reader = SQLiteAuthorityReader(descriptor_path)
queries = reader.component_queries()
reader.close()
revision_query = next(query for query in queries if isinstance(query, ModeloRevisionComponentQuery))
fact_query = next(query for query in queries if query.kind is AuthorityComponentKind.GOVERNED_FACT)
evidence_query = next(
    query
    for query in queries
    if query.kind in (AuthorityComponentKind.LEGAL_EVIDENCE, AuthorityComponentKind.SOURCE_EVIDENCE)
)
authority = IndexedRegistryAuthority(descriptor_path)
with authority.operation() as operation:
    profile = operation.profile_schema()
    fact = operation.governed_fact(fact_query.fact_id)
    revision = operation.revision(revision_query.modelo_id, revision_query.revision_id)
    evidence = operation.load(evidence_query, pin=operation.pin())
authority.close()
print(json.dumps({
    "descriptor": str(descriptor_path),
    "descriptor_sha256": hashlib.sha256(descriptor_path.read_bytes()).hexdigest(),
    "database": str(database),
    "database_sha256": hashlib.sha256(database_raw).hexdigest(),
    "database_size": len(database_raw),
    "logical_generation": selected.logical_generation,
    "authoring_exists": registry.joinpath("aeat").is_dir(),
    "profile_schema_source_exists": registry.joinpath("cadrumo", "user_profile", "schema.toml").exists(),
    "profile_schema": profile.id,
    "fact_id": fact.fact_id,
    "revision": f"{revision_query.modelo_id}:{revision_query.revision_id}",
    "revision_id": revision.id,
    "evidence_id": getattr(evidence, "legal_reference_id", getattr(evidence, "source_reference_id", "")),
    "component_count": len(queries),
}, sort_keys=True))
"""
_TYPED_AUTHORITY_PROBE = """
import json
from copy import deepcopy
from decimal import Decimal
from importlib.resources import files
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityComponentKind,
    EvidenceComponentQuery,
    ExportLayoutComponentQuery,
    ModeloRevisionComponentQuery,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor, SQLiteAuthorityReader
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    parse_fixed_width_export_field,
    render_fixed_width_export_field,
)
from cadrumo.domain.calculations.registry.ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values

descriptor_path = Path(str(files("cadrumo").joinpath(
    "_data", "registry", "authority", "authority.current.json"
))).resolve(strict=True)
selected = AuthorityDescriptor.read(descriptor_path)
reader = SQLiteAuthorityReader(descriptor_path)
queries = reader.component_queries()
reader.close()
revision_query = next(
    query
    for query in queries
    if isinstance(query, ModeloRevisionComponentQuery)
    and query.modelo_id == "303"
    and query.revision_id == "2025"
)
layout_query = next(
    query
    for query in queries
    if isinstance(query, ExportLayoutComponentQuery)
    and query.modelo_id == revision_query.modelo_id
    and query.revision_id == revision_query.revision_id
)
fact_query = next(query for query in queries if query.kind is AuthorityComponentKind.GOVERNED_FACT)
evidence_query = next(
    query
    for query in queries
    if query.kind in (AuthorityComponentKind.LEGAL_EVIDENCE, AuthorityComponentKind.SOURCE_EVIDENCE)
)
authority = IndexedRegistryAuthority(descriptor_path)
try:
    with authority.operation() as operation:
        profile = operation.profile_schema()
        create_context = operation.profile_create_context()
        decode_context = operation.profile_decode_context()
        fact = operation.governed_fact(fact_query.fact_id)
        revision = operation.revision(revision_query.modelo_id, revision_query.revision_id)
        layout = operation.export_layout(
            layout_query.modelo_id,
            layout_query.revision_id,
            layout_query.layout_id,
        )
        evidence = operation.load(evidence_query, pin=operation.pin())
        runtime = operation.runtime_catalogue("iva_regulations")
finally:
    authority.close()
m303_values = resolve_ledger_iva_aggregation_binding_values(revision, ())
assert m303_values and all(value == 0 for value in m303_values.values())
assert deepcopy(revision) == revision
export_fields = [
    field
    for record in layout.records
    for field in record.fields
    if field.kind == "casilla" and field.data_type == "money" and field.value_policy is None
]
assert export_fields
for field in export_fields:
    amount = Decimal("123.45")
    wire = render_fixed_width_export_field(field, amount)
    assert len(wire) == field.length
    assert parse_fixed_width_export_field(field, wire) == amount
try:
    render_fixed_width_export_field(export_fields[0], "not-an-amount")
except RegistryValidationError:
    pass
else:
    raise AssertionError("installed modelo export accepted a malformed amount")
print(json.dumps({
    "profile_schema": profile.id,
    "profile_create_generation": create_context.generation.logical_generation,
    "profile_decode_generation": decode_context.generation.logical_generation,
    "fact_id": fact.fact_id,
    "revision": f"{revision_query.modelo_id}:{revision_query.revision_id}",
    "evidence_id": getattr(evidence, "legal_reference_id", getattr(evidence, "source_reference_id", "")),
    "m303_empty_ledger_bindings": len(m303_values),
    "m303_export_money_fields": len(export_fields),
    "authority_record_types": [type(next(iter(runtime.values()))).__name__],
    "iva": len(runtime),
    "temporal_refusals": 0,
    "logical_generation": selected.logical_generation,
}, sort_keys=True))
"""


@dataclass(frozen=True)
class InstalledCohort:
    """One built and installed command/data/agent cohort."""

    work_dir: Path
    venv: Path
    root_wheel: Path
    data_wheels: tuple[Path, Path]
    cli: Path
    mcp_server: Path
    cohort_dir: Path
    source_digest: str
    artifact_sha256: dict[str, str]
    authority_descriptor: Path
    authority_database: Path
    authority_descriptor_sha256: str
    authority_database_sha256: str
    evidence_path: Path
    metadata: dict[str, Any]
    python_cohort: PythonCohort


@dataclass(frozen=True)
class DisposableInstallation:
    """A fresh installation of an already-built cohort for one hostile case."""

    root: Path
    venv: Path
    cli: Path
    mcp_server: Path
    authority_descriptor: Path
    authority_database: Path
    authority_descriptor_sha256: str
    authority_database_sha256: str


def _installed_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (venv_bin_dir(venv) / f"{name}{suffix}").resolve()


def _fresh_installation(cohort: InstalledCohort, root: Path) -> DisposableInstallation:
    """Install the fixture's exact wheels into a new per-case environment."""
    root.mkdir()
    venv = create_pip_venv(root, f"{sys.version_info.major}.{sys.version_info.minor}")
    run_checked(
        [
            str(venv_python_path(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            str(cohort.root_wheel.resolve()),
            *(str(wheel.resolve()) for wheel in cohort.data_wheels),
        ],
        cwd=root,
    )
    execution_root = root / "outside-checkout"
    execution_root.mkdir()
    descriptor, descriptor_sha256, database, database_sha256 = _installed_authority_resource(
        venv,
        execution_root=execution_root,
        state_root=root / "probe-state",
    )
    assert root.resolve() in descriptor.parents
    assert root.resolve() in database.parents
    return DisposableInstallation(
        root=root,
        venv=venv,
        cli=_installed_script(venv, "aeat"),
        mcp_server=_installed_script(venv, "cadrumo-mcp"),
        authority_descriptor=descriptor,
        authority_database=database,
        authority_descriptor_sha256=descriptor_sha256,
        authority_database_sha256=database_sha256,
    )


def _installed_authority_resource(
    venv: Path,
    *,
    execution_root: Path,
    state_root: Path,
) -> tuple[Path, str, Path, str]:
    """Resolve and attest the installed authority through package resources."""
    execution_root.mkdir(parents=True, exist_ok=True)
    observed = json.loads(
        run_checked(
            [str(venv_python_path(venv)), "-I", "-c", _AUTHORITY_RESOURCE_PROBE],
            cwd=execution_root,
            env=installed_product_env(state_root, venv),
        ).stdout
    )
    assert observed["authoring_exists"] is False
    assert observed["profile_schema_source_exists"] is False
    assert observed["component_count"] > 0
    assert observed["profile_schema"] == "cadrumo.user_profile"
    assert observed["fact_id"]
    assert observed["revision"]
    assert observed["revision_id"]
    assert observed["evidence_id"]
    descriptor = Path(observed["descriptor"]).resolve(strict=True)
    database = Path(observed["database"]).resolve(strict=True)
    assert database.name == f"authority-{observed['database_sha256']}.sqlite3"
    assert int(observed["database_size"]) == database.stat().st_size
    return (
        descriptor,
        str(observed["descriptor_sha256"]),
        database,
        str(observed["database_sha256"]),
    )


def _assert_no_durable_calculation_work(storage_root: Path) -> None:
    """Prove a refused workflow wrote no work/calculation secure object."""
    forbidden = {
        "cadrumo.calculations.observations",
        "cadrumo.domain.modelos.calculation_revisions",
        "cadrumo.domain.modelos.work_units",
    }
    observed: set[str] = set()
    for database in storage_root.rglob("*.db"):
        with sqlite3.connect(database) as connection:
            has_secure_objects = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'secure_objects'"
            ).fetchone()
            if has_secure_objects:
                observed.update(row[0] for row in connection.execute("SELECT DISTINCT namespace FROM secure_objects"))
    assert observed.isdisjoint(forbidden), f"refused workflow persisted calculation state: {observed & forbidden}"


def _requirement_name(requirement: str) -> str:
    """Return the distribution name of one core-metadata ``Requires-Dist`` line."""
    match = _REQUIREMENT_NAME_PATTERN.match(requirement)
    return normalise_distribution_name(match.group(0)) if match else ""


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_evidence(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _legacy_cohort_fallbacks(source: str) -> tuple[str, ...]:
    forbidden = (
        "var/packaging-smoke-cohort",
        "packaging/cadrumo_harness",
        "attest_command_specs",
    )
    normalized = source.replace("\\", "/")
    return tuple(token for token in forbidden if token in normalized)


def test_installed_oracle_has_no_prebuilt_or_manual_cohort_fallback() -> None:
    """A pre-existing var cohort cannot bypass the canonical clean cohort builder."""
    assert _legacy_cohort_fallbacks('root = "var/packaging-smoke-cohort"')
    assert _legacy_cohort_fallbacks(inspect.getsource(installed_cohort)) == ()


@pytest.fixture(scope="module")
def installed_cohort(tmp_path_factory: pytest.TempPathFactory) -> InstalledCohort:
    """Build one snapshot of the tree once, install one cohort once, and inspect installed metadata."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed oracle cohort"

    work_dir = tmp_path_factory.mktemp("installed-oracle-cohort")
    clean_repo = work_dir / "clean-repository"
    # An isolated copy of the enumerated tree, not the live one: this fixture
    # needs a private `var/` to build the cohort into, isolated from whatever
    # a concurrent agent is doing to the real repository's own `var/`.
    snapshot(_REPO_ROOT, repository_files(_REPO_ROOT), clean_repo)
    _stage_authority_candidate(clean_repo)
    # Under the snapshot's OWN var/, not beside it. `build_python_cohort` refuses
    # an output that is not below `<repo_root>/var`, and repo_root here is the
    # snapshot -- so a sibling of it can never satisfy it and this fixture
    # raised SystemExit on every platform. The SystemExit then escaped a
    # module-scoped fixture, which left pytest's finalizer bookkeeping
    # inconsistent and reported the module's other tests as bare internal
    # AssertionErrors naming nothing.
    cohort_dir = clean_repo / "var" / "python-cohort"
    supplied = build_python_cohort(clean_repo, cohort_dir)
    source_digest = supplied.source_digest
    root_wheel = supplied.root_wheel
    data_wheels = supplied.companion_wheels
    artifact_sha256 = dict(supplied.sha256)

    venv = create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    run_checked(
        [
            str(venv_python_path(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            str(root_wheel.resolve()),
            *(str(wheel.resolve()) for wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    run_checked([str(venv_python_path(venv)), "-m", "pip", "check"], cwd=work_dir)
    metadata_result = run_checked(
        [str(venv_python_path(venv)), "-c", _COHORT_PROBE],
        cwd=work_dir,
    )
    metadata = json.loads(metadata_result.stdout)
    assert isinstance(metadata, dict)

    cli = _installed_script(venv, "aeat")
    mcp_server = _installed_script(venv, "cadrumo-mcp")
    assert cli.is_file()
    assert mcp_server.is_file()
    authority_descriptor, authority_descriptor_sha256, authority_database, authority_database_sha256 = (
        _installed_authority_resource(
            venv,
            execution_root=work_dir / "authority-resource-probe",
            state_root=work_dir / "authority-resource-probe-state",
        )
    )
    evidence_path = (
        _REPO_ROOT / "var" / "distribution-install-readiness" / "installed-cohorts" / source_digest / "evidence.json"
    )
    _write_evidence(
        evidence_path,
        {
            "artifact_sha256": artifact_sha256,
            "source_digest": source_digest,
        },
    )
    return InstalledCohort(
        work_dir=work_dir,
        venv=venv,
        root_wheel=root_wheel,
        data_wheels=data_wheels,
        cli=cli,
        mcp_server=mcp_server,
        cohort_dir=cohort_dir,
        source_digest=source_digest,
        artifact_sha256=artifact_sha256,
        authority_descriptor=authority_descriptor,
        authority_database=authority_database,
        authority_descriptor_sha256=authority_descriptor_sha256,
        authority_database_sha256=authority_database_sha256,
        evidence_path=evidence_path,
        metadata=metadata,
        python_cohort=supplied,
    )


def _stage_authority_candidate(clean_repo: Path) -> None:
    """Copy release-selected authority bytes into only the private cohort tree."""
    from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

    raw_candidate = os.environ.get(_AUTHORITY_CANDIDATE_ENV)
    assert raw_candidate, f"{_AUTHORITY_CANDIDATE_ENV} must name the validated candidate directory"
    candidate = Path(raw_candidate).resolve(strict=True)
    descriptor = candidate / "authority.current.json"
    selected = AuthorityDescriptor.read(descriptor.resolve(strict=True))
    database_name = selected.database
    database = candidate / database_name
    assert database.is_file()
    database_digest = sha256_path(database)
    assert database_name == f"authority-{database_digest}.sqlite3"
    assert selected.database_sha256 == database_digest
    assert selected.database_size == database.stat().st_size
    destination = clean_repo / "src" / "cadrumo" / "_data" / "registry" / "authority"
    destination.mkdir(parents=True, exist_ok=True)
    for stale_database in destination.glob("authority-*.sqlite3"):
        if re.fullmatch(r"authority-[0-9a-f]{64}\.sqlite3", stale_database.name):
            stale_database.unlink()
    shutil.copy2(descriptor, destination / descriptor.name)
    shutil.copy2(database, destination / database.name)


def test_installed_cli_and_mcp_are_one_hashed_cohort(installed_cohort: InstalledCohort) -> None:
    """Both commands and all mandatory distributions have one installed origin."""
    cohort = installed_cohort
    metadata = cohort.metadata
    scripts_dir = Path(metadata["scripts_dir"]).resolve()

    assert cohort.cli.parent == scripts_dir
    assert cohort.mcp_server.parent == scripts_dir
    assert cohort.cli.parent == cohort.mcp_server.parent
    assert len(set(metadata["site_roots"].values())) == 1
    assert len(set(metadata["versions"].values())) == 1

    version = metadata["versions"]["cadrumo"]
    requirements = set(metadata["root_requirements"])
    assert {
        f"cadrumo-data-manuals=={version}",
        f"cadrumo-data-official=={version}",
    } <= requirements
    assert metadata["console_scripts"]["aeat"] == "cadrumo.entrypoints.cli.bootstrap:main"
    # The package split is internal to one distribution: the wheel target packs
    # both source packages, so the root distribution declares the server script
    # and installing the root wheel is what puts `cadrumo_harness` on disk.
    assert metadata["console_scripts"]["cadrumo-mcp"] == "cadrumo_harness.mcp.main:main"
    assert {"cadrumo", "cadrumo_harness"} <= set(metadata["root_top_level"])
    # No harness distribution is required to obtain either command.
    assert not any(_requirement_name(requirement) == "cadrumo-harness" for requirement in requirements)

    authority_prefix = "cadrumo/_data/registry/authority/"
    descriptor_member = authority_prefix + "authority.current.json"
    database_member = authority_prefix + cohort.authority_database.name
    with zipfile.ZipFile(cohort.root_wheel) as wheel:
        wheel_members = set(wheel.namelist())
    assert descriptor_member in wheel_members
    assert database_member in wheel_members
    assert {member for member in wheel_members if member.startswith(authority_prefix)} == {
        descriptor_member,
        database_member,
    }
    assert not any(member.startswith("cadrumo/_data/registry/aeat/") for member in wheel_members)
    assert "cadrumo/_data/registry/cadrumo/user_profile/schema.toml" not in wheel_members
    assert cohort.authority_database.name == f"authority-{cohort.authority_database_sha256}.sqlite3"

    artifacts = {
        "cadrumo": cohort.root_wheel,
        "cadrumo-data-manuals": cohort.data_wheels[0],
        "cadrumo-data-official": cohort.data_wheels[1],
    }
    assert set(artifacts) == set(_DISTRIBUTIONS)
    for name, artifact in artifacts.items():
        direct_url = metadata["direct_urls"][name]
        assert direct_url["url"] == artifact.resolve().as_uri()
        assert direct_url["archive_info"]["hashes"]["sha256"] == cohort.artifact_sha256[name]

    print(
        "installed-cohort-identity="
        + json.dumps(
            {
                "artifact_sha256": cohort.artifact_sha256,
                "evidence_path": str(cohort.evidence_path),
                "source_digest": cohort.source_digest,
            },
            sort_keys=True,
        ),
    )


def test_installed_runtime_imports_authority_without_authoring_sources(
    installed_cohort: InstalledCohort,
) -> None:
    """The isolated installed interpreter admits only the selector/database pair."""
    execution_root = installed_cohort.work_dir / "authority-artifact-only"
    execution_root.mkdir()
    probe = """
import json
from importlib.resources import files
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

registry = files("cadrumo").joinpath("_data", "registry")
descriptor = registry.joinpath("authority", "authority.current.json")
descriptor_path = Path(str(descriptor)).resolve(strict=True)
selected = AuthorityDescriptor.read(descriptor_path)
database = descriptor_path.with_name(selected.database)
authority = IndexedRegistryAuthority(descriptor_path)
try:
    with authority.operation() as operation:
        profile = operation.profile_schema()
finally:
    authority.close()
print(json.dumps({
    "authoring_exists": registry.joinpath("aeat").is_dir(),
    "legacy_json_exists": registry.joinpath("authority", "authority.json").exists(),
    "descriptor_name": descriptor_path.name,
    "database_name": database.name,
    "descriptor_format": selected.format,
    "profile_schema": profile.id,
}, sort_keys=True))
"""
    result = run_checked(
        [str(venv_python_path(installed_cohort.venv)), "-I", "-c", probe],
        cwd=execution_root,
        env=installed_product_env(execution_root / "state", installed_cohort.venv),
    )

    observed = json.loads(result.stdout)
    assert observed["authoring_exists"] is False
    assert observed["legacy_json_exists"] is False
    assert observed["descriptor_name"] == "authority.current.json"
    assert observed["database_name"].startswith("authority-")
    assert observed["database_name"].endswith(".sqlite3")
    assert observed["descriptor_format"] == "cadrumo-authority-descriptor-v1"
    assert observed["profile_schema"] == "cadrumo.user_profile"


def test_installed_consumers_use_pinned_profile_fact_model_and_evidence_components(
    installed_cohort: InstalledCohort,
) -> None:
    """One installed process loads each representative typed component on demand."""
    execution_root = installed_cohort.work_dir / "typed-authority-consumers"
    execution_root.mkdir()
    result = run_checked(
        [str(venv_python_path(installed_cohort.venv)), "-I", "-c", _TYPED_AUTHORITY_PROBE],
        cwd=execution_root,
        env=installed_product_env(execution_root / "state", installed_cohort.venv),
    )

    observed = json.loads(result.stdout)
    assert observed["profile_schema"] == "cadrumo.user_profile"
    assert observed["profile_create_generation"] == observed["logical_generation"]
    assert observed["profile_decode_generation"] == observed["logical_generation"]
    assert observed["fact_id"]
    assert observed["revision"]
    assert observed["evidence_id"]
    assert observed["authority_record_types"] == ["PublishedIvaRegulation"]
    assert observed["iva"] > 0
    assert observed["temporal_refusals"] == 0
    assert observed["m303_empty_ledger_bindings"] > 0
    assert observed["m303_export_money_fields"] > 0


def test_cli_and_mcp_complete_the_same_grounded_oracle_from_that_cohort(
    installed_cohort: InstalledCohort,
) -> None:
    """One installation completes the direct and protocol tax-work claims."""
    cohort = installed_cohort
    execution_root = cohort.work_dir / "outside-checkout"
    execution_root.mkdir()

    cli_evidence = run_installed_tax_oracle(
        cohort.cli,
        storage_root=cohort.work_dir / "cli-state",
        work_dir=execution_root / "cli",
        cohort_source_digest=cohort.source_digest,
        cohort_manifest_sha256=sha256_path(cohort.evidence_path),
        cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )
    mcp_evidence = run_installed_mcp_oracle(
        cohort.mcp_server,
        storage_root=cohort.work_dir / "mcp-state",
        work_dir=execution_root / "mcp",
        cohort_source_digest=cohort.source_digest,
        cohort_manifest_sha256=sha256_path(cohort.python_cohort.manifest),
        cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )

    assert Path(cli_evidence.resolved_executable) == cohort.cli
    assert Path(mcp_evidence.resolved_executable) == cohort.mcp_server
    assert (
        Path(cli_evidence.resolved_executable).parent
        == Path(
            mcp_evidence.resolved_executable,
        ).parent
    )
    assert cli_evidence.target_casilla == mcp_evidence.target_casilla
    assert cli_evidence.target_value == mcp_evidence.target_value == "23000.00"
    assert cli_evidence.formula_id == mcp_evidence.formula_id == "modelo-200-cuota-integra"
    assert cli_evidence.legal_refs == mcp_evidence.legal_refs
    assert cli_evidence.source_refs == mcp_evidence.source_refs
    assert cli_evidence.notice_codes == mcp_evidence.notice_codes
    expected_cli_sha256 = _text_sha256(str(cohort.cli))
    assert mcp_evidence.invoked_cli_sha256 == expected_cli_sha256
    assert mcp_evidence.invoked_cli_sha256_by_command == {
        "modelo.work.calculate": expected_cli_sha256,
        "modelo.work.create": expected_cli_sha256,
        "modelo.work.observations": expected_cli_sha256,
    }
    assert any(call.command_key == "modelo.work.calculate" for call in mcp_evidence.calls)

    _write_evidence(
        cohort.evidence_path,
        {
            "artifact_sha256": cohort.artifact_sha256,
            "cli_oracle": cli_evidence.to_jsonable(),
            "mcp_oracle": mcp_evidence.to_jsonable(),
            "source_digest": cohort.source_digest,
        },
    )
    retained = json.loads(cohort.evidence_path.read_text(encoding="utf-8"))
    assert retained["mcp_oracle"]["invoked_cli_sha256"] == expected_cli_sha256
    assert retained["mcp_oracle"]["invoked_cli_sha256_by_command"] == {
        "modelo.work.calculate": expected_cli_sha256,
        "modelo.work.create": expected_cli_sha256,
        "modelo.work.observations": expected_cli_sha256,
    }


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_installed_cli_and_mcp_refuse_an_unusable_authority_before_durable_work(
    installed_cohort: InstalledCohort,
    tmp_path: Path,
    damage: str,
) -> None:
    """Real installed workflows fail closed when their sole authority is unusable."""
    installation = _fresh_installation(installed_cohort, tmp_path / damage)
    assert sha256_path(installation.authority_descriptor) == installation.authority_descriptor_sha256
    assert sha256_path(installation.authority_database) == installation.authority_database_sha256
    baseline_cli = run_installed_tax_oracle(
        installation.cli,
        storage_root=installation.root / "cli-baseline-state",
        work_dir=installation.root / "cli-baseline",
        cohort_source_digest=installed_cohort.source_digest,
        cohort_manifest_sha256=sha256_path(installed_cohort.evidence_path),
        cohort_root_wheel_sha256=installed_cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )
    baseline_mcp = run_installed_mcp_oracle(
        installation.mcp_server,
        storage_root=installation.root / "mcp-baseline-state",
        work_dir=installation.root / "mcp-baseline",
        cohort_source_digest=installed_cohort.source_digest,
        cohort_manifest_sha256=sha256_path(installed_cohort.python_cohort.manifest),
        cohort_root_wheel_sha256=installed_cohort.artifact_sha256["cadrumo"],
        cohort_harness_wheel_sha256=installed_cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )
    assert baseline_cli.target_value == baseline_mcp.target_value == "23000.00"
    if damage == "missing":
        installation.authority_database.unlink()
        assert not installation.authority_database.exists()
    else:
        corrupted = bytearray(installation.authority_database.read_bytes())
        corrupted[-1] ^= 0x01
        installation.authority_database.write_bytes(corrupted)
        assert sha256_path(installation.authority_database) != installation.authority_database_sha256

    # The store may report an unavailable descriptor/database or an integrity
    # refusal at admission.  Both are fail-closed and neither may expose the
    # old JSON-era error vocabulary as a compatibility path.
    refusal_pattern = r"(?is)(authority|sqlite).*(unavailable|malformed|digest|disagree|corrupt|changed)"

    cli_storage = installation.root / "cli-refusal-state"
    with pytest.raises(
        InstalledTaxOracleError,
        match=refusal_pattern,
    ) as cli_refusal:
        run_installed_tax_oracle(
            installation.cli,
            storage_root=cli_storage,
            work_dir=installation.root / "cli-refusal",
            cohort_source_digest=installed_cohort.source_digest,
            cohort_manifest_sha256=sha256_path(installed_cohort.evidence_path),
            cohort_root_wheel_sha256=installed_cohort.artifact_sha256["cadrumo"],
            timeout_seconds=240.0,
        )
    assert "23000.00" not in str(cli_refusal.value)
    _assert_no_durable_calculation_work(cli_storage)

    mcp_storage = installation.root / "mcp-refusal-state"
    with pytest.raises(
        InstalledMcpOracleError,
        match=refusal_pattern,
    ) as mcp_refusal:
        run_installed_mcp_oracle(
            installation.mcp_server,
            storage_root=mcp_storage,
            work_dir=installation.root / "mcp-refusal",
            cohort_source_digest=installed_cohort.source_digest,
            cohort_manifest_sha256=sha256_path(installed_cohort.python_cohort.manifest),
            cohort_root_wheel_sha256=installed_cohort.artifact_sha256["cadrumo"],
            cohort_harness_wheel_sha256=installed_cohort.artifact_sha256["cadrumo"],
            timeout_seconds=240.0,
        )
    assert "23000.00" not in str(mcp_refusal.value)
    _assert_no_durable_calculation_work(mcp_storage)


def _operative_oracle_identity(evidence: Any) -> tuple[object, ...]:
    return (
        evidence.target_casilla,
        evidence.target_value,
        evidence.formula_id,
        evidence.legal_refs,
        evidence.source_refs,
        evidence.notice_codes,
        evidence.installed_wheel_payload_sha256
        if hasattr(evidence, "installed_wheel_payload_sha256")
        else evidence.installed_cli_payload_sha256,
    )


def test_post_build_source_mutation_cannot_change_an_existing_installation(
    installed_cohort: InstalledCohort,
) -> None:
    """Only republishing and rebuilding can carry authoring changes into runtime."""
    from dev.registry.pipeline.authority_publication import authority_candidate_identity

    cohort = installed_cohort
    clean_repo = cohort.work_dir / "clean-repository"
    registry_root = clean_repo / "src" / "cadrumo" / "_data" / "registry" / "aeat"
    authored = registry_root / "modelos" / "200" / "manifest.toml"
    before_candidate = authority_candidate_identity(registry_root=registry_root, source_root=clean_repo)
    installed_descriptor, installed_descriptor_digest, installed_database, installed_database_digest = (
        _installed_authority_resource(
            cohort.venv,
            execution_root=cohort.work_dir / "source-isolation-resource-probe",
            state_root=cohort.work_dir / "source-isolation-resource-probe-state",
        )
    )

    execution_root = cohort.work_dir / "source-isolation-outside-checkout"
    cli_before = run_installed_tax_oracle(
        cohort.cli,
        storage_root=cohort.work_dir / "source-isolation-cli-before-state",
        work_dir=execution_root / "cli-before",
        cohort_source_digest=cohort.source_digest,
        cohort_manifest_sha256=sha256_path(cohort.evidence_path),
        cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )
    mcp_before = run_installed_mcp_oracle(
        cohort.mcp_server,
        storage_root=cohort.work_dir / "source-isolation-mcp-before-state",
        work_dir=execution_root / "mcp-before",
        cohort_source_digest=cohort.source_digest,
        cohort_manifest_sha256=sha256_path(cohort.python_cohort.manifest),
        cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        cohort_harness_wheel_sha256=cohort.artifact_sha256["cadrumo"],
        timeout_seconds=240.0,
    )

    original = authored.read_bytes()
    try:
        authored.write_bytes(original + b"\n# post-build isolation probe\n")
        after_candidate = authority_candidate_identity(registry_root=registry_root, source_root=clean_repo)
        assert after_candidate != before_candidate
        assert sha256_path(installed_descriptor) == installed_descriptor_digest
        assert sha256_path(installed_database) == installed_database_digest

        cli_after = run_installed_tax_oracle(
            cohort.cli,
            storage_root=cohort.work_dir / "source-isolation-cli-after-state",
            work_dir=execution_root / "cli-after",
            cohort_source_digest=cohort.source_digest,
            cohort_manifest_sha256=sha256_path(cohort.evidence_path),
            cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
            timeout_seconds=240.0,
        )
        mcp_after = run_installed_mcp_oracle(
            cohort.mcp_server,
            storage_root=cohort.work_dir / "source-isolation-mcp-after-state",
            work_dir=execution_root / "mcp-after",
            cohort_source_digest=cohort.source_digest,
            cohort_manifest_sha256=sha256_path(cohort.python_cohort.manifest),
            cohort_root_wheel_sha256=cohort.artifact_sha256["cadrumo"],
            cohort_harness_wheel_sha256=cohort.artifact_sha256["cadrumo"],
            timeout_seconds=240.0,
        )
    finally:
        authored.write_bytes(original)

    assert _operative_oracle_identity(cli_after) == _operative_oracle_identity(cli_before)
    assert _operative_oracle_identity(mcp_after) == _operative_oracle_identity(mcp_before)
    assert sha256_path(installed_descriptor) == installed_descriptor_digest
    assert sha256_path(installed_database) == installed_database_digest


def _as_plugin_cohort(cohort: PythonCohort) -> Any:
    """Adapt a PythonCohort to the marketplace materialiser's protocol.

    PythonCohort satisfies the runtime protocol exactly; the materialiser
    annotates its mutable digest mapping as a read-only Mapping protocol,
    which static structural typing cannot prove for a frozen dataclass
    (same documented cast as the release-cohort builder).
    """
    return cast("Any", cohort)


def test_owned_server_launch_capture_is_a_clean_real_subprocess(installed_cohort: InstalledCohort) -> None:
    """The A-client launch capture spawns the real server and it exits 0 on stdin EOF.

    Proves the option-A pure-client command transcript is a genuinely-owned
    subprocess: real argv, a real ``initialize`` handshake identifying the server
    as ``cadrumo``, and a clean exit (a killed server would be non-zero and could
    never sit in a passing distribution-evidence record).
    """
    from .._acquire_common import capture_owned_server_launch
    from ..installed_mcp_oracle import isolated_mcp_environment

    work = installed_cohort.work_dir / "owned-launch-capture"
    work.mkdir()
    environment = isolated_mcp_environment(work / "state")
    environment["CADRUMO_CLI_EXECUTABLE"] = str(installed_cohort.cli)
    transcript = capture_owned_server_launch(
        server=installed_cohort.mcp_server,
        env=environment,
        cwd=work,
        timeout_seconds=180.0,
    )
    assert Path(transcript.argv[0]) == installed_cohort.mcp_server
    assert transcript.exit_status == 0
    assert transcript.relevant_output == ("initialize serverInfo.name=cadrumo",)
    assert transcript.completed_at >= transcript.started_at


def _retired_state_environment(base: Path) -> dict[str, str]:
    """A per-OS platform-data root whose retired ``aeat`` state triggers the refusal.

    Mirrors the ``smoke_mcpb`` hostile-platform fixture: the resolver refuses on
    the retired directory's existence alone, and refusal fires only in INSTALLED
    run mode - which this file's wheel-installed cohort guarantees, unlike an
    editable checkout whose resolver never inspects the platform data dir.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    hostile_root = base / "platform-data-with-retired-state"
    if sys.platform == "win32":
        former_product_root = hostile_root / "aeat"
        environment["LOCALAPPDATA"] = str(hostile_root)
    elif sys.platform == "darwin":
        hostile_home = base / "home-with-retired-state"
        former_product_root = hostile_home / "Library" / "Application Support" / "aeat"
        environment["HOME"] = str(hostile_home)
    else:
        former_product_root = hostile_root / "aeat"
        environment["XDG_DATA_HOME"] = str(hostile_root)
    former_product_root.mkdir(parents=True)
    (former_product_root / "custody-marker.bin").write_bytes(b"retired-aeat-state-must-remain")
    return environment


async def _read_mcp_response_async(stdout: asyncio.StreamReader, target_id: int) -> dict[str, Any]:
    while True:
        line = await stdout.readline()
        if not line:
            raise AssertionError(f"server closed stdout before answering request id {target_id}")
        stripped = line.decode("utf-8", errors="replace").strip()
        if not stripped:
            continue
        message = json.loads(stripped)
        if isinstance(message, dict) and message.get("id") == target_id:
            return message


async def _drive_mcp_server(
    executable: Path,
    *,
    environment: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Drive the installed stdio server until tools are listed, then stop it."""
    process = await asyncio.create_subprocess_exec(
        str(executable),
        cwd=str(Path.cwd()),
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "storage-root-regression", "version": "0"},
            },
        }
        process.stdin.write((json.dumps(initialize_request) + "\n").encode("utf-8"))
        await process.stdin.drain()
        initialize = await asyncio.wait_for(_read_mcp_response_async(process.stdout, 1), timeout=300)
        process.stdin.write(
            (
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
                + "\n"
                + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                + "\n"
            ).encode("utf-8")
        )
        await process.stdin.drain()
        tools = await asyncio.wait_for(_read_mcp_response_async(process.stdout, 2), timeout=300)
    finally:
        if process.returncode is None:
            process.kill()
        _stdout, stderr = await process.communicate()
    return initialize, tools, stderr.decode("utf-8", errors="replace")


def test_installed_mcp_server_serves_when_storage_root_refuses(installed_cohort: InstalledCohort) -> None:
    """The installed server completes initialize/tools-list on a retired-state machine.

    Storage-root resolution on a machine carrying retired former-product state
    raises the refusal; that must surface on the tool calls that need storage,
    never kill the server pre-protocol. This drives the REAL installed
    ``cadrumo-mcp`` console script over stdio with a fabricated retired-state
    platform root and no ``CADRUMO_*`` overrides - the environment a real
    client on an upgrader's machine provides. It pins the startup chain that
    died four separate ways during the distribution campaign: import-time
    registry settings, the schema-build config subtree, the adapter module
    constants, and the eager telemetry-directory resolution.
    """
    cohort = installed_cohort
    environment = _retired_state_environment(cohort.work_dir / "storage-root-refusal")
    initialize, tools, stderr_text = asyncio.run(_drive_mcp_server(cohort.mcp_server, environment=environment))
    assert initialize["result"]["serverInfo"]["name"] == "cadrumo"
    assert len(tools["result"]["tools"]) > 0
    # The degradation is visible, never silent: the startup note names the
    # storage-root refusal on stderr, which the client's MCP log captures.
    assert "serving without telemetry" in stderr_text
