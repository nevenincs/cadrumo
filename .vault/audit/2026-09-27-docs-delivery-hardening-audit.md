---
tags:
  - '#audit'
  - '#docs-delivery-hardening'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:d0cd035fceb642df189073dc72416cd9f85a5191885400f512afedb04c6b0b0a'
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

## Recommendations

PASS for S01 and S02 after revision: no unresolved critical or high implementation findings. S03 still requires production activation and verification. The platform conditional behavior and hostname handshake limits remain explicitly recorded. No paid subscription or archive deletion is authorized by this plan.
