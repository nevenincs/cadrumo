---
tags:
  - '#reference'
  - '#mcp-closed-value-axes'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:2a02b10b40282daabbdd7c7c1234f99cff0ec2f2f7f920d75d31ddb84a1f6acf'
related:
  - "[[2026-08-08-mcp-closed-value-axes-audit]]"
---

# `mcp-closed-value-axes` reference: `What this remediation campaign found, and what not to re-attempt`

## Summary

A thirty-two iteration remediation pass over the CLI, calculation and ledger surfaces. It produced **two real defect classes fixed** and, more usefully for whoever reads this next, **a record of which searches work on this tree and which do not**.

The fixes are in git and need no explanation here. What git cannot preserve is why three separate measuring instruments produced confident wrong answers, and which conclusions were reached by inference rather than by check. That is what this document is for. **Read the "do not re-attempt" section before starting a similar sweep.**

## The three instruments that failed, and how

All three were built to answer "which fields lack a guard". Each was honest about something and blind to something else. **The pattern is that every one of them was trusted before it was validated against a case whose answer was already known.**

**Static `Field` metadata.** Cannot see a guard written as a validator. This produced the campaign's one confidently wrong finding -- and the blind spot had been *documented in writing one iteration earlier*, then not applied to the very next result.

**Name-based validator search.** Misses a guard living inside a `model_validator` that covers several fields at once, which is exactly where the real one was.

**Differential behavioural probe** (construct with an in-range value, then an out-of-range one; credit only models that accept the first). This one cannot lie, and for that reason returned *inconclusive* for 84 of 96 fields -- including all three whose guard state was known. Adding a recursive minimal-instance builder moved it to 36 of 96 and left the controls still inconclusive: those models carry cross-field arithmetic validators, so no instance assembled from field types alone is valid.

**The stopping rule that came out of it:** three instruments, each honest about a different thing, none validatable against known ground truth -- that is the signal to stop measuring, distinct from and sharper than a time-box, because it is about validatability rather than elapsed effort.

**What would actually settle that class**, for anyone who returns to it: stop asking each *model* whether it refuses and ask each *durable persistence boundary* whether a percentage survives a save-and-load round trip. That reuses the hand-built roundtrip fixtures the quality rules already mandate, which satisfy the cross-field validators a synthetic builder cannot.

## Judgement lessons, in rough order of usefulness

**Absence-claims are the weakest claim type.** Twice this campaign reported "nothing enforces X" from a failed search, and both times the enforcement existed -- once named after the *error* rather than the field it protects. A found thing is verified by inspecting it; a not-found thing is only as good as the search. **Standing fix: before claiming an absence, search by at least two independent shapes -- the symbol name AND the error/exception type -- and state which searches ran.** This rule paid for itself on its first use, locating an entire pre-existing handoff-path audit that a single-shape search had missed.

**A uniform or suspiciously large result is usually the probe, not the code.** Three occurrences. A tracing pass reported 17 gaps against a "covered" set of 3; the real answer was 2, and the 17 came from a silent `getattr` default. A persisted-model sweep reported 378 of 393 "unnamed"; the real answer was that the discriminator does not apply to that surface at all. **Check the instrument before writing anything about the code.**

**A documented rationale is evidence, not a suspect.** Three rationales were tested; all three held. The single wrong finding came from the one case where inference from a structural signal replaced a check. The campaign began by treating in-code rationales as claims to interrogate; the evidence says they are more reliable than the instruments used to doubt them. Test them -- but weight them above a static signal that contradicts them.

**The substitutability pre-filter earns its place.** Before replacing X with Y, confirm Y's constraint shape is a superset of X's. Applied properly it caught a `--state` option that accepts `all` on top of its enum, and a period comparison that looked exactly like a rule's own named bad example but drew its bounds from the `Period` itself -- with a comment showing the author had already considered and rejected the "fix".

**The pre-filter has a second edge that is invisible at the declaration site.** Ask not only whether the value set can shrink safely, but whether anything downstream *depends on receiving an out-of-set value*. Three separate guards in this tree accept out-of-taxonomy values in order to refuse them with a legal citation. A campaign regression shipped because that check was skipped. **In a regulated domain, assume an instructive refusal exists until the command body says otherwise** -- the excluded values are precisely the ones a taxpayer is most likely to try, because they are real tax concepts governed by another authority.

**And a third edge: input normalisation.** A hand-rolled parser that case-folds or rewrites separators is silently narrowed by a bare enum annotation. `click.Choice(case_sensitive=False)` preserves the accepted spellings *and* the enum-typed parameter -- the trade-off is not real, it just looks real.

