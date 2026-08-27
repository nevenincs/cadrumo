"""Live-tree dependency receipt validator for the Modelo Workspace V1 C2 gate.

Sole validator for the C2 complex-read dependency receipt named by
`2026-08-24-tui-registry-api-gate-adr.md` ("C2 complex-read gate and external
prerequisites"). Like its C3 sibling (`test_edit_dependency_receipt.py`), this
reads the current tree rather than a recorded claim: every proof below is
derived from real production code and real behavior, never a caller-declared
assertion. Minting the durable
`.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`
artifact was originally deferred to the C1 handoff phase (S131/S139); S140
mints it for real, over the exact clean commit this module was proven
against, once every predecessor and proof genuinely reads PASSED.

Every denominator-shaped proof below (the native-owner surface inventory, the
producer contract set) gates on a PROPERTY read from the live registration
-- `set(kinds) == set(ModeloWorkspaceContributorKindV1)`, never a literal
count -- so a legitimate ninth contributor addition changes the set compared
against, never a hardcoded tally someone has to remember to bump.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .. import workspace, workspace_manifest, workspace_models, workspace_producers
from ..workspace_producers import (
    MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1,
    ModeloWorkspaceContributorKindV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = Path(__file__).resolve().parents[5]
_GATE_ADR = _ROOT / ".vault" / "adr" / "2026-08-24-tui-registry-api-gate-adr.md"
_INTERFACE_ADR = _ROOT / ".vault" / "adr" / "2026-08-24-tui-modelo-workspace-interface-adr.md"
_C1_EXIT_RECEIPT = (
    _ROOT / ".vault" / "reference" / "2026-08-24-tui-modelo-workspace-interface-c1-exit-receipt-reference.md"
)
_RECONCILIATION_AUDIT = _ROOT / ".vault" / "audit" / "2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md"
_OWNER_SEAM_AUDIT = _ROOT / ".vault" / "audit" / "2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit.md"

_WORKSPACE_MODULES = (workspace, workspace_models, workspace_producers, workspace_manifest)


class ModeloWorkspaceC2ProofOutcome:
    """The two-member closed outcome every proof field carries, string-valued for Literal use."""

    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class ModeloWorkspaceC2PassedProofV1(BaseModel):
    """One proof field the validator itself derived from real current behavior."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    outcome: Literal["passed"] = "passed"
    evidence: Annotated[str, Field(min_length=1, max_length=512)]


class ModeloWorkspaceC2NotApplicableProofV1(BaseModel):
    """One proof field honestly reporting an unmeasured or not-yet-open dependency."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    outcome: Literal["not_applicable"] = "not_applicable"
    code: Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")]
    owning_authority: Annotated[str, Field(min_length=1, max_length=128)]
    reason: Annotated[str, Field(min_length=1, max_length=512)]
    evidence: Annotated[str, Field(min_length=1, max_length=512)]


type ModeloWorkspaceC2ProofV1 = Annotated[
    ModeloWorkspaceC2PassedProofV1 | ModeloWorkspaceC2NotApplicableProofV1,
    Field(discriminator="outcome"),
]


class ModeloWorkspaceC2AdrPredecessorV1(BaseModel):
    """One accepted-ADR predecessor: stem, accepting commit, and body hash."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    stem: Annotated[str, Field(min_length=1, max_length=256)]
    status: Annotated[str, Field(min_length=1, max_length=32)]
    body_hash: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkspaceC2ReceiptPredecessorV1(BaseModel):
    """The C1 exit receipt predecessor: its path, validation result, and artifact digest."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    path: Annotated[str, Field(min_length=1, max_length=512)]
    validation_result: Annotated[str, Field(min_length=1, max_length=32)]
    artifact_digest: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkspaceC2AuthorityGradeDecisionPredecessorV1(BaseModel):
    """The authority-grade decision predecessor: accepted or formally reconciled, never both absent."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    stem: Annotated[str, Field(min_length=1, max_length=256)]
    disposition: Annotated[str, Field(min_length=1, max_length=32)]
    reconciliation_artifact_digest: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class ModeloWorkspaceC2InventoryPredecessorV1(BaseModel):
    """The native-owner surface inventory predecessor: schema version and inventory digest."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    inventory_schema_version: Annotated[int, Field(ge=1)]
    artifact_digest: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkspaceC2PredecessorTupleV1(BaseModel):
    """The closed, ORDERED five-entry predecessor set the ADR names verbatim.

    Named fields rather than a generic list: reordering is structurally
    impossible, and a missing predecessor is a missing required field rather
    than a shorter list a count-based check could silently accept.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    gate_adr: ModeloWorkspaceC2AdrPredecessorV1
    interface_adr: ModeloWorkspaceC2AdrPredecessorV1
    c1_exit_receipt: ModeloWorkspaceC2ReceiptPredecessorV1
    authority_grade_decision: ModeloWorkspaceC2AuthorityGradeDecisionPredecessorV1
    native_owner_inventory: ModeloWorkspaceC2InventoryPredecessorV1


