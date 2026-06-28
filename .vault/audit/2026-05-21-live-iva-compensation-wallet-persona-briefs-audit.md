---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# Live IVA compensation wallet W04 persona briefs

Date: 2026-05-21

CLI entrypoint: `uv run aeat ...`

Safety boundary: personas may exercise local commands and CLI help. No persona may enter real taxpayer secrets, submit information to AEAT, click through a live representation gate, or perform any live form mutation. Live-wallet checks stop at the documented read-only boundary.

## W04.P01.S01 - first-run autonomo persona

Persona: a first-run autónomo with no prior local state who wants to get from profile setup to a Modelo 303 calculation attempt.

Official CLI surfaces to operate:

- `uv run aeat config profile --help`
- `uv run aeat config profile create <local-test-profile>`
- `uv run aeat app ledger --help`
- `uv run aeat app ledger import --help`
- `uv run aeat app ledger add --help`
- `uv run aeat app modelo work --help`
- `uv run aeat app modelo work create --help`
- `uv run aeat app modelo work calculate --help`

Bounded task:

1. Create or switch to a disposable local profile.
2. Discover whether ledger evidence should be imported or manually entered.
3. Discover the minimum commands needed to create a Modelo 303 work unit and calculate a draft.
4. Stop at the first point where real taxpayer values would be needed.

Testimonial questions:

- Which command first made the next step unclear?
- Was the difference between ledger evidence, manual casilla input, and binding input understandable?
- Did the CLI make clear that calculation is local and does not submit to AEAT?
- What output would have reduced uncertainty?

## W04.P01.S02 - returning accountant persona

Persona: an accountant returning to a local profile with historical data who wants to inspect state, calculate four Modelo 303 quarters, and prepare Modelo 390.

Official CLI surfaces to operate:

- `uv run aeat app ledger status --help`
- `uv run aeat app ledger list --help`
- `uv run aeat app modelo work list --help`
- `uv run aeat app modelo work revisions --help`
- `uv run aeat app modelo bindings list --help`
- `uv run aeat app modelo work calculate --help`
- `uv run aeat app modelo work verify --help`
- `uv run aeat app modelo export --help`

Bounded task:

1. Inspect available ledger and modelo work-unit state.
2. Identify the CLI path to calculate four Modelo 303 periods.
3. Identify the path to calculate and verify Modelo 390 from prior local observations.
4. Stop before exporting any real taxpayer artifact.

Testimonial questions:

- Can the accountant see which quarters have local calculation observations?
- Can they tell whether Modelo 390 is using filed-history observations or ledger aggregation?
- Are missing unsupported IVA regimes or missing prior filings surfaced as blocking issues?
- Does export clearly state that it is local-only and still legally sensitive?

## W04.P01.S03 - live-wallet reviewer persona

Persona: a reviewer focused only on the live IVA compensation wallet capture and the no-live-mutation safety boundary.

Official CLI surfaces to operate:

- `uv run aeat app live iva-wallet --help`
- `uv run aeat app live iva-wallet pull --help`
- `uv run aeat app live iva-wallet history --help`
- `uv run aeat app live iva-wallet capture-history --help`

Bounded task:

1. Inspect the live wallet command help and required arguments.
2. Verify the command descriptions identify the operation as read-only capture.
3. If operating against live AEAT in a controlled review, stop immediately at any representation gate, Cl@ve post-auth gate, or page requiring outbound form submission.
4. Confirm that no AEAT form is submitted and no representation choice is posted.

Testimonial questions:

- Did the CLI make the read-only boundary visible before authentication?
- Was it clear what `--year`, `--period`, and `--taxpayer-nif` mean?
- Did any command text imply that form submission or representation selection might be automated?
- What refusal text would be clearest at the fail-closed boundary?

## W04.P01.S04 - multiyear compensation reviewer persona

Persona: a reviewer validating whether cross-year carry-forward, expiry age, and authority decisions are understandable to an operator.

Official CLI surfaces to operate:

- `uv run aeat app live iva-wallet history --help`
- `uv run aeat app live iva-wallet capture-history --help`
- `uv run aeat app modelo work revisions --help`
- `uv run aeat app modelo work verify --help`
- `uv run aeat app modelo export --help`

Bounded task:

1. Inspect how local IVA compensation history is captured and listed.
2. Check whether the CLI exposes source year, source period, remaining amount, applied amount, and expiry review state.
3. Check whether wallet/local/override authority decisions are visible before a Modelo 303 calculation or export.
4. Stop before any live AEAT operation or real export artifact.

Testimonial questions:

- Can the reviewer explain which source period generated a remaining compensation balance?
- Can they see whether a balance is active, due for expiry review, or blocked?
- Can they distinguish AEAT wallet evidence from local filed-history recurrence?
- Does the CLI show enough evidence to decide whether an override is justified?

## Captured setup evidence

Help commands executed locally on 2026-05-21:

- `uv run aeat --help`
- `uv run aeat app modelo --help`
- `uv run aeat app live iva-wallet --help`
- `uv run aeat config profile --help`
- `uv run aeat app ledger --help`
- `uv run aeat app modelo work --help`
- `uv run aeat app live iva-wallet pull --help`

No live AEAT command was run while creating these briefs.
