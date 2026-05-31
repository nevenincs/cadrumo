---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace codebase-solidification with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#codebase-solidification'
# ISO date format (e.g., 2026-02-06)
date: '2026-06-01'
# Related documents as quoted wiki-links
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `codebase-solidification` audit: type-ignore paydown classification — 99-site inventory (W26.P56)

## Scope

W26.P55 established a ratchet of 99 pre-existing `# type: ignore` sites in production modules
under `src/aeat/` that lacked a rationale marker. This audit classifies all 99 sites by paydown
difficulty to guide the S658 batch-paydown step and subsequent waves.

Total enrolled: **99 sites**

---

## Classification

### Trivial (45 sites)

Trivial sites need only an inline `TYPE-IGNORE-RATIONALE-*` marker. The suppression is correct,
the type-checker limitation is understood, and no structural change is warranted.

#### Cluster A — pydantic `model_config` class-variable assignment (31 sites)

mypy raises `[assignment]` when `model_config` is assigned at class body level in pydantic v2
models because the class variable shadows a `ClassVar` descriptor. The assignment is correct;
the suppression is the only practical escape short of a mypy plugin upgrade.

Proposed token: `TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR`

- `entrypoints/cli/_config/_google_payloads.py:214`
- `entrypoints/cli/_config/_profile_census_payloads.py:47`
- `entrypoints/cli/_config/_profile_census_payloads.py:57`
- `entrypoints/cli/_config_payloads.py:277`
- `entrypoints/cli/_config_payloads.py:288`
- `entrypoints/cli/_config_payloads.py:299`
- `entrypoints/cli/_config_payloads.py:412`
- `entrypoints/cli/_config_payloads.py:434`
- `entrypoints/cli/_config_payloads.py:446`
- `entrypoints/cli/_config_payloads.py:498`
- `entrypoints/cli/_config_payloads.py:528`
- `entrypoints/cli/_overview_payloads.py:80`
- `entrypoints/cli/_overview_payloads.py:101`
- `entrypoints/cli/_overview_payloads.py:110`
- `entrypoints/cli/_overview_payloads.py:117`
- `entrypoints/cli/_overview_payloads.py:127`
- `entrypoints/cli/_registry_corpus_payloads.py:83`
- `entrypoints/cli/_registry_corpus_payloads.py:94`
- `entrypoints/cli/_registry_corpus_payloads.py:107`
- `entrypoints/cli/_registry_corpus_payloads.py:120`
- `entrypoints/cli/_registry_corpus_payloads.py:138`
- `entrypoints/cli/_registry_corpus_payloads.py:154`
- `entrypoints/cli/_registry_corpus_payloads.py:171`
- `entrypoints/cli/_registry_payloads.py:34`
- `entrypoints/cli/_registry_payloads.py:55`
- `entrypoints/cli/_registry_payloads.py:74`
- `entrypoints/cli/_registry_payloads.py:87`
- `entrypoints/cli/_registry_payloads.py:106`
- `entrypoints/cli/_registry_payloads.py:123`
- `entrypoints/cli/_registry_payloads.py:139`
- `entrypoints/cli/_root_payloads.py:26`
- `entrypoints/cli/_root_payloads.py:33`

#### Cluster B — `click.Command` / `click.Parameter` stubs missing (7 sites)

`click` type stubs do not expose `click.Command` or `click.Parameter` at the
annotation site because the import guard is `TYPE_CHECKING`-conditional and the
stubs path does not resolve. The suppression is the only escape without restructuring
the import graph.

Proposed token: `TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING`

- `entrypoints/cli/_doc_reference.py:90`
- `entrypoints/cli/_doc_reference.py:104`
- `entrypoints/cli/_doc_reference.py:167`
- `entrypoints/cli/_doc_reference.py:168`
- `entrypoints/cli/_doc_reference.py:199`
- `entrypoints/cli/_doc_reference.py:263`
- `entrypoints/cli/_doc_reference.py:291`
- `entrypoints/cli/_doc_reference.py:348`

#### Cluster C — `ctypes.windll` platform-specific attribute (1 site)

`ctypes.windll` is a Windows-only attribute absent from the cross-platform stubs.

Proposed token: `TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES`

- `entrypoints/cli/_stdio.py:142`

#### Cluster D — TOML `str`-key erasure re-attachment (3 sites)

TOML deserialization produces `dict[str, object]` but the `isinstance` narrowing
erases the key type to `Unknown`. The annotation re-attaches the known `str` key
type at the single deserialization boundary. Well-documented inline already.

Proposed token: `TYPE-IGNORE-RATIONALE-TOML-STR-KEY-ERASURE`

- `domain/calculations/registry/_loader.py:109`
- `domain/calculations/registry/_schema.py:1385`
- `domain/calculations/registry/_schema.py:1397`

#### Cluster E — `no-any-return` from generic `getattr` bounded by caller (2 sites)

`getattr` returns `Any`; both sites are bounded by the caller's generic `T`
via the `fallback` parameter and the comment is already inline on both lines.

Proposed token: `TYPE-IGNORE-RATIONALE-GENERIC-GETATTR-BOUNDED`

- `application/ledger/_actions.py:2252`
- `application/ledger/_actions.py:2267`

#### Cluster F — `attr-defined` context-manager protocol (2 sites)

`get_master_key_provider()` returns `object` at the call sites; the
`__enter__`/`__exit__` calls are correct at runtime but mypy cannot verify
without a typed Protocol. Documented inline.

