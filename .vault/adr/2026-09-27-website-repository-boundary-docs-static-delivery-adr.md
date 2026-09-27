---
tags:
  - "#adr"
  - "#website-repository-boundary"
date: '2026-09-27'
related:
  - "[[2026-09-23-website-repository-boundary-docs-cloudflare-delivery-adr]]"
supersedes:
  - '2026-09-23-website-repository-boundary-docs-cloudflare-delivery-adr'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:85ca5c8a30827b9854a30513cc00571e229041e493e94575aec8b8a5baaf99e6'
---
# `website-repository-boundary` adr: `static documentation with versioned search objects` | (**status:** `accepted`)

## Problem Statement

Remove documentation delivery from the shared executable Worker allowance and make publication recoverable. Evidence: the account and deployment audits in `Y:/code/portfolio2026-worktrees/main/.vault/audit/2026-09-27-workers-audit-cadrumo-audit.md` and `2026-09-26-workers-audit-audit.md`.

## Considerations

Preserve the two documentation mounts, language roots, search, errors, existing links, private release archives, and the independently owned CloudFront landing page. Reuse the existing Python publishing toolchain.

## Considered options

- Static pages and small search runtime with versioned R2 search fragments: selected; fits the existing static asset allowance without a subscription change.
- A paid Workers subscription: retains unnecessary execution or changes recurring billing; not selected.
- Multiple static services partitioned by language: complicates release consistency and retention; not selected.
- A direct public binding of the private release archive: would expose unverified releases; rejected.

## Constraints

Keep build validation mandatory and credentials isolated to documentation resources. No AWS changes, unrelated service migrations, paid plan changes, or automatic deletion of existing releases. Static asset and redirect limits must be checked before activation.

## Implementation

Publish HTML, styles, scripts, search metadata, and directory aliases through an assets-only service on both mounts. Redirect only Pagefind index and fragment trees to a dedicated public R2 bucket under immutable release paths. Keep the search module on the original origin so result URLs remain local. Verify complete archive and public manifests before activation, serialize publishers with an atomic storage lock, and restore the previous deployment if activation verification fails. Native delivery replaces the proxy's HTTP conditional handling. Harden scoped transport, cache headers, routes, and monitoring, and serialize CI with a working least-privilege alert path.

## Rationale

This removes request-time execution while retaining the public contract and avoiding the static asset count constraint established by the audit. The existing private bucket remains the release and recovery authority; publication exposes only verified search payloads.

## Consequences

Search fragment requests gain a redirect and require anonymous read CORS on the public bucket. Both mounts fit one static manifest, allowing one activation to switch both. Completed releases retain checksums and recovery metadata. Retention reports protect active and rollback releases; deletion is a separately explicit operation.

Accepted 2026-09-27: the user instructed "Action and fix the findings" after the full Cadrumo deployment audit. This authorizes the scoped code and live delivery corrections. It does not authorize a paid subscription change or an unrelated migration.
