---
name: aeat-continuidad-grounding
description: 'Ground casilla continuity chains: derive the candidate evidence programmatically,
  adjudicate identity against official AEAT/BOE sources, author the continuidad_id
  stamps and evolution records, and verify through the registry''s strict cross-revision
  gates. Use when stamping chains, reviewing continuity candidates, or preparing the
  grounding worklist.'
---

# Continuidad chain grounding

Ground a continuity chain: turn "casilla `X` in revision A and casilla `X` in
revision B are the same legal concept" from an assumption into an evidenced,
compiler-validated registry fact. Grounding is the prerequisite for one
translation per concept, safe cross-revision value sharing, and cross-year
carry semantics.

## The contract in one screen

- A repeated casilla id, matching label, or identical field shape is NEVER
  proof of identity. Ids renumber across filing years (Modelo 100 id `1911` is
  a ganancia box in 2024 and a maternity-deduction box in 2022). Only
  `continuidad_id` asserts cross-revision identity, and only with evidence.
- A chain id is concept-named, never numeric, so it survives renumbering.
  Constraint: `^[a-z0-9][a-z0-9._:-]*[a-z0-9]$`, max 128 chars. Which of the
  two shapes below applies is decided by ONE question — does the casilla's
  `semantic_role` identify exactly one box per revision?
  - **Role-unique → flat kebab, derived from the role**: `semantic_role`
    lowercased with `_` → `-`, nothing else. `irpf_deduccion_galicia_otras`
    → `irpf-deduccion-galicia-otras`. This is the overwhelming majority of the
    corpus and it is mechanically exact — every one of the 3,159 occurrences
    measured on 2026-08-05 equals `role.replace("_", "-")` with no exceptions.
    Derive it; do not invent a prettier name.
  - **Role-ambiguous → dotted, instance-keyed, hand-adjudicated**: when two or
    more casillas in one revision share the role, a role-derived id would
    collide and merge distinct concepts into one chain. Key on whatever DOES
    identify the box — the event, the column, the distinguishing clause — as
    `<impuesto>.<familia>.<instancia>.<columna>`. The anexo-A AEIP family is
    the worked example: 71 boxes share `irpf_anexo_a_aeip_aplicado` and the ids
    repack yearly, so `dev/registry/aeip` keys them on the programme title AEAT
    prints (`irpf.aeip.<event-slug>.aplicado`, its `CHAIN_PREFIX`).
  Check role-uniqueness before naming. Reaching for dotted on a role-unique
  chain is the drift that has to be swept back out later; reaching for kebab on
  a role-ambiguous one silently merges two concepts, which is worse.
- Evolution kinds are a closed set: `unchanged`, `label_evolved`,
  `legal_refs_evolved`, `label_and_legal_refs_evolved`, `repurposed`,
  `retired`. Two are safety-critical: `retired` ends a chain (the target
  revision MUST NOT declare the id — validated), and `repurposed` is an
  inheritance BARRIER: no value, translation, or carry crosses it.
- Enforcement is two-tier: unannotated repeated-id drift is advisory;
  declared continuity surfaces hard-fail under a revision's
  `continuidad_validation = "strict"` opt-in (drift on a stamped surface must
  be covered by a matching evolution record).
- Division of labour: tooling prepares the dossier and suggests a
  classification; the identity judgment is TAX REVIEW against official
  sources (AEAT dictionary/XSD, Manual Práctico, BOE-published form), never
  text similarity. Ground per `aeat-safety-legal-gates`; record honest
  reviewer provenance. Governing decision:
  `2026-05-27-schema-hardening-casilla-continuity-contract-adr`.

## Workflow per chain

1. **Pick from the tiered worklist** (tooling below). Work easiest-first:
   T1 rubber-stamps build corpus coverage cheaply; T4 needs full adjudication.
2. **Generate the dossier** for the candidate — per-revision labels, legal
   refs, structural core, existing stamps/evolutions, locale leaves.
3. **Adjudicate**: same legal question in every revision? If the structural
   core drifts (`data_type`, `semantic_role`, formula role), suspect
   renumbering — consider `repurposed` or reject the chain. If only wording
   or legal refs moved, pick the matching evolution kind. Verify against the
   official sources for BOTH endpoint years; the dossier's suggestion is a
   hypothesis, not a decision.
4. **Author** (shapes below): stamp every occurrence, add evolution records,
   flip the strict flag once the revision's surfaces are covered.
