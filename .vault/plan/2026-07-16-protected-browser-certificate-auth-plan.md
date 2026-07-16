---
tags:
  - '#plan'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
  - '[[2026-07-16-protected-browser-certificate-auth-research]]'
  - '[[2026-07-16-protected-browser-certificate-auth-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace protected-browser-certificate-auth with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `protected-browser-certificate-auth` plan

### Phase `P01` - Remove residual parallel authorities

Make the live code and accepted decision corpus expose only encrypted certificate-bound protected-browser state.


Remove the final plaintext, lifecycle, coverage, and decision-corpus gaps
without restoring any retired certificate-auth compatibility surface.

- [ ] `P01.S01` - Delete implicit plaintext profile storage-state consumption from fresh provider sessions and make every persistence source explicit; `src/cadrumo/adapters/outbound/aeat/browser/session.py; src/cadrumo/adapters/outbound/aeat/auth/`.
- [ ] `P01.S02` - Reconcile every still-accepted auth decision with the protected-browser authority and remove retired handshake marker and configurable-target clauses; `.vault/adr/2026-04-17-session-persistence-adr.md; .vault/adr/2026-04-17-aeat-access-gate-adr.md; .vault/adr/2026-04-18-auth-provider-abstraction-adr.md; .vault/adr/2026-04-18-auth-protocol-adr.md`.
- [ ] `P01.S03` - Correct maintainer contracts that still describe marker evidence or implicit browser-factory construction; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`.

### Phase `P02` - Harden owned browser lifecycle

Close every provider-owned context and browser deterministically across failures and concurrent close calls.

- [ ] `P02.S04` - Close Clave contexts and browsers when fresh-session persistence fails before ownership transfer; `src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py; src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente.py`.
- [ ] `P02.S05` - Make certificate context teardown bounded retryable and primary-exception preserving; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py; src/cadrumo/adapters/outbound/aeat/auth/_browser_lifecycle.py`.
- [ ] `P02.S06` - Serialize concurrent provider closure so the drain barrier cannot tear down newly admitted work; `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py; src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py; src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente.py`.

### Phase `P03` - Prove and close the hard cut

Replace synthetic proof coverage with the strongest credential-free real behavior available, retain the external live oracle, and close only after repository-wide gates.

- [ ] `P03.S07` - Replace synthetic decisive proof and lifecycle coverage with credential-free real browser and process behavior while retaining the external live protected oracle; `src/cadrumo/adapters/outbound/aeat/auth/tests; src/cadrumo/adapters/outbound/aeat/browser/tests`.
- [ ] `P03.S08` - Run repository-wide quality Vault documentation packaging and CI-equivalent gates and resolve the formal audit; `.vault/audit/2026-07-16-protected-browser-certificate-auth-audit.md; repository`.

## Description

Execute the accepted protected-browser certificate-auth decision and resolve
the formal reconciliation audit. The implementation retains one exact
Playwright protected-resource proof, typed certificate credentials, encrypted
session persistence, and provider abstraction while deleting residual
plaintext state tolerance and making context and browser ownership reliable
under failure and concurrency.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Phase P01 decision-corpus work can run alongside its storage-authority and
maintainer-contract code changes. Phase P02 lifecycle fixes can be split by
certificate and Cl@ve ownership, but the concurrent-close contract must be
shared across all three providers. Phase P03 starts only after P01 and P02
settle so its real-behavior tests and repository gates exercise the final
architecture.

## Verification

The feature is complete only when semantic and exact searches find no active
handshake, marker, backend-selection, configurable-target, implicit plaintext
storage-state, or compatibility authority; every accepted auth decision agrees
with the protected-browser ADR; real Playwright process and lifecycle tests
pass without fakes, mocks, stubs, patches, skips, or xfails; the external live
oracle remains exact and fail-closed; the full pytest, style, format, type,
import, registry, documentation, Vault, and GitHub CI gates pass; and every
Step has its CLI-checked state and execution record.
