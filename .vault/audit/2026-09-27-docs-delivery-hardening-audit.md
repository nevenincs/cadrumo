---
tags:
  - '#audit'
  - '#docs-delivery-hardening'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:9377d349d7842f7d99e74d11fa8368f8b8a7e5b53acdb6d953c7636a858ab5e5'
related:
  - "[[2026-09-27-docs-delivery-hardening-plan]]"
---
# `docs-delivery-hardening` audit: `Static delivery implementation and migration`

## Scope

Integrated review of S01 and S02 against the accepted static documentation delivery ADR. Review performed in this session, not independently. Inspected manifest validation, complete inventories, storage isolation, local/CI deployment locking, native redirects, route switching, failure recovery, credential scope, monitoring, and the release guide. Live migration remains S03.

## Findings

### migration-identity | high | Same-release migration needs an explicit static-delivery marker

The old proxy and candidate serve the same release identifier. Release-only polling could accept an old edge during migration. Add a native delivery header and require it on both public roots before recording activation. Preserve generic release checks for recovery to the preceding proxy.

### displaced-publisher | medium | Remove the unused executable proxy publication surface

The new publisher no longer calls the old Worker deploy helper, but its bindings, module, and tests remain. Remove that displaced source path and its command consumers; retain the deployed proxy and ignored downloaded module only as migration recovery evidence until cutover is verified.

### native-http-limitations | medium | Platform conditional precedence remains imperfect

Candidate HTTP evidence in `var/docs-hardening/candidate-http.json` proves strong HTML ETags, warm HIT, ordinary 304 revalidation, and malformed-validator 200 instead of the old 500. Cloudflare native assets still return 304 for a failed If-Match combined with a matching If-None-Match, and return full 200 for the tested range. Do not claim complete conditional precedence or static range support. Ordinary browser navigation and Chromium search pass both candidate mounts without failed requests.

### hostname-tls | low | Paid hostname handshake control replaced with scoped request enforcement

Cloudflare rejected per-host minimum TLS with API error 1450 requiring Advanced Certificate Manager. Scoped rules now validate the Cadrumo origin certificate and block documentation requests using obsolete TLS. The public R2 custom domain is configured with minimum TLS 1.2. This does not change the shared zone's handshake minimum or unrelated hosts.

### verification | low | Focused gates pass with one diagnosed integration retry

105 unit tests passed. Of 37 integration tests, 36 passed initially; one registry fingerprint race failed outside changed delivery code and passed on isolated rerun. Ruff, ty, actionlint and zizmor passed. Candidate checks cover both mounts, four language roots, redirects and errors; real browser search fetched direct public R2 payloads and navigated correctly on both mounts. Redirect rules are globally partitioned so exact rules precede dynamic rules, after a rejected candidate exposed Cloudflare's ordering requirement.

### revision-verification | low | Migration identity and displaced source findings resolved

The publisher now requires the static delivery marker on both public roots, including when the release ID is unchanged. A boundary test proves the preceding proxy response cannot satisfy that check. The unused proxy uploader, bindings, module, Node tests and test recipe were removed together. Candidate deployment and browser search remain successful. The final focused deployment lane passes 103 tests; Ruff, ty, actionlint and zizmor pass.

The broader lane-reachability suite has six failures caused by discovery of another contributor's nested `.claude/worktrees/agent-a7e74860a37e5cce6/` checkout. The failure lists name that nested copy, not changed deployment files. Its 39 other lane tests pass. Do not remove or rewrite that checkout as part of this migration. This is an existing workspace completeness limitation, not a passing repository-wide gate.

### production-cutover | low | Verified release now serves through native assets and direct R2

At 05:16:51 UTC on 2026-09-27, production activated static version `16f13780-f0be-43e3-9c5e-91f5d5b0e823` for release `feature-docsbuild-20260924T081959Z`. Both service records report assets present and no executable modules; their reported fetch handlers are platform metadata, not an uploaded module. The old proxy has no public routes. Both release archives and recovery metadata remain private. Full verification compared 69,745 private objects and 61,562 public search objects before sealing.

