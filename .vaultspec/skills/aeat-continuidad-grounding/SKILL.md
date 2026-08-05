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
    the ids repack yearly. `dev/registry/aeip/manager.py:96` now declares
    `CHAIN_PREFIX = "irpf-aeip-"`, so that planner already emits the flat form.
  Both errors are real: a role-derived id on a role-ambiguous chain silently
  merges two legal concepts, and a dotted id on any chain silently produces an
  opaque locale key.
  Corpus state 2026-08-05: every chain id is flat. The eleven dotted Modelo 100
  pilots were converted in one pass (92 `continuidad_id` values across stamps and
  evolution records, 2 test files, and 88 locale leaves moved off their base32
  keys). There is no dotted backlog left and no second convention to copy — a
  dotted id appearing again is a regression, not legacy.
- Evolution kinds are a closed set: `unchanged`, `label_evolved`,
  `legal_refs_evolved`, `label_and_legal_refs_evolved`, `repurposed`,
  `retired`. Two are safety-critical: `retired` ends a chain (the target
  revision MUST NOT declare the id — validated), and `repurposed` is an
  inheritance BARRIER: no value, translation, or carry crosses it.
- **`section` drift is ungroundable.** The engine compares five fields but the
  kinds only cover two: `_evolution_covers_field` maps `label_evolved`→label,
  `legal_refs_evolved`→legal_refs, `label_and_legal_refs_evolved`→both. The only
  kind that covers `section` is `repurposed`, which asserts an inheritance
  barrier — the opposite of what a same-concept chain claims. So a chain with any
  `section`-drifting pair cannot be stamped under the current contract at all:
  it would produce a strict failure no record can close. Park it and say so;
  do not reach for `repurposed` to silence the gate. Measured 2026-08-05: 16 such
  chains in Modelo 100. Widening the kind set is an ADR question.
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

   For a legal-refs delta, the question that decides rubber-stamp versus
   adjudication is whether the delta is MONOTONE: does every later revision keep
   the earlier refs and add to them? A pure addition is the honest annual shape —
   a stable statutory article with that year's implementing orden layered on
   (`ley-35-2006:art-31` holding while HFP/1359/2023 → HAC/1347/2024 →
   HAC/1425/2025 rotate beneath it; or `orden-hac-277-2026:art-3` appearing across
   Modelo 100's 2025 revision). A delta that REMOVES or REPLACES a ref is not
   rubber-stampable: `art-66-2015` giving way to `art-66`, or
   `orden-hac-248-2021:art-10` to `orden-hac-265-2024:art-11`, is a displaced
   provision and needs checking against BOE per chain. Measured 2026-08-05 on the
   Modelo 100 tranche: 593 monotone, 19 not.
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
becomes visible, and nothing else refuses one. `0063` is the worked case: while
it was stamped `irpf.inmueble.porcentaje-propiedad` the dossier printed its
continuity key as
`...casilla.continuidad.x-d5p70phed5n6qtb5c9m6abjgdtp66pbeehgmkp9de1p6us39cli62p0.label`;
now that it is `irpf-inmueble-porcentaje-propiedad` the key reads back verbatim.
A base32 blob in this output means the id you just wrote is about to reach four
locale catalogues unreadable — it is the only warning you get.

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
- Chains still on the dotted form (the conversion backlog):
  `rg -oh 'continuidad_id = "[^"]*\.[^"]*"' src/cadrumo/_data/registry/aeat/modelos/ | sort -u`
- The anexo-A planner's naming, before hand-authoring an instance-keyed id:
  `dev/registry/aeip/manager.py` (`CHAIN_PREFIX`, and the slug builder at :254).

`dev.registry.migration.manager` was deleted with the cascade's migration
package; earlier revisions of this skill pointed at it for locale drift context.
Resolve labels through the loader instead — `casilla.get_label("es")`, as both
scripts above do.

## Authoring shapes (exact, from the live corpus)

**Stamp every occurrence** — one line in each revision's casilla fragment,
inserted immediately after `semantic_role`:

```toml
continuidad_id = "irpf-pf-modulos-1-unidades"
```

**Evolution records** — one record per DRIFTING pair, over ALL revision pairs,
each declared under that pair's own `to_revision`.

Two details here are easy to get wrong and both fail silently:

- *All pairs, not adjacent pairs.* `iter_cross_revision_casilla_divergences`
  compares every combination `(i, j)` of a chain's occurrences and skips any
  pair whose five-field signature matches. A six-revision chain that drifts at
  every step needs 15 records, not 5. Authoring only adjacent pairs leaves the
  non-adjacent ones uncovered, which reds the strict gate; authoring `unchanged`
  records for pairs that do not drift is harmless but pointless — the engine
  never yields them.
- *Declared under the pair's own `to_revision`, not the newest revision.*
  `_matching_evolution` searches only `left_revision` and `right_revision` for
  a record. A 2024→2025 record filed under `revisions."2026"` is invisible to
  the matcher and the pair stays uncovered. So a chain spanning 2024/2025/2026
  files its 2024→2025 record under 2025, and its 2024→2026 and 2025→2026
  records under 2026.

File one per `(to_revision, casilla, kind)` in that revision's `continuidad/`
directory, named `<casilla>-<from>-<to>-<kind>.toml` after the adjacent pair it
carries. `legal_refs` is the `to_revision` casilla's own refs; `source_refs` is
the `to_revision`'s revision-level source set.

```toml
[[revisions."2025".casilla_continuidad_evolutions]]
id = "m131-modulos-1-unidades-2024-2025-legal-refs-evolved"
continuidad_id = "irpf-pf-modulos-1-unidades"
from_revision = "2024"
to_revision = "2025"
evolution_kind = "legal_refs_evolved"
legal_refs = ["ley-35-2006:art-31", "orden-hac-1347-2024:art-4"]
source_refs = ["aeat-dr-131-2025", "aeat-modelo-131-procedure"]
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
uv run --no-sync pytest \
  src/cadrumo/domain/calculations/registry/tests/test_cross_revision_drift.py \
  src/cadrumo/domain/calculations/registry/tests/test_registry_locales_parity.py \
  src/cadrumo/domain/calculations/registry/tests/test_casilla_fragment_naming.py \
  src/cadrumo/domain/calculations/registry/tests/test_continuidad_completeness_ratchet.py \
  -q -m "integration or not integration" -p no:randomly -n 0
```

Run these sequentially (`-n 0`). Under `-n auto` the registry suite races its own
loader cache, and a peer landing registry fragments mid-run makes the same test
pass and fail in one session — re-run sequentially before triaging anything as a
regression.

A stamped surface that drifts without a covering evolution record fails the drift
gate under strict mode — that failure is the tool telling you which evolution
record is missing, not an obstacle to silence.

The ratchet gate is the one that will stop you: it pins the ungrounded backlog
per modelo to an exact committed baseline, so a grounding commit MUST lower its
modelo's entry in `_UNGROUNDED_BASELINE` in the same commit. The failure prints
the replacement literal. Lower only your own modelo — in a shared worktree the
count for another modelo can move because a peer's uncommitted work is in the
tree, and adopting their delta claims their progress under your commit. Confirm
by re-reading the affected files from HEAD before you touch a number that is not
yours.

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
- Park loudly, with a counted reason per bucket. A batch pass is judged by what
  it declined as much as by what it stamped, and a silent scope-out reads as
  completed work. The Modelo 100 tranche stamped 593 of 1,221 and reported the
  other 628 as 593 role-collision, 19 replaced-legal-ref, 16 `section`-drift.
  Never let a park bucket be inferred from a subtraction.
- Never stamp a chain that skips a revision, and never reuse the id across the
  gap: a chain asserts one concept running continuously, so the later concept
  takes a NEW grounded id. `_validate_cross_revision_contiguity` enforces this
  and a resuming chain now fails rather than passing silently.
- Never stamp a chain whose occurrences stop before the modelo's latest
  revision. Under strict validation the adjacent-pair check demands a `retired`
  record, and retirement-versus-renumbering is a legal judgment, not a batch
  step. Exclude those and report them as their own tier.
- Commit stamps + evolution records + strict flips for one modelo revision
  set together, with an explicit `git commit -- <pathspec>` naming only your
  files; never a bare commit in the shared worktree.
