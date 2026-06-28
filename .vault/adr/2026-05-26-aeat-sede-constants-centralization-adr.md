---
tags:
  - '#adr'
  - '#aeat-sede-constants-centralization'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-research]]'
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-06-04-aeat-sede-constants-centralization-research]]'
---



# `aeat-sede-constants-centralization` adr: `AEAT and Sede constants are schema-owned architecture data` | (**status:** `accepted`)

## Problem Statement

AEAT/Sede hosts, paths, selector markers, Cl@ve routes, wallet routes, live
action labels, and timeouts are architectural inputs. When they are embedded as
ad hoc literals in executable code or tests, live drivers become difficult to
audit and can regress without touching a central schema.

The live IVA work exposed this concretely: authentication and wallet behavior
cannot be made reliable while URLs, route fragments, and action labels are
distributed across code, tests, and comments.

## Considerations

The settings dependency-injection work already distinguishes runtime-tunable
settings from external constants. Timeouts, operator preferences, and storage
routes belong in `Settings`. AEAT-owned hosts, service paths, selector markers,
and externally defined route fragments belong in the external constants
registry or registry TOML/YAML.

The no-synthetic Sede ADR makes live-surface classification legally sensitive.
That classification depends on host ownership and operation class, so host and
action constants must be centrally auditable.

Official corpus manifests and archived source evidence legitimately retain
source URLs as evidence metadata. That is different from executable
source-of-truth constants.

## Constraints

Executable AEAT/Sede source-of-truth constants must live in `Settings`,
`external_constants.toml`, registry TOML/YAML, or typed schema models.

Tests may assert configured values and may carry evidence URLs inside fixtures,
but tests must not introduce a competing source of truth for hosts, Sede routes,
Cl@ve paths, wallet paths, action labels, or development database passwords.

Runtime-tunable values must remain in `Settings`; externally defined values
must remain in the external constants registry or registry data.

Static guards must allow docstrings, comments, official corpus evidence, and
negative examples when they are not used as executable constants.

## Implementation

Extend the external constants registry to cover all AEAT-family hosts used by
portal and live-driver code. Portal host resolution must use that registry
instead of fallback enum host literals.

Move status-reader and live-driver path defaults out of inline `Settings`
defaults and into external constants. `Settings` fields may remain overrideable,
but their defaults must be loaded from the registry.

Register the shared development/test database password in core settings and the
environment example file. Database-backed tests must use the settings field or
the secure SQL helper.

Add static guard tests for executable live Sede surfaces. The first guard
targets high-risk live auth, Sede, verify, and settings modules. Broader portal
and registry metadata guards can expand after the existing portal catalogue is
classified.

## Rationale

Centralization makes live behavior reviewable. A reviewer can inspect one
registry and one settings model to understand the external routes and runtime
tunables a live driver uses.

It also improves legal safety. The no-synthetic rule is host-sensitive, and
host-sensitive behavior is fragile if hosts are scattered as strings.

Keeping evidence URLs in corpus metadata preserves source traceability without
turning every historical source URL into a runtime constant.

## Consequences

Some tests must change from literal comparisons to configured-value
comparisons.

Adding guards will initially surface many existing literals. Each must be
classified as executable source of truth, official evidence metadata, test
negative example, or harmless documentation.

Portal registry centralization may require additional host fields and typed
schema coverage before all fallback literals disappear.
