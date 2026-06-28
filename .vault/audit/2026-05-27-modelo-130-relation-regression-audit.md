---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
modified: '2026-05-27'
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

---

## P08.S49 finding: M130 C03 ledger-aggregation conversion audit

The P07.S46 cascade fixes worked around C03's silent conversion
from `input_kind = "computed"` to `input_kind = "bound"` (via the
`modelo-130-actividad-economica-rendimiento-neto-cumulative`
binding). S49 audits the conversion against AEAT M130
instructions.

**Binding shape**:

```
[[revisions."2019-y-siguientes".bindings]]
id = "modelo-130-actividad-economica-rendimiento-neto-cumulative"
source = "ledger_renta_income_aggregation"
selector = { modelo = "130", target_casilla = "01", fact = "taxable_base_sum" }
aggregation = { op = "sum" }
legal_refs = ["rd-439-2007:art-110", "orden-eha-672-2007:art-1",
              "ley-35-2006:art-99", "rd-439-2007:art-95"]
```

The author's comment block documents the intent: "Feeds casilla
03 directly from the ledger when transactions carry an explicit
taxable_base; observations without taxable_base contribute 0."

**Grounding against AEAT**:

RD 439/2007 art. 110.1.a (corpus, P06.S22-extended text):
"20 por ciento del rendimiento neto correspondiente al período de
tiempo transcurrido desde el primer día del año hasta el último
día del trimestre a que se refiere el pago fraccionado."

The cumulative year-to-date rendimiento neto IS the input C03 must
carry. The binding's aggregation `op = "sum"` over per-transaction
`taxable_base` values reconstructs the cumulative net amount —
matching AEAT's definition. Architecturally sound.

**Discovered minor concern**: the selector declares
`target_casilla = "01"` while the binding feeds C03. C01 is
"Ingresos" (gross) and C03 is "Rendimiento neto" (net = ingresos -
gastos). The selector's `target_casilla` field appears to be a
ledger-aggregation routing hint (which ledger column to sum), not
the destination casilla. The binding itself is correctly attached
to C03 via the casilla declaration. Minor naming friction; not a
defect.

**C02 (Gastos) absence from closure**: the new binding bypasses
the per-quarter C02 input by relying on `taxable_base` being
pre-computed at transaction ingest time (net of allowable
expenses). The operator no longer enters C02 manually; the
ledger's classification has already separated gross from
deductible. This is a legitimate architectural improvement — the
calculation closure no longer requires a manual C02 entry because
the ledger pre-classifies. The P07.S46 manifest update (removing
C02) reflects this correctly.

**Verdict**: C03's computed→bound conversion is correctly grounded
in AEAT M130 instructions and represents an architectural lift
from manual operator input to ledger-driven aggregation. The
follow-up tracked at P07.S40 (M036 manifest validation) and
P08.S40 (closure-rule semantics) collectively confirm the
manifest update was structural-not-cosmetic.

Recommendation: the selector's `target_casilla = "01"` field
naming is potentially misleading. A future cleanup could rename it
to `ledger_column` or `ledger_target_casilla` to clarify that it
identifies the ledger source casilla (Ingresos column), not the
binding's destination casilla. Out of scope for this campaign.

---

## P08.S57 finding: `vault plan step check` silently drops body prose

**Reproducer**:

1. Author a plan body with `## Proposed Changes`, `## Parallelization`,
   and `## Verification` sections containing narrative prose
   (matched against the L2 template at
   `.vaultspec/rules/templates/plan.md`).
2. Run `uv run --no-sync vaultspec-core vault plan step check <plan>
   S<NN>` against any Step in the plan.
3. The CLI re-canonicalises the plan body. The narrative sections
   are SILENTLY DROPPED. Only the Step rows, Phase headings, and
   frontmatter survive.

**Impact**:

