---
tags:
  - '#audit'
  - '#google-oauth'
date: '2026-07-14'
modified: '2026-07-17'
body_hash: 'sha256:0cdfaebdb4fb82c28f1468b4e282035e4e13eb04178696b0b608af7dc2ed3d07'
related:
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-07-12-google-oauth-audit]]"
---

# `google-oauth` audit: `master plan reconciliation`

## Scope

Reconcile the May Google OAuth master plan against the accepted July architecture,
the live CLI, and the implementation. The audit distinguishes authentication from
the much larger storage, ingestion, recovery, correction, and calculation-Sheets
campaign that accumulated under the same feature name.

Evidence was grounded with Vaultspec RAG and then verified against exact source and
test symbols. The reconciliation is documentary: it does not claim that absent
features were implemented.

## Findings

### master-plan-reconciliation | high | authentication is delivered

P01 is implemented, including OAuth client registration, loopback login, secure
per-profile token persistence, refresh and revocation handling, status, logout, typed
errors, and import-contract coverage. P02 is also implemented: the provider protocol,
local and Google Drive providers, provider factory, enumeration, probing, and root
folder handling are present. The 49 targeted authentication and storage tests passed.
The original impression that Google authentication already exists is correct.

### master-plan-reconciliation | high | P03 is superseded rather than pending

The accepted July ADR explicitly supersedes the May local SQL sync-state and
`DriveSync` design. The live implementation uses remote ciphertext namespace manifests
and supports `google sync push`; it deliberately does not retain the proposed local
sync-state table, label-deriver registry, general pull/status/orphans/claim matrix, or
underscore workspace hierarchy. Consequently P03.S01-P03.S20 are no longer an
implementation backlog. P03.S08 is delivered in the replacement architecture; the
remaining P03 rows are retired or require a new ADR if their user outcome is desired.

### master-plan-reconciliation | high | P08 conflicts with the canonical command surface

The planned `ledger transaction edit` and CSV `corrections` namespaces are not the
canonical operator surface. Current ledger decisions and code use `ledger update` and
lineage-preserving lifecycle commands, but the May two-way ADR required an EPIC sign-off
that has no matching record. P08.S01-P08.S13 and P08.S15 are therefore an unresolved
ADR-versus-code contradiction, not delivered work and not missing authentication.
P08.S14 alone is superseded: its prohibition on a Sheets pull command was overturned by
the later bidirectional calculation-Sheets decision and the current CLI has that pull.

### master-plan-reconciliation | medium | P04 and P05 remain genuine unresolved scope

P04's Google-specific escrow, Drive restore, and cross-machine bootstrap are absent.
The product does have a generic sealed full-custody export/import archive, but that is
not evidence for the planned Google escrow commands. The July ADR also states that
escrow and cross-machine recovery remain unimplemented. P05's Drive inbound drop-zone,
deduplication pipeline, acknowledgement/rejection flow, and inbound CLI are likewise
absent. These phases remain open until explicitly superseded or moved to successor
campaigns.

### master-plan-reconciliation | medium | calculation Sheets exists but differs from the May contract

The current code contains the calculation-Sheets record model, layout, translator,
engine, styling, workbook export, Google apply/pull adapters, parity harness, and the
`calc export`, `verify`, `pull`, and `compute` commands. It does not match every P07/P09
row: the planned `Resultado`, list/delete commands, three-tier parity stack,
`ParityManifest`, `headRevisionId` gate, and local-state-mutating pull contract are not
present. P07/P09 therefore need a decision reconciliation before their individual rows
can be closed honestly; their open checkboxes do not mean Google authentication is
missing.

### master-plan-reconciliation | medium | P06 mixes retired dependencies with independent backlog

The planned label-deriver and reverse-merge families derive from the superseded P03
design and the contradictory P08 design. `SecureObjectRepository.iter_all_records_raw`
and its namespace-listing equivalent are implemented, closing P06.S01-P06.S02. The
planned P06.S28 `SourceKind` duplicate is retired in favour of the canonical
`BindingSourceKind` taxonomy. The six correction event enum values exist, but the
emitter wiring required by that row does not. P06.S14-P06.S25 are retired by the July
ADR's rejection of the decrypting label-registry/allow-list model; most other rows are
absent or belong to non-Google domain campaigns. P06 should be split during successor
planning rather than executed wholesale as an OAuth phase.

### master-plan-reconciliation | high | legacy checkbox compatibility required a guarded path

