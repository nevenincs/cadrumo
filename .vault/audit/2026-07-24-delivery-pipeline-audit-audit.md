---
tags:
  - '#audit'
  - '#delivery-pipeline-audit'
date: '2026-07-24'
modified: '2026-07-24'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace delivery-pipeline-audit with a kebab-case feature tag, e.g. #foo-bar.
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

# `delivery-pipeline-audit` audit: `delivery pipeline audit campaign close`

## Scope

Operator-ordered full audit of the plugin delivery pipeline on self-hosted
runners (2026-07-24), forked into seven lanes: organization structure,
correctness, naming, metadata, secret scrubbing, end-to-end delivery
pipeline, and documentation/artifact cross-linking. Surfaces:
`.github/workflows/` (packaging-*, publish-release, pypi-upload),
`dev/packaging/`, `dev/release/`, `dev/runners/`, `dev/deploy/`,
`packaging/` (scoop, homebrew, mcpb, marketplace), `docs/download.md` and
the docs frontend. A fix wave applied every confirmed finding; a
fresh-context close review (independent reviewer) then re-verified the
whole commit range `30d4c53ce5..14719d463e` and its own blocking finding
was fixed before this close. Fix commits: `6ff8badf29`, `4690ddf2a6`,
`718faec471`, `87c1ca3481`, `0b59ecb561`, `d0da96326b`, `9bf4cc5962`,
`c94af5229b`, `8b9d63f5d4`, `4f95b784ec`, `4e0c72c926`, `58b8f26e57`,
`579b5178b1`, `ca0f561795`, `fe02a99b0c`, `d29404aff0`, `30d4c53ce5`,
`7b2f97c8d9`, `891e8adfe1`, `9c4bcf3e8f`, `7d129c6dd6`, `200d0af28c`,
`04ef8b3970`, `2d89791816`, `14719d463e`.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### delivery pipeline audit campaign close | {level} | {summary}

     followed by a paragraph carrying the detail. delivery pipeline audit campaign close is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### evidence-rows-asserted-not-observed | critical | PASSED evidence rows hardcoded isolation claims and accepted stale captures — FIXED

`dev/packaging/distribution_evidence_emit.py` minted rows whose
`ExecutionIsolation` booleans were hardcoded `True` (validated
tautologically) and accepted any pre-existing oracle capture against any
cohort with no version binding. Fixed: isolation flags derive from
oracle-recorded facts; the mint refuses a capture whose CLI version output
does not carry the cohort version on a token boundary (the close review
caught and closed a 0.2.1-vs-0.2.10 substring false-accept in the first
fix). Consequence for the release train: pre-campaign v0.2.1 oracle
captures refuse re-emission with an instructive error — the installed
oracles must be re-run against the cohort before the next publication.

### real-client-session-shipped-unscanned | high | operator session JSON shipped verbatim into public claude-* rows — FIXED

`dev/packaging/emit_real_client_evidence.py` passed operator-supplied
session JSON to public release rows with no secret scan; an embedded
email/token/session id would have published uncaught. Fixed: fail-closed
secret scan (token-shaped strings, emails) before minting. Residual low:
the walk scans string values only, not dict keys.

### pypi-upload-second-ungated-authority | high | pypi-upload.yml bypassed every publish gate with a workspace-reuse hazard — FIXED

The fast-follow workflow had no opt-in gate, swallowed download failure
with `|| true`, and never cleaned `dist/` on a persistent self-hosted
runner, so stale artifacts could publish for the wrong package. Fixed:
`CADRUMO_PUBLISH_ENABLED` gate first, stale-dist cleanup, hard download
failure, exactly-one-wheel/one-sdist guard, conformance test. Retirement
vs. hardening was adjudicated to hardening (the workflow was
operator-ordered).

### unpinned-user-install-closure | high | Scoop and MCPB installs resolved transitive deps live from PyPI — FIXED

`packaging/scoop/generate.py` and `packaging/mcpb/build.py` pinned only the
product wheels; every transitive dependency resolved fresh at user install
time, so an upstream release after cohort testing gave users an untested
closure. Fixed: `dev/packaging/uv_constraints.py` exports the frozen
uv.lock closure; Scoop passes a staged constraints file, MCPB embeds
constraint-dependencies. Deferred: no smoke lane yet asserts installed
versions equal the lock export at install time.

### gate2-blocker-check-fail-open | medium | readiness P0-blocker check silently passed on gh failure — FIXED

`dev/release/readiness.py` skipped the open-blocker check under
`--skip-network` on the CI publish path, and on gh absence/error degraded
to advisory. Fixed: Gate 2 runs the check in strict mode; an unresolvable
blocker state is now a blocking refusal.

