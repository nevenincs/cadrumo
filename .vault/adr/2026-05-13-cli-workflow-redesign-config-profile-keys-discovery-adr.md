---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-profile-use-and-status-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Config profile keys discovery verb` | (**status:** `accepted`)

## Problem Statement

`aeat config profile set KEY VALUE` accepts a dotted PROFILE_KEYS path
(e.g., `iva.regime`). Today an unknown key returns "Clave de perfil
desconocida" (UX-007). The 2026-05-07 config-cli-profile-surface ADR
defines the verb tree but does not include a discovery surface for
PROFILE_KEYS. Operators on first-run have no way to learn what keys
exist, what values they accept, or what each key controls. This is a
first-session blocker.

## Considerations

- PROFILE_KEYS is a typed schema in the domain layer (`domain/profile/
  _keys.py`). It evolves as new modelos and regimes are added.
- The schema includes key path, value type (string/enum/bool/int), valid
  enum values where applicable, default, and a short description.
- A discovery verb does not need to mutate state; it is a read-only query
  over the in-process schema definition.
- Operators commonly need to discover keys by domain (`iva.*`, `irpf.*`,
  `address.*`) rather than scrolling the full list.

## Constraints

- `aeat config profile keys [--prefix PREFIX] [--format json|text]`
  enumerates all PROFILE_KEYS with their type, enum values, default, and
  description.
- `--prefix PREFIX` filters by dotted path prefix (e.g.,
  `aeat config profile keys --prefix iva` returns all IVA-related keys).
- The verb is read-only and emits no bucket events.
- The verb's text output is workflow-ordered: required keys first
  (those with no default), then optional with defaults. Within each
  group, keys are grouped by domain prefix.
- When `set` rejects an unknown key, the rejection error includes the
  suggestion "Run `aeat config profile keys` to see valid keys" plus a
  fuzzy-match hint when the typed key is within a small edit distance of
  a known key.
- The verb shows source attribution per key: whether the value comes from
  the schema default, the active profile, or is unset.

## Implementation

Command shape:

```text
aeat config profile keys [--prefix PREFIX] [--format json|text]
```

Pipeline:

- Load the PROFILE_KEYS schema from the domain layer.
- If `--prefix` is supplied, filter to keys matching the prefix.
- For each key, resolve the current value from the active profile if a
  profile is selected; otherwise emit `unset` as the value.
- Order by required-vs-optional, then by domain prefix.

Output:

- Text: a table with columns `key`, `type`, `valid values`, `current
  value`, `source`, `description`.
- JSON: an envelope with `keys: [{key, type, enum_values, default,
  current_value, source, description}, ...]`.

Discoverability hooks:

- `aeat config profile set` rejection error appends: "Run `aeat config
  profile keys` to see valid keys."
- `aeat config init` interactive mode prints "(use `aeat config profile
  keys` after init to see the full schema)" as the first onboarding
  footer.

## Rationale

PROFILE_KEYS is the bridge between a Spanish autónomo's tax situation
and the modelo binding pipeline. An operator who cannot discover the
keys cannot configure their profile correctly. A read-only discovery
verb costs nothing structurally and unblocks every first-session user.
Closing UX-007 with this verb plus the rejection-error suggestion gives
operators a deterministic path from "key not recognized" to "valid keys
are X, Y, Z".

## Consequences

- The 2026-05-07 config-cli-profile-surface ADR's verb tree gains one
  read-only verb; the canonical surface gains the `keys` discovery
  command.
- The `set` command's rejection-error wording is locked to point at
  `aeat config profile keys`.
- Tests must cover: `keys` enumerates the full schema; `--prefix`
  filters correctly; `keys` shows current value when a profile is
  active and `unset` otherwise; `set KEY VALUE` rejection error
  contains the discovery hint; fuzzy match suggests close keys.