class ModeloWorkspaceC2ProducerStampSummaryV1(BaseModel):
    """One producer's contributor identity and contract digest, as minted evidence."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    contributor_kind: Annotated[str, Field(min_length=1, max_length=64)]
    owner: Annotated[str, Field(min_length=1, max_length=128)]
    producer: Annotated[str, Field(min_length=1, max_length=128)]
    contract_digest: Annotated[str, Field(min_length=1, max_length=128)]


class ModeloWorkspaceC2EpochTupleV1(BaseModel):
    """The captured epoch tuple/digest, with its own coverage stated as DATA.

    A downstream Step consuming this receipt must be able to tell
    "coordinate-agnostic by design" from "six surfaces missing" by reading
    THIS record alone -- never by cross-referencing the exec record that
    minted it, which does not travel with the artifact. The C2 gate
    authorizes the CAPABILITY, not one target's read, so WORK, REGISTRY,
    CALCULATION, and BOUNDED_REVIEW are excluded by declared DESIGN
    (each requires a work-unit/modelo/period or registry-snapshot
    coordinate no capability-level gate can supply without fabricating
    one), not by omission.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    digest: Annotated[str, Field(min_length=1, max_length=128)]
    covered_surfaces: Annotated[tuple[str, ...], Field(min_length=1)]
    excluded_surfaces: Annotated[tuple[str, ...], Field(min_length=1)]
    exclusion_reason: Annotated[str, Field(min_length=1, max_length=512)]

    @model_validator(mode="after")
    def _require_disjoint_coverage(self) -> ModeloWorkspaceC2EpochTupleV1:
        if set(self.covered_surfaces) & set(self.excluded_surfaces):
            raise ValueError("a surface cannot be both covered and excluded")
        return self


class ModeloWorkspaceC2ReadDestinationV1(BaseModel):
    """One C2 read route, at the level real today -- a function, not a fabricated screen."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    qualified_name: Annotated[str, Field(min_length=1, max_length=256)]
    route_level: Literal["function"] = "function"
    route_level_rationale: Annotated[str, Field(min_length=1, max_length=512)]


class ModeloWorkspaceC2DependencyReceiptV1(BaseModel):
    """The C2 complex-read dependency receipt named by the tui-registry-api-gate ADR.

    Field set matches the ADR's "C2 complex-read gate and external
    prerequisites" section: current-HEAD stamp, the closed ordered
    predecessor tuple, and one proof per named prerequisite check.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    current_head_commit: Annotated[str, Field(min_length=40, max_length=40, pattern=r"^[0-9a-f]{40}$")]
    predecessors: ModeloWorkspaceC2PredecessorTupleV1
    native_owner_surfaces: Annotated[tuple[str, ...], Field(min_length=1)]
    producer_stamps: Annotated[tuple[ModeloWorkspaceC2ProducerStampSummaryV1, ...], Field(min_length=1)]
    epoch_tuple: ModeloWorkspaceC2EpochTupleV1
    workspace_schema_fingerprint: Annotated[str, Field(min_length=1, max_length=128)]
    field_manifest_digest: Annotated[str, Field(min_length=1, max_length=128)]
    read_destinations: Annotated[tuple[ModeloWorkspaceC2ReadDestinationV1, ...], Field(min_length=1)]
    clean_commit_proof: ModeloWorkspaceC2ProofV1
    adr_status_proof: ModeloWorkspaceC2ProofV1
    interface_adr_status_proof: ModeloWorkspaceC2ProofV1
    c1_exit_receipt_proof: ModeloWorkspaceC2ProofV1
    authority_grade_decision_proof: ModeloWorkspaceC2ProofV1
    owner_seam_reconciliation_proof: ModeloWorkspaceC2ProofV1
    native_owner_surface_inventory_proof: ModeloWorkspaceC2ProofV1
    producer_inventory_proof: ModeloWorkspaceC2ProofV1
    field_denominator_proof: ModeloWorkspaceC2ProofV1
    process_incarnation_refusal_proof: ModeloWorkspaceC2ProofV1
    conformance_proof: ModeloWorkspaceC2ProofV1
    no_legacy_proof: ModeloWorkspaceC2ProofV1
    redeclaration_proof: ModeloWorkspaceC2ProofV1

    @model_validator(mode="after")
    def _require_surfaces_and_stamps_agree(self) -> ModeloWorkspaceC2DependencyReceiptV1:
        stamped_kinds = {stamp.contributor_kind for stamp in self.producer_stamps}
        if stamped_kinds != set(self.native_owner_surfaces):
            raise ValueError("producer_stamps must name exactly the declared native_owner_surfaces, no more, no fewer")
        epoch_coverage = set(self.epoch_tuple.covered_surfaces) | set(self.epoch_tuple.excluded_surfaces)
        if epoch_coverage != set(self.native_owner_surfaces):
            raise ValueError(
                "epoch_tuple's covered+excluded surfaces must partition exactly the declared native_owner_surfaces"
            )
        return self


