"""Modelo 210's inception statement names the earliest edition the registry authors.

The unauthored arm records that earlier filing years existed in law and are not
authored; its ``earliest_authored`` is a claim about the corpus, so it must agree
with the editions the modelo actually declares rather than lag behind them.
"""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.modelo_inception import UnauthoredBefore

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_210_inception_names_its_earliest_authored_edition() -> None:
    declared = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "210"))
    assert isinstance(declared.inception, UnauthoredBefore)
    earliest = min(revision.valid_from.year for revision in declared.revisions.values())
    assert declared.inception.earliest_authored == earliest
