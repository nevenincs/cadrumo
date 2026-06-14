---
tags:
  - '#audit'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-adr]]'
  - '[[2026-06-10-aeat-cli-userdocs-hardening-audit]]'
---

# `aeat-cli-userdocs-hardening` audit: `userdocs backlog and decision steps resolution`

## Scope

Resolution pass over the six product-gap and decision steps the userdocs
hardening plan deferred for live-CLI assessment: `S11` (curated root-help
advertising decision) and the five backlog candidates `S20`, `S26`, `S32`,
`S37`, `S52`. Each was assessed against the live CLI and the source to decide
whether the operator need is already met (close as already-covered), genuinely
missing (record a backlog item with acceptance criteria), or a decision to make
and act on. The prior session audit flagged exactly this set as
backlog/decision candidates depending on the CLI surface.

## Findings

### S11 | DECISION (acted) | Curated help omitted journey-critical surfaces

The backend-authored curated help in `src/aeat/application/operator_surface/_help.py`
advertised `import` through `export` for the ledger and `list`/`describe`/`bindings`/`work`
for modelo, but omitted six real surfaces from `aeat app --help`: `ledger add`,
`ledger evidence`, `ledger doclink`, `ledger providers`, `modelo
verification-report`, and `modelo m036`. Decision: advertise the three
first-journey surgical surfaces and leave the evidence/provider power surfaces to
`aeat app ledger --help`. Acted on: added curated entries for `aeat app ledger
add`, `aeat app modelo verification-report list`, and `aeat app modelo m036`,
with locale keys authored through the locale CLI in all four catalogues
(`ledger_add`, `modelo_verification_report`, `modelo_m036`). Verified rendering
in `aeat --language en app --help`; locale scaffold, parity, and translation
honesty gates green.

### S20 | CLOSED already covered | Profile-driven applicability is answerable

`aeat app overview calendar --show-suppressed` enumerates applicable and
non-applicable modelos for the active profile with each verdict and reason, and
`aeat app overview explain MODELO` decomposes one modelo into its
registry-backed rationale plus the profile facts the decision depends on. The
"which enrolments apply, and why" need is met from the profile in plain language.

### S26 | CLOSED already covered | Ledger review surface is sufficient

`aeat app ledger status` (readiness rollup), `aeat app ledger review --filter
issue` (the actionable queue), and `aeat app ledger preflight --year --period`
(the per-field missing-facts report) together answer "what still needs review?"
plainly. No missing surface.

### S32 | BACKLOG | Discovery report exists; guided manual-value prompt does not

The discovery half is already answered: `aeat app modelo bindings list` shows a
per-binding `source` plus a plain-language `readiness` column (the
`_BINDING_SOURCE_TO_READINESS` mapping), and `--missing` filters to bindings
still owed, so users do not have to infer sources from raw ids. The residual gap
is a guided entry flow: `aeat app modelo work calculate` takes raw repeatable
`--casilla` and `--binding` flags with no interactive prompt. This is recorded
as a backlog item (acceptance criteria in Recommendations).

### S37 | CLOSED already covered | Verification findings carry a plain next action

`ModeloVerificationFinding` carries a typed `next_action` rendered across the
text, JSON, and notice transports. The values are operator-plain concrete
commands (for example a missing-casilla finding emits the exact `work calculate
... --casilla ...` to run; an unsupported-IVA finding names the `ledger attach`
step). `legal_refs`/`source_refs` ride alongside but never replace the plain
action.

### S52 | CLOSED already covered | Filing-history surface separates local vs AEAT state

`aeat app overview calendar`/`agenda`/`backlog` answer what is filed, what was
missed, and what remains due, and keep local state distinct from official AEAT
state: each row carries a separate `local_filing_state` and an
`aeat_submission_state` that defaults to `NOT_OBSERVED` until a real AEAT pull
populates it. The calendar therefore never implies official AEAT state it has not
observed.

## Recommendations

- **S32 backlog acceptance criteria.** Deliver a guided manual-value entry flow
  (an interactive verb, or an `--interactive` mode on `work calculate`) that
  iterates the `bindings list --missing` set, shows each binding's plain
  `readiness`/`source` and casilla label, prompts for the value with type and
  format hints, validates at the boundary, and persists the same draft revision
  `work calculate` would. Acceptance: on a work unit with N missing non-constant
  bindings it prompts for exactly those N and produces an equivalent draft. The
  documentation already covers the discovery report and the honest first-filing
  zero pattern, so this backlog item is a UX surface, not a docs gap.
- **S11 follow-on (optional).** A future pass may also surface `ledger evidence`
  / `doclink` / `providers` in `aeat app ledger --help` prose; they remain
  reachable via the Typer help and are intentionally out of the first-journey
  curated set.

## Codification candidates

No finding meets the three durability criteria. S11 is a one-time curated-help
completion already enforced by the locale parity and honesty gates; the four
CLOSED items are confirmations of existing capability; the S32 backlog is a
single tracked UX follow-up. Nothing here generalises into a new cross-session
rule.