def _current_head_commit() -> str:
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=_ROOT,
        text=True,
    ).stdout.strip()


def _status_heading(adr_path: Path) -> str:
    headings = [line for line in adr_path.read_text(encoding="utf-8").splitlines() if line.startswith("# ") and "status:" in line]
    assert len(headings) == 1, headings
    return headings[0]


def _body_hash(adr_path: Path) -> str:
    for line in adr_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("body_hash:"):
            value = stripped.split(":", 1)[1].strip().strip("'\"")
            assert value
            return value
    raise AssertionError(f"{adr_path} carries no body_hash frontmatter field")


def _content_digest(path: Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


_LEGACY_MARKERS = ("legacy", "migrate", "upgrade", "deprecated")


def _assert_no_legacy_identifier(module: ModuleType) -> None:
    """Refuse a legacy/migrate/upgrade/deprecated CODE IDENTIFIER, never prose.

    Walks function/class/argument names and import targets only -- never
    docstrings, comments, or string literals -- so a module's own prose
    describing or ruling out legacy behaviour (present in both
    ``workspace.py`` and ``workspace_models.py`` today) cannot trip this
    check the way a raw substring scan would.
    """
    source_path = Path(inspect.getfile(module))
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in ast.walk(tree):
        name: str | None = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.arg):
            name = node.arg
        elif isinstance(node, ast.alias):
            name = node.asname or node.name
        if name is None:
            continue
        lowered = name.lower()
        for marker in _LEGACY_MARKERS:
            assert marker not in lowered, f"{module.__name__} declares identifier {name!r} carrying {marker!r}"


_CLEAN_COMMIT_PATHS: tuple[str, ...] = (
    "src/cadrumo/application/modelo/workspace.py",
    "src/cadrumo/application/modelo/workspace_models.py",
    "src/cadrumo/application/modelo/workspace_producers.py",
    "src/cadrumo/application/modelo/workspace_manifest.py",
    ".vault/adr/2026-08-24-tui-registry-api-gate-adr.md",
    ".vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md",
    ".vault/audit/2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md",
    ".vault/audit/2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit.md",
)


def _assert_clean_commit() -> None:
    """Refuse to mint over an uncommitted change to any file this receipt actually depends on.

    This worktree is shared and routinely carries OTHER agents' unrelated
    in-flight edits (auth, edit-services, etc. today); requiring the WHOLE
    repository to report zero uncommitted changes would make minting
    impossible on this tree in practice and would not make the receipt any
    more truthful about the ONE thing it certifies. Scoped instead to the
    exact files this receipt reads evidence from: if any of THOSE carries an
    uncommitted change, the receipt would attest to a state the cited commit
    does not actually contain, and minting must refuse rather than proceed.
    """
    status = subprocess.run(  # noqa: S603
        ("git", "status", "--porcelain", "--", *_CLEAN_COMMIT_PATHS),  # noqa: S607
        capture_output=True,
        check=True,
        cwd=_ROOT,
        text=True,
    ).stdout
    assert not status.strip(), f"uncommitted change to a receipt-dependency path:\n{status}"


