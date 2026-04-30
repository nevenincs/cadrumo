# Tax-Residence CCAA Profile

Issue: #452

The tax-residence profile records Kent's ordinary autonomous community for RENTA. It is separate from financial usage profiles, browser profiles, and financial category profiles.

Modelo 100 calculations depend on autonomous-community context. LIRPF arts. 46 bis and 73-77 define how tax residence affects the autonomous-community share of IRPF and regional rules. In the M100 flow, the tax-residence CCAA drives casilla 0551, provides Anexo Ñ context, and supports aggregation of autonomous deductions into casilla 0622.

## Model

The public package is `aeat.profile`.

`KentTaxResidence` is a strict, frozen model with schema version `"1"`:

- `ccaa`: one ordinary CCAA value from the closed CCAA enum re-exported by `aeat.profile`
- `tax_residence_since`: optional start date
- `tax_residence_change_history`: optional change history

Kent supports one tax-residence CCAA per tax year. Multi-residency within a single tax year is out of scope for #452.

The in-scope values are the 15 ordinary CCAAs. País Vasco and Navarra are foral regimes and are intentionally refused for this profile; support belongs to #424. The aliases `pais-vasco`, `país-vasco`, `pais_vasco`, `país_vasco`, `euskadi`, and `navarra` are rejected with a #424 pointer. Ceuta and Melilla are not tax-residence CCAA profile values and are treated at state level.

## Persistence

Kent uses Path A local JSON persistence. This does not depend on the #216 database work.

The profile is stored as `tax-residence.json`. The location can be overridden with `AEAT_TAX_RESIDENCE_PROFILE_PATH`.

Default locations are:

- Windows: `%APPDATA%\aeat\tax-residence.json`
- POSIX: `$XDG_CONFIG_HOME/aeat/tax-residence.json`
- POSIX fallback: `~/.config/aeat/tax-residence.json`

Writes are atomic: the profile writer writes a temporary file and replaces the target with `os.replace`.

Setup captures `tax_residence_ccaa`, prompts for the RENTA tax-residence CCAA, defaults to Madrid, and persists the tax-residence JSON alongside the existing `AutonomoProfile`.

## CLI

The tax-residence profile is managed through `aeat profile`.

Available commands:

- `aeat profile show`
- `aeat profile show --json`
- `aeat profile set tax-region <ccaa> [--since YYYY-MM-DD]`
- `aeat profile clear`

`show` reports the configured tax-residence CCAA and references downstream Modelo 100 casillas 0551 and 0622.

If a Modelo 100 import needs the profile and it is missing, the CLI raises `ProfileNotConfiguredError` with the suggested command:

```bash
aeat profile set tax-region <ccaa>
```

## Modelo 100 Imports

`aeat filing import --from-borrador` requires a configured tax-residence profile. The import validates casilla 0551 from casilla 0545, the configured profile CCAA, and the tax year when both casillas are present.

`aeat filing import --from-declaracion` also requires the tax-residence profile for Modelo 100.

For terminology around borrador, predeclaración, and declaración PDFs, see `docs/concepts/aeat-pdfs.md`.
