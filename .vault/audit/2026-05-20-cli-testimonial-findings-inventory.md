---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger]]"
  - "[[2026-05-20-cli-testimonial-lucia]]"
  - "[[2026-05-20-cli-testimonial-marco]]"
  - "[[2026-05-20-cli-testimonial-diego]]"
  - "[[2026-05-20-cli-testimonial-sofia]]"
  - "[[2026-05-20-cli-testimonial-raul]]"
  - "[[2026-05-20-cli-testimonial-elena]]"
---

# CLI testimonial findings - consolidated inventory

Six human-persona agents operated the real `aeat` CLI with isolated
state to accomplish realistic tax tasks. This consolidates their
testimonials into one verified bug inventory. Findings marked
**[verified]** were reproduced directly against the live CLI by the
coordinator; **[transient]** marks shared-worktree mid-refactor
breakage that is not a stable defect.

## Personas and goals

| Persona | Goal | Goal met? |
|---|---|---|
| Lucia | First-time autonoma: set up, find obligations | No (blocked by crash) |
| Marco | Bookkeeper: import a quarter of transactions | Partial (import worked, then crash) |
| Diego | Self-employed: prepare Modelo 130 | Partial (calculation worked) |
| Sofia | Owner: "what do I file and when?" | No |
| Raul | Configure AEAT authentication | Partial |
| Elena | Company admin: Modelo 303 / 200 | Partial (303 calc worked) |

## What genuinely works

- **The calculation engine.** Diego's Modelo 130 produced coherent,
  arithmetically correct casilla values (01=18,500 -> 03=14,300 ->
  19=2,860 to pay). Elena's Modelo 303 draft calculated correctly.
  The core value proposition - compute a tax draft - functions.
- **Ledger import.** Marco's OFX import ingested 14 rows cleanly.
- **Profile creation, auth configure, modelo list/describe** all run.

## Stable bugs

### Blocker

1. **No deadline / filing-obligation surface anywhere.** [verified]
   `aeat app overview status` reports workspace state (movements,
   drafts) and next-command hints but **zero filing deadlines or
   obligations**; no `agenda`/`deadlines`/`calendar` command exists.
   Sofia's primary use-case - "what do I file and when?" - is
   unanswerable. Reported independently by Sofia, Diego, Lucia.
2. **`aeat config auth test` ignores the active profile.** [verified]
   With profile `reprouser` active, `auth test --provider certificate`
   returns `active_profile` empty, `active_profile_registered False`,
   `active_profile_record_present False`. The operator's primary
   auth-readiness check is broken.
3. **`verify` is unreachable: `NO_PENDING_OBLIGATION` with no CLI way
   to register an obligation.** (Elena) The create -> calculate ->
   verify -> file path dead-ends; there is no command to register the
   obligation that `verify` demands.

### Major

4. **`auth status` is self-contradictory.** [verified] After
   `auth configure --provider certificate` with no file:
   `configured: True`, `certificate_path` empty,
   `health_summary: certificate path not configured`. "Configured"
   and the health summary disagree.
5. **Calculation output omits legal grounding.** (Diego) The CLI
   calculate output carries no `legal_refs`, `source_refs`, or
   `formula_id`. This contradicts the project's calculation-grounding
   rule, which requires provenance on every operator-facing payload.
6. **`--help` flag names do not match the runtime flags.** (Diego,
   Elena) e.g. help shows `-retention`, runtime requires `-retencion`;
   Elena needed 6 such corrections. Help text is unreliable.
7. **`modelo list` is an unfiltered 26-row catalogue.** [verified]
   No "applies to your profile" filter; a non-expert cannot tell
   which modelos are theirs.
8. **No individual-vs-company profile discriminator.** (Elena) A
   company admin sees IRPF/personal fields; profiles do not model
   entity type.
9. **`work create` silently accepts an invalid period token** (`Q1`)
   that only fails later at `calculate` time. (Diego, Elena)
10. **Period token format is inconsistent** across subcommands
    (`Q1` vs `1T` vs `2026Q1`). (Lucia)
11. **Silent `profile create`.** [verified] Exit 0, zero output -
    silent success is indistinguishable from silent failure. (All
    personas.)

### Minor

12. Internal field names (`prompt_key`, `question_id`, `raw`) leak in
    NIF/CIF validation errors. (Lucia, Sofia, Marco)
13. Modelo 200 calculate output shows raw numeric casilla ids with no
    semantic labels. (Elena)
14. `auth configure --file` accepts non-existent paths silently;
    Cl@ve `identity_alignment: mismatch` is unexplained; locale
    leakage (Spanish `health_summary` under an English profile). (Raul)
15. `registry inspect` shows aggregate developer metrics, not
    per-modelo health. (Elena)

## Transient (shared-worktree mid-refactor breakage)

These are **not stable defects** - the shared worktree passes through
broken states while parallel campaigns refactor. Observed crashes:

- `ModuleNotFoundError: aeat.application.workflow._bucket_pointer_io`
  (Lucia, Marco) - resolved during the session when the owning
  campaign committed the missing module.
- `ImportError: cannot import name 'resources' from
  'aeat.core.resources'` (coordinator, live) - `_censo_modelos.py`
  imports a symbol mid-removal.
- `aeat.core.resources._registry` (Diego).

Not coordinator-owned code; not fixed here to avoid colliding with the
active refactor. They confirm the CLI import graph is fragile to the
in-flight `core.resources` / `workflow` restructure - worth a CI
import-smoke gate once those land.

## Assessment

Testimonial-driven verification surfaced a class of defect the
registry-data audits structurally could not: import-time crashes,
broken readiness checks, missing operator surfaces, help/runtime
drift. The calculation core is sound; the operator-facing shell around
it has real gaps - most importantly the absent deadline surface and
the unreachable verify->file path.

