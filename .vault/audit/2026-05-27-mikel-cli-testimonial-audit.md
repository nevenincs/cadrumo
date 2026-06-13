---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-aitor-cli-testimonial-audit]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-28 Mikel Aramburu sea worker Gipuzkoa marinero`

## Scope

Mikel Aramburu Otaegi — Donostia (Gipuzkoa foral), 41, marinero
on Pesquera Itxas Argia. 220 días navegados (150 outside Spanish
waters). Salary €38k. Exercises trabajador del mar surface
(Art. 11.2 LIRPF, DA 24ª, dietas a bordo Art. 9.B.1 RIRPF) +
regression-checks for #228 (wizard) and #175 (foral refusal) +
re-confirms #212 (euskera locale).

## Findings

### POSITIVE — #228 wizard regression CONFIRMED resolved

`aeat config --help` exits 0. P0 fix at 2124486c7 holds.

### POSITIVE — #175 foral refusal CONFIRMED working

Both `pais_vasco` + `navarra` correctly refused with redirect to
foral Hacienda (Bizkaia/Gipuzkoa/Álava/Navarra URLs). Legal
authority cited.

### CRITICAL P0 (NEW) — profile create bricked post-5d66679f9 — RESOLVED a05f120cb

After the `taxpayer_type.fiscal_residency` schema-field backfill
(#550+#197 at 5d66679f9), profile create failed with:
`Integrity. bucket manifest is missing required lifecycle status`.

Different failure mode than original, same outcome: NO operator
could create a profile. Blocks every CLI persona/workflow downstream.
Filed as #244 P0.

RESOLVED at commit a05f120cb: ProfileRepository.list() now tolerates
legacy manifests missing the lifecycle-status field, matching the
silent-skip pattern that workflow/_profile_bucket_scan already uses.
The torn-manifest case was unrelated to the fiscal_residency
backfill — pre-existing legacy buckets in the developer storage
root triggered it because _refuse_duplicate_tax_id drives
self.list() before any write, and one torn bucket blew up the
entire inventory scan. Reproduced clean on a fresh storage root
after the fix; the torn bucket is still surfaced separately via
list_profile_bucket_scan_issues() for repair surfaces.

### HIGH — Art. 11.2 LIRPF marinero exención (50% navegado fuera aguas)

No binding / casilla / profile flag for `dias_navegados_fuera_aguas`
or the 50% exención cap (€60,100/año). Mikel's case: 150/220 ×
€38k × 50% = ~€12,955 reducción silently unavailable.

### HIGH — DA 24ª LIRPF pesquería fuera archipiélago canario

Adicional para tripulantes de buques pesca fuera Canarias. Itxas
Argia operates Cantábrico/Atlántico Norte — exact supuesto. No
reference anywhere in registry.

### MEDIUM — Dietas a bordo Art. 9.B.1 RIRPF exemption

€4,200 dietas a bordo (exempt within statutory limits). No
ledger-classify category, no M100 binding, no distinguishing from
dietas ordinarias.

### LOW — INSS-Marítima régimen especial SS (Ley 47/2015)

Different bases + tipos than general régimen. No profile axis
captures inscription. Affects cotizaciones deducibles in 0012/0013.

### CONFIRMED — Euskera (eu) locale absent (#212 still pending)

`--output-language eu` rejected. Already tracked.

## Recommendations

1. **#244 P0** — fix profile create bucket-manifest lifecycle
   regression IMMEDIATELY. Blocks everything.
2. **NEW task** — Art. 11.2 LIRPF + DA 24ª LIRPF + dietas a
   bordo trabajador del mar régimen axis.
3. **#212** — euskera locale still pending.

Trabajador del mar is ~25k filers/year in Spain — niche but
material when affected.
