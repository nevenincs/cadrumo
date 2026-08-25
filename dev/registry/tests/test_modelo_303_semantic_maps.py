"""Real-source closure proofs for every reviewed Modelo 303 semantic-map corpus.

ONE suite covers every AEAT design epoch.  It replaces three near-identical
per-epoch modules whose only true differences were a handful of measured
totals and the amendment-evidence block, so each new AEAT re-layout cost
another module plus another census.  The epochs are DISCOVERED from the
authored mapping tree and resolved to their registry revision through the
canonical temporal resolver, never enumerated in a list here: a list is the
thing that goes stale silently when an epoch is added.

ANTI-VACUITY.  A discovery-driven suite that discovers nothing is
indistinguishable from a suite that finds nothing wrong, so an empty epoch set,
an epoch with no render profile, an epoch with no reviewed census expectation,
and an epoch whose design declares no integer slot of a probed width are all
FAILURES rather than silent skips.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final, Literal

import pytest

from cadrumo.core import DirectoryEntryKind, scan_directory
from cadrumo.domain.calculations.registry import (
    ExportComputedKey,
    ExportEncoding,
    RegistryRevisionInspection,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry import load_registry_tree

from ..analysis.m303_semantic_census import (
    M303_SEMANTIC_CENSUS_EXPECTATIONS,
    M303_VARIABLE_ENVELOPE_ANCHOR_COUNT,
    census_m303_semantic_map,
    pair_epoch_anchors,
    resolve_semantic_home,
)
from ..pipeline._export_tree import (
    _DECIMAL_CONTENT_RE,
    _INTEGER_CONTENT_RE,
    _OFFICIAL_LITERAL_RE,
    _QUOTED_NUMERIC_BOOLEAN_ENUMERATION_RE,
    _QUOTED_NUMERIC_ENUMERATION_RE,
    _TRAILING_NOTE_REFERENCE_RE,
    ExportTreeTransportProfile,
    _render_records,
    _split_official_note_references,
    render_complete_export_tree,
)
from ..pipeline._provenance_manifest import semantic_map_digest
from ..pipeline._record_design_ir import RecordDesignIntermediate, load_record_design_intermediate
from ..pipeline._render_profile import (
    RenderProfile,
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    load_and_validate_render_profile,
    render_profile_digest,
)
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import JoinedRecordDesign, join_record_design_semantics
from ..pipeline._semantic_map_loader import load_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO: Final[str] = "303"
_MAPPING_ROOT: Final[Path] = Path("dev/registry/mappings/modelo_303")
_PROFILE_ROOT: Final[Path] = Path("dev/registry/render_profiles/modelo_303")
_SOURCE_ROOT: Final[Path] = Path("src/cadrumo/_data")
_REGISTRY_ROOT: Final[Path] = _SOURCE_ROOT / "registry" / "aeat"
#: The body records every bundled 303 design lays out, in official order.
_RECORD_IDS: Final[tuple[str, ...]] = (
    "m303-declaration",
    "m303-regimen-simplificado",
    "m303-resultados",
    "m303-exonerado-390",
    "m303-prorrata-deducciones",
    "m303-domiciliacion",
)
#: The DP30300 prefix byte length, fixed by the AEAT auxiliary-envelope contract.
_ENVELOPE_PREFIX_LENGTH: Final[int] = 328
_SINGLETON_RULE_COUNT: Final[int] = 3
_INTEGER_CONTENT: Final[re.Pattern[str]] = re.compile(
    r"^(?P<whole>\d+)\s*enteros?(?:[.,\s]+Nota\s+\d+)*\.?$",
    re.IGNORECASE,
)
#: Every record-design source id belongs to exactly one 303 revision and is
#: prefixed this way; the sweep finds designs by that declaration, not by a list.
_DESIGN_SOURCE_PREFIX: Final[str] = "aeat-dr-303"
_NOTE_TOKEN: Final[re.Pattern[str]] = re.compile(r"\bNota\b", re.IGNORECASE)
_NOTE_REFERENCE: Final[re.Pattern[str]] = re.compile(r"\bNota\s+(\d+)", re.IGNORECASE)
#: A note reference wrapped in parentheses is part of the value description,
#: not a trailing annotation.  Peeling one would silently truncate the
#: enumeration it belongs to, so it is called out as its own shape.
_PARENTHESISED_NOTE: Final[re.Pattern[str]] = re.compile(r"\(\s*Nota\s+\d+\s*\)", re.IGNORECASE)
#: The AEAT type codes that route a field through the numeric derivation, where
#: the peeled stem must be readable by one of the declared value grammars.
_NUMERIC_AEAT_TYPES: Final[frozenset[str]] = frozenset({"n", "num"})

_AnchorAttribute = Literal["casilla_id", "computed_key", "producer_key", "kind", "literal"]

#: Facts every reviewed epoch asserts about the same anchors.  The page and
#: activity markers are structural, so an epoch that moved one would be
#: reporting a re-layout rather than a re-vocabulary.
_SHARED_ANCHOR_FACTS: Final[tuple[tuple[str, int, _AnchorAttribute, object], ...]] = (
    ("DP30303", "20", "casilla_id", "iva.compensacion-pendiente-periodos-anteriores"),
    ("DP30303", "22", "casilla_id", "iva.compensacion-pendiente-periodos-posteriores"),
    ("DP30301", "5", "literal", ""),
    ("DP30301", "5", "computed_key", None),
    ("DP30304", "5", "literal", ""),
    ("DP30304", "5", "computed_key", None),
    ("DP30302", "5", "computed_key", ExportComputedKey.COMPLEMENTARIA_PAGE_MARKER),
    ("DP30305", "5", "computed_key", ExportComputedKey.COMPLEMENTARIA_PAGE_MARKER),
)


@dataclass(frozen=True, slots=True)
class _EpochSurfaceExpectation:
    """The reviewed surface facts one design epoch states on its own."""

    #: The DP30303 amendment-evidence block.  The 2024-late orden replaced a
    #: single complementaria marker with an itemised rectificativa block, so
    #: this is genuinely per-epoch vocabulary rather than a re-layout.
    amendment_evidence: tuple[tuple[str, str, _AnchorAttribute, object], ...]
    #: The closed wire domain the design states for the DP30301 general-rate
    #: slot.  The 2024-late design replaced its quoted enumeration with note
    #: references, so that slot states no closed domain and its value is
    #: carried by the casilla's dated rate parameter instead.
    general_rate_allowed_values: tuple[str, ...] | None
    #: The DP30303 ordinal carrying the no-activity marker. It sat at 28 from
    #: 2023 through 2025 and was a shared fact until the 2026 design inserted
    #: box [112] ahead of it, which is a re-layout rather than a re-vocabulary
    #: and so is stated per epoch instead of assumed constant.
    no_activity_marker_ordinal: str
    #: The epoch this design re-lays out, or ``None`` for the earliest reviewed
    #: design.  Exactly one epoch may be the root, and every other predecessor
    #: must itself be a discovered epoch, so an added epoch cannot opt out of
    #: the review below by simply not naming what it came from.
    predecessor: str | None
    #: Every semantic home this epoch INTRODUCES over its predecessor, and every
    #: home it RETIRES, each with the anchor it is reviewed at.
    #:
    #: This is the hand review the epoch rows require, held as data.  A re-layout
    #: shifts most homes by an offset, which the census totals already cover;
    #: what they cannot see is a home moving to a DIFFERENT canonical authority,
    #: because swapping two anchors of the same class leaves every total
    #: identical.  Homes are compared by their fully-qualified identity and NOT
    #: by ordinal, so a pure offset shift is correctly silent here while a
    #: slot-for-slot or cohort-for-cohort swap is not.
    introduced_homes: tuple[tuple[str, str, str], ...]
    retired_homes: tuple[tuple[str, str, str], ...]


#: The simplified-regime facts the 2024-late orden adds, as
#: ``(anchor ordinal, cohort, fact, slot)``.  Held as a table because the block
#: is one reviewed regulatory change -- the DANA relief of RDL 6/2024 and
#: RDL 7/2024, alongside the Lorca reduction amounts the same re-layout gave
#: their own slots -- rather than twelve unrelated anchors.
_M303_2024_LATE_SIMPLIFIED_ADDITIONS: Final[tuple[tuple[int, str, str, int], ...]] = (
    (95, "no_agricola", "dana_elegible", 1),
    (124, "no_agricola", "dana_elegible", 2),
    (154, "agricola", "dana_elegible", 1),
    (155, "agricola", "reduccion_dana", 1),
    (156, "agricola", "dana_elegible", 2),
    (157, "agricola", "reduccion_dana", 2),
    (158, "no_agricola", "reduccion_lorca", 1),
    (159, "no_agricola", "reduccion_dana", 1),
    (160, "no_agricola", "reduccion_lorca", 2),
    (161, "no_agricola", "reduccion_dana", 2),
)


#: The Superficie de horno module gains a per-activity multiplicity in 2025:
#: each activity's single day count becomes four (Superficie, Días) pairs, as
#: ``(anchor ordinal, cohort, fact, slot, sub-index)``. Both facts were already
#: declared repeating in the core vocabulary, so this is a multiplicity change
#: rather than new vocabulary.
_M303_2025_SUPERFICIE_ADDITIONS: Final[tuple[tuple[int, str, str, int, int], ...]] = tuple(
    (
        149 + (slot - 1) * 8 + (sub_index - 1) * 2 + offset,
        "no_agricola",
        fact,
        slot,
        sub_index,
    )
    for slot in (1, 2)
    for sub_index in (1, 2, 3, 4)
    for offset, fact in enumerate(("superficie_horno_cuarto_trimestre", "superficie_horno_dias_cuarto_trimestre"))
)

#: The DP30303 amendment-evidence block the 2024-late orden introduced. Every
#: later epoch re-asserts it explicitly: the rows require this region to be
#: hand-reviewed per epoch rather than inherited by silence, and naming the
#: shared tuple keeps that assertion honest without re-transcribing it.
_M303_RECTIFICATIVA_EVIDENCE: Final[tuple[tuple[str, int, _AnchorAttribute, object], ...]] = (
    ("DP30303", "29", "producer_key", "amendment_evidence.is_rectificativa"),
    ("DP30303", "30", "producer_key", "amendment_evidence.original_aeat_receipt"),
    ("DP30303", "31", "producer_key", "prior_domiciliation.action"),
    ("DP30303", "32", "casilla_id", "108"),
    ("DP30303", "33", "casilla_id", "111"),
    ("DP30303", "34", "kind", "filler"),
    ("DP30303", "35", "producer_key", "amendment_evidence.m303_motive.rectificaciones"),
    ("DP30303", "36", "producer_key", "amendment_evidence.m303_motive.discrepancia_criterio_administrativo"),
    ("DP30303", "37", "kind", "filler"),
)


def _simplified_fact_home(cohort: str, fact: str, slot: int, sub_index: int | None = None) -> str:
    """Return one simplified-regime fact's fully-qualified home identity.

    The argument order mirrors how the epoch tables read; the rendered order is
    the projection payload's own sorted-key order, so it matches what
    :func:`resolve_semantic_home` measures from a loaded map.
    """
    payload = f"cohort={cohort},fact={fact},slot={slot}"
    if sub_index is not None:
        payload += f",sub_index={sub_index}"
    return f"projection:m303_regimen_simplificado_fact({payload})"


_EPOCH_SURFACES: Final[Mapping[str, _EpochSurfaceExpectation]] = {
    "2022": _EpochSurfaceExpectation(
        # The 2022 semantic map was authored without a surface expectation, so
        # every epoch-scoped case refused with "no reviewed surface expectation".
        # 2022 precedes 2023, so it -- not 2023 -- is the root of the chain.
        #
        # Its DP30303 markers sit one slot apart from where 2023 puts them: the
        # complementaria marker at ordinal 27 and the no-activity marker at 29,
        # against 29 and 28 in 2023. That is a re-layout, which is exactly the
        # per-epoch fact this row exists to state rather than assume.
        #
        # `general_rate_allowed_values` is None because the 2022 DP30301
        # general-rate slot states no closed enumeration, measured through the
        # same rendered-field accessor the case below reads.
        no_activity_marker_ordinal="29",
        amendment_evidence=(("DP30303", "27", "computed_key", ExportComputedKey.M303_COMPLEMENTARIA_MARKER),),
        general_rate_allowed_values=None,
        predecessor=None,
        introduced_homes=(),
        retired_homes=(),
    ),
    "2023": _EpochSurfaceExpectation(
        no_activity_marker_ordinal="28",
        amendment_evidence=(("DP30303", "29", "computed_key", ExportComputedKey.M303_COMPLEMENTARIA_MARKER),),
        general_rate_allowed_values=("0", "50", "62"),
        # 2023 re-lays out 2022. Two changes account for the whole diff, and both
        # are AEAT's, not the registry's:
        #
        #  - the RATE-BOX relayout: the fixed printed "Tipo %" boxes are retired
        #    (02, 05 and 08 of the three general-regime devengado triplets, plus
        #    20 and 23 of the recargo de equivalencia rows) and a variable-rate
        #    base/tipo/cuota block arrives as 150 and 152-155, because a rate
        #    that moves mid-period cannot be printed on the form. Box 109,
        #    "Devoluciones acordadas por la AEAT", arrives with them.
        #  - the REGIMEN SIMPLIFICADO actividad modules arrive on DP30302: 62 of
        #    the 82 introduced homes are simplified-regime projections, which is
        #    also why 2022 declares no pure-integer DP30302 slot at all.
        predecessor="2022",
        introduced_homes=(
            ("DP30301", "25", "casilla:150"),
            ("DP30301", "26", "literal:'00000'@DP30301"),
            ("DP30301", "27", "casilla:152"),
            ("DP30301", "29", "literal:'00400'@DP30301"),
            ("DP30301", "31", "casilla:153"),
            ("DP30301", "32", "casilla:154"),
            ("DP30301", "33", "casilla:155"),
            ("DP30301", "38", "literal:'02100'@DP30301"),
            ("DP30301", "46", "casilla:156"),
            ("DP30301", "47", "literal:'00175'@DP30301"),
            ("DP30301", "48", "casilla:158"),
            ("DP30301", "53", "literal:'00140'@DP30301"),
            ("DP30301", "56", "literal:'00520'@DP30301"),
            (
                "DP30302",
                "90",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=actividad_temporada_dias_ejercicio_anio_anterior,slot=1)",
            ),
            (
                "DP30302",
                "91",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=dias_ejercicio_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "92",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=empleados_inicio_ejercicio,slot=1)",
            ),
            (
                "DP30302",
                "93",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=actividad_temporada_dias_ejercicio_cuarto_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "94",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=max_asalariados_simultaneos,slot=1)",
            ),
            (
                "DP30302",
                "95",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=lorca_elegible,slot=1)",
            ),
            (
                "DP30302",
                "96",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=cuotas_soportadas_cuarto_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "97",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=compensaciones_reagp_cuarto_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "98",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_mayores_19,slot=1)",
            ),
            (
                "DP30302",
                "99",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_menores_19_o_formacion,slot=1)",
            ),
            (
                "DP30302",
                "100",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_discapacidad_33,slot=1)",
            ),
            (
                "DP30302",
                "101",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_convenio_colectivo,slot=1)",
            ),
            (
                "DP30302",
                "102",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_horas_titular,slot=1)",
            ),
            (
                "DP30302",
                "103",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_titular_discapacidad_33,slot=1)",
            ),
            (
                "DP30302",
                "104",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_horas_conyuge,slot=1)",
            ),
            (
                "DP30302",
                "105",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_horas_hijos_menores_18,slot=1)",
            ),
            (
                "DP30302",
                "106",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=1,sub_index=1)",
            ),
            (
                "DP30302",
                "107",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=1,sub_index=1)",
            ),
            (
                "DP30302",
                "108",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=1,sub_index=1)",
            ),
            (
                "DP30302",
                "109",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=1,sub_index=2)",
            ),
            (
                "DP30302",
                "110",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=1,sub_index=2)",
            ),
            (
                "DP30302",
                "111",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=1,sub_index=2)",
            ),
            (
                "DP30302",
                "112",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=1,sub_index=3)",
            ),
            (
                "DP30302",
                "113",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=1,sub_index=3)",
            ),
            (
                "DP30302",
                "114",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=1,sub_index=3)",
            ),
            (
                "DP30302",
                "115",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=1,sub_index=4)",
            ),
            (
                "DP30302",
                "116",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=1,sub_index=4)",
            ),
            (
                "DP30302",
                "117",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=1,sub_index=4)",
            ),
            (
                "DP30302",
                "118",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=actividad_temporada_dias_ejercicio_anio_anterior,slot=2)",
            ),
            (
                "DP30302",
                "119",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=dias_ejercicio_trimestre,slot=2)",
            ),
            (
                "DP30302",
                "120",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=empleados_inicio_ejercicio_actual,slot=2)",
            ),
            (
                "DP30302",
                "121",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=actividad_temporada_dias_ejercicio_cuarto_trimestre,slot=2)",
            ),
            (
                "DP30302",
                "122",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=max_asalariados_simultaneos,slot=2)",
            ),
            (
                "DP30302",
                "123",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=lorca_elegible,slot=2)",
            ),
            (
                "DP30302",
                "124",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=cuotas_soportadas_cuarto_trimestre,slot=2)",
            ),
            (
                "DP30302",
                "125",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=compensaciones_reagp_cuarto_trimestre,slot=2)",
            ),
            (
                "DP30302",
                "126",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_mayores_19,slot=2)",
            ),
            (
                "DP30302",
                "127",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_menores_19_o_formacion,slot=2)",
            ),
            (
                "DP30302",
                "128",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_discapacidad_33,slot=2)",
            ),
            (
                "DP30302",
                "129",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_asalariado_horas_convenio_colectivo,slot=2)",
            ),
            (
                "DP30302",
                "130",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_horas_titular,slot=2)",
            ),
            (
                "DP30302",
                "131",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_titular_discapacidad_33,slot=2)",
            ),
            (
                "DP30302",
                "132",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_horas_conyuge,slot=2)",
            ),
            (
                "DP30302",
                "133",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=personal_no_asalariado_horas_hijos_menores_18,slot=2)",
            ),
            (
                "DP30302",
                "134",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=2,sub_index=1)",
            ),
            (
                "DP30302",
                "135",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=2,sub_index=1)",
            ),
            (
                "DP30302",
                "136",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=2,sub_index=1)",
            ),
            (
                "DP30302",
                "137",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=2,sub_index=2)",
            ),
            (
                "DP30302",
                "138",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=2,sub_index=2)",
            ),
            (
                "DP30302",
                "139",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=2,sub_index=2)",
            ),
            (
                "DP30302",
                "140",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=2,sub_index=3)",
            ),
            (
                "DP30302",
                "141",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=2,sub_index=3)",
            ),
            (
                "DP30302",
                "142",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=2,sub_index=3)",
            ),
            (
                "DP30302",
                "143",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_capacidad,slot=2,sub_index=4)",
            ),
            (
                "DP30302",
                "144",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_numero,slot=2,sub_index=4)",
            ),
            (
                "DP30302",
                "145",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=mesas_dias_cuarto_trimestre,slot=2,sub_index=4)",
            ),
            (
                "DP30302",
                "146",
                "projection:m303_regimen_simplificado_fact(cohort=agricola,fact=cuotas_soportadas_cuarto_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "147",
                "projection:m303_regimen_simplificado_fact(cohort=agricola,fact=compensaciones_reagp_cuarto_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "148",
                "projection:m303_regimen_simplificado_fact(cohort=agricola,fact=cuotas_soportadas_cuarto_trimestre,slot=2)",
            ),
            (
                "DP30302",
                "149",
                "projection:m303_regimen_simplificado_fact(cohort=agricola,fact=compensaciones_reagp_cuarto_trimestre,slot=2)",
            ),
            (
                "DP30302",
                "150",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=superficie_horno_dias_cuarto_trimestre,slot=1)",
            ),
            (
                "DP30302",
                "151",
                "projection:m303_regimen_simplificado_fact(cohort=no_agricola,fact=superficie_horno_dias_cuarto_trimestre,slot=2)",
            ),
            ("DP30303", "26", "casilla:109"),
            ("DP303DID", "1", "literal:'<T'@DP303DID"),
            ("DP303DID", "2", "literal:'303'@DP303DID"),
            ("DP303DID", "3", "literal:'DID00'@DP303DID"),
            ("DP303DID", "4", "literal:'>'@DP303DID"),
            ("DP303DID", "12", "filler@DP303DID"),
            ("DP303DID", "13", "literal:'</T303DID00>'@DP303DID"),
        ),
        retired_homes=(
            ("DP30301", "26", "casilla:02"),
            ("DP30301", "29", "casilla:05"),
            ("DP30301", "32", "casilla:08"),
            ("DP30301", "44", "casilla:20"),
            ("DP30301", "47", "casilla:23"),
        ),
    ),
    "2024-early": _EpochSurfaceExpectation(
        no_activity_marker_ordinal="28",
        amendment_evidence=(("DP30303", "29", "computed_key", ExportComputedKey.M303_COMPLEMENTARIA_MARKER),),
        general_rate_allowed_values=("0", "50", "62"),
        predecessor="2023",
        # The 2024-early design is anchor-identical to 2023 and introduces no
        # new home at all: it only reserves four simplified-regime slots the
        # 2023 design carried as payload.
        introduced_homes=(),
        retired_homes=(
            ("DP30302", "92", _simplified_fact_home("no_agricola", "empleados_inicio_ejercicio", 1)),
            ("DP30302", "94", _simplified_fact_home("no_agricola", "max_asalariados_simultaneos", 1)),
            ("DP30302", "120", _simplified_fact_home("no_agricola", "empleados_inicio_ejercicio_actual", 2)),
            ("DP30302", "122", _simplified_fact_home("no_agricola", "max_asalariados_simultaneos", 2)),
        ),
    ),
    "2024-late": _EpochSurfaceExpectation(
        no_activity_marker_ordinal="28",
        amendment_evidence=_M303_RECTIFICATIVA_EVIDENCE,
        general_rate_allowed_values=None,
        predecessor="2024-early",
        introduced_homes=(
            # DP30301: the RDL 4/2024 transitional super-reducido rung -- base,
            # tipo and cuota -- and its recargo de equivalencia companion. The
            # design gives each of the six its own official box, so each is one
            # casilla rather than a shared rung.
            *(
                ("DP30301", str(ordinal), f"casilla:{casilla}")
                for ordinal, casilla in enumerate(range(165, 171), start=80)
            ),
            *(
                ("DP30302", str(ordinal), _simplified_fact_home(cohort, fact, slot))
                for ordinal, cohort, fact, slot in _M303_2024_LATE_SIMPLIFIED_ADDITIONS
            ),
            # DP30303: the amendment-evidence region the epoch rows require be
            # hand-reviewed rather than inherited. Ordinal 29 stops being a
            # complementaria marker and becomes the rectificativa flag, which
            # moves the home between two producers rather than shifting it.
            ("DP30303", "29", "producer:amendment_evidence.is_rectificativa"),
            ("DP30303", "31", "producer:prior_domiciliation.action"),
            ("DP30303", "32", "casilla:108"),
            ("DP30303", "33", "casilla:111"),
            ("DP30303", "35", "producer:amendment_evidence.m303_motive.rectificaciones"),
            ("DP30303", "36", "producer:amendment_evidence.m303_motive.discrepancia_criterio_administrativo"),
        ),
        retired_homes=(("DP30303", "29", "computed:m303_complementaria_marker"),),
    ),
    "2025": _EpochSurfaceExpectation(
        no_activity_marker_ordinal="28",
        # DP30303 is anchor-identical to 2024-late and every one of its homes
        # carries over, so the rectificativa block is re-asserted here rather
        # than inherited by silence.
        amendment_evidence=_M303_RECTIFICATIVA_EVIDENCE,
        # Ordinal 50 stops enumerating: the 2025 design mandates a plain
        # Constante there, so the slot states no closed domain of its own.
        general_rate_allowed_values=None,
        predecessor="2024-late",
        introduced_homes=tuple(
            ("DP30302", str(ordinal), _simplified_fact_home(cohort, fact, slot, sub_index))
            for ordinal, cohort, fact, slot, sub_index in _M303_2025_SUPERFICIE_ADDITIONS
        ),
        retired_homes=(
            # [17] loses its Nota 9 enumeration and becomes a plain mandated
            # `Constante "00000"`. It is `manual` with no formula and no dated
            # parameter, so no computed authority stands behind the slot and a
            # literal is the faithful home; [154] and [166] keep their casilla
            # homes precisely because they DO have one. Same design shape, two
            # homes, decided by whether an authority exists rather than by how
            # the slot reads.
            ("DP30301", "50", "casilla:17"),
            # The DANA relief of RD-ley 6/2024 and 7/2024 was a 2024-only
            # measure; the 2025 design reclaims its slots as reserved space
            # and drops the Lorca eligibility flags with it.
            ("DP30302", "95", _simplified_fact_home("no_agricola", "dana_elegible", 1)),
            ("DP30302", "96", _simplified_fact_home("no_agricola", "lorca_elegible", 1)),
            ("DP30302", "124", _simplified_fact_home("no_agricola", "dana_elegible", 2)),
            ("DP30302", "125", _simplified_fact_home("no_agricola", "lorca_elegible", 2)),
            ("DP30302", "154", _simplified_fact_home("agricola", "dana_elegible", 1)),
            ("DP30302", "155", _simplified_fact_home("agricola", "reduccion_dana", 1)),
            ("DP30302", "156", _simplified_fact_home("agricola", "dana_elegible", 2)),
            ("DP30302", "157", _simplified_fact_home("agricola", "reduccion_dana", 2)),
            ("DP30302", "158", _simplified_fact_home("no_agricola", "reduccion_lorca", 1)),
            ("DP30302", "159", _simplified_fact_home("no_agricola", "reduccion_dana", 1)),
            ("DP30302", "160", _simplified_fact_home("no_agricola", "reduccion_lorca", 2)),
            ("DP30302", "161", _simplified_fact_home("no_agricola", "reduccion_dana", 2)),
            # The single Superficie de horno day count per activity is replaced
            # by the four sub-indexed pairs introduced above.
            ("DP30302", "152", _simplified_fact_home("no_agricola", "superficie_horno_dias_cuarto_trimestre", 1)),
            ("DP30302", "153", _simplified_fact_home("no_agricola", "superficie_horno_dias_cuarto_trimestre", 2)),
        ),
    ),
    "2026": _EpochSurfaceExpectation(
        # DP30303 is re-laid out rather than re-vocabularised: box [112] is
        # inserted into the resultado block and [108] moves to its head, so
        # every later ordinal shifts. The block is re-derived from the 2026
        # design rather than carried across, which is why the ordinals differ
        # from every earlier epoch while the homes do not.
        amendment_evidence=(
            ("DP30303", "24", "casilla_id", "108"),
            ("DP30303", "31", "producer_key", "amendment_evidence.is_rectificativa"),
            ("DP30303", "32", "producer_key", "amendment_evidence.original_aeat_receipt"),
            ("DP30303", "33", "producer_key", "prior_domiciliation.action"),
            ("DP30303", "34", "casilla_id", "111"),
            ("DP30303", "35", "producer_key", "amendment_evidence.m303_motive.rectificaciones"),
            ("DP30303", "36", "producer_key", "amendment_evidence.m303_motive.discrepancia_criterio_administrativo"),
            ("DP30303", "37", "kind", "filler"),
        ),
        general_rate_allowed_values=None,
        no_activity_marker_ordinal="30",
        predecessor="2025",
        introduced_homes=(
            # Entitlement to deduct the advance payment on fuel deliveries
            # after the non-customs deposit regime ends. The producer key was
            # already in the closed filing vocabulary and had no anchor until
            # this design declared one.
            ("DP30301", "25", "producer:m303.hydrocarbon_deposit_advance_payment_deduction_entitled"),
            # The matching resultado box, summed from the modelo 319 filings
            # the autoliquidación covers, which also enters [71]'s formula.
            ("DP30303", "28", "casilla:112"),
        ),
        retired_homes=(),
    ),
}


@dataclass(frozen=True, slots=True)
class _NoteBearingForm:
    """One distinct official content string that carries a ``Nota`` reference."""

    content: str
    aeat_type: str
    design_epochs: frozenset[str]

    @property
    def is_numeric(self) -> bool:
        return self.aeat_type.casefold() in _NUMERIC_AEAT_TYPES

    @property
    def notes_are_all_parenthesised(self) -> bool:
        return len(_PARENTHESISED_NOTE.findall(self.content)) == len(_NOTE_REFERENCE.findall(self.content))


@dataclass(frozen=True, slots=True)
class _EpochAuthorities:
    """Every real authority one design epoch is proved against."""

    design_epoch: str
    intermediate: RecordDesignIntermediate
    semantic_map: SemanticMap
    inspection: RegistryRevisionInspection
    joined: JoinedRecordDesign
    profile: RenderProfile
    source_evidence: RenderProfileSourceEvidence

    @property
    def source_ref(self) -> str:
        return str(self.semantic_map.source_ref)

    @property
    def source_sha256(self) -> str:
        return self.semantic_map.source_sha256

    @property
    def field_id_prefix(self) -> str:
        return f"m303-{self.design_epoch}"

    def transport(self) -> ExportTreeTransportProfile:
        return ExportTreeTransportProfile(
            modelo=_MODELO,
            design_epoch=self.design_epoch,
            source_ref=self.source_ref,
            source_sha256=self.source_sha256,
            layout_id=f"generated-modelo-303-{self.design_epoch}-fichero",
            format="fixed_width",
            encoding=ExportEncoding.LATIN_1,
            line_ending="crlf",
            serializer_convention="rtoml-pretty-v1",
        )


def _discovered_design_epochs() -> tuple[str, ...]:
    """Return every authored mapping epoch, in stable lexical order."""
    return tuple(sorted(path.name for path in scan_directory(_MAPPING_ROOT, select=DirectoryEntryKind.DIRECTORIES)))


_DESIGN_EPOCHS: Final[tuple[str, ...]] = _discovered_design_epochs()


#: These proofs verify AUTHORING artefacts -- semantic maps and render profiles --
#: against the compiled design, so they read the compiler tier rather than
#: `ValidatedRegistryAuthority`. The authority is a filing-grade gate that
#: refuses a tree which cannot file yet, which is the state these maps exist to
#: move the tree out of; asking it to load here would make map verification wait
#: on an operator attestation it has no bearing on.
@cache
def _compiled_modelo():
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return next(modelo for modelo in modelos if str(modelo.id) == _MODELO), catalogues


def _resolve_owning_inspection(source_ref: str) -> tuple[RegistryRevisionInspection, int]:
    """Resolve the revision owning one record-design source, from its own declaration.

    The revision is found BY the design source it declares, never by feeding a
    stored revision id into resolution, and its filing year is read from that
    revision's own published period selector.
    """
    modelo, catalogues = _compiled_modelo()
    owners = tuple(revision for revision in modelo.revisions.values() if source_ref in revision.source_refs)
    if len(owners) != 1:
        raise AssertionError(
            f"record-design source {source_ref!r} must be declared by exactly one Modelo 303 revision, "
            f"found {tuple(revision.id for revision in owners)!r}",
        )
    revision = owners[0]
    selector = revision.period_selector
    filing_year = selector.years[0] if selector.years else selector.year_from
    assert filing_year is not None
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=revision,
        source_root=_SOURCE_ROOT,
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    assert str(inspection.revision_id) == str(revision.id)
    return inspection, int(filing_year)


@cache
def _bundled_design_note_forms() -> tuple[_NoteBearingForm, ...]:
    """Return every distinct ``Nota``-bearing content form in every bundled 303 design.

    The sweep is deliberately WIDER than the mapped epochs.  A semantic map and
    a render profile exist for only some designs, but the note peeler runs on
    the parsed design alone, so restricting it to the mapped subset would leave
    the newest bundled designs -- the ones a future map will be authored
    against -- unexamined until somebody authored that map.
    """
    modelo, _catalogues = _compiled_modelo()
    epochs_by_form: dict[tuple[str, str], set[str]] = {}
    for revision in modelo.revisions.values():
        design_refs = tuple(ref for ref in revision.source_refs if str(ref).startswith(_DESIGN_SOURCE_PREFIX))
        if not design_refs:
            continue
        inspection, selector_year = _resolve_owning_inspection(str(design_refs[0]))
        for design_ref in design_refs:
            source = inspection.sources[str(design_ref)]
            assert source.record_design_epoch is not None
            assert source.applies_from is not None
            # A revision may open years before the design it currently declares
            # applies (the 2022 span carries the 2022 design), so
            # the probe year is the later of the two rather than the revision's.
            intermediate = load_record_design_intermediate(
                inspection.source_root,
                inspection.sources,
                source_ref=str(design_ref),
                filing_year=max(selector_year, source.applies_from.year),
                design_epoch=source.record_design_epoch,
            )
            for sheet in intermediate.sheets:
                for field in sheet.fields:
                    content = " ".join((field.content or "").split())
                    if not content or _NOTE_TOKEN.search(content) is None:
                        continue
                    key = (content, field.aeat_type.strip())
                    epochs_by_form.setdefault(key, set()).add(source.record_design_epoch)
    return tuple(
        _NoteBearingForm(content=content, aeat_type=aeat_type, design_epochs=frozenset(epochs))
        for (content, aeat_type), epochs in sorted(epochs_by_form.items())
    )


@cache
def _authorities(design_epoch: str) -> _EpochAuthorities:
    semantic_map = load_semantic_map(_MAPPING_ROOT / design_epoch)
    assert semantic_map.design_epoch == design_epoch
    inspection, filing_year = _resolve_owning_inspection(str(semantic_map.source_ref))
    intermediate = load_record_design_intermediate(
        inspection.source_root,
        inspection.sources,
        source_ref=str(semantic_map.source_ref),
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    source_evidence = RenderProfileSourceEvidence(
        design_identity=RenderProfileDesignIdentity(
            modelo=_MODELO,
            design_epoch=design_epoch,
            source_ref=str(semantic_map.source_ref),
            source_sha256=semantic_map.source_sha256,
        ),
        entries=(),
    )
    profile = load_and_validate_render_profile(_PROFILE_ROOT / design_epoch, joined, source_evidence)
    return _EpochAuthorities(
        design_epoch=design_epoch,
        intermediate=intermediate,
        semantic_map=semantic_map,
        inspection=inspection,
        joined=joined,
        profile=profile,
        source_evidence=source_evidence,
    )


@pytest.fixture(scope="module", params=_DESIGN_EPOCHS)
def epoch(request: pytest.FixtureRequest) -> _EpochAuthorities:
    return _authorities(str(request.param))


def test_every_authored_design_epoch_is_discoverable_and_reviewed() -> None:
    """Discovery must find real epochs, each with a profile and a reviewed census."""
    assert _DESIGN_EPOCHS, "no Modelo 303 semantic-map epoch was discovered under the mapping tree"
    for design_epoch in _DESIGN_EPOCHS:
        assert (_PROFILE_ROOT / design_epoch).is_dir(), f"epoch {design_epoch!r} has no render profile"
        assert design_epoch in M303_SEMANTIC_CENSUS_EXPECTATIONS, (
            f"epoch {design_epoch!r} has no reviewed census expectation"
        )
        assert design_epoch in _EPOCH_SURFACES, f"epoch {design_epoch!r} has no reviewed surface expectation"


def test_the_reviewed_epoch_chain_reaches_every_epoch_from_one_root() -> None:
    """Every epoch but the earliest must be reviewed against a real predecessor.

    Without this, a newly authored epoch could declare ``predecessor = None``
    and its whole introduced-home review would be vacuously satisfied -- the
    exact escape the per-epoch hand review exists to prevent.
    """
    roots = tuple(name for name in _DESIGN_EPOCHS if _EPOCH_SURFACES[name].predecessor is None)
    assert len(roots) == 1, f"exactly one design epoch may be the review root, found {roots!r}"

    walked: dict[str, int] = {}
    for design_epoch in _DESIGN_EPOCHS:
        seen: list[str] = []
        cursor: str | None = design_epoch
        while cursor is not None:
            assert cursor in _EPOCH_SURFACES, f"epoch {design_epoch!r} chains to unreviewed {cursor!r}"
            assert cursor not in seen, f"epoch {design_epoch!r} has a cyclic predecessor chain: {seen!r}"
            seen.append(cursor)
            cursor = _EPOCH_SURFACES[cursor].predecessor
        assert seen[-1] == roots[0]
        walked[design_epoch] = len(seen)

    assert set(walked) == set(_DESIGN_EPOCHS)
    assert sorted(walked.values()) == list(range(1, len(_DESIGN_EPOCHS) + 1)), (
        f"the predecessor chain must be one line through every epoch, measured depths {walked!r}"
    )


def test_source_inspection_map_and_profile_are_exhaustive(epoch: _EpochAuthorities) -> None:
    expectation = M303_SEMANTIC_CENSUS_EXPECTATIONS[epoch.design_epoch]
    census = census_m303_semantic_map(
        epoch.intermediate,
        epoch.semantic_map,
        design_epoch=epoch.design_epoch,
    )

    assert epoch.intermediate.source.source_sha256 == epoch.source_sha256
    assert census.fixed_anchor_count == expectation.fixed_anchor_count
    assert census.variable_envelope_anchor_count == M303_VARIABLE_ENVELOPE_ANCHOR_COUNT
    assert census.total_anchor_count == expectation.total_anchor_count
    assert census.class_totals == dict(expectation.class_totals)
    assert census.review_home_totals == dict(expectation.review_home_totals)
    assert census.simplified_projection_anchor_count == len(expectation.simplified_anchors)
    assert sum(len(record.fields) for record in epoch.joined.records) == expectation.fixed_anchor_count
    assert len(epoch.joined.variable_envelopes) == 1
    assert len(epoch.profile.singleton_rules) == _SINGLETON_RULE_COUNT
    assert epoch.profile.design_identity == epoch.source_evidence.design_identity


def test_reviewed_anchor_vocabulary_is_exact(epoch: _EpochAuthorities) -> None:
    """Every shared and epoch-specific reviewed anchor still carries its own home."""
    by_anchor = {(entry.anchor.record_identity, entry.anchor.ordinal): entry for entry in epoch.semantic_map.entries}
    surface = _EPOCH_SURFACES[epoch.design_epoch]
    no_activity_marker = (
        "DP30303",
        surface.no_activity_marker_ordinal,
        "computed_key",
        ExportComputedKey.M303_NO_ACTIVITY_MARKER,
    )
    for record_identity, ordinal, attribute, expected in (
        *_SHARED_ANCHOR_FACTS,
        no_activity_marker,
        *surface.amendment_evidence,
    ):
        entry = by_anchor[(record_identity, ordinal)]
        assert _anchor_fact(entry, attribute) == expected, (
            f"{epoch.design_epoch} {record_identity}/{ordinal}.{attribute}"
        )


def test_simplified_projections_cover_exactly_the_s63_declaration_index(epoch: _EpochAuthorities) -> None:
    expectation = M303_SEMANTIC_CENSUS_EXPECTATIONS[epoch.design_epoch]
    simplified = {
        (entry.anchor.record_identity, entry.anchor.ordinal)
        for entry in epoch.semantic_map.entries
        if entry.projection_ref is not None
        and str(entry.projection_ref.projection_kind).startswith("m303_regimen_simplificado")
    }
    by_anchor = {(entry.anchor.record_identity, entry.anchor.ordinal): entry for entry in epoch.semantic_map.entries}

    assert simplified == set(expectation.simplified_anchors)
    assert all(
        by_anchor[("DP30302", str(ordinal))].kind.value == "filler"
        for ordinal in expectation.simplified_filler_ordinals
    )


def test_real_static_compiler_normalizes_the_complete_map(epoch: _EpochAuthorities) -> None:
    """The static compiler resolves every sourced field without filing-instance inputs."""
    records, derivations = _render_records(epoch.joined.records, epoch.transport(), epoch.profile)

    # Body records in official order, but only the ones THIS design lays out.
    # `_RECORD_IDS` is the full official sequence; the 2022 design carries five
    # body sheets (DP30301..DP30305) and the domiciliacion record DP303DID
    # arrives with the 2023 design, so a flat equality asserted a record that
    # design has never had. The count comes from the design's own sheets and the
    # ORDER from `_RECORD_IDS`, so a record that renders out of official order,
    # or a design sheet that renders no record at all, still fails.
    rendered = tuple(record.id for record in records)
    declared_sheets = {
        field.semantic_entry.anchor.record_identity for record in epoch.joined.records for field in record.fields
    }
    assert len(rendered) == len(declared_sheets), (
        f"{epoch.design_epoch} lays out {len(declared_sheets)} body sheets but rendered {len(rendered)} records"
    )
    assert rendered == tuple(record_id for record_id in _RECORD_IDS if record_id in set(rendered))
    assert set(rendered) <= set(_RECORD_IDS)
    by_field_id = {str(derivation.field.id): derivation.field for derivation in derivations}
    blank_page_marker_ids = {
        f"{epoch.field_id_prefix}.dp30301.f005",
        f"{epoch.field_id_prefix}.dp30304.f005",
    }
    assert blank_page_marker_ids <= set(by_field_id)
    assert all(
        by_field_id[field_id].literal == ""
        and by_field_id[field_id].length == 1
        and by_field_id[field_id].padding.value == "none"
        for field_id in blank_page_marker_ids
    )
    result_disposition = by_field_id[f"{epoch.field_id_prefix}.dp30301.f006"]
    assert result_disposition.kind.value == "header"
    assert result_disposition.producer_key is not None
    assert result_disposition.producer_key.value == "filing.result_disposition"
    assert (
        by_field_id[f"{epoch.field_id_prefix}.dp30301.f050"].allowed_values
        == _EPOCH_SURFACES[epoch.design_epoch].general_rate_allowed_values
    )


def _integer_slot_widths(design_epoch: str) -> frozenset[int]:
    """Widths for which ``design_epoch``'s DP30302 sheet declares a pure-integer slot."""
    authorities = _authorities(design_epoch)
    return frozenset(
        field.parser_field.length
        for record in authorities.joined.records
        for field in record.fields
        if field.semantic_entry.anchor.record_identity == "DP30302"
        and field.semantic_entry.kind.value not in {"literal", "filler"}
        and (match := _INTEGER_CONTENT.fullmatch((field.parser_field.content or "").strip())) is not None
        and int(match.group("whole")) == field.parser_field.length
    )


