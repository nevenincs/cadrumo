"""The real validation-verdict cache file matches its declared grammar shape.

Unlike the LLM usage/telemetry/cache logical paths, ``validation_verdict_cache_entry``
is a real filesystem write: :func:`write_verdict` persists through
:func:`~core.atomic_write.atomic_write_best_effort_text`. This drives the real
:func:`verdict_cache_path` + :func:`write_verdict` pair and asserts the real
resulting path against the declared grammar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from .....core.config import override_settings
from .....tests import assert_path_matches_grammar
from ..verdict_cache import (
    VERDICT_OUTCOME_GREEN,
    RegistryValidationVerdict,
    verdict_cache_path,
    write_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"cache", "registry-verdict"})
"""Taxonomy-vocabulary literals this module deliberately pins.

``tmp_path / "cache" / "registry-verdict" / ...`` in the positive-control
test is the real declared grammar shape, deliberately mis-named at the
filename to prove the matcher can still fail -- both segments are the shape
under test.
"""


def test_the_real_verdict_file_matches_its_declared_shape(tmp_path: Path) -> None:
    root = tmp_path
    registry_root = tmp_path / "registry" / "aeat"
    with override_settings(cadrumo_local_storage_root=root):
        path = verdict_cache_path(registry_root)
        write_verdict(
            path,
            RegistryValidationVerdict(
                verdict_key="k" * 16,
                package_version="1.2.3",
                outcome=VERDICT_OUTCOME_GREEN,
            ),
        )

    assert path.is_file()
    assert_path_matches_grammar(key="validation_verdict_cache_entry", root=root, produced=path)


def test_a_non_conforming_verdict_filename_is_rejected_by_the_grammar(tmp_path: Path) -> None:
    """Positive control: the matcher can still fail."""
    malformed = tmp_path / "cache" / "registry-verdict" / "not-the-declared-prefix.json"
    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="validation_verdict_cache_entry", root=tmp_path, produced=malformed)
