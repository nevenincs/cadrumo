"""Planted Modelo fixtures the casilla lineage seeder tests build their scenarios from."""

from __future__ import annotations

from datetime import date

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..analysis.casilla_lineage_seed_design import DesignOracle
from ..analysis.casilla_lineage_seed_types import Ruling
from ..compiler.loader import load_shared_catalogues


def planted_casilla(**updates: object) -> CasillaDefinition:
    payload: dict[str, object] = {
        "id": "01",
        "number": "01",
        "localization_keys": ("modelo.schema.test.casilla.01.label",),
        "section": ("liquidacion",),
        "semantic_role": "base_imponible",
        "legal_refs": ("ley-35-2006:art-25",),
        "source_refs": ("aeat-dr-123-2024-v20",),
    }
    payload.update(updates)
    return CasillaDefinition.model_validate(payload)


PLANTED_MODELO = "999"


def design_oracle() -> DesignOracle:
    return DesignOracle(load_shared_catalogues(bundled_path("registry", "aeat")).sources)


_NO_PREDECESSOR = {
    "none": {
        "reason": "a parallel scheme variant taking effect alongside its siblings",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    },
}


def planted_revision(
    revision_id: str,
    valid_from: date,
    valid_to: date | None,
    years: tuple[int, ...],
    casillas: tuple[CasillaDefinition, ...],
    *,
    no_predecessor: bool = False,
) -> ModeloRevision:
    payload: dict[str, object] = {
        "id": revision_id,
        "localization_key": f"modelo.schema.test.revision.{revision_id}.label",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "period_selector": PeriodSelector(years=years, periods=("0A",)),
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
        "casillas": casillas,
    }
    if no_predecessor:
        payload["predecessor"] = _NO_PREDECESSOR
    return ModeloRevision.model_validate(payload)


def planted_modelo(*revisions: ModeloRevision) -> ModeloDefinition:
    return ModeloDefinition.model_validate(
        {
            "id": PLANTED_MODELO,
            "title_localization_key": "modelo.schema.test.modelo.title",
            "official_name_localization_key": "modelo.schema.test.modelo.official_name",
            "tax_domain": "irpf",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {revision.id: revision for revision in revisions},
        },
    )


HELD_STEM = "planted-held"


HELD_ROW = f"{HELD_STEM}-02"


HELD_REASON = "a positional convention the record design cannot settle"


NEW_EVIDENCE = "disenos_registro/modelo_999/files/2024.txt:12 box [02] first printed in the successor design"


def held_modelo(*, origin: CasillaLineageOrigin | None) -> ModeloDefinition:
    """Two editions where the successor adds one row matching a held stem, with or without an origin."""
    updates: dict[str, object] = {"id": HELD_ROW, "number": "02", "semantic_role": "importe_planted"}
    if origin is not None:
        updates["continuidad_origin"] = origin.value
        updates["continuidad_evidence"] = NEW_EVIDENCE
    return planted_modelo(
        planted_revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (planted_casilla(),)),
        planted_revision(
            "2024", date(2024, 1, 1), date(2024, 12, 31), (2024,), (planted_casilla(), planted_casilla(**updates))
        ),
    )


def held_pair_ruling(predecessor: str, successor: str) -> Ruling:
    """The same hold, named as one adjudicated pair rather than by stem."""
    return Ruling(
        predecessor=predecessor,
        successor=successor,
        refuse_bare=False,
        rationale="planted for this gate",
        grounded=(),
        new_on_form=frozenset(),
        new_on_form_stems=frozenset(),
        not_on_form=frozenset(),
        held=(("01", HELD_ROW),),
        held_stems=frozenset(),
        held_reason=HELD_REASON,
        withheld=(),
        withheld_reason="",
        merged=(),
        merged_reason="",
        discontinued=frozenset(),
    )


ABSENT_ROW = "planted-absent"


ABSENT_EVIDENCE = "disenos_registro/modelo_999/files/2023.txt:7 box [02] printed; the 2023 edition declares no row"


def absence_modelo(*, origin: CasillaLineageOrigin | None) -> ModeloDefinition:
    """Two editions where the successor adds a row with no predecessor and no printed box."""
    updates: dict[str, object] = {
        "id": ABSENT_ROW,
        # A byte range is not a printed box, so no record design can classify the absence.
        "number": "0001-0010",
        "semantic_role": "importe_planted",
    }
    if origin is not None:
        updates["continuidad_origin"] = origin.value
        updates["continuidad_evidence"] = ABSENT_EVIDENCE
    return planted_modelo(
        planted_revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (planted_casilla(),)),
        planted_revision(
            "2024", date(2024, 1, 1), date(2024, 12, 31), (2024,), (planted_casilla(), planted_casilla(**updates))
        ),
    )
