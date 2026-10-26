---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:fd1043377d4418efea189d2131f4d3e69a5fc11b995400459739211774101350'
related:
  - "[[2026-09-23-tuimodelo-export-paths-reference]]"
  - "[[2026-09-07-tuimodelo-export-destinations-adr]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
  - '[[2026-08-24-tui-operation-observation-adr]]'
---

# `tuimodelo` adr: `one export path for every surface` | (**status:** `proposed`)

## Problem Statement

A fichero-BOE export reaches the application layer by three entrypoint routes,
and only one of them is supervised (`2026-09-23-tuimodelo-export-paths-reference`).
The command line carries its own export path, and the review-package verb runs a
business flow inside its command handler. Both break the rule that an entrypoint
parses and delegates but never carries a second business implementation. Two
surfaces that reach the export differently can diverge silently. The dropped
elections defect was exactly that divergence, and the operation failed where the
command line refused. Unifying the routes changes a public result contract, so the
choice cannot be made inside an implementation step.

## Considerations

- The accepted export-destinations decision requires that an export whose
  completeness could not be verified says so on the artefact and in the result,
  and that the export surface stays a thin renderer over a real contract
  (`2026-09-07-tuimodelo-export-destinations-adr`).
- The command-line envelope reports facts the operation result lacks: event id,
  resolved disposition, address coordinates, evidence status and completeness
  advisory (`2026-09-23-tuimodelo-export-paths-reference`).
- Seventeen generated docs sequences depend on the command-line export output
  (`2026-09-23-tuimodelo-export-paths-reference`).
- The resolved disposition and the elections are persisted provenance of an export
  under the carry-reconciliation amendments, so they are facts of the export
  itself, not presentation (`2026-06-21-m303-carry-reconciliation-adr`).
- The review-package flow consumes the command-line wrapper, so the wrapper cannot
  be removed alone (`2026-09-23-tuimodelo-export-paths-reference`).

## Considered options

- **Widen the public operation result** to carry every fact the command-line
  envelope reports, and have the command line render that result. The CLI output
  stays stable and the TUI gains the evidence and completeness facts the accepted
  destinations decision already requires. The cost is a new result schema
  version. Kept.
- **Shrink the command-line output** to the current operation result. This is
  cheaper in the application layer, but it breaks the command-line contract and
  seventeen docs goldens, and it removes the completeness advisory the
  destinations decision requires. Rejected.
- **Keep two routes and prove them equal by test.** This is today's boundary. The
  parity test catches choice divergence but not a second implementation drifting
  in its gates. Rejected as the end state and retained as the interim guard.

## Constraints

- The operation supervisor's result projection is the only channel a supervised
  surface may read (`2026-08-24-tui-operation-observation-adr`).
- No compatibility shim may keep the displaced wrapper alive, and consumers move
  atomically with the definition they use.
- Byte-level export correctness remains unproven by fixture, so this decision
  moves routes and contracts, not rendering
  (`2026-09-07-tuimodelo-export-destinations-adr`).

## Implementation

`ModeloExportPublicResultV1` gains a successor result version. It carries the
export's address coordinates, event id, resolved disposition, the elections as
applied, the evidence status and the completeness verdict, as typed fields with
no artefact bytes. The command-line export verb submits the `modelo.export`
operation, observes it to its terminal state, and renders the command envelope
and its notices from the projected result. The direct wrapper
`export_modelo_revision_for_cli` is deleted in the same change. The review-package
build becomes an application service that exports through the same service the
operation calls, builds the package, and returns a typed result. The
review-package verb delegates to that service, as a supervised operation if the
package write needs journalling. The docs sequence goldens are regenerated
through their generator, never edited, and any intentional output difference is
reviewed in the regenerated diff.

## Rationale

The destinations decision already requires completeness in the result. So the
widened result is not new scope. It is the contract the TUI export surface is
owed, and the command line then renders the same facts the TUI shows. Shrinking
the command line would satisfy "one path" by deleting facts the product is
required to state. Keeping two routes leaves the class of defect open that
produced the dropped elections.

## Consequences

- The TUI can show the evidence status and the completeness advisory after an
  export, instead of only a digest.
- Command-line exports become journalled operations, so an interrupted export is
  reconciled like every other mutation.
- The command-line export gains the operation's submission overhead.
- Seventeen docs goldens regenerate, and any output difference beyond ordering
  must be justified in review.
- Review-package building gains an application home, and its parity with export
  is then structural rather than tested.
