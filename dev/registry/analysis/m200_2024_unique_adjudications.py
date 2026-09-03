"""Compile the closed target-evidence-reviewed M200/2024 S13 cohort.

The prior-year registry is deliberately absent from this module.  Its former
match only identifies the finite candidate list; record-design geometry, the
2024 manual extraction and resolved 2024 legal catalogue are the evidence that
admits a declaration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import rtoml

from cadrumo.core.hashing import content_hash_hex, sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.loader import load_catalogue_file
from cadrumo.domain.calculations.registry.schema_references import governed_period_span

from ..pipeline._record_design_ir import intermediate_anchor_key, load_record_design_intermediate
from ..pipeline._semantic_map import semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_restored_semantic_audit import audit_bundled_restorations

ADJUDICATION_PATH = Path(__file__).with_suffix(".toml")
TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"
MANUAL_SOURCE_REF = "aeat-modelo-200-manual-2024"
MANUAL_SOURCE_SHA256 = "ad02f914246632dcd7ab30f3e7280daf3501be6ee3938237e2ebfe7328ff8179"
TARGET_WINDOW = (date(2024, 1, 1), date(2024, 12, 31))
_COMMON_LEGAL = ("ley-27-2014:art-41", "ley-27-2014:art-39", "ley-27-2014:art-19", "ley-27-2014:art-100", "rd-634-2015:art-3")
_CLOSED_IDS = frozenset({"00814", "00831", "00832", "01134", "01135", "01136", "01469", "01683", "01684", "01685", "01935", "01964", "01965", "01966", "01967", "02079", "02080", "02287", "02288", "02363", "02364", "02471", "02495", "02496", "02576", "02577", "02691", "02692", "02693", "02694", "02695", "02696", "02697", "02698", "02700", "DP200018:00588"})

# These are target-manual meanings, reviewed independently from a sibling
# declaration.  The source map's current legal anchors are retained exactly so
# the compiler detects an unreviewed map rewrite rather than silently changing
# a filing declaration's legal scope.
_PROFILES: dict[str, tuple[tuple[str, ...], str, tuple[str, ...]]] = {
    "idi_limit_information": (("deducciones_i_d_i_excluidas_de_limite", "informacion_adicional_para_el_calculo_de_limites_d"), "is_deduccion_idi_excluida_limite_info_adicional", _COMMON_LEGAL),
    "deduction_total_pending": (("deducc_para_incentivar_determ_actividades", "total"), "is_deduccion_actividades_total_pendiente", _COMMON_LEGAL),
    "deduction_total_future": (("deducc_para_incentivar_determ_actividades", "total"), "is_deduccion_idi_suma_pendiente", _COMMON_LEGAL),
    "deduction_total_applied": (("liquidacion_iv", "otras_deducciones"), "is_liquidacion_iv_importe", _COMMON_LEGAL),
    "aid_excess_quota": (("conversion_activos_impuesto_diferido_credito_exigi", "exceso_cuota_liquida_positiva"), "is_conversion_aid_exceso_cuota_importe", _COMMON_LEGAL),
    "public_interest_generated": (("deducc_para_incentivar_determ_actividades", "2026_otras_deducciones_relativas_a_programas_de_ap"), "is_deduccion_acontecimiento_interes_publico_otras", _COMMON_LEGAL),
    "public_interest_applied": (("deducc_para_incentivar_determ_actividades", "2026_otras_deducciones_relativas_a_programas_de_ap"), "is_deduccion_eventos_especiales_aplicado_periodo", _COMMON_LEGAL),
    "public_interest_future": (("deducc_para_incentivar_determ_actividades", "2026_otras_deducciones_relativas_a_programas_de_ap"), "is_deduccion_eventos_especiales_pendiente", _COMMON_LEGAL),
    "nivelacion_dotacion": (("reserva_de_nivelacion", "dotacion_de_la_reserva"), "is_reserva_nivelacion_dotacion", _COMMON_LEGAL),
    "nivelacion_pendiente": (("reserva_de_nivelacion", "dotacion_de_la_reserva"), "is_reserva_nivelacion_dotacion_pendiente", _COMMON_LEGAL),
    "nivelacion_dispuesta": (("reserva_de_nivelacion", "dotacion_de_la_reserva"), "is_reserva_nivelacion_dotacion_dispuesta", _COMMON_LEGAL),
    "canarias_financier_cinema": (("informacion_adicional_para_el_calculo_de_limites_d", "2025_financiador_deduccion_por_producciones_cinema"), "is_informacion_adicional_limites_deducciones_canarias_generada", _COMMON_LEGAL),
    "canarias_financier_live": (("informacion_adicional_para_el_calculo_de_limites_d", "2025_financiador_deduccion_por_espectaculos_en_viv"), "is_informacion_adicional_limites_deducciones_canarias_generada", _COMMON_LEGAL),
    "canarias_rd": (("informacion_adicional_para_el_calculo_de_limites_d", "2025_deduccion_por_investigacion_y_desarrollo_en_c"), "is_informacion_adicional_limites_deducciones_canarias_generada", _COMMON_LEGAL),
    "canarias_it": (("informacion_adicional_para_el_calculo_de_limites_d", "2025_deduccion_por_innovacion_tecnologica_en_canar"), "is_informacion_adicional_limites_deducciones_canarias_generada", _COMMON_LEGAL),
    "canarias_producer_cinema": (("informacion_adicional_para_el_calculo_de_limites_d", "2025_productor_deduccion_por_producciones_cinemato"), "is_informacion_adicional_limites_deducciones_canarias_generada", _COMMON_LEGAL),
    "canarias_producer_live": (("informacion_adicional_para_el_calculo_de_limites_d", "2025_productor_deduccion_por_espectaculos_en_vivo"), "is_informacion_adicional_limites_deducciones_canarias_generada", _COMMON_LEGAL),
    "riib_anticipated": (("reg_especial_reserva_inversiones_illes_balears", "inversiones_anticipadas_2025"), "is_reserva_inversiones_illes_balears_importe", _COMMON_LEGAL),
    "donation_general": (("deduccion_donativos_entidades_sin_fines_lucro", "donaciones_de_caracter_general"), "is_deduccion_donativos_general", _COMMON_LEGAL),
    "donation_priority": (("deduccion_donativos_entidades_sin_fines_lucro", "donaciones_para_actividades_prioritarias_de_mecena"), "is_deduccion_donativos_prioritarias", _COMMON_LEGAL),
}


@dataclass(frozen=True, slots=True)
class Adjudication:
    casilla_id: str
    export_field_id: str
    profile: str
    official_column: str
    official_label_sha256: str
    section: tuple[str, ...]
    semantic_role: str
    legal_refs: tuple[str, ...]
    semantic_payload_sha256: str


@dataclass(frozen=True, slots=True)
class CompiledM200UniqueAuthority:
    reviewed_by: str
    reviewed_at: str
    adjudications: tuple[Adjudication, ...]


def compile_m200_2024_unique_authority(path: Path = ADJUDICATION_PATH) -> CompiledM200UniqueAuthority:
    raw = rtoml.loads(path.read_text(encoding="utf-8"))
    _require_header(raw)
    rows = tuple(_parse_row(value) for value in raw.get("adjudications", ()))
    _require_closed_membership(rows)
    fields, maps = _target_fields_and_map()
    rows = _require_target_evidence(rows, fields, maps)
    _require_legal_coverage(rows)
    _require_withheld_01403()
    return CompiledM200UniqueAuthority(str(raw["reviewed_by"]), str(raw["reviewed_at"]), tuple(sorted(rows, key=lambda row: row.export_field_id)))


def render_canonical_declaration(authority: CompiledM200UniqueAuthority, casilla_id: str) -> str:
    matches = tuple(row for row in authority.adjudications if row.casilla_id == casilla_id)
    if len(matches) != 1:
        raise RegistryValidationError(f"M200/2024 unique authority has no unique declaration for {casilla_id!r}")
    row = matches[0]
    return "\n".join(("[[revisions.2024.casillas]]", f"id = {_literal(row.casilla_id)}", f"number = {_literal(row.casilla_id)}", "data_type = 'money'", f"semantic_role = {_literal(row.semantic_role)}", "required = false", "input_kind = 'manual'", f"section = {_array(row.section)}", f"legal_refs = {_array(row.legal_refs)}", f"source_refs = {_array((TARGET_SOURCE_REF, MANUAL_SOURCE_REF))}", ""))


def verify_canonical_declarations(authority: CompiledM200UniqueAuthority, *, casillas_root: Path | None = None) -> None:
    root = bundled_path("registry", "aeat", "modelos", "200", "revisions", "2024", "casillas") if casillas_root is None else casillas_root
    for row in authority.adjudications:
        path = root / f"c{row.casilla_id.replace(':', '+')}.toml"
        if not path.is_file() or path.read_text(encoding="utf-8") != render_canonical_declaration(authority, row.casilla_id):
            raise RegistryValidationError(f"M200/2024 unique declaration {row.casilla_id!r} is not compiler-identical")


def promoted_candidate_ids(authority: CompiledM200UniqueAuthority, *, casillas_root: Path | None = None) -> frozenset[str]:
    if authority != compile_m200_2024_unique_authority():
        raise RegistryValidationError("M200/2024 unique compiler receipt/provenance drifted")
    verify_canonical_declarations(authority, casillas_root=casillas_root)
    return frozenset(row.casilla_id for row in authority.adjudications)


def _require_header(raw: dict[str, object]) -> None:
    expected = {"schema_version": 1, "modelo": "200", "revision": "2024", "source_ref": TARGET_SOURCE_REF, "source_sha256": TARGET_SOURCE_SHA256, "manual_source_ref": MANUAL_SOURCE_REF, "manual_source_sha256": MANUAL_SOURCE_SHA256, "review_status": "agent_reviewed"}
    if any(raw.get(key) != value for key, value in expected.items()) or not isinstance(raw.get("reviewed_by"), str) or not isinstance(raw.get("reviewed_at"), str):
        raise RegistryValidationError("M200/2024 unique adjudication header is not target-authoritative")


def _parse_row(raw: object) -> Adjudication:
    if not isinstance(raw, dict):
        raise RegistryValidationError("M200/2024 unique adjudication entry is malformed")
    try:
        identifier, export, profile, column = (str(raw["casilla_id"]), str(raw["export_field_id"]), str(raw["profile"]), str(raw["column"]))
        section, role, legal = _PROFILES[profile]
    except (KeyError, TypeError) as exc:
        raise RegistryValidationError("M200/2024 unique adjudication entry is malformed") from exc
    digest = content_hash_hex({"section": section, "semantic_role": role, "data_type": "money", "required": False, "input_kind": "manual", "legal_refs": legal, "source_refs": (TARGET_SOURCE_REF, MANUAL_SOURCE_REF)})
    return Adjudication(identifier, export, profile, column, "", section, role, legal, digest)


def _require_closed_membership(rows: tuple[Adjudication, ...]) -> None:
    identifiers = frozenset(row.casilla_id for row in rows)
    if identifiers != _CLOSED_IDS or len(rows) != len(_CLOSED_IDS):
        raise RegistryValidationError("M200/2024 S13 unique adjudication membership is not closed")
    observed = frozenset(row.casilla_id for row in audit_bundled_restorations() if row.cross_revision_status == "unique_non_authoritative")
    if identifiers | {"00942"} != observed:
        raise RegistryValidationError("M200/2024 S13 source candidate membership drifted")


def _target_fields_and_map() -> tuple[dict[str, object], dict[str, object]]:
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    source = catalogues.sources.get(TARGET_SOURCE_REF)
    manual = catalogues.sources.get(MANUAL_SOURCE_REF)
    if source is None or manual is None or source.sha256 != TARGET_SOURCE_SHA256 or manual.sha256 != MANUAL_SOURCE_SHA256:
        raise RegistryValidationError("M200/2024 pinned target evidence drifted")
    design = load_record_design_intermediate(bundled_path(), catalogues.sources, source_ref=TARGET_SOURCE_REF, filing_year=2024, design_epoch="2024")
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    return fields, {str(entry.export_field_id): entry for entry in semantic_map.entries}


def _require_target_evidence(
    rows: tuple[Adjudication, ...], fields: dict[str, object], maps: dict[str, object]
) -> tuple[Adjudication, ...]:
    verified: list[Adjudication] = []
    for row in rows:
        entry = maps.get(row.export_field_id)
        owner = None if entry is None or entry.casilla_id is None else str(entry.casilla_id)
        owner = owner if owner is not None and ":" in owner else None if owner is None else owner.zfill(5)
        if entry is None or owner != row.casilla_id:
            raise RegistryValidationError(f"M200/2024 unique {row.casilla_id!r} lacks canonical target-map ownership")
        field = fields.get(semantic_anchor_key(entry.anchor))
        if field is None or TARGET_SOURCE_REF not in entry.source_refs or tuple(entry.legal_refs) != row.legal_refs:
            raise RegistryValidationError(f"M200/2024 unique {row.casilla_id!r} target-map provenance drifted")
        label = str(field.normalized_description)
        if row.official_column.casefold() not in label.casefold():
            raise RegistryValidationError(f"M200/2024 unique {row.casilla_id!r} official column distinction drifted")
        verified.append(Adjudication(row.casilla_id, row.export_field_id, row.profile, row.official_column, sha256_hex(label.encode("utf-8")), row.section, row.semantic_role, row.legal_refs, row.semantic_payload_sha256))
    return tuple(verified)


def _require_legal_coverage(rows: tuple[Adjudication, ...]) -> None:
    legal = {key: value for path in bundled_path("registry", "aeat", "legal").glob("*.toml") for key, value in load_catalogue_file(path).legal.items()}
    for row in rows:
        for reference in row.legal_refs:
            provision = legal.get(reference)
            if provision is None or str(provision.id) != reference:
                raise RegistryValidationError(f"M200/2024 unique {row.casilla_id!r} has unresolved legal authority")
            start, end = governed_period_span(provision)
            if start > TARGET_WINDOW[0] or end is not None and end < TARGET_WINDOW[1]:
                raise RegistryValidationError(f"M200/2024 unique {row.casilla_id!r} legal authority misses 2024")


def _require_withheld_01403() -> None:
    candidate = next((row for row in audit_bundled_restorations() if row.casilla_id == "01403"), None)
    if candidate is None or candidate.cross_revision_status == "unique_non_authoritative" or "contradict" not in candidate.reason:
        raise RegistryValidationError("M200/2024 casilla 01403 must remain outside the S13 receipt")


def _literal(value: str) -> str:
    if "'" in value:
        raise RegistryValidationError("M200/2024 unique declaration cannot render an apostrophe")
    return f"'{value}'"


def _array(values: tuple[str, ...]) -> str:
    return "[\n" + "".join(f"    {_literal(value)},\n" for value in values) + "]"
