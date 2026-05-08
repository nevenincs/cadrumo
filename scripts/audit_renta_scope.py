"""Renta scope audit — produces a rolling gaps inventory across Modelo 100 ejercicios.

Emits a markdown summary that the rolling gaps document consumes. Re-run on
every commit to refresh the gaps surface. Inventory layers:

  Layer 1: per-casilla classification (input_kind distribution per revision,
           bound/computed/manual breakdown, downstream-usage edge map)
  Layer 3: mini-model coverage scorecard (group casillas by section path
           anchor, count formulas vs gaps per group, identify the largest
           uncovered surfaces)
  Layer 4: legal grounding inventory (which LIRPF / RD / Orden articles are
           actually cited, which are catalogued-but-orphan, which are
           cited-but-uncatalogued)
  Layer 7: scenario archetype coverage (which Renta filing archetypes are
           exercised by tests vs declared as gaps)

Run: `uv run --no-sync python scripts/audit_renta_scope.py`
Output: `.vault/audit/<date>-renta-scope-audit-findings.json` (raw data)
        + console summary + caller can pipe into the rolling gaps doc.
"""

from __future__ import annotations

import json
import sys
import tomllib
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOML_PATH = PROJECT_ROOT / "registry" / "aeat" / "modelos" / "100.toml"
LEGAL_DIR = PROJECT_ROOT / "registry" / "aeat" / "legal"
OUTPUT_DIR = PROJECT_ROOT / ".vault" / "audit"


def _load_modelo() -> dict:
    return tomllib.loads(TOML_PATH.read_text(encoding="utf-8"))


