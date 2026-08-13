---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9c812f8ea79fe0ec6fe4cfeaaffb1518ba0ead771133dc7df5901114330bcfd0'
step_id: 'S12'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Close the gap that leaves the built language roots unreachable on the live site and prove es, ca, and hu roots respond after deploy

## Scope

- `dev/deploy/docs_static_site.py`

## Description

- Run focused vaultspec-rag discovery over the deployment surface and read the accepted plan, ADR deployment ruling, and existing P04 execution records.
- Inspect the committed CloudFront router and publisher sync path for the localized-root delivery mechanism.
- Probe the live Spanish, Catalan, and Hungarian documentation roots and their expected public paths.
- Check the local AWS CLI session boundary without changing cloud state.

## Outcome

P04.S12 remains open. The repository already contains the intended local mechanism: the CloudFront viewer function maps each language root to its index and the publisher syncs the complete built tree beneath the `docs/` prefix. The live acceptance property is not satisfied: the `es`, `ca`, and `hu` roots each returned HTTP 404.

## Notes

No implementation files changed. The AWS CLI is installed, but `aws sts get-caller-identity` reports that the session has expired and the worker's CloudFormation inspection could not complete. The deployed routing/object state therefore cannot be distinguished from the committed mechanism without re-authentication. Do not close this step or dispatch the redeploy/live-verification step until an authenticated operator session proves the roots respond.

### 2026-08-06 authorized build/deployment continuation

Strict user-doc builds for en, es, ca, and hu each stop on the same five known sequence/product divergences: profile-setup history ordering, correct-review history expectation, Modelo 100 export authority absence, the Modelo 303 verification-report localized divergence, and the Renta assembly localized-help divergence. No golden was refreshed and no authoritative source was invented.

Deployment was not attempted because `aws sts get-caller-identity` reports an expired session and requires reauthentication. P04.S12 remains open; P04.S13 has no deploy evidence.

### 2026-08-06 current full strict preflight timeout

The current full strict preflight command, `uv run --no-sync python -m dev.docs.build --strict docs/conf.py`, ran for 304.372 seconds and exited with code 124 from the command timeout before returning an actionable build failure or a green result. This is an unverified timeout boundary, not evidence for changing source, refreshing golden artifacts, closing the gate, or publishing deployment. AWS STS authentication remains expired, so the live deployment proof is still unavailable.

### 2026-08-06 current strict build legal-corpus failure

The longer retry of `uv run --no-sync python -m dev.docs.build --strict docs/conf.py` reached Sphinx `builder-inited` and exited with code 1. Registry validation failed before page generation because 39 legal references could not resolve exactly one bundled corpus unit for their declared anchors, including Ley 35/2006 arts. 68.1-68.5, Orden HAC 56/2024 art. 1, Orden HAP 1732/2014 art. 2, Ley 37/1992 and several other Ordenes/RD references. This is an actionable legal-corpus data gate; no resolver fallback, source invention, artifact promotion, or deployment was performed.

### 2026-08-06 current strict build sequence-golden failure

The current strict retry cleared the registry legal-corpus validation after the bounded resolver and sidecar repair. It then reached the sequence-golden gate and exited with code 1 on nine divergences caused by concurrent peer changes (invoice option requirements, category ordering, profile-history ordering, ledger split behavior, and localized registry output). This is not a legal-search failure; the step remains open until a later full build is green.

### 2026-08-07 read-only live-root re-probe

A read-only GET probe of the four public documentation roots returned:

- `https://cadrumo.neve.md/docs/`: HTTP 200.
- `https://cadrumo.neve.md/docs/es/`: HTTP 404.
- `https://cadrumo.neve.md/docs/ca/`: HTTP 404.
- `https://cadrumo.neve.md/docs/hu/`: HTTP 404.

No deployment, cache invalidation, or live mutation was attempted. P04.S12 remains open; the three localized roots are still not proven reachable.

### 2026-08-07 current local parity confirmation

The current shared-tree local integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` returned `25 passed in 541.71s`, exercising `en`, `es`, `ca`, and `hu` through the production local Pagefind path. This does not alter the live-root result: `/docs/` returned HTTP 200 while `/docs/es/`, `/docs/ca/`, and `/docs/hu/` returned HTTP 404 on the read-only probe. P04.S12 remains open; no deploy, cache invalidation, or live mutation was attempted.

### 2026-08-07 current all-locale local parity rerun

The authorized real-behaviour integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` completed with `25 passed in 383.05s (0:06:23)`, exercising `en`, `es`, `ca`, and `hu` through the production local Pagefind path. This confirms the local full-record projection remains present across all four roots.

The live read-only probe remains unchanged: `/docs/` returned 200, while `/docs/es/`, `/docs/ca/`, and `/docs/hu/` returned 404. AWS STS authentication remains expired, so P04.S12 remains open and no deploy or cache invalidation was attempted.

### 2026-08-11 formal carry-forward

This row stays OPEN by operator decision, and the deferral is recorded rather than absorbed into a green close.

