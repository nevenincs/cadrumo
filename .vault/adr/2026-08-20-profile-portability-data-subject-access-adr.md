---
tags:
  - '#adr'
  - '#profile-portability'
date: '2026-08-20'
modified: '2026-08-20'
body_schema: 'body-v1'
body_hash: 'sha256:5a545936ca7cf9aafb322253f7fe13e36e318409b553da0ac645f7351c332ec1'
related:
  - "[[2026-08-13-profile-portability-successor-adr]]"
  - '[[2026-08-20-profile-portability-bundle-surface-inventory-audit]]'
---
# `profile-portability` adr: `data subject access` | (**status:** `accepted`)

## Problem Statement

The `config profile subject-access-request` verb was deleted as collateral of the
profile-capsule cutover, not by a decision. Its schema declaration, locale strings and
result model outlived it. The declaration entry that recorded the absence asserted an
unmet legal obligation, and the shipped locale strings advertised a "GDPR
right-of-access archive" for a verb the tree no longer exposes. A decision is needed now
because those two surfaces make a compliance claim the repository cannot ground, and
because the absence is otherwise recorded nowhere.

## Considerations

- The bundled corpus under `src/cadrumo/_data/corpus/normatives/html/` carries BOE tax
  norms only. No RGPD and no LO 3/2018 text is bundled, so no data-protection claim in
  this repository can be grounded against a re-fetchable authority.
- The withdrawn verb exported the operator's own profile to the operator's own disk. It
  answered no access request made by another party.
- The withdrawn verb hardcoded cleartext transport with no override.
- A profile bundle carries third-party personal data: counterparty identities, and a
  descendant disability grade in `src/cadrumo/domain/contribuyente/_descendant_facts.py`.
- The one capability with no successor is the data-category disclosure: the verb reported
  which categories the bundle carried and which stayed in encrypted storage. The profile
  manager's export discards that record.
- `2026-08-13-profile-portability-successor-adr` is accepted and keeps a separate
  structured export/import. Neither half exists on the live CLI.

## Considered options

- **Restore the verb as removed.** Rejected. It wrote cleartext to operator disk, so
  restoring it verbatim would write third-party special-category data as plaintext,
  against the secure-storage-only mandate. Under a data-protection name it would also
  publish a compliance signal for behaviour that is a self-directed local export.
- **Build a per-subject disclosure surface now.** Rejected for now. No grounded
  requirement establishes its shape, and authoring one from ungrounded legal reasoning is
  the failure this project forbids for regulated behaviour.
- **Delete the declaration entry.** Rejected. It is the only place the absence is stated.
- **Defer, and correct the claims.** Chosen.

## Constraints

No data-protection corpus is bundled, so the scope question that would size any future
surface is unresolved here: whether a private taxpayer's processing of a descendant's
disability grade engages the regulation at all, and how that differs for a gestor. This
record does not settle it and must not be read as settling it.

## Implementation

The capability stays unbuilt. Three corrections carry the decision. The declaration entry
in `src/cadrumo/entrypoints/cli/_verb_input_schema.py` states the missing capability - the
data-category disclosure - instead of asserting a legal duty, and its gate docstring says
the same. The orphaned `sar_help` and `sar_catalogue_info` strings, which advertised a
right-of-access archive in all four catalogues, are removed. The reference documentation
states that no command writes a portable bundle, that the profile manager still can, that
nothing reads one back, and that this is a portability gap rather than a recovery one.

Restoring `export` and `import` is separate work owned by the successor record above, not
by this one.

## Rationale

Deferring is chosen because the alternative that looks responsible is the one that does
harm. A restored verb under a data-protection name would read as a discharged duty while
exporting the operator's own data to their own disk, and would reintroduce a cleartext
path that was deliberately pinned shut. An unbuilt capability with its absence stated is
recoverable; a false compliance signal is harder to find later than an open gap.

The decision was reached by a dispatched ruling reviewed by an independent adversarial
verifier, on the operator's instruction, after the operator declined to rule personally.
The verifier refuted parts of the original ruling, including its claim that the
declaration text was factually wrong; the surviving finding is narrower and is what this
record carries.

## Consequences

Accepted cost: a profile bundle holds third-party personal data, including a descendant
disability grade, and the product offers no per-subject disclosure, correction or erasure
surface for it. Nothing in the tree reports which personal-data categories a bundle
carries.

Unchanged by this record, and worse: the profile manager writes bundles nothing in the
product reads back, and the accepted successor record's export/import verbs are still
absent from the CLI. Both are the portability gap, not this one.

Revisit when any of these becomes true: the product serves more than one taxpayer or any
gestor or multi-client use; profile data is processed off-host or over a network; any
user-facing or marketing text claims a rights response, portability or a data-protection
capability; or a third-party subject category is added whose data is not derivable from
the taxpayer's own filing obligation.
