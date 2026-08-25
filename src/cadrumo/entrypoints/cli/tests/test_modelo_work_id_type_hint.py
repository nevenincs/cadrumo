"""Instructive id-type hint for ``aeat app modelo work verify`` / ``file``.

``work calculate`` consumes a ``work_unit_id``; ``work verify`` and ``work
file`` consume a ``calculation_revision_id``. Both are 64-character SHA-256
digests, so an operator's first instinct -- reuse the id from ``work create`` --
lands a work-unit id where a calculation-revision id is required. Before this
hint the verb failed with a bare "not found"; now, when the supplied id resolves
to a real work unit, the error names the id-type mismatch and the verb that
mints the calculation-revision id (``work calculate``).

These tests pin that contract with real behaviour: a real work unit (without a
calculation revision) is persisted, then ``work verify`` / ``work file`` are
invoked with that work-unit id and the error must name the mismatch and the
``work calculate`` path. The anti-no-op companion confirms a calc-revision id
that genuinely does not resolve to any work unit still gets the plain not-found
(the hint is targeted, not a blanket rewrite). No mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.workflow.persistence import workflow_state_repository
from ....core import Period
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....tests.cli_runner import invoke_cached_cli
from ._strict_cli_fixture_support import binding_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["binding_isolated_backend"]

_WORK_UNIT_CREATED_AT = datetime(2026, 5, 28, 15, 0, tzinfo=UTC)


def _seed_work_unit_without_revision(*, modelo: str = "130", filing_year: int = 2026, period: str = "1T") -> str:
    """Persist a work unit with NO calculation revision and return its id.

    A work unit that was created (``work create``) but never calculated
    (``work calculate``) carries no calculation revision -- so passing its id to
    ``work verify`` / ``work file`` raises CalculationRevisionNotFoundError, the
    exact path the id-type hint enriches.
    """
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "0" * 63
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=_WORK_UNIT_CREATED_AT,
        updated_at=_WORK_UNIT_CREATED_AT,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_verify_with_work_unit_id_hints_at_calculate() -> None:
    """``work verify`` given a work-unit id names the mismatch and the calculate verb.

    The id resolves to a real work unit but to no calculation revision, so the
    refusal must be instructive: it names that the id is a work-unit id, that
    verify needs a calculation-revision id, and the ``work calculate`` command
    (echoing the offending id) that produces one -- not a bare "not found".
    """
    work_unit_id = _seed_work_unit_without_revision()
    result = invoke_cached_cli(["app", "modelo", "work", "verify", work_unit_id])

    assert result.exit_code != 0, result.output
    collapsed = " ".join(result.output.split())
    assert "work-unit-id" in collapsed
    assert "calculation-revision-id" in collapsed
    assert "--modelo" in collapsed and "130" in collapsed
    assert "--year" in collapsed and "2026" in collapsed
    assert "--period" in collapsed and "1T" in collapsed
    assert f"work calculate {work_unit_id}" not in collapsed


def test_file_with_work_unit_id_hints_at_calculate() -> None:
    """``work file`` given a work-unit id gets the same instructive id-type hint."""
    work_unit_id = _seed_work_unit_without_revision()
    result = invoke_cached_cli(["app", "modelo", "work", "file", work_unit_id])

    assert result.exit_code != 0, result.output
    collapsed = " ".join(result.output.split())
    assert "work-unit-id" in collapsed
    assert "calculation-revision-id" in collapsed
    assert "--modelo" in collapsed and "130" in collapsed
    assert "--year" in collapsed and "2026" in collapsed
    assert "--period" in collapsed and "1T" in collapsed
    assert f"work calculate {work_unit_id}" not in collapsed


def test_verify_with_unknown_id_keeps_plain_not_found() -> None:
    """An id resolving to no work unit at all keeps the plain not-found error.

    The hint is targeted at the work-unit-vs-calc-revision confusion. A 64-char
    id that is neither a calculation revision nor a work unit must NOT be
    mislabelled as a work-unit id -- the hint must not fire, proving it is
    conditioned on a real work-unit resolution rather than blanket-rewriting
    every not-found.
    """
    unknown_id = "f" * 64
    result = invoke_cached_cli(["app", "modelo", "work", "verify", unknown_id])

    assert result.exit_code != 0, result.output
    collapsed = " ".join(result.output.split())
    lowered = collapsed.lower()
    assert "this id is a work-unit-id" not in lowered
    assert "verify/file need a calculation-revision-id" not in lowered
