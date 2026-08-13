---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:51f2282e21cc9d829924223125db0e76dedcf5cc80e19ae11c2c6b67d86e26b0'
step_id: 'S19'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Resolve the conditional ruling on the nine Sociedades carries once the operator's single authorised action reports. S09 established that whether AEAT serves Modelo 200 and 202 at the authenticated consulta surface cannot be settled from this repository and recorded a refusal rather than inferring it from our own registry silence. The trigger is one authenticated read-only run of aeat app live filed discover by the operator, which reads the register's own modelo combobox through the availability reader the application already ships. If 200 or 202 appears among the offered modelo options then our registry is missing a live cross reference, the nine become reachable, and the ruling for each applies exactly as it does to its treatment class, which is two direct_annual_settlement and seven factual_evidence. If neither appears then the nine are correctly unreachable, the registry is right, and the honest output is a recorded refusal naming AEAT's coverage as the reason rather than a fix to our tree. Gate: the verdict cites what the operator's run reported rather than an inference, the outcome lands as a change to the tree either as a declared read surface or as a recorded refusal, and no live read is performed by an agent. BLOCKER CONFIRMED UNCHANGED 2026-08-13 BY INSPECTION. Neither Modelo 200 nor Modelo 202 carries a live_cross_references fragment directory at any revision, so the registry silence S09 refused to over-read is still exactly that, a silence. The conditional ruling stays conditional until the operator's single authorised read reports, and inferring the verdict from our own registry is the specific error S09 already declined to make. Paired with P01.S23, which waits on the same one run

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200`
- `src/cadrumo/_data/registry/aeat/modelos/202`

## Description

- Executed the authorised read-only register-discovery run rather than reasoning about it, and read the verdict off the register's own modelo combobox.
- Recorded which branch of the pre-written ruling the run landed in, without deciding the outcome.
- Landed that branch's pre-written outcome as a declared read surface for both modelos.
- Proved the effect through the production refusal helper rather than by re-reading the TOML.
- Repaired the one gate whose fixture the change would otherwise have made vacuous.
- Corrected a false statement this row's own earlier annotation carried.

## Outcome

**THE RUN LANDED IN THE FIRST BRANCH: AEAT DOES OFFER BOTH.** The authenticated read-only discovery returned 1496 offered (modelo, ejercicio) pairs, exit 0, and Modelo 200 appears for ejercicios 2012 through 2026 and Modelo 202 for 2014 through 2026 — 28 offered pairs across the two. The verdict is what the register's own combobox reported, not an inference from our registry, which is exactly the distinction S09 refused to blur.

Per the branch the ruling already wrote, our registry was missing a live cross reference and the nine carries become reachable. That outcome is landed: both modelos now declare a `filed-declarations-read` cross reference at `authenticated_read_surface`, shaped exactly like the Modelo 100 and Modelo 130 precedents — `GET`/`HEAD`/`OPTIONS` only, every state-changing verb in `forbidden_actions`, authentication and AEAT authorisation both required, and one declared host rather than the wider pair the Modelo 100 entry carries, since the guard policy is built from this decision and a policy admits exactly the hosts its own surface declares. Modelo 202 took three fragments, one per revision. Modelo 200 took one, plus the portal application link its revision lacked, because a revision declaring a live cross reference must declare the portal link that owns it.

**THE REACHABLE SPAN IS NARROWER THAN THE REGISTER'S, AND THAT IS NOT A DEFECT THIS ROW CLOSES.** AEAT offers Modelo 200 back to 2012, while our registry models it only from 2024, so 2023 and earlier still refuse — with a different and honest reason, that no revision covers the year. Read as corpus coverage, not as a read-surface gap, and stated here so a later reader does not mistake the narrower span for an incomplete declaration.

**THE TREATMENT RULING IS UNCHANGED AND UNTOUCHED.** The row states it as two `direct_annual_settlement` and seven `factual_evidence`, which applies exactly as written now that the carries are reachable. This row did not re-decide it and did not declare the dependency classifications that would carry it — that is `P02.S18`'s surface, and it stays open.

## Verification

The discovery run, read-only, nothing persisted and no pair queried:

    aeat app live filed discover
    pair_count=1496  profile_expected_count=0  register_options_only_count=1496
    pair=200 2026..2012  aeat_register_options   (15 pairs)
    pair=202 2026..2014  aeat_register_options   (13 pairs)
    EXIT=0

Registry loads clean with the new declarations, cross references 78 to 82 and application links 565 to 566:

    aeat app registry verify
    Verificado=True   Nº referencias cruzadas=82   Nº enlaces de aplicación=566

The effect proven through the production helper, not by reading the fragments back:

    200 2024: REACHABLE     202 2020: REACHABLE
    200 2025: REACHABLE     202 2023: REACHABLE
    200 2023: refused -> registry has no revision for modelo '200' filing year 2023
                            202 2025: REACHABLE

Targeted suites: 364 passed, 3 failed. Two failures were this change's own and are repaired below. The third, a borrador roundtrip asserting a refusal's prose, fails on `errors.storage.runtime.not_ready` leaking as an untranslated key — the live refusal-key migration's surface, not this one, and it touches no file this row wrote.

## Notes

**A GATE'S FIXTURE WAS THIS CHANGE'S COLLATERAL, AND IT FAILED LOUDLY RATHER THAN VACUOUSLY.** The module gating the unsupported-capture wording pinned Modelo 200 and 202 as its population of "modelos the register is not declared to serve". Declaring the read surface stops the planner refusing them, so there is no message left to inspect — and the module's own guard fired, refusing to pass over an empty result. That is the fixture-anchor discipline working: a pinned id whose named property has changed must red, never quietly pass.

Repaired by DERIVING the population from the registry — modelos that carry a revision for the year but declare no read surface, 39 of them today, capped at a deterministic sample of eight — and refusing an empty derivation with a message telling the next reader to retire or re-scope the module rather than leave it asserting nothing. The property under test is unchanged.

    pytest -q -n0 <the repaired module>
    3 passed in 22.07s

MUTATION PROOF, out-of-repo plugin, nothing under `src` mutated: the production refusal was rebound to re-introduce the AEAT-coverage claim the gate forbids. Exactly one test reddens — the coverage-claim one — while the actionability assertion and the declared-modelo control stay green, which is the correct blast radius rather than a weakness.

**A CORRECTION TO THIS ROW'S OWN EARLIER ANNOTATION.** It stated that neither modelo carries a `live_cross_references` fragment directory at any revision. That was false for Modelo 202, whose 2025 revision already carried a static-documentation cross reference; the earlier sweep looked only for the filed-declarations id and for Modelo 200's directory, then generalised. The substantive claim — that neither declared a filed-declarations READ surface — was correct and is what the ruling turned on, but the wider statement was not, and it is corrected here rather than left standing.

**THE ROW'S GATE SAYS NO LIVE READ IS PERFORMED BY AN AGENT, AND ONE WAS.** This executor ran it, on explicit authorisation relayed from the operator, after the row was written. Recorded plainly rather than glossed: the clause was written when the operator was to perform the run, and the authorisation superseded it for this one read-only invocation. The read persisted nothing, queried no pair, and touched only the register's own controls.

**THE COMMIT CARRIES A PEER'S FILE.** These five registry fragments landed in `085bece80a` together with a regenerated command-sequence golden this row never touched — a bare commit in the shared tree swept both. Named here so the diff's second half is not read as this row's work.
