---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-persona-fleet-round2-findings-audit]]"
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]"
---

# Persona-fleet round 3 — auth / recovery / entity-shape findings

Third testimonial batch — 3 personas on domains orthogonal to the
round-2 remediation: the live/auth surface, lifecycle & recovery, and
a non-autónomo taxpayer shape (a landlord). Method: the testimonial
playbook.

## Roster

| Persona | Task |
|---|---|
| Oriol Camps | Live / auth surface, safety gates |
| Teresa Aguilar | Lifecycle & recovery tooling |
| Bernat Solé | Landlord (rental-only) - does the tool model him? |

## Confirmed positives

- The live-AEAT **safety gate is consistent** - it refuses every live
  path (`filed`, `iva-wallet`, `notifications`, `expedientes`,
  `verify`, `borrador`) when live tests are not enabled (Oriol). No
  accidental live call is possible.
- The **recovery tooling is well-designed** - `repair integrity
  objects`/`registry`, `repair profile` (dry-run by default, refuses
  to clear a healthy pointer), and `reset-state` / `quarantine`
  (destructive-refusal without `--yes`) all gate safely (Teresa).
- The NIF actionable error is re-confirmed by all three personas.

## DESIGN QUESTION (needs an ADR)

### Q1 - the applicability engine has no taxpayer-type model; it defaults everyone to autónomo
The profile has no structured income-type / taxpayer-type field. The
`overview` applicability engine therefore treats every profile as an
*autónomo en estimación directa*. Consequences a landlord (Bernat)
hit:
- `overview agenda` / `calendar` / `explain 130` report **Modelo 130
  applicable and overdue** for a taxpayer whose only income is
  *rendimientos del capital inmobiliario* - he has no *actividad
  económica* and no 130 obligation. The tool gives wrong, harmful
  filing guidance.
- There is no profile field a pure landlord (or a salaried-only
  taxpayer, or a pensioner) can set to say "I have no economic
  activity", so inapplicable quarterly modelos cannot be gated out.

This is an architecture question - how the profile models a
taxpayer's income type, and how modelo applicability is derived from
it. It belongs in an ADR cross-referenced from the apex CLI ADR, not
an ad-hoc patch. **Highest-value round-3 finding.**

## Registry-data gap (hand off to the registry track)

- **R1** - `overview explain` for modelo 100 / 303 / 347 fails with
  `No registry deadline windows registered for modelo '<m>' in year
  2026` (and 2025). The Renta filing window - the single most
  important annual obligation - is registered nowhere, so it never
  appears in any calendar. This is registry deadline-window data;
  hand off to the registry-hardening track. The CLI should also
  degrade gracefully (see H-cluster) rather than erroring out.

## G - Auth surface (in scope - Oriol)

- **G1** `auth status` leaks a stale `certificate_path` after the
  provider is switched (e.g. to `clave_movil`) - shows the old cert
  path beside the new provider.
- **G2** `clave_movil` configure reports `identity_alignment:
  mismatch` with no explanation and no remediation; the suggested
  `auth test` adds nothing.
- **G3** `auth login` refusal renders in Spanish under a Catalan
  (`--output-language ca`) profile.
- **G4** `health_severity` is always empty, even in degraded states.
- **G5** `auth test` is observably identical to `auth status` (no
  deeper check) - recurring (Francisco, round 1).

## H - Recovery & lifecycle UX (in scope - Teresa)

- **H1** `ledger preflight` is referenced by `work calculate` errors
  but is absent from `ledger --help` - a pure discoverability gap
  (the command exists and works).
- **H2** `work resume` requires a 16-char workflow-run id with no CLI
  way to obtain or list it - recurring (Rosario, round 1).
- **H3** `repair quarantine` has no `--dry-run` / no preview of the
  rows it would quarantine.
- **H4** `reset-state --dry-run` reports `reason_class: unreadable`
  on a freshly-created storage root - needs direct reproduction;
  possibly a stray-state bug.
- **H5** the diagnostic log lives system-wide
  (`~/.config/aeat/logs/aeat.log`), not under `AEAT_LOCAL_STORAGE_ROOT`
  - it mixes other sessions' / test paths into a user's log.
- **H6** `overview explain` errors out (exit 2) on a modelo with no
  deadline windows instead of degrading gracefully.

## I - Taxpayer modelling (in scope, investigate - Teresa, Bernat)

- **I1** `ledger categories` lists only expense categories; an
  autónomo's professional-income entries have no correct category.
- **I2** `overview explain` reads stale profile facts - after
  `profile edit --professional-income-withholding-ge-70pct`,
  `profile show` reports `true` but `explain 130` still reports
  `False`. A real read-snapshot bug.

## Disposition

- **Q1** - flagged for a taxpayer-type / applicability ADR; the
  highest-value round-3 follow-up.
- **R1** - registry deadline-window data; handed to the registry
  track. The graceful-degradation half (H6) is in-scope CLI.
- **G, H, I** - in-scope CLI/auth/recovery defects; remediation
  dispatched after the round-2 modelo/bindings cluster lands.
