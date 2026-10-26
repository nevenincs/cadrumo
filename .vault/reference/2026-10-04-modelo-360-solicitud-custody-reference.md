---
tags:
  - '#reference'
  - '#modelo-360-solicitud-custody'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:06977ddecbad7712ffc243d9d0101dbf462ec9c554ca2d7680fe5edf507d9b8f'
related: []
---

# `modelo-360-solicitud-custody` reference: `Modelo 360 export refusal and the encrypted register analogue`

Code read on 2026-10-04 in the `feature/tui` worktree to locate why modelo 360 refused export and which existing storage mechanism the fix should reuse.

## Summary

Why export refused, layer by layer (locators are as of the pre-fix tree unless noted):

- The snapshot boundary demands the typed facts: `src/cadrumo/application/filing/producer_snapshot.py:1142` refuses a 360 snapshot whose model profile is not `Modelo360ProfileFacts`, or whose selected account is absent or has no BIC.
- The export never supplied them: `src/cadrumo/application/modelo/export.py:1021` returned `GeneralFilingProfileFacts` for every modelo outside 303, 202 and 111.
- No refund account was ever selected: modelo 360 has no result-disposition spec, so it resolves to the INGRESO fallback (`src/cadrumo/application/modelo/result_disposition_resolution.py:88`), and the account is selected only for refund dispositions or 303 Nota 3. `ModeloIVAProfile.refund_account` is also never populated by `src/cadrumo/domain/deadlines/profiles.py:685`, so no modelo's refund account reaches export from storage.
- Draft construction coerced every non-text casilla through the Decimal channel, so the required date casillas `devolucion.periodo-fecha-inicio` and `devolucion.periodo-fecha-fin` could never be supplied (`src/cadrumo/application/filing/draft_construction.py`, `_draft_input_channels`).
- After the above, the published página 2 layout declares `m360-2010.pagina02.f002` (computed `complementaria_page_marker`) `required = true` (`src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/export/0003-record-m360-operaciones.toml:33`), while DR360 prints it "obligatorio, blanco o C"; `src/cadrumo/domain/calculations/registry/fixed_width_codec.py:539` refuses an absent required field, so an ordinary solicitud stops there.

The analogue reused for storage:

- `src/cadrumo/adapters/persistence/profile/foreign_assets.py` persists one operator-declared filing-input document as a `FINANCIAL` singleton through `ProfileBareModelSecurePersistence` (`src/cadrumo/adapters/persistence/profile/_secure_model_document.py:65`), whose `mutate` (line 180) is the revision-guarded compare-and-swap unit of work.
- Its namespace is declared in `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py` and enrolled in `src/cadrumo/adapters/persistence/storage/namespace_registry.py`; the secure-object store applies AES-GCM with namespace-bound associated data and an HMAC-derived object-key digest to every such row.
- Export reaches persisted authorities only through `ModeloExportPorts` (`src/cadrumo/application/modelo/export_ports.py`), composed in `src/cadrumo/entrypoints/adapter_composition.py` (`build_modelo_export_ports`).
- `RefundAccount` (`src/cadrumo/domain/deadlines/models.py:165`) is the checksum-validated account identifier (ISO 13616 mod-97).
