---
tags:
  - '#audit'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:ab4a72a005261bf651aa0bdf542dccf9e3af0d7f34817ce91f26941d101bdf17'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
---

# `invoice-canonical-structure` audit: `Close honesty review: what a fresh inheritor finds behind the 38/38`

## Scope

## Findings

## Recommendations

## Context

Run before declaring the campaign structurally complete, as the close-honesty-review rule requires. The persona is a fresh inheritor reading the tracker at 38/38 and asking what that number does not cover. It found one live operator-facing defect and three gaps between what was claimed and what was proven.

## FIXED during this review -- the user docs still taught the retired surface

The campaign swept code, tests, sequences, contracts, locales, and the risk table. It did not sweep the how-to prose, and two pages were still teaching operators a surface that no longer exists.

`docs/how-to/manage-invoices.md` described **two** invoice concepts: a bookkeeping "invoice record" that "on their own do **not** feed a modelo calculation", and a separate "reconciliation catalogue (`aeat app ledger invoice catalogue ...`)" that was "the linkable copy". It then instructed the operator to record an invoice and, if it needed to drive a calculation, "also create it in the catalogue". After the collapse that is not merely stale, it is harmful: it tells a taxpayer to enter every calculable invoice twice, into a sub-noun that would refuse.

`docs/how-to/ledger-evidence.md` carried the same inversion the locale strings did, and self-contradictorily: the link id "comes from an imported, reconciled, or `invoice add` entry - it is not the id `aeat app ledger invoice add` prints." Both halves of that sentence cannot be true, and after the collapse the second half is simply false.

Both are corrected. The remaining "catalogue" hits across the docs tree are the aggregate's own name or unrelated catalogues (modelo, expense-category) and are correct.

The lesson generalises past this campaign: the verb-rename sweep list in the CLI standard names the write-policy allowlist, the error-registry suggestions, the next-action builders, the curated help surface, and the envelope identifiers. It does not name the how-to prose, and the conformance gate parses `.seq` contracts rather than the surrounding markdown. Narrative documentation is the one operator-facing surface with no gate at all.

## OPEN -- 21 ADR decisions, zero cited in the plan

The ADR declares decisions `D-A` through `D-U`. The plan cites none of them, and carries no decision-to-step coverage section. The sibling llm-package-split plan has exactly such a section, so this is a gap in this plan rather than a convention the project lacks.

The practical consequence is that `38/38` means every Step ran. It does not mean every decision was discharged, and nothing in the corpus lets a reader check the difference. A decision could have been ratified in the ADR, never turned into a Step, and the campaign would still report 100%.

This is not a claim that a decision WAS missed -- it is a claim that no one can currently tell. Building the map is the follow-up, and it is the kind of work that finds either nothing or something important.

## OPEN -- "zero capability loss" was verified, not proven

The governing constraint was that nothing is deleted until its replacement is proven by a test that fails when the capability is absent. Each retired test was repointed onto the canonical surface and observed green, which shows the canonical path produces the right answer. It does not show the test would go red if that path stopped producing it.

The two declarable-coverage proofs are the exception and are genuinely strong: re-pinned to fixture-derived literals independent of either implementation, with the Modelo 349 clave grounded in its own table, and they passed first try with no fitting. The Modelo 347 threshold test is also sharp, because its control invoice sits exactly ON the declaration floor rather than comfortably below it, so a `>=` comparison would fail it.

The rest -- the repointed verb suite, the consignment refusal, the attach refusal -- are green but unmutated. A mutation pass over them is cheap and would convert the claim from verified to proven.

## OPEN -- the bucket-attribution nullability difference was resolved by decision, and the decision is unrecorded

The handover named this a blocking gap: the slim record REQUIRED a bucket id, the canonical model defaults it to `None`, and the remedy was to rescope the inventory to a defaults-and-nullability diff rather than field presence.

The canonical model still declares `bucket_id: BucketId | None = Field(default=None)`. The resolution was to treat an unattributed record as BELONGING to the bucket whose encrypted store it was loaded from, rather than as foreign -- the repository already refuses a foreign row on read, so an unattributed one came from this bucket and simply never had the redundant field stamped. That is a sound decision and it is enforced by a test with a full rationale.

What is missing is the decision's own record. It resolves a gap the handover called blocking, it changes the meaning of a persisted field, and it lives only in a test docstring. It belongs in an ADR amendment.

## OPEN -- the whole-tree suite has not run since the deletions

Every gate cited in the execution records is path-scoped. The invoice, ledger, domain, CLI, storage, locale and apidocs surfaces are green, and 402 tests pass across every gate this campaign touched. The full `src/cadrumo` suite has not been run since the slim surface was deleted, and this is a shared worktree with several campaigns landing concurrently, so a cross-campaign interaction would not necessarily appear in any scoped run.

The full-tree gate must also distinguish owner when it runs: peers currently hold red gates in the import-hygiene ratchet, the profile-create wizard inventory, and an ECB-rate-dependent journey.

## Assessment

The structural work is complete and the collapse is real: one aggregate, one payload family, one taxonomy, and the previously-unreachable add-then-link chain now resolves. The four open items above are traceability and proof-strength gaps rather than missing implementation, and none of them blocks the surface being used. They are the honest remainder, and they are what the next pass should take.
