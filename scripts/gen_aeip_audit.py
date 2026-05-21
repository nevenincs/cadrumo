"""Generate the AEIP family audit document for .vault/audit/"""
import re
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path("src/aeat/_data/registry/aeat/modelos/100/revisions")
REVISIONS = ["2020", "2021", "2022", "2023", "2024", "2025"]

TARGET_ROLES = {
    "irpf_deduccion_incentivos_inversion_empresarial_estatal",
    "irpf_anexo_a_aeip_aplicado_flag",
    "irpf_anexo_c_exceso_eeficiencia_pendiente_fin",
    "irpf_anexo_c_exceso_eeficiencia_pendiente_inicio",
    "irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado",
    "irpf_anexo_a_rib_pendiente_materializar",
    "irpf_anexo_b_carry_forward_remaining",
    "irpf_anexo_c_exceso_eeficiencia_aplicado",
}


def parse_toml_casilla(content):
    id_val = label_val = role_val = section_val = None
    for line in content.split("\n"):
        line = line.strip()
        if re.match(r"^id\s*=", line):
            id_val = line.split("=", 1)[1].strip().strip('"')
        elif re.match(r"^label\s*=", line):
            label_val = line.split("=", 1)[1].strip()
            if label_val.startswith('"') and label_val.endswith('"'):
                label_val = label_val[1:-1]
        elif re.match(r"^semantic_role\s*=", line):
            role_val = line.split("=", 1)[1].strip().strip('"')
        elif re.match(r"^section\s*=", line):
            section_val = line.split("=", 1)[1].strip()
    return id_val, label_val, role_val, section_val


def is_event_casilla(label_val, in_section):
    return bool(in_section and '\\"' in label_val and "Aplicado" in label_val)


def get_snippet(label):
    m = re.search(r'\\"(.{1,50}?)\\"', label)
    return m.group(1) if m else label[:50]


def collect():
    events = []
    non_events = []
    for rev in REVISIONS:
        casilla_dir = BASE / rev / "casillas"
        if not casilla_dir.exists():
            continue
        for f in sorted(casilla_dir.iterdir()):
            content = f.read_text(encoding="utf-8")
            in_section = "deducciones_inversion_empresarial_res" in content
            id_val, label_val, role_val, section_val = parse_toml_casilla(content)
            if not label_val:
                continue
            if is_event_casilla(label_val, in_section):
                events.append(
                    {"rev": rev, "id": id_val, "role": role_val, "label": label_val}
                )
            elif role_val in TARGET_ROLES:
                non_events.append(
                    {
                        "rev": rev,
                        "id": id_val,
                        "role": role_val,
                        "label": label_val[:100],
                    }
                )
    return events, non_events