---

# Round 2 - deeper-path personas (2026-05-20)

Three further personas exercised paths the first round did not reach:
Teresa (export / filed records), Pablo (profile lifecycle / repair),
Nuria (deep ledger grooming). CLI confirmed healthy at dispatch
(import-smoke: 685 modules, 0 failures).

## Round-2 blockers

R2-1. **The `create -> calculate -> verify -> export` path is
unreachable.** [verified] `aeat app modelo work verify` dead-ends at
`NO_PENDING_OBLIGATION`, and there is **no CLI command anywhere in
`app` to register a filing obligation** (confirmed by command-surface
grep). Hit independently by Elena and Teresa. The tool can compute a
draft but cannot carry it through to a fileable/exportable state. This
is the central product-completeness gap. The `modelo export` command
itself is well-built - but structurally unreachable.

R2-2. **`profile rename` is non-atomic and corrupts the registry.**
[verified] `rename alpha beta` fails on a Windows SQLite file-lock
(`WinError 32` on `aeat.db`) AFTER registering `beta` - `profile list`
then shows both `alpha` and `beta`. The ghost profile cannot be
deleted (`profile delete` rejects it as unknown). **Exit code 0
despite the failure.**

R2-3. **`allocate --business-pct 1.0` silently downgrades BUSINESS to
MIXED** (Nuria) - a 100%-business allocation is silently recorded as
mixed-use, i.e. silent tax-treatment corruption.

R2-4. **`ledger attach` is unreachable** (Nuria) - no CLI surface
creates the blob/evidence id it requires.

R2-5. **`repair profile` loops on `missing_profile_record` without
repairing**, and **`repair reset-state --dry-run` crashes** [verified]
dumping a raw SQL fragment, exit 0. The recovery tooling does not
recover.

## Round-2 major

- `modelo readiness` reports `ready: True` while `verify` blocks the
  same profile - contradictory readiness signals (Teresa).
- M303 bindings are all `borrador_capable: False` - no declaration
  draft is generatable from the binding path (Nuria).
- `ledger view` does not surface classification / IVA / allocation
  state after grooming (Nuria); `allocate` without prior `classify`
  silently marks transactions reviewed.
- `repair reset-state --dry-run` should preview, not crash; creating a
  second profile silently switches the active context (Pablo).
- `AEAT_LIVE_TESTS_ENABLED` accepts `1` but not `true` (Teresa);
  `--force` export bypass absent; period tokens validated late.
- Spouse fields supplied at `profile create` are absent from
  `profile show` - no round-trip verification (Pablo).

## Cross-cutting themes (rounds 1 + 2, 9 personas)

1. **Failures exit 0.** `profile rename`, `repair reset-state`,
   `auth`-refusals all return exit 0 on failure - no script or wrapper
   can detect them. Systemic.
2. **Silent success.** `profile create` confirms nothing - every
   persona flagged it.
3. **Help / runtime flag drift.** `--help` flag names differ from the
   accepted flags across `profile create`, `modelo work`, export
   (Diego, Elena, Teresa, Pablo).
4. **Internal field leakage.** `prompt_key`, `question_id`, `raw`,
   raw SQL fragments surface in user-facing errors.
5. **The operator shell is thinner than the engine.** The calculation
   core is sound (M130, M303 compute correctly); the surrounding
   workflow - obligations, deadlines, verify->export, repair - has
   real holes.

## Disposition

These are verified findings, not speculation - the central blockers
were reproduced directly against the live CLI. They are recorded here
as an actionable inventory. Fixes were deliberately NOT applied in
this pass: the CLI / persistence / `core.resources` / `workflow`
layers are under concurrent refactor by other campaigns in this shared
worktree (the tree was observed in a broken import state mid-session),
so editing them now would collide. The inventory is the handoff.

---

# Coordinator verification corrections (2026-05-20)

Direct reproduction against the live CLI corrected/extended testimonial
findings - testimonials are evidence, not gospel.

## Correction: Diego's "legal refs absent from calculation output"

**Inaccurate as stated.** A successful `modelo work calculate` (130,
1T) JSON output *does* carry full provenance under `observations[]`:
`observations[].formula_id`, `observations[].legal_refs[]`,
`observations[].source_refs[]`. The flat `casilla_values` mapping omits
them - but that is by design (the calculation-grounding rule: the typed
`observations` list is the contract, the flat view is for human
readability). Diego likely inspected `casilla_values`, or his calc
errored on a missing binding before producing observations. The data
contract is satisfied. A residual *presentation* question remains
(does the default text renderer surface the observation provenance to
the operator?) - that is a UX gap, not a data gap. Severity downgraded
major -> minor (presentation).

## New finding: mojibake in error messages

[verified] `aeat --format json app modelo work calculate ...` on a
missing binding emits
`"message": "La vinculaciÃ³n ... no tiene valor asignado."`
- `vinculacion` is double-encoded (`Ã³` = the UTF-8 bytes of
`o-acute` decoded as latin-1). The locale source `src/aeat/locales/
es.yml` is correct, valid UTF-8 (`vinculaci\xc3\xb3n`); the corruption
is introduced downstream between locale read and JSON emit. Spanish
accented characters in user-facing error messages render as mojibake.
Severity: major (every accented Spanish error string is affected;
`test_windows_encoding.py` confirms CLI encoding is a known fragility).

## New finding: no pre-flight binding check before calculate

[verified] confirms Diego - `modelo work calculate` fails one missing
binding at a time (`irpf.previous_year_economic_activity_net_income`
surfaced only on the calculate attempt). A preflight that lists all
unsatisfied bindings up front would save round-trips.