5. **Verify** with the registry gates, then commit with an explicit pathspec
   naming only your files (shared-worktree discipline).

## Programmatic tooling

Save the two scripts below into your session scratchpad and run them from the
repo root with plain `python` (stdlib only, read-only, seconds per run).

### 1. Tiered triage worklist (which chains, in what order)

Classifies every ungrounded multi-revision casilla id by review effort:
`T1-rubber-stamp` (label, core, legal refs all identical),
`T2-legal-refs-review` (only legal refs differ), `T3-wording-review`
(label diverges, core stable), `T4-full-adjudication` (core drifts —
renumbering suspect). Measured on 2026-08-05: 2,354 candidates = 171 T1 +
1,260 T2 + 406 T3 + 517 T4. Also flags partially-stamped chains.

```python
"""chain_worklist.py [repo-root] [--json out.json] -- easiest-first triage."""
import json, re, sys, tomllib, unicodedata
from collections import defaultdict
from pathlib import Path

repo = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else Path.cwd()
out_path = Path(sys.argv[sys.argv.index("--json") + 1]) if "--json" in sys.argv else None
_WS, _YEAR = re.compile(r"\s+"), re.compile(r"(19|20)\d{2}")
# The strict validator compares exactly five fields
# (_CROSS_REVISION_CASILLA_FIELDS in _cross_revision_divergence.py): label,
# section, data_type, semantic_role, legal_refs. Tier on those, or the triage
# lies -- `section` especially, because NO evolution kind covers it except
# `repurposed`, which is an inheritance barrier and the opposite of the claim a
# stamp makes. A section-drifting chain called "rubber-stamp" produces a strict
# failure nothing can close.
CORE = ("section", "data_type", "semantic_role")
# Not validated, so never a strict failure -- but a `number` or `formula` move
# is a strong renumbering signal, so carry it as a visible column.
INFO = ("number", "input_kind", "formula", "binding")

def norm(t):
    t = unicodedata.normalize("NFKC", t).casefold()
    return _WS.sub(" ", t).strip().rstrip(".,;:")

rows = []
for modelo_dir in sorted(p for p in (repo / "src/cadrumo/_data/registry/aeat/modelos").iterdir() if p.is_dir()):
    owners = defaultdict(dict)
    for path in sorted((modelo_dir / "revisions").rglob("*.toml")):
        if "locales" in path.parts:
            continue
        for rev, body in tomllib.loads(path.read_text(encoding="utf-8")).get("revisions", {}).items():
            if isinstance(body, dict):
                for e in body.get("casillas", []) or []:
                    if isinstance(e, dict) and e.get("id"):
                        owners[str(e["id"])][str(rev)] = e
    for cid, per in owners.items():
        if len(per) < 2 or all(e.get("continuidad_id") for e in per.values()):
            continue
        labels = {norm(str(e.get("label", ""))) for e in per.values()}
        cores = {tuple((f, str(e.get(f))) for f in CORE) for e in per.values()}
        infos = {tuple((f, str(e.get(f))) for f in INFO) for e in per.values()}
        legal = {tuple(e.get("legal_refs") or ()) for e in per.values()}
        label_state = ("identical" if len(labels) == 1
                       else "year_token_only" if len({_YEAR.sub("Y", v) for v in labels}) == 1
                       else "divergent")
        core_ok = len(cores) == 1
        tier = ("T1-rubber-stamp" if label_state != "divergent" and core_ok and len(legal) == 1
                else "T2-legal-refs-review" if label_state != "divergent" and core_ok
                else "T3-wording-review" if core_ok else "T4-full-adjudication")
        rows.append({"modelo": modelo_dir.name, "casilla_id": cid, "revisions": sorted(per),
                     "label_state": label_state, "core_stable": core_ok,
                     "legal_refs_stable": len(legal) == 1,
                     "unvalidated_drift": sorted(
                         f for f in INFO if len({dict(t)[f] for t in infos}) > 1
                     ),
                     "partially_stamped": any(e.get("continuidad_id") for e in per.values()),
                     "tier": tier})

order = {"T1-rubber-stamp": 0, "T2-legal-refs-review": 1, "T3-wording-review": 2, "T4-full-adjudication": 3}
rows.sort(key=lambda r: (order[r["tier"]], r["modelo"], r["casilla_id"]))
tally = defaultdict(int)
for r in rows:
    tally[r["tier"]] += 1
print(f"ungrounded multi-revision candidate chains: {len(rows)}")
for tier in sorted(tally, key=order.get):
    print(f"  {tier}: {tally[tier]}")
partial = sum(1 for r in rows if r["partially_stamped"])
if partial:
    print(f"  WARNING partially-stamped chains: {partial}")
if out_path:
    out_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"worklist written to {out_path}")
```

