---
name: aeat-continuidad-grounding
description: >-
  Ground casilla continuity chains: derive the candidate evidence
  programmatically, adjudicate identity against official AEAT/BOE sources,
  author the continuidad_id stamps and evolution records, and verify through
  the registry's strict cross-revision gates. Use when stamping chains,
  reviewing continuity candidates, or preparing the grounding worklist.
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
- A chain id is concept-named, never numeric, so it survives renumbering, and
  it MUST be a single plain segment — `^[A-Za-z0-9_-]+$`, max 128 chars. **Never
  put a dot in a chain id.** The localization cascade
  (`2026-08-04-modelo-localization-cascade-adr`) makes the chain id a segment of
  the shared locale key,
  `modelo.schema.<modelo>.casilla.continuidad.<chain-id>.<field>`, and
  `encode_modelo_locale_segment` base32-encodes any id that is not a plain
  segment. So `irpf-deduccion-galicia-otras` stays readable in every catalogue
  while `irpf.deduccion-autonomica.galicia.otras` becomes
  `x-d5p70phechim8tb3cdkmurhdc5qn8rredtmmior15pjm2r39cdkm2bjfehp62so`. Nothing
  refuses a dotted id — `ContinuidadId` still permits dots — so the damage is
  silent and only shows up as unreadable locale keys.
  Within that one shape, how you DERIVE the name depends on whether the
  casilla's `semantic_role` identifies exactly one box per revision:
  - **Role-unique → derive mechanically from the role**: lowercase, `_` → `-`,
    nothing else. `irpf_deduccion_galicia_otras` → `irpf-deduccion-galicia-otras`.
    Exact on all 3,159 occurrences measured 2026-08-05. Do not invent a prettier
    name.
  - **Role-ambiguous → hand-adjudicate an instance-keyed name, still flat**:
    when two or more casillas in one revision share the role, a role-derived id
    would merge distinct concepts into one chain. Key on whatever DOES identify
    the box — the event, the column, the distinguishing clause — joined with
    `-`, e.g. `irpf-aeip-centenario-del-hockey-1923-2023-aplicado`. The anexo-A
    family is the worked case: 71 boxes share `irpf_anexo_a_aeip_aplicado` and
    the ids repack yearly. (`dev/registry/aeip` still declares
    `CHAIN_PREFIX = "irpf.aeip."` — dotted, and therefore wrong under the
    cascade. Flatten it before that planner grounds anything.)
  Both errors are real: a role-derived id on a role-ambiguous chain silently
  merges two legal concepts, and a dotted id on any chain silently produces an
  opaque locale key.
- Evolution kinds are a closed set: `unchanged`, `label_evolved`,
  `legal_refs_evolved`, `label_and_legal_refs_evolved`, `repurposed`,
  `retired`. Two are safety-critical: `retired` ends a chain (the target
  revision MUST NOT declare the id — validated), and `repurposed` is an
  inheritance BARRIER: no value, translation, or carry crosses it.
- `label` is no longer stored on the casilla. The cascade removed the Spanish
  string from the schema; `CasillaDefinition.label` is now a property resolving
  `get_label("es")` through the shared catalogues, and the drift engine reads it
  by `getattr`, so cross-revision label comparison still works — it just compares
  resolved values now. **The consequence for `label_evolved`: a chain whose
  labels differ only by an embedded filing year is a transitional record.** The
  cascade's year-parameterized amendment represents that class (247 chains
  measured) as ONE locale value carrying a `{year}` placeholder under the
  continuity key, and `get_label` resolves with no `year` argument, so every
  revision returns the identical template and the drift disappears. Do not
  author `label_evolved` for a year-token difference expecting it to be durable
  — it covers drift the cascade is removing. `label_and_legal_refs_evolved` on a
  year-token chain likely becomes plain `legal_refs_evolved`. `retired` and
  `repurposed` are unaffected: they are about the id and the concept, not the
  wording.
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
repo root with `uv run --no-sync python` (read-only, seconds per run).

**They must run through the venv, not plain `python`.** The localization
cascade moved the Spanish label out of the casilla fragments, so a raw-TOML
walk cannot see it and every label silently compares equal. Measured against
the corpus on 2026-08-05: a raw-TOML worklist reported `T1=14, T2=1093, T3=0`
where resolving labels through the loader gives `T1=5, T2=752, T3=353` — 350
chains mis-tiered, 9 of them offered as rubber-stamps, and an entire tier
vanishing rather than reporting empty. Anything that reads a casilla field the
cascade relocated MUST resolve it through the loader, and an unresolvable
label must tier DOWN, never compare equal.

### 1. Tiered triage worklist (which chains, in what order)

