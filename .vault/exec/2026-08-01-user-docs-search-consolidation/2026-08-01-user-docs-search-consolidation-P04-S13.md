---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:13ebca5911bf16961e922987641318bbf5049e4daef456a04166a5d86cf6b8c9'
step_id: 'S13'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Redeploy and live-verify the full-mode index, the casilla destination pages, and the language roots, recording the live checks in the exec record

## Scope

- `dev/deploy/`

## Description

- Ground the deployment and per-root parity contract with `vaultspec-rag` and inspect the current deployment script.
- Attempt the authorized deployment preflight after the source/build work was allowed to proceed.
- Check cloud credentials before mutating any live root; do not fabricate a publish or live verification when authentication is expired.

## Outcome

Deployment was intentionally not performed. The source deployment script is configured for full Pagefind mode and all four language roots, but the local AWS session is expired. The required live publish and post-publish checks therefore remain open.

## Verification

`aws sts get-caller-identity`

`aws: [ERROR]: Your session has expired. Please reauthenticate using 'aws login'.`

No deployment, root mutation, cache invalidation, or live URL claim was made.

## Notes

The strict en/es/ca/hu builds also remain red on the five known sequence/product divergences recorded in P04.S12/P03.S08. Once the user reauthenticates and the source tree reaches the required full-green build boundary, this step can resume without changing the deployment contract.

### 2026-08-06 current full strict preflight timeout

The current full strict preflight command, `uv run --no-sync python -m dev.docs.build --strict docs/conf.py`, ran for 304.372 seconds and exited with code 124 from the command timeout before returning an actionable build failure or a green result. This is an unverified timeout boundary, not evidence for changing source, refreshing golden artifacts, closing the gate, or publishing deployment. AWS STS authentication remains expired, so the live deployment proof is still unavailable.

### 2026-08-06 current strict build legal-corpus failure

The longer retry of `uv run --no-sync python -m dev.docs.build --strict docs/conf.py` reached Sphinx `builder-inited` and exited with code 1. Registry validation failed before page generation because 39 legal references could not resolve exactly one bundled corpus unit for their declared anchors, including Ley 35/2006 arts. 68.1-68.5, Orden HAC 56/2024 art. 1, Orden HAP 1732/2014 art. 2, Ley 37/1992 and several other Ordenes/RD references. This is an actionable legal-corpus data gate; no resolver fallback, source invention, artifact promotion, or deployment was performed.

### 2026-08-06 current strict build sequence-golden failure

The current strict retry cleared the registry legal-corpus validation after the bounded resolver and sidecar repair. It then reached the sequence-golden gate and exited with code 1 on nine divergences caused by concurrent peer changes (invoice option requirements, category ordering, profile-history ordering, ledger split behavior, and localized registry output). This is not a legal-search failure; the step remains open until a later full build is green.

### 2026-08-11 formal carry-forward

This row stays OPEN by operator decision. No deployment was performed, no root was mutated, no cache was invalidated, and no live URL claim is made.

The source deployment configuration is ready: full Pagefind mode is pinned for every root and all four language roots are configured. The blocker is solely that the AWS session is expired, so the publish and its post-publish checks cannot run.

Three checks remain unproven and are named here so the close cannot imply them: that every deployed root's entry carries the injected record corpus in that root's language, that the casilla destination page resolves live, and that the `es`, `ca` and `hu` roots respond.

### 2026-08-12 publish readiness: one blocker cleared, one found, and it is not this campaign's

Re-authentication alone will not produce a successful publish. Stating that plainly, because the previous record left the impression that the credential was the only thing missing.

The publish builds every root through the docs driver with the strict flag, which is nitpicky warnings-as-errors, and it does that BEFORE it uploads anything. So any build warning fails the publish outright.

Cleared this session: the three translated roots were red on two credential-free causes, both this campaign's own surface and both fixed. Two unauthored projection-only casilla labels aborted the reference generator, and five stale preview pages in the generated directory sat in no toctree. The generator now prunes pages a render no longer produces, so that second cause cannot recur.

Still blocking, and NOT this campaign's: the English root is the one root built at full scope, and its nitpicky build reports unresolved py-domain cross-references. The cause is 23 source modules with no API stub, so autodoc cannot resolve the types their docstrings name. Every one belongs to another campaign's surface -- the M303 filing and aggregation modules, the IVA deduction and regimen rows, the profile sync store, the work-progress and official-box core types, the LLM preconditions. None is a docs-side module; the stub scaffold walks the shipped package only, so nothing this campaign owns can appear in that list.

Deliberately not fixed here. The scaffold is tree-wide, so one run would emit stubs for all 23, and the standing rule is to stage only the stubs whose added lines name your own module and leave the rest to their owners. Regenerating and committing another campaign's API surface to unblock a deploy would be exactly the opportunistic peer edit that rule exists to prevent.

So the publish needs two things, in either order: the credential, and those owners running the stub scaffold for their modules. The first is the operator's, the second is theirs.

### 2026-08-12 the credential is no longer the blocker; the stub gap has grown and the build could not be reconfirmed