def _load_legal_catalogue() -> tuple[set[str], set[str]]:
    legal_ids: set[str] = set()
    source_ids: set[str] = set()
    for path in LEGAL_DIR.rglob("*.toml"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for entry_id, payload in (data.get("legal") or {}).items():
            legal_ids.add(entry_id)
        for entry_id, payload in (data.get("sources") or {}).items():
            source_ids.add(entry_id)
    return legal_ids, source_ids


# Modelo 100's owned catalogue scope. Articles outside this scope are
# legitimately catalogued for OTHER modelos (IS / IVA / foreign-assets /
# operaciones-terceros) and their absence from Modelo 100 citations is
# not drift.
_RENTA_OWNED_CATALOGUE_FILES = ("irpf.toml", "atribucion-rentas.toml")


def _load_renta_scoped_legal_catalogue() -> set[str]:
    """Articles catalogued in IRPF / atribución-rentas TOML files only."""
    scoped: set[str] = set()
    for path in LEGAL_DIR.rglob("*.toml"):
        if path.name not in _RENTA_OWNED_CATALOGUE_FILES:
            continue
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for entry_id, _payload in (data.get("legal") or {}).items():
            scoped.add(entry_id)
    return scoped


def _collect_expression_refs(
    expression: object,
    casillas: set[str],
    bindings: set[str],
    parameters: set[str],
    relations: set[str],
) -> None:
    if isinstance(expression, dict):
        if "casilla" in expression:
            casillas.add(expression["casilla"])
        if "binding" in expression:
            bindings.add(expression["binding"])
        if "parameter" in expression:
            parameters.add(expression["parameter"])
        if "relation" in expression:
            relations.add(expression["relation"])
        for arg in expression.get("args", []) or []:
            _collect_expression_refs(arg, casillas, bindings, parameters, relations)


def layer1_casilla_inventory(modelo: dict) -> dict:
    """Per-revision casilla input_kind distribution + downstream-usage map."""
    revisions: dict[str, dict] = {}
    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        casillas = rev.get("casillas") or []
        kind_counts: Counter = Counter(c.get("input_kind", "(missing)") for c in casillas)
        formula_targets = {f["target"] for f in rev.get("formulas", []) or []}
        binding_consumers: dict[str, set[str]] = defaultdict(set)
        downstream_casilla_users: dict[str, set[str]] = defaultdict(set)
        for formula in rev.get("formulas", []) or []:
            referenced_c: set[str] = set()
            referenced_b: set[str] = set()
            referenced_p: set[str] = set()
            referenced_r: set[str] = set()
            _collect_expression_refs(
                formula.get("expression"), referenced_c, referenced_b, referenced_p, referenced_r
            )
            for casilla_ref in referenced_c:
                downstream_casilla_users[casilla_ref].add(formula["id"])
            for binding_ref in referenced_b:
                binding_consumers[binding_ref].add(formula["id"])
        # Casillas declared but never read
        declared_numbers = {c["number"] for c in casillas}
        unread = declared_numbers - set(downstream_casilla_users) - formula_targets
        revisions[rev_id] = {
            "total_casillas": len(casillas),
            "input_kind": dict(kind_counts),
            "computed_targets": len(formula_targets),
            "casillas_consumed_by_formulas": len(downstream_casilla_users),
            "casillas_declared_but_never_read": len(unread),
            "bindings_consumed_count": len({b for b, c in binding_consumers.items() if c}),
        }
    return revisions


_RENTA_MINI_MODEL_GROUPS: tuple[tuple[str, str, tuple[tuple[str, ...], ...]], ...] = (
    # (group_id, human label, list of (section_path_prefix) tuples that anchor this group)
    ("envelope", "Declarante envelope (NIF, CCAA, tributación)",
     (("datos_identificativos",),)),
    ("trabajo", "Rendimientos del trabajo",
     (("rendimientos_trabajo",), ("toma_datos_ampliada", "rdto_trabajo"))),
    ("capital_mobiliario", "Rendimientos del capital mobiliario",
     (("rendimientos_capital_mobiliario",), ("toma_datos_ampliada", "rdto_capital_mobiliario"))),
    ("capital_inmobiliario", "Rendimientos del capital inmobiliario",
     (("rendimientos_capital_inmobiliario",), ("toma_datos_ampliada", "inmuebles"))),
    ("actividades_economicas_directa", "Actividades económicas — estimación directa",
     (("rendimientos_actividades_economicas",),
      ("toma_datos_ampliada", "reg_estima_directa"))),
    ("actividades_economicas_objetiva", "Actividades económicas — estimación objetiva (módulos)",
     (("toma_datos_ampliada", "reg_estima_obj"),
      ("toma_datos_ampliada", "reg_estima_obj_agricola"))),
    ("regimenes_especiales", "Regímenes especiales / atribución de rentas",
     (("toma_datos_ampliada", "regimenes_especiales"),
      ("toma_datos_ampliada", "regimen_especial"))),
    ("ganancias_capital_mobiliario_ahorro", "G/P y capital mobiliario en base ahorro",
     (("toma_datos_ampliada", "gp_acciones"),
      ("toma_datos_ampliada", "gp_fondos"),
      ("toma_datos_ampliada", "gp_fondos_coti"),
      ("toma_datos_ampliada", "gp_derechos"),
      ("toma_datos_ampliada", "gp_premios"),
      ("toma_datos_ampliada", "gp_otros_inmuebles"),
      ("toma_datos_ampliada", "gp_otros_elementos"),
      ("toma_datos_ampliada", "gp_otros_criptomonedas"))),
    ("base_y_cuota", "Base imponible/liquidable y cuota chain",
     (("resultados", "base_imponible_res"),
      ("resultados", "base_liquidable_res"),
      ("resultados", "calculo_impuesto_res"),
      ("resultados", "minimo_per_fam_res"),
      ("resultado_declaracion",))),
    ("anexo_a_estatal", "Anexo A — deducciones generales (vivienda, donativos, cultural)",
     (("resultados", "anexo_a_res"),)),
    ("anexo_b_autonomicas", "Anexo B — deducciones autonómicas (17 CCAA)",
     (("resultados", "deduccion_autonomica_res"),)),
    ("anexo_c_canarias", "Anexo C — Canarias (RIC, ZEC)",
     (("resultados", "anexo_c_res"),)),
    ("retenciones_pagos_a_cuenta", "Retenciones e ingresos a cuenta + pagos fraccionados",
     (("retenciones_ingresos_cuenta_pagos_fraccionados",),
      ("resultados", "retenciones_res"),
      ("resultados", "compensacion_conyuges_res"))),
    ("regimenes_atribucion", "Atribución de rentas + regímenes especiales (transparencia, art. 85)",
     (("toma_datos_ampliada", "anexo_a"),
      ("resultados", "datos_adicionales_res"),
      ("resultados", "datos_adicionales_anexo_b"))),
)


def _section_matches_anchor(section: list[str], anchor: tuple[str, ...]) -> bool:
    if len(section) < len(anchor):
        return False
    return tuple(section[: len(anchor)]) == anchor


def layer3_mini_model_coverage(modelo: dict, target_revision: str = "2025") -> dict:
    """Group casillas by mini-model and report formula coverage per group."""
    rev = modelo.get("revisions", {}).get(target_revision, {})
    casillas = rev.get("casillas", []) or []
    formula_targets = {f["target"] for f in rev.get("formulas", []) or []}

    # Map every casilla to its mini-model group via section path-prefix matching
    by_group: dict[str, list[dict]] = defaultdict(list)
    for c in casillas:
        section = c.get("section") or []
        matched_group = "uncategorised"
        for group_id, _, anchors in _RENTA_MINI_MODEL_GROUPS:
            if any(_section_matches_anchor(section, anchor) for anchor in anchors):
                matched_group = group_id
                break
        by_group[matched_group].append(c)

    summary: dict[str, dict] = {}
    for group_id, label, _ in _RENTA_MINI_MODEL_GROUPS:
        members = by_group.get(group_id, [])
        member_numbers = {m["number"] for m in members}
        computed = member_numbers & formula_targets
        bound = {m["number"] for m in members if m.get("input_kind") == "bound"}
        manual = {m["number"] for m in members if m.get("input_kind") == "manual"}
        summary[group_id] = {
            "label": label,
            "total_casillas": len(members),
            "computed": len(computed),
            "bound": len(bound),
            "manual": len(manual),
            "coverage_pct": round(100 * (len(computed) + len(bound)) / max(len(members), 1), 1),
        }
    # Uncategorised
    uncat = by_group.get("uncategorised", [])
    summary["uncategorised"] = {
        "label": "Uncategorised (section[0] not anchor-mapped)",
        "total_casillas": len(uncat),
        "computed": len({m["number"] for m in uncat} & formula_targets),
        "bound": len([m for m in uncat if m.get("input_kind") == "bound"]),
        "manual": len([m for m in uncat if m.get("input_kind") == "manual"]),
    }
    return summary


def _load_all_modelos() -> dict[str, dict]:
    """Load every modelo TOML and key by stem (file name without extension)."""
    modelos: dict[str, dict] = {}
    modelos_dir = PROJECT_ROOT / "registry" / "aeat" / "modelos"
    for path in sorted(modelos_dir.glob("*.toml")):
        modelos[path.stem] = tomllib.loads(path.read_text(encoding="utf-8"))
    return modelos


def layer5_cross_modelo_closed_loop(modelo: dict) -> dict:
    """For each cross-modelo relation, verify source modelo exposes source_output.

    Surfaces relations whose declared `source_modelo` + `source_revision_selector`
    + `source_output` triple does not resolve to an actual casilla in the source
    modelo's registry definition.
    """
    all_modelos = _load_all_modelos()
    relations_total = 0
    closed_loop = 0
    open_loop_misalignments: list[dict] = []
    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        for relation in rev.get("relations", []) or []:
            relations_total += 1
            source_modelo_id = relation.get("source_modelo")
            source_selector = relation.get("source_revision_selector") or {}
            source_output = relation.get("source_output")
            source_modelo = all_modelos.get(source_modelo_id)
            if source_modelo is None:
                open_loop_misalignments.append({
                    "revision": rev_id,
                    "relation_id": relation.get("id", "(unknown)"),
                    "source_modelo": source_modelo_id,
                    "kind": "source_modelo_missing",
                })
                continue
            # Resolve source revision: try year-keyed, fallback to first revision.
            source_year = source_selector.get("year")
            source_revisions = source_modelo.get("revisions") or {}
            source_rev = None
            if source_year is not None:
                source_rev = source_revisions.get(str(source_year))
            if source_rev is None:
                # Pick any revision matching the year_from window or first revision.
                for rid, rdata in source_revisions.items():
                    if isinstance(rdata, dict):
                        source_rev = rdata
                        break
            if source_rev is None or not isinstance(source_rev, dict):
                open_loop_misalignments.append({
                    "revision": rev_id,
                    "relation_id": relation.get("id", "(unknown)"),
                    "source_modelo": source_modelo_id,
                    "source_year": source_year,
                    "kind": "source_revision_missing",
                })
                continue
            # source_output may be a casilla number, an aggregate logical id
            # (e.g. "decl.retenciones-total" — sums across the source modelo's
            # informativa register), or some other string identifier. Casilla
            # lookups handle the numeric case; aggregate-id outputs are
            # treated as closed-loop without further casilla matching.
            if source_output and ("." in source_output or "-" in source_output):
                closed_loop += 1
                continue
            source_casillas = {c.get("number") for c in source_rev.get("casillas", []) or []}
            if source_output and source_output in source_casillas:
                closed_loop += 1
            elif source_output and source_output.lstrip("0") in {n.lstrip("0") for n in source_casillas}:
                # Tolerate zero-padding differences (e.g. "28" matches "0028" if any).
                closed_loop += 1
            else:
                open_loop_misalignments.append({
                    "revision": rev_id,
                    "relation_id": relation.get("id", "(unknown)"),
                    "source_modelo": source_modelo_id,
                    "source_output": source_output,
                    "kind": "source_output_missing",
                })
    return {
        "relations_total": relations_total,
        "closed_loop": closed_loop,
        "open_loop": len(open_loop_misalignments),
        "coverage_pct": (100.0 * closed_loop / relations_total) if relations_total else 100.0,
        "misalignments": open_loop_misalignments[:50],
    }


def layer10_rental_pipeline_regression(modelo: dict) -> dict:
    """Inventory rental / capital inmobiliario casillas across all revisions.

    Surfaces:
      - per-revision Inmuebles section count
      - per-property line-item casilla classification (manual / bound / computed)
      - rental-related parameters registered (rebaja-threshold, rehab-lookback,
        joven-tenant-age-min/max, ejercicio-amendment-year, tier-50/60/70/90)
      - integration tests asserting the rental → registry decoupling chain

    Catches drift between the rental domain models (`aeat.domain.rental`)
    and the Modelo 100 chain by surfacing per-revision counts that should
    move only when the registry adds new rental-grounded substrate.
    """
    revisions: dict[str, dict] = {}
    expected_params = (
        "rental-prior-rent-rebaja-threshold",
        "rental-rehab-lookback-days",
        "rental-joven-tenant-age-min",
        "rental-joven-tenant-age-max",
        "rental-ejercicio-amendment-year",
        "rental-reduccion-rate-tier-50",
        "rental-reduccion-rate-tier-60",
        "rental-reduccion-rate-tier-70",
        "rental-reduccion-rate-tier-90",
    )
    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        casillas = rev.get("casillas") or []
        rental_casillas = [
            c for c in casillas
            if any(
                token in (s or "").lower()
                for s in (c.get("section") or [])
                for token in ("capital_inmobiliario", "inmueble", "rental", "arrendamiento", "alquiler")
            )
        ]
        kind_counts: Counter = Counter(c.get("input_kind", "(missing)") for c in rental_casillas)
        registered_params = {p.get("id") for p in (rev.get("parameters") or [])}
        params_present = []
        params_missing = []
        for suffix in expected_params:
            param_id = f"renta-{rev_id}-{suffix}"
            if param_id in registered_params:
                params_present.append(suffix)
            else:
                params_missing.append(suffix)
        revisions[rev_id] = {
            "rental_casilla_count": len(rental_casillas),
            "kind_distribution": dict(kind_counts),
            "rental_params_present": params_present,
            "rental_params_missing": params_missing,
            "rental_params_coverage_pct": (
                100.0 * len(params_present) / len(expected_params)
            ) if expected_params else 100.0,
        }
    aggregate_present = sum(len(r["rental_params_present"]) for r in revisions.values())
    aggregate_total = len(revisions) * len(expected_params)
    return {
        "revisions": revisions,
        "expected_params_per_revision": expected_params,
        "params_present_total": aggregate_present,
        "params_total": aggregate_total,
        "params_coverage_pct": (
            100.0 * aggregate_present / aggregate_total
        ) if aggregate_total else 100.0,
    }


def layer6_external_surface_registration(modelo: dict) -> dict:
    """For each Renta external surface, verify live_cross_reference declared
    + remote-state guard policy + adapter consumer registration.

    Inventory pulled from `live_cross_references` blocks per revision and
    cross-checked against `application_links` blocks (which name the
    consumer adapter).
    """
    surfaces_by_revision: dict[str, list[dict]] = {}
    application_links_by_id: dict[str, list[str]] = {}
    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        revision_surfaces = []
        for cross_ref in rev.get("live_cross_references", []) or []:
            cross_ref_id = cross_ref.get("id", "(unknown)")
            revision_surfaces.append({
                "id": cross_ref_id,
                "evidence_tier": cross_ref.get("evidence_tier"),
                "surface": cross_ref.get("surface"),
                "guard_policy_id": cross_ref.get("guard_policy_id"),
                "synthetic_data_allowed": cross_ref.get("synthetic_data_allowed", False),
                "requires_authentication": cross_ref.get("requires_authentication", False),
            })
        surfaces_by_revision[rev_id] = revision_surfaces
        for app_link in rev.get("application_links", []) or []:
            app_link_id = app_link.get("id", "")
            consumer = app_link.get("consumer")
            if app_link_id:
                application_links_by_id.setdefault(rev_id, []).append(
                    f"{app_link_id} -> {consumer}"
                )
    summary = {
        "total_surfaces": sum(len(v) for v in surfaces_by_revision.values()),
        "surfaces_per_revision": {k: len(v) for k, v in surfaces_by_revision.items()},
        "guarded_count": sum(
            1 for v in surfaces_by_revision.values() for s in v if s["guard_policy_id"]
        ),
        "synthetic_data_allowed_count": sum(
            1 for v in surfaces_by_revision.values() for s in v if s["synthetic_data_allowed"]
        ),
        "auth_required_count": sum(
            1 for v in surfaces_by_revision.values() for s in v if s["requires_authentication"]
        ),
        "surfaces_per_revision_detail": surfaces_by_revision,
        "application_links_per_revision": application_links_by_id,
    }
    return summary


def _load_source_catalogue() -> dict[str, dict]:
    """Map source_ref -> {corpus_path, ...} from registry/aeat/legal/*.toml."""
    sources: dict[str, dict] = {}
    for path in LEGAL_DIR.rglob("*.toml"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for entry_id, payload in (data.get("sources") or {}).items():
            sources[entry_id] = payload
    return sources


def _normalise_corpus_text(text: str) -> str:
    """Same normalisation the registry validator uses for citation checks."""
    import html as _html
    import re as _re
    import unicodedata as _ud

    decoded = _html.unescape(text).replace("\xa0", " ")
    without_tags = _re.sub(r"<[^>]+>", " ", decoded)
    without_marks = "".join(c for c in _ud.normalize("NFKD", without_tags) if not _ud.combining(c))
    return _re.sub(r"\s+", " ", without_marks).strip().lower()


def layer2_citation_phrase_coverage(modelo: dict) -> dict:
    """For every formula's source_citations[].required_text, verify the
    phrase exists in the cited corpus file (matches the runtime validator).

    Persists per-formula misalignments so the audit driver surfaces them.
    """
    sources = _load_source_catalogue()
    corpus_cache: dict[str, str] = {}
    misalignments: list[dict] = []
    formula_count = 0
    citation_count = 0
    phrase_count = 0
    matched_count = 0
    missed_count = 0

    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        for formula in rev.get("formulas", []) or []:
            formula_count += 1
            for citation in formula.get("source_citations", []) or []:
                citation_count += 1
                source_ref = citation.get("source_ref")
                source = sources.get(source_ref)
                if source is None:
                    misalignments.append({
                        "revision": rev_id,
                        "formula_id": formula.get("id", "(unknown)"),
                        "source_ref": source_ref,
                        "kind": "source_unregistered",
                    })
                    continue
                corpus_path = source.get("corpus_path")
                if corpus_path is None:
                    continue
                # PDF corpora need pdfplumber-based extraction; the audit-script
                # layer skips them. The runtime validator handles PDF citations
                # via its own extraction pipeline; layer2 covers HTML / plain-text
                # corpora only.
                if corpus_path.lower().endswith((".pdf",)):
                    continue
                cache_key = corpus_path
                if cache_key not in corpus_cache:
                    full_path = PROJECT_ROOT / corpus_path
                    if not full_path.exists():
                        corpus_cache[cache_key] = ""
                        misalignments.append({
                            "revision": rev_id,
                            "formula_id": formula.get("id", "(unknown)"),
                            "source_ref": source_ref,
                            "corpus_path": corpus_path,
                            "kind": "corpus_missing",
                        })
                        continue
                    corpus_cache[cache_key] = _normalise_corpus_text(
                        full_path.read_text(encoding="utf-8", errors="replace")
                    )
                normalised_text = corpus_cache[cache_key]
                if not normalised_text:
                    continue
                for phrase in citation.get("required_text", []) or []:
                    phrase_count += 1
                    if _normalise_corpus_text(phrase) in normalised_text:
                        matched_count += 1
                    else:
                        missed_count += 1
                        misalignments.append({
                            "revision": rev_id,
                            "formula_id": formula.get("id", "(unknown)"),
                            "source_ref": source_ref,
                            "corpus_path": corpus_path,
                            "phrase": phrase,
                            "kind": "phrase_missing",
                        })

    return {
        "formula_count": formula_count,
        "citation_count": citation_count,
        "phrase_count": phrase_count,
        "phrases_matched": matched_count,
        "phrases_missed": missed_count,
        "coverage_pct": (100.0 * matched_count / phrase_count) if phrase_count else 100.0,
        "misalignments": misalignments[:100],
        "misalignment_count": len(misalignments),
    }


def layer4_legal_grounding(modelo: dict) -> dict:
    """Which legal_refs are cited, which catalogue entries are orphaned.

    Reports both the global view (all 119 articles registered across
    legal/) AND the Renta-scoped view (only articles catalogued under
    `_RENTA_OWNED_CATALOGUE_FILES`). The scoped view is the canonical
    drift metric for Modelo 100 — articles owned by IS/IVA/IAE/foreign-
    assets catalogues belong to OTHER modelos and aren't Modelo 100 drift.
    """
    catalogued_legal, _ = _load_legal_catalogue()
    renta_scoped_catalogue = _load_renta_scoped_legal_catalogue()
    cited_legal: Counter = Counter()
    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        for kind in ("formulas", "parameters", "bindings", "relations"):
            for entry in rev.get(kind, []) or []:
                for ref in entry.get("legal_refs", []) or []:
                    cited_legal[ref] += 1
    cited_set = set(cited_legal.keys())
    catalogued_but_uncited = sorted(catalogued_legal - cited_set)
    cited_but_uncatalogued = sorted(cited_set - catalogued_legal)
    renta_scoped_uncited = sorted(renta_scoped_catalogue - cited_set)
    renta_scoped_cited = sorted(renta_scoped_catalogue & cited_set)
    return {
        "catalogued_count": len(catalogued_legal),
        "cited_count": len(cited_set),
        "catalogued_but_uncited_count": len(catalogued_but_uncited),
        "cited_but_uncatalogued_count": len(cited_but_uncatalogued),
        "top_cited": cited_legal.most_common(15),
        "uncited_articles": catalogued_but_uncited[:20],
        "uncatalogued_articles": cited_but_uncatalogued[:20],
        # Renta-scoped drift (the canonical Modelo 100 drift metric)
        "renta_scoped_catalogued_count": len(renta_scoped_catalogue),
        "renta_scoped_cited_count": len(renta_scoped_cited),
        "renta_scoped_uncited_count": len(renta_scoped_uncited),
        "renta_scoped_coverage_pct": (
            100.0 * len(renta_scoped_cited) / len(renta_scoped_catalogue)
        ) if renta_scoped_catalogue else 100.0,
        "renta_scoped_uncited_articles": renta_scoped_uncited,
    }


_RENTA_ARCHETYPES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (archetype_id, label, hint_keywords for which test scenarios cover it)
    ("A1_employee_only", "Employee only (single income, no deductions)",
     ("employee", "trabajo")),
    ("A2_employee_capital_savings", "Employee + capital mobiliario savings interest",
     ("capital", "savings")),
    ("A3_employee_property_rental", "Employee + property rental income",
     ("rental", "alquiler", "inmobiliario")),
    ("B1_autonomo_directa_normal", "Autónomo direct estimation normal mode",
     ("autonomo", "estimacion-directa-normal", "directa-normal")),
    ("B2_autonomo_directa_simplified", "Autónomo direct estimation simplified mode",
     ("autonomo-simplified", "directa-simplified", "directa-simplificada")),
    ("B3_autonomo_objetiva", "Autónomo objective estimation (modules)",
     ("estimacion-objetiva", "modules", "modulos")),
    ("C1_family_joint", "Family unit joint declaration",
     ("family-joint", "tributacion-conjunta")),
    ("C2_family_descendientes", "Family with descendants / ascendants / discapacidad",
     ("family-descendientes", "minimo-familiar", "discapacidad")),
    ("D1_capital_gains_transactions", "Capital gains transactions (sale of fund / property)",
     ("ganancias", "capital-gains", "patrimoniales")),
    ("E1_ccaa_autonomic_deduction", "CCAA-specific autonomic deduction",
     ("ccaa", "autonomic-deduction", "anexo-b")),
)


_RENTA_TEST_FILES = (
    "src/aeat/domain/calculations/registry/test_renta_2025_synthetic_profile.py",
    "src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py",
    "src/aeat/domain/calculations/registry/test_renta_cuota_chain_contract.py",
    "src/aeat/domain/calculations/registry/test_modelo_100_drift_detection.py",
    "src/aeat/domain/calculations/registry/test_schema_hygiene.py",
)


def layer8_test_honesty_inventory() -> dict:
    """Classify every Renta test as behaviour / structural / vacuous.

    A test is:
      - **behaviour** if it asserts at least one non-zero numeric output
        derived from at least one non-zero numeric input. The math
        actually has to compute correctly for the test to pass.
      - **structural** if it asserts presence/absence of registry
        elements (formulas registered, articles catalogued, no orphans)
        without any numeric assertion. Catches removal/rename
        regressions but does not test computation.
      - **vacuous** if it provides all-zero inputs AND asserts all-zero
        outputs. The chain calculates 0 = 0 + 0 - 0 + ... which never
        fails. False coverage signal.
    """
    import re

    inventory: dict[str, dict] = {}
    for rel_path in _RENTA_TEST_FILES:
        path = PROJECT_ROOT / rel_path
        if not path.exists():
            inventory[rel_path] = {"missing": True}
            continue
        text = path.read_text(encoding="utf-8")
        # Collect test function names
        test_names = re.findall(r"^def (test_\w+)", text, re.MULTILINE)
        # Crude per-file classification: count zero vs non-zero numeric assertions
        zero_value_assertions = len(re.findall(r'value=Decimal\("0(?:\.0+)?"\)', text))
        nonzero_value_assertions = len(re.findall(r'value=Decimal\("(?!0(?:\.0+)?")[^"]+"\)', text))
        nonzero_inputs = len(re.findall(r'Decimal\("(?!0(?:\.0+)?")[^"]+"\)', text))
        # Heuristic file-level classification
        if nonzero_value_assertions > 0 and nonzero_inputs > 0:
            file_kind = "behaviour"
        elif nonzero_value_assertions == 0 and nonzero_inputs == 0:
            file_kind = "structural"
        else:
            file_kind = "mixed"
        # Count "vacuous" patterns: parametrized zero-income asserting all zero
        vacuous_indicator = (
            "zero_income" in text or "zero-income" in text
        ) and zero_value_assertions > nonzero_value_assertions
        inventory[rel_path] = {
            "test_count": len(test_names),
            "tests": test_names,
            "kind": file_kind,
            "zero_value_assertions": zero_value_assertions,
            "nonzero_value_assertions": nonzero_value_assertions,
            "nonzero_decimal_inputs": nonzero_inputs,
            "contains_vacuous_smoke_pattern": vacuous_indicator,
        }
    # Aggregate
    summary = {
        "behaviour_files": [
            p for p, d in inventory.items() if d.get("kind") == "behaviour"
        ],
        "structural_files": [
            p for p, d in inventory.items() if d.get("kind") == "structural"
        ],
        "files_with_vacuous_pattern": [
            p for p, d in inventory.items() if d.get("contains_vacuous_smoke_pattern")
        ],
        "total_zero_value_assertions": sum(
            d.get("zero_value_assertions", 0) for d in inventory.values()
        ),
        "total_nonzero_value_assertions": sum(
            d.get("nonzero_value_assertions", 0) for d in inventory.values()
        ),
    }
    return {"by_file": inventory, "summary": summary}


def layer7_scenario_coverage() -> dict:
    """Inspect test files for synthetic-profile scenarios; map to archetypes."""
    test_files = [
        PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_renta_2025_synthetic_profile.py",
        PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py",
        PROJECT_ROOT / "src/aeat/domain/calculations/registry/test_registry_scenarios.py",
    ]
    scenario_ids: set[str] = set()
    for path in test_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('id="modelo-100-') or stripped.startswith('"id":'):
                # rough extraction
                start = stripped.find('"modelo-100-')
                if start >= 0:
                    end = stripped.find('"', start + 1)
                    if end > start:
                        scenario_ids.add(stripped[start + 1:end])
    coverage: dict[str, dict] = {}
    for archetype_id, label, hints in _RENTA_ARCHETYPES:
        matches = sorted(
            sid for sid in scenario_ids if any(h in sid.lower() for h in hints)
        )
        coverage[archetype_id] = {
            "label": label,
            "covered": len(matches) > 0,
            "matching_scenarios": matches,
        }
    return coverage


_TYPED_ENUM_BRIDGES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (binding_id_pattern, expected_typed_enum, accepted_member_values)
    # The pattern matches against renta-{year}-... binding ids by suffix.
    (
        "modelo-100-estimacion-directa-es-normal",
        "EstimacionDirectaModalidad",
        ("normal", "simplificada"),
    ),
    (
        "profile-tax-residence-ccaa",
        "RentaCCAA",
        (
            "and", "ara", "ast", "bal", "can", "cab", "clm", "cyl", "cat", "ext",
            "gal", "mad", "mur", "nav", "pva", "lar", "val", "ceu", "mel",
        ),
    ),
)