### leak-sweep-token-gap | medium | Gate-3 publication leak-sweep ran with an empty token list — FIXED

The last-line sweep could not catch hostname/username residue. Fixed:
promotion-runner identity tokens fed to the sweep; comments state the
actual (this-runner-only) coverage honestly. Related medium fixed: push
tokens no longer persist in the clone `.git/config` (http.extraheader auth
plus workdir cleanup); workspace roots now scrubbed from evidence.

### structure-and-naming-hygiene | medium | dead lane, orphaned generator, plan-step tags in shipped CI identifiers — FIXED

`dev/packaging/smoke_plugin_validate.py` deleted as a superseded dead lane;
the manual corpus-text extractor gained a `just` re-run path; the
`cadrumo-s24`/`cadrumo-s20` plan-step scratch-root names were renamed to
semantic homebrew/scoop names in lockstep across the workflows and all
three runner cleanup scripts; MCPB tracked manifest version became a
`0.0.0` sentinel with a readiness gate binding the stamped bundle version
to the cohort (a first-pass regression here was caught and repaired the
same day); `dev/packaging/source_preflight.py` gained its missing test
coverage; various PowerShell 5.1 regressions in `acquire_scoop.ps1` were
re-ported verbatim from the smoke template.

### docs-download-surface-ungated | medium | download page hand-authored, over-promising, with no generator or gate — FIXED

`docs/download.md` promised per-channel install commands it never carried,
omitted MCPB as a channel, and had no drift gate. Fixed: channel facts live
in `docs/_data/download_channels.toml`, rendered by
`dev/docs/download_matrix.py` into a generator-owned zone (parity-gated
against `ArtifactKind`, availability-gated against the distribution-claims
test), with a release-time `download-latest.json` attached by
publish-release and pulled by the docs deploy for direct version-pinned
download links (progressive enhancement, silent degrade). Locale
catalogues re-synced and the es/ca/hu deltas translated.

### scoop-channel-structurally-blocked | medium | Scoop acquisition cannot run on the current fleet — OPEN (status, not defect)

The Windows-container preflight fails on every run because the self-hosted
Windows host does not run Docker in Windows-container mode; the
scoop-windows-x86-64 evidence row cannot mint and readiness hard-requires
it, blocking the whole promotion train until a container-mode window is
scheduled. Fail-closed and correct; operator scheduling item.

### relocation-atomicity-slip | medium | the corpus-sync relocation ran as two commits — RECORDED

The `relocation:sync_aeat_record_design_corpus` move added the `dev/corpus`
copy while leaving the 545-line duplicate in `dev/packaging` for a two-commit
window (pathspec omitted the rename source); the follow-up commit completed
the deletion. No consumer imported the dead copy inside the window, and the
final state is verified residue-free. Recorded as a process slip against the
atomic-relocation discipline; the corrective pattern (post-commit duplicate
sweep) held.

### rulings-batch-close-review | low | fresh-context review passed the batch code-grade — CLOSED WITH FOLLOW-UPS

The independent review of the rulings + identity range verified spec
conformance, deletion residue, gate liveness, and anti-tautology across all
sixteen changed test files, and ran the readiness/publish gates green (79
passed). Its one blocking finding — the D5 identity ruling existed only in the
tree, contradicting the accepted decision record — is resolved by the D5
amending ruling now recorded in the delivery-pipeline ADR. Its hardening
follow-ups (negative test for the manifest author refusal, real-behavior
execution test for the minimum-uv guard, environment-marker exactness in the
constraint-effect assertion) were dispatched and land as the campaign's final
commits.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

Release-driver actions before the next publication (from
evidence-rows-asserted-not-observed): re-run the installed tax and MCP
oracles against the promotable cohort — pre-campaign captures refuse
re-emission by design. Schedule the Windows container-mode window for the
Scoop lane (scoop-channel-structurally-blocked).

Non-blocking follow-ups (from unpinned-user-install-closure and the close
review): an install-time smoke assertion that the constrained Scoop/MCPB
install resolves exactly the lock-export versions; a minimum-uv note or
bootstrap check for the MCPB constraint-dependencies mechanism; extend the
real-client secret scan to dict keys; when a channel's distribution
evidence lands, flip its `availability` in
`docs/_data/download_channels.toml` to `available` in the same change so
the literal install commands render.

Deferred decisions surfaced but not taken here: whether to retire
`pypi-upload.yml` outright once Gate 3 is armed (hardened for now);
whether `dev/packaging/sync_aeat_record_design_corpus.py` moves to a
corpus-owned home; whether the data-companion Development Status
classifiers (Alpha vs the root Beta) and the MCPB author string are
intentional.
