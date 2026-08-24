"""Shared wizard-registered profile bucket for the mínimo advisory suite.

Every advisory test in this cluster does the same setup: open an isolated,
wizard-registered profile bucket scoped to the test's own ``tmp_path``. What
must NOT be shared is which bucket id each module opens -- some modules read
their own module-level ``_BUCKET_ID`` again later, in assertions and collector
calls, so a module that silently inherited another module's id would still
pass while asserting against the wrong bucket. Each consuming module supplies
its own id by overriding ``bucket_id`` (the shared scaffold in
:mod:`cadrumo.tests._bucket_id_fixture`); its default raises so a module that
forgets the override fails loudly instead of inheriting one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests import bucket_id  # noqa: F401
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...aggregation import CalculationSourceDiagnostic


def operator_text(diagnostic: CalculationSourceDiagnostic) -> str:
    """The text an OPERATOR sees, not the message field alone.

    A diagnostic states the problem in ``message`` and the fix in ``remedy``,
    which the calculate CLI projects onto the notice's ``suggestion`` and renders
    as one line. Asserting against ``message`` alone would let a remedy fall off
    the operator-facing surface without any test noticing.
    """
    remedy = getattr(diagnostic, "remedy", None)
    message = diagnostic.message
    return message if remedy is None else f"{message} {remedy}"


@pytest.fixture(autouse=True)
def _bucket(tmp_path: Path, bucket_id: str) -> Iterator[None]:  # noqa: F811 - pytest injects the imported fixture
    from ... import wizard as _wizard

    assert _wizard.WIZARD_FLOWS
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(bucket_id):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(profile_id=bucket_id)
        yield
