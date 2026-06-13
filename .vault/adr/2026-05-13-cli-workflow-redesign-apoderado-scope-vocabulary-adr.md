---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Apoderado configure --scope vocabulary` | (**status:** `accepted`)

## Problem Statement

`aeat config auth apoderado configure --represented-nif NIF --scope
SCOPE` is the verb for configuring representative-of (apoderado)
authentication. The apoderamientos-surface ADR declares the verb
but does not define the SCOPE vocabulary: whether SCOPE is a single
modelo code, a comma-separated list, a repeated flag, or a named
AEAT delegation category. Without a defined vocabulary, every
implementation diverges and gestoras cannot reason about whether
their apoderamiento covers a given filing.

## Considerations

- AEAT publishes a fixed catalogue of delegation categories (`apud-acta`
  scopes) identified by short codes (e.g. `GENEQ` for general
  representation, `TRIBT` for tax procedures, `IVAQT` for IVA-quarterly,
  `IRPFQ` for IRPF-quarterly, `IRPFA` for IRPF-annual, plus
  modelo-specific scopes).
- A single apoderamiento commonly covers multiple categories. Gestoras
  configuring one client may need three or four scopes at once.
- Coercing AEAT scope codes into modelo numbers (e.g. `--scope 303`)
  is wrong: AEAT scopes are not modelo identifiers; they are
  procedure categories that map to modelo families.
- The CLI must accept SCOPE in a form the operator can verify against
  AEAT's own apoderamiento certificate; the canonical form must match
  AEAT's published codes.

## Constraints

- SCOPE values are uppercase short codes from the AEAT-published
  apoderamiento catalogue. The CLI ships a fixed catalogue file
  (`registry/aeat/apoderamientos/scopes.toml`) listing accepted codes
  and a one-line description per code.
- `--scope SCOPE` accepts a single uppercase code per occurrence.
- `--scope` is a repeated flag: pass it multiple times to grant
  multiple scopes (`--scope IVAQT --scope IRPFQ --scope IRPFA`).
  Comma-separated values inside one flag (`--scope IVAQT,IRPFQ`) are
  rejected.
- The special token `--scope ALL` grants every scope in the catalogue
  at configuration time. `ALL` expands to a snapshot of the catalogue
  at command time; subsequent catalogue additions do not retroactively
  grant the new scope to an existing apoderamiento.
- Unknown SCOPE values are rejected with a `CliValidationBoundaryError`
  whose message includes the list of valid codes for the active
  catalogue version.
- Stored apoderamiento records preserve the exact scope codes granted;
  catalogue updates do not mutate stored grants.
- The catalogue is a static registry; runtime fetching from AEAT is
  forbidden and is out of scope of this ADR.

## Implementation

Catalogue location and shape:

- `registry/aeat/apoderamientos/scopes.toml` defines:
  - `code`: uppercase short string (e.g. `IVAQT`)
  - `name_es`: Spanish display name (e.g. "IVA - declaraciones
    trimestrales")
  - `name_en`: English gloss (e.g. "VAT - quarterly declarations")
  - `modelo_codes`: list of modelo numbers covered by the scope
  - `notes`: optional clarifying notes
- The catalogue is loaded at command-init time via the registry
  loader.

Command shape:

```text
aeat config auth apoderado configure
    --represented-nif NIF
    --scope SCOPE [--scope SCOPE ...]
    [--certificate-path PATH]
    [--certificate-password-env VAR]
    [--format json|text]
```

Validation:

- Trim and uppercase each `--scope` value before lookup.
- Reject values not in the catalogue with an error listing the valid
  codes (in catalogue order).
- Reject comma-separated values inside a single `--scope` flag.
- Reject duplicate scopes within one invocation; emit a clear
  duplicate error rather than silently de-duplicating.

Output:

- Text: a per-scope confirmation line including the code and the
  `name_es` display.
- JSON envelope: `granted_scopes: [{code, name_es, name_en,
  modelo_codes}, ...]` plus `represented_nif`, `apoderamiento_id`,
  `event_id`.

Bucket event:

- `auth.apoderado.configured` event includes `represented_nif`,
  `granted_scopes` (list of codes), and the catalogue version snapshot
  identifier.

Discovery:

- `aeat config auth apoderado scopes list` is a read-only verb that
  emits the full scope catalogue, with `name_es`, `name_en`, and
  `modelo_codes` per code, through `_emit`.

## Rationale

Pinning SCOPE to the AEAT-published apoderamiento catalogue gives
gestoras a deterministic verification path: each granted scope code
maps 1:1 to a row on the operator's signed apoderamiento certificate.
Treating `--scope` as a repeated flag (not comma-separated) is the
Typer / argparse idiom and avoids quoting traps. The static catalogue
keeps the CLI offline and audit-stable; live catalogue fetching
violates the read-only-live-signals boundary.

## Consequences

- A new static registry file (`registry/aeat/apoderamientos/scopes.toml`)
  ships with the CLI and is versioned with the codebase. Updates to
  AEAT's apoderamiento catalogue require a registry update PR.
- `aeat config auth apoderado scopes list` becomes the discoverable
  vocabulary surface for operators.
- The bucket event history records the catalogue version at grant
  time so audit traces remain interpretable across catalogue updates.
- Tests must cover: valid scope codes accepted; unknown codes rejected
  with the catalogue listed in the error; comma-separated values
  rejected; duplicate scopes rejected; `ALL` expands at command time;
  the `auth.apoderado.configured` event records the granted scopes
  and catalogue version; `scopes list` emits every catalogue entry.
