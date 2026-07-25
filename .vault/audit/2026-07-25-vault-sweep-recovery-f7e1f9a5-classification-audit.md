---
tags:
  - '#audit'
  - '#vault-sweep-recovery'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
  - "[[2026-07-24-worktree-commit-attribution-audit]]"
---

# `vault-sweep-recovery` audit: `Classification of the 119 unexamined records deleted by f7e1f9a523`

## Scope

`f7e1f9a523` ("chore(vault): commit accumulated exec-record changes", landed
2026-07-17) deleted 127 exec records without a targeted pathspec. Eight belong
to the compatibility-lifecycle plan and were already restored and recorded
separately. This record covers the remaining 119, spanning twenty-three
feature clusters dated 2026-04-12 through 2026-05-14 — the project's first six
weeks, entirely under the pre-rename `src/aeat/` package root (the rename to
`src/cadrumo/` landed 2026-07-12 in `8d4cd1efce`).

Method: for each cluster, the true addition commit was located with
`git log --follow --diff-filter=A`, its original content read with
`git show <sha>:<path>`, and the described packages/classes checked for
survival under any name in the current tree. Given the volume, this was a
representative per-cluster pass (the highest-level summary/closeout record per
cluster plus decisive existence checks), not an individual open of all 119
files; every cluster's defining facts were uniform and decisive across every
sample taken, including repeated samples on the two largest clusters. Read
this record's confidence accordingly: high on the classification and the
discriminator below, cluster-representative rather than exhaustively
per-file on line-by-line content.

## Findings

### absence-of-a-governing-plan-is-the-discriminator | high | The reusable check is "does a plan still reference this cluster," not "does the work look finished"

This is the load-bearing finding and the reusable test for any future sweep
investigation. The compatibility-lifecycle harm was specifically that a plan
still read complete while the evidence for its completeness had been deleted
— the count stayed green, the grounding under it was gone. That is a
false-green, and it is the only shape of harm a sweep can actually cause
against `plan-closure-requires-exec-records`.

A swept record with no plan pointing at it is a different event entirely: it
is bookkeeping loss, not evidence loss against a live claim. Distinguishing
the two requires exactly one check per cluster, run against the CURRENT vault
tree, not against the record's own content or how complete the described work
looks: does any plan document — live under `.vault/plan/` or properly retired
under `.vault/_archive/plan/` — still carry this cluster's feature tag. If
yes, the swept record is the actionable case: find the corresponding step,
confirm it reads checked, and that is the false-green to fix. If no plan
exists anywhere, no reader can currently be misled by the record's absence,
regardless of whether the underlying work was finished, abandoned, or
superseded — there is no N/N claim left standing for it to falsify.

Applied here: `.vault/plan/` and `.vault/_archive/plan/` were checked by name
for all twenty-three clusters. Zero carried a governing plan, live or
archived. That is the finding that closes the question, independent of and
prior to any judgment about whether each cluster's implementation still
exists.

### all-119-classified-deliberately-retired | high | Every cluster predates the package rename and describes superseded architecture

All 119 records classify as deliberately retired. Zero restorations. Zero
records remained genuinely ambiguous after the plan-existence check plus a
representative content/survival sample.

Per-cluster file counts (23 clusters, 119 files): `google-oauth` 53,
`self-healing-sync` 10, `submission-engine` 8, `casilla-db` 7,
`modelo-115-calc-verify` 5, `auth-protocol` 5, `aeat-filing-detail-fetch` 5,
`r1-vat-enumeration` 4, `operator-workflows-expansion` 2, `google-auth-ux` 2,
`aeat-access-gate` 2, `google-workspace-mcp-auth` 2, `docs-rewrite` 2,
`base-module-structure` 2, `secure-persistence-foundation` 2 (two separate
2026-04-27/28 files), `test-clave-movil-mark-fix` 1, `modelo-111-calc-verify`
1, `synthetic-filing-fixtures` 1, `status-reader` 1, `setup-wizard` 1,
`notifications-inbox` 1, `gsuite-bootstrap` 1, `data-storage` 1.

Every sampled cluster's original content scopes to `src/aeat/...` — the
pre-rename root — and describes packages or classes verified absent from
`src/cadrumo/` under any current name: `aeat.casillas` (a hand-maintained
casilla corpus, superseded by the TOML-authored `ValidatedRegistryAuthority`
registry per `aeat-registry-authority-flow`), `aeat.inbox`, `aeat.storage`
(the old config-field shape), `aeat.setup`, `aeat.status`, `aeat.testing`,
`aeat.financial.vat`, `aeat.mcp`, `aeat.auth._gate`/`_authenticator`,
`aeat.submission._engine`, `aeat.formulas._rulesets`,
`aeat.declaracion._extractors`, `aeat.models._citation_registry`. None exist
under any name at HEAD.

### google-oauth-has-explicit-documented-supersession | high | The dominant cluster (53/119) is not inferred-retired, it is stated-retired

`google-oauth` is 53 of the 119 files and carries the strongest possible
supersession signal: not architectural drift inferred from absence, but an
explicit accepted ADR. The live `google-oauth` ADR dated 2026-07-12 states
verbatim that it "supersedes `2026-05-13-google-oauth-adr` in whole," and the
current governing plan for this domain is a separate, live document, `2026-07-14-google-optional-adapter-boundary-plan`.

One nuance worth recording rather than flattening: the same ADR states that
an earlier sibling ADR "remains accepted for the provider protocol," and
`get_storage_provider`/`GoogleDriveProvider`/`LocalFileSystemProvider`/`ProviderKind`
were confirmed still present under `cadrumo.adapters.outbound.storage` —
relocated and renamed, not deleted. The earliest phase of this cluster's
underlying mechanism has genuine code continuity even though its own exec
records do not survive. This does not change the classification: no live
plan cites the old records under either name, so restoring them closes no
gap; it is recorded so a future reader does not read "no surviving code" into
a "no surviving plan" finding for this specific cluster.

### two-files-are-non-events-not-classification-calls | low | One was already safely archived, one was never real content

`.vault/exec/2026-04-12-synthetic-filing-fixtures/2026-04-12-synthetic-filing-fixtures-phase1-summary-exec.md`
had already been properly archived via the standard mechanism before the
sweep: `.vault/_archive/plan/2026-04-12-synthetic-filing-fixtures-plan.md` and
a corresponding archived exec record both exist, with paths already updated
for the later `src/aeat/testing` -> `src/aeat/domain/testing` restructuring.
The swept copy was a stale, un-updated duplicate left behind in the live
`.vault/exec/` tree; the archive holds the corrected, authoritative version.
Nothing was lost.

`.vault/exec/2026-04-27-secure-persistence-foundation-exec.md` was never
filled in — its entire body at the original commit is still the unedited
scaffold comment block ("REQUIRED TAGS (minimum 2)...", placeholder
instructions). It was never a real record, so its deletion carries no
evidentiary loss.

## Recommendations

Apply the discriminator in `absence-of-a-governing-plan-is-the-discriminator`
as the standing check for any future suspected sweep, before any per-record
content judgment: does a plan, live or archived, still carry the cluster's
feature tag. Only a cluster that passes that check (a plan exists and reads
checked against the missing record) is an actionable false-green; everything
else is bookkeeping loss and does not warrant restoration on its own.

No further action needed on the 119 records themselves — all twenty-three
clusters are closed as deliberately retired with the grounding above. If a
specific cluster's classification is later disputed, the representative
sampling this pass used (documented in Scope) means an exhaustive per-file
open of that one cluster, not the whole 119, is the right next step.