def _epoch_width_pairs() -> list[tuple[str, int]]:
    """Every (epoch, width) the DESIGNS actually declare a pure-integer slot for.

    The note-grammar probes were parametrised over every epoch crossed with the
    fixed widths 4 and 7. The 2022 design declares NO pure-integer DP30302 slot
    at all -- every numeric slot on that sheet is money ("15 enteros y 2
    decimales") -- because the pure-integer slots are the Regimen Simplificado
    actividad modules (epigrafe, numero de unidades, modulos) that the 2023
    design introduced on DP30302. So 2022 x {4, 7} asked for slots that design
    has never had, and `_integer_field_of_width`'s anti-vacuity guard correctly
    refused rather than passing on nothing.

    Deriving the pairs keeps that guard meaningful -- an epoch that LOSES a slot
    silently drops out of its own coverage, which is why the widths are asserted
    non-empty below -- while covering strictly more than the hardcoded pair did:
    widths 2 and 3 are probed too, wherever a design declares them.
    """
    pairs = [
        (design_epoch, width) for design_epoch in _DESIGN_EPOCHS for width in sorted(_integer_slot_widths(design_epoch))
    ]
    assert pairs, "no design epoch declares a pure-integer DP30302 slot; the note-grammar probes would all vanish"
    return pairs


