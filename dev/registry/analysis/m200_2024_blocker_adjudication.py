"""Emit target-only adjudication evidence for the M200/2024 S14/S15 cohorts.

The output is deliberately non-authoritative and has no apply path.  It joins
the current target-first blocker census to the pinned 2024 record design and
the bundled official 2024 AEAT manual.  Cross-revision payloads are never used
as authority: their status selects the finite cohort, nothing more.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.loader import load_catalogue_file

from ..pipeline._record_design_ir import intermediate_anchor_key, load_record_design_intermediate
from ..pipeline._semantic_map import semantic_anchor_key
from ..pipeline._semantic_map_loader import load_semantic_map
from .m200_restored_semantic_audit import audit_bundled_restorations

TARGET_SOURCE_REF = "aeat-dr-200-2024"
TARGET_SOURCE_SHA256 = "ed4df89a451abc2184bc60a1d13ff53a3d38e9a6201698fb635cf0b8ee455218"
MANUAL_SOURCE_REF = "aeat-modelo-200-manual-2024"
MANUAL_SOURCE_SHA256 = "ad02f914246632dcd7ab30f3e7280daf3501be6ee3938237e2ebfe7328ff8179"
BLOCKER_STATUSES = frozenset({"conflicting_non_authoritative", "no_applicable_match"})


def build_worklist() -> dict[str, object]:
    """Build the closed 119-member worklist from target-year evidence only."""
    registry_root = bundled_path("registry", "aeat")
    catalogues = load_catalogue_file(registry_root / "legal" / "is.toml")
    source = catalogues.sources[TARGET_SOURCE_REF]
    manual_source = catalogues.sources[MANUAL_SOURCE_REF]
    if source.sha256 != TARGET_SOURCE_SHA256 or manual_source.sha256 != MANUAL_SOURCE_SHA256:
        raise ValueError("pinned Modelo 200/2024 official source identity drifted")

    design = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=TARGET_SOURCE_REF,
        filing_year=2024,
        design_epoch="2024",
    )
    semantic_map = load_semantic_map(Path(__file__).parents[1] / "mappings" / "modelo_200" / "2024")
    fields = {intermediate_anchor_key(field): field for sheet in design.sheets for field in sheet.fields}
    entries = {str(entry.export_field_id): entry for entry in semantic_map.entries}
    manual_units = _manual_units(Path(manual_source.corpus_path))

    rows: list[dict[str, object]] = []
    for audit in audit_bundled_restorations():
        if audit.cross_revision_status not in BLOCKER_STATUSES:
            continue
        entry = entries[audit.export_field_id]
        field = fields[semantic_anchor_key(entry.anchor)]
        family, column = _family_and_column(field.normalized_description, field.record_identity)
        manual_pages = _manual_pages(manual_units, family, field.record_identity)
        legal_locator = _legal_locator(field.normalized_description, family, field.record_identity, manual_units)
        refusal = None
        if not manual_pages:
            refusal = "bundled official 2024 manual has no applicable family definition"
        rows.append(
            {
                "casilla_id": audit.casilla_id,
                "export_field_id": audit.export_field_id,
                "source_cohort": audit.cross_revision_status,
                "adjudication": "unresolved_refusal" if refusal else "safely_compilable_from_target_2024",
                "refusal": refusal,
                "official_family": family,
                "official_column_role": column,
                "official_description": field.normalized_description,
                "record_design_locator": {
                    "source_ref": TARGET_SOURCE_REF,
                    "sha256": TARGET_SOURCE_SHA256,
                    "sheet": field.sheet,
                    "record_identity": field.record_identity,
                    "source_row": field.source_row,
                    "source_cell": field.source_cell,
                    "ordinal": field.ordinal,
                    "offset": field.offset,
                    "length": field.length,
                    "aeat_type": field.aeat_type,
                },
                "manual_locator": {
                    "source_ref": MANUAL_SOURCE_REF,
                    "sha256": MANUAL_SOURCE_SHA256,
                    "pages": manual_pages,
                },
                "legal_locator": legal_locator,
            }
        )
    rows.sort(key=lambda item: str(item["export_field_id"]))
    if len(rows) != 119:
        raise ValueError(f"S14/S15 blocker cohort drifted: expected 119 members, found {len(rows)}")
    counts = {
        "conflicting_non_authoritative": sum(row["source_cohort"] == "conflicting_non_authoritative" for row in rows),
        "no_applicable_match": sum(row["source_cohort"] == "no_applicable_match" for row in rows),
        "safely_compilable": sum(row["adjudication"] == "safely_compilable_from_target_2024" for row in rows),
        "unresolved_refusal": sum(row["adjudication"] == "unresolved_refusal" for row in rows),
    }
    if counts["conflicting_non_authoritative"] != 17 or counts["no_applicable_match"] != 102:
        raise ValueError(f"S14/S15 source partition drifted: {counts!r}")
    return {
        "schema_version": 1,
        "authority_status": "proposal_only_non_authoritative",
        "modelo": "200",
        "revision": "2024",
        "policy": {
            "target_first": True,
            "sibling_semantics_used_as_authority": False,
            "canonical_write_path": False,
            "geometry_source": "parsed_pinned_official_record_design",
        },
        "counts": counts,
        "member": rows,
    }


def _manual_units(corpus_path: Path) -> tuple[dict[str, object], ...]:
    extracted = bundled_path(str(corpus_path) + ".extracted.json")
    payload = json.loads(extracted.read_text(encoding="utf-8"))
    if payload.get("source_sha256") != MANUAL_SOURCE_SHA256:
        raise ValueError("official manual extraction is not bound to the pinned PDF")
    return tuple(payload["units"])


def _family_and_column(description: str, segment: str) -> tuple[str, str]:
    parts = tuple(part.strip() for part in description.replace("\n", " ").split(" - "))
    last = re.sub(r"\s*\[[0-9]{5}\]\s*$", "", parts[-1]).strip()
    column_markers = (
        "Deducción pendiente/generada",
        "Aplicado en esta liquidación",
        "Pendiente de aplicación en periodos futuros",
        "Pendiente aplicación a principio del período",
        "Pendiente aplicación períodos futuros",
        "Importe de la bonificación",
        "Importe de la deducción",
        "Aumentos",
    )
    column = next((marker for marker in column_markers if _fold(marker) in _fold(last)), last)
    family_parts = parts[:-1]
    if segment == "DP200024":
        family_parts = parts[3:-1]
    elif segment in {"DP200018", "DP200018C", "DP200020", "DP200020B", "DP200022", "DP200022B"}:
        family_parts = parts[1:-1]
    family = " - ".join(family_parts).strip() or parts[0]
    family = re.sub(r"^2024:?\s*", "", family, flags=re.IGNORECASE)
    return family, column


def _manual_pages(units: Iterable[dict[str, object]], family: str, segment: str) -> list[int]:
    needles = _manual_needles(family, segment)
    pages = []
    for unit in units:
        text = _fold(str(unit["text"]))
        if any(_fold(needle) in text for needle in needles):
            match = re.fullmatch(r"Pag\. ([0-9]+)", str(unit["section"]))
            if match is not None:
                pages.append(int(match.group(1)))
    pages = sorted(set(pages))
    if segment == "DP200016B":
        return [page for page in pages if 689 <= page <= 717]
    if segment == "DP200018":
        return [page for page in pages if 457 <= page <= 466]
    if segment == "DP200018C":
        return [page for page in pages if 483 <= page <= 485]
    if segment == "DP200020B":
        limits = (359, 361) if "nivelaci" in _fold(family) else (352, 355)
        return [page for page in pages if limits[0] <= page <= limits[1]]
    if segment == "DP200022":
        return [page for page in pages if 719 <= page <= 745]
    if segment == "DP200022B":
        return [page for page in pages if 773 <= page <= 789]
    if segment == "DP200024":
        return [page for page in pages if 579 <= page <= 587]
    return pages


def _manual_needles(family: str, segment: str) -> tuple[str, ...]:
    if segment == "DP200012":
        return (re.sub(r"^.*Corrección por\s+", "", family, flags=re.IGNORECASE),)
    if segment == "DP200016B":
        return ("Deducción por inversiones en Canarias",)
    if segment == "DP200018C":
        return ("Subtotal donaciones 2014", "actividades prioritarias de mecenazgo")
    if segment == "DP200020":
        return ("Pendiente de adición por límite beneficio operativo no aplicado",)
    if segment == "DP200020B":
        return ("Reserva de nivelación",) if "nivelaci" in _fold(family) else ("Reserva de capitalización",)
    if segment == "DP200022":
        return ("Reserva para inversiones en Canarias",)
    if segment == "DP200022B":
        return ("Reserva para inversiones en las Illes Balears", "Reserva para inversiones en las Islas Baleares")
    if segment == "DP200024":
        return ("Régimen especial de las agrupaciones de interés económico",)
    # Programme names include an authoring year prefix in the record design.
    programme = re.sub(r"^[0-9]{4}\s+", "", family)
    programme = re.sub(r"\s+\([^()]{1,5}\)\s*$", "", programme)
    programme = re.sub(r"\s+2022-2024\s*$", "", programme)
    programme = re.sub(r"^[0-9]+\.?ª\s+", "", programme)
    return (programme,)


def _legal_locator(
    description: str,
    family: str,
    segment: str,
    units: Iterable[dict[str, object]],
) -> dict[str, object]:
    explicit = re.findall(r"\(([^)]*(?:art\.|Ley|DA\s)[^)]*)\)", description, flags=re.IGNORECASE)
    provision = explicit[0] if explicit else _family_provision(family, segment)
    if segment == "DP200012":
        provision = "artículo 1.7 Ley 38/2022" if "energ" in _fold(family) else "artículo 2.6 Ley 38/2022"
    elif segment == "DP200018C":
        provision = (
            "artículo 22 Ley 49/2002" if "actividades prioritarias" in _fold(family) else "artículo 20 Ley 49/2002"
        )
    elif segment == "DP200024":
        provision = _dp200024_provision(family)
    if segment == "DP200018":
        needle = _manual_needles(family, segment)[0]
        for unit in units:
            text = str(unit["text"]).replace("\n", " ")
            position = _fold(text).find(_fold(needle))
            if position < 0:
                continue
            window = text[position : position + 260]
            match = re.search(r"\((disposición adicional [^)]+)\)", window, flags=re.IGNORECASE)
            if match is not None:
                provision = match.group(1)
                break
    return {
        "provision": provision,
        "basis": "official_2024_manual_and_record_design",
    }


def _family_provision(family: str, segment: str) -> str:
    if segment == "DP200016B":
        return "artículo 94 Ley 20/1991; régimen de deducción por inversiones en Canarias"
    if segment == "DP200018":
        return "artículo 27.3 Ley 49/2002; specific programme provision not extracted"
    if segment == "DP200018C":
        return "artículos 20 y 22 Ley 49/2002"
    if segment == "DP200020":
        return "artículo 16.2 LIS"
    if segment == "DP200020B" and "nivelaci" in _fold(family):
        return "artículo 105 LIS"
    if segment == "DP200020B":
        return "artículo 25 LIS"
    if segment == "DP200022":
        return "artículo 27 Ley 19/1994"
    if segment == "DP200022B":
        return "disposición adicional 70.Cuatro Ley 31/2022"
    if segment == "DP200024":
        return "artículos 43 a 47 LIS; exact deduction or bonus named by the official field"
    return "provision named by the official field"


def _dp200024_provision(family: str) -> str:
    folded = _fold(family)
    provisions = (
        ("ventas bienes corporales", "artículo 26 Ley 19/1994"),
        ("illes balears", "disposición adicional 70.Cinco Ley 31/2022"),
        ("sociedades cooperativas", "artículo 34 Ley 20/1990"),
        ("arrendamiento de viviendas", "artículos 48 y 49 LIS"),
        ("empresas navieras en canarias", "artículo 76 Ley 19/1994"),
        ("investigacion y desarrollo (ct)", "artículo 35.1 LIS"),
        ("innovacion tecnologica (it)", "artículo 35.2 LIS"),
        ("cinematograficas espanolas (pc)", "artículo 36.1 LIS"),
        (
            "artes escenicas y musicales en canarias",
            "artículo 36.3 LIS y disposición adicional 14 Ley 19/1994",
        ),
        ("espectaculos en vivo", "artículo 36.3 LIS"),
        ("trabajadores con discapacidad", "artículo 38 LIS"),
        ("prevision social empresarial", "artículo 38 ter LIS"),
        ("inversion de beneficios", "disposición transitoria 24 LIS"),
        ("sociedades forestales", "disposiciones adicionales 5 y 13 Ley 43/2003"),
        ("africa occidental", "artículo 27 bis Ley 19/1994"),
        ("acontecimientos de excepcional interes publico", "artículo 27.3 Ley 49/2002"),
        ("inversiones en canarias", "artículo 94 Ley 20/1991"),
        ("cinematograficas extranjeras en canarias", "artículo 36.2 LIS y disposición adicional 14 Ley 19/1994"),
        ("cinematograficas extranjeras", "artículo 36.2 LIS"),
        ("autoridades portuarias", "artículo 38 bis LIS"),
        ("donaciones a entidades sin fines de lucro", "artículo 20 Ley 49/2002"),
        ("investigacion y desarrollo en canarias", "artículo 35.1 LIS y artículo 94 Ley 20/1991"),
        ("innovacion tecnologica en canarias", "artículo 35.2 LIS y artículo 94 Ley 20/1991"),
        ("cinematograficas espanolas en canarias", "artículo 36.1 LIS y disposición adicional 14 Ley 19/1994"),
    )
    for needle, provision in provisions:
        if needle in folded:
            return provision
    if "normativa foral" in folded:
        return "artículo 43 LIS; cuantía determinada por la normativa foral aplicable"
    if "resto de bonificaciones" in folded or "otras deducciones" in folded:
        return "artículo 43 LIS; categoría residual sin una única disposición subyacente"
    return "artículos 43 a 47 LIS"


def _fold(value: str) -> str:
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(character)
    )
    return " ".join(folded.split())


def main() -> int:
    """Write deterministic UTF-8 JSON to stdout without mutating authority."""
    json.dump(build_worklist(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