Dry-running `vault plan step check` for P03.S01 with Vaultspec Core 0.1.36 and 0.1.26
does not produce a one-row checkbox change. The serializer would remove most standard
step rows, retain only letter-suffixed exceptions in place, and relocate the authored
plan body. The destructive serializer path was not applied. A guarded local CLI
compatibility path was used instead: it is available only to check, uncheck, and toggle
commands on a legacy plan whose declared tier has rows but no parsed containers. It
replaces checkbox state in the uniquely matched raw row and preserves every other byte
apart from the CLI-managed modified stamp. Dry runs proved one-row diffs before 39
reconciliation records were created and their rows checked. Structural mutation of the
legacy shape remains prohibited pending a canonical migration or upstream fix.

### master-plan-reconciliation | high | retirement closes documentary residue, not production work

The final raw-row inventory remains 183 rows: 76 checked and 107 open. The
archive-aware canonical parser reports 177 Steps, with 74 complete and 103 open
(41.8 percent); the difference remains the six non-canonical suffixed rows, two
of which are checked. The definitive disposition ledger accounts for every raw
row: 67 `shipped-equivalent`, 83 `retired-obsolete`, 24
`moved-domain-not-approved`, 9 `new-ADR-only`, and 0
`genuine-current-gap`. These counts establish that the legacy plan is not an
implementation backlog.

The legacy Google retirement archived exactly one document,
`2026-05-13-google-oauth-plan`, after classifying all 63 incoming references as
preserved provenance: 63 preserve, 0 rewrite, and 0 active-authority block. The
active source is absent, the archive destination exists, and the archived file
still contains the same 183-row, 76-checked, 107-open inventory.

The ledger-Google retirement archived exactly four historical documents: its
superseded ADR, reconciled plan, research, and feature index. Their active
locations are absent, all four archive destinations exist, and the four
incoming references remain provenance: 4 preserve, 0 rewrite, and 0 block. The
accepted optional-adapter ADR is the successor authority; the checked legacy
ledger-Google plan is historical evidence, not proof of a shipped live ledger
round trip.

This reconciliation and retirement sequence changes Vault documentation and
lifecycle state only. It does not implement Google escrow or restore, watched
inbound ingestion, reverse merge, a Google-owned taxonomy, persistent Sheets
pull, or any other production capability. The honest implementation outcome is
zero new production code and zero genuine current Google gap authorized by the
retired plans.

## Recommendations

1. Treat P01 and P02 as the completed Google authentication and provider foundation;
   do not schedule another OAuth implementation campaign.
2. Treat P03.S01-P03.S20, P06.S14-P06.S25, P07.S01, and P08.S14 as retired scope under
   this audit. Do not implement those exact rows without a new accepted ADR.
3. Upstream the guarded legacy state-mutation behavior or migrate the plan structure
   before any structural add/edit/move operation. Continue requiring a dry-run diff
   containing only the requested checkbox and CLI-maintained metadata change.
4. Create narrowly scoped successor decisions for any desired P04/P05 recovery or
   inbound outcomes, adjudicate the P08 command-surface conflict, and reconcile the
   P07/P09 calculation-Sheets differences. Do not carry them as an undifferentiated
   “Google OAuth” remainder.
5. Split P06: retire dependencies that exist only for P03/P08, preserve independently
   valuable domain work under its owning campaign, and attach exact execution records
   before checking any delivered rows.

## Verification

- The plan contains 183 rows before and after reconciliation. Exactly the 39 approved
  rows changed state; no row action or scope changed, and no row was added or removed.
- The archived raw plan remains 76 of 183 rows checked. Canonical parser status
  reports 74 of 177 parsed Steps complete, or 41.8 percent, and retains the
  known legacy execution-record diagnostics rather than hiding them.
- The Google OAuth feature index was rebuilt and contains the reconciliation audit and
  all 39 execution records.
- Feature-scoped Markdown, frontmatter, placeholder, body-link, annotation,
  modified-stamp, link, and feature-index checks pass. The global structure check also
  passes after the two alpha-suffixed execution records were normalised by the Vault
  structure fixer.
- The targeted OAuth and storage-provider suite passes 105 tests. Live Google tests
  remain credential-gated and were not used as closure evidence.
- The plan-specific convention checker still reports the pre-existing legacy grammar:
  old heading depths, duplicate phase-local leaf identifiers, alpha-suffixed rows, and
  historical row-scope forms. Those findings require a separate structural migration;
  they do not contradict the preserved row set or the checked reconciliation state.
- Archive-state verification finds the one legacy Google destination and all four
  ledger-Google destinations present, with their five active source paths absent.
- Production-path diffs are inherited concurrent work. Their unstaged and staged
  hashes remained `40fb4a0434b99c935499c7582201caeb5eae2c40` and
  `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`, with no untracked production paths,
  across this documentation Step.