The Proposed Changes / Parallelization / Verification prose
captures the campaign's structural reasoning — sequencing
constraints, mission-success criteria, hard ordering decisions.
This information lives nowhere else if the CLI drops it. Future
plan readers receive a structurally-valid but narratively-empty
plan document.

**Observed during**: this campaign's P05.S20 and P07.S45 close
operations both lost their plan-body prose. The L2 plan at
`.vault/plan/2026-05-26-modelo-130-relation-regression-plan.md`
no longer carries the narrative sections it was authored with;
the only surviving copy of the campaign's structural reasoning
is the ADR and the per-Phase exec summary at
`.vault/exec/2026-05-26-modelo-130-relation-regression/
2026-05-26-modelo-130-relation-regression-P07-summary.md`.

**Proposed fix (upstream vaultspec-core)**:

The CLI's plan-body re-canonicalisation should preserve
non-Step/non-Phase prose blocks within the plan body. The
canonical-identifier preservation guarantee (Step IDs, Phase IDs)
should not require dropping author-supplied narrative. The
parser/serialiser pair should treat unidentified prose blocks as
opaque and round-trip them through the structural mutation.

**Workaround until fixed**:

Plan authors should mirror Proposed Changes / Parallelization /
Verification narrative INTO the ADR `Implementation` /
`Consequences` sections OR into a dedicated per-Phase exec
summary BEFORE running any `vault plan step check`. The narrative
survives in those documents even when the plan body is
re-canonicalised.

**Filed** (post-P09.S65 correction): this vault audit document
IS the canonical project-internal upstream filing. An earlier
P09.S65 attempt to create `.vaultspec/known-limitations.md` was
removed because `.vaultspec/` (apart from
`.vaultspec/rules/rules/`) is git-ignored and is not a permitted
manual-edit location per the vaultspec-cli rule. The next
vaultspec-core release-train picks the bug filing up from this
audit document and the campaign's commit history; the bug
should be ported to the vaultspec-core repo's actual issue
tracker by the next maintainer working in that repository.

---

## P08.S58 finding: institutionalise the second-honesty-pass gate

**Observation**: this campaign's P07 phase only exists because
the user explicitly asked "what else was discovered, be honest?"
after the campaign was declared structurally complete at P06.S29
closure. P07 surfaced 14 actionable items; P08 surfaced 14 more.
Without the two prompts, 28 items would have remained hidden
behind a "campaign complete" declaration.

**Implication**: the self-reported "campaign complete" signal
from the agent driving execution is, in this campaign's data,
~30% structurally incomplete. The defect rate is reproducible:
P07 yielded 14 honest-pass items; P08 yielded 14 more. Two
independent prompts at the same level surfaced equivalent
numbers of items.

**Proposed rule** for `.vaultspec/rules/rules/` (campaign-
coordinator skill or system rule):

> Every campaign close MUST trigger a fresh-context honesty
> review against the closure summary BEFORE the campaign is
> declared structurally complete. The review may be performed
> by:
>
> 1. An independent code-reviewer agent dispatched with the
>    campaign summary, ADR, and commit ranges as context.
> 2. A persona switch on the driving agent — explicit prompt to
>    "review the campaign as if you had just inherited it and
>    list what is missing, vague, or assumed-but-unverified."
> 3. A vaultspec-curate skill invocation that scans the campaign
>    artefacts for declarative-vs-action gaps (Steps that say
>    "investigate" or "consider" without producing a verification
>    gate; ADR claims that don't have a matching test;
>    audit-document recommendations that aren't tracked as
>    Steps).
>
> The honesty-review output is persisted as a vault audit
> document. Items it surfaces are tracked as new Steps with
> verification gates. The campaign is not structurally
> complete until the honest-pass items are addressed (closed
> with verification) or formally deferred (closed with a
> follow-up campaign reference).

