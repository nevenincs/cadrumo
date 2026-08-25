---
tags:
  - '#adr'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:7720175125a5b2e11a789a08e4b88e6ae7a0956e16eefadfd434b1babdd3e439'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-research]]"
  - "[[2026-08-09-cli-action-envelope-hardening-reference]]"
---

# `cli-action-envelope-hardening` adr: `Application-owned precondition verdicts and schema-resolved action chains` | (**status:** `accepted`)

## Problem Statement

Operator guidance cannot remain free-form text detached from the guard or state
transition that selected it. The system needs one contract that identifies why
an action is unavailable, which recovery action follows, and whether its inputs
are executable. The scope and blast radius are grounded in
`2026-08-09-cli-action-envelope-hardening-research` and
`2026-08-09-cli-action-envelope-hardening-reference`.

## Considerations

- Application and domain gates already own applicability and must remain the
  policy authority.
- The live Click projection already owns executable leaf and input shape.
- Envelopes, CLI, MCP, TUI, locales, and help are presentation consumers.
- Full blast-radius claims require fixed-point semantic discovery and
  mechanically reconciled inventories, per the related reference.

## Considered options

- **Manifest-owned transitions:** rejected because it would duplicate dynamic
  application predicates.
- **Application-owned verdicts only:** retained but insufficient without a
  canonical resolver for target commands and bindings.
- **Central action catalogue only:** rejected because it could become a second
  workflow authority.
- **Application verdicts referencing a validated action catalogue:** accepted.
  Applicability stays with the gate; executable projection stays with the live
  command schema.
- **Static Click/schema inference:** retained as validation infrastructure, not
  as a source of semantic preconditions.

## Constraints

- Typed verdicts carry stable condition identity, evidence, action identity,
  bindings, missing bindings, and conditionality; they do not carry localized
  command prose.
- Action projection must resolve against the live leaf and input schema.
- Permanent and safety refusals explicitly declare no recovery action.
- The census runs to a fixed point and maintains separate candidate,
  adjudicated, and live-coverage sets. Exact total-count gates are forbidden.
- Every live leaf is classified, and every reachable failed precondition is a
  `(leaf, condition, scenario)` row with negative and recover-then-retry proof.
- Reconciled identities, not equal counts, prove completeness: live callable
  leaves, registered result schemas, manifest leaf capabilities, action profiles,
  and policy-filtered MCP leaves must join exactly, with typed rows for aliases,
  callbacks, exclusions, and intentionally unexposed surfaces.
- Every observed actionable outcome joins to one declaration and every declared
  outcome joins to a real observation. Unmatched rows on either side fail.
- The accepted profile-diagnostics decision remains the upstream authority for
  profile requirement labels and grounding; this decision does not duplicate it.
- `ErrorCode` registry rows carry taxonomy and locale-key metadata only; no
  action identity or no-recovery outcome belongs on a registry row.
- The immutable retired-default preimage is discovery evidence, not runtime
  policy.
- Every historical non-null default must join its exact immutable key and a
  fail-closed structural producer or reference fingerprint:
  `(path, lexical_owner, role, recovery-ast-v1 normalized AST SHA-256,
  identical_site_ordinal)`. Canonical `recovery-ast-v1` JSON contains every
  semantic field and their ordering, and excludes coordinates only. The
  locator `(line, column, end_line, end_column)` is diagnostic metadata only:
  it never identifies a gate match or owner. The resolver accepts explicit
  import aliases and re-exports, including only statically enumerable PEP-562
  export maps; it rejects ambiguity and nested-scope leakage, and it records
  every resolved call context. Each current structural fingerprint has exactly
  one current owner Step, keyed by that structural identity. Acceptance compares
  the derived exact key and structural-fingerprint multisets, never an
  aggregate count alone. Line identity is explicitly rejected in the shared
  campaign because independent worktree edits can shift coordinates without
  changing a producer's semantics; using it as identity would manufacture false
  missing or duplicate evidence.
- The current observed-key set, constructor/reference partition, scanner-absent
  set, and physical fingerprint multiset are derived afresh from the current
  source tree at validation time. Every observed key begins as evidence-only
  `migration_required` with exactly one open, scope-valid owner; it is not a
  final recovery outcome. A scanner-absent key is only eligible for
  `retired_or_unreachable` after absence is proven. Snapshot discovery totals
  are evidence only and never architecture.
- The final kinds are `verified_typed_action`,
  `verified_terminal_no_recovery`, `verified_nonproducer_reference`, and
  `retired_or_unreachable`. Reference-only keys begin as `migration_required`
  and can become `verified_nonproducer_reference` only
  after proof that no emitting, dynamic, or re-export route remains.
- `retired_or_unreachable` is allowed only for a source-proven scanner-absent
  key; a historical `None` does not itself establish a terminal outcome.
  Rehoming evidence carries no action, condition, command, or localized-text
  authority; user-facing rendering uses locale keys plus typed facts only.
## Implementation

Introduce strict application-owned precondition and action-reference models plus
a central action catalogue. Join catalogue entries to live Click-derived input
schemas and registered result schemas in the operator manifest. Project the
resolved record through success notices and error envelopes, preserving localized
human rendering as a derived view. Migrate producer-to-projection slices by behavioral cluster, beginning with root
storage/profile guards, then workflow and modelo, diagnostics/overview/provisioning,
and remaining adjudicated clusters. Rehome every retired non-null default at its
current producer or guard before changing any registry-shard ownership. The
rehoming join records only immutable provenance, structural identity, diagnostic
locator, current owner Step, and disposition; it is policy- and locale-neutral
and carries no action, command, condition, prose, or locale policy. Runtime
policy remains in the producer verdict and its catalogue/live-schema projection.

Add an AST-backed census and a live coverage join. New unclassified action sites,
unresolved action identities, insufficient bindings, undeclared preconditions,
and missing real dispatch/recovery/retry proofs fail the campaign gates.
Repeat the semantic-plus-mechanical census after every migration wave until a
complete pass produces no new action source, consumer, renderer, emitted command,
or rejection site; any new alias restarts the fixed-point pass.

## Rationale

Only the combined model proves genuine linkage without moving business policy
into the manifest or CLI. It also makes completeness measurable against the live
surface rather than a handwritten scenario list. The knockout evidence and
inventory method are recorded in the related research and reference.

## Consequences

Operators and agents receive machine-resolvable failure conditions and executable
recovery chains derived from the same authority that refused the action. CLI and
MCP share one semantic contract. The migration is broad and cannot be represented
as one envelope edit; each cluster requires real negative and positive proof.
Temporary coexistence of migrated typed records and adjudicated legacy sites is
allowed only while the census makes the remainder explicit and shrinking.
