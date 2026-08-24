"""Live-tree C0 dependency receipt validator for the public operation contract."""

from __future__ import annotations

import ast
import asyncio
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core import content_hash_hex
from ....entrypoints._operation_composition import compose_operation_dependencies
from ....tests.secure_sql import isolated_runtime_profile
from .. import OperationPublicContractSetV1, OperationSchemaIdentityV1
from .. import __all__ as operation_public_exports

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_STRICT_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_DIGEST = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
_COMMIT = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
_BODY_HASH = Annotated[str, Field(pattern=r"^sha256:[a-f0-9]{64}$")]
_ROOT = Path(__file__).resolve().parents[5]
_GOVERNING_ADR_STEM = "2026-08-11-tui-architecture-adr"
_STAGING_ADR_STEM = "2026-08-24-tui-operation-observation-adr"
_RECEIPT_PATH = ".vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md"
_GIT_EXECUTABLE = shutil.which("git")
_UVX_EXECUTABLE = shutil.which("uvx")
_SEMANTIC_PRODUCER_QUERY = (
    "public operation observation immutable snapshot progress fold safe review workspace refresh authority only:prod exclude:tests"
)


class TuiOperationReceiptDocumentProvenanceV1(BaseModel):
    """One decision record whose current body is bound into the C0 receipt."""

    model_config = _STRICT_CONFIG

    stem: Annotated[str, Field(pattern=r"^20[0-9]{2}-[a-z0-9-]+-adr$")]
    status: Literal["accepted", "rejected"]
    body_hash: _BODY_HASH
    producing_commit: _COMMIT


class TuiOperationDefinitionDigestV1(BaseModel):
    """One definition contract identity in the independently checkable manifest."""

    model_config = _STRICT_CONFIG

    definition_id: Annotated[str, Field(min_length=3, max_length=160)]
    definition_contract_digest: _DIGEST


class TuiOperationCapabilityInventoryV1(BaseModel):
    """The independent public endpoint tuple exposed for one definition."""

    model_config = _STRICT_CONFIG

    definition_id: Annotated[str, Field(min_length=3, max_length=160)]
    definition_contract_digest: _DIGEST
    observation_version: Literal[1] = 1
    review_projection_version: Literal[1] = 1
    response_control_version: Literal[1] = 1
    cancellation_version: Literal[1] = 1
    detach_version: Literal[1] = 1
    refresh_target_version: Literal[1] = 1


class TuiOperationProofEvidenceV1(BaseModel):
    """A source-fingerprinted real-behavior proof required by the C0 gate."""

    model_config = _STRICT_CONFIG

    proof_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]+$")]
    source_path: Annotated[str, Field(pattern=r"^src/cadrumo/.+\.py$")]
    test_function: Annotated[str, Field(pattern=r"^test_[a-z0-9_]+$")]
    source_digest: _DIGEST


