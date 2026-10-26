"""Real descriptor cutover while an encrypted-ledger membership query holds A."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.published_authority_support import release_published_authority_operation
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_membership import query_ledger_membership
from cadrumo.application.modelo.profile_readiness_gate import load_modelo_work_profile
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifact, AuthorityEvidenceProjection
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor
from cadrumo.domain.calculations.registry.tests.artifact_runtime_support import (
    minimal_catalogues,
    minimal_modelo,
    minimal_revision,
    synthetic_legal_identity,
)
from cadrumo.entrypoints.adapter_composition import build_ledger_membership_ports, profile_adapter_composition
from cadrumo.entrypoints.tests.profile_persistence.ledger_drift_support import BUCKET_ID, calculate_irene_revision
from cadrumo.tests.audited_process import run_audited_process
from dev.registry.pipeline.authority_publication import install_validated_authority_database

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _exercise_cutover(authority_root: Path, profile_root: Path) -> None:
    """Fresh process admits the temp root before its bundled singleton is opened."""
    with (
        profile_adapter_composition(),
        isolated_runtime_profile(tmp_path=profile_root, bucket_id=BUCKET_ID) as runtime,
        bundled_indexed_authority().operation() as held,
    ):
        result = calculate_irene_revision(runtime.repository, operation=held)
        target = result[0]
        work_units, _calculations, _filings, _reports, _events, transactions = result[3:]
        (unit,) = work_units.load().values()
        revision = held.revision(unit.modelo, unit.revision_id)
        profile = load_modelo_work_profile(bucket_id=BUCKET_ID, profile_decode_context=held.profile_decode_context())
        assert profile is not None
        ports = build_ledger_membership_ports(bucket_id=BUCKET_ID, transaction_repository=transactions)
        original_pin = held.pin()
        second = AuthorityArtifact(
            modelos=(minimal_modelo(minimal_revision()),),
            catalogues=minimal_catalogues(),
            identity_digest=synthetic_legal_identity("membership-second"),
            evidence=AuthorityEvidenceProjection(),
            profile_schema=held.profile_schema().model_copy(update={"title": "Membership generation B"}),
        )
        switched = install_validated_authority_database(
            second,
            destination=authority_root,
            require_current=lambda: None,
        )
        assert switched.logical_generation != original_pin.logical_generation
        with bundled_indexed_authority().operation() as current:
            assert current.pin().logical_generation == switched.logical_generation
            assert current.profile_schema().title == "Membership generation B"
            # B deliberately lacks IVA authority. A nested admission of B
            # must fail this same query, proving the retained-A assertion's teeth.
            unavailable = query_ledger_membership(
                target=target,
                work_unit=unit,
                revision=revision,
                profile=profile,
                ports=ports,
                operation=current,
            )
            assert unavailable.available is False
            # Even with B's fact scope active, the explicit A query retains A.
            observed = query_ledger_membership(
                target=target,
                work_unit=unit,
                revision=revision,
                profile=profile,
                ports=ports,
                operation=held,
            )
            assert observed.available is True
            assert observed.observed_transaction_ids == target.source_transaction_ids
            assert observed.observed_transaction_ids
        assert held.pin() == original_pin
        print(json.dumps({"retained_a": original_pin.logical_generation, "admitted_b": switched.logical_generation}))


def test_membership_keeps_held_generation_when_current_descriptor_changes(tmp_path: Path) -> None:
    """Use the production singleton with a fresh process, without changing globals."""
    origin = bundled_authority_descriptor_path()
    descriptor = AuthorityDescriptor.read(origin)
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    shutil.copy2(origin, authority_root / "authority.current.json")
    shutil.copy2(origin.parent / descriptor.database, authority_root / descriptor.database)
    completed = run_audited_process(
        [sys.executable, "-m", __name__, str(authority_root), str(tmp_path / "profile")],
        env={**os.environ, "CADRUMO_AUTHORITY_ROOT": str(authority_root)},
        capture_output=True,
        text=True,
        timeout=None,
    )
    assert isinstance(completed.stdout, str)
    assert isinstance(completed.stderr, str)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout.splitlines()[-1])
    assert receipt["retained_a"] == descriptor.logical_generation
    assert receipt["admitted_b"] != descriptor.logical_generation


if __name__ == "__main__":
    try:
        _exercise_cutover(Path(sys.argv[1]), Path(sys.argv[2]))
    finally:
        release_published_authority_operation()
