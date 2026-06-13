---
tags:
  - '#plan'
  - '#linkage-design-audit'
date: '2026-05-15'
modified: '2026-05-15'
tier: L2
related:
  - '[[2026-05-15-linkage-design-audit-research]]'
  - '[[2026-05-15-linkage-design-audit-reference]]'
  - '[[2026-05-26-linkage-design-audit-adr]]'
---
# `linkage-design-audit` `Wave 1: type-system uniformity (Phase 1 of linkage epic)` plan

### Phase `P01` - inventory and tooling

Complete. Catalogues at `scratch/out/suppressions.{json,csv}`, summary
at `scratch/out/summary.json`. Detailed counts per category and per
file recorded; top 20 worst offenders identified.

- [x] `P01.S01` - build suppression inventory tool; `scratch/suppression_inventory.py`.
- [x] `P01.S02` - run inventory and produce master catalogue; `scratch/out/suppressions.json`.
- [x] `P01.S03` - categorise sites by package and external API; `scratch/out/summary.json`.
- [x] `P01.S04` - build pydantic-model audit tool for Wave 2 prep; `scratch/pydantic_audit.py`.

### Phase `P02` - external-API type acquisition

Install community type stubs and remove over-conservative
`allowed-unresolved-imports` entries from `pyproject.toml`. Verify
ty and pyright resolve the typed surface after each change.

- [x] `P02.S05` - add `google-api-python-client-stubs` as dev dependency; `pyproject.toml`.
- [x] `P02.S06` - remove over-conservative unresolved-import entries; `pyproject.toml`.
- [x] `P02.S07` - extend `playwright_stealth` stub if surface gaps remain; `stubs/playwright_stealth/__init__.pyi`.
- [x] `P02.S08` - investigate single tomllib dict-any site; `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`.
- [x] `P02.S09` - re-run inventory to confirm external-API site count drops; `scratch/out/summary.json`.

### Phase `P03` - test-file deliberate-suppression rewrite

The 19 `# ty: ignore[...]` and `# noqa: B010/E731` suppressions in
test files exist to construct invalid pydantic input or bypass lint
on test helpers. Rewrite using `pytest.raises`, named functions in
place of lambdas, or proper pydantic error-construction patterns.

- [x] `P03.S10` - rewrite ty-ignore in master-key kdf-params test; `src/aeat/adapters/persistence/storage/master_key/test_kdf_params.py`.
- [x] `P03.S11` - rewrite ty-ignore in bucket-manifest test; `src/aeat/adapters/persistence/storage/bucket/test_manifest.py`.
- [x] `P03.S12` - rewrite ty-ignore in bucket-export-header test; `src/aeat/adapters/persistence/storage/bucket/test_export_header.py`.
- [x] `P03.S13` - rewrite ty-ignore in master-key recovery-record test; `src/aeat/adapters/persistence/storage/master_key/test_recovery_record.py`.
- [x] `P03.S14` - rewrite ty-ignore in workflow bucket-pointer test; `src/aeat/application/workflow/test_bucket_pointer.py`.
- [x] `P03.S15` - rewrite ty-ignore in aggregation oss-ioss test; `src/aeat/application/aggregation/test_oss_ioss.py`.
- [x] `P03.S16` - rewrite ty-ignore in vat oss test; `src/aeat/domain/vat/test_oss.py`.
- [x] `P03.S17` - rewrite ty-ignore in pdf label-regex test; `src/aeat/adapters/inbound/pdf/test_label_regex.py`.
- [x] `P03.S18` - rewrite ty-ignore in browser evasion test; `src/aeat/adapters/outbound/aeat/browser/test_evasion.py`.
- [x] `P03.S19` - replace lambda noqa in aggregation grouping test; `src/aeat/application/aggregation/test_grouping.py`.
- [x] `P03.S20` - replace setattr noqa in transactions import test; `src/aeat/application/transactions/test_import.py`.
- [x] `P03.S21` - replace setattr noqa in auth sessions-storage test; `src/aeat/application/auth/test_sessions_storage_state_paths.py`.
- [x] `P03.S22` - replace setattr noqa in modelos external-evidence test; `src/aeat/domain/modelos/test_external_evidence.py`.
- [x] `P03.S23` - replace setattr noqa in sanitizer records test; `src/aeat/adapters/inbound/sanitizer/test_records.py`.

### Phase `P04` - domain/ suppression eradication

81 sites across 26 files. Cleanest expected wins; canonical pydantic
shapes already live here. Highest-leverage files: `_models.py` in
`invoices` (16) and `transactions` (16); `_loader.py` in registry (6);
`attachments/_models.py` (6).

