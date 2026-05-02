"""Enforce corpus coverage against all supported and implemented modelos.

Ensures that every registered extractor has a corresponding casilla catalogue
in the corpus for all defined periods, and that all casillas extracted by
the code are actually defined in the corpus JSON.
"""

from __future__ import annotations

import pytest

from ...adapters.inbound.declaracion._extractors import _REGISTERED_CLASSES
from ...adapters.inbound.declaracion._generic_extractor import GenericDeclaracionExtractor
from ..modelos import UnknownModeloError, get_modelo
from ..modelos._categories import ModeloCadence
from . import CasillaParseError, load_casillas

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_corpus_fully_covers_implemented_extractors() -> None:
    """Every registered extractor must have full corpus coverage.

    1. A valid JSON must exist for every period defined by the modelo's cadence and extractor year.
    2. Every casilla expected by the extractor must be defined in the corpus.
    """
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
            elif metadata.cadence == ModeloCadence.ANNUAL:
                periods = [str(y)]
            elif metadata.cadence == ModeloCadence.AD_HOC:
                periods = [str(y)]
            else:
                periods = [str(y)]

            for period in periods:
                try:
                    catalogue = load_casillas(f"MODELO_{modelo_code}", period)
                except CasillaParseError as exc:
                    msg = f"Missing or invalid corpus for MODELO_{modelo_code} {period} ({cls.__name__}): {exc}"
                    failures.append(msg)
                    continue

                corpus_casilla_ids = {record.casilla_id for record in catalogue.records}
                missing_casillas = required_casillas - corpus_casilla_ids
                if missing_casillas:
                    msg = (
                        f"Corpus for MODELO_{modelo_code} {period} is missing casillas "
                        f"required by {cls.__name__}: {sorted(missing_casillas)}"
                    )
                    failures.append(msg)

    if failures:
        msg = "Corpus coverage is incomplete. The following gaps must be filled:\n" + "\n".join(
            f" - {f}" for f in failures
        )
        pytest.fail(msg)
