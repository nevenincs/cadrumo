---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
related:
  - "[[2026-05-26-modelo-130-relation-regression-plan]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
---

# `modelo-130-relation-regression` audit: `art-110-5-corpus-fragment-gap`

## Scope

Plan step `P04.S15` (extend `[legal."rd-439-2007:art-110"].required_text`
with the BOE-verbatim art. 110.5 carry-forward sentence fragment)
investigated; this audit documents the corpus-state finding and
defers the required_text extension to a follow-up.

## Finding

The corpus normative source at
`src/aeat/_data/corpus/normatives/rd-439-2007.json#art-110`
contains paragraphs 1-4 of art. 110 (2679 chars). It does not
include explicit text covering the same-ejercicio prior-quarter
saldo-negativo carry-forward (no occurrence of "negativo",
"trimestres anteriores", "minorar", "compensar", or
"apartado 5" in the cached body). The corpus appears to predate
or be incomplete relative to the current BOE source for
RD 439/2007 art. 110.

`src/aeat/_data/corpus/normatives/ley-35-2006.json` likewise does
not contain the carry-forward fragment under any article.

## Disposition

The Modelo 130 carry-forward binding ALREADY cites
`rd-439-2007:art-110` as its legal_refs anchor, alongside three
other authoritative references (`orden-eha-672-2007:art-1`,
`ley-35-2006:art-99`, `rd-439-2007:art-95`). The legal grounding
chain is therefore intact for the binding-level audit trail.

The mechanism (casilla 17 negative -> saldo-negativo-fin-periodo
-> carry into casilla 15 the following quarter within the same
ejercicio) is documented in `aeat-modelo-130-instructions` cited
via `source_refs` on the binding and the per-casilla declarations.

The plan's `P04.S15` asked for a verbatim BOE fragment extension
to the legal entry's `required_text`. Because the BOE fragment is
not in the cached corpus and re-fetching is out of session scope,
S15 is closed with this audit as deferral evidence. Follow-up
work to re-fetch RD 439/2007 from BOE and extend `required_text`
with the art. 110.5 verbatim sentence is recommended but does not
block:

  - P04.S16 verification (selector + binding load cleanly).
  - P05 regression test suite (asserts runtime behaviour, not
    legal-text-fragment presence).

## Follow-up recommendation

Re-fetch `https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a110`
into the corpus pipeline, identify the carry-forward sentence in
the consolidated text, and extend
`[legal."rd-439-2007:art-110"].required_text` with the verbatim
fragment. Cross-check that the AEAT Manual de la Renta para
empresarios y profesionales 2025 cites the same article paragraph
to confirm the substrate.

---

## P07.S40 finding: M036 manifest informational-exclusion validated

S26 removed `vigencia` (M036 casilla declared with `input_kind =
"informational"`) from the calculation-completeness manifest. The
honesty review at 2026-05-27 questioned whether the fix matched
the architectural rule or just the test expectation.

**Resolution**: validated against the documented closure rule in
`_record_design.py:1299-1346` (`calculation_closure_numbers`
docstring). The calculation closure is the set of casillas the
engine traverses: formula targets, formula-expression refs,
formula/binding endpoints, verification operands. A casilla
declared with `input_kind = "informational"` and NO `formula` and
NO `binding` and NOT referenced by any formula expression and NOT
named as a verification operand is, by definition, outside the
closure.

`decl.vigencia-2025` carries `input_kind = "informational"`, no
`formula`, no `binding`, and is not referenced by any formula
expression or verification expectation in M036's revision. It is
correctly excluded from the calculation closure and therefore
correctly absent from the calculation-completeness manifest.

The S26 fix is architecturally sound; the manifest gate firing
on the prior `vigencia` entry was correctly catching real drift,
not a false-positive. No revisit needed.

---

## P07.S41 finding: registry-wide provisional_pending_specimen inventory

Sweep of every extraction profile across every modelo for the
`provisional_pending_specimen = true` flag and the
`src/aeat/tests/fixtures/justificantes/{modelo}/` specimen
inventory:

**Specimen coverage**: every modelo (M036, M100, M111, M115, M123,
M130, M131, M180, M184, M190, M193, M232, M303, M347, M349, M369,
M390, M720, M840) has at least one specimen PDF committed under
`src/aeat/tests/fixtures/justificantes/`. No modelo is missing a
specimen.

**`provisional_pending_specimen = true` flag set on**:

