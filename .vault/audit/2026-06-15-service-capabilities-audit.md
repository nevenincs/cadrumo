---
tags:
  - '#audit'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
  - "[[2026-06-15-service-capabilities-adr]]"
  - "[[2026-06-15-dependency-provisioning-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
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

# `service-capabilities` audit: `service-capabilities campaign close honesty review`

## Scope

Fresh-context honesty review (per the campaign-close-honesty-review rule) run by
an independent `vaultspec-code-reviewer` (Opus) before declaring the
`service-capabilities` campaign structurally complete. The review skeptically
audited every sensitive-data egress for capability bypasses, the resolver's
narrow-never-widen invariant, the gestor bar, the three dependency probes'
never-raise guarantee, stub/TODO hygiene, and claim-vs-implementation gaps in
the two ADRs and the plan. The driving agent then verified each finding against
HEAD and actioned or formally deferred it.

## Findings

### H1 (HIGH, FIXED) — `google_export` gated only `export`; `verify` / `push` / `probe --no-read-only` wrote to Google ungated

The capability gate existed on only one of four Google-write CLI leaves.
`calc verify` creates a Drive spreadsheet and writes cells, `sync push` mirrors
secure-object ciphertext to Drive, and `sync probe --no-read-only` round-trips a
sentinel write — all bypassed `resolve_active_capability(GOOGLE_EXPORT)`. The two
ADRs and the plan claimed the plural "Google export entry points," so this was a
real safety-claim gap on the regulated egress surface, not merely cosmetic.

**Disposition: FIXED** (commit `fe474ff1d`). All three sibling verbs now route
through the same capability refusal `export` uses (`probe` gates only its write
arm; the read-only probe stays open). A parametrized conformance test asserts
every Google-write leaf refuses with the capability message when `google_export`
is off — the gate fires before any Google call, so it is deterministic without
credentials.

### H2 (HIGH, RESOLVED-BY-H1) — ADR/plan overstated the shipped Google-export coverage

The claim "the Google export entry points check `google_export`" was true for
cloud and vision (single chokepoints) but only partially true for Google. With
H1 landed the claim is now accurate; no separate action required.

### M1 (MEDIUM, FIXED) — vision gate sits past two early returns; no off-refusal regression for both on-host read modes

The `llm_vision` check in `_resolve_evidence` is functionally correct (text →
cloud gate; image/scan → vision gate) and reviewer-verified, but it guards only
the image/scan arm by position. A future on-host read mode could land above the
gate.

**Disposition: FIXED** (S17, commit `9803e9dc0`). A parametrized regression now
persists a profile with `capabilities.llm_vision=false` (real lifecycle save, no
mocks) and asserts both a scan-only PDF and an image attachment refuse — pinning
the gate's coverage of every on-host read mode. The earlier-deferred note below is
superseded.

<!-- superseded deferral rationale, retained for history -->

**(superseded) Was DEFERRED** as a coverage nicety on confirmed-correct behavior. A
focused regression (an `llm_vision=off` profile refuses both a scan-only PDF and
an image attachment) needs profile-fact persistence plumbing the vision test
harness does not currently wire; it is a follow-up, not a close blocker.

### M2 (MEDIUM, ACCEPTED-NO-OP) — `config check` passes `lines` as a list, not a tuple

`_emit_envelope` accepts `lines: Iterable[str]`; a list satisfies the contract,
so there is no defect. Left as-is to avoid churn; recorded for completeness.

### L1 (LOW, CONFIRMED) — S09 (lean-core pyproject extras) is the only genuine deferred implementation item

Zero `TODO`/`FIXME`/`NotImplementedError`/`xfail`/`skip`/stub markers exist in
`provisioning.py`, `_capabilities.py`, `_capabilities_cli.py`, or `_check_cli.py`
(the `NotImplementedError`s in `_evidence_input.py` are deliberate persistence
tripwires). Torch relocation and — in a later pass on this campaign — the full
lean-core extras migration (S09) both landed; no deferred implementation items
remain.

### L2 (LOW, SOUND) — residual surface verified

Probes never raise on absence (typed `DependencyStatus` on every path);
`_active_profile_record` returns `None` on a locked store so the doctor/gates
degrade to the conservative global default; the gestor bar is unconditional and
applied first; the wizard persists all three capability facts to the exact schema
paths the resolver reads. All confirmed.

## Recommendations

- **Done:** H1 fixed with a no-allowlist conformance test that any future
  Google-write verb must satisfy. H2 resolves with it.
- **Done (later pass):** M1 — the `llm_vision=off` two-mode refusal regression
  landed (S17, commit `9803e9dc0`) via a real lifecycle-saved profile fact.
- **Done (later pass):** S09 — the capability-extras lean-core pyproject migration
  landed (commits `2490c33af` foundation, `dd6122263` doctor probes, `975a98e39`
  docs, `3a0ab7823` hexagonal feature-boundary guards). google / playwright /
  anthropic now install on demand via the `google` / `browser` / `anthropic`
  extras; the dev environment is unchanged; the package imports without any extra;
  each feature reached without its extra refuses with its own typed error naming
  `pip install aeat[<extra>]`; and the doctor reconciles each enabled capability
  against its extra. The feature-boundary guards — initially deferred on a
  layer-violation concern — were completed by siting the guard primitive in `core`
  (contract-legal for adapters) and making the eager-import adapters import-safe;
  real-behaviour import-blocker tests cover every boundary. No deferred items
  remain.
- **Process note:** during closeout the driving agent twice hit the shared-index
  hazard — once a peer `git commit` swept staged vault files into its commit, once
  a bare `git commit` (no pathspec) swept peer-staged work (a `filing/reconciliation`
  removal + regenerated api stubs) into a capability commit. The resulting tree was
  verified consistent (clean collection, conformant api stubs, no dangling imports),
  but the lesson stands: in this shared worktree always `git commit -- <pathspec>`,
  never bare `git commit`. This is already mandated by `aeat-git-worktree-safety`.
- **Peer-owned full-tree note:** the nitpicky docs build was red on a peer
  `_repository.py` `:meth:` xref (`save_with_secure_object_writes`), unrelated to
  the new onboarding page (which built clean). Fixed forward as an absorbed
  in-scope regression (commit `402918258`).

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

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->

- **Candidate (not yet codified — first encounter):** finding H1 (a
  capability-governed egress was gated at only one of its several entry points).
  **Proposed slug:** `capability-governed-egress-gated-at-every-entry-point`.
  **Rule:** every entry point that performs a capability-governed external egress
  (cloud evidence upload, on-host vision read, Google export to Sheets/Drive) must
  consult `resolve_active_capability` before the egress, and a no-allowlist
  conformance test must assert every such leaf is gated so a new verb cannot
  silently bypass the floor. Per the `vaultspec-codify` discipline this is recorded
  as a candidate, not promoted — it should hold across one more campaign cycle (the
  cloud/vision/google surfaces each gaining or moving a verb) before codification.