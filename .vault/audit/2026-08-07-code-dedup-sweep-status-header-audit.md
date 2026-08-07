---
tags:
  - '#audit'
  - '#code-dedup-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4f094a2707516b5e093251fcda50c5f04793e173e204504a674fe0a3dd34f162'
related:
  - '[[2026-07-25-code-dedup-sweep-rag-inventory-audit]]'
  - '[[2026-08-07-code-dedup-sweep-d1-1-binding-validator-refutation-audit]]'
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace code-dedup-sweep with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `code-dedup-sweep` audit: `status header for the 2026-07-25 rag inventory audit`

## Scope

Process note for a status header prepended to `2026-07-25-code-dedup-sweep-rag-inventory-audit`.
That document had grown to 754 lines under active, ongoing use by a swarm of
concurrent agents, with the property that an early finding's resolution or
refutation is typically recorded as a LATER addendum, often hundreds of lines
below the finding it resolves — never as an edit to the original entry. This is
not a defect in that document; append-only recording of who found what, when,
and against which HEAD is the right shape for a shared audit log written by many
concurrent agents. The cost is findability: a reader who samples the head of the
document, or who reads roughly the first quarter of it, sees the original
29-finding inventory and any early open addenda, and has no signal that a later
section already closed several of them.

## Findings

### status-header-findability-gap | high | four independent readers missed a later resolution in the same afternoon

Measured, not asserted: this agent independently investigated the document's D1-1
(dual binding-validator convention) and D1-2 (English/Spanish stem pair) findings
after sampling roughly the first 200 of 754 lines, reached the correct technical
conclusions on both, and only discovered — after being directed to write a
combined refutation note and instead reading the full document first — that both
were ALREADY resolved in-document, in more detail, at headings written earlier by
other agents (`refuted-2-dual-binding-validator-convention` for D1-1,
`resolved-expense-gasto-rename-sweep` for D1-2). A third spot-check, on a
CRITICAL/URGENT claim of a live failing test in the document's own untriaged
recommendations tail (`execute-the-emit-bucket-event-fix-forward-plan`), was also
stale: superseded by `resolved-emit-bucket-event-relocation`, confirmed by running
the named test at HEAD with markers cleared (1 passed). Three for three
spot-checks from the head and tail of the document were superseded by content in
its middle. This is a structural property of the document's shape (append-only,
no index), reproducible by any reader who does not read linearly to the end
before acting, not a one-off miss.

A companion note, `2026-08-07-code-dedup-sweep-d1-1-binding-validator-refutation-audit`,
records the fourth instance directly: it was written believing D1-1 was
unresolved, then retracted to SUPERSEDED once the full document was read.

## Recommendations

Prepend a status header to `2026-07-25-code-dedup-sweep-rag-inventory-audit` —
done, in the same pass as this note, as an index only (RESOLVED / REFUTED / OPEN
per originally-inventoried finding, one-line pointer to the heading that already
records the verdict). The body of that document is untouched; this is indexing
what it already says, not a new judgement, so it did not require the owning
campaign's approval before landing.

Ten items were confirmed, by direct `rg` search across the whole document, to
have NO later section addressing them at all (lazy-Typer-subcommand materialiser,
FX rate resolution, scalar-parameter resolver, sensitive-key redaction predicate,
accent-fold, `_renta_ledger::_casilla_aggregation`, evidence-covers-snapshot
guard, two parallel synthetic-PDF generator families, the grimp runtime
import-graph axis, `ledger_transaction_review_payload`). These are marked OPEN in
the header, not resolved-by-omission: absence of a later section is evidence of
"never investigated," not evidence of "fine." They were not independently
re-verified against HEAD by this pass — doing so is the next real Tier-1/Tier-2
sweep work, distinct from the indexing this note performs.

One entry in the untriaged recommendations tail,
`execute-the-expense-gasto-rename-sweep`, is itself stale and should be struck or
annotated superseded by whoever owns that document next — it recommends work
already completed at `resolved-expense-gasto-rename-sweep`. Likewise
`execute-the-emit-bucket-event-fix-forward-plan`, superseded by
`resolved-emit-bucket-event-relocation` and independently reverified at HEAD by
this pass. Both are called out in the header rather than deleted from the tail,
since deleting recommendation entries is a judgement call for the owning
campaign, not this indexing pass.

For any future large rolling audit document of this shape: consider a status
header as a standing convention rather than a one-time fix, prepended and
refreshed whenever a resolution/refutation addendum is appended, so the
findability gap this note describes cannot silently recur.
