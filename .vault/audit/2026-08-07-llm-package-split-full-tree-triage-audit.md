---
tags:
  - '#audit'
  - '#llm-package-split'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b0d3cedcac1bcc359cc70635701a76c2c783516fe412b4355d95feb3e35fe1d0'
related:
  - "[[2026-08-06-llm-package-split-plan]]"
  - "[[2026-08-07-llm-package-split-plan-tracker-reconciliation-audit]]"
---

# `llm-package-split` audit: `Full-tree triage: what the whole-suite run found, and who owns it`

## Scope

## Findings

## Recommendations

## Context

The invoice campaign's close review left "the whole-tree suite has not run since the deletions" as its last open item. It has now run: **24,245 passed, 127 failed, 8 errors, 34 minutes**. This is the owner triage, because in this worktree a red whole-tree gate is mostly other people's in-flight work and a number without attribution is not actionable.

## Owned and fixed

One failure was genuinely mine. Making `counterparty_country` required on the evidence-confirm path left two CLI suites still invoking the verb without it: `test_ledger_evidence_printed_total_notice` and `test_ledger_evidence_self_counterparty`, six invocations between them. Both sit outside every path-scoped suite the change was verified against.

That is the whole argument for running the tree at least once. The change was verified across the invoice, ledger, CLI-conformance and evidence-confirm suites and every one was green; the two files that broke were reachable only from a run that selects everything. A scoped gate cannot tell you about the callers you did not think to scope.

## Peer-owned, confirmed by inspection rather than assumed

**The docs build.** Failing, and the failure MOVED between two runs minutes apart: first a control character in a `notes` field on a legal entry (`real-decreto-ley-4-2024:art-1`), then an `ImportError` for `UnroutedRentaQuantity` from `_ledger_bindings`. The first was fixed by its author while this triage was running. The second is an uncommitted edit in that same file, with consumers still importing the symbol. Both belong to the legal-grounding and IVA-binding work landing continuously through the morning.

**The docstring core-struct gate.** One public function missing its `:class:`ModeloRevision`` cross-link, in `_ledger_bindings` -- the same actively-modified file.

**The legal-anchor ratchet.** 91 entries carry an anchor nothing verifies, one above the committed ceiling of 90. Five legal-grounding commits landed between 10:02 and 10:53, including corpus sidecar generation for the anchor resolver itself. The honest fix is to ground the new anchor, not to raise the ceiling -- raising it is what a ratchet exists to prevent -- and grounding someone's in-flight legal entry mid-campaign would collide with them.

**Import hygiene, nine undocumented private reaches.** Five are `llm/tests` reaching back into `application/ledger` -- into `_llm_classification` privates and into `tests/_llm_vision_evidence_support`. One is `einvoice/tests` reaching into `sanitizer._dynamic` for `strip_attachments`, which is worth a second look: W02.P03.S11 asked for the sanitizer's embedded-file walker to be extracted into a REUSABLE reader, and a test reaching a private for it suggests the extraction landed without a public surface. The rest are sede-auth, core tty-probe and renta.

The gate itself names the remedy: promote to the owning package's facade, or add a named, reasoned debt entry in the same commit. Both are the author's call. Writing debt entries for another agent's actively-moving files would bless a state they may be mid-way through changing, and the reasons would be mine to invent rather than theirs to state.

## A note on the instrument

Running these gates under `xdist` produced `Different tests were collected between gw0 and gw1` across every worker -- a collection mismatch, not a test failure. The tree was changing under the run. Every triage above was re-run with `-n 0` before being believed. A parallel run against a worktree with several agents landing commits reports races as failures, and on this volume that is the default outcome rather than an unlucky one.