- [x] `P04.S24` - replace Any/cast in invoice models; `src/aeat/domain/invoices/_models.py`.
- [x] `P04.S25` - replace Any/cast in transaction models; `src/aeat/domain/transactions/_models.py`.
- [x] `P04.S26` - replace cast in registry loader; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P04.S27` - replace Any in attachment models; `src/aeat/domain/attachments/_models.py`.
- [x] `P04.S28` - sweep remaining 22 domain files for suppression eradication; `src/aeat/domain/`.

### Phase `P05` - application/ suppression eradication

70 sites across 28 files. Highest-leverage files: `auth/_sessions.py`
(11), `auth/__init__.py` (6), `workflow/_models.py` (5).

- [x] `P05.S29` - replace Any/cast in auth sessions; `src/aeat/application/auth/_sessions.py`.
- [x] `P05.S30` - replace Any in auth package init; `src/aeat/application/auth/__init__.py`.
- [x] `P05.S31` - replace Any in workflow models; `src/aeat/application/workflow/_models.py`.
- [x] `P05.S32` - sweep remaining 25 application files for suppression eradication; `src/aeat/application/`.

### Phase `P06` - adapter-internal suppression eradication

86 sites across 31 files. Adapter code not at an external boundary.
Per the disciplined adapter-boundary policy these are direct fixes,
not shims. Highest-leverage file: encrypted-columns adapter (8).

- [x] `P06.S33` - replace Any/cast in encrypted-columns adapter — verified already-satisfied: `rg "Any|cast\("` returns zero matches across the file (272 lines); current state uses `object | None` parameter typing and `TypeDecorator[object]` rather than `Any` or runtime `cast()`. A prior commit must have done the cleanup; no further code change required.
- [x] `P06.S34` - sweep remaining 30 adapter-internal files for suppression eradication; `src/aeat/adapters/`.

### Phase `P07` - core/ suppression eradication

20 sites across 9 files. `core/json_contract.py` (6) ties to T-08 and
will be revisited when `SchemaEnvelope` is adopted in Wave 3.

- [x] `P07.S35` - replace Any/cast in JSON-contract module; `src/aeat/core/json_contract.py`.
- [x] `P07.S36` - sweep remaining 8 core files for suppression eradication; `src/aeat/core/`.

### Phase `P08` - entrypoints/ suppression eradication

7 sites across 6 files. Smallest leak surface.

- [x] `P08.S37` - sweep 6 entrypoint files for suppression eradication; `src/aeat/entrypoints/`.

### Phase `P09` - dunder-override investigation

5 sites on 5 files. `__iter__` / `__getitem__` / similar overrides on
pydantic-extending types. Most likely must remain as pydantic v2
compatibility shims. Investigation determines whether each is
necessary or can be replaced with a typed pattern.

- [x] `P09.S38` - investigate each dunder-override site and write report; `scratch/out/dunder_overrides.md`.
- [x] `P09.S39` - replace removable dunder shims with typed patterns; `src/aeat/`.
- [x] `P09.S40` - document irreducible shims with rationale comments; `src/aeat/`.

### Phase `P10` - 'other' bucket investigation

12 sites on 3 files. Sites that did not classify into any leak
category. Investigation determines correct categorisation and Phase
assignment.

- [x] `P10.S41` - categorise the 12 unclassified sites; `scratch/out/other_sites.md`.
- [x] `P10.S42` - dispatch each site to the correct Phase or address inline; `src/aeat/`.

### Phase `P11` - dual-checker strictness gate

Adopt `pyright` alongside the existing `ty` (`all = "error"`) for
cross-checker verification on `src/aeat/domain/` and
`src/aeat/application/`. Different inference algorithms catch
different issues.

- [x] `P11.S43` - add pyright dev dependency; `pyproject.toml`.
- [x] `P11.S44` - add pyright strict configuration; `pyrightconfig.json`.
- [x] `P11.S45` - run pyright strict on domain and capture findings; `src/aeat/domain/`.
- [x] `P11.S46` - run pyright strict on application and capture findings; `src/aeat/application/`.
- [x] `P11.S47` - resolve pyright-only findings across domain and application; `src/aeat/`.
- [x] `P11.S48` - wire pyright into CI alongside ty; `.github/workflows/`.

### Phase `P12` - regression gates

Mechanical prevention of suppression reintroduction. CI step plus
semgrep rules. Aligns with the prior-art research recommendation for
`semgrep` as the per-pattern enforcement layer.

- [x] `P12.S49` - add semgrep rule rejecting new Any annotations; `.semgrep/rules/no-any-annotation.yml`.
- [x] `P12.S50` - add semgrep rule rejecting new dict-str-Any declarations; `.semgrep/rules/no-dict-str-any.yml`.
- [x] `P12.S51` - add semgrep rule rejecting new cast calls in domain and application; `.semgrep/rules/no-cast-in-domain.yml`.
- [x] `P12.S52` - add semgrep rule requiring inline justification for new ty-ignore; `.semgrep/rules/justify-ty-ignore.yml`.
- [x] `P12.S53` - wire semgrep into CI as gating check; `.github/workflows/`.
- [x] `P12.S54` - close out Wave 1 by re-running suppression inventory; `scratch/out/suppressions.json`.
