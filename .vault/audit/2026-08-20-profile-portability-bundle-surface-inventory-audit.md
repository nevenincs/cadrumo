---
tags:
  - '#audit'
  - '#profile-portability'
date: '2026-08-20'
modified: '2026-08-20'
body_schema: 'body-v1'
body_hash: 'sha256:5ec17de64a4f09e86d4ac143c779666d0db4f40bb9a5e536df98a7f25de2bb8a'
related: []
---

# `profile-portability` audit: `bundle surface inventory`

## Scope

What survived the profile-capsule cutover of the portable-bundle surface, and what did
not. Established by a dispatched investigation and re-checked by an independent
adversarial reviewer against the live tree; every claim below was read at source, and the
reviewer refuted several claims the first pass made.

## Findings

### The export half is live and reachable; the import half is not

`src/cadrumo/entrypoints/cli/_config/_manager_actions.py` registers an export action that
calls the live bundle export service with portable-transfer purpose and
passphrase-encrypted transport. It is reachable from a bare interactive
`aeat config profile edit`. On the read side, `decrypt_profile_bundle_with_passphrase`
and `register_imported_profile_bundle` have no production caller anywhere; the only
callers are the facade re-export and tests.

An operator can therefore write an encrypted bundle of their whole financial history that
no shipped surface reads back. This is a portability gap, not a recovery gap: backup and
recovery run through the sealed capsule archive and restore verbs and are unaffected.

The gap is already recorded in prose in the tree, in the exported-contract test and in
the manager-actions module docstring. It was shipped knowingly.

### The tree contradicts an accepted decision

`2026-08-13-profile-portability-successor-adr` is accepted and keeps a separate structured
export and import. Neither verb exists on the live CLI. An accepted decision ruling on
code is not self-executing; this wants implementing rows, not further analysis.

### Orphaned surfaces left by the cutover

Three result schemas remain registered with no producing verb: the export, import and
subject-access results in `src/cadrumo/entrypoints/cli/_config_payloads.py`. The
`SUBJECT_ACCESS` member of the export-purpose enum has zero references tree-wide - a dead
branch of a closed taxonomy. The census disposition data in `dev/quality` carries roughly
two dozen rows whose path is a module the cutover deleted, each quoting a locator that no
longer resolves.

### Test coverage deleted with the verbs

The cutover removed roughly 2,300 lines of bundle export, import and recovery tests. The
durable three-phase publication service survives at around 670 lines. One CLI maintenance
test still drives the export for real and covers the crash-orphan journal path, so the
service is thinly gated rather than ungated - but the crash-window assertions that the
earlier fix bought are gone.

### Shipped text claimed a capability that did not exist

All four locale catalogues carried an operator-facing string advertising a
right-of-access archive, and a second describing its category disclosure, for a verb the
tree no longer exposes. Both keys had zero code references. They are removed.

## Remediation

Done: the declaration entry and its gate docstring now state the missing capability - the
data-category disclosure - rather than asserting a legal duty the repository cannot
ground; the two orphaned locale strings are removed from all four catalogues; the
reference documentation states that the manager can still write a bundle, that nothing
reads one back, and that recovery is unaffected.

Deferred by decision, recorded in `2026-08-20-profile-portability-data-subject-access-adr`:
the subject-access capability stays unbuilt.

Open, and owned elsewhere: restoring the export and import verbs under the accepted
successor record; the three orphaned schemas and the dead enum member; the stale
disposition rows; and rebuilding the deleted export-service coverage, which is owed
whether or not any verb returns, because the service is live through the profile manager
today.

## Note on method

The first pass claimed a single file was deleted by the cutover; the reviewer found
roughly ninety-seven, including ten production modules. It also claimed the declaration
text was factually wrong; the reviewer showed the text is true of the category disclosure
and only its legal framing is overstated. Both corrections are carried above. Dispatched
findings are inventory to confirm, not conclusions to adopt.