- `src/aeat/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/extraction_profiles/0005-extraction_profiles.toml`
- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2026/extraction_profiles/0001-extraction_profiles.toml`

All three modelos already have specimen PDFs in the fixtures
directory (M111: `2024-1T.pdf`, M130: `2021-2T.pdf`, M131:
`2024-1T.pdf`). Per `test_corpus_round_trip_gate.py`'s shape
test, the flag is opt-out (specimen + flag = OK; specimen
without flag = required round-trip; no specimen without flag =
hard fail).

**Disposition**: the flag on these three profiles is structurally
redundant (the specimen alone satisfies the gate). It may signal
that the specimen exists but is synthetic or unverified against
the corpus round-trip path — in which case the flag is the
author's deliberate opt-out from round-trip verification while
the specimen ages into authenticity. The flag is NOT a defect.

**Follow-up recommendation**: each of the three profiles should
either (a) remove the flag if the specimen is corpus-verified
and round-trips cleanly, or (b) keep the flag with a brief
comment explaining the specimen's provisional nature. Not
tracked as a new Step — author-driven authenticity review is
out of scope for a structural hardening sweep.

---

## P07.S38 finding: M131 carry-forward semantics validated against AEAT

The AEAT Modelo 131 instructions at
`src/aeat/_data/corpus/aeat_official/instructions/modelo_131/files/modelo-131-instrucciones.html`
declare the carry-forward rule for casilla 11 verbatim:

> Casilla 11. Si en la casilla 10 anterior se hubiera obtenido
> una cantidad positiva, se hará constar en la casilla 11 el
> importe (sin signo) de los resultados negativos que, en su
> caso, se hubieran obtenido en la casilla 15 de cualquiera de
> las autoliquidaciones anteriores, modelo 131, del mismo
> ejercicio y que no hubieran sido deducidos anteriormente,
> teniendo en cuenta que en ningún caso podrá figurar en la
> casilla 11 un importe superior a la cantidad positiva
> consignada en la casilla 10.

The registry binding lands:

- `source_modelo = "131"` — autoliquidaciones anteriores modelo 131 ✓
- `source_output = "saldo-negativo-fin-periodo"` — prior period
  saldo seed (formula: `max(0, -C10)`) ✓
- `source_period_offset_from_target = -1` — anterior (prior) ✓
- `max_year_delta = 0` — "del mismo ejercicio" same-ejercicio
  constraint ✓
- 1T suppression — 1T has no prior period in the same ejercicio ✓

**Verified**. The four M131 cap revisions (2019-2023, 2024,
2025, 2026) match the AEAT rule structurally.

**Discovered defect not in scope of S38**: the AEAT cap "en
ningún caso podrá figurar en la casilla 11 un importe superior
a la cantidad positiva consignada en la casilla 10" is NOT
enforced. The binding aggregates `op = "copy"` which strait-
copies the prior period's seed; if the seed exceeds the current
period's C10, the AEAT cap is violated. This is a verification-
predicate gap, not a binding-selector defect. Recommended
follow-up: declare a verification predicate that asserts C11 ≤
C10 when C10 is positive, OR clamp the binding via an
aggregation operator that caps to a current-period casilla
reference (no such aggregation op exists today). Tracked
informally here; the M131 calculation contract for the cap
rule needs its own ADR/plan if AEAT-cap enforcement is in scope
for a follow-up campaign.

---

## P07.S42 finding: M353.toml FileNotFoundError loader race

`load_modelo_file` (`src/aeat/domain/calculations/registry/_loader.py:123-128`)
calls `path.resolve()` then immediately `resolved.stat()`. The
caller `discover_modelo_sources` enumerates `*.toml` files via
`glob` and passes each path to `load_modelo_file`. The race
window: a parallel campaign deletes a `.toml` file (e.g.,
fragmenting `353.toml` into `353/manifest.toml` +
`353/revisions/<rev>/...`) between the `glob` enumeration and
the `stat()` call. The `stat()` raises `FileNotFoundError`; the
loader propagates it as `FileNotFoundError`, not as a typed
`RegistryLoadError`.

**Why it surfaced once**: the M353 fragmentation commit
(`42e9cd4dc`) landed during a 33-minute full-registry suite
run. The loader's `glob` had already enumerated `353.toml` (still
present at glob time); by the time the test's lazy
`_committed_registry_tree` call reached `353.toml`, the file
was gone. Fresh process reruns succeed because `glob` is
re-evaluated after the deletion.

**Why it didn't recur**: the race window is small and only
manifests under concurrent registry-tree mutation. The campaign
work after this discovery did not trigger another window
because no further mid-suite registry fragmentations landed.

**Disposition**: this is a shared-worktree operational hazard,
not a defect in the loader's design intent. Two mitigations
are recommended:

1. **Operational**: do not launch the full-registry-suite gate
   while peer campaigns hold uncommitted registry changes. The
   campaign coordinator should declare a freeze window around
   long gates.
2. **Code-level (optional, low priority)**: catch
   `FileNotFoundError` in `load_modelo_file` and re-raise as a
   typed `RegistryLoadError("modelo source disappeared between
   discovery and load: {path}")`. The error surfaces as
   typed-and-attributable rather than as a bare OSError; the
   underlying race is unchanged but the diagnostic is
   actionable. Tracked informally here; not authored in this
   campaign because the operational mitigation is sufficient
   and the code change touches a hot path.

The transient FileNotFoundError observed during the campaign
was correctly identified as race-condition-from-fragmentation,
not a regression caused by P03 or P07 work.

---

## P07.S43 finding: cross-campaign sweep commits audit

Audited the four sweep commits that absorbed campaign edits:

### `0ba779481` — sweep: cross-campaign auth/sede/formula-runtime WIP + corpus fixture regen

Touched 9 files including:
- `src/aeat/domain/calculations/registry/_formula_runtime.py`
  (60 lines): MY P03.S09-S11 work (bound-casilla input rejection
  with `resolve_bound_casilla_inputs` projection allowance).
  Diff verified against the campaign intent — no semantic delta.
- `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`
  (5 lines): MY P06.S25 fixture extension. Verbatim match.
- Plus corpus fixture regens for M100/M130/M303/M840 (binary PDFs)
  authored by other agents. Not my files; out of campaign scope.

**Verdict**: NO drift from campaign intent. The sweep absorbed
my edits cleanly.

### `1f2eb4b7e` — sweep: cross-campaign m130-relation plan + M100 cuota chain construct + 100-drift + M720 + tautology gate + fixture regens + scratch

Touched 12 files. Includes the M130 plan tracker (`vault plan
step check` re-canonicalisations of my P06 closures) and
multiple modelo fixture regens.

**Verdict**: NO drift. The plan tracker re-canonicalisations
preserved my Step-close intent; the modelo fixture regens are
out of scope.

### `451845d09` — sweep: application overview applicability (cross-campaign final)

1-line edit to `application/overview/_applicability.py`
swapping a private-import to the public registry surface — the
exact same edit I made for S24. The sweep landed it before
mine; no semantic delta.

**Verdict**: NO drift. (The shim was subsequently deleted by
my P07.S34 — same intent extended.)

### `dc6e6c63d` — exec: step record W05.P24.S91-S95 IVA classification enrichment

Pure documentation: a single `.vault/exec/` step record for an
unrelated cross-domain-continuity campaign. Did not touch any
file in my campaign's scope.

**Verdict**: NOT my campaign. Out of scope; included in the
list only because git history showed it interleaved with my
commits.

### `42e9cd4dc` — Registry hardening: fragment Modelo 131 revisions

Cross-campaign schema-hardening fragmentation: deleted 4 flat-
file `M131/revisions/<rev>.toml` files, created the per-domain
fragment directories. ABSORBED my P02.S08 cap-revision edits
into the new fragmented files — verified at the time as commit
`5d069ce6b` cite.

**Verdict**: NO drift. The fragmentation script preserved my
selector cap additions cleanly into the new file layout.

### Overall

The four sweeps absorbed my campaign edits cleanly with no
detected semantic drift. Trust-but-verify discharged. The
shared-worktree absorption pattern is operating as documented;
no rollback required.

---

## P07.S44 finding: tautology gate elevation strategy

The hand-summed-aggregation gate at
`src/aeat/domain/calculations/registry/test_tautology_gate.py::test_no_hand_summed_aggregation_tests_across_codebase`
runs in ~2 seconds in isolation. The gate kept re-firing during
P06 and P07 because new tests with the pattern landed from
parallel campaigns; the gate caught them at full-suite-gate
time, not at authoring time.

**Pre-commit hook elevation is rejected** per the user's
documented stance (memory note `prek_disarmed`: pre-commit
hooks are permanently off because prek's stash/pop pattern
destroys files in the shared worktree).

**Ruff plugin** would require authoring a custom ruff rule
(rust+config). High-cost for one gate; out of scope for a
hardening Step.

**Adopted strategy**: the gate is already fast enough (~2s) to
include in any pre-flight subset a dev runs locally. Documented
the explicit invocation in this audit as the recommended
authoring-time check:

```
uv run --no-sync pytest \
  src/aeat/domain/calculations/registry/test_tautology_gate.py::test_no_hand_summed_aggregation_tests_across_codebase \
  -q
```

Devs should run this command after authoring any aggregation
test. Operational discipline replaces process gate; the cost
of the failure mode (CI re-fire on long full-suite) is bounded
because the gate fires within 2 seconds of running the named
test.

The gate's defect-detection logic is unchanged; only the
authoring-time-feedback path is documented. A future
infrastructure investment (ruff plugin) is recommended once the
project has enough custom gates to justify the rust+config
overhead.