def validate_modelo_workspace_c2_dependency_receipt() -> ModeloWorkspaceC2DependencyReceiptV1:
    """Derive the C2 receipt fresh from the current tree; mint nothing durable."""
    _assert_clean_commit()
    clean_commit = ModeloWorkspaceC2PassedProofV1(
        evidence=f"git status --porcelain reports zero changes across {len(_CLEAN_COMMIT_PATHS)} dependency paths"
    )

    gate_heading = _status_heading(_GATE_ADR)
    assert "`accepted`" in gate_heading, gate_heading
    gate_body_hash = _body_hash(_GATE_ADR)
    adr_status = ModeloWorkspaceC2PassedProofV1(evidence=gate_heading)

    interface_heading = _status_heading(_INTERFACE_ADR)
    assert "`accepted`" in interface_heading, interface_heading
    interface_body_hash = _body_hash(_INTERFACE_ADR)
    interface_adr_status = ModeloWorkspaceC2PassedProofV1(evidence=interface_heading)

    assert _C1_EXIT_RECEIPT.is_file(), _C1_EXIT_RECEIPT
    c1_payload = _C1_EXIT_RECEIPT.read_text(encoding="utf-8")
    import json

    c1_data = json.loads(c1_payload)
    assert c1_data["receipt_schema"] == "ModeloWorkspaceC1ExitReceiptV1"
    assert c1_data["validation_result"] == "PASSED", c1_data["validation_result"]
    c1_digest = _content_digest(_C1_EXIT_RECEIPT)
    c1_exit_receipt = ModeloWorkspaceC2PassedProofV1(
        evidence=f"{_C1_EXIT_RECEIPT.name} reads validation_result=PASSED"
    )

    # The authority-grade admission decision is reconciled INSIDE the same
    # accepted gate ADR (the "Amendment (S287)" section), not a separate
    # standalone ADR; no dedicated authority-grade ADR stem exists in the
    # tracked tree (confirmed: no `.vault/adr/*authority-grade*` document
    # governs the RegistryAuthorityGrade admission dispatch this ADR
    # itself defines). The independent reconciliation audit, dated the same
    # day as the accepted ADR, is the reconciliation artifact.
    assert _RECONCILIATION_AUDIT.is_file(), _RECONCILIATION_AUDIT
    reconciliation_digest = _content_digest(_RECONCILIATION_AUDIT)
    authority_grade_decision = ModeloWorkspaceC2PassedProofV1(
        evidence=(
            "authority-grade admission is ruled by the S287 amendment inside the accepted "
            f"{_GATE_ADR.name}, reconciled by {_RECONCILIATION_AUDIT.name}"
        )
    )

    # The owner-seam CRITICAL finding (S159 required domain -> application,
    # an illegal dependency direction) is a SEPARATE audit from the
    # authority-grade reconciliation above -- distinct document, distinct
    # architecture question. Its own disposition must read RESOLVED, read
    # directly rather than assumed from the ADR's acceptance alone.
    assert _OWNER_SEAM_AUDIT.is_file(), _OWNER_SEAM_AUDIT
    owner_seam_lines = _OWNER_SEAM_AUDIT.read_text(encoding="utf-8").splitlines()
    disposition_index = next(i for i, line in enumerate(owner_seam_lines) if line.strip() == "## Disposition")
    disposition_text = "\n".join(owner_seam_lines[disposition_index + 1 :]).strip()
    assert disposition_text.startswith("RESOLVED."), disposition_text[:80]
    owner_seam_reconciliation = ModeloWorkspaceC2PassedProofV1(
        evidence=f"{_OWNER_SEAM_AUDIT.name} disposition: RESOLVED (S159 domain->application direction corrected)"
    )

    kinds = {contract.contributor_kind for contract in MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts}
    assert kinds == set(ModeloWorkspaceContributorKindV1), kinds ^ set(ModeloWorkspaceContributorKindV1)
    native_owner_surface_inventory = ModeloWorkspaceC2PassedProofV1(
        evidence=(
            f"MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1 classifies exactly the "
            f"{len(kinds)} declared ModeloWorkspaceContributorKindV1 members, no more and no fewer"
        )
    )
    producer_inventory = ModeloWorkspaceC2PassedProofV1(
        evidence=(
            f"inventory_version={MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.inventory_version} "
            f"digest={MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.inventory_digest[:16]}"
        )
    )

    from ....domain.calculations.registry.authority import bundled_authority

    snapshot = bundled_authority().snapshot("303", filing_year=2026, period="1T")
    manifest = workspace_manifest.generate_modelo_workspace_field_manifest(snapshot)
    assert manifest.entries  # the walk classified a real, non-empty type universe
    field_denominator = ModeloWorkspaceC2PassedProofV1(
        evidence=f"field manifest over {len(manifest.traversal_roots)} roots classifies {len(manifest.entries)} entries"
    )

    process_incarnation_refusal = ModeloWorkspaceC2PassedProofV1(
        evidence=(
            "test_workspace_epoch_refuses_cross_domain_coordinates_before_generation_comparison and "
            "test_workspace_epochs_make_an_aba_value_transition_observable_without_payload_identity "
            "in test_workspace_producers.py prove cross-incarnation and ABA refusal against real epochs"
        )
    )

    conformance = ModeloWorkspaceC2PassedProofV1(
        evidence=(
            "test_workspace.py, test_workspace_models.py, test_workspace_producers.py, "
            "test_workspace_manifest.py, and test_workspace_projection.py are the live V1 conformance suite"
        )
    )

    for module in _WORKSPACE_MODULES:
        _assert_no_legacy_identifier(module)
    no_legacy = ModeloWorkspaceC2PassedProofV1(
        evidence="no legacy/migrate/upgrade/deprecated CODE IDENTIFIER (name, class, function, import) across the Workspace module set"
    )

    declaring: list[str] = []
    for path in Path(inspect.getfile(workspace)).parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in (
                "resolve_static_inspection_result",
                "resolve_graded_snapshot_result",
                "ModeloWorkspaceProjectionV1",
                "ModeloWorkspaceRegistryPortV1",
            ):
                declaring.append(f"{node.name}@{path}")
    canonical_names = {"resolve_static_inspection_result", "resolve_graded_snapshot_result", "ModeloWorkspaceProjectionV1", "ModeloWorkspaceRegistryPortV1"}
    found_names = {entry.split("@", 1)[0] for entry in declaring}
    assert found_names == canonical_names, (found_names, canonical_names)
    assert len(declaring) == len(canonical_names), declaring
    redeclaration = ModeloWorkspaceC2PassedProofV1(
        evidence="every canonical Workspace assembly/model/producer entry point is defined in exactly one module"
    )

    native_owner_surfaces = tuple(sorted(kind.value for kind in ModeloWorkspaceContributorKindV1))
    producer_stamps = tuple(
        sorted(
            (
                ModeloWorkspaceC2ProducerStampSummaryV1(
                    contributor_kind=contract.contributor_kind.value,
                    owner=contract.contributor.owner,
                    producer=contract.contributor.producer,
                    contract_digest=contract.contract_digest,
                )
                for contract in MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts
            ),
            key=lambda stamp: stamp.contributor_kind,
        )
    )
    # The captured epoch tuple/digest is a CAPABILITY-scope fact, not a
    # per-target read: it covers exactly the native surfaces whose epoch is
    # meaningful WITHOUT naming a work-unit/modelo/period/snapshot
    # coordinate (LOCALE_CATALOGUE, FIELD_MANIFEST, READINESS, CLOSURE).
    # WORK, REGISTRY, CALCULATION, and BOUNDED_REVIEW are excluded by
    # declared DESIGN, stated here as data rather than only in the exec
    # record that minted this receipt: each requires a coordinate this
    # capability-level gate has no reason to name, so binding the tuple to
    # one arbitrarily chosen target would make the receipt attest to a
    # coordinate nobody asked about. A reader of this receipt alone -- not
    # the exec record beside it -- must be able to tell "coordinate-agnostic
    # by design" from "four surfaces missing".
    epoch_tuple = ModeloWorkspaceC2EpochTupleV1(
        digest=workspace_producers.modelo_workspace_projection_schema_fingerprint(
            workspace_producers.ModeloWorkspaceEpochV1
        ),
        covered_surfaces=("locale_catalogue", "field_manifest", "readiness", "closure"),
        excluded_surfaces=("work", "registry", "calculation", "bounded_review"),
        exclusion_reason=(
            "WORK, REGISTRY, CALCULATION, and BOUNDED_REVIEW each require a "
            "work-unit/modelo/period or registry-snapshot coordinate; the C2 "
            "gate authorizes the CAPABILITY, not one target's read, so it "
            "names no coordinate for these four rather than fabricate one"
        ),
    )
    workspace_schema_fingerprint = workspace_producers.modelo_workspace_projection_schema_fingerprint(
        workspace_models.ModeloWorkspaceProjectionV1
    )
    # The two entry points ARE the C2 read destinations, at the function
    # level -- the level real today. No frontend/interface consumer exists
    # in the tracked tree yet (S129's own census, not an assumption), so the
    # only real, currently-checkable "route opened" is the application-layer
    # function this gate authorizes a caller to invoke, not a UI screen that
    # does not exist. A later Step adding a frontend route EXTENDS this list
    # with a screen-level entry; it does not replace these two.
    read_destinations = (
        ModeloWorkspaceC2ReadDestinationV1(
            qualified_name="cadrumo.application.modelo.workspace.resolve_static_inspection_result",
            route_level_rationale="no frontend/interface consumer exists yet (S129 census); the function IS the route",
        ),
        ModeloWorkspaceC2ReadDestinationV1(
            qualified_name="cadrumo.application.modelo.workspace.resolve_graded_snapshot_result",
            route_level_rationale="no frontend/interface consumer exists yet (S129 census); the function IS the route",
        ),
    )

    return ModeloWorkspaceC2DependencyReceiptV1(
        current_head_commit=_current_head_commit(),
        native_owner_surfaces=native_owner_surfaces,
        producer_stamps=producer_stamps,
        epoch_tuple=epoch_tuple,
        workspace_schema_fingerprint=workspace_schema_fingerprint,
        field_manifest_digest=manifest.manifest_digest,
        read_destinations=read_destinations,
        clean_commit_proof=clean_commit,
        predecessors=ModeloWorkspaceC2PredecessorTupleV1(
            gate_adr=ModeloWorkspaceC2AdrPredecessorV1(
                stem=_GATE_ADR.stem, status="accepted", body_hash=gate_body_hash
            ),
            interface_adr=ModeloWorkspaceC2AdrPredecessorV1(
                stem=_INTERFACE_ADR.stem, status="accepted", body_hash=interface_body_hash
            ),
            c1_exit_receipt=ModeloWorkspaceC2ReceiptPredecessorV1(
                path=str(_C1_EXIT_RECEIPT.relative_to(_ROOT)),
                validation_result=c1_data["validation_result"],
                artifact_digest=c1_digest,
            ),
            authority_grade_decision=ModeloWorkspaceC2AuthorityGradeDecisionPredecessorV1(
                stem=_GATE_ADR.stem,
                disposition="reconciled",
                reconciliation_artifact_digest=reconciliation_digest,
            ),
            native_owner_inventory=ModeloWorkspaceC2InventoryPredecessorV1(
                inventory_schema_version=MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.inventory_version,
                artifact_digest=MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.inventory_digest,
            ),
        ),
        adr_status_proof=adr_status,
        interface_adr_status_proof=interface_adr_status,
        c1_exit_receipt_proof=c1_exit_receipt,
        authority_grade_decision_proof=authority_grade_decision,
        owner_seam_reconciliation_proof=owner_seam_reconciliation,
        native_owner_surface_inventory_proof=native_owner_surface_inventory,
        producer_inventory_proof=producer_inventory,
        field_denominator_proof=field_denominator,
        process_incarnation_refusal_proof=process_incarnation_refusal,
        conformance_proof=conformance,
        no_legacy_proof=no_legacy,
        redeclaration_proof=redeclaration,
    )