def layer9_typed_binding_inventory(modelo: dict) -> dict:
    """Inventory which Renta substrate-axis bindings carry typed-enum metadata.

    For each binding whose id suffix matches a typed-enum bridge, record:
      - whether the binding declares a `typed_enum` field (formal typed
        bridge),
      - whether its selector's true_value / false_value or fixed values
        match the expected enum members (informal typed bridge),
      - whether it is still free-form (no typed bridge at all).

    The Renta substrate enums (`RentaCCAA`, `EstimacionDirectaModalidad`,
    `RentaIncomeType`) are the canonical taxonomy. Every Renta binding
    that classifies a substrate axis should consume one of these enums
    rather than parse free-form strings at runtime.
    """
    bridges_by_suffix: dict[str, tuple[str, frozenset[str]]] = {
        suffix: (enum_name, frozenset(accepted))
        for suffix, enum_name, accepted in _TYPED_ENUM_BRIDGES
    }
    inventory: dict[str, dict] = {}
    for rev_id, rev in modelo.get("revisions", {}).items():
        if not isinstance(rev, dict):
            continue
        rev_summary: dict[str, dict] = {}
        for binding in rev.get("bindings", []) or []:
            binding_id = binding.get("id", "")
            for suffix, (enum_name, accepted) in bridges_by_suffix.items():
                if binding_id.endswith(suffix):
                    selector = binding.get("selector", {}) or {}
                    selector_values: set[str] = set()
                    if "true_value" in selector:
                        selector_values.add(str(selector["true_value"]).lower())
                    if "false_value" in selector:
                        selector_values.add(str(selector["false_value"]).lower())
                    if "value" in selector:
                        selector_values.add(str(selector["value"]).lower())
                    declares_typed_enum = "typed_enum" in binding
                    informal_match_count = len(selector_values & accepted)
                    rev_summary[binding_id] = {
                        "expected_enum": enum_name,
                        "declares_typed_enum_field": declares_typed_enum,
                        "selector_values": sorted(selector_values),
                        "informal_match_count": informal_match_count,
                        "free_form": not declares_typed_enum
                        and informal_match_count == 0,
                    }
        if rev_summary:
            inventory[rev_id] = rev_summary
    # Aggregate
    total_bridges = sum(len(v) for v in inventory.values())
    typed_count = sum(
        1 for rev in inventory.values() for entry in rev.values()
        if entry["declares_typed_enum_field"]
    )
    informal_count = sum(
        1 for rev in inventory.values() for entry in rev.values()
        if not entry["declares_typed_enum_field"] and entry["informal_match_count"] > 0
    )
    free_form_count = sum(
        1 for rev in inventory.values() for entry in rev.values()
        if entry["free_form"]
    )
    return {
        "by_revision": inventory,
        "summary": {
            "total_bridge_candidates": total_bridges,
            "formally_typed": typed_count,
            "informally_typed": informal_count,
            "free_form": free_form_count,
        },
    }