## The co-production hypothesis

Every axis whose rule cites a concrete past defect turned out to be **already gated** -- provenance-drop, dual-mechanism fold-in, period boundaries, selector/binding drift. Four for four, usually by a gate named after the defect rather than the concept.

The mechanism makes this more than a correlation: **a rule citing a past defect exists because someone hit that defect, and whoever hits one badly enough to write a rule usually writes the gate in the same change.** Rule and gate are co-produced, so "a rule cites a real defect here" is close to a proxy for "a gate already exists here".

Honest caveats: four observations, not a law, and not independent -- one repo, one unusually disciplined rule corpus. The converse (undefended ground is where no rule points) is the weaker half, resting on two findings by a single author who chose where to look.

**The practical inversion:** the eight-axis audit cadence is a list of the codebase's *known* risks, which is exactly the set most likely already handled. Working down it is systematic and, on this evidence, low-yield. Both real defects came from surfaces no rule names.

## What remains genuinely open

- **Persisted models and cross-package facade exports were never assessed.** The set-difference method that worked on registry source kinds does *not* transfer: it needs a rule corpus that enumerates individual tokens, and rules speak categorically about persisted records. This is an instrument limitation, not a clean result.
- **One-sided boundary re-validation**, the third cross-domain shape, was never swept.
- **`BindingSourceKind` carries two roles** -- a binding's declared input source, and an observation's provenance label -- and two of its members are only ever the second. Recorded, not promoted: the design is coherent, the policy sets that matter are explicit and gated, and nothing is silently wrong.
- **The `--iva-rate` unit split** (fraction on the ledger verbs, percentage on inventory) persists deliberately; see the dedicated ADR for why a rename was deferred rather than rejected.

## What was actually fixed

**A silently-accepted 2100% IVA rate.** `Transaction.iva_rate` holds a fraction -- 21% is `0.21` -- and was unbounded, while the inventory ledger takes the same concept as a percentage bounded `0..100` and asks for `21` by default. `21` written into the fraction field was accepted, persisted, and inherited by every downstream aggregation. Over-statement is the direction this codebase watches least: an under-declaration eventually contradicts a filing, while a hundredfold over-statement produces a valid-looking return the taxpayer overpays.

**Four operator-facing help strings that advertised values the CLI refuses.** One named a spending category that exists in no casing; one named two movement kinds that do not exist while omitting two that do; one offered a manuals volume absent from the tree. The fourth is the one that matters: `modelo work amend --kind` advertised `complementaria or sustitutiva` and omitted **`rectificativa`** -- a legally distinct instrument under LGT art. 122 that the engine supports and the operator-facing surface said did not exist. Three of the four had been wrong long enough to be translated into Catalan and Hungarian.

**The structural fix behind the second class is the durable one:** declaring the enum at the Typer boundary makes the accepted set *derived* rather than *restated*, and a derived set cannot drift the way a sentence can.

## Do not re-attempt these

Each was investigated to a conclusion. Re-opening them costs an iteration and reaches the same place.

**Re-typing `FormulaExpression` onto the CLI payload schemas.** It is a recursive strict model whose `args` is a tuple; `model_dump(mode="json")` renders that as a list and strict re-validation refuses it. The `dict[str, object]` is a deliberate, documented escape hatch. Reproducible in four lines.

**Adding a fraction guard to `Invoice.retention_rate`.** One already exists, inside a multi-field `model_validator`, with the same bound and the same unit-naming message. A campaign iteration was spent building a redundant duplicate.

**Re-typing `CalculationSourceDiagnostic.source_kind` to `BindingSourceKind`.** The field is deliberately a superset: it carries binding source kinds *and* advisory category labels that are not enum members. Re-typing would refuse the advisory rows the collector exists to emit.

**Bounding `LedgerEvidenceRow`'s rate fields.** They are projected directly from `Transaction`, which validates them at the durable boundary. `fx_rate` in particular must *not* carry an upper bound -- a currency conversion rate is not a fraction.

**Pinning `--modelo` on `modelo work create`, `--ccaa`, or `--valuation-method` to their enums.** Each deliberately accepts out-of-set values so a guard can refuse them *well*: ceded autonomic taxes are named with their regional filing route, foral territories raise `ForalRegimeError`, and LIFO is refused citing LIS art. 17.1. A `Choice` refuses before the body runs and replaces a legally-grounded answer with "not one of".