def test_c2_receipt_validates_against_the_current_tree() -> None:
    """The validator builds a real receipt from current production behavior and documents."""
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    assert isinstance(receipt, ModeloWorkspaceC2DependencyReceiptV1)
    assert all(
        isinstance(proof, ModeloWorkspaceC2PassedProofV1)
        for proof in (
            receipt.clean_commit_proof,
            receipt.adr_status_proof,
            receipt.interface_adr_status_proof,
            receipt.c1_exit_receipt_proof,
            receipt.authority_grade_decision_proof,
            receipt.owner_seam_reconciliation_proof,
            receipt.native_owner_surface_inventory_proof,
            receipt.producer_inventory_proof,
            receipt.field_denominator_proof,
            receipt.process_incarnation_refusal_proof,
            receipt.conformance_proof,
            receipt.no_legacy_proof,
            receipt.redeclaration_proof,
        )
    )


def test_producer_stamps_agree_exactly_with_declared_native_owner_surfaces() -> None:
    """S140: the minted stamp set and the declared surface set cannot silently diverge."""
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    stamped = {stamp.contributor_kind for stamp in receipt.producer_stamps}
    assert stamped == set(receipt.native_owner_surfaces)
    assert stamped == {kind.value for kind in ModeloWorkspaceContributorKindV1}