class TuiOperationSemanticProducerCensusV1(BaseModel):
    """A source-bound successful Vaultspec RAG producer discovery result."""

    model_config = _STRICT_CONFIG

    schema_version: Literal[1] = 1
    tool_name: Literal["vaultspec-rag"] = "vaultspec-rag"
    result_schema: Literal["vaultspec-rag.search.code.v1"] = "vaultspec-rag.search.code.v1"
    tool_version: Annotated[str, Field(min_length=1, max_length=80)]
    query: Literal[_SEMANTIC_PRODUCER_QUERY] = _SEMANTIC_PRODUCER_QUERY
    disposition: Literal["success"] = "success"
    source_tree_digest: _DIGEST
    discovered_paths: tuple[Annotated[str, Field(pattern=r"^src/cadrumo/application/operations/.+\.py$")], ...] = Field(
        min_length=1
    )
    result_digest: _DIGEST

    @field_validator("discovered_paths")
    @classmethod
    def _discovered_paths_are_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(value)) or len(set(value)) != len(value):
            raise ValueError("semantic producer paths must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _validate_result_digest(self) -> TuiOperationSemanticProducerCensusV1:
        expected = content_hash_hex(
            {
                "schema_version": self.schema_version,
                "tool_name": self.tool_name,
                "result_schema": self.result_schema,
                "tool_version": self.tool_version,
                "query": self.query,
                "disposition": self.disposition,
                "source_tree_digest": self.source_tree_digest,
                "discovered_paths": self.discovered_paths,
            }
        )
        if self.result_digest != expected:
            raise ValueError("semantic producer census result digest does not reproduce")
        return self


class TuiOperationObservationDependencyReceiptV1(BaseModel):
    """Machine-checkable C0 admission evidence; never an operation runtime authority."""

    model_config = _STRICT_CONFIG

    receipt_schema_version: Literal[1] = 1
    cohort: Literal["c0.operation-projection"] = "c0.operation-projection"
    producing_commit: _COMMIT
    source_tree_digest: _DIGEST
    governing_adr: TuiOperationReceiptDocumentProvenanceV1
    staging_adr: TuiOperationReceiptDocumentProvenanceV1
    public_contract_set: OperationPublicContractSetV1
    definition_digests: tuple[TuiOperationDefinitionDigestV1, ...] = Field(min_length=1)
    schema_identities: tuple[OperationSchemaIdentityV1, ...] = Field(min_length=1)
    schema_manifest_digest: _DIGEST
    public_exports: tuple[Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]+$")], ...] = Field(min_length=1)
    public_export_digest: _DIGEST
    capability_inventory: tuple[TuiOperationCapabilityInventoryV1, ...] = Field(min_length=1)
    capability_inventory_digest: _DIGEST
    semantic_producer_census: TuiOperationSemanticProducerCensusV1
    proofs: tuple[TuiOperationProofEvidenceV1, ...] = Field(min_length=1)

    @field_validator("definition_digests")
    @classmethod
    def _definition_digests_are_sorted(
        cls,
        value: tuple[TuiOperationDefinitionDigestV1, ...],
    ) -> tuple[TuiOperationDefinitionDigestV1, ...]:
        definition_ids = tuple(item.definition_id for item in value)
        if definition_ids != tuple(sorted(definition_ids)) or len(set(definition_ids)) != len(definition_ids):
            raise ValueError("definition digest inventory must be sorted and unique")
        return value

    @field_validator("schema_identities")
    @classmethod
    def _schema_identities_are_sorted(
        cls,
        value: tuple[OperationSchemaIdentityV1, ...],
    ) -> tuple[OperationSchemaIdentityV1, ...]:
        keys = tuple((item.schema_id, item.schema_version) for item in value)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("schema identity inventory must be sorted and unique")
        return value

    @field_validator("public_exports")
    @classmethod
    def _public_exports_are_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(value)) or len(set(value)) != len(value):
            raise ValueError("public export inventory must be sorted and unique")
        return value

    @field_validator("capability_inventory")
    @classmethod
    def _capability_inventory_is_sorted(
        cls,
        value: tuple[TuiOperationCapabilityInventoryV1, ...],
    ) -> tuple[TuiOperationCapabilityInventoryV1, ...]:
        definition_ids = tuple(item.definition_id for item in value)
        if definition_ids != tuple(sorted(definition_ids)) or len(set(definition_ids)) != len(definition_ids):
            raise ValueError("capability inventory must be sorted and unique")
        return value

    @field_validator("proofs")
    @classmethod
    def _proofs_are_sorted(cls, value: tuple[TuiOperationProofEvidenceV1, ...]) -> tuple[TuiOperationProofEvidenceV1, ...]:
        proof_ids = tuple(item.proof_id for item in value)
        if proof_ids != tuple(sorted(proof_ids)) or len(set(proof_ids)) != len(proof_ids):
            raise ValueError("proof inventory must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _validate_derived_manifests(self) -> TuiOperationObservationDependencyReceiptV1:
        contracts = self.public_contract_set.definitions
        expected_definition_digests = _definition_digests(contracts)
        if self.definition_digests != expected_definition_digests:
            raise ValueError("definition digest inventory does not reproduce the public contract set")
        expected_schemas = _schema_identities(contracts)
        if self.schema_identities != expected_schemas:
            raise ValueError("schema identity inventory does not reproduce the public contract set")
        if self.schema_manifest_digest != _manifest_digest(expected_schemas):
            raise ValueError("schema manifest digest does not reproduce")
        if self.public_export_digest != content_hash_hex(self.public_exports):
            raise ValueError("public export digest does not reproduce")
        expected_capabilities = _capability_inventory(contracts)
        if self.capability_inventory != expected_capabilities:
            raise ValueError("capability inventory does not reproduce the public contract set")
        if self.capability_inventory_digest != _manifest_digest(expected_capabilities):
            raise ValueError("capability inventory digest does not reproduce")
        if self.semantic_producer_census.source_tree_digest != self.source_tree_digest:
            raise ValueError("semantic producer census does not bind the receipt source tree")
        if self.governing_adr.stem != _GOVERNING_ADR_STEM or self.governing_adr.status != "accepted":
            raise ValueError("C0 receipt must bind the accepted governing TUI architecture ADR")
        if self.staging_adr.stem != _STAGING_ADR_STEM or self.staging_adr.status != "rejected":
            raise ValueError("C0 receipt must retain the rejected staging ADR only as provenance")
        if tuple(item.proof_id for item in self.proofs) != tuple(sorted(_REQUIRED_PROOFS)):
            raise ValueError("C0 receipt proof inventory is incomplete or has an undeclared proof")
        return self


_REQUIRED_PROOFS: Mapping[str, tuple[str, str]] = {
    "atomic_interleaving": (
        "src/cadrumo/adapters/persistence/operations/tests/test_journal.py",
        "test_operation_observation_is_one_locked_record_under_a_real_interleaved_transition",
    ),
    "current_only_deletion": (
        "src/cadrumo/adapters/persistence/operations/tests/test_journal.py",
        "test_operation_journal_refuses_every_superseded_snapshot_schema_without_byte_mutation",
    ),
    "digest_drift_refusal": (
        "src/cadrumo/application/operations/tests/test_observation.py",
        "test_observation_returns_closed_safe_refusals",
    ),
    "production_di": (
        "src/cadrumo/entrypoints/tests/test_operation_composition.py",
        "test_production_composition_reaches_the_owner_registry_fixed_point",
    ),
    "progress_replay": (
        "src/cadrumo/application/operations/tests/test_observation.py",
        "test_observation_resynchronization_replaces_progress_from_authoritative_checkpoint",
    ),
    "restart_refresh": (
        "src/cadrumo/application/operations/tests/test_projection_services.py",
        "test_refresh_target_resolves_only_authoritative_successful_terminal_receipt",
    ),
    "review_non_authority": (
        "src/cadrumo/application/operations/tests/test_projection_services.py",
        "test_review_resolution_uses_encrypted_operand_and_is_read_only",
    ),
    "sentinel_non_retention": (
        "src/cadrumo/adapters/persistence/operations/tests/test_ephemeral_secret_submission.py",
        "test_exact_one_shot_submission_executes_once_and_never_reaches_filesystem",
    ),
    "strict_round_trip": (
        "src/cadrumo/application/operations/tests/test_journal.py",
        "test_observation_materialization_binds_snapshot_replay_and_progress_to_one_anchor",
    ),
}

_EXPECTED_AUTHORITY_OWNERS: Mapping[str, str] = {
    "OperationSnapshot": "src/cadrumo/application/operations/_models.py",
    "OperationPersistedSnapshot": "src/cadrumo/application/operations/_journal.py",
    "OperationRegistry": "src/cadrumo/application/operations/_registry.py",
    "OperationObservationService": "src/cadrumo/application/operations/_observation.py",
    "OperationReviewProjectionService": "src/cadrumo/application/operations/_projection_services.py",
    "OperationWorkspaceRefreshTargetService": "src/cadrumo/application/operations/_projection_services.py",
    "OperationComposedServices": "src/cadrumo/application/operations/_composition.py",
    "_fold_progress": "src/cadrumo/application/operations/_observation.py",
    "compose_operation_dependencies": "src/cadrumo/entrypoints/_operation_composition.py",
}

_EXPECTED_CONSTRUCTORS: Mapping[str, str] = {
    "OperationRegistry": "src/cadrumo/entrypoints/_operation_composition.py",
    "OperationPersistedSnapshot": "src/cadrumo/application/operations/_supervisor.py",
    "OperationObservationService": "src/cadrumo/application/operations/_composition.py",
    "OperationPublicProjectionV1": "src/cadrumo/application/operations/_observation.py",
    "OperationReviewProjectionService": "src/cadrumo/application/operations/_composition.py",
    "OperationWorkspaceRefreshTargetService": "src/cadrumo/application/operations/_composition.py",
}

_SEMANTIC_ALLOWED_OWNERS = frozenset(
    {
        "src/cadrumo/application/operations/_composition.py",
        "src/cadrumo/application/operations/_journal.py",
        "src/cadrumo/application/operations/_models.py",
        "src/cadrumo/application/operations/_observation.py",
        "src/cadrumo/application/operations/_projection_services.py",
        "src/cadrumo/application/operations/_public.py",
        "src/cadrumo/application/operations/_registry.py",
        "src/cadrumo/application/operations/_supervisor.py",
    }
)

_C0_OWNER_PREFIXES = (
    "src/cadrumo/application/operations/",
    "src/cadrumo/adapters/persistence/operations/",
)
_C0_OWNER_FILES = frozenset(
    {
        "src/cadrumo/application/auth/_operation_definitions.py",
        "src/cadrumo/application/live/_filed_history_operation.py",
        "src/cadrumo/application/user_profile/_bundle_export_operation.py",
        "src/cadrumo/application/user_profile/_censal_operation.py",
        "src/cadrumo/application/user_profile/_operation_definitions.py",
        "src/cadrumo/entrypoints/_operation_composition.py",
        "src/cadrumo/entrypoints/tests/test_operation_composition.py",
        "src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py",
    }
)


def _manifest_digest(items: Iterable[BaseModel]) -> str:
    return content_hash_hex(tuple(item.model_dump(mode="json") for item in items))


def _definition_digests(
    contracts: tuple[object, ...],
) -> tuple[TuiOperationDefinitionDigestV1, ...]:
    return tuple(
        TuiOperationDefinitionDigestV1(
            definition_id=contract.definition_id,
            definition_contract_digest=contract.definition_contract_digest,
        )
        for contract in contracts
    )


def _schema_identities(contracts: tuple[object, ...]) -> tuple[OperationSchemaIdentityV1, ...]:
    identities = {
        (identity.schema_id, identity.schema_version): identity
        for contract in contracts
        for identity in (
            contract.request_schema,
            contract.result_schema,
            contract.review_projection_schema,
            contract.interaction_response_schema,
            contract.workspace_refresh_target_schema,
        )
        if identity is not None
    }
    return tuple(identities[key] for key in sorted(identities))


def _capability_inventory(contracts: tuple[object, ...]) -> tuple[TuiOperationCapabilityInventoryV1, ...]:
    return tuple(
        TuiOperationCapabilityInventoryV1(
            definition_id=contract.definition_id,
            definition_contract_digest=contract.definition_contract_digest,
        )
        for contract in contracts
    )


def _run_git(workspace_root: Path, *arguments: str) -> str:
    if _GIT_EXECUTABLE is None:
        raise ValueError("C0 receipt validation requires the resolved local git executable")
    completed = subprocess.run(  # noqa: S603 - resolved local Git with test-owned fixed command families.
        [_GIT_EXECUTABLE, *arguments],
        cwd=workspace_root,
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise ValueError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _git_is_ancestor(workspace_root: Path, ancestor: str, descendant: str) -> bool:
    if _GIT_EXECUTABLE is None:
        raise ValueError("C0 receipt validation requires the resolved local git executable")
    completed = subprocess.run(  # noqa: S603 - resolved local Git with fixed ancestry verification arguments.
        [_GIT_EXECUTABLE, "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=workspace_root,
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if completed.returncode not in {0, 1}:
        raise ValueError(f"git ancestry verification failed: {completed.stderr.strip()}")
    return completed.returncode == 0


def _file_digest(path: Path) -> str:
    return content_hash_hex(path.read_bytes().hex())


def _source_tree_digest(workspace_root: Path) -> str:
    tracked = {
        item
        for item in _run_git(workspace_root, "ls-files", "-z", "--", "src/cadrumo").split("\0")
        if item and (item.startswith(_C0_OWNER_PREFIXES) or item in _C0_OWNER_FILES)
    }
    tracked.update(source_path for source_path, _function in _REQUIRED_PROOFS.values())
    tracked.update(_C0_OWNER_FILES)
    source_paths = tuple(sorted(item for item in tracked if (workspace_root / item).is_file()))
    if not source_paths:
        raise ValueError("C0 receipt source tree is not a tracked Cadrumo worktree")
    return content_hash_hex(
        tuple((relative, _file_digest(workspace_root / relative)) for relative in source_paths)
    )


def _document_provenance(workspace_root: Path, *, stem: str, status: Literal["accepted", "rejected"]):
    path = workspace_root / ".vault" / "adr" / f"{stem}.md"
    source = path.read_text(encoding="utf-8")
    hash_match = re.search(r"^body_hash: '(sha256:[a-f0-9]{64})'$", source, flags=re.MULTILINE)
    if hash_match is None:
        raise ValueError(f"{stem} has no canonical body hash")
    status_match = re.search(r"\*\*status:\*\* `([a-z]+)`", source)
    if status_match is None or status_match.group(1) != status:
        raise ValueError(f"{stem} does not carry required {status!r} status")
    return TuiOperationReceiptDocumentProvenanceV1(
        stem=stem,
        status=status,
        body_hash=hash_match.group(1),
        producing_commit=_run_git(workspace_root, "log", "-1", "--format=%H", "--", path.relative_to(workspace_root).as_posix()),
    )


def _proof_inventory(workspace_root: Path) -> tuple[TuiOperationProofEvidenceV1, ...]:
    return tuple(
        TuiOperationProofEvidenceV1(
            proof_id=proof_id,
            source_path=source_path,
            test_function=test_function,
            source_digest=_file_digest(workspace_root / source_path),
        )
        for proof_id, (source_path, test_function) in sorted(_REQUIRED_PROOFS.items())
    )


def _semantic_census(
    *,
    tool_version: str,
    source_tree_digest: str,
    discovered_paths: tuple[str, ...],
) -> TuiOperationSemanticProducerCensusV1:
    payload = {
        "schema_version": 1,
        "tool_name": "vaultspec-rag",
        "result_schema": "vaultspec-rag.search.code.v1",
        "tool_version": tool_version,
        "query": _SEMANTIC_PRODUCER_QUERY,
        "disposition": "success",
        "source_tree_digest": source_tree_digest,
        "discovered_paths": discovered_paths,
    }
    return TuiOperationSemanticProducerCensusV1(
        **payload,
        result_digest=content_hash_hex(payload),
    )


def build_tui_operation_observation_dependency_receipt(
    *,
    semantic_producer_census: TuiOperationSemanticProducerCensusV1,
    workspace_root: Path = _ROOT,
) -> TuiOperationObservationDependencyReceiptV1:
    """Materialize the V1 receipt from the sole production composition and current tree."""
    dependencies = compose_operation_dependencies()
    try:
        contract_set = dependencies.observation.registry.public_contract_set
    finally:
        asyncio.run(dependencies.shutdown())
    schemas = _schema_identities(contract_set.definitions)
    capabilities = _capability_inventory(contract_set.definitions)
    return TuiOperationObservationDependencyReceiptV1(
        producing_commit=_run_git(workspace_root, "rev-parse", "HEAD"),
        source_tree_digest=_source_tree_digest(workspace_root),
        governing_adr=_document_provenance(
            workspace_root,
            stem=_GOVERNING_ADR_STEM,
            status="accepted",
        ),
        staging_adr=_document_provenance(
            workspace_root,
            stem=_STAGING_ADR_STEM,
            status="rejected",
        ),
        public_contract_set=contract_set,
        definition_digests=_definition_digests(contract_set.definitions),
        schema_identities=schemas,
        schema_manifest_digest=_manifest_digest(schemas),
        public_exports=tuple(sorted(operation_public_exports)),
        public_export_digest=content_hash_hex(tuple(sorted(operation_public_exports))),
        capability_inventory=capabilities,
        capability_inventory_digest=_manifest_digest(capabilities),
        semantic_producer_census=semantic_producer_census,
        proofs=_proof_inventory(workspace_root),
    )


def _top_level_authorities(workspace_root: Path) -> dict[str, set[str]]:
    observed: dict[str, set[str]] = {name: set() for name in _EXPECTED_AUTHORITY_OWNERS}
    for path in (workspace_root / "src" / "cadrumo").rglob("*.py"):
        if "tests" in path.parts:
            continue
        relative = path.relative_to(workspace_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in observed:
                observed[node.name].add(relative)
    return observed


def _constructor_sites(workspace_root: Path) -> dict[str, set[str]]:
    observed: dict[str, set[str]] = {name: set() for name in _EXPECTED_CONSTRUCTORS}
    for path in (workspace_root / "src" / "cadrumo").rglob("*.py"):
        if "tests" in path.parts:
            continue
        relative = path.relative_to(workspace_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name in observed:
                observed[name].add(relative)
    return observed


def _validate_exact_producer_census(workspace_root: Path) -> None:
    authorities = _top_level_authorities(workspace_root)
    expected_authorities = {name: {path} for name, path in _EXPECTED_AUTHORITY_OWNERS.items()}
    if authorities != expected_authorities:
        raise ValueError(f"duplicate or displaced operation authority: {authorities!r}")
    constructors = _constructor_sites(workspace_root)
    expected_constructors = {name: {path} for name, path in _EXPECTED_CONSTRUCTORS.items()}
    if constructors != expected_constructors:
        raise ValueError(f"duplicate or displaced operation producer: {constructors!r}")


def capture_tui_operation_semantic_producer_census(
    *,
    workspace_root: Path = _ROOT,
) -> TuiOperationSemanticProducerCensusV1:
    """Capture the required real Vaultspec RAG discovery for the C0 receipt producer."""
    version = _vaultspec_rag_version(workspace_root)
    completed = subprocess.run(  # noqa: S603 - resolved local RAG executable with a fixed repository-owned query.
        [
            _require_uvx_executable(),
            "vaultspec-rag",
            "search",
            _SEMANTIC_PRODUCER_QUERY,
            "--type",
            "code",
            "--include-path",
            "src/cadrumo/application/operations/**",
            "--limit",
            "16",
        ],
        cwd=workspace_root,
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise ValueError(f"semantic producer census failed: {completed.stderr.strip()} {completed.stdout.strip()}")
    discovered = tuple(sorted(set(re.findall(r"src/cadrumo/application/operations/[A-Za-z0-9_./-]+\.py", completed.stdout))))
    if not discovered:
        raise ValueError("semantic producer census returned no operation authorities")
    return _semantic_census(
        tool_version=version,
        source_tree_digest=_source_tree_digest(workspace_root),
        discovered_paths=discovered,
    )


def _require_uvx_executable() -> str:
    if _UVX_EXECUTABLE is None:
        raise ValueError("C0 receipt semantic census requires the resolved local uvx executable")
    return _UVX_EXECUTABLE


def _vaultspec_rag_version(workspace_root: Path) -> str:
    version = subprocess.run(  # noqa: S603 - resolved local RAG executable with a fixed version probe.
        [_require_uvx_executable(), "vaultspec-rag", "--version"],
        cwd=workspace_root,
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if version.returncode != 0 or not version.stdout.strip():
        raise ValueError(f"semantic producer census cannot identify vaultspec-rag: {version.stderr.strip()}")
    return version.stdout.strip()


def _validate_semantic_producer_census(
    census: TuiOperationSemanticProducerCensusV1,
    *,
    workspace_root: Path,
    source_tree_digest: str,
) -> None:
    if census.tool_version != _vaultspec_rag_version(workspace_root):
        raise ValueError("semantic producer census Vaultspec RAG tool identity drifted")
    if census.source_tree_digest != source_tree_digest:
        raise ValueError("semantic producer census source-tree digest drifted")
    discovered = set(census.discovered_paths)
    required = {
        "src/cadrumo/application/operations/_observation.py",
        "src/cadrumo/application/operations/_projection_services.py",
        "src/cadrumo/application/operations/_registry.py",
    }
    if not required <= discovered:
        raise ValueError(f"semantic producer census missed canonical operation authorities: {discovered!r}")
    unexpected = discovered - _SEMANTIC_ALLOWED_OWNERS
    if unexpected:
        raise ValueError(f"semantic producer census found competing operation authorities: {unexpected!r}")


def _validate_proofs(receipt: TuiOperationObservationDependencyReceiptV1, workspace_root: Path) -> None:
    for proof in receipt.proofs:
        expected_path, expected_function = _REQUIRED_PROOFS[proof.proof_id]
        if (proof.source_path, proof.test_function) != (expected_path, expected_function):
            raise ValueError(f"C0 proof {proof.proof_id!r} does not name its canonical real-behavior test")
        source_path = workspace_root / proof.source_path
        if proof.source_digest != _file_digest(source_path):
            raise ValueError(f"C0 proof {proof.proof_id!r} source digest drifted")
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=proof.source_path)
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        if proof.test_function not in functions:
            raise ValueError(f"C0 proof {proof.proof_id!r} no longer has its named real-behavior test")


def validate_tui_operation_observation_dependency_receipt(
    receipt: TuiOperationObservationDependencyReceiptV1,
    *,
    workspace_root: Path = _ROOT,
    require_clean_tree: bool = True,
) -> None:
    """Refuse every stale, dirty, non-canonical, or duplicate-authority C0 receipt."""
    if require_clean_tree and _run_git(workspace_root, "status", "--porcelain"):
        raise ValueError("C0 receipt requires a clean implementation worktree")
    current_commit = _run_git(workspace_root, "rev-parse", "HEAD")
    if receipt.producing_commit != current_commit:
        raise ValueError("C0 receipt was not produced by the current commit")
    if receipt.source_tree_digest != _source_tree_digest(workspace_root):
        raise ValueError("C0 receipt source-tree digest drifted")
    for expected in (
        _document_provenance(workspace_root, stem=_GOVERNING_ADR_STEM, status="accepted"),
        _document_provenance(workspace_root, stem=_STAGING_ADR_STEM, status="rejected"),
    ):
        actual = receipt.governing_adr if expected.stem == _GOVERNING_ADR_STEM else receipt.staging_adr
        if actual != expected:
            raise ValueError(f"C0 receipt decision provenance drifted for {expected.stem}")
        if _git_is_ancestor(workspace_root, expected.producing_commit, receipt.producing_commit):
            continue
        raise ValueError(f"C0 receipt commit does not descend from {expected.stem}")
    dependencies = compose_operation_dependencies()
    try:
        live_contract_set = dependencies.observation.registry.public_contract_set
    finally:
        asyncio.run(dependencies.shutdown())
    if receipt.public_contract_set != live_contract_set:
        raise ValueError("C0 receipt public contract set is not production DI parity")
    if receipt.public_exports != tuple(sorted(operation_public_exports)):
        raise ValueError("C0 receipt public export inventory drifted")
    _validate_proofs(receipt, workspace_root)
    _validate_exact_producer_census(workspace_root)
    _validate_semantic_producer_census(
        receipt.semantic_producer_census,
        workspace_root=workspace_root,
        source_tree_digest=receipt.source_tree_digest,
    )


def _working_tree_is_clean(workspace_root: Path) -> bool:
    return not _run_git(workspace_root, "status", "--porcelain")


def _supplied_semantic_census_for_contract_test() -> TuiOperationSemanticProducerCensusV1:
    """Provide current-tree evidence to exercise receipt validation without a RAG service dependency."""
    return _semantic_census(
        tool_version=_vaultspec_rag_version(_ROOT),
        source_tree_digest=_source_tree_digest(_ROOT),
        discovered_paths=tuple(sorted(_SEMANTIC_ALLOWED_OWNERS)),
    )


def test_c0_receipt_round_trips_strictly_and_validates_current_production_di(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        receipt = build_tui_operation_observation_dependency_receipt(
            semantic_producer_census=_supplied_semantic_census_for_contract_test()
        )
        restored = TuiOperationObservationDependencyReceiptV1.model_validate_json(receipt.model_dump_json())

        assert restored == receipt
        validate_tui_operation_observation_dependency_receipt(restored, require_clean_tree=False)


def test_c0_receipt_refuses_digest_and_provenance_drift(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        receipt = build_tui_operation_observation_dependency_receipt(
            semantic_producer_census=_supplied_semantic_census_for_contract_test()
        )
        changed_digest = receipt.model_copy(update={"source_tree_digest": "f" * 64})
        changed_provenance = receipt.model_copy(
            update={"governing_adr": receipt.governing_adr.model_copy(update={"body_hash": "sha256:" + "f" * 64})}
        )

        with pytest.raises(ValueError, match="source-tree digest"):
            validate_tui_operation_observation_dependency_receipt(changed_digest, require_clean_tree=False)
        with pytest.raises(ValueError, match="decision provenance"):
            validate_tui_operation_observation_dependency_receipt(changed_provenance, require_clean_tree=False)


def test_c0_receipt_model_is_closed_and_proof_inventory_is_complete(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        receipt = build_tui_operation_observation_dependency_receipt(
            semantic_producer_census=_supplied_semantic_census_for_contract_test()
        )
        raw = receipt.model_dump(mode="json")
        raw["undeclared"] = "forbidden"

        with pytest.raises(ValueError):
            TuiOperationObservationDependencyReceiptV1.model_validate(raw)

    assert tuple(item.proof_id for item in receipt.proofs) == tuple(sorted(_REQUIRED_PROOFS))


def test_c0_receipt_exact_and_semantic_producer_censuses_are_a_fixed_point() -> None:
    _validate_exact_producer_census(_ROOT)
    _validate_semantic_producer_census(
        _supplied_semantic_census_for_contract_test(),
        workspace_root=_ROOT,
        source_tree_digest=_source_tree_digest(_ROOT),
    )


def test_c0_receipt_dirty_tree_guard_uses_a_real_git_worktree(tmp_path: Path) -> None:
    workspace = tmp_path / "receipt-git"
    workspace.mkdir()
    _run_git(workspace, "init")
    assert _working_tree_is_clean(workspace)
    (workspace / "untracked.txt").write_text("receipt staging is not clean\n", encoding="utf-8")

    assert not _working_tree_is_clean(workspace)