@pytest.mark.parametrize(("design_epoch", "width"), _epoch_width_pairs())
@pytest.mark.parametrize(
    "suffix",
    [
        "",
        # A bare terminator with no annotation behind it. The 2025 and 2026
        # designs write their money slots this way, and no test covered the
        # shape until it refused a real epoch.
        ".",
        # Every separator form below is present in the bundled Modelo 303
        # corpus: dot-space dominates, comma-space carries Nota 3, and a bare
        # space carries Nota 2 after a quoted enumeration token.
        ". Nota 6",
        ", Nota 6",
        " Nota 6",
        # The note NUMBER is a per-design vocabulary fact, not a wire-grammar
        # fact. The 2024-late design annotates numeric and enumeration anchors
        # with notes 8, 9 and 10, which a six-keyed tolerance could not admit,
        # and its note table defines 1 through 10.
        ". Nota 5",
        ". Nota 10",
        ". Nota 8. Nota 7",
    ],
)
def test_integer_source_grammar_peels_any_trailing_note_reference(
    design_epoch: str,
    width: int,
    suffix: str,
) -> None:
    """A trailing note reference annotates official content without changing its wire fact."""
    epoch = _authorities(design_epoch)
    field_id = _integer_field_of_width(epoch, width)
    _render_with_integer_content(epoch, field_id=field_id, content=f"{width} enteros{suffix}")