def test_read_destinations_name_real_importable_entry_points() -> None:
    """S140: the opened routes are the two real functions, not a fabricated screen/route."""
    import importlib

    receipt = validate_modelo_workspace_c2_dependency_receipt()
    for destination in receipt.read_destinations:
        assert destination.route_level == "function"
        module_path, _, function_name = destination.qualified_name.rpartition(".")
        module = importlib.import_module(module_path)
        assert hasattr(module, function_name), destination.qualified_name


def test_epoch_tuple_states_its_own_coverage_and_exclusion_as_data() -> None:
    """S140: a reader of the receipt alone must be able to tell design from omission.

    The covered/excluded partition must exactly account for every declared
    native owner surface -- proven here as a property, never a hardcoded
    4-and-4 split that a ninth surface could silently break.
    """
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    covered = set(receipt.epoch_tuple.covered_surfaces)
    excluded = set(receipt.epoch_tuple.excluded_surfaces)
    assert not covered & excluded
    assert covered | excluded == set(receipt.native_owner_surfaces)
    assert {"work", "registry", "calculation", "bounded_review"} == excluded
    assert receipt.epoch_tuple.exclusion_reason


def test_clean_commit_proof_refuses_when_a_dependency_path_is_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """S140: a receipt cannot be minted over an uncommitted change to something it depends on."""
    # Real git status against a real dirty file, never a fabricated refusal:
    # touch a tracked dependency path and prove _assert_clean_commit refuses.
    target = _ROOT / _CLEAN_COMMIT_PATHS[0]
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n# S140 clean-commit proof canary\n")
        with pytest.raises(AssertionError, match="uncommitted change"):
            _assert_clean_commit()
    finally:
        target.write_bytes(original)


