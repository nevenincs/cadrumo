---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:cf7c12ca558c16ecab295906819b4760feb41271f31e7159348f2a25194189d4'
step_id: 'S17'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Chase the Modelo 180 data_type-vs-diseno mismatch flagged for perc.provincia and perc.modalidad. Verified all 170 casilla-kind fixed-width export fields across the three modelos carrying fixed-width layouts (131, 145, 180) against their bundled diseno at exact offset and length, not a summary table. Confirmed five casilla_ids where AEAT's own Naturaleza column says Numerico and the registry declares data_type text - perc.provincia 76-77, perc.modalidad 78, perc.porcentaje-retencion 93-96, perc.situacion-inmueble 114, perc.inmueble-provincia 321-322, all Modelo 180, both revisions. No further mismatches found beyond these five - Modelo 145 is otherwise fully correct field by field, Modelo 131 has zero casilla-kind text fields at all. Fixed three of five, each by the shape its own diseno text calls for rather than one uniform typing move. perc.modalidad and perc.situacion-inmueble gained value_policy digit-string, refusing non-ASCII-digit content on render and parse without changing the parsed value's type, since each is a single closed-code Numerico slot the export field enum has no dedicated type for. perc.porcentaje-retencion is different in kind, not degree - its diseno text declares 93-96 as one field, Numerico % RETENCION, explicitly subdivided into a 93-94 ENTERO and 95-96 DECIMAL sub-part, a parent field with two Numerico sub-parts rather than an opaque digit string. That shape is a scaled numeric with two decimals, so the fix is data_type decimal with decimals 2 at the export layer, mirrored by data_type ratio at the casilla's own semantic layer to match the established percentage convention elsewhere in the registry, both replacing an earlier digit-string attempt on the same field that only refused non-digit content without correcting the parsed type. Render and parse round-trip verified directly against realistic rates including AEAT's own worked 19 percent example, which renders to wire bytes 1900 exactly. The committed golden fixture's expected value for this casilla was corrected from the string 0000 to Decimal 0.00 to match the corrected parsed type - the fixture's four-digit expectation was the right shape, the declaration's type was wrong, not the other way round. All three fixes verified against the golden parse fixture in both revisions, the full fixed-width codec and schema suites, and a full sequential registry suite run before and after diffed failure-line by failure-line, showing a clean one-test net improvement (167 to 166 failed) with zero collateral regressions across three separate full runs. Declined the other two, each for a concrete reason rather than force-fitting a fix. perc.provincia and perc.inmueble-provincia are left_zero right-justified two-character province-code fields - the registry's own build-time validator requires digit-string to pair with padding none, and requires allowed_values to pair with value_policy enumerated-digits which itself requires data_type integer, and integer changes the parsed value from str to Decimal and breaks the existing golden fixture that asserts a string - no safe fix exists at this field shape without a design decision this row does not make. Confirmed via the diseno's own wording, los dos digitos numericos, that both province fields are always exactly two digits with no legitimate blank case, which narrows what a future padding change could break to that single verified case. Two further candidates, perc.inmueble-codigo-municipio and perc.inmueble-codigo-postal, are plausibly numeric INE and postal codes but the diseno's own text does not use the word numerico for either, unlike provincia which does - left unconfirmed rather than assumed. Did not touch the fixed-width codec, which unblock-export owns live and uncommitted.

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/export_layouts/0001-0002-modelo-180-perceptor.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2019-2022/casillas/cperc.porcentaje-retencion.toml`
- `src/cadrumo/_data/registry/aeat/modelos/180/revisions/2023-y-siguientes/casillas/cperc.porcentaje-retencion.toml`

## Description

- Compare all fixed-width casilla fields for Modelos 131, 145, and 180 against their bundled record designs at exact offsets and lengths.
- Correct the three Modelo 180 declarations whose official numeric shapes can be represented without changing identifier semantics.
- Preserve the two province-code fields pending the separate padding-policy decision rather than coercing their parsed identity.

## Outcome

The audit found five Modelo 180 mismatches and no additional mismatches in Modelos
131 or 145. The representable fields now enforce digit-string codes or a scaled
two-decimal retention ratio as appropriate. The focused fixed-width and golden
parse gates passed, including the official 19 percent value rendering as `1900`.

## Notes

The province-code padding class was deliberately carried into `P03.S18`, where it
could be repaired without conflating identifiers with numeric quantities.
