---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-nuria-cli-testimonial-audit]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-18 Pedro Iglesias intracom IVA M349 reverse-charge`

## Scope

Eighteenth testimonial round, Pedro Iglesias Romaní — Madrid
autónomo software consultant. EDS régimen + IVA general + ROI
inscrito. 2024 mix: €60k Spanish-domestic B2B + €38k EU-B2B
(Germany SaaS €22k + France SaaS €16k) + €13.8k EU adquisiciones
servicios (Stripe/GitHub/Notion/Slack/Linear from Ireland).
Exercises M303 quarterly autoliquidación + M349 informativa
intracom recapitulativa + reverse-charge mechanism Art. 84.1.2º
LISIVA. Three new surfaces this round.

## Findings

### CRITICAL — M303 calculation blocked for new profiles (wallet seed not surfaced)

`aeat app modelo work calculate --modelo 303 --year 2024 --period 1T`
fails with `Modelo 303 prior compensation requires a persisted IVA
wallet reconciliation decision`. Tried every override — `--binding
modelo-303-compensacion-pendiente-anteriores=0`, `--casilla
"110=0"`, `--casilla "iva.compensacion-pendiente-periodos-anteriores=0"`.
None work.

Error message suggests `aeat app ledger preflight --mode modelo`
but the `--mode` flag does not exist (`No such option`). Obsolete
hint. The S352 iva-wallet seed verb (shipped at c5a41d7c2) is the
correct path: `aeat app modelo iva-wallet seed --filing-year 2024
--period 1T --amount 0 --confirm`. FU-S352 #165 (de6641b0d) was
supposed to route the hint through tr() but the M303 calculate
path appears to surface a different error site that wasn't
updated.

Every new autónomo on their FIRST M303 hits this wall. No
workaround documented in any CLI verb help.

### CRITICAL — M349 row data fields inaccessible (third instance of cross-cutting pattern)

M349 fila de operador requires per-row: `codigo-pais` (string),
`nif-comunitario` (string), `apellidos-razon-social` (string),
`clave-operacion` (S/E/T/R/I/M enum), `importe` (decimal).

- `--casilla "op.codigo-pais=DE"` rejected (post-#174 non-decimal
  guard, correct).
- `--binding vat-349-operador-row-codigo-pais=DE` accepted but
  silently discarded; casilla output stays 0.
- Indexed syntax `[0]` / `:0` rejected.

Same pattern as M184 (Núria F1+F2, #200) and M232 (Sergio C4,
#184). Three modelos × multi-row × non-decimal-fields × no-CLI-
input-path. Structural cross-cutting gap.

The `collectible_invoice` ledger source could feed M349
operador rows but the invoice schema has no `--country-code`,
`--eu-vat-id`, `--operation-type` fields. Circuit incomplete.

### HIGH — `ledger collectible-invoice` / `payable-invoice` missing intracom fields

Both verbs accept any string as `--counterparty-nif`. No
intracom-specific fields:
- `--country-code` (2-letter ISO).
- `--eu-vat-id` (free string for now, validated by format).
- `--operation-type` (E=entrega bienes, S=prestación servicios,
  T=triangular, A=adquisición bienes, I=adquisición servicios).

Without these, no automated path from ledger to M349 rows
exists. Pedro's invoices to DE/FR clients cannot be flagged as
intracom services. His Stripe/GitHub Ireland invoices cannot be
flagged as intracom adquisiciones de servicios.

### HIGH — No EU NIF format validation, no VIES integration

`DE345678901` (9 digits, correct DE format) and `FR12345678901`
(11 chars, correct FR format) accepted without comment. So is
`DE12345` (invalid — too short). No regex per country, no VIES
lookup. An M349 presented with malformed EU NIF is bounced by
AEAT.

VIES real-time validation is optional but BASIC format validation
per country regex is inexcusable. Minimum: regex per country code
(DE+9d, FR+11c, IT+11d, IE+specific pattern, etc.).

### MEDIUM — M303 binding intracom doesn't separate bienes vs servicios

Single binding `modelo-303-iva-autorepercutido-intracomunitaria-
cuota` (`ledger_iva_aggregation`) lumps bienes + servicios. The
BOE M303 form has separate casillas 10/11 grouping but with
distinct economic meaning for reverse-charge analysis. The
engine cannot segregate Stripe (servicio Art. 84.1.2º) from a
hypothetical hardware acquisition (bien Art. 13 LISIVA) for
M349 cross-reference.

### MEDIUM — M303 ↔ M349 cross-reference absent

No verify or check cross-references M303 casilla 10/11 sum
against M349 clave A/I (adquisiciones) declarations for the
same period. Discrepancies are a frequent AEAT paralela
trigger. A finding `INTRACOM_DISCREPANCY` in `work verify`
when sums mismatch would close the loop.

### MEDIUM — Obsolete `--mode modelo` flag in M303 wallet error hint

The wallet-reconciliation error references `aeat app ledger
preflight --mode modelo`. The `--mode` flag does not exist on
preflight. Mis-direction. Likely a #165 FU regression — the
hint update via tr() did not reach this specific error site.

### LOW — M369 OSS present without B2B-not-applicable note

M369 (One Stop Shop, OSS) is in the catalog as `ad_hoc`. A new
autónomo with EU-B2B operations could confuse M349 (B2B) vs
M369 (B2C digital). No note in M369 entry explaining "for B2C
cross-border digital services; for B2B use M349".

### POSITIVE — Profile axes for intracom are well-modelled

`--does-intracomunitario` and `--iva-intracommunity-operations-
exceed-50000-eur` (M349 frequency threshold) flags exist and
flow into profile. The framework knows the intracom concept;
the gap is in the downstream calculation engine + ledger
binding completion.

## Recommendations

Priority remediation:

1. **M303 wallet-seed error guidance** (CRITICAL P0) — investigate
   why FU-S352 (#165 de6641b0d) tr() routing did not reach the
   error site Pedro hit. Audit all sites raising the wallet-
   reconciliation refusal; route every site through `tr()` and
   point operators at the existing `iva-wallet seed --confirm`
   verb. Cheap fix (locale + error-site update) but unblocks
   every new autónomo.

2. **Multi-row non-decimal-field CLI mechanism** (CRITICAL,
   cross-cutting) — task #200 (M184 multi-row member declaration)
   should be GENERALISED to cover M232 (operaciones vinculadas
   rows, #184 task), M349 (operador rows, Pedro), and M184
   (member rows, #200). Single mechanism design: repeatable
   `--row` flag OR `aeat app modelo work row add` subcommand
   with typed pydantic models per modelo. Saves three separate
   ad-hoc implementations.

3. **Ledger intracom invoice fields** (HIGH) — extend
   `collectible-invoice add` and `payable-invoice add` with
   `--country-code`, `--eu-vat-id`, `--operation-type` flags.
   Feed M349 row auto-generation.

4. **EU NIF format validation** (HIGH) — per-country regex
   table (DE+9d, FR+11c, IT+11d, IE+pattern, NL+pattern, etc.).
   Reject malformed at `--counterparty-nif` entry time.

5. **M303 intracom segregation** (MEDIUM) — split binding into
   bienes vs servicios. Enable cross-reference with M349
   clave-operacion taxonomy.

6. **M303 ↔ M349 cross-reference** (MEDIUM) — verify finding
   when sums diverge.

7. **Obsolete `--mode modelo` cleanup** (MEDIUM) — purge
   reference; replace with current `iva-wallet seed --confirm`
   verb.

8. **M369 disambiguation** (LOW) — add help note explaining B2C/
   B2B distinction.

Quantitative impact: M303 wallet block affects 100% of new
autónomos. M349 unfileability affects every autónomo with EU
intracom operations (~150k filers/year). The multi-row pattern
gap structurally blocks 3+ modelos.