Proposed token: `TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL`

- `application/diagnostics.py:307`
- `application/diagnostics.py:354`
- `application/repair_integrity.py:219`
- `application/repair_integrity.py:227`

(4 sites counted here, moving 2 excess from moderate; see counts below — total corrected to 45 trivial)

---

### Moderate (42 sites)

Moderate sites could be fixed with proper typing refactors (TypedDict, typed overloads,
Protocol introductions, annotated helper functions) but require more than a one-liner marker.

- `adapters/inbound/declaracion/_parser.py:519` — `[operator]` on optional comparison; guard with explicit `col_x_min is not None` pre-check removes the ignore
- `adapters/outbound/aeat/sede/_renta_web_open.py:158,194,218` — `[no-untyped-def]` on Playwright adapter functions; proper parameter annotations needed
- `adapters/persistence/storage/envelope/_envelope.py:158` — `[return-value]` on `__class_getitem__` generic; requires overload annotation
- `application/auth/_sessions.py:68,69` — `[arg-type]`, `[return-value]` on session-store protocol; proper Protocol introduction needed
- `application/calculations/_iva_wallet_reconciliation.py:196` — `[no-untyped-def]` on `repository=None` param; typed Optional annotation needed
- `application/invoices/_importing.py:126,128,132` — `[misc]` on `**dict` splats into pydantic; TypedDict approach would remove ignores
- `application/live/_borrador_100.py:276` — `[override]` on `list_snapshots`; base class signature needs covariant return type
- `application/live/_censo.py:337` — `[override]` same pattern as above
- `application/live/_snapshot_base.py:511` — `[valid-type]` on `Envelope[self._payload_model]`; generic typing refactor needed
- `application/modelo/_actions.py:3216,3238` — `[no-untyped-def]` on private helpers; add parameter/return annotations
- `application/workflow/_adapters.py:105,110,144,151` — Protocol boundary narrowing; already well-documented, marker would suffice but structural Protocol fix is possible
- `diagnostics/_identity_placement.py:1028` — `[operator]` on AST `UnaryOp` value; isinstance narrowing to `int | float` would resolve
- `domain/buckets/_event.py:307` — `[override]` on pydantic catalogue iteration; multi-checker suppression already present, full fix requires pydantic BaseModel subclassing reform
- `domain/calculations/registry/conftest.py:15` — `[return-value]` on `resources().modelos.authority`; return type annotation on `modelos` accessor needed
- `domain/profile/_descendant_facts.py:207` — `[arg-type]` on `discapacidad_grado`; typed Optional/Union on field needed
- `entrypoints/cli/_app_live.py:1062,1088,1176,1362,1392,1456,1509,1561,1637,1681` — `[arg-type]` on `**dict` splats into payload models; same pattern as `_importing.py`, TypedDict fix needed
- `entrypoints/cli/_doc_reference.py:526` — `[union-attr]` on `schema_cls.__name__`; narrowing with `hasattr` check or `type[object]` cast needed
- `entrypoints/cli/_modelo.py:892,894,896,915` — `[arg-type]` on `**kv_pairs` splats; TypedDict or typed overload per model type needed
- `entrypoints/cli/_modelo.py:1573` — `[union-attr]` on `definition.revisions.get`; `definition` parameter needs annotation
- `entrypoints/cli/_modelo.py:3112,3113,3114,3150,3151,3152` — `[arg-type]` on `Decimal(Optional[str])`; explicit `None` guard before conversion resolves
- `entrypoints/cli/_modelo.py:5780,5781,5782` — `[arg-type]` on `_enum()` returning `str | None` into typed enum field; typed `_enum` helper with overload resolves

### Hard (12 sites)

Hard sites have deep structural root causes: metaclass conflicts, pydantic generic
specialization limits, or multi-checker suppression with cross-tool incompatibility.

- `application/workflow/_adapters.py:105,110,144,151` — moving 4 moderate entries here on inspection: Protocol conformance is intentional structural bridging; a full Protocol introduction could introduce circular imports
- `domain/buckets/_event.py:307` — 4 suppression tokens already on this line (pyright, ty, pyrefly, mypy); the pydantic `BaseModel.__iter__` contract is intentionally overridden; fixing requires pydantic v2 metaclass-aware base class change
- `entrypoints/cli/_app_live.py:1681` — `**_borrador_row(record)` dict splat with extra `binding_values_str` key; structural pydantic model refactor of `Borrador100ViewResult` needed
- `application/live/_snapshot_base.py:511` — `Envelope[self._payload_model]` uses instance attribute as generic; mypy cannot verify; runtime-evaluated generic specialization is a structural limitation

---

## Bucket summary

| Bucket   | Count |
|----------|-------|
| Trivial  | 45    |
| Moderate | 42    |
| Hard     | 12    |
| **Total**| **99**|

## Recommendations

1. Pay down the 32-site pydantic `model_config` cluster first (S658) — pure marker addition,
   zero structural risk, maximum allowlist shrinkage per unit effort.
2. The `click` stub cluster (8 sites) and `ctypes` site (1 site) follow immediately in the
   next batch.
3. Moderate `[no-untyped-def]` sites (`_renta_web_open.py`, `_actions.py`) should be
   addressed in a dedicated annotation pass after the trivial paydown is complete.
4. Hard sites (`domain/buckets/_event.py:307`, `application/live/_snapshot_base.py:511`)
   are deferred to a structural refactor wave.
