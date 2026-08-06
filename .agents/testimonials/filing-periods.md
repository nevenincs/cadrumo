---
doc: docs/how-to/filing-periods.md
persona: user unsure which period token to use, covered directly by coordinator (background persona failed to launch)
date: 2026-06-18
---

# Understand filing periods — walkthrough

Isolated base `/tmp/coord-periods`; passphrase via env.

## Walkthrough
- **`overview calendar --from 2026-01-01 --to 2026-12-31`** — DOC/APP MINOR: errors on the minimal
  profile (`el perfil activo no declara este modelo fiscal / anulación de perfil incompleto`), same
  root cause as quickstart step 4. The page's first example doesn't run on a fresh profile.
- **`modelo work status --modelo 303 --year 2026 --period 1T`** — refuses `Ejecute primero aeat app
  modelo work create` (S-PREREQ). The token example can't run without a work unit.
- **Reject `--period 2026Q1`** — OK, instructive: `Tokens válidos: 01..12, 1T, 2T, 3T, 4T` (note: the
  list is modelo-scoped — 303 has no `0A`, so `0A` is absent here even though the page lists it as a
  general token; correct, but a reader might be briefly confused).
- **`ledger list --filter period=1T` (no year)** — OK, refused exactly as documented:
  `ledger-period-year-pairing`.
- **`ledger list --filter period=2026-1T --filter year=2026`** — OK, rejected with a helpful message
  listing valid tokens and `--year`.
- **`ledger list --filter period=1T --filter year=2026`** — OK, works.

## Findings
1. **[MINOR][BOTH]** `overview calendar` (the page's first example) errors on a minimal profile that
   declares no modelo. Same root as quickstart M3/step 4. Fix: note the profile must declare an
   activity/modelo, or use an example that works on a fresh profile. (Cross-ref S-PREREQ.)
2. **[NIT][DOC]** The page lists `0A` among "common period tokens," but a modelo-scoped rejection
   (e.g. 303) lists only `1T–4T`/`01–12`; a reader testing `0A` on 303 gets it rejected. Clarify that
   valid tokens are modelo-specific.
3. **[NIT][DOC]** Master-key passphrase prerequisite unmentioned (S-PASS).

## Testimonial
This page does its actual job — explaining period tokens and ledger filters — accurately and well:
every rejection I tried (`2026Q1`, `period=2026-1T`, `period=1T` without a year) was refused exactly
as the page promised, with genuinely helpful error text. My only stumbles were the two example
commands that quietly need more setup than the page admits: the calendar example errors on a fresh
profile and `work status` wants a work unit first. The token/filter contract itself is trustworthy.

## Scorecard
- Doc clarity: 4/5
- App capability: 5/5 (token/filter validation is precise and instructive)
- Findings: BLOCKER 0, MAJOR 0, MINOR 1, NIT 2
