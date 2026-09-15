"""Development-only regression coverage for generation-pinned parameter reads."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry import formula_runtime_ops
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    ModeloRevisionComponentQuery,
)
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.formula_runtime_ops import read_parameter
from cadrumo.domain.calculations.registry.schema_formula import DatedValue, ParameterDefinition
from cadrumo.domain.calculations.registry.tests._artifact_runtime_support import (
    _minimal_catalogues,
    _minimal_modelo,
    _minimal_revision,
)
from cadrumo.domain.user_profile.schema import (
    ProfileFieldDefinition,
    ProfileFieldType,
    ProfileRemovePolicy,
    ProfileSchemaDefinition,
    ProfileSectionDefinition,
    ProfileSnapshotPolicy,
)

from ..pipeline.authority_publication import install_validated_authority_database

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_ID = "130"
_REVISION_ID = "test-revision"
_PARAMETER_ID = "synthetic-rate"


def _profile_schema() -> ProfileSchemaDefinition:
    """Build the smallest valid profile component required by publication."""
    return ProfileSchemaDefinition(
        id="cadrumo.user_profile",
        version=1,
        title="Parameter invalidation fixture",
        snapshot_policy=ProfileSnapshotPolicy.IMMUTABLE_SECURE_SNAPSHOT_HASH,
        remove_policy=ProfileRemovePolicy.LIVE_PROFILE_TOMBSTONE_RETAIN_SNAPSHOTS,
        sections=(
            ProfileSectionDefinition(
                key="identity",
                title="Identity",
                sensitivity=SensitivityClass.IDENTITY,
                fields=(
                    ProfileFieldDefinition(
                        key="tax_id",
                        type=ProfileFieldType.STRING,
                        sensitivity=SensitivityClass.IDENTITY,
                        description="Tax identifier",
                    ),
                ),
            ),
        ),
    )


def _artifact(value: str) -> AuthorityArtifact:
    """Build one immutable authority generation carrying the fixture rate."""
    catalogues = _minimal_catalogues()
    legal_id = next(iter(catalogues.legal))
    source_id = next(iter(catalogues.sources))
    parameter = ParameterDefinition(
        id=_PARAMETER_ID,
        data_type="ratio",
        unit="ratio",
        values=(
            DatedValue(
                value=Decimal(value),
                date_axis="filing_period",
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
        ),
        legal_refs=(legal_id,),
        source_refs=(source_id,),
    )
    revision = _minimal_revision().model_copy(update={"parameters": (parameter,)})
    build_identity = AuthorityBuildIdentity.from_inputs(
        sha256_hex(f"fixture-source:{value}".encode()),
        sha256_hex(b"fixture-authority-compiler"),
    )
    return AuthorityArtifact(
        modelos=(_minimal_modelo(revision),),
        catalogues=catalogues,
        identity_digest=build_identity.identity_digest,
        build_identity=build_identity,
        profile_schema=_profile_schema(),
        evidence=AuthorityEvidenceProjection(),
    )


def test_read_parameter_sees_a_registry_edit_under_a_new_generation(tmp_path: Path) -> None:
    """A descriptor cutover reaches the next operation without cache reuse."""
    authority_root = tmp_path / "authority"
    first_artifact = _artifact("0.05")
    first_descriptor = install_validated_authority_database(
        first_artifact,
        destination=authority_root,
        require_current=lambda: None,
    )
    authority = IndexedRegistryAuthority(authority_root / "authority.current.json")
    try:
        with authority.operation() as first_operation:
            before = read_parameter(
                _MODELO_ID,
                _REVISION_ID,
                _PARAMETER_ID,
                date_context={"filing_period": date(2025, 6, 30)},
                operation=first_operation,
            )
            assert before == Decimal("0.05")
            first_generation = first_operation.pin()
            assert first_generation.logical_generation == first_descriptor.logical_generation

            second_artifact = _artifact("0.06")
            second_descriptor = install_validated_authority_database(
                second_artifact,
                destination=authority_root,
                require_current=lambda: None,
            )
            assert first_artifact.identity_digest == first_descriptor.logical_generation
            assert second_artifact.identity_digest == second_descriptor.logical_generation
            assert (
                second_artifact.build_identity.source_identity_digest
                != first_artifact.build_identity.source_identity_digest
            )
            assert second_descriptor.logical_generation != first_descriptor.logical_generation

            held = read_parameter(
                _MODELO_ID,
                _REVISION_ID,
                _PARAMETER_ID,
                date_context={"filing_period": date(2025, 6, 30)},
                operation=first_operation,
            )
            assert held == Decimal("0.05")

            with authority.operation() as current_operation:
                after = read_parameter(
                    _MODELO_ID,
                    _REVISION_ID,
                    _PARAMETER_ID,
                    date_context={"filing_period": date(2025, 6, 30)},
                    operation=current_operation,
                )
                assert after == Decimal("0.06")
                assert current_operation.pin().logical_generation == second_descriptor.logical_generation
                with pytest.raises(RegistrySnapshotError, match="generation boundary"):
                    first_operation.load(
                        ModeloRevisionComponentQuery(_MODELO_ID, _REVISION_ID),
                        pin=current_operation.pin(),
                    )
    finally:
        authority.close()


def test_no_memo_in_the_parameter_read_module_can_outlive_a_registry_edit() -> None:
    """No callable in this module carries a functools memo.

    Derived rather than enumerated, so it also catches a memo added to a
    function this test has never heard of. Any memo here is keyed on the
    arguments of a registry READ, and none of those arguments -- a modelo id, a
    revision id, a parameter id, a root path -- changes when the registry
    changes, so any such memo can outlive the tree it was computed from. The
    bounded caches this module must rely on live behind the authority, keyed on
    the complete authority generation identity.
    """
    memoised = sorted(name for name, value in vars(formula_runtime_ops).items() if hasattr(value, "cache_info"))
    assert memoised == [], (
        f"functools-memoised callables in the registry parameter-read module cannot observe a registry edit: {memoised}"
    )