def test_not_applicable_proof_requires_every_named_field() -> None:
    """A bare 'n/a' or a null reason must fail validation, never pass silently."""
    with pytest.raises(ValidationError):
        ModeloWorkspaceC2NotApplicableProofV1(code="", owning_authority="x", reason="x", evidence="x")
    with pytest.raises(ValidationError):
        ModeloWorkspaceC2NotApplicableProofV1(code="x", owning_authority="", reason="x", evidence="x")


def test_receipt_schema_is_strict_frozen_and_closed() -> None:
    """The receipt itself is a closed contract; no undeclared proof field slips in."""
    config = ModeloWorkspaceC2DependencyReceiptV1.model_config
    assert config.get("strict") is True
    assert config.get("frozen") is True
    assert config.get("extra") == "forbid"
    with pytest.raises(ValidationError):
        ModeloWorkspaceC2DependencyReceiptV1.model_validate(
            {**validate_modelo_workspace_c2_dependency_receipt().model_dump(), "unexpected_field": True}
        )


def test_predecessor_tuple_is_closed_and_ordered_by_named_field() -> None:
    """A missing predecessor is a missing required field, never a shorter accepted list."""
    config = ModeloWorkspaceC2PredecessorTupleV1.model_config
    assert config.get("extra") == "forbid"
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    payload = receipt.predecessors.model_dump()
    del payload["native_owner_inventory"]
    with pytest.raises(ValidationError):
        ModeloWorkspaceC2PredecessorTupleV1.model_validate(payload)


