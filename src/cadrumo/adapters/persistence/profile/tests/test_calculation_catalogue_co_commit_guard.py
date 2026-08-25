"""A co-committed calculation catalogue does not overwrite a concurrent revision.

The calculation-revision catalogue is a SINGLETON row, so persisting one
revision rewrites every revision in it. The calculate path composes that write
with the work-unit pointer and the creation event in one unit of work -- it has
to, or a failure leaves an advanced pointer standing over state that never
committed -- which rules out the self-committing guarded mutation the other
catalogues use.

What remained was the read. Composing from a plain ``load()`` writes the whole
catalogue back and discards any revision another calculate run persisted in
between. That is the worst instance of this class in the tree: a lost bucket
event costs an audit entry, a lost calculation revision costs a tax
computation, and nothing downstream can tell -- the surviving revisions are all
internally valid and the missing one leaves no hole.

``to_secure_object_write`` could not even express the guard before this: it took
no ``expected_revision_id`` at all, and neither did the shared persistence
primitive underneath it, so every repository composed on that base was unable
to carry one.

Real bucket runtime, real encrypted SQL backend, real repositories. The conflict
is produced by a real second write, not a simulated one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....domain.modelos import (
    CalculationRevisionCatalogue,
    CalculationRevisionCatalogueRepositoryProtocol,
)
from .....tests.secure_sql import isolated_runtime_profile
from ...storage.errors import SecureObjectRevisionConflictError
from ..modelos_calculation import CalculationRevisionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET = "2c2c2c2c-2c2c-42c2-8c2c-2c2c2c2c2c2c"


def _repository() -> CalculationRevisionCatalogueRepository:
    return CalculationRevisionCatalogueRepository()


def test_repository_satisfies_the_revisioned_catalogue_port(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        assert isinstance(_repository(), CalculationRevisionCatalogueRepositoryProtocol)


def test_a_revisioned_read_reports_the_revision_it_was_read_at(tmp_path: Path) -> None:
    """Baseline: the read a guarded co-commit needs is available at all.

    This surface did not exist before; the catalogue could only be read
    unrevisioned, so no caller could have carried a guard even deliberately.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        catalogue, revision_id = _repository().load_revisioned()

        assert isinstance(catalogue, CalculationRevisionCatalogue)
        assert revision_id


def test_a_co_commit_carrying_a_stale_revision_is_refused(tmp_path: Path) -> None:
    """DISCRIMINATING: the write that used to overwrite a concurrent revision.

    The catalogue is read, a second writer commits, and the first writer's
    batch then carries the revision it read. Refusing is the point: it is the
    outcome that lets a caller re-compose, where the unguarded write simply
    discarded whichever revision landed first.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        repository = _repository()
        _, stale_revision_id = repository.load_revisioned()

        # A real intervening write by another holder of the same row.
        _repository().save(CalculationRevisionCatalogue())

        with pytest.raises(SecureObjectRevisionConflictError):
            repository.save_with_secure_object_writes(
                CalculationRevisionCatalogue(),
                (),
                expected_revision_id=stale_revision_id,
            )


def test_a_co_commit_carrying_the_current_revision_lands(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the guard is not refusing every write.

    Without this, a repository wired to reject unconditionally would satisfy the
    refusal above while making the calculate path unusable.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        repository = _repository()
        _, revision_id = repository.load_revisioned()

        repository.save_with_secure_object_writes(
            CalculationRevisionCatalogue(),
            (),
            expected_revision_id=revision_id,
        )

        assert repository.exists()


def test_an_omitted_revision_still_writes(tmp_path: Path) -> None:
    """The optional half, pinned so its looseness is deliberate rather than latent.

    A caller persisting a catalogue it did not derive from a read has no
    revision to assert, so the parameter stays optional. That is also the shape
    a future caller can slip back into silently, which is why it is stated here
    rather than left to be rediscovered.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        repository = _repository()
        _repository().save(CalculationRevisionCatalogue())

        repository.save_with_secure_object_writes(CalculationRevisionCatalogue(), ())

        assert repository.exists()
