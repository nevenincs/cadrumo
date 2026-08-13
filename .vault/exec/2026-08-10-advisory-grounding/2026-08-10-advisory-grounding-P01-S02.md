---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:81ea402b38fdbbf1b1c4b7b9e9a4749655663d472e7b8f0363cf4569a94766e4'
step_id: 'S02'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Refuse at registry build any declared provision id that does not resolve to a legal-catalogue entry. This is the check the prose form could never carry. State a control proving the legitimate population still passes and do not close on the refusal firing. The disconfirming observation: if the control shows a legitimate advisory declaring an id that does not resolve, the catalogue is incomplete for that provision and this row must stop and report rather than relax the refusal

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/tests/`

## Description

- Add `assert_legal_ref_ids_resolve(ref_ids, *, legal, subject)` to the registry domain layer: refuses, naming every absent id at once, when any declared id is not a key in the legal catalogue mapping.
- Export it from the registry package facade.
- Unit-test the refusal (single and multi-id) and the pass-through case directly against the committed catalogue.
- Add the CONTROL as its own project-wide test: construct `CalculationSourceDiagnostic` instances declaring `asserted_legal_refs` set to the eight provision ids the grounding reference's Population B measurement evidenced (`ley-35-2006:art-58-1`, `art-61-norma-2`, `art-81-2`, `art-81-3`; `ley-37-1992:art-103` through `art-106`), and confirm every one still resolves against the live bundled legal catalogue.
- Add a second, separate test proving the refusal fires on a fabricated id, kept distinct from the control so closure does not rest on it.
- Determine WHERE the refusal can actually be enforced, and wire it there, so the check is not an available helper that a declaring site can decline to call.
- Add the enforcing gate: scan the production source surface for every site declaring `asserted_legal_refs` and resolve the declared ids against the live catalogue, refusing a declaration that is unreadable as well as one that names an absent provision.

## Outcome

A declared provision id can no longer reach the tree unresolved. The refusal exists as `assert_legal_ref_ids_resolve`, naming the id and the declaring subject, and a gate now applies it to every declaring site rather than waiting to be invoked.

**The determination the row's wording required.** The row says "refuse at REGISTRY BUILD". Registry build validates the compiled TOML tree, and `asserted_legal_refs` has no TOML surface: the field lives on a runtime model that application code constructs in Python, so every declaration is a keyword argument in a call expression. Confirmed by inspection -- no registry data declares the field anywhere. The source tree is therefore the enforcement point, and the gate is a source scan. This is stated plainly rather than quietly satisfying different words than the row used: if the field were ever given a registry-authored surface, registry build would become the right home and this gate would be the wrong shape.

**A computed declaration is refused, not skipped.** A value assembled at runtime cannot be resolved by any static reader, so permitting it would leave the one shape that defeats the gate entirely available. It is also the shape the field's own contract forbids, because declaring an id is a tax review against the provision the message states rather than a derivation from a casilla already in hand -- so refusing it enforces the contract and the checkability with one rule.

**Closure rests on the control, and the control holds.** All eight ADR-evidenced ids -- drawn from the reference's own hand-checked measurement, not fabricated for this test -- resolve against the live bundled catalogue. No legitimate id failed, so no stop-and-report was triggered.

**The gate was proven to bite, in both directions and at the real surface.** The declaring population is empty today, which is exactly why a silently-blind scan would be indistinguishable from a working one, so the proofs carry the weight rather than the green run:

- the scanner finds declarations in each syntactic position it claims to cover, over real files written outside the repository;
- a fabricated id refuses and a real id passes, so a gate that refused everything could not satisfy both;
- a computed declaration refuses;
- the production scan surface is asserted to include the module that DEFINES the field, resolved from the class rather than hardcoded, which closes the failure an anti-tautology proof alone cannot catch: a detector correct on synthetic input that never reaches the real site;
- and the decisive one, the REAL tree scan composed with a single out-of-tree declaring site carrying a bad id goes red, having first been confirmed green without it, so the refusal is attributable to the added site.

Nothing was written into the repository to prove any of this, and no production code was mutated.

## Notes

**Sequencing, stated honestly.** This row was first closed on the control alone, with the enforcement gap recorded rather than hidden: the refusal existed as a helper no caller invoked, which reads as enforcement while enforcing nothing. That is a named defect class here -- a safety net built and switched off -- so the gate was built in the same session, before any declaring site exists. Adding it while the population is empty lands green and costs nothing; the same gate added after the first declaring site would be a cleanup someone argues about.

**No count is baked in.** The declaring population is expected to grow one adjudicated advisory at a time, and a tally as a pass condition would only train the next author to bump it. The gate asserts the property. The exemption map for statically unreadable declarations is keyed by `(path, enclosing function)` rather than by line number, and is empty by construction -- the first site to declare should declare literals rather than earn an exemption.

**The helper stays generic** (`Iterable[str]` in, not `CalculationSourceDiagnostic` in), so it is not coupled to this one caller shape, and the gate composes it rather than reimplementing the resolution.