def _epochs_declaring_width(width: int) -> list[str]:
    """Design epochs whose DP30302 sheet declares a pure-integer slot of ``width``."""
    epochs = [item for item in _DESIGN_EPOCHS if width in _integer_slot_widths(item)]
    assert epochs, f"no design epoch declares a pure-integer DP30302 slot of width {width}"
    return epochs


#: Every probe below is written for a FOUR-integer slot, so the epochs are those
#: whose design declares one. The 2022 sheet declares no pure-integer slot at any
#: width -- those are the Regimen Simplificado actividad modules the 2023 design
#: introduced -- so it was asking `_integer_field_of_width` for a field that
#: design has never carried.
@pytest.mark.parametrize("design_epoch", _epochs_declaring_width(4))
@pytest.mark.parametrize(
    "content",
    [
        "4 enteros. Nota",
        "4 enteros. Nota 6 y siguientes",
        "4 enteros. Véase la nota",
        "cuatro enteros. Nota 6",
        "4 enteros y 2 decimales. Nota 6",
    ],
)
def test_integer_source_grammar_refuses_malformed_or_mismatched_content(
    design_epoch: str,
    content: str,
) -> None:
    """A numberless, trailing-prose, non-numeric or width-mismatched form still fails closed."""
    epoch = _authorities(design_epoch)
    field_id = _integer_field_of_width(epoch, 4)
    with pytest.raises(RegistryValidationError):
        _render_with_integer_content(epoch, field_id=field_id, content=content)