All 72 directory checks across both mounts match archived bytes and carry the static marker. HTML ETags, warm HITs, HEAD, 304 revalidation, missing-page 404s, and all language health probes pass. Public search responses retain wildcard read CORS, immutable one-year cache metadata, warm HITs, and a tested 32-byte 206 range. The canonical landing remains 200 without the documentation release header; similarly named non-docs paths no longer reach this deployment. GraphQL returned no documentation invocations for the interval starting 05:17 UTC, queried at 05:21 UTC. Evidence: `var/docs-hardening/activation.json`, `deployed-state.json`, `live-http.json`, `analytics-after.json`, and `retention.json`.

### query-routing | medium | Bare-mount query bypass found and corrected

Exact Worker routes do not match a bare mount carrying a query. A scoped zone redirect now normalizes only those two paths and preserves the full query. Normal native deep-link redirects already preserve queries. The publisher's candidate and production checks now exercise the query case and accept equivalent absolute or relative destinations. Fresh public probes return 301 to the correct same-host mount with the original query intact.

### transport-and-prefetch | low | Scoped transport verified and theme prefetch removed from future builds

Live TLS 1.1 requests to docs return 403, TLS 1.2 returns 200, and the unrelated landing still accepts its existing protocols. The public R2 domain rejects TLS 1.1 during the handshake. The original archived HTML explicitly prefetches two theme logos, which Cloudflare route delivery declines with 503. Browser request headers prove these failures are prefetch-only; ordinary logo requests, navigation and real search succeed. A shared Furo base-template override removes those speculative links from future builds; its real Sphinx rendering test passes. The currently preserved archive retains its original bytes until the next normal documentation publication.

### ci-handoff | low | Protected main requires the project pull-request checks

GitHub rejected the authorized direct main push under its PR and required-check rules. The reviewed changes are submitted through PR 693. Source checks and the dependency-free monitoring command pass locally; the workflow explicitly provisions Python through the pinned uv setup action. Scheduled monitoring becomes active only after the PR reaches the default branch. The ongoing required checks are not reported as passing or merged prematurely. No production runtime depends on the ignored `var/docs-hardening/` scratch directory.

### import-inventory | medium | New deployment modules required regenerated load metadata

The first protected-branch CI run failed its import gate. The local reproduction identified stale `dev` load-target metadata after four deployment modules were added. Regenerated `dev/quality/metadata/import_load_targets.json` through `dev.quality.import_load_probe --compile-targets`; the diff adds exactly those four modules. The complete import gate now exits zero: 15 dependency contracts kept, 2,900 governed modules loaded, zero hard findings. Evidence: `var/docs-hardening/import-gate-after.log`. This corrects the integration omission without weakening the gate; the updated commit still requires CI verification.

### recovery-exercise | low | Real version restoration and overlapping publisher exclusion passed

A content-identical temporary native asset version was deployed under the R2 lock, then the publisher's recovery operation restored production version `16f13780-f0be-43e3-9c5e-91f5d5b0e823`. Both public mount checks passed afterwards. A second real lock acquisition while the first owner held the lock returned HTTP 412; the original owner released it correctly. Evidence: `var/docs-hardening/live-recovery.json` and `live-lock.json`. No archived content changed during either exercise.
### workflow-contracts | medium | Availability checks now follow the repository CI contract

The completed first CI run confirmed stale import metadata and four workflow contract failures; its remaining 1,005 scoped tests passed. Corrected the workflow and job names, removed the Python override in favor of `.python-version`, and removed the cron trigger to preserve the accepted `2026-07-21-ci-discipline-adr` zero-schedule decision. Every publication still verifies both mounts; the standalone availability workflow is dispatch-only. The owning 45 CI contract tests pass without test changes. The earlier scheduled-monitor descriptions in this audit describe the initial proposal, not the final deployment cadence. PASS for the correction; the next protected-branch CI run remains required.
## Recommendations

PASS for the reviewed implementation and live migration: no unresolved critical or high implementation findings. Complete the protected-branch CI handoff and dispatch the availability check after merge. The platform conditional behavior, scoped handshake limits, and existing archive's logo-prefetch behavior remain explicitly recorded. No paid subscription or archive deletion was performed.
