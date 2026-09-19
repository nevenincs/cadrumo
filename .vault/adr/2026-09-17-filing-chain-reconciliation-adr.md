---
tags:
  - '#adr'
  - '#filing-chain-reconciliation'
date: '2026-09-17'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:04d068a71afcce1058ec441e35d4abeb57a4c7e9ae791db11e197723c28ce73a'
related:
  - "[[2026-09-17-filing-chain-reconciliation-reference]]"
---

# `filing-chain-reconciliation` adr: `Filing chain with pending local entries and AEAT reconciliation` | (**status:** `accepted`)

Accepted 2026-09-17 under the operator's pre-authorisation of all approval gates for this feature. The operator asked for a self-contained decision, so no earlier ADR is cited.

## Problem Statement

Cadrumo cannot record a correction of a period whose original filing came from AEAT. It also mixes "filed locally" with "accepted by AEAT". A re-pull can stamp AEAT acceptance onto a correction that was never presented, and later periods can carry forward superseded figures without any warning. The six defects are listed in `2026-09-17-filing-chain-reconciliation-reference` (Defects). The law treats a period as a linear chain in which the latest AEAT-accepted declaration is in force (same reference, Legal mechanics). The product needs one general mechanism for that chain, for reconciling it with AEAT, and for traceable manual overrides.

## Considerations

- The filing catalogue already holds a chain with supersession and amendment links. The observation store holds one slot per period (reference, Two stores).
- Each correction references the immediately preceding accepted declaration. Complementaria and rectificativa differ per modelo and date, and the registry policy fact already owns that difference (reference, Legal mechanics).
- A local filing is only an intention until an AEAT register entry proves it was presented.
- Seventeen production readers use the observation store through `load_observation`/`iter_modelo`. Changing their contract is costly.
- Private data must stay in encrypted storage, so a plaintext "recorded pull" file cannot be a product input.

## Considered options

- **A. Keep one observation slot per period and let official win** (status quo). Rejected: local corrections cannot be filed.
- **B. A fully event-sourced chain store** that replaces both the catalogue and the observation store. Rejected: it rewrites every reader and duplicates the catalogue's existing chain.
- **C. Chosen.** Treat the filing catalogue as the chain and give each entry an explicit origin and AEAT confirmation state. Split the observation slot into an official layer and a pending-local layer behind the unchanged reader contract. Route every AEAT entry through one reconciliation service. Record manual overrides as audited pending-local entries.
- **D. Add a plaintext recorded-pull import command** for offline tests. Rejected: it would bring private taxpayer payloads into files. Tests instead replace only the AEAT transport at one named composition factory.

## Constraints

- No legacy compatibility: `replace_official_evidence` and the stored `aeat_accepted` flag are removed rather than aliased. If stored catalogues already exist, a forward, deterministic migration is required, using the existing persistence schema mechanism.
- Correction kinds stay governed by `resolve_amendment_kind_regime_for_period`. This feature does not change registry facts. The survey's doubt about `sustitutiva` for autoliquidaciones stays an open grounding item.
- A local calculation never becomes filing-grade. Pending entries stay visible to the cross-period gate as `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`.

## Implementation

### Chain entry (domain, `ModeloRecord`)

Each entry gains the following fields:
- `origin`: `LOCAL` or `AEAT`;
- `confirmation`: one of
  - `PENDIENTE`: local and not yet seen at AEAT;
  - `CONFIRMADA`: backed by an AEAT register entry and evidence;
  - `DISCREPANTE`: AEAT holds different content, so the entry is superseded by the AEAT entry;
  - `DESCARTADA`: a pending entry replaced before it was presented;
- `declaration_kind`: `ORIGINAL`, `COMPLEMENTARIA`, `SUSTITUTIVA` or `RECTIFICATIVA`;
- `aeat_register`: expediente id, CSV, número de justificante, `tipo_solicitud` and presentation instant.

`aeat_accepted` becomes a property derived from `confirmation`. The invariants are:
- `AEAT` origin implies `CONFIRMADA`;
- `CONFIRMADA` requires `external_evidence`;
- `PENDIENTE` forbids it.

The two-sided amendment-link check ignores `DESCARTADA` entries. The catalogue adds `latest_confirmed_for(...)`; `current_for` stays the in-force entry.

### Local transitions

