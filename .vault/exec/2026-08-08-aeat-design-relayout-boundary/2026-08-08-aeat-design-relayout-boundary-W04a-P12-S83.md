---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:40eed1873c56f7b1652f90ec303f8266994cb5bcd8255f67038d6ea320825c74'
step_id: 'S83'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W04a.P12.S83`

Reclassify the 32 Administracion-reserved name slots from bindings to filler in both Modelo 232 mapping epochs, and delete the reservado casilla and binding fragments, the construct rows and the completeness-manifest rows from both revisions.

## Executed

- 4 mapping fragments (`dev/registry/mappings/modelo_232/{2016,2018}/{0002-dr23201,0003-dr23202}.toml`): 32 entries per epoch reclassified — 5 `kind = "casilla"` and 3 `kind = "binding"` in dr23201, 24 `kind = "binding"` in dr23202 — each flipped to `kind = "filler"` with its casilla/binding line removed.
- 64 binding fragments deleted (`bindings/*reservado-nombre.toml`, 32 per revision).
- 5 `vinculada-N-reservado-nombre` casilla rows removed per revision from the multi-id casilla fragments.
- 32 binding ids removed from each revision's `constructs/0001-modelo-232-informative.toml` `bindings` list.
- 5 casilla rows removed from the 2018 completeness manifest (the 2016 manifest carried none).
- The generated `export/` trees were deliberately NOT hand-edited: the publication verb regenerated them once the emission contract landed.

## Verification

- `load_modelo_directory` on the swept modelo 232 directory loads clean for both revisions.
- The semantic-map join (`join_record_design_semantics`) passes for both trees; the anchor bijection is unchanged because the entries keep their anchors.
- Post-landing, the coverage validator reports zero reserved-byte intrusions for either revision, and the generated fragments carry `kind = "filler"` for every reservado slot.
- The one-shot sweep script lives at `tmp/s83_m232_reserved_sweep.py`; its per-file counts matched the inventory exactly (8/24 per map, 5/5 casilla rows, 32/32 construct ids, 64 files).