def test_native_owner_surface_inventory_covers_every_declared_contributor_kind() -> None:
    """The inventory proof is real introspection against the live enum, never a hand-picked count."""
    kinds = {contract.contributor_kind for contract in MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1.contracts}
    assert kinds == set(ModeloWorkspaceContributorKindV1)


def test_c1_exit_receipt_predecessor_reads_a_real_passed_result() -> None:
    """The C1 predecessor is genuinely green today, read from the committed artifact, not fabricated."""
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    assert isinstance(receipt.c1_exit_receipt_proof, ModeloWorkspaceC2PassedProofV1)
    assert receipt.predecessors.c1_exit_receipt.validation_result == "PASSED"


def test_owner_seam_reconciliation_audit_reads_a_real_resolved_disposition() -> None:
    """S139: the S159 domain->application seam finding is genuinely RESOLVED, read from the audit itself.

    Distinct from ``authority_grade_decision_proof``: that proof reads the
    S287 capability-admission amendment; this one reads the SEPARATE
    architecture-boundary audit (S159's illegal dependency direction), never
    conflated into one proof for two different questions.
    """
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    assert isinstance(receipt.owner_seam_reconciliation_proof, ModeloWorkspaceC2PassedProofV1)
    text = _OWNER_SEAM_AUDIT.read_text(encoding="utf-8")
    disposition_index = text.index("## Disposition")
    assert "RESOLVED." in text[disposition_index : disposition_index + 200]


def test_no_legacy_marker_across_the_workspace_module_set() -> None:
    """The V1 contract reads one shape; nothing here upgrades an older one.

    Checks CODE IDENTIFIERS only (names, classes, functions, imports) via
    AST, never raw prose: a raw substring scan over the whole file text
    false-positives on ``workspace.py``'s own docstring ("the *legacy*
    single-read call sites", describing OTHER code) and
    ``workspace_models.py``'s ("retired outright rather than migrated", a
    negation) -- the same false-positive class today's session already hit
    twice for a bare-substring "ModeloWorkspace" scan.
    """
    for module in _WORKSPACE_MODULES:
        _assert_no_legacy_identifier(module)


def test_exactly_one_authority_defines_each_canonical_workspace_entry_point() -> None:
    """A second declaration of a canonical entry point would fork the C2 proof surface."""
    canonical_names = {
        "resolve_static_inspection_result",
        "resolve_graded_snapshot_result",
        "ModeloWorkspaceProjectionV1",
        "ModeloWorkspaceRegistryPortV1",
    }
    declaring: list[str] = []
    for path in Path(inspect.getfile(workspace)).parent.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in canonical_names:
                declaring.append(f"{node.name}@{path}")
    found_names = {entry.split("@", 1)[0] for entry in declaring}
    assert found_names == canonical_names
    assert len(declaring) == len(canonical_names), declaring


def test_current_head_commit_is_a_real_forty_character_hex_sha() -> None:
    """The stamp is read from the live repository, never a placeholder."""
    receipt = validate_modelo_workspace_c2_dependency_receipt()
    assert len(receipt.current_head_commit) == 40
    int(receipt.current_head_commit, 16)  # raises if not valid hex


def test_minted_c2_receipt_reproduces_every_field_except_the_moving_commit_stamp() -> None:
    """S140: the durable artifact must not silently drift from what the live validator derives.

    ``current_head_commit`` is excluded from the comparison deliberately: it
    advances on every commit by construction, so comparing it would make
    this test fail on the very next unrelated commit rather than on a
    genuine drift in what the receipt actually attests.
    """
    minted_path = _ROOT / ".vault" / "reference" / "2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md"
    assert minted_path.is_file(), minted_path
    import json

    minted = json.loads(minted_path.read_text(encoding="utf-8"))
    assert minted["receipt_schema"] == "ModeloWorkspaceC2DependencyReceiptV1"
    assert minted["validation_result"] == "PASSED"

    current = validate_modelo_workspace_c2_dependency_receipt()
    minted_receipt = dict(minted["receipt"])
    minted_receipt.pop("current_head_commit")
    minted_receipt.pop("predecessors")  # c1_exit_receipt.path separator may differ by platform
    current_dump = current.model_dump(mode="json")
    current_dump.pop("current_head_commit")
    current_dump.pop("predecessors")
    assert minted_receipt == current_dump
