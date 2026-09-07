"""A read cohort refuses a projection whose contract it does not read.

``open_workspace_read_session`` is the one gate both admission paths cross
before a renderer receives a session, and its single refusal had no test
anywhere in the tree.

What it protects is a silent misreading rather than a crash. Every screen in
this cohort reads the projection positionally -- capabilities, casillas,
provenance, filing rows -- so a projection built under a different contract
would render field-for-field against the wrong meaning, and the operator would
see a workspace that looked entirely normal. Refusing is the only outcome that
cannot mislead.

The valid projection is obtained from the real resolver rather than assembled
here, and the invalid one is that same projection with its version moved, so
the test differs from production in exactly the fact under test.
"""

from __future__ import annotations

import pytest

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import ModeloWorkspaceProjectionV1
from ......core.external_constants import OutputLanguage
from ..controller import (
    SUPPORTED_WORKSPACE_CONTRACT_VERSION,
    ModeloWorkspaceSessionAdmissionError,
    admit_workspace_session,
    open_workspace_read_session,
)
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _admitted_projection(
    bucket_id: str,
    repository: WorkUnitCatalogueRepository,
) -> ModeloWorkspaceProjectionV1:
    """The real resolver's projection, already admitted once."""
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, OutputLanguage.ES))
    assert refusal is None, f"expected an admitted projection, got: {refusal}"
    assert session is not None
    return session.projection


def test_a_projection_on_the_supported_contract_opens_a_session(bucket_and_repository) -> None:
    """The control: the refusal below must not be a gate that rejects everything."""
    bucket_id, repository = bucket_and_repository
    projection = _admitted_projection(bucket_id, repository)

    session = open_workspace_read_session(projection)

    assert session.projection is projection
    assert projection.contract_version == SUPPORTED_WORKSPACE_CONTRACT_VERSION


def test_a_projection_from_a_newer_contract_is_refused(bucket_and_repository) -> None:
    """Rendering it would misread every positional field as though it fitted."""
    bucket_id, repository = bucket_and_repository
    projection = _admitted_projection(bucket_id, repository)
    newer = projection.model_copy(update={"contract_version": SUPPORTED_WORKSPACE_CONTRACT_VERSION + 1})

    with pytest.raises(ModeloWorkspaceSessionAdmissionError, match="does not read"):
        open_workspace_read_session(newer)


def test_a_projection_from_an_older_contract_is_refused_too(bucket_and_repository) -> None:
    """The refusal is an equality, not a floor.

    An older contract is as unreadable as a newer one -- this cohort reads
    exactly one version -- and testing only the newer direction would let a
    ``>=`` comparison pass while silently admitting every past shape.
    """
    bucket_id, repository = bucket_and_repository
    projection = _admitted_projection(bucket_id, repository)
    older = projection.model_copy(update={"contract_version": SUPPORTED_WORKSPACE_CONTRACT_VERSION - 1})

    with pytest.raises(ModeloWorkspaceSessionAdmissionError, match="does not read"):
        open_workspace_read_session(older)


def test_the_refusal_names_both_versions_so_the_gap_is_actionable(bucket_and_repository) -> None:
    """A version mismatch the operator cannot size is not a diagnosis.

    Naming what arrived AND what is read is what lets a reader tell an upgrade
    from a downgrade without reading this module.
    """
    bucket_id, repository = bucket_and_repository
    projection = _admitted_projection(bucket_id, repository)
    newer = projection.model_copy(update={"contract_version": SUPPORTED_WORKSPACE_CONTRACT_VERSION + 1})

    with pytest.raises(ModeloWorkspaceSessionAdmissionError) as raised:
        open_workspace_read_session(newer)

    message = str(raised.value)
    assert str(SUPPORTED_WORKSPACE_CONTRACT_VERSION + 1) in message
    assert str(SUPPORTED_WORKSPACE_CONTRACT_VERSION) in message
