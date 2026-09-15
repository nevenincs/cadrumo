"""The real validation-verdict cache file matches its declared filename shape.

``write_verdict`` persists a real file through
:func:`~cadrumo.core.atomic_write.atomic_write_best_effort_text`. This drives the
real :func:`verdict_cache_path` + :func:`write_verdict` pair and asserts the real
resulting path against the shape the verdict store declares: one file directly
in the store, named ``cadrumo_validation_verdict_<16 lowercase hex>.json``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from cadrumo.tests.env_scope import scoped_env_var

from ..compiler.verdict_cache import (
    VERDICT_OUTCOME_GREEN,
    RegistryValidationVerdict,
    verdict_cache_path,
    write_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CACHE_DIR_ENV: Final = "CADRUMO_REGISTRY_VERDICT_CACHE_DIR"
_VERDICT_FILENAME: Final = re.compile(r"cadrumo_validation_verdict_[0-9a-f]{16}\.json")


def _assert_verdict_shape(store: Path, produced: Path) -> None:
    assert produced.parent == store, f"{produced} is not directly inside the verdict store {store}"
    assert _VERDICT_FILENAME.fullmatch(produced.name), f"{produced.name} does not match the verdict filename shape"


def test_the_real_verdict_file_matches_its_declared_shape(tmp_path: Path) -> None:
    store = tmp_path / "verdicts"
    registry_root = tmp_path / "registry" / "aeat"
    with scoped_env_var(_CACHE_DIR_ENV, str(store)):
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
    _assert_verdict_shape(store, path)


def test_a_non_conforming_verdict_filename_is_rejected_by_the_shape(tmp_path: Path) -> None:
    """Positive control: the shape check can still fail."""
    store = tmp_path / "verdicts"
    with pytest.raises(AssertionError):
        _assert_verdict_shape(store, store / "not-the-declared-prefix.json")
    with pytest.raises(AssertionError):
        _assert_verdict_shape(store, tmp_path / "elsewhere" / "cadrumo_validation_verdict_0123456789abcdef.json")
