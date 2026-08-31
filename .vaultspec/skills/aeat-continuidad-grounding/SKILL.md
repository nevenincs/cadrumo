---
name: aeat-continuidad-grounding
description: >-
  Ground or review cross-revision casilla continuity using the validated
  registry authority and official AEAT/BOE evidence. Use when assigning a
  continuidad_id, authoring evolution records, resolving an ambiguous chain,
  or preparing a continuity worklist.
---

# Ground casilla continuity

Continuity means two revision-specific casillas represent the same legal concept. Repeated numbers, similar labels, or formula resemblance produce candidates only; they do not prove identity.

## Guardrails

- Work from the live repository and current registry schema. Do not reuse frozen corpus counts, copied inventories, or embedded scratch scripts.
- Inspect compiled definitions through `bundled_authority()` from `cadrumo.domain.calculations.registry.authority`. Raw TOML is the authoring surface, not evidence of validated runtime behavior.
- Use official AEAT instructions, record designs, forms, and BOE provisions for identity. Treat search results and third-party summaries only as discovery aids.
- Never infer continuity solely from a casilla number. Numbers can be reused, split, merged, or repurposed.
- Do not mark a chain covered while a material semantic ambiguity remains. Leave it ungrounded and record the missing evidence.

## Workflow

### 1. Build the candidate dossier

Load the bundled validated authority and compare the relevant modelo revisions. For each candidate, collect:

- modelo, revision, casilla identifier, label key, section, value type, unit, sign, formula or source role, applicability, and legal references;
- predecessor and successor candidates, including number changes;
- structural differences that could indicate split, merge, scope drift, or repurposing.

Use repository search only to find the owning registry declarations and existing tests. Do not create a second registry loader. When the work concerns the Modelo 100 AEIP family, use the existing `python -m dev.registry.aeip` workflow and its committed adjudication data rather than a generic pasted script.

### 2. Adjudicate identity

Compare the official descriptions and governing provisions for both revisions. Classify the relationship:

- **same concept**: legal meaning and role are stable;
- **same concept with evolution**: identity remains, but label, formula, section, source, applicability, or presentation changed;
- **split or merge**: the relationship requires explicit evolution semantics and must not be represented as a simple one-to-one identity;
- **repurposed**: a number or position now represents a different concept;
- **ambiguous**: evidence is insufficient, so no stamp is allowed.

Section movement alone neither proves nor disproves identity. A changed legal role or population is substantive even when wording is similar.

### 3. Choose the identifier

Assign one stable `continuidad_id` to the proven concept across revisions.

- Prefer a concise, flat, semantic identifier derived from the legal role.
- Do not encode a revision, transient section path, or current casilla number in an otherwise stable identity.
- Use an instance-specific identifier when two simultaneous concepts would otherwise collide.
- Follow the live `ContinuidadId` schema and naming gates; do not invent punctuation or a parallel namespace.

### 4. Author stamps and evolutions

Stamp every member of the proven chain. For each divergent transition, add the required evolution record at the revision boundary where the change becomes effective.

The evolution records the exact semantic change, affected predecessor/successor, and official evidence. Do not use an evolution entry to excuse an identity break. Splits, merges, and repurposing must follow the live cross-revision schema and validator rather than prose conventions.

Edit only the authoritative registry declarations. Locale reuse follows from grounded continuity; do not force shared translations before the chain is valid.

### 5. Validate before claiming coverage

Run the focused gates sequentially so failures remain attributable:

```powershell
uv run pytest tests/test_cross_revision_drift.py -q
uv run pytest tests/test_registry_locales_parity.py -q
uv run pytest tests/test_casilla_fragment_naming.py -q
uv run pytest tests/test_continuidad_completeness_ratchet.py -q
```

Also run the owning modelo registry tests when declarations changed. A successful raw-file parse is not sufficient; the compiled authority and strict cross-revision validator must accept the chain.

## Handoff

Report the chain identifier, revisions and casillas covered, official evidence used, evolution classifications, files changed, commands and exit statuses, and any candidates deliberately left ambiguous. Do not report a reduced baseline or a passing count as proof that identity was grounded.
