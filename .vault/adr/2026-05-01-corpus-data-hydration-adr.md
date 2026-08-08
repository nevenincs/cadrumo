---
tags:
  - '#adr'
  - '#corpus-data-hydration'
date: '2026-05-01'
modified: '2026-08-08'
body_hash: 'sha256:b95f1d66c7a7329875d7221d4f8ad464a079649f4a5108446477fbf53bfe8cea'
related:
  - "[[2026-05-01-corpus-data-hydration-research]]"
  - "[[2026-04-12-manual-practico-adr]]"
---

# `corpus-data-hydration` adr: Grounded AEAT Domain Knowledge Strategy | (**status:** `accepted`)

## Problem Statement
The project requires a strictly-typed, version-controlled repository of Spanish tax domain knowledge (the "corpus") to drive calculations, validations, and trilingual help systems. Previous attempts used unverified web search data, which fails the "vigorously grounded" requirement. This ADR formalizes the requirement to source all data exclusively from official AEAT Manuals and BOE Orders for the 2023-2026 period.

## Considerations
- **Legal Accuracy:** AEAT form instructions and BOE orders are the only authoritative sources.
- **Period Coverage:** Support for 2023-2025 is mandatory; 2026 requires future-proofing (placeholder schemas).
- **Trilingualism:** Every record must be available in Spanish (authoritative), English, and Hungarian.
- **Auditability:** Every casilla must be linked to its specific source manual section or BOE article.

## Constraints
- **Human Review Gate:** Autonomous extraction is draft-only. Every committed record must carry a `reviewed_by` and `reviewed_at` stamp.
- **Tooling:** Must use the `src/cadrumo/domain/casillas` models and loaders.

## Implementation
1. **Source Lock-in:** Map every supported model and year to its specific BOE Order and Manual URL (as identified in `[[2026-05-01-corpus-data-hydration-research]]`).
2. **Extraction Pipeline:**
   - Fetch official manual PDFs via `domain/manuals/_fetch.py::fetch_manual_part`, invoked ad hoc by a maintainer. It is NOT, and must never become, an operator CLI verb: `manuals fetch`/`citations fetch` under `app registry` is structurally forbidden by `test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry`, on the grounds that manual fetch writes PDFs and manifests and is not bucket-scoped or evented. (This corrects the original text here, which named a CLI verb — `aeat manual fetch` — that does not exist and was deliberately barred by that later decision.) The record-design ("Diseño de Registro") subtree has its own actually-runnable mechanism instead: `dev/corpus/sync_aeat_record_design_corpus.py --pull` (a dev-only script, also not CLI-wired).
   - Parse "Diseño de Registro" tables to lock casilla IDs and data types.
   - Extract trilingual descriptions using the Manual structure.
   - No fetch mechanism of any kind currently exists for the `aeat_official/instructions/` subtree (the AEAT sede "Instrucciones" pages, distinct from the Manual and the Diseño de Registro): no `ManualId` member, no `PartSpec` entry, no sync script, no manifest. Hydrating that subtree needs new tooling, not an extension of an existing invocation.
   - The same is true of the `corpus/normatives/html/` subtree (consolidated BOE legal texts, which the Problem Statement above requires as a source), with one difference that makes it easier to miss: it already holds committed files and extracted sidecars. Only the EXTRACTOR exists — `dev/docs/preprocess/_html.py::extract_html`, which operates on an `.html` already present. Nothing acquires that `.html`: no BOE retrieval anywhere in `src/` or `dev/`, confirmed both by URL search and by HTTP-client search, the latter with a passing positive control (the same search finds `fetch_manual_part`). The `instructions/` subtree is visibly empty and noted; this one is populated and was not, and the presence of artefacts reads as evidence of a working pipeline. Hydrating it likewise needs new tooling, maintainer-only and not CLI-wired, and it must enforce rather than merely document the consolidated-text traps.

     **Version selection must NOT be positional, in either direction.** An earlier draft of this bullet said to take the LAST listed version, on the belief that consolidated payloads list oldest-first. **That is inverted for the payloads this repo actually holds, and following it would have selected repealed text** — exactly the defect the rule exists to prevent. Measured from the bundled bytes: `ley-37-1992-art-90.html` lists `20120714, 20091224, 19951230, 19941231, 19921229`, so its LAST entry is the original 1992 text. `boe-a-2024-12944-...html` is not even monotonic across the document (`20250123, 20241224, 20240627, 20250129`), because the radios repeat per bloque — so no single positional rule, and no document-wide maximum, is correct either.

     The safe rule is readable from the payload rather than inferred from order: request `buscar/act.php?id=<BOE-ID>` with **no `p` parameter**, so BOE serves the current consolidated text, and then **assert the served version carries the `checked` marker** — whose label reads "Última actualización, publicada el …" where the others read "Modificación publicada el …" or "Texto original, publicado el …". That refuses by construction and survives BOE reordering the list, which positional selection cannot.

     **The invariant is PER FIELDSET, not document-wide.** A multi-block payload repeats the selector once per bloque, and blocks amended at different times legitimately sit at different versions: `boe-a-2024-12944` has four blocks, two checked at `20250123` and two at `20250129`, because the 29/01/2025 amendment did not touch the first two. So the assertion is `checked == max(that fieldset's own values)`. **A document-wide maximum would refuse this correct payload** — a safe failure direction, but still a defect, because it blocks a valid fetch. The repeated selector is the signal that blocks are independent, not redundancy. Remaining enforceable checks: the hidden document id in the payload must equal the requested id; the amending norm's identifier must appear in the taken bytes; write binary and read back before trusting; never pass legal text through a shell. The gate's mutation proof is *"select the last listed version instead of the checked one"*, which must red.
3. **Continuous Pattern:** Establish a standard directory layout `corpus/casillas/<modelo>/<year><period>.json` to be mirrored for every new tax year.

## Rationale
This strategy ensures the application's tax engine is 100% grounded in law. By moving from "fake" skeleton data to "real" citation-backed data, we eliminate the risk of calculation errors based on outdated or misremembered rules.

## Consequences
- **Red CI on Drift:** Any mismatch between extractor code and corpus JSON will fail the coverage test.
- **Review Overhead:** Adding a new year or model requires a one-time human review pass to approve the extracted records.
- **Robust Calcs:** Calculations can now safely use the `formula` field in the corpus, knowing it accurately reflects the official AEAT logic.