def test_the_note_form_sweep_reaches_every_bundled_design_and_all_three_shapes() -> None:
    """Anti-vacuity for the corpus sweep: it must read every design and find every shape.

    A sweep that silently reads nothing reports the same clean verdict as a
    corpus with no defect, so the reach is asserted before the property is.
    """
    modelo, _catalogues = _compiled_modelo()
    declared_designs = {
        str(ref)
        for revision in modelo.revisions.values()
        for ref in revision.source_refs
        if str(ref).startswith(_DESIGN_SOURCE_PREFIX)
    }
    forms = _bundled_design_note_forms()
    swept_epochs = {epoch for form in forms for epoch in form.design_epochs}

    assert len(declared_designs) > 1, declared_designs
    assert len(swept_epochs) == len(declared_designs), (swept_epochs, declared_designs)
    assert _DESIGN_EPOCHS and set(_DESIGN_EPOCHS) <= swept_epochs
    assert any(form.notes_are_all_parenthesised for form in forms), "no parenthesised note form was swept"
    assert any(
        not form.notes_are_all_parenthesised and not _split_official_note_references(form.content)[0] for form in forms
    ), "no note-only form was swept"
    assert any(
        not form.notes_are_all_parenthesised and _split_official_note_references(form.content)[0] for form in forms
    ), "no annotated-value form was swept"
    assert any(len(_split_official_note_references(form.content)[1]) > 2 for form in forms), (
        "no form carrying more than two chained notes was swept"
    )


