---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7723cc2d113b6efb9f3bd8f679dba7eecd2126c42de263fcfcd63547061635c9'
related: []
---

# `source-casilla-integration` audit: `s144 descriptor safe evidence review`

## Scope

Review descriptor-safe repository evidence verification for replacement races, root escape, malformed locators, platform guarantees, and same-handle hashing.

## Findings

### s144-descriptor-safe-evidence-review | medium | malformed repository references were normalized before validation

Drive-qualified paths, alternate-data-stream syntax, repeated separators, and dot segments could reach filesystem handling instead of being rejected lexically.

### s144-descriptor-safe-evidence-review | low | changed files required canonical formatting

The initial implementation did not satisfy the focused Ruff format check.

### s144-descriptor-safe-evidence-review | info | descriptor verification is bound to the bytes hashed

The verifier opens once, obtains the final operating-system path from that handle, compares the exact requested path, checks root containment and regular-file mode, and hashes through the same descriptor. Unsupported handle-path platforms fail closed.

## Recommendations

- Reject every non-canonical repository reference before opening; covered by malformed-path cases.
- Format and lint the exact changed source surface; completed.
- Retain deterministic controlled descriptor substitution plus real leaf and intermediate link escapes as adversarial regression coverage.