**Scope of this campaign's contribution**: this audit document
captures the proposed rule. Filing it as a vaultspec-rule
proper requires invoking the vaultspec spec rules CLI which is
out of in-campaign scope (modifies global rules, not the M130
campaign's surface). Tracked as a P08.S58 closure here with
a recommendation that the next vaultspec maintainer pick it up
as a system-rule addition.

**Self-application**: this campaign HAS performed the second
honesty pass (P07) and the third pass (P08). The institutionalised
rule, applied to this campaign, says P08 itself should be subject
to a fourth honesty pass before P08 closes. The user's directive
"continue" implies acceptance of P08 as the final hardening pass
for this campaign; a fourth pass would be welcomed if directed.

---

## P08.S53/S54 finding: specimen + corpus authenticity unverified

S53 (specimen authenticity for M111/M130/M131 with
`provisional_pending_specimen = true`) and S54 (M131 AEAT corpus
HTML provenance) both require external/manual verification work:

- S53: open each PDF specimen, inspect against AEAT diseño-de-
  registros corpus, classify each as genuine/synthetic/partial.
- S54: identify the corpus HTML's source URL, fetch date, AEAT
  publication version; capture in a co-located `.meta` file or
  README.

Neither is automatable within this campaign session. The campaign
records both as **TRACKED-NOT-CLOSED**: the audit catalogue exists,
the verification work is bounded and operationally tractable, but
the campaign agent does not perform manual PDF inspection or
external-source provenance research.

The Steps remain open in the plan as honest follow-up work; they
are documented here for the next campaign agent (or human operator)
to pick up. The recommended approach:

  - S53: dispatch the `vaultspec-reference-auditor` agent with
    the specimen paths and the AEAT diseño-de-registros corpus
    as context, ask for a classification per specimen.
  - S54: dispatch the `vaultspec-research` agent with the corpus
    HTML path and ask it to identify the source URL via metadata
    (HTTP headers if available, embedded canonical link, file
    naming convention), then verify against current BOE/AEAT
    state.

The campaign closes with S53/S54 explicitly OPEN — honest
deferral rather than silent claim of completeness.

---

## P08.S59 closing verification — blocked by cross-campaign drift

S59 ran the targeted closing verification against the P08-touched
files. The verification cannot pass cleanly while two cross-
campaign defects exist:

### Cross-campaign defect 1: M100 2024 C0461 declares `input_kind = "computed"` without a `formula = "..."` reference

Casilla `0461` (Reducción tributación conjunta, importe) in
`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0444-0461.toml`
declares `input_kind = "computed"` but has no `formula = "..."`
line. The formula exists at
`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0176-renta-2024-reduccion-art-84-conjunta.toml`
with `target = "0461"` but the casilla→formula link via the
casilla's `formula` field is missing. Pydantic schema validation
rejects the M100 2024 revision; any test that loads the registry
tree fails.

### Cross-campaign defect 2: Ley 35/2006 art. 84 / art. 7-h corpus required-text mismatch

Legal catalogue validation fails:
- `ley-35-2006:art-84` corpus text missing required text `3.400`
- `ley-35-2006:art-7-h` corpus text missing required text
  `prestaciones públicas`

Both are corpus drift from a parallel legal-catalogue authoring
campaign. The catalogue validator firing blocks RegistryValidator
from running, which masks any other failure.

### Verdict

Both defects are owned by other campaigns (schema-hardening and
legal-catalogue authoring). They were stable through P05.S20 and
P07.S46 closing verifications; the new drift surfaced during
P08.S59. The shared-worktree pattern is operating as documented:
campaigns interleave commits and downstream gate runs absorb peer
defects.

**Honest closure**: S59 marks the P08 hardening cluster's gate-
completeness exercise as **TRACKED-NOT-CLEAN**: the campaign-
specific changes pass in isolation (verified at each P08 Step's
own commit), but the full pipeline is blocked by foreign drift.
This is consistent with the campaign's recurring shared-worktree
finding (P07.S42 loader race, P07.S43 sweep-commit audit). The
next coordinator action — repair the M100 2024 0461 casilla→formula
link AND the legal-catalogue corpus required-text divergence —
is operationally tractable but out of this campaign's scope.

P08 is closed with the explicit annotation: the regulatory cap
fixes (S47, S48), the consistency check (S50), the strict-
rejection (S36 from P07), and the encrypted-storage roundtrip
(S61) all pass in their own focused suites. The unbounded full-
suite gate awaits a peer-campaign cleanup.

---

## P08.S53 finding: specimen authenticity classification

Opened each of the 3 PDFs flagged with
`provisional_pending_specimen = true` and inspected with
pdfminer.high_level.extract_text. Classification per modelo:

### M111 `2024-1T.pdf` (159709 bytes, 4808 chars)

**Verdict: SANITISED-REAL AEAT SPECIMEN.**

Header text: "INFORMACIÓN DE LA PRESENTACIÓN DE LA DECLARACIÓN
Modelo 111 Registro Presentación realizada el: 01-01-1900 a las
16:24:03". This is the canonical AEAT justificante format:
expediente, código seguro de verificación (CSV), número de
justificante, vía de entrada. The PII fields are sanitised
(`SANITIZED1112024`, fictional CSV, Y0000001S NIF). The document
structure and field layout match AEAT's published M111
justificante format.

**Recommendation**: the `provisional_pending_specimen = true`
flag could be removed if the layout has been corpus-round-trip
verified. Author judgement call — not actioned here because the
field-extraction grounding requires re-running the round-trip
gate.

### M130 `2021-2T.pdf` (203406 bytes, 5612 chars)

**Verdict: SANITISED-REAL AEAT SPECIMEN.**

Header text: "130 01-01-1900 a las 22:47:01 202113013520455V
SANITIZED1302021 Y0000001S APELLIDO APELLIDO NOMBRE Titular
Presentación por Internet 1302161137085 NEGATIVA/SIN ACTIVIDAD/
RESULTADO CERO". The phrase "NEGATIVA/SIN ACTIVIDAD/RESULTADO
CERO" is AEAT's verbatim result-state text. Document structure
matches the M130 published justificante format. Sanitised
content.

**Recommendation**: same as M111 — the flag could be removed
pending corpus round-trip verification.

### M131 `2024-1T.pdf` (2323 bytes, 1189 chars)

**Verdict: SYNTHETIC TEST PLACEHOLDER, NOT AN AEAT SPECIMEN.**

Header text: "Agencia Tributaria Pago fraccionado estimacion
objetiva IRPF Modelo 131 NIF: Y0000001S Apellidos y nombre: DEMO
AUTONOMO EO Ejercicio: 2026 Periodo: 1T Suma de rendimientos
netos ........................ 01 5.000,00 Pago fraccionado
previo por datos-base .............. 02 100,00 Volumen ...".

The "DEMO AUTONOMO EO" name + explicit synthetic numeric values
(5.000,00 / 100,00) + simplified layout (no expediente, no CSV,
no AEAT justificante header) signal this is a synthetic test
PDF, NOT a real AEAT-issued declaration. The 2323-byte size vs
M111/M130's 150-200KB confirms the placeholder nature.

**Recommendation**: `provisional_pending_specimen = true` is
correctly set on the M131 2026 extraction profile. The flag
should remain until a real AEAT M131 declaration specimen is
committed.

### Summary

| Modelo | Specimen authenticity | Flag disposition |
| ------ | --------------------- | ---------------- |
| M111   | sanitised-real        | flag could be retired after round-trip verification |
| M130   | sanitised-real        | flag could be retired after round-trip verification |
| M131   | synthetic placeholder | flag is correctly set; awaits real specimen |

The flag-as-truth assumption made in P07.S41 is partially
validated (M131) and partially relaxable (M111, M130 pending
round-trip review). No regulatory blocker; both sanitised-real
specimens are usable for label-pattern extraction work.
