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


def layer4_legal_grounding(modelo: dict) -> dict:
    """Which legal_refs are cited, which catalogue entries are orphaned."""
    catalogued_legal, _ = _load_legal_catalogue()
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
    return {
        "catalogued_count": len(catalogued_legal),
        "cited_count": len(cited_set),
        "catalogued_but_uncited_count": len(catalogued_but_uncited),
        "cited_but_uncatalogued_count": len(cited_but_uncatalogued),
        "top_cited": cited_legal.most_common(15),
        "uncited_articles": catalogued_but_uncited[:20],
        "uncatalogued_articles": cited_but_uncatalogued[:20],
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
        "layer3": layer3_mini_model_coverage(modelo, "2025"),
        "layer4": layer4_legal_grounding(modelo),
        "layer7": layer7_scenario_coverage(),
        "layer8": layer8_test_honesty_inventory(),
    }
    json_path = OUTPUT_DIR / f"{date.today()}-renta-scope-audit-findings.json"
    json_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_summary = render_markdown(findings)
    print(md_summary)
    print(f"\n--- raw JSON written to: {json_path.relative_to(PROJECT_ROOT)} ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