@pytest.mark.parametrize(
    ("content", "grammar"),
    [
        ("15 enteros y 2 decimales.", "decimal"),
        ("15 enteros y 2 decimales", "decimal"),
        ("15 enteros y 2 decimales, menor o igual que 100.", "decimal"),
        ("7 enteros.", "integer"),
        ("7 enteros", "integer"),
        ("4 entero.", "integer"),
    ],
)
def test_a_bare_trailing_period_is_the_value_grammar_s_business_not_the_note_peel_s(
    content: str,
    grammar: str,
) -> None:
    """Sentence punctuation is read by the grammar; the peel leaves it alone.

    Stated as two assertions because the ruling is about WHERE the terminator is
    handled, not merely that it is: the peel must report this content unchanged,
    since there is no note to remove and a peel that silently ate the period
    would mutate a stem while accounting for nothing.
    """
    assert _split_official_note_references(content) == (content, ())
    pattern = {"decimal": _DECIMAL_CONTENT_RE, "integer": _INTEGER_CONTENT_RE}[grammar]
    assert pattern.fullmatch(content) is not None


@pytest.mark.parametrize(
    "content",
    [
        # Tolerating one terminator must not tolerate a doubled one, nor any
        # trailing prose, nor a note reference the peel did not remove.
        "15 enteros y 2 decimales..",
        "15 enteros y 2 decimales, menor o igual que 100..",
        "15 enteros y 2 decimales .",
        "7 enteros..",
        "7 enteros. y algo",
        "7 enteros. Nota",
    ],
)
def test_the_trailing_period_tolerance_did_not_loosen_the_numeric_grammars(content: str) -> None:
    """The fix must admit one terminator and nothing else."""
    stem, _notes = _split_official_note_references(content)
    assert _DECIMAL_CONTENT_RE.fullmatch(stem) is None
    assert _INTEGER_CONTENT_RE.fullmatch(stem) is None