Re-checked `aws sts get-caller-identity`: it now succeeds. The one blocker this row's own last entry attributed solely to the operator is cleared, and nothing here did the re-authenticating.

That does not clear the OTHER blocker the same entry named as not this campaign's. `python -m dev.docs.apidocs scaffold --check` currently reports 29 missing stubs, up from the 23 measured that day, still none belonging to this campaign's surface (the same M303/IVA/TUI/profile-sync/LLM module set). `_publish` runs the identical strict full build before any upload, so nothing suggests it would pass now, and the gap is larger than when it was last measured.

Attempted a fresh strict full build to get direct current evidence rather than resting on the stub census alone. A first attempt stalled under concurrent shared-tree load and never returned a result; it is SUPERSEDED by the second attempt below and carries no signal of its own -- do not re-chase it. A second, separately launched attempt completed and corrects the picture: it passed the stage the stub census predicted would fail, then failed at the sequence-golden gate on the same class of divergence this row already recorded on 2026-08-06/07 -- CLI-sequence drift on M303 filing evidence and wallet notices, plus two per-machine hardware-fact fields no golden fixture can pin across runs. No `publish` was run either way; the precondition is unmet regardless of which gate reds first, and neither is this campaign's surface.

No deployment, root mutation, cache invalidation, or live URL claim was made. P04.S13 remains open, blocked on the cross-campaign stub gap this campaign cannot close by itself and, independently, on a clean window to confirm the build precondition.

### 2026-08-13 re-verified: both technical preconditions are now CLEAR, only the deploy authorisation remains

Re-established from direct probes this session rather than inherited from the entries above, because both of the blockers those entries name have changed state.

**The API stub gap is closed.** The census now reports the stub tree conformant with no drift detected. The 31 missing stubs recorded earlier on 2026-08-13 — the M303 filing, aggregation, regimen-simplificado, prorrata and exonerado rows, the IVA deduction facts, the TUI work-review screen, the profile sync-runs store, the calc-sheets export service, the filing-evidence and filing-projection core types, and the LLM preconditions modules — have been closed by the campaigns that own them. This campaign ran no scaffold, consistent with the tree-wide stage-your-own-lines discipline that forbade it closing a gap in modules it does not own.

**The cloud session is valid.** The identity call succeeds. The credential that had lapsed twice across earlier sessions is live, and nothing in this session re-authenticated it.

**The live state is unchanged.** The apex answers 200 but serves a stale build last modified 2026-07-12. The English, Spanish, Catalan and Hungarian roots and the casilla destination page all answer 404, confirmed on response headers.

So the blocker on this row is no longer a technical precondition. It is the deploy authorisation itself: publishing is outward-facing, and an agent may not perform it however clear the path in front of it looks. A valid credential is emphatically not an authorisation to use it.

What changed in this campaign's favour is that the publish is now checkable before it runs. The build-and-validate prefix a publish performs is reachable as its own verb, requires no session, writes nothing outward, and returns the complete pre-upload verdict: every root's artifact set, each root's own canonically-rooted sitemap, each root's record-bearing index, the apex's own search bundle, and an apex entry reaching every built language. An operator preparing this deploy can now get that verdict in advance instead of discovering a defect mid-publish. It stops at the upload, so it substitutes for nothing this row claims.

One caveat stated plainly rather than glossed: a clean stub census is not proof that the full strict build passes end to end. The entries above also record sequence-golden divergences and machine-specific hardware-fact fields as a separate, recurring red. That class is unverified today and the dry-run verb is exactly how to settle it without publishing.

P04.S13 remains open. No deploy, cache invalidation or live mutation was attempted.

### 2026-08-13 the sequence-golden class: measured three ways, no verdict obtainable

The entry above flagged the recurring sequence-golden divergences as unverified. They were then actively measured, because the distinction between a cleared precondition and a still-red one decides what an operator is being asked to authorise. Three attempts, none of which produced a divergence:

- The goldens gate under parallel pytest lost three workers to "node down: Not properly terminated". That is this worktree's documented backing-share failure under concurrent I/O and carries no information about the code.
- Re-run sequentially, as the local-execution discipline requires before blaming code: five sibling tests passed, then the goldens test itself hit its own deadlock ceiling while blocked inside its subprocess pool. It reported zero divergences because it never reached a verdict.
- Run directly outside the pytest ceiling, unsharded: still executing after roughly fifty minutes wall and thirty-eight minutes of CPU, on a box carrying 140 concurrent Python processes from other agents.

So the honest state of this class is UNMEASURED UNDER LOAD, not red. No failing signature is named here, because none was observed, and restating the earlier record's divergences as current would be an inherited claim rather than a measurement. If a later run returns a verdict it belongs in this record with its signature and its owning surface.

The distinction matters for exactly one reason: the other precondition this row's history named, the missing API stubs, is now definitively CLEAR. Nothing technical is known to be blocking a publish. That is not the same as knowing nothing is, and the dry-run verb remains the way to settle it without writing anything outward.
