---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-modelo-file-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `Actor attribution and --by default on app modelo file` | (**status:** `accepted`)

## Problem Statement

The `aeat app modelo file` command takes a mandatory `--by ACTOR` flag, but
the apex and modelo-file ADRs do not specify what ACTOR is, what type system
it follows, or what default applies when the operator does not pass it.
Solo autónomos must repeat the same identity on every invocation; gestoras
under apoderamiento must distinguish their own gestora identity from the
client identity recorded in the bucket. Without a defined grammar and
default, every implementation choice diverges and audit traces become
unreliable.

## Considerations

- The active profile identifies the bucket owner (the autónomo or legal
  entity whose data the bucket holds).
- A gestora operating under apoderamiento acts on behalf of the bucket
  owner; her recorded action attribution is distinct from the bucket
  owner identity.
- Audit traces in the filing record, bucket event history, and verification
  reports must be able to answer "who performed this action" without
  conflating "whose data is this".
- `--by` is the existing flag; renaming it (e.g. to `--actor`) creates
  needless churn and is rejected.

## Constraints

- ACTOR is a free-form short string with maximum 64 Unicode characters,
  validated as non-empty after trimming whitespace. ACTOR is NOT validated
  as a NIF; ACTOR is an action-attribution label.
- When the operator omits `--by`, the active profile's `display_name`
  field becomes the default ACTOR value. The default is materialised at
  command time and written verbatim into the filing record; subsequent
  active-profile renames do not retroactively alter past records.
- When `--by` is supplied, the supplied value is written verbatim.
- ACTOR is never auto-derived from the operating-system username, shell
  environment, or any non-bucket source.
- ACTOR is stored on the filing record (`filing_record.actor`) and on every
  bucket event emitted by `aeat app modelo file` (in the event's
  `actor_or_source` field).
- ACTOR is rendered in `aeat config bucket history`, `aeat app modelo
  status`, and `aeat app modelo filing-record show` output exactly as it
  was supplied or defaulted at the time of recording.
- ACTOR is not a secret. The active-profile `display_name` is already a
  bucket-readable label; defaulting from it does not leak credentials.

## Implementation

- `--by` becomes an optional flag on `aeat app modelo file`. The Typer
  option declaration uses `default_factory` to read the active profile's
  `display_name` from `workflow_state_repository()` at invocation time.
- The `--by` help text reads: "Action attribution label, max 64 chars.
  Defaults to the active profile's display name."
- The materialised ACTOR value is rendered in the `aeat app modelo file`
  text output footer ("filed by carlos") and in the JSON envelope field
  `actor`.
- Validation: trim leading/trailing whitespace; reject empty strings;
  reject strings longer than 64 Unicode characters; reject strings
  containing control characters. Validation failure raises
  `CliValidationBoundaryError`.
- The `--reason TEXT` flag remains independent of `--by`; reason has no
  default and is optional.

## Rationale

Defaulting from the active profile's `display_name` removes the most
common friction (solo autónomo repeating her own name on every quarterly
filing) without losing audit fidelity. Treating ACTOR as a free-form
label (not a NIF) reflects the real attribution semantics: it answers
"who pressed the button" rather than "whose taxes". The gestoría case is
served by explicitly supplying `--by "María García (gestora-12345678Z)"`
or any other unambiguous label of the gestora's choosing; the bucket
owner remains identified by the active profile, not by ACTOR.

## Consequences

- `aeat app modelo file` invocation is one flag shorter for the solo
  autónomo case.
- Audit traces gain a deterministic default that always matches the
  active profile context at the time of filing.
- Tests must cover: omitted `--by` defaults to active-profile display
  name; supplied `--by` is written verbatim; over-long, empty, and
  control-character inputs are rejected; the recorded value is immutable
  across subsequent display-name renames.
- The flag grammar is locked. Future deviation (e.g. structured actor
  identifiers) requires its own ADR.

## 2026-05-15 amendment - widen scope to all mutating modelo verbs

The 2026-05-15 ground-truth audit found that `--by` is wired on
`discard` / `file` / `amend` (the original ADR scope) but absent from
`calculate` and `rename`, despite the plan rows describing actor
attribution as covering "mutations" in the broad sense. This
amendment widens the locked scope to include every mutating modelo
verb.

Required: `--by ACTOR` Typer Option with `default_factory=
_resolve_default_actor` MUST be added to the following modelo CLI
handlers and threaded through to the backend services as an explicit
`actor` parameter recorded in the resulting bucket event payload:

- `aeat app modelo work calculate` - default `system` becomes the
  active profile display_name; backend `calculate_modelo_revision`
  takes `actor: str` and records it in the `MODELO_CALCULATION_CREATED`
  event payload.
- `aeat app modelo work rename` - same default-factory pattern;
  backend `rename_work_unit` takes `actor: str` and records it in the
  `MODELO_WORK_UNIT_RENAMED` event payload (add the event type if
  absent).

Other mutating verbs (`work create`, `work delete`, `bindings *`,
`filing-record *`) remain out of scope until each is reviewed for
operator-attribution semantics. Read-only verbs (`work list`,
`work show`, `bindings list`, `bindings preview`,
`verification-report *`, etc.) are explicitly excluded.