def test_note_reference_peeling_only_ever_removes_a_trailing_annotation() -> None:
    """Peeling is suffix-only, idempotent, and accounts for every note it removes.

    Stated as invariants rather than as an expected (stem, notes) pair per
    string: an expected pair would be a second transcription of the same regex,
    which agrees with the implementation by construction and so proves nothing.
    """
    failures: list[str] = []
    for form in _bundled_design_note_forms():
        stem, notes = _split_official_note_references(form.content)
        tail = form.content[len(stem) :] if form.content.startswith(stem) else None
        if tail is None:
            failures.append(f"{form.content!r}: peeled stem {stem!r} is not a prefix of the official content")
            continue
        if _TRAILING_NOTE_REFERENCE_RE.search(stem) is not None:
            failures.append(f"{form.content!r}: stem {stem!r} still ends in a note reference")
        if _split_official_note_references(stem) != (stem, ()):
            failures.append(f"{form.content!r}: peeling stem {stem!r} is not a fixed point")
        removed = tuple(int(number) for number in _NOTE_REFERENCE.findall(tail))
        if removed != notes:
            failures.append(f"{form.content!r}: reported notes {notes} do not match the removed tail {removed}")
    assert not failures, "\n".join(failures)


def test_a_parenthesised_note_reference_is_peeled_only_from_the_tail() -> None:
    r"""A parenthesised note is an annotation when it TRAILS and part of the value when it does not.

    This asserted that a parenthesised reference is never peeled at all, on the
    reading that ``blanco, "1" o "2" (Nota 3)`` carries its reference INSIDE the
    enumeration. It does not: the reference trails the complete enumeration, and
    peeling it leaves ``blanco, "1" o "2"`` with nothing lost. The peeler says so
    itself -- `_TRAILING_NOTE_REFERENCE_RE` spells an optional ``\(?`` and
    ``\)?`` around the reference and anchors on ``$`` -- so refusing to peel a
    trailing parenthesised note contradicted the shipped grammar rather than
    guarding the value.

    The hazard the old wording named is real but is a DIFFERENT shape: a note
    sitting between two enumeration members. That is asserted directly below,
    and the ``$`` anchor is what makes it safe.
    """
    parenthesised = tuple(form for form in _bundled_design_note_forms() if form.notes_are_all_parenthesised)
    assert parenthesised, "the corpus no longer exercises a parenthesised note reference"
    for form in parenthesised:
        stem, notes = _split_official_note_references(form.content)
        # Only a TAIL may be removed: the stem must be a leading slice of the
        # content, and everything dropped must be note text and punctuation.
        assert form.content.startswith(stem), form.content
        removed = form.content[len(stem) :]
        assert notes, form.content
        assert all(f"Nota {number}" in removed for number in notes), form.content
        assert re.fullmatch(r"[\s.,;()]*(?:Nota\s+\d+[\s.,;()]*)+", removed), removed

    # An INTERIOR reference is part of the value and stays untouched, which is
    # what keeps the peel from truncating an enumeration mid-way.
    interior = '"1" (Nota 3) o "2"'
    assert _split_official_note_references(interior) == (interior, ())


def test_every_numeric_note_bearing_form_peels_to_one_readable_value_grammar() -> None:
    """A peeled numeric stem is either note-only or read by exactly one grammar.

    This is what makes the peel safe to run ahead of the value grammars rather
    than inside each of them: on every numeric slot the bundled designs
    declare, removing the annotation leaves content the derivation can read,
    and leaves it unambiguous.  Non-numeric slots are excluded because their
    content never reaches the numeric derivation at all.
    """
    grammars = {
        "integer": _INTEGER_CONTENT_RE,
        "decimal": _DECIMAL_CONTENT_RE,
        "enumeration": _QUOTED_NUMERIC_ENUMERATION_RE,
        "boolean-enumeration": _QUOTED_NUMERIC_BOOLEAN_ENUMERATION_RE,
        "constant": _OFFICIAL_LITERAL_RE,
    }
    numeric = tuple(form for form in _bundled_design_note_forms() if form.is_numeric)
    assert numeric, "the corpus no longer exercises a numeric note-bearing form"

    failures: list[str] = []
    for form in numeric:
        stem, notes = _split_official_note_references(form.content)
        if not stem:
            if not notes:
                failures.append(f"{form.content!r}: peeled to nothing at all")
            continue
        matched = sorted(name for name, pattern in grammars.items() if pattern.fullmatch(stem) is not None)
        if len(matched) != 1:
            failures.append(f"{form.content!r}: stem {stem!r} is read by {matched or 'no'} value grammar")
    assert not failures, "\n".join(failures)


def test_static_declaration_preserves_dp30300_without_instance_values(
    epoch: _EpochAuthorities,
    tmp_path: Path,
) -> None:
    """The reviewed map compiles DP30300 without period or payload inputs."""
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=epoch.inspection.revision_id,
        joined=epoch.joined,
        semantic_map=epoch.semantic_map,
        transport_profile=epoch.transport(),
        render_profile=epoch.profile,
        render_profile_source_evidence=epoch.source_evidence,
    )
    declaration = rendered.layout.filing_envelope
    assert declaration is not None

    assert declaration.source_ref == epoch.source_ref
    assert declaration.source_sha256 == epoch.source_sha256
    assert declaration.body_record_ids == tuple(record.id for record in rendered.layout.records)
    assert sum(field.length for field in declaration.prefix_fields) == _ENVELOPE_PREFIX_LENGTH
    assert rendered.provenance_manifest.variable_envelope_contract is not None
    assert rendered.provenance_manifest.variable_envelope_contract.envelope == declaration


