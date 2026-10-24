---
tags:
  - '#plan'
  - '#desktop-native-sign-in'
date: '2026-10-24'
tier: L1
related:
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
modified: '2026-10-24'
body_schema: body-v2
body_hash: 'sha256:a647fb1ddd30fdeaf4cf3dfb969559c5ca7a0d38ee1c764bf46c006ef0f199a0'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries governing ADRs, if any.
       Steps inherit their evidence transitively. Direct supporting
       evidence links are optional; per-row footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace desktop-native-sign-in with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries governing ADRs; Steps inherit their evidence transitively.
     Direct supporting evidence links are optional. A decision-free plan
     records its coverage assessment in the Description.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution artifact: the plan's ledger.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 until `vaultspec-core vault check all --fix` adds it).
     The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Select the smallest hierarchy that clarifies coordination:
       L1 = a flat sequence of cohesive revisions, including broad changes.
       L2 = Phases clarify groups of Steps.
       L3 = Waves clarify dependencies between groups of Phases.
       L4 = an Epic coordinates a program with external tracking.
     Duration, file count, package count, or short parallel work alone
     never requires a higher tier.
     Between two tiers take the smaller and promote later.
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

<!-- COHESIVE GRANULARITY:
     One Step is one cohesive, verifiable commit. Coordinated repeated edits
     may share a row when scope and verification are explicit. Separate
     unrelated outcomes. Name the bounded files or area, expected creations,
     and intended result; avoid unspecified catch-all work. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change; the `plan_edit` and `plan_progress`
     MCP tools reach the Step verbs only, and the above-Step verbs run
     through the CLI. Hand edits are forbidden and
     flagged by `vaultspec-core vault plan check`; canonical-identifier
     preservation is guaranteed only when a verb performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `desktop-native-sign-in` plan

The desktop window holds the person's runtime session on its own native connection; the Python hold child leaves the desktop.

## Description

Approved 2026-10-24. Basis: the user's instruction of 2026-10-24, "Your only task is implementing candidate 1: native sign-in", which named retiring the desktop's Python `session hold` child and the remaining sign-in children.

Decision coverage: the 2026-10-24 amendments of `2026-10-04-application-sign-in-adr` and `2026-10-04-desktop-shell-adr` record the ownership change (the window holds its own person session; the hold command stays for development probes and attended admission). Non-Windows sign-in stays unavailable, as those records already rule, because no login and lock observer exists there; the native transport stays Windows-only.

Today the window already signs in natively (`native/desktop/src-tauri/src/shell/sign_in/mod.rs`, `native_sign_in`), but every person request (status, activity, service admission, attendance, language, presentation and the registered-operation relay) still crosses a Python child (`native/desktop/src-tauri/src/agent/person.rs`, `src/cadrumo_runtime/host/session_hold.py`). The work moves those requests onto the window's connection in Rust, keeps the hold's reply shapes so the agent host, language, ledger, presentation and relay consumers stay unchanged, and resumes a stored sign-in natively where the window holds none.

## Steps

- [ ] `S01` - keep refusal detail and session-scoped events in the native runtime client, add a session-exchange seam and the receipt resume with its retry and refusal map; `native/application/src/runtime_client.rs`.
- [ ] `S02` - port the hold's registered-operation relay and profile language read and set to Rust over that seam, with fake-exchange unit tests; `native/application/src/person_operations.rs`.
- [ ] `S03` - hold the window's person session on its own native connection with the hold's reply shapes, retire the hold child and prepared hold from sign-in, and move consumer tests to the native session; `native/desktop/src-tauri/src/agent/person.rs, native/desktop/src-tauri/src/shell/sign_in/mod.rs`.
- [ ] `S04` - extend the live native client proof to the person session and time native sign-in against a real runtime; `native/application/src/runtime_client.rs, dev/runtime_lifecycle/native_client_live.py`.

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- Progress is recorded through the plan verbs (`plan_progress`,
     `vaultspec-core vault plan step check`), one Step at a time. -->

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

     For user-requested coordination across the program and its tracker,
     vaultspec-projectmanager owns that context and assignments; this
     plan remains the home of implementation sequencing.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

S01 lands first: it defines the session-exchange seam. S02 and S03 then run in parallel with disjoint files: S02 owns `native/application/src/person_operations.rs` and its registration in `native/application/src/lib.rs`; S03 owns `native/desktop/src-tauri/src/agent/person.rs`, `native/desktop/src-tauri/src/shell/sign_in/` and their tests, and wires S02's API once it lands. S04 follows both.

## Verification

- `cargo test` passes for `native/application` (with the `platform` feature) and `native/desktop/src-tauri`, including the person-session and operation-relay unit tests; clippy and rustfmt are clean.
- The desktop crate spawns no `session hold` child: no `"session", "hold"` argument remains under `native/desktop/src-tauri/src`.
- The live proof (`dev/runtime_lifecycle/native_client_live.py`) signs in, holds, reads status, notes activity, reads the profile language through the relay and signs out against a real runtime, and reports the native sign-in time.
- One integrated review at plan close.
