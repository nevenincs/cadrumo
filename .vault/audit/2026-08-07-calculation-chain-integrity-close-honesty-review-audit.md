---
tags:
  - '#audit'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:eb761dc014e0a23024b7dab930f72eefb1b22ebcb8d9da5d74a7eec6896a0335'
related: []
---
# `calculation-chain-integrity` audit: close honesty review

Run as a persona switch on the driving agent, per the campaign-close rule's second option: the campaign re-read as if inherited cold, with claims probed mechanically rather than recalled. Written before the campaign is declared structurally complete, which is the point of the gate.

The mechanical probes came back clean. The reading did not.

## Scope

Every step, exec record and decision record carrying the `#calculation-chain-integrity` tag, read against the tree at HEAD. Mechanical probes over the plan (scope-touched, hedging language, exec-record coverage) plus a reading pass over the ADRs the campaign's steps were meant to execute.

### What the probes cleared

- **57 of 57 steps closed**, and every closed step's named scope path was genuinely touched today. Zero steps checked against untouched code.
- **No hedging rows.** No closed step still says *investigate*, *consider*, *assess whether*, or *if needed* — the declarative-vs-action gap the rule names is absent.
- **Exec records complete**, after this pass. `vault plan status` flagged `S44` as checked with no execution record; it now has one, written from the commit and the code at HEAD rather than from memory.

## Findings

### FINDING-1 (critical): the shipped activity axis contradicts its own governing ADR

`2026-08-07-calculation-chain-integrity-activity-type-placement-adr` considers exactly the placement `W03.P05.S11` shipped, and **rejects it**:

> **B. A per-transaction marker beside `irpf_category`** … Accepted in part, and only as a REFERENCE. … Carrying the activity TYPE VALUE on the transaction is rejected: the type is a fact AEAT records per activity slot, so copying it onto every row duplicates an upstream declaration and will drift from it.

Its accepted shape is option E — the value lives on a per-activity profile row, and the transaction carries a *reference* to the slot. What shipped is `tipo_actividad: TipoActividad | None` on `Transaction`: the value, on the row.

I did not read this ADR before implementing. The step record for `S11` argues the per-row placement from first principles and never mentions that a decision record had already considered and refused it. That is the failure worth naming: the campaign's own discovery discipline was applied to code and skipped for decisions.

**Mitigating, and stated so it is not read as an excuse.** Both ADRs are `proposed`, not accepted. Option E depends on `2026-07-26-multi-activity-profile-adr`, also `proposed`, and no profile activity row exists in the tree — a grep for an activity-row model returns nothing. So the ADR's own Constraints section says the build is "blocked until that record is accepted or its row model is otherwise settled". A step that waited for it would have shipped nothing, and `S13` would still be blocked behind it.

**The hazard is real and dated.** Today there is no upstream declaration, so nothing is being duplicated and nothing can drift. The moment the multi-activity profile lands, `Transaction.tipo_actividad` becomes a second home for a fact the activity slot owns — precisely the drift the ADR predicts. It is not wrong now; it is wrong later, silently, unless someone is told.

### FINDING-2: the ADR's blocking constraint is closed, and the ADR does not say so

The same ADR carries a Constraints paragraph requiring, before any rate mapping is implemented, that someone establish

> whether AEAT's *Tipo de actividad* code set discriminates profesional, agrícola/ganadera, forestal and objetiva at the granularity RIRPF art. 95 requires, including the engorde de porcino y avicultura carve-out.

`S37` and `S38` answered it: the code set discriminates three of the four, and **not** the engorde carve-out, because the table's finest livestock grain is `B02`. The ADR's own fallback then applies — "a mapping … must be grounded and declared in the registry rather than inferred in code" — and that is exactly what the `rirpf-art-95:selector-m036-*` parameters are.

So the campaign satisfied the constraint and left the record saying it is open. A reader of the ADR alone would re-do the work.

### FINDING-3: deferrals that hand work onward with no receiving plan

Five closed steps defer real work. Three are properly tracked; two are not:

| deferral | tracked? |
|---|---|
| `S30` — ADR awaiting an operator ruling | yes, owned by `llm-invoice-read-reconciliation` |
| `S11` — profile-side placement | now FINDING-1 |
| `S22` — extraction of 11 over-budget modules | no receiving plan |
| `S46`/`S47`/`S56` — M390 annual under-modelling | research doc exists, **no plan** |

`S47` produced a scoping research document with a candidate ordering and a stated dependency, and nothing carries it forward. `S56` then routed its remaining work to that non-existent campaign. A scoping document with no successor is the "recommendations that aren't tracked" shape the rule names.

### FINDING-4: a gate running at 81 % of its ceiling

A cold registry load measures **48.7 s** against the loader-cache isolation test's 60 s subprocess ceiling. It passes in isolation and reds whenever the machine is loaded, which is most of the time in this worktree. Not caused by this campaign's four small TOML files — but this campaign added to a tree where it is now the norm rather than the exception, and an intermittently-red gate teaches people to ignore it.

### What is NOT a finding

Three things looked like findings and did not survive checking.

- **The duplicate exclusion set** (`INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE` in `core` and the registry parameter) is a deliberate two-home design with a parity test binding them, following the binding-source taxonomy's shape. Declared, gated, not drift.
- **`ConceptoIngreso` versus `OperationKind347.SUBSIDY`** share a subject and answer different questions — one is a Modelo 347 clave about an operation with a counterparty, the other is a statement about base inclusion. Checked by reading both, not by name.
- **The two opposite defaults** on the M131 filters read as an inconsistency and are not: each points away from the worse error for its own axis, and both directions are asserted in tests.

## Recommendations

**FINDING-1 — actioned.** `src/cadrumo/tests/test_tipo_actividad_single_home.py` asserts that exactly one production field stores a `TipoActividad`, and its refusal names the ADR and the two readers to repoint. Mutation-proven: adding a second stored field reds it with that message; the probe was reverted and the gate is green. The check is structural rather than keyed on the future row model's name, which has none agreed.

**FINDING-2 — actioned.** The ADR carries an amendment recording that its grounding constraint is discharged by `S37`/`S38`, that the answer was *three of four boundaries and not the engorde carve-out*, that the registry fallback it specifies was the path taken, and that its placement ruling was violated rather than revised.

**FINDING-3 — formally deferred, with the deferral made visible.** The M390 annual under-modelling has a scoping research document and no receiving plan; `S56` routes work to a campaign that does not exist yet. The over-budget extraction from `S22` is in the same state. Neither is invented here as a plan, because authoring a campaign nobody has scheduled is how a plan corpus fills with fiction — but the absence is now written down where the next reader of either step will meet it.

**FINDING-4 — reported, not owned.** The 60 s ceiling belongs to the loader-cache test, and the 48.7 s load belongs to the whole tree. This campaign is not the cause and is not the right owner; what it can do is put the number on the record so the next intermittent red is recognised rather than re-diagnosed.

### On the pattern

The recurring shape across this pass is not carelessness in the code — the mechanical probes were clean — it is that decision records were not searched the way code was. `FINDING-1` is that failure exactly: a mandatory semantic sweep before writing a symbol, and no equivalent habit before making a placement choice a record had already made. The campaign's own rule corpus requires searching `--type vault --doc-type adr`, and this campaign did that for grounding questions and not for design ones.

That is the item worth carrying forward, and it is worth more than the four findings it produced.
