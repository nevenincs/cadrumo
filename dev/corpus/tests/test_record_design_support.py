"""Integrity gate for the supported AEAT record-design corpus."""

from __future__ import annotations

import json

import pytest

from ..sync_aeat_record_design_corpus import _HISTORICAL_EXCLUSIONS_PATH, _REQUIRED, check

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_supported_record_design_corpus_is_complete_and_current() -> None:
    """The captured official matrix and every manifested source rehash cleanly."""
    check()


def test_modelos_308_and_309_historical_designs_are_required_not_excluded() -> None:
    """The six AEAT historical IVA designs stay in the canonical sync inventory.

    The corpus checker proves their persisted bytes and exclusion partition.  This
    explicit cohort prevents a future inventory edit from silently returning the
    claimed-year evidence to the historical exclusion ledger.
    """
    expected = {
        "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/ant_300_399/archivos/dr308.xls": (
            "308",
            "308 - Orden EHA/1033/2011 (Ejercicios 2009 a 2011- julio)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr308_2011.pdf"
        ): (
            "308",
            "308 - Orden EHA/1033/2011 (Ejercicios 2011 - julio - a 2015)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr308e16v12.xls"
        ): (
            "308",
            "308 - Orden EHA/1033/2011 (Ejercicios 2016 hasta 2018)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr309_2004.pdf"
        ): (
            "309",
            "309 - Orden EHA/3212/2004 (Ejercicios hasta 2015)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "ant_300_399/archivos/dr309e16v10.xls"
        ): (
            "309",
            "309 - Orden EHA/3212/2004 (Ejercicios 2016 y 2017)",
        ),
        (
            "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
            "DR_300_399/archivos_17/dr309e17v13.xls"
        ): (
            "309",
            "309 - Orden EHA/3212/2004 (Ejercicios 2018 y posteriores)",
        ),
    }
    required = {artifact.url: (artifact.modelo, artifact.title) for artifact in _REQUIRED}
    exclusions = set(json.loads(_HISTORICAL_EXCLUSIONS_PATH.read_text(encoding="utf-8"))["urls"])

    assert {url: required[url] for url in expected} == expected
    assert exclusions.isdisjoint(expected)