Classifies every ungrounded multi-revision casilla id by review effort:
`T1-rubber-stamp` (label, core, legal refs all identical),
`T2-legal-refs-review` (only legal refs differ), `T3-wording-review`
(label diverges, core stable), `T4-full-adjudication` (core drifts —
renumbering suspect). Measured on 2026-08-05 after the M100/M180/M131 batch:
1,540 candidates = 5 T1 + 752 T2 + 353 T3 + 430 T4. Also flags
partially-stamped chains and labels that would not resolve.

```python
"""chain_worklist.py [--json out.json] -- easiest-first triage.

Run through the venv (`uv run --no-sync python chain_worklist.py`): the
localization cascade moved the Spanish label out of the casilla fragments, so a
raw-TOML walk can no longer see it. Tiering resolves labels through the same
loader the drift engine reads, and a label that will not resolve is reported as
`unresolved` -- never silently treated as equal, which would tier a
label-drifting chain as a rubber stamp.
"""

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from cadrumo.core.resources import resources

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
_UNRESOLVED = "\x00unresolved"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return _WS.sub(" ", text).strip().rstrip(".,;:")


def label_of(casilla) -> str:
    """Resolve the official Spanish label, or the unresolved sentinel."""
    try:
        resolved = casilla.get_label("es")
    except Exception:
        return _UNRESOLVED
    return norm(resolved) if resolved else _UNRESOLVED


rows = []
for definition in resources().modelos.authority.modelos:
    owners = defaultdict(dict)
    for revision_id, revision in definition.revisions.items():
        for casilla in revision.casillas:
            owners[str(casilla.id)][str(revision_id)] = casilla
    for cid, per in owners.items():
        if len(per) < 2 or all(c.continuidad_id for c in per.values()):
            continue
        labels = {label_of(c) for c in per.values()}
        cores = {tuple((f, str(getattr(c, f, None))) for f in CORE) for c in per.values()}
        infos = {tuple((f, str(getattr(c, f, None))) for f in INFO) for c in per.values()}
        legal = {tuple(c.legal_refs or ()) for c in per.values()}
        if _UNRESOLVED in labels:
            label_state = "unresolved"
        elif len(labels) == 1:
            label_state = "identical"
        elif len({_YEAR.sub("Y", v) for v in labels}) == 1:
            label_state = "year_token_only"
        else:
            label_state = "divergent"
        core_ok = len(cores) == 1
        label_ok = label_state in ("identical", "year_token_only")
        tier = (
            "T1-rubber-stamp" if label_ok and core_ok and len(legal) == 1
            else "T2-legal-refs-review" if label_ok and core_ok
            else "T3-wording-review" if core_ok
            else "T4-full-adjudication"
        )
        rows.append({
            "modelo": definition.id,
            "casilla_id": cid,
            "revisions": sorted(per),
            "label_state": label_state,
            "core_stable": core_ok,
            "legal_refs_stable": len(legal) == 1,
            "unvalidated_drift": sorted(f for f in INFO if len({dict(t)[f] for t in infos}) > 1),
            "partially_stamped": any(c.continuidad_id for c in per.values()),
            "tier": tier,
        })

order = {"T1-rubber-stamp": 0, "T2-legal-refs-review": 1, "T3-wording-review": 2, "T4-full-adjudication": 3}
rows.sort(key=lambda r: (order[r["tier"]], r["modelo"], r["casilla_id"]))
tally = defaultdict(int)
for row in rows:
    tally[row["tier"]] += 1
print(f"ungrounded multi-revision candidate chains: {len(rows)}")
for tier in sorted(tally, key=order.get):
    print(f"  {tier}: {tally[tier]}")
unresolved = sum(1 for r in rows if r["label_state"] == "unresolved")
if unresolved:
    print(f"  WARNING labels unresolved (tiered down, never rubber-stamped): {unresolved}")
partial = sum(1 for r in rows if r["partially_stamped"])
if partial:
    print(f"  WARNING partially-stamped chains: {partial}")
if out_path:
    out_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"worklist written to {out_path}")
```

### 2. Chain dossier (everything known about one candidate)

`uv run --no-sync python chain_dossier.py <modelo> <casilla-id>` prints every
occurrence's label/legal_refs/structural core, drift classification, a
SUGGESTED evolution kind (a hypothesis to verify, never a decision), existing
stamps and evolution records, and the localization keys the chain owns.
Positive control: run it on grounded `100 0063` — its suggestion must match the
authored `legal_refs_evolved` records (verified 2026-08-05: it does, against 12
existing records).

Read the localization-key section every time. It is where a dotted chain id
becomes visible: `0063` is stamped `irpf.inmueble.porcentaje-propiedad`, and the
dossier prints its continuity key as
`modelo.schema.100.casilla.continuidad.x-d5p70phed5n6qtb5c9m6abjgdtp66pbeehgmkp9de1p6us39cli62p0.label`.
Nothing refuses that id, so the base32 blob in this output is the only place the
damage shows up before it reaches four locale catalogues.

