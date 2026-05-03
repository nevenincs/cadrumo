"""Enforce corpus coverage for every supported / implemented modelo.

Locks two invariants:

* Every registered declaración extractor has a corresponding casilla
  catalogue committed under ``corpus/casillas/`` for every period
  the modelo's cadence requires (mandated 2023-2026 at minimum).
* Every casilla the extractor claims to read is actually defined
  in that catalogue.

These tests fail loud as soon as an extractor lands without the
matching corpus rows, which prevents silent drift between the code
and the canonical legal corpus.
"""

from __future__ import annotations

import pytest

from ...adapters.inbound.declaracion._extractors import _REGISTERED_CLASSES
from ...adapters.inbound.declaracion._generic_extractor import GenericDeclaracionExtractor
from ..modelos import UnknownModeloError, get_modelo
from ..modelos._categories import ModeloCadence
from .models import CasillaCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_corpus_fully_covers_implemented_extractors(
    corpus_catalogues: tuple[tuple[object, str, str, CasillaCatalogue], ...],
) -> None:
    """Every registered extractor must have full corpus coverage.

    1. A valid JSON must exist for every period defined by the modelo's cadence and extractor year.
    2. Every casilla expected by the extractor must be defined in the corpus.
    """
    by_key: dict[tuple[str, str], CasillaCatalogue] = {
        (modelo, period): catalogue for _path, modelo, period, catalogue in corpus_catalogues
    }

    failures: list[str] = []

    for cls in _REGISTERED_CLASSES:
        tr = cls.template_revision
        modelo_code = tr.modelo
        year = tr.año

        try:
            metadata = get_modelo(modelo_code)
        except UnknownModeloError:
            failures.append(f"Extractor {cls.__name__} has unknown modelo code {modelo_code}")
            continue

        # Determine expected periods (2023-2026 mandate)
        years = sorted({year, 2023, 2024, 2025, 2026})

        # Collect required casillas if it's a generic extractor
        required_casillas: set[str] = set()
        if issubclass(cls, GenericDeclaracionExtractor):
            decimal_ids = getattr(cls, "casilla_ids", ())
            text_ids = getattr(cls, "text_casilla_ids", ())
            required_casillas.update(decimal_ids)
            required_casillas.update(text_ids)

        for y in years:
            periods: list[str] = []
            if metadata.cadence == ModeloCadence.QUARTERLY:
                periods = [f"{y}Q{q}" for q in range(1, 5)]
            elif metadata.cadence == ModeloCadence.MONTHLY:
                periods = [f"{y}-{m:02d}" for m in range(1, 13)]
            elif metadata.cadence == ModeloCadence.ANNUAL or metadata.cadence == ModeloCadence.AD_HOC:
                periods = [str(y)]
            else:
                periods = [str(y)]

            modelo_label = f"MODELO_{modelo_code}"
            for period in periods:
                catalogue = by_key.get((modelo_label, period))
                if catalogue is None:
                    failures.append(f"Missing or invalid corpus for {modelo_label} {period} ({cls.__name__})")
                    continue

                corpus_casilla_ids = {record.casilla_id for record in catalogue.records}
                missing_casillas = required_casillas - corpus_casilla_ids
                if missing_casillas:
                    failures.append(
                        f"Corpus for {modelo_label} {period} is missing casillas "
                        f"required by {cls.__name__}: {sorted(missing_casillas)}"
                    )

    if failures:
        msg = "Corpus coverage is incomplete. The following gaps must be filled:\n" + "\n".join(
            f" - {f}" for f in failures
        )
        pytest.fail(msg)
