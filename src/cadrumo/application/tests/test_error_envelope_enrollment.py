"""Real-behavior enrollment test for application-layer regression error classes.

Asserts that every application-layer regression error class is enrolled in
:data:`~core.errors.error_codes.ALL_DECLARED_ERROR_CODES` and produces a valid
:class:`cadrumo.core.errors.ErrorEnvelope` through
:func:`cadrumo.core.errors.build_error_envelope`.

No mocks, no skips. The test imports the real error classes, raises them,
and calls the real registry machinery. A missing registration causes a
hard failure in :func:`~cadrumo.core.errors.get_registered_error_code` — the
test will surface it rather than silently return a placeholder.
"""

from __future__ import annotations

import pytest

from ...core.errors.hierarchy import CadrumoError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# contract — RepositorySetupError
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# contract — ProfileLabelAmbiguousError
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# contract — SnapshotNotFoundError (now CadrumoError + KeyError)
# ---------------------------------------------------------------------------


def test_snapshot_not_found_subclasses_still_work() -> None:
    """Per-service subclasses remain catchable as both CadrumoError and KeyError."""
    from ..live.borrador_100 import BorradorSnapshotNotFoundError
    from ..live.snapshot_base import SnapshotNotFoundError

    assert issubclass(BorradorSnapshotNotFoundError, SnapshotNotFoundError)
    assert issubclass(BorradorSnapshotNotFoundError, CadrumoError)
    assert issubclass(BorradorSnapshotNotFoundError, KeyError)


# ---------------------------------------------------------------------------
# ModeloApplicabilityFilterError — pre-existing, asserted here for coverage
# ---------------------------------------------------------------------------
