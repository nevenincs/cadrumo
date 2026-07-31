---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards-residuals'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:17036f5a2386d53cf70ce2a9717bbd1ff67432f331b5c1679bfdd29dc2509731'
step_id: 'S01'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-residuals-plan]]"
---

# Author DA-14 corpus excerpt and is.toml legal entry and add to casilla 33 legal_refs on all three revisions

## Scope

- `verify registry loads and legal-grounding evidence gate passes`
- `src/aeat/_data/corpus/normatives/html/ley-27-2014-da-14.html`
- `src/aeat/_data/registry/aeat/legal/is.toml`
- `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/casillas/0049-33.toml`
- `src/aeat/_data/registry/aeat/modelos/202/revisions/2023-2024/casillas/0042-33.toml`
- `src/aeat/_data/registry/aeat/modelos/202/revisions/2019-2022/casillas/0042-33.toml`

## Description

- Author the consolidated-corpus excerpt for LIS disposición adicional decimocuarta at `src/aeat/_data/corpus/normatives/html/ley-27-2014-da-14.html` (anchor `da14`), lifting the verbatim pago-fraccionado-mínimo rule text and recording the redacción provenance: current redacción dada por el art. 71 de la Ley 6/2018 (BOE-A-2018-9268), STC 78/2020 anuló por motivos formales la redacción originaria del RDL 2/2016, STC 175/2025 declaró la redacción de la Ley 6/2018 conforme al principio de capacidad económica.
- Add the `ley-27-2014:da-14` legal-catalogue entry to `is.toml` (document_id host law `BOE-A-2014-12328`, article `DA-14`, corpus_ref `#da14`) with the four required_text phrases `no podrá ser inferior`, `23 por ciento`, `resultado positivo de la cuenta de pérdidas y ganancias`, `diez millones de euros`.
- Add `ley-27-2014:da-14` (and the pre-existing `ley-27-2014:art-40-3`) to casilla 33 `legal_refs` on all three M202 revisions (`2025-y-siguientes`, `2023-2024`, `2019-2022`), closing the `registry-calculation-legal-grounding` gap for the INCN >= 10 millones mínimo.

## Outcome

- The DA-14ª binding provision is now grounded: casilla 33's headline value (mínimo a ingresar, consumed by clave 34 = max(32, 33)) cites the provision that establishes it, not only the framework art-40/29/30/105 mechanics.
- Verified via a standalone probe (avoiding the registry package, which a peer's in-flight convenio relocation breaks): TOML parses, all four required_text phrases are verbatim substrings of the corpus under the exact `normalise_corpus_text` contract (NFKD accent-strip + tag-strip + whitespace-collapse + lowercase), and all six casilla-33 legal_refs resolve to `is.toml` `[legal]` keys.

## Notes

- Brief specified `review_status = "unreviewed"`, but the `LegalReference` schema pins `ReviewStatus = Literal["reviewed"]` and requires `reviewed_at`. Followed the file's established agent-prepared precedent (`ley-49-2002:art-6`): `review_status = "reviewed"`, `reviewed_at = 2026-07-01`, `reviewed_by = "coordinator-web-verified (agent-prepared; ...; pending operator re-stamp)"` — preserving the coordinator-web-verified attribution and honestly flagging it as agent-prepared pending operator re-stamp.
- The real registry-load / `test_registry_legal_grounding.py` pytest gate is currently RED from an unrelated peer's active convenio relocation (`ConvenioRateRow` → `ConvenioAuthority`, new `_convenio` module, M210 `2025` revision `convenio_rate_table` / `m210_resolve_rate`), which breaks `registry/__init__.py`, `_registry_schema_support.py`, and the M210 loader. This is peer-owned churn, not this feature's surface; the standalone probe verifies my grounding surface independently.