- **File and re-file** append a `PENDIENTE` `ORIGINAL` entry (or a correction kind, for amendments). A superseded `PENDIENTE` entry becomes `DESCARTADA`; a superseded confirmed entry stays `SUPERSEDIDO`.
- **Amend** accepts any in-force entry.
  - It always amends the latest `CONFIRMADA` entry, so the chain follows the immediately preceding accepted declaration.
  - An in-force `PENDIENTE` entry is marked `DESCARTADA`.
  - With no confirmed entry, amend refuses as today; re-filing corrects an unpresented local filing.
- File and amend both write the pending-local observation layer in the same unit of work as the catalogue.

### Observation layers (adapter, `CalculationObservationRepository`)

- Official source kinds write the official layer. `app_filing` and `operator_manual` write the pending-local layer. The displacement guard and its error go away.
- `load_observation`/`iter_modelo` return the effective envelope for each coordinate: the pending-local layer if present, otherwise the official one. `load_observation_layers` exposes both, and `clear_pending_local` removes the local layer.
- Readers keep their contract, and a pending envelope keeps its non-official `source_kind`, so the existing gates flag it.

### Manual override

`record_operator_local_observation` requires an actor and a reason. It stores an `ObservationOverride` (actor, reason, recorded instant, the replaced envelope's source kind and replaced casilla values) on the pending-local envelope, and emits a bucket event. A clear operation removes the override and emits its own event.

### Reconciliation (application, one service)

`reconcile_aeat_register_entry` takes one normalized `AeatRegisterEntry` for a period: identity, register ref, optional declared kind, optional justificante, optional casilla values and evidence kind. It returns one of five outcomes:
- `ALREADY_RECORDED`: the register ref matches an existing chain entry. Nothing changes.
- `CONFIRMED`: the in-force `PENDIENTE` entry matches.
  - Its kind must be compatible with the declared kind when AEAT states one.
  - Its content must be equal on the casillas AEAT declares; when only a justificante is available, its receipt totals must match the result casilla.
  - The entry becomes `CONFIRMADA` with evidence and register ref. The pending layer is promoted to the official layer.
- `CONTRADICTED`: a pending entry exists but its content differs.
  - The AEAT entry is appended as in force and amends the latest confirmed entry.
  - The pending entry becomes `DISCREPANTE`, the pending layer is cleared, and the differing casillas are reported.
- `APPENDED`: there is no pending entry. The AEAT entry is appended as in force. It amends the previous in-force entry when AEAT declares a correction kind or presents after a confirmed entry.
- `UNVERIFIABLE`: a pending entry exists, but the AEAT entry carries neither casillas nor totals. Nothing is stamped, and a notice is raised.

The live pull (`enroll_filed_justificante_evidence` and the observation persistence) and `import_external_filing_evidence` both call this service. Nothing else stamps AEAT acceptance, and each outcome emits one bucket event.

### Surfaces

- **Pull and import**: `aeat app live filed pull` and `filing-record import` report the per-period outcomes.
- **Filing-record list and view**: show origin, confirmation, kind, amends link, register ref, both observation layers and any override audit.
- **observe-local**: takes a required `--reason` and a `--clear` option, replacing `--replace-official-evidence`.
- **TUI**: the declarations filing history shows the same chain columns and the reconciliation and override events.
- **Test seam**: the composition root builds the Sede port through one named factory, which tests replace with a recorded, in-memory port. The recorded events still flow through the real capture, finalize and reconcile pipeline.

## Rationale

Option C reuses the chain the catalogue already validates. It limits the observation change to one adapter behind an unchanged reader contract. It makes "presented" a fact proven only by AEAT, and it puts every AEAT entry through one decision point. That removes defects 1 to 6 without rewriting the readers or duplicating per-modelo logic, because the correction kinds remain registry-driven.

## Consequences

- Filing a correction after an import works. A re-pull cannot confirm a correction that was never presented, and contradictions stay visible until an operator resolves them.
- Carry-forwards use the pending local value, and the clean-state gate still blocks filing-grade use until AEAT confirms it.
- Manual overrides become non-destructive and auditable.
- The stored filing-catalogue shape changes, which needs a forward migration if stored data exists.
- A justificante-only confirmation relies on receipt totals rather than per-casilla equality. That is weaker evidence, so it is reported as such in the outcome.
- Remaining work: the solicitud de rectificación workflow for liability decreases in pre-rectificativa modelos, and the registry grounding of `sustitutiva` per modelo.