```python
"""chain_dossier.py <modelo> <casilla-id> -- everything known about one candidate.

Run through the venv (`uv run --no-sync python chain_dossier.py 100 0063`).
Labels resolve through the loader, never from raw TOML: the localization
cascade moved them out of the casilla fragments, and a raw read would report
every label as empty and therefore identical, suggesting `unchanged` for a
chain whose wording actually moved.
"""

import re
import sys
import unicodedata

from cadrumo.core.resources import resources

modelo, cid = sys.argv[1], sys.argv[2]
_WS, _YEAR = re.compile(r"\s+"), re.compile(r"(19|20)\d{2}")
# The strict validator's compared set, minus label/legal_refs which are
# classified separately below. Keep in step with
# _CROSS_REVISION_CASILLA_FIELDS in _cross_revision_divergence.py.
CORE = ("section", "data_type", "semantic_role")
# Unvalidated, but a renumbering tell worth seeing during adjudication.
INFO = ("number", "input_kind", "formula", "binding")
_UNRESOLVED = "<label did not resolve>"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return _WS.sub(" ", text).strip().rstrip(".,;:")


def label_of(casilla) -> str:
    try:
        return casilla.get_label("es") or _UNRESOLVED
    except Exception:
        return _UNRESOLVED


definition = resources().modelos.authority.modelo(modelo)
occ, evos = {}, []
for revision_id, revision in definition.revisions.items():
    for casilla in revision.casillas:
        if str(casilla.id) == cid:
            occ[str(revision_id)] = casilla
    evos += list(revision.casilla_continuidad_evolutions or ())
if not occ:
    sys.exit(f"modelo {modelo}: no occurrence of casilla id {cid!r}")

print(f"=== modelo {modelo} casilla {cid}: {len(occ)} occurrence(s) ===")
for rev in sorted(occ):
    c = occ[rev]
    core = {f: getattr(c, f, None) for f in CORE}
    info = {f: getattr(c, f, None) for f in INFO if getattr(c, f, None) is not None}
    print(f"\n[{rev}] stamp={c.continuidad_id!r}")
    print(f"  label: {label_of(c)}")
    print(f"  legal_refs: {list(c.legal_refs or ())}")
    print(f"  core (validated): {core}")
    print(f"  info (unvalidated): {info}")

labels = {rev: label_of(c) for rev, c in occ.items()}
core_ok = len({tuple((f, str(getattr(c, f, None))) for f in CORE) for c in occ.values()}) == 1
legal_ok = len({tuple(c.legal_refs or ()) for c in occ.values()}) == 1
lv = set(labels.values())
if _UNRESOLVED in lv:
    label_state = "UNRESOLVED -- do not tier this as stable; fix resolution first"
elif len(lv) == 1:
    label_state = "byte-identical"
elif len({norm(v) for v in lv}) == 1:
    label_state = "identical after normalise"
elif len({_YEAR.sub("Y", norm(v)) for v in lv}) == 1:
    label_state = "differs only by embedded year"
else:
    label_state = "SUBSTANTIVELY DIVERGENT -- adjudicate reword vs repurpose"
info_drift = sorted(f for f in INFO if len({str(getattr(c, f, None)) for c in occ.values()}) > 1)
print("\n=== drift classification ===")
print(f"  validated core stable:  {core_ok}\n  legal_refs stable:      {legal_ok}\n  label:                  {label_state}")
print(f"  unvalidated drift:      {info_drift or 'none'}  (no strict failure; a renumbering tell)")
tidy = label_state in ("byte-identical", "identical after normalise")
resolved = not label_state.startswith("UNRESOLVED")
suggestion = (
    "NO SUGGESTION -- labels did not resolve" if not resolved
    else "unchanged" if core_ok and legal_ok and tidy
    else "label_evolved" if core_ok and legal_ok
    else "legal_refs_evolved" if core_ok and tidy
    else "label_and_legal_refs_evolved" if core_ok
    else "NO SUGGESTION -- core drifts; suspect renumbering/repurposed"
)
print(f"  suggested evolution_kind (verify against official sources!): {suggestion}")

stamps = {c.continuidad_id for c in occ.values()} - {None}
mine = [v for v in evos if v.continuidad_id in stamps]
print(f"\n=== existing evolution records touching these stamps: {len(mine)} ===")
for v in mine:
    print(f"  {v.id}: {v.from_revision} -> {v.to_revision} [{v.evolution_kind}]")

print("\n=== localization keys this chain owns ===")
for rev in sorted(occ):
    for key in occ[rev].localization_keys or ():
        print(f"  {rev}: {key}")
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