The committed mechanism is present and unchanged: the viewer function maps each language root to its index, the publisher syncs the complete built tree, and the publish path refuses outright when any built language is unreachable from the language entry. What is missing is proof, not code.

The live acceptance property is still unsatisfied: the `es`, `ca` and `hu` roots each return HTTP 404. That evidence is preserved as-is. It cannot be advanced because the AWS session is expired and re-authentication is an operator action; without it the deployed routing and object state cannot be distinguished from the committed mechanism.

Nothing here may be read as a claim that the localized roots respond. The campaign closes with this row open.

### 2026-08-12 the publish would have failed on its own build; two blockers removed

This row stays open on the live proof, but its engineering half moved materially, and what was found changes the value of the pending re-authentication.

The live state was re-verified directly this session rather than inherited from the earlier record. Reading a public site needs no credentials, only publishing does, so the roots were probed over plain HTTPS: the default root answers 200 while `/es/`, `/ca/`, `/hu/`, `/en/` and the casilla destination page all answer 404. The gap is real and current.

More useful: the publish would have failed even with valid credentials. It builds every root through the docs driver under strict settings before it uploads anything, and all three translated builds were red. Two independent causes, both credential-free and both now fixed.

First, the casilla reference generator aborted at builder-inited because `docs.casilla.input_kind.projection_only` and its count sibling had no authored value. A new projection-only input kind had entered the schema, and the surface derives its label keys from that enum precisely so a new member demands its string rather than rendering nothing. The design worked; the strings were simply never written. Authored in all four languages on the register the sibling kinds establish.

Second, five stale preview pages sat in the generated casilla directory from an earlier session, in no toctree, so the nitpicky build warned and failed. Nothing in the tree emits them any more. They are gitignored build residue, not source, and were moved aside rather than deleted outright.

All four roots now build clean: es and ca passed immediately, and hu passed on a sequential re-run after a concurrent registry write raced its cache fingerprint the first time.

So the remaining blocker really is only the credential. Before this session a re-authentication would have hit a failing build; now the publish path is clear up to the upload.

One recurrence risk recorded rather than fixed: the generator does not prune its own output directory, and that directory is gitignored, so stale pages survive across builds and can red the strict build again. A pruning pass belongs with the generator's owner.

### 2026-08-12 credential cleared; the outstanding blocker is the cross-campaign stub gap, not AWS

`aws sts get-caller-identity` now succeeds. The session that blocked every prior attempt in this row is no longer expired, and nothing in this pass re-authenticated it -- it was already valid when checked.

That does not make the mechanism live. `python -m dev.docs.apidocs scaffold --check` reports 29 missing stubs at HEAD, up from the 23 the sibling P04.S13 entry named the same day, none under any module this campaign owns: M303 filing and aggregation, IVA deduction and régimen rows, the TUI review screen, the profile sync store, and LLM precondition modules. The tree-wide scaffold-and-stage-your-own-lines discipline forbids this campaign closing that gap by running the scaffold itself.

A fresh attempt at the strict full build that `_build_site` runs before any AWS call was made to get direct evidence rather than relying on the stub census alone. A first parallel attempt produced no further output for over ten minutes under heavy concurrent shared-tree load and never returned a result; it is SUPERSEDED by the second attempt below and should not be re-chased or treated as a pending signal. A second, separately launched attempt completed: it got past the stage the stub census predicted would fail and reached the sequence-golden gate, where it failed on divergences matching the standing, already-recorded pattern -- CLI-sequence output drift on M303 filing-evidence requirements and wallet notices, and two machine-specific hardware-fact fields (`free_memory_bytes`, `free_vram_bytes`) that a golden fixture cannot pin across runs. This is the same class of red this row's own history already named on 2026-08-06/07, not the stub gap, and not anything under `dev/docs/`.

The live read-only probe is unchanged: `/docs/` answers 200; `/docs/es/`, `/docs/ca/`, `/docs/hu/` answer 404. No deploy, cache invalidation, or live mutation was attempted; a valid credential does not justify a publish attempt while the build precondition is unconfirmed and a known, cross-campaign content gap sits in front of it. P04.S12 remains open.

### 2026-08-13 fresh re-check: both blockers persist and the cross-campaign gap widened

Re-verified from a clean context rather than trusting the prior entries. `aws sts get-caller-identity` again reports an expired session -- the credential has lapsed a second time since the 2026-08-12 clearance. `python -m dev.docs.apidocs scaffold --check` now reports 31 missing stubs (up from 29), still none under any module this campaign owns: the M303 filing/aggregation/regimen-simplificado/prorrata/exonerado-390 rows, IVA deduction facts, the TUI work-review screen, the profile sync-runs store, the calc-sheets export service, filing-evidence and filing-projection core types, and the LLM preconditions/supply-nature modules. The named modules match the same cross-domain surfaces recorded on 2026-08-12, confirmed again by full name today.

The live read-only probe is unchanged: `/docs/` answers 200; `/docs/es/`, `/docs/ca/`, `/docs/hu/` answer 404.

