---
tags:
  - '#audit'
  - '#profile-lifecycle-disaster'
date: '2026-05-20'
related: []
---

# `profile-lifecycle-disaster` audit: `operator blind re-test P06 testimonials and findings`

## Scope

P06 re-test gate of the profile-lifecycle disaster-recovery campaign. Five
blind operator personas (newcomer, returning, dual, fumbler, curious)
each operated the `aeat` CLI in an isolated clean install with no source
access, scoring operator friction 0 (effortless) to 10 (blocked). The
goal criterion is the campaign's close condition: operator pain reduced
from the original "heavy" baseline toward zero. This document also
records the three-axis semantic audit swarm (persistence-boundary
identity, cross-domain handoffs, calculation grounding) run after the
reconciliation campaign's structural refactor.

Status: re-test in progress — three persona testimonials recorded
below; newcomer and curious pending; S47 closing synthesis to follow.

## Findings

### Persona re-test — pain scores

- returning (Monday-morning re-orientation): overall pain 6/10.
- dual (two-client bookkeeper): overall pain 4/10.
- fumbler (error-prone usage): overall pain 2/10.
- newcomer: pending.
- curious: pending.

### Real defects (operator-facing bugs)

HIGH — `aeat config profile edit --quiet` is a destructive full
rewrite, not a patch. Fields not explicitly supplied silently revert
to their defaults; the returning persona's `preferences.output_language`
flipped from `en` to `es` with no warning while changing an unrelated
field. There is no `--set key=value` / `--patch` mode. Corroborated
independently by the returning and dual personas. For a tax tool,
silent mutation of stored data on a single-field edit is a data-integrity
defect.

HIGH — postcode `08001` is stored as `8001`. The leading zero is
stripped by an integer coercion; Spanish postcodes are 5-digit strings
and `8001` is invalid. No warning shown. Surfaced by the returning
persona.

MEDIUM — `aeat config profile create` silently promotes the new
profile to active with no line in its output saying so. The dual
persona created a second profile and was then operating under it
without knowing. `create` output should emit the active-profile line
that `switch` already emits.

MEDIUM — the `--activity` flag accepts arbitrary free text. The
fumbler persona created a profile with activity `pizza-delivery`; no
enumeration, no validation, no warning. If activity drives downstream
IAE-epigrafe lookups or modelo bindings it will fail silently far
later.

### UX and i18n friction

MEDIUM — help-text tables truncate every long flag name to roughly
twenty characters (`--address-postco...`, `--tax-residence-...`), so
the actual invocable flag name is unreadable. The only discovery path
is to type a wrong truncated form, read the error's did-you-mean
suggestion, and retry.

LOW — the `profile list` subcommand help text wrongly says it lists
all config keys and their values; it lists profiles.

LOW — a NIF validation error leaks the internal translation-key path
`wizard.setup.profile.tax-id.prompt` into the operator-facing message.

LOW — error text rendered in Spanish under a profile whose
`output_language` is `en` (entangled with the edit-rewrite defect
above, which reverts the language preference).

### Robustness note

The dual persona hit a raw Pydantic `ValidationError` traceback on
`profile switch` once (`ExternalConstants` schema mismatch —
`auth_gate_4033` missing / `auth_gate_path_marker` extra), then an
identical retry succeeded. Verified non-reproducing now (`import aeat`
clean across repeated runs): it was transient drift from a concurrent
external-constants edit. The latent concern stands — a module-import-time
`_Settings()` / `_BROWSER_DEFAULTS` construction can surface a raw
traceback on an unrelated command during concurrent config edits;
lazy initialisation would remove that failure class.

### Error-path quality — the campaign's original worst axis

The fumbler persona recorded 13 of 14 deliberately-wrong inputs
producing a clean, translated, actionable refusal, with zero raw
Python tracebacks across the whole session. Did-you-mean fires at
every level of the command tree; every state guard names the bad
value and gives the exact remedy command. The original campaign's
heaviest pain point — error handling — is now a strength.

### Semantic audit swarm

- persistence-boundary identity: clean. Persisted namespace/table/key
  strings stable across the campaign's renames; 87 roundtrip tests
  with anti-tautology proofs; typed `Envelope` version discipline
  across 18 repositories; SHA-256 identity helpers sound.
- cross-domain handoffs: two HIGH findings, both fixed — a
  silently-empty cross-domain snapshot check, and two re-broken
  import-linter contracts. All four layered contracts now enforced.
- calculation grounding: clean — provenance chain, casilla coverage,
  referential integrity intact; one reported test-coverage gap
  verified moot (the roundtrip test exists).

## Recommendations

The re-test confirms error-path quality is excellent but the
mutation/edit surface still carries real defects, so the campaign
does not close yet. Drive the fix wave (tracked as the P06 re-test
fix-wave task) after the disaster-plan tail lands, sequenced:

1. `profile edit` becomes a true patch — only explicitly-supplied
   fields are written; unsupplied fields are preserved. Add a
   `--set key=value` style targeted edit.
2. `contact.postcode` (and any zero-significant identifier field)
   typed and stored as a string, not coerced through `int`.
3. `profile create` emits the active-profile line in its output.
4. `--activity` validated against the IAE / activity catalogue, or
   the free-text contract made explicit.
5. UX: stop truncating flag names in help; fix the `profile list`
   description; strip the internal translation-key path from the NIF
   error; honour `output_language` on every refusal message.
6. Robustness: make `ExternalConstants` / browser-defaults
   initialisation lazy so it cannot crash an unrelated command.

The S47 closing synthesis will append the newcomer and curious
testimonials and the before/after pain-score comparison.
