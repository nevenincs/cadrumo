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
