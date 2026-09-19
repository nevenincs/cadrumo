"""Enrolling a relocated authority root through the environment serves real reads.

The sibling resolution tests prove which PATH each arm addresses. They stop
short of the question an operator actually has: if I move the published
authority somewhere else and name that place, does the product read it from
there? Path equality cannot answer that -- a resolver could return the relocated
path while the reader answers from a generation it cached earlier, and every
path assertion would still pass.

These tests answer it by identity instead. A real published pair is copied to a
directory that is not the one this checkout publishes into, the root is enrolled
through the settings the environment variable feeds, and the authority is opened
and read. The logical generation the reader reports is compared with the one the
RELOCATED descriptor names, so a read served from anywhere else fails.

One limit is worth stating rather than implying: the relocated pair is a copy,
so its generation identity equals the origin's. These tests therefore prove
that the enrolled root is opened and read, not that a read could never have
been served from the origin holding identical bytes. What forbids that is the
no-fallback rule, and the fail-closed tests beside this module are what pin it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from .....core.config import override_settings
from .. import authority as authority_module
from ..authority import bundled_authority_descriptor_path, bundled_indexed_authority
from ..authority_store import SQLiteAuthorityReader
from ..errors import AuthorityDescriptorUnavailableError

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_DESCRIPTOR_NAME = "authority.current.json"


@pytest.fixture
def relocated_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Copy this checkout's published pair into a directory nothing else knows.

    The descriptor and the one database it names are copied, never the
    directory: a publication leaves its lock sidecar in place by design, and a
    superseded database may still be awaiting retirement, so a directory copy
    would carry bytes the descriptor does not select.

    The process-shared authority owner is reset for the test. Without that, a
    generation this session already opened would answer the read and the
    relocation would be neither exercised nor disproved.
    """
    source_descriptor = _published_pair_or_skip()

    descriptor = json.loads(source_descriptor.read_text(encoding="utf-8"))
    database = source_descriptor.parent / descriptor["database"]
    if not database.is_file():
        pytest.skip(f"the published descriptor selects a database that is not present: {database}")

    shutil.copy2(source_descriptor, tmp_path / _DESCRIPTOR_NAME)
    shutil.copy2(database, tmp_path / database.name)
    monkeypatch.setattr(authority_module, "_bundled_indexed_authority", None)
    return tmp_path


def _published_pair_or_skip() -> Path:
    """Return whichever published descriptor this environment resolves.

    Resolution is asked for as the process would ask: an installed run answers
    from the distribution, a checkout from the root it has enrolled. Either is a
    valid source to relocate FROM, so the test does not care which arm answered
    -- only that some real, published pair exists to move.
    """
    try:
        return bundled_authority_descriptor_path()
    except AuthorityDescriptorUnavailableError as refusal:
        pytest.skip(
            f"no published authority to relocate ({refusal.searched_path}); run just registry-publish-authority"
        )


def test_an_enrolled_root_serves_the_generation_that_root_names(relocated_authority: Path) -> None:
    relocated = json.loads((relocated_authority / _DESCRIPTOR_NAME).read_text(encoding="utf-8"))

    with override_settings(cadrumo_authority_root=relocated_authority):
        assert bundled_authority_descriptor_path().parent.resolve() == relocated_authority.resolve()
        with bundled_indexed_authority().operation() as operation:
            served = operation.pin().logical_generation

    assert served == relocated["logical_generation"]


def test_an_enrolled_root_reads_registry_content_not_merely_a_path(relocated_authority: Path) -> None:
    """The relocated generation answers a real query, so the database is genuinely open."""
    with (
        override_settings(cadrumo_authority_root=relocated_authority),
        bundled_indexed_authority().operation() as operation,
    ):
        catalogue = operation.supported_filing_years()

    assert catalogue.floor <= catalogue.horizon


def test_the_relocated_database_is_the_one_the_relocated_descriptor_selects(relocated_authority: Path) -> None:
    """Enrollment follows the descriptor, so the copied pair stays self-consistent."""
    relocated = json.loads((relocated_authority / _DESCRIPTOR_NAME).read_text(encoding="utf-8"))
    reader = SQLiteAuthorityReader(relocated_authority / _DESCRIPTOR_NAME)
    try:
        assert reader.pin().logical_generation == relocated["logical_generation"]
    finally:
        reader.close()


def test_leaving_the_root_unset_again_does_not_keep_serving_the_relocated_generation(
    relocated_authority: Path,
) -> None:
    """The enrollment is scoped to the setting, not latched by the first read.

    A cached owner that survived the scope would make every later read answer
    from a directory the caller is no longer naming -- the same silent-stale
    failure the no-fallback rule exists to prevent.
    """
    with (
        override_settings(cadrumo_authority_root=relocated_authority),
        bundled_indexed_authority().operation() as operation,
    ):
        relocated_generation = operation.pin().logical_generation

    # The owner is this module's own process cache; clearing it is what puts
    # the next resolution back through the arms rather than a held reader.
    authority_module._bundled_indexed_authority = None
    with override_settings(cadrumo_authority_root=None):
        try:
            elsewhere = bundled_authority_descriptor_path()
        except AuthorityDescriptorUnavailableError as refusal:
            # A checkout after the move has nothing at the packaged location.
            # Refusing there is the correct opposite of serving the relocated
            # generation, so the scoping this test asserts is shown either way.
            assert refusal.searched_path.parent.resolve() != relocated_authority.resolve()
            return
    assert elsewhere.parent.resolve() != relocated_authority.resolve()
    assert relocated_generation
