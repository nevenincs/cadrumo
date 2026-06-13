---
tags:
  - '#research'
  - '#ccaa-in-profile'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - '[[2026-04-27-modelo-100-renta-full-calc-adr]]'
---

# `ccaa-in-profile` research: `tax-residence profile for Modelo 100`

Issue `#452` exists because the Modelo 100 full-form work landed a closed `CCAA` enum and per-CCAA tarifa/deduction inputs, but no durable user profile records Kent's ordinary autonomous community of tax residence. The result is an incomplete automation path: RENTA verification can re-derive state and autonomic casillas only when the call site supplies CCAA manually.

## Findings

The authoritative CCAA source is `aeat.domain.formulas._rulesets.modelo_100._ccaa.CCAA`. It encodes the 15 ordinary CCAAs and deliberately excludes País Vasco and Navarra because those are foral regimes tracked by `#424`. Ceuta and Melilla are also deliberately excluded from this enum because their RENTA treatment is state-level, not LIRPF art. 46 bis autonomic deduction competence.

The M100 consumer surface currently lives in `aeat.entrypoints.cli.filing`. `aeat filing import --from-borrador` parses a Modelo 100 PDF, audits the summary ruleset, and separately validates the estatal progressive tarifa. It does not validate casilla `0551` against `compute_cuota_autonomica_general(blg, ccaa, año)` because there is no profile CCAA to consult. `aeat filing import --from-declaracion` resolves the ruleset for full declaration imports and verifies it, but likewise has no profile lookup for Modelo 100.

The three existing profile namespaces are unrelated. `aeat.entrypoints.cli.financial.profile` manages per-category usage ratios, `aeat.adapters.outbound.aeat.browser.profile` manages Playwright session profile directories, and `aeat.domain.financial.categories._profile` models spending-category defaults. Reusing any of them would blur tax-residence state with financial classifier, browser, or category metadata.

`aeat.core.config.Settings` already provides env-var and dotenv configuration, but tax residence is personal local state, not process configuration. Tying it only to `AEAT_TAX_RESIDENCE_CCAA` would make CLI-driven first-run setup awkward and would collide with the in-flight storage work in `#216` if it later changes persistence. A small JSON file under the OS config directory gives independent Path A persistence and avoids `#216` entirely.

The setup wizard is already the correct capture point for first-run local state. It writes an `AutonomoProfile` JSON and env vars, so adding a tax-residence prompt and saving the independent tax-residence JSON keeps the concerns separate while making first-run setup complete.

Similar CLI tools typically separate durable identity/profile state from environment configuration, reserving env vars for automation overrides. Here the durable source should be `~/.config/aeat/tax-residence.json` on POSIX-like systems, `%APPDATA%\aeat\tax-residence.json` on Windows, and `XDG_CONFIG_HOME/aeat/tax-residence.json` when present.

The M100 call sites that hand-feed or require CCAA today are: the external caller responsibility documented on `compute_cuota_autonomica_general`, the `aeat filing import --from-borrador` summary verification path that has enough extracted `0545`/`0551` data to validate the autonomic cuota, and the `aeat filing import --from-declaracion` Modelo 100 path that should load the same profile before any full-form autonomic verification.

Recommendation: introduce a new public `aeat.domain.profile` subpackage with strict frozen Pydantic models, atomic JSON storage, and explicit `ProfileNotConfiguredError` / `ForalRegimeError` errors registered in the shared registry. Add `aeat profile show`, `aeat profile set tax-region`, and `aeat profile clear`; wire M100 filing import to load this profile; extend setup to prompt and persist it.