### 2. Chain dossier (everything known about one candidate)

`python chain_dossier.py <modelo> <casilla-id> [repo-root]` prints every
occurrence's label/legal_refs/structural core, drift classification, a
SUGGESTED evolution kind (a hypothesis to verify, never a decision), existing
stamps and evolution records, and the revision-catalogue locale leaves the
chain will eventually own. Positive control: run it on grounded `100 0063` —
its suggestion must match the authored `legal_refs_evolved` records.

```python
"""chain_dossier.py <modelo> <casilla-id> [repo-root]"""
import re, sys, tomllib, unicodedata
from pathlib import Path

modelo, cid = sys.argv[1], sys.argv[2]
repo = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.cwd()
mdir = repo / "src/cadrumo/_data/registry/aeat/modelos" / modelo
_WS, _YEAR = re.compile(r"\s+"), re.compile(r"(19|20)\d{2}")
# The strict validator's compared set, minus label/legal_refs which are
# classified separately below. Keep in step with
# _CROSS_REVISION_CASILLA_FIELDS in _cross_revision_divergence.py.
CORE = ("section", "data_type", "semantic_role")
# Unvalidated, but a renumbering tell worth seeing during adjudication.
INFO = ("number", "input_kind", "formula", "binding")

def norm(t):
    t = unicodedata.normalize("NFKC", t).casefold()
    return _WS.sub(" ", t).strip().rstrip(".,;:")

occ, evos = {}, []
for path in sorted((mdir / "revisions").rglob("*.toml")):
    if "locales" in path.parts:
        continue
    for rev, body in tomllib.loads(path.read_text(encoding="utf-8")).get("revisions", {}).items():
        if not isinstance(body, dict):
            continue
        for e in body.get("casillas", []) or []:
            if isinstance(e, dict) and str(e.get("id")) == cid:
                occ[str(rev)] = dict(e)
        evos += [dict(v) for v in body.get("casilla_continuidad_evolutions", []) or []]
if not occ:
    sys.exit(f"modelo {modelo}: no occurrence of casilla id {cid!r}")

print(f"=== modelo {modelo} casilla {cid}: {len(occ)} occurrence(s) ===")
for rev in sorted(occ):
    e = occ[rev]
    core = {f: e.get(f) for f in CORE if e.get(f) is not None}
    info = {f: e.get(f) for f in INFO if e.get(f) is not None}
    print(f"\n[{rev}] stamp={e.get('continuidad_id')!r}")
    print(f"  label: {e.get('label', '')}")
    print(f"  legal_refs: {e.get('legal_refs')}")
    print(f"  core (validated): {core}")
    print(f"  info (unvalidated): {info}")

labels = {rev: str(e.get("label", "")) for rev, e in occ.items()}
core_ok = len({tuple((f, str(e.get(f))) for f in CORE) for e in occ.values()}) == 1
legal_ok = len({tuple(e.get("legal_refs") or ()) for e in occ.values()}) == 1
lv = set(labels.values())
label_state = ("byte-identical" if len(lv) == 1
               else "identical after normalise" if len({norm(v) for v in lv}) == 1
               else "differs only by embedded year" if len({_YEAR.sub("Y", norm(v)) for v in lv}) == 1
               else "SUBSTANTIVELY DIVERGENT -- adjudicate reword vs repurpose")
info_drift = sorted(f for f in INFO if len({str(e.get(f)) for e in occ.values()}) > 1)
print("\n=== drift classification ===")
print(f"  validated core stable:  {core_ok}\n  legal_refs stable:      {legal_ok}\n  label:                  {label_state}")
print(f"  unvalidated drift:      {info_drift or 'none'}  (no strict failure; a renumbering tell)")
tidy = label_state in ("byte-identical", "identical after normalise")
suggestion = ("unchanged" if core_ok and legal_ok and tidy
              else "label_evolved" if core_ok and legal_ok
              else "legal_refs_evolved" if core_ok and tidy
              else "label_and_legal_refs_evolved" if core_ok
              else "NO SUGGESTION -- core drifts; suspect renumbering/repurposed")
print(f"  suggested evolution_kind (verify against official sources!): {suggestion}")

stamps = {e.get("continuidad_id") for e in occ.values()} - {None}
mine = [v for v in evos if v.get("continuidad_id") in stamps]
print(f"\n=== existing evolution records touching these stamps: {len(mine)} ===")
for v in mine:
    print(f"  {v.get('id')}: {v.get('from_revision')} -> {v.get('to_revision')} [{v.get('evolution_kind')}]")

print("\n=== locale leaves for this id (revision catalogues) ===")
for rev_dir in sorted((mdir / "revisions").iterdir()):
    loc = rev_dir / "locales"
    if not loc.is_dir():
        continue
    for entry in sorted(loc.iterdir()):
        paths = [entry] if entry.is_file() else sorted(entry.rglob("*.toml"))
        for path in paths:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            for table in ("labels", "help"):
                value = data.get(table, {}).get(cid)
                if value is not None:
                    name = entry.stem if entry.is_file() else entry.name
                    print(f"  {rev_dir.name}/{name}/{table}: {value[:70]}")
```