No implementation files changed, no scaffold was run (the tree-wide scaffold-and-stage-your-own-lines discipline forbids this campaign closing a gap in modules it does not own), no deploy, cache invalidation, or live mutation was attempted. P04.S12 remains open. The blocker is the same documented failure mode as every prior entry: a full-tree build precondition red for reasons entirely outside this campaign's surface, compounded by an operator-owned credential that keeps re-expiring between sessions.

### 2026-08-13 the code half lands: the emission is now verifiable without a publish

The row's split was re-measured rather than inherited, and the opening sentence's premise is confirmed obsolete. The publisher already carries complete per-root handling: `_build_language_roots` builds each root under its own environment and canonical base URL, `_validate_language_roots` requires the full `_REQUIRED_ARTIFACTS` set plus a sitemap rooted at that language's own sub-path plus a record-bearing index on every root, `_validate_language_entry` refuses an apex that strands any built language, `_public_delivery_checks` already carries a 200 expectation for every localized root, and the committed CloudFront viewer function rewrites `/docs/es/` to that root's `index.html`. No language-root reachability defect remains in the code.

What was genuinely missing was narrower and more useful: **none of that validation could be run without publishing.** The whole build-and-validate prefix lived inline inside `_publish`, behind an AWS session, a provisioned stack, a distribution-alias check and an authorization guard, with `_sync_site` as its very next statement. So the one check that would catch a root landing incomplete could not run until bytes were already going to the live destination. The sibling landing-page publisher had solved exactly this with a `dry-run` verb; the docs publisher had none.

Landed in `dcf31c758a`:

- `_build_site_roots` and `_validate_built_site` factor the publish's pre-upload prefix into ONE composition. `_publish` now calls exactly those two functions, so the dry run cannot drift from what a publish actually checks — a second composition would be free to diverge, and the divergence would only ever surface on the live site.
- `dev.deploy.docs_static_site dry-run` builds every root and runs every validation, uploading nothing. It deliberately requires no AWS session and no publish authorization: unlike the sibling's dry run, whose subject IS the S3 sync, every check here reads the built tree. A pre-publish check available only to a credentialed caller is unavailable exactly where it is most useful — and this row's own history is the proof, since the credential lapsed twice and blocked every prior attempt.
- Three real-behaviour gates in `dev/deploy/tests/test_docs_static_site.py` run the production validators over a real on-disk multi-root tree: the complete matrix passes, a root missing a required artifact refuses, and an apex entry that strands a root refuses. Their teeth are structural — drop `_validate_built_site` from the dry run and both refusal gates go red, with no edit to production code needed to prove it.
- A `docs-site-dry-run` recipe in the justfile's `docs` group, not `deploy`: it needs no session and writes nothing outward, so it is a build-and-check verb by that file's own stated taxonomy.

Gates run: `dev/deploy/tests` plus the justfile-scanning `test_justfile_release_guidance` and `test_ci_workflow` — 74 passed. Ruff clean.

What this does NOT claim. The live-response half is untouched and stays rowed: `/docs/es/`, `/docs/ca/` and `/docs/hu/` are not proven to respond, and nothing here may be read as claiming they do. Nor does the verb make the deploy green — this row's 2026-08-12 and 2026-08-13 entries record a full-tree build precondition that is red for reasons entirely outside this campaign (31 missing API stubs owned by other campaigns, sequence-golden divergences, machine-specific hardware facts). The verb's value is that this precondition is now MEASURABLE offline, by anyone, at any time, instead of being discoverable only at the moment of publishing.

### 2026-08-13 honesty review corrections to the entry above

A fresh-context review confirmed every mechanism claim in the entry above against current code, individually rather than inherited, and confirmed the dry-run verb is real rather than ceremony: its two refusal gates run production validators over a real on-disk multi-root tree and would go red if the validation were dropped, and its build seam matches this module's own documented DI precedent. Three corrections and additions follow.

**The composition is now gated.** The entry above leaned on an anti-drift property that was true by construction and enforced by nothing: re-inlining the validation calls into the publish, the exact shape that existed before the extraction, would have reintroduced a dry run that passes where a publish refuses, with a green suite. A gate now reads the publish's own call sequence, requires build then validate then upload, refuses the re-inlined form by name, and pins the dry run's default build to the shared composition. Proven to bite by re-inlining the validation in a copy of the source outside the repository and confirming the verdict flips to red.

**The dry run's verdict is not yet the publish's verdict.** The shared validation covers the apex entry page and the language roots but NOT the apex root's own Pagefind bundle, while the post-publish index verification includes the apex and raises when that built file is absent — after the upload and the cache invalidation. So an apex root that would fail the publish's own index check still passes the dry run. This is rowed as an open step rather than absorbed, because it turns on an unresolved contradiction about what the apex owes at all, and on the fate of an uncalled validator that would have covered exactly this.

**One prose correction**, the same one recorded against the sibling row: the claim that a localized build with no output directory "cleared that root's non-canonical entries on the way in" misstates the mechanism. That function removes stale entries directly under `docs/_build` that are not `html` and never reaches inside `html`. The English root was polluted, not cleared, and the true second cause of the observed residue was the full-build orphan sweep deleting every page of every nested language root.