def test_each_epoch_carries_its_own_map_and_render_profile_identity() -> None:
    """No two epochs share a semantic map or a render profile.

    This replaces three hand-transcribed digest literals.  A pinned hex only
    ever attested that an artefact had not changed since somebody copied the
    value out of a failure message, and it had to be re-copied on every
    legitimate revision.  What the digests can prove without a transcription is
    that the epochs are genuinely distinct artefacts -- the failure a
    copy-forwarded fragment directory or a profile left bound to its
    predecessor's design identity would actually produce.
    """
    semantic_digests = {epoch: semantic_map_digest(_authorities(epoch).semantic_map) for epoch in _DESIGN_EPOCHS}
    profile_digests = {
        epoch: render_profile_digest(_authorities(epoch).profile, _authorities(epoch).source_evidence)
        for epoch in _DESIGN_EPOCHS
    }

    assert len(set(semantic_digests.values())) == len(_DESIGN_EPOCHS), semantic_digests
    assert len(set(profile_digests.values())) == len(_DESIGN_EPOCHS), profile_digests


def _homes_by_anchor(semantic_map: SemanticMap) -> dict[str, tuple[str, int]]:
    """Return each distinct home identity and one anchor that carries it.

    Identities come from the census module's single home resolver, so this
    review and the census totals cannot disagree about what an entry's home is.
    """
    return {
        resolve_semantic_home(entry).identity: (entry.anchor.record_identity, entry.anchor.ordinal)
        for entry in semantic_map.entries
    }


def test_every_semantic_home_an_epoch_introduces_or_retires_is_reviewed(epoch: _EpochAuthorities) -> None:
    """A home that changes canonical authority between epochs must be hand-reviewed.

    The census proves each epoch's map covers its own source exactly once, and
    its totals catch a home that changes CLASS.  Neither can see a home that
    moves to a different authority of the same class -- exchanging two casillas,
    or two simplified-regime slots, leaves every total identical while sending a
    taxpayer's figure to the wrong official box.  Comparing fully-qualified home
    identities against the predecessor epoch's real map is what closes that, and
    it stays quiet for the offset shifts a re-layout genuinely is.
    """
    surface = _EPOCH_SURFACES[epoch.design_epoch]
    if surface.predecessor is None:
        assert not surface.introduced_homes and not surface.retired_homes, (
            f"the root epoch {epoch.design_epoch!r} has no predecessor to introduce or retire a home against"
        )
        return

    predecessor = _authorities(surface.predecessor)
    before = _homes_by_anchor(predecessor.semantic_map)
    after = _homes_by_anchor(epoch.semantic_map)

    measured_introduced = {home: after[home] for home in set(after) - set(before)}
    measured_retired = {home: before[home] for home in set(before) - set(after)}
    reviewed_introduced = {home: (record, ordinal) for record, ordinal, home in surface.introduced_homes}
    reviewed_retired = {home: (record, ordinal) for record, ordinal, home in surface.retired_homes}

    assert measured_introduced == reviewed_introduced, _review_mismatch(
        f"{surface.predecessor} -> {epoch.design_epoch} introduced-home review",
        measured_introduced,
        reviewed_introduced,
    )
    assert measured_retired == reviewed_retired, _review_mismatch(
        f"{surface.predecessor} -> {epoch.design_epoch} retired-home review",
        measured_retired,
        reviewed_retired,
    )


def test_a_paired_anchor_keeps_the_home_its_predecessor_gave_it(epoch: _EpochAuthorities) -> None:
    """A slot both designs declare identically must carry the same home in both.

    This is the gate that catches an exchange of two homes the epoch INHERITS.
    The introduced-and-retired review beside it cannot: swapping two casillas
    that both already existed changes neither set, so it stays silent while a
    taxpayer's figure moves to the wrong official box. Correspondence comes from
    the designs' own declarations, so a re-layout that only shifts ordinals is
    still correctly silent here.
    """
    surface = _EPOCH_SURFACES[epoch.design_epoch]
    if surface.predecessor is None:
        return

    predecessor = _authorities(surface.predecessor)
    pairing = pair_epoch_anchors(predecessor.intermediate, epoch.intermediate)
    before = {(e.anchor.record_identity, e.anchor.ordinal): e for e in predecessor.semantic_map.entries}
    after = {(e.anchor.record_identity, e.anchor.ordinal): e for e in epoch.semantic_map.entries}

    assert pairing.paired, f"{epoch.design_epoch} paired no anchor at all against {surface.predecessor}"
    assert set(after) == set(pairing.paired) | pairing.unpaired_target, (
        "every anchor must be either paired with its predecessor or declared unpaired"
    )

    drifted = tuple(
        f"{target} (declared as {source} in {surface.predecessor}): "
        f"{resolve_semantic_home(before[source]).identity} -> {resolve_semantic_home(after[target]).identity}"
        for target, source in sorted(pairing.paired.items())
        if resolve_semantic_home(before[source]).identity != resolve_semantic_home(after[target]).identity
    )
    assert not drifted, (
        f"{surface.predecessor} -> {epoch.design_epoch}: these anchors are declared identically by both "
        f"designs yet carry different homes, which is a re-homing rather than a re-layout:\n  " + "\n  ".join(drifted)
    )


def _review_mismatch(
    label: str,
    measured: Mapping[str, tuple[str, int]],
    reviewed: Mapping[str, tuple[str, int]],
) -> str:
    """Explain a review mismatch by cause, not by dumping two mappings.

    The three causes read differently to whoever has to act on them: an
    unreviewed home is new work, a stale one is a review of something no longer
    there, and a relocated one is the same home reviewed at a different anchor.
    """
    relocated = tuple(
        f"{home} reviewed at {reviewed[home]} but measured at {measured[home]}"
        for home in sorted(set(measured) & set(reviewed))
        if measured[home] != reviewed[home]
    )
    return (
        f"{label} failed: "
        f"unreviewed={sorted(set(measured) - set(reviewed))}, "
        f"stale={sorted(set(reviewed) - set(measured))}, "
        f"relocated={list(relocated)}"
    )


def _anchor_fact(entry, attribute: _AnchorAttribute) -> object:
    if attribute == "kind":
        return entry.kind.value
    value = getattr(entry, attribute)
    if attribute == "producer_key":
        return None if value is None else value.value
    return value


def _integer_field_of_width(epoch: _EpochAuthorities, width: int) -> str:
    """Return the lowest-numbered DP30302 slot the design declares as ``width`` integers.

    Derived from the parsed design rather than transcribed.  A hardcoded field
    id is exactly what went wrong before: an id copied between epochs named a
    seven-digit slot in one design and a four-digit slot in the next, so the
    case failed on a width mismatch that had nothing to do with the grammar
    under test.
    """
    candidates = sorted(
        str(field.semantic_entry.export_field_id)
        for record in epoch.joined.records
        for field in record.fields
        if field.semantic_entry.anchor.record_identity == "DP30302"
        and field.semantic_entry.kind.value not in {"literal", "filler"}
        and field.parser_field.length == width
        and (match := _INTEGER_CONTENT.fullmatch((field.parser_field.content or "").strip())) is not None
        and int(match.group("whole")) == width
    )
    assert candidates, (
        f"{epoch.design_epoch} declares no DP30302 integer slot of width {width}; "
        "the note-grammar probe would pass vacuously"
    )
    return candidates[0]


def _render_with_integer_content(epoch: _EpochAuthorities, *, field_id: str, content: str) -> None:
    records = tuple(
        record.model_copy(
            update={
                "fields": tuple(
                    field.model_copy(
                        update={"parser_field": field.parser_field.model_copy(update={"content": content})},
                    )
                    if str(field.semantic_entry.export_field_id) == field_id
                    else field
                    for field in record.fields
                ),
            },
        )
        for record in epoch.joined.records
    )
    _render_records(records, epoch.transport(), epoch.profile)