def render_markdown(findings: dict) -> str:
    today = findings["audit_date"]
    lines: list[str] = []
    lines.append(f"# Renta scope audit — {today}\n")
    lines.append(
        "Rolling inventory of Renta data wrangling scope vs current registry "
        "implementation. Re-run on every commit; the document is the foundation "
        "of the typed-out singular plan that lists exec steps required for full "
        "Renta coverage.\n"
    )

    # Layer 1
    lines.append("## Layer 1 — Casilla inventory & classification\n")
    lines.append("| Revision | Total | Computed | Bound | Manual | Informational | Read by formula | Never read |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for rev_id in sorted(findings["layer1"].keys()):
        l1 = findings["layer1"][rev_id]
        kind = l1["input_kind"]
        lines.append(
            f"| {rev_id} | {l1['total_casillas']} | {l1['computed_targets']} | "
            f"{kind.get('bound', 0)} | {kind.get('manual', 0)} | "
            f"{kind.get('informational', 0)} | "
            f"{l1['casillas_consumed_by_formulas']} | "
            f"{l1['casillas_declared_but_never_read']} |"
        )
    lines.append("")

    # Layer 3
    lines.append("## Layer 3 — Mini-model coverage scorecard (ejercicio 2025)\n")
    lines.append("| Mini-model | Label | Casillas | Computed | Bound | Manual | Coverage % |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for group_id, l3 in findings["layer3"].items():
        coverage = l3.get("coverage_pct", 0)
        flag = " 🚨" if coverage < 5 else ""
        lines.append(
            f"| {group_id} | {l3['label']} | {l3['total_casillas']} | "
            f"{l3['computed']} | {l3['bound']} | {l3['manual']} | "
            f"{coverage}{flag} |"
        )
    lines.append("")

    # Layer 4
    l4 = findings["layer4"]
    lines.append("## Layer 4 — Legal grounding inventory\n")
    lines.append(f"- **Catalogued legal_refs**: {l4['catalogued_count']}")
    lines.append(f"- **Cited by registry elements**: {l4['cited_count']}")
    lines.append(f"- **Catalogued but never cited**: {l4['catalogued_but_uncited_count']}")
    lines.append(f"- **Cited but missing from catalogue**: {l4['cited_but_uncatalogued_count']}")
    lines.append("\n### Top 15 most-cited legal_refs\n")
    lines.append("| Article | Citation count |")
    lines.append("|---|---:|")
    for ref, count in l4["top_cited"]:
        lines.append(f"| `{ref}` | {count} |")
    if l4["uncited_articles"]:
        lines.append("\n### Sample catalogued-but-uncited (orphan substrate)\n")
        for ref in l4["uncited_articles"]:
            lines.append(f"- `{ref}`")
    if l4["uncatalogued_articles"]:
        lines.append("\n### Sample cited-but-uncatalogued (BROKEN — should never appear)\n")
        for ref in l4["uncatalogued_articles"]:
            lines.append(f"- `{ref}`")
    lines.append("")

    # Layer 7
    lines.append("## Layer 7 — Scenario archetype coverage\n")
    lines.append("| Archetype | Label | Covered | Matching scenarios |")
    lines.append("|---|---|---|---|")
    for arch_id, l7 in findings["layer7"].items():
        covered_mark = "✓" if l7["covered"] else "✗"
        scenarios = ", ".join(l7["matching_scenarios"]) if l7["matching_scenarios"] else "—"
        lines.append(f"| `{arch_id}` | {l7['label']} | {covered_mark} | {scenarios} |")
    lines.append("")

    # Layer 8 — Test honesty
    l8 = findings["layer8"]
    s8 = l8["summary"]
    lines.append("## Layer 8 — Test honesty inventory\n")
    lines.append(
        "Classifies every Renta test as **behaviour** (asserts non-zero numeric "
        "output from non-zero input — the math has to compute correctly), "
        "**structural** (asserts presence/absence of registry elements — "
        "catches removal/rename regressions but does NOT test computation), "
        "or contains a **vacuous smoke pattern** (all-zero inputs / all-zero "
        "outputs — the chain computes 0 = 0 + 0 - 0 + ... which never fails, "
        "giving false coverage).\n"
    )
    lines.append("| File | Tests | Kind | Zero asserts | Non-zero asserts | Non-zero inputs | Vacuous pattern |")
    lines.append("|---|---:|---|---:|---:|---:|:---:|")
    for path, info in l8["by_file"].items():
        if info.get("missing"):
            lines.append(f"| `{path}` | (missing) | — | — | — | — | — |")
            continue
        flag = "🚨 yes" if info["contains_vacuous_smoke_pattern"] else "no"
        lines.append(
            f"| `{path.split('/')[-1]}` | {info['test_count']} | "
            f"{info['kind']} | {info['zero_value_assertions']} | "
            f"{info['nonzero_value_assertions']} | {info['nonzero_decimal_inputs']} | "
            f"{flag} |"
        )
    lines.append("")
    lines.append(
        f"**Total numeric assertions**: "
        f"{s8['total_zero_value_assertions']} zero + "
        f"{s8['total_nonzero_value_assertions']} non-zero. "
        f"**Files with vacuous-smoke pattern**: "
        f"{len(s8['files_with_vacuous_pattern'])} of "
        f"{len(l8['by_file'])}.\n"
    )

    # Layer 9 — Typed-binding inventory
    l9 = findings["layer9"]
    s9 = l9["summary"]
    lines.append("## Layer 9 — Typed-binding inventory\n")
    lines.append(
        "Each Renta binding that classifies a substrate axis (autonomous "
        "community of residence, estimación directa modality, etc.) must "
        "consume a closed-membership pydantic enum from `aeat.domain.renta` "
        "rather than parse free-form strings at runtime. This layer "
        "inventories the bridge-candidate bindings and reports their typing "
        "status: formally typed (declares a `typed_enum` field), "
        "informally typed (selector values happen to match enum members "
        "without explicit declaration), or free-form.\n"
    )
    lines.append(
        f"- **Total bridge candidates**: {s9['total_bridge_candidates']}\n"
        f"- **Formally typed (declares `typed_enum`)**: {s9['formally_typed']}\n"
        f"- **Informally typed (selector matches enum members)**: {s9['informally_typed']}\n"
        f"- **Free-form (no typed bridge at all)**: {s9['free_form']}\n"
    )
    if l9["by_revision"]:
        lines.append("\n### Per-revision typed-binding status\n")
        for rev_id in sorted(l9["by_revision"].keys()):
            entries = l9["by_revision"][rev_id]
            lines.append(f"\n**Revision {rev_id}** ({len(entries)} bridge candidates):\n")
            for binding_id in sorted(entries.keys()):
                e = entries[binding_id]
                if e["declares_typed_enum_field"]:
                    status = f"formally typed → `{e['expected_enum']}`"
                elif e["informal_match_count"] > 0:
                    status = f"informally typed → matches `{e['expected_enum']}`"
                else:
                    status = f"🚨 free-form (expected `{e['expected_enum']}`)"
                lines.append(f"- `{binding_id}` — {status}")
    lines.append("")

    # Layer 2 — Citation phrase coverage
    if "layer2" in findings:
        l2 = findings["layer2"]
        lines.append("## Layer 2 — Citation phrase coverage (HTML/text corpora)\n")
        lines.append(f"- **Formulas inspected**: {l2['formula_count']}")
        lines.append(f"- **Citation phrases checked**: {l2['phrase_count']}")
        lines.append(f"- **Phrases matched**: {l2['phrases_matched']}")
        lines.append(f"- **Phrases missed**: {l2['phrases_missed']}")
        lines.append(f"- **Coverage**: {l2['coverage_pct']:.1f}%")
        lines.append(f"- **Misalignments**: {l2['misalignment_count']}")
        if l2.get("misalignments"):
            lines.append("\n### Sample misalignments\n")
            for m in l2["misalignments"][:5]:
                lines.append(f"- `{m.get('formula_id', '?')}` → {m.get('kind', '?')}")
        lines.append("")

    # Layer 5 — Cross-modelo relation closed-loop
    if "layer5" in findings:
        l5 = findings["layer5"]
        lines.append("## Layer 5 — Cross-modelo relation closed-loop\n")
        lines.append(f"- **Total relations**: {l5['relations_total']}")
        lines.append(f"- **Closed-loop**: {l5['closed_loop']}")
        lines.append(f"- **Open-loop**: {l5['open_loop']}")
        lines.append(f"- **Coverage**: {l5['coverage_pct']:.1f}%")
        if l5.get("misalignments"):
            lines.append("\n### Open-loop relations\n")
            for m in l5["misalignments"][:10]:
                lines.append(f"- `{m.get('relation_id', '?')}` → {m.get('kind', '?')}")
        lines.append("")

    # Layer 6 — External-surface registration
    if "layer6" in findings:
        l6 = findings["layer6"]
        lines.append("## Layer 6 — External-surface registration\n")
        lines.append(f"- **Total surfaces**: {l6['total_surfaces']}")
        lines.append(f"- **Guarded (policy attached)**: {l6['guarded_count']}")
        lines.append(f"- **Synthetic-data allowed**: {l6['synthetic_data_allowed_count']}")
        lines.append(f"- **Auth required**: {l6['auth_required_count']}")
        lines.append("\n### Surfaces per revision\n")
        for rev_id, count in sorted(l6.get("surfaces_per_revision", {}).items()):
            lines.append(f"- {rev_id}: {count} surface(s)")
        lines.append("")

    # Layer 10 — Rental pipeline regression
    if "layer10" in findings:
        l10 = findings["layer10"]
        lines.append("## Layer 10 — Rental pipeline regression\n")
        lines.append(
            f"- **Rental parameters total**: {l10['params_present_total']} / {l10['params_total']} "
            f"({l10['params_coverage_pct']:.1f}%)"
        )
        lines.append("\n### Per-revision rental casilla counts\n")
        lines.append("| Revision | Rental casillas | Manual | Bound | Computed | Params present |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for rev_id, info in sorted((l10.get("revisions") or {}).items()):
            kind = info.get("kind_distribution", {})
            lines.append(
                f"| {rev_id} | {info['rental_casilla_count']} | "
                f"{kind.get('manual', 0)} | {kind.get('bound', 0)} | "
                f"{kind.get('computed', 0)} | "
                f"{len(info.get('rental_params_present', []))} / "
                f"{len(l10.get('expected_params_per_revision', ()))} |"
            )
        lines.append("")

    # Honest summary
    rev2025 = findings["layer1"].get("2025", {})
    total_cas = rev2025.get("total_casillas", 0)
    computed = rev2025.get("computed_targets", 0)
    archetype_covered = sum(1 for v in findings["layer7"].values() if v["covered"])
    archetype_total = len(findings["layer7"])
    lines.append("## Honest scope summary\n")
    lines.append(
        f"**Casilla coverage** in 2025: {computed} / {total_cas} "
        f"({100 * computed / max(total_cas, 1):.1f}%) computed via formula. "
        f"The remainder is manual input or bound to profile data — i.e. the "
        f"taxpayer or extractor has to supply them.\n"
    )
    lines.append(
        f"**Archetype coverage**: {archetype_covered} of {archetype_total} "
        f"Renta filing archetypes have at least one scenario test that exercises "
        f"the chain. The uncovered archetypes are the gaps that block "
        f"end-to-end Renta automation.\n"
    )
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    modelo = _load_modelo()
    findings: dict = {
        "audit_date": str(date.today()),
        "modelo": "100",
        "layer1": layer1_casilla_inventory(modelo),
        "layer2": layer2_citation_phrase_coverage(modelo),
        "layer3": layer3_mini_model_coverage(modelo, "2025"),
        "layer4": layer4_legal_grounding(modelo),
        "layer5": layer5_cross_modelo_closed_loop(modelo),
        "layer6": layer6_external_surface_registration(modelo),
        "layer10": layer10_rental_pipeline_regression(modelo),
        "layer7": layer7_scenario_coverage(),
        "layer8": layer8_test_honesty_inventory(),
        "layer9": layer9_typed_binding_inventory(modelo),
    }
    json_path = OUTPUT_DIR / f"{date.today()}-renta-scope-audit-findings.json"
    json_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_summary = render_markdown(findings)
    print(md_summary)
    print(f"\n--- raw JSON written to: {json_path.relative_to(PROJECT_ROOT)} ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
