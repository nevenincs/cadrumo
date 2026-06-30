---
tags:
  - '#audit'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# `cli-persona-testimonials` audit: W05 checkpoint closure

## Scope

This audit closes the W05 certification checkpoint for the open-ended persona
testimonial campaign. It does not claim that `tmp/personas` is bounded, that every
artifact root has a local transcript and final summary, or that the full repository
runtime suite is all green.

The checkpoint covers the work already tracked in W01 through W05: testimonial
inventory, calculation and data-safety hardening, weak-root replay, live-read and
legal-source hardening, owner-aware gates, and reviewer closure.

## Fixed Clusters

### calculation-and-carry | high | M303 compensation and refund carry edges are bounded

The campaign closed the highest-risk Modelo 303 carry paths: first-period zero
compensation, missing prior filing evidence, refund-request periods that must not
double-claim compensación carry, and REDEME/product-policy wording. The latest W05
review found no behavioral blocker in this area and the remaining low wording issue
was fixed in `src/aeat/application/modelo/_filed_revision_observation.py`.

### ledger-and-currency | high | ledger import and non-EUR IVA diagnostics fail closed

Ledger import provenance, duplicate diagnostics, provider boundaries, same-signature
rows, cross-profile refusal, and unsupported currency behavior are covered by focused
gates. Converted non-EUR IVA rows now refuse aggregation/preflight without separate
EUR taxable-base and cuota substrate instead of silently projecting native tax facts
as EUR filing facts.

### profile-identity | high | active-profile and cross-profile leakage risks were hardened

The W02 profile fixes keep tombstoned active profiles out of live routing while
preserving read-only inspection parity. Gestor and same-signature testimonial risks
were rechecked through focused profile and ledger tests.

### export-and-evidence | medium | local artifacts are no longer official filing proof

Modelo 100 borrador/filed observation handling and local export receipts now keep
draft/local files separate from official AEAT filing evidence. The closure ledger
keeps persona artifact hygiene separate from product correctness.

### live-read-and-legal-source | medium | read-only live surfaces and source verification hardened

Live AEAT command-tree guards block mutation/submission verbs, justificante capture
records hash/evidence provenance, filed-data capture fails closed on registry
enrollment failures, and legal `required_text` verification runs before article-only
short-circuiting.

## W05 Gates

The touched-surface gate passed after one campaign-owned test-harness fix in
`src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py` and
`src/aeat/entrypoints/cli/tests/test_live_justificante_verbs.py`: service seed data
now uses the same active UUID bucket as the secure-storage fixture. The post-fix
gates included IVA/ledger/preflight saturation, legal verifier and legal grounding,
live CLI schema/guard tests, live capture tests, Modelo/refund/calendar tests,
registry CLI verification, and ledger preflight CLI tests.

The owner-aware broad classification collected `src/aeat` successfully and the
targeted catalogue/Modelo 210 baseline check passed. Full-tree Ruff still fails in
unrelated script/docs-test files: `add_frontmatter.py` and
`dev/docs/tests/test_glossary_anchor_parity.py`. Those are not campaign-owned
calculation or CLI regressions.

Vault hygiene for the feature passed: plan check, feature index rebuild, body-link
check, and placeholder check.

The fresh reviewer found no behavioral blocker. Live AEAT network reads were not
exercised; the review covered structural live-read guards and focused code/tests.

## Residual Edges

### full-tree-runtime | medium | full runtime all-green remains unclaimed

The campaign did not run full runtime pytest. The owner-aware classifier used
collection and targeted gates because prior W04 verification hit Windows resource
exhaustion and the project unit gate uses parallel workers.

### artifact-hygiene | medium | persona root evidence remains mixed

Some `tmp/personas` roots are scratch or storage roots, not transcript stores. Some
artifact-only roots lack local BOE/export/approval evidence even when product gates
cover the underlying surface. The ignored ledger `tmp/personas/_cpdefix-closeout-ledger.md`
records per-root disposition but is not a replacement for original transcripts.

### ongoing-corpus | medium | new testimony is not bounded

New persona roots and final summaries may arrive after this checkpoint. W06 in the
plan keeps intake, artifact hygiene, replay, fixer dispatch, and owner-aware gates
open.

### broad-static-debt | low | unrelated broad Ruff failures remain outside scope

The current broad Ruff failures belong to `add_frontmatter.py` and
`dev/docs/tests/test_glossary_anchor_parity.py`. They should be repaired by their
own owner or campaign before a repo-wide static all-green claim.

### live-aeat-network | low | live network behavior remains unexercised here

W05 verified read-only live command structure and local capture behavior. It did not
authenticate against or query the live AEAT portal.

## Recommendation

Close W05 as an owner-aware checkpoint, not as a final campaign stop. Keep W06 open
for newly arriving testimonial roots, artifact hygiene, replay of final closeout
messages, RAG-grounded fixer dispatches, and post-fix owner-aware gates.
