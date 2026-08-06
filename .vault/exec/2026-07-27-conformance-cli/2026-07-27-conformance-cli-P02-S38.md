---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:0797c3fa2535573b4f86e47bab9f6026236219c12add0f80c403de3f4b0ccb49'
step_id: 'S38'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# declare the prorrata percentage casilla in the external grounding claims now that both preconditions of the oracle-evidence rule are satisfied and verified, so the AEAT manual figure becomes an enforced independent check

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Description

- Re-verified both preconditions of the oracle-evidence rule directly rather
  than inheriting the prior Step's claim.
- Declared the prorrata percentage casilla in the external grounding claims of
  the one revision a bundled oracle actually covers.
- Added the governing provision to that verification contract's legal grounding,
  matching how the five already-grounded leaves are cited.
- Recorded at the change site which AEAT authority states the figure, why the
  leaf is worth grounding, and why the sibling revision is excluded.

## Outcome

Both preconditions were verified independently before anything was declared,
because a grounding claim with no bundled evidence reds the symmetric honesty
gate in the other direction.

The evidence precondition holds. The bundled AEAT manual oracle payload declares
modelo 303 and filing year 2025 and carries exactly one expected value, the
prorrata percentage at 56. The grounding fold attributes it to the M303
2023-y-siguientes revision, and before the change that revision's row already
listed the casilla in its oracle evidence set while omitting it from its declared
grounding set. The figure was therefore evidence the honesty relation could see
and no revision claimed, which is precisely the unenforced state this Step
closes.

The reproduction precondition holds. The real registry snapshot for the payload's
own filing year, driven with the manual's stated annual volumes of 45.000 total
and 25.000 con derecho, returns 56, matching the payload's expected value
exactly. The existing application-layer oracle test that drives the same chain
end to end was re-run and passes. The figure is the manual's printed number, not
a re-derivation of the registry formula, so the check is independent.

The declaration is scoped to one revision on purpose. The 2009-y-siguientes
revision also reconciles the same casilla, but no bundled oracle covers a filing
year that resolves to it, so declaring it there would assert a grounding tier
with nothing behind it. That exclusion is stated at the change site so a later
reader does not mistake the asymmetry for an oversight.

The declaration moved the numbers it should and nothing else. Declared groundings
across the registry went from 58 to 59; findings stayed at zero; the audit still
returns 90 rows over 9 checked revisions; and the set difference between the
revision's declared grounding and its oracle evidence is empty in the direction
the honesty gate polices. The verification verdict is unaffected by construction:
the verdict status derives from discrepancies and coverage, while the grounding
set feeds only the reported independently-grounded fraction, so this is a
governance and reporting change and not a filing-grade behaviour change. The
enclosing contract already carries a zero minimum coverage, so no legitimate
filing's verdict can flip on it.

The contract's legal grounding was extended to name the provision governing the
newly grounded leaf. The five already-grounded leaves are cited through the
devengado and deducible articles the contract already listed; the prorrata
percentage is governed by the prorrata-general article, whose catalogue entry
already exists at legal-authority tier with a bundled corpus reference, a BOE
document id and verbatim required text. No legal-catalogue entry was authored or
amended, so no legal-entry co-commit was required.

Why this leaf earns grounding rather than only enrollment. The percentage is a
deduction rate that multiplies into every deducible cuota, so a wrong rate
rescales the whole deducible side while every total it feeds stays internally
consistent. That is the same compensating-error gap the five existing leaves
close for the devengado and deducible sums: a totals-only oracle stays green
while the individual figures the operator files are wrong.

Verification run. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references,
including the required-text corpus check on every legal reference. The
external-oracle honesty gate is 3 passed in its integration lane, covering both
directions. The verification, legal-grounding, catalogue-normatives and prorrata
grounding suites together are 95 passed. The prorrata and M303 surfaces together
are 493 passed.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so grounding was done
with ripgrep plus whole-file reads and confirmed against the loaded registry
snapshot rather than fragment listings.

A scoped suite run over the verification, application-registry and registry test
trees produced seven failures that are peer-owned, not owner-owned. Six are in an
untracked test module a peer is landing for the fragment placement refusal Step,
which does not exist at HEAD at all. The seventh was a loader disk-cache test
whose subprocess exited non-zero mid-run; the same subprocess command run
directly afterwards succeeded, and the whole module passed on re-run, so it was a
race against the peer edits landing in the loader and schema modules during the
run rather than a defect. Neither cluster touches any file this Step changed.

The staged index at commit time held a peer's in-flight dev-side conformance
work. The commit was made with an explicit pathspec naming only the single
registry file, so the peer's staged entries stayed in the index untouched.
