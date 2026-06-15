---
tags:
  - '#audit'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - "[[2026-06-15-llm-classification-workflow-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace llm-classification-workflow with a kebab-case feature tag, e.g. #foo-bar.
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

# `llm-classification-workflow` audit: `Campaign-close honesty review: audit-trailed reject terminal (F10)`

## Scope

Fresh-context campaign-close honesty review of the F10 audit-trailed reject
terminal (commit `30ba4925c`), conducted by an independent code-reviewer persona
against the review-loop ADR's claims and the shipped code at HEAD. Covers the new
rejection event, `reject_llm_suggestion`, the `classify --reject` CLI across all
three routes, the `ledger history` surfacing, and the size-budget refactor
(`_ledger_autosplit_cli.py`→`_ledger_llm_cli.py`, LLM payloads → `_ledger_llm_payloads.py`).

## Findings

Overall verdict: **PASS** — no CRITICAL or HIGH issues. Every audit-focus claim
verified: reject mutates nothing (unchanged catalogue, row stays `pending`);
persistence routes through the active-bucket secure-write batch
(`_save_transaction_catalogue_and_events`, not the fail-open bare event-repo
`.save()`); the rejection reaches `ledger history` via the updated allowlist;
`--reject`/`--apply` is refused on all three routes with a localised message; the
event payload captures the concrete proposal (split `child_count`, saturated
`iva_category`); the refactor is a pure relocation with no dangling imports and all
modules within budget; tests are real-behaviour; the ADR/code parity holds (history
surfacing, view one-liner deferred). `LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED`
is correctly generic English review-workflow vocabulary (not an AEAT Spanish surface).

### CLOSED THIS PASS

- **F1 (MEDIUM) — stale `P04.S09` plan Step + exec Scope.** The Step row read
  "surface the prior rejection in ledger view" and listed the pre-rename
  `_ledger_autosplit_cli.py`; both contradicted HEAD (history surfacing, file
  renamed to `_ledger_llm_cli.py`). Closed: edited the plan Step action + scope via
  `vault plan step edit` and reconciled the S09 exec title + Scope.
- **F2 (LOW) — saturate/auto-split reject-XOR untested.** Only the stage-1 route
  asserted the `--reject --apply` refusal. Closed: parametrised the XOR test across
  stage-1, saturate, and auto-split routes.
- **F3 (LOW) — `LedgerClassifyLlmRejectResult` absent from the payload contract
  test.** Closed: added a construction + JSON round-trip + extra-forbid assertion to
  the interface-contract suite, matching its siblings.

### CONFIRMED BY DESIGN (no action)

- **F4 (LOW, informational) — the rejection result omits `review_status`.** This is
  the ADR Constraint that reject must not couple to the review projection; the row's
  `pending` status is read via a follow-on `view`/`list`. Deliberate, ADR-grounded.

## Recommendations

- The three closeable items (F1–F3) land in this pass; no REVISION was required.
- The campaign is structurally complete: the LLM surface categorises, classifies,
  saturates IVA/base, reads evidence with on-host vision, recommends and actions
  evidence-driven base/IVA splits, and now records every operator decision
  (approve / reject / override) with an auditable trail.

## Codification candidates

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
via `vaultspec-core vault rule promote --from <this-audit-stem>
--as <rule-name>`.

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

**None.** The reject terminal's constraints are already bound by existing rules:
the confirmation notice rides `cli-notices-are-the-only-diagnostic-channel`, the
no-model-number / no-mutation guarantee is the same registry-derivation discipline
`aeat-calculation-grounding` enforces, and the audit-event persistence is the
standard bucket-event-history pattern. No new cross-session rule is warranted.