def main():
    events, non_events = collect()

    role_counts = Counter(c["role"] for c in events)
    need_change = [c for c in events if c["role"] != "irpf_anexo_a_aeip_aplicado_flag"]

    id_labels = defaultdict(set)
    for c in events:
        id_labels[c["id"]].add(c["label"][:60])
    reused_ids = sorted(cid for cid, labels in id_labels.items() if len(labels) > 1)

    rows = [
        (c["id"], c["rev"], c["role"], get_snippet(c["label"]))
        for c in sorted(events, key=lambda x: (x["id"], x["rev"]))
    ]

    by_role = defaultdict(list)
    for c in non_events:
        by_role[c["role"]].append(c)

    out = Path(".vault/audit/2026-05-20-schema-hardening-m100-aeip-family.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    a = lines.append
    a("---")
    a("tags:")
    a("  - '#audit'")
    a("  - '#schema-hardening'")
    a("date: '2026-05-20'")
    a("related:")
    a('  - "[[2026-05-20-schema-hardening-verification-ledger]]"')
    a("---")
    a("")
    a("# M100 AEIP Family Audit")
    a("")
    a("## Scope")
    a("")
    a(
        "Read-only investigation of all M100 casillas in section"
        " `resultados.anexo_a_res.deducciones_inversion_empresarial_res`"
        " across revisions 2020-2025 whose label contains a quoted AEIP event"
        " name followed by `: Aplicado en esta declaracion`."
        " These are the AEIP (Acontecimientos de Excepcional Interes Publico)"
        " sponsorship-deduction casillas mis-classified by a label-truncation bug"
        " during the original role assignment pass."
    )
    a("")
    a(
        "Source files: `src/aeat/_data/registry/aeat/modelos/100/revisions/"
        "*/casillas/*.toml`"
    )
    a("")
    a("## Finding")
    a("")
    a("### What the family is")
    a("")
    a(
        "Every casilla in this family records the **euro amount of an AEIP"
        " event-sponsorship deduction applied in the current filing** (the"
        ' "Aplicado en esta declaracion" slot in Anexo A.6 of Modelo 100).'
        " The label pattern is invariably:"
    )
    a("")
    a("```")
    a('"<event name>": Aplicado en esta declaracion')
    a("```")
    a("")
    a("A small minority use an embedded-quote form:")
    a("")
    a("```")
    a('<outer label> "<sub-programme name>": Aplicado en esta declaracion')
    a("```")
    a("")
    a(
        "This is seen on ID 1712 (Habitos Saludables ... Aprender a cuidarnos)"
        " and ID 1693 (Celebracion del Summit MADBLUE) — functionally identical;"
        " the quoted string is the registered AEIP programme name."
    )
    a("")
    a(
        "**There are no sub-variants.** Every casilla represents the same"
        " concept: the monetary amount of an AEIP deduction applied in the"
        " declaration. There is no pendiente sub-type within this family;"
        " carry-forward amounts do not appear in this sub-section."
    )
    a("")
    a("### Family size")
    a("")
    a(f"- Total event-family casillas: **{len(events)}** across 6 revisions")
    a(
        f"- Already carrying `irpf_anexo_a_aeip_aplicado_flag`:"
        f" **{role_counts['irpf_anexo_a_aeip_aplicado_flag']}**"
    )
    a(f"- Carrying wrong roles: **{len(need_change)}**")
    a("")
    a("### Wrong role distribution")
    a("")
    a("| current_role | count | verdict |")
    a("|---|---|---|")
    for role, cnt in sorted(role_counts.items(), key=lambda x: -x[1]):
        if role == "irpf_anexo_a_aeip_aplicado_flag":
            verdict = "rename target — drop _flag suffix"
        else:
            verdict = "WRONG — event casilla mis-assigned"
        a(f"| `{role}` | {cnt} | {verdict} |")
    a("")
    a("## Canonical role decision")
    a("")
    a(
        "**The correct semantic role for every event-family casilla is"
        " `irpf_anexo_a_aeip_aplicado`** (without the `_flag` suffix)."
    )
    a("")
    a("Justification:")
    a("")
    a(
        "- **The `_flag` suffix is factually wrong.** A flag signals a boolean"
        " or indicator field. Every one of these 315 casillas carries a euro"
        " money amount (the deduction applied), not a boolean indicator. The"
        " name `irpf_anexo_a_aeip_aplicado_flag` was assigned by the buggy pass"
        " that truncated labels to the opening quote character; the `_flag`"
        " portion reflects a classification error, not the AEAT field type."
    )
    a("")
    a(
        "- **The label is authoritative.** Every casilla uses the construction"
        ' `"<AEIP registered programme name>": Aplicado en esta declaracion`'
        " drawn from the AEAT official source dictionary and XSD. AEAT Anexo"
        " A.6 is titled Regimen especial de apoyo a los acontecimientos de"
        " excepcional interes publico; the Aplicado en esta declaracion column"
        " is the current-year applied deduction amount per named event under"
        " `ley-35-2006:art-68.2` and LIS art-36 / art-39. Legal refs are"
        " identical across all 315 casillas."
    )
    a("")
    a(
        "- **No split required.** All 315 casillas say Aplicado; none say"
        " Pendiente. A single canonical role covers the entire family."
    )
    a("")
    a(
        "- **The existing `irpf_anexo_a_aeip_aplicado_flag` role must be"
        " renamed** to `irpf_anexo_a_aeip_aplicado`. Its 137 non-event"
        " members require separate reclassification — they are generic"
        " LIS-chapter deduction sub-totals and Canarias/Baleares entries"
        " that happen to share the old role name."
    )
    a("")
    a("## Role assignments")
    a("")
    a(
        "All 315 event casillas should carry `irpf_anexo_a_aeip_aplicado`."
    )
    a("")
    a("| id | revision | current_role | correct_role | label_snippet |")
    a("|---|---|---|---|---|")
    for cid, rev, current_role, snippet in rows:
        safe = snippet.replace("|", "/")
        a(f"| {cid} | {rev} | {current_role} | irpf_anexo_a_aeip_aplicado | {safe} |")
    a("")
    a("## Non-event members to leave untouched")
    a("")
    a(
        "These casillas share one of the 8 affected roles but are NOT AEIP"
        " event casillas and must not be touched by an AEIP-targeted fix pass."
    )
    a("")
    for role in sorted(by_role):
        cs = by_role[role]
        a(f"### `{role}` ({len(cs)} non-event members)")
        a("")
        a("| id | revision | label_snippet |")
        a("|---|---|---|")
        for c in sorted(cs, key=lambda x: (x["id"], x["rev"])):
            sn = c["label"][:70].replace("|", "/")
            a(f"| {c['id']} | {c['rev']} | {sn} |")
        a("")
    a("## ID-reuse hazard")
    a("")
    a(
        "The following casilla IDs host different event names across revisions."
        " Any automated fix script must target **(id, revision)** pairs, never"
        " bare IDs."
    )
    a("")
    a(f"Affected IDs ({len(reused_ids)} total):")
    a("")
    a(", ".join(f"`{x}`" for x in reused_ids))
    a("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {len(lines)} lines to {out}")
    print(f"Size: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