### 3. Quick probes

- Existing chain-id inventory (naming precedent before inventing a new id):
  `rg -h 'continuidad_id = "' src/cadrumo/_data/registry/aeat/modelos/ | sort -u`
- Every fragment declaring one casilla id:
  `rg -l '^id = "0063"' src/cadrumo/_data/registry/aeat/modelos/100/revisions/`
- Concept-naming precedent by meaning (semantic search before naming):
  `uv run --no-sync vaultspec-rag search "<concept in words>" --type code --port 8766 --timeout 120`
- Localization-side register (the migration campaign's classified candidates —
  richer locale drift context): the `dev.registry.migration.manager` API
  (`extract_resolved_localization_matrix`,
  `generate_canonical_occurrence_candidates`,
  `classify_canonical_occurrence_candidates`, `build_source_manifest`,
  `build_unresolved_review_register`), driven from the production loader.

## Authoring shapes (exact, from the live corpus)

**Stamp every occurrence** — one line in each revision's casilla fragment:

```toml
continuidad_id = "irpf.inmueble.porcentaje-propiedad"
```

**Evolution records** — a fragment file in the NEWEST revision's
`continuidad/` directory (convention: declared under the `to_revision`;
one file per casilla, named `<casilla>-<from>-<to>-<kind>.toml`), records
pairwise per revision pair, adjacent pairs at minimum plus any drifting
non-adjacent pair the strict validator reports:

```toml
[[revisions."2025".casilla_continuidad_evolutions]]
id = "m100-0063-2023-2024-unchanged"
continuidad_id = "irpf.inmueble.porcentaje-propiedad"
from_revision = "2023"
to_revision = "2024"
evolution_kind = "unchanged"
legal_refs = ["ley-35-2006:art-22"]
source_refs = ["aeat-dr-100-2024-dictionary", "aeat-dr-100-2024-xsd"]
```

`from_revision != to_revision` is validated; `legal_refs`/`source_refs` must
cite what was actually consulted (they are the audit trail of the identity
claim); a `retired` record requires the id present in `from_revision` and
ABSENT from `to_revision`.

**Strict opt-in** — scalar in the revision's `revision.toml`, flipped when the
revision's declared surfaces are covered by evolutions:

```toml
continuidad_validation = "strict"
```

## Verification gates

```
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py -q
uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests -q -k "continuidad or locales_parity"
uv run --no-sync pytest --collect-only -q src/cadrumo/domain/calculations 2>&1 | tail -3
```

A stamped surface that drifts without a covering evolution record fails the
first gate under strict mode — that failure is the tool telling you which
evolution record is missing, not an obstacle to silence.

## Safety rails

- NEVER promote a chain because the dossier suggested it. The suggestion
  encodes text/structure similarity; identity is a legal judgment.
- NEVER "fix" a year-embedded label ("Vivienda habitual en 2020") while
  grounding — the official Spanish label is per-revision published text and
  moves only through the localization-cascade migration's reviewed path.
- A `repurposed` verdict is as valuable as an approved chain: it permanently
  protects against cross-year contamination. Record it, do not skip it.
- Partially-stamped chains (some occurrences stamped, some not) are
  inconsistencies to resolve first — the worklist flags them.
- Commit stamps + evolution records + strict flips for one modelo revision
  set together, with an explicit `git commit -- <pathspec>` naming only your
  files; never a bare commit in the shared worktree.
