---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-w62-p306-s1832-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---


# `cli-workflow-redesign` Code Review

Review topic: W62.P306.S1832 strict application registry corpus contracts.
Audit surface: `src/aeat/application/registry/_corpus.py`, `src/aeat/application/registry/__init__.py`, `src/aeat/application/registry/test_corpus.py`, with scoped context from topics, manuals, normatives, registry CLI, and governing ADRs.
Rewrite scope: append review findings only; no source implementation changes.

W62-P306-S1832-001 | HIGH | Listed Renta manual parts cannot be consumed by the show/rules/verify application contracts
`src/aeat/application/registry/_corpus.py` discovers legacy on-disk directories named `parte1`, `parte2-deducciones-autonomicas`, and `parte3`, maps them to canonical `ManualPart` enum values, and then emits `part.value` in the list projection. The downstream `show_registry_manual`, `list_registry_manual_rules`, and `verify_registry_manual` contracts pass that canonical enum to the public manuals loader/verifier, whose resolver looks under `part1` and `part2-deducciones-autonomicas` rather than the discovered `parte*` roots. On the committed corpus, `list_registry_manuals()` advertises `renta/2025/part1` from a root under `renta/2025/parte1`, but `verify_registry_manual(RegistryManualVerifyCommand(manual=ManualId.RENTA, year=2025, part=ManualPart.PARTE_1))` raises `ManualNotFoundError` for `corpus/manuals/renta/2025/part1`. This breaks the read-only local corpus inspection contract because a row returned by the application list projection is not a valid input to the application verify/show/rules contracts. Add a real round-trip test from `list_registry_manuals().parts` into verify or resolve the discovered root through a public manuals API so legacy corpus roots and canonical enum values stay consistent.

W62-P306-S1832-002 | MEDIUM | Manual command contracts accept `sociedades` despite the ADR locking manuals to `renta|iva`
The governing ADRs lock the registry manual corpus surface to `--manual renta|iva`, but `RegistryManualsListCommand`, `RegistryManualShowCommand`, `RegistryManualRulesCommand`, and `RegistryManualVerifyCommand` all type `manual` as the full domain `ManualId`. The domain enum currently includes `SOCIEDADES`, so the application contract accepts `RegistryManualShowCommand(manual=ManualId.SOCIEDADES, year=2025)` even though that operator surface is outside the approved W62 registry/manuals scope. Because S1832 is the strict Pydantic contract step, the application boundary should enforce the accepted manual vocabulary before the later CLI adapter consumes it. Restrict these registry corpus commands to an application-level `renta|iva` type or validator, and add a negative real-behavior test proving `sociedades` is refused with `RegistryApplicationInputError`.

W62-P306-S1832-REMEDIATION-001 | CLOSED | Listed manual parts now round-trip through canonical corpus roots
The Renta manual corpus directories were normalized from the legacy `parte*` filesystem names to the canonical `ManualPart` values already enforced by the public manuals domain loader. The application registry discovery path now accepts only `ManualPart(part_dir.name)` and no longer maps `parte1`, `parte2-deducciones-autonomicas`, or `parte3` as aliases. The Renta manifest records and `registry/aeat/legal/irpf.toml` source corpus paths were updated to the canonical `part1` and `part2-deducciones-autonomicas` directories. `test_manuals_list_report_rows_verify_against_canonical_corpus` proves that a row returned by `list_registry_manuals()` can be fed back into `verify_registry_manual()` without a missing-root failure.

W62-P306-S1832-REMEDIATION-002 | CLOSED | Registry manual commands now enforce the approved `renta|iva` vocabulary
The application registry corpus layer now defines `RegistryManualId` with only `renta` and `iva`, uses it in `RegistryManualsListCommand`, `RegistryManualShowCommand`, `RegistryManualRulesCommand`, and `RegistryManualVerifyCommand`, and converts to the domain `ManualId` only inside the backend service boundary. `registry_manual_id()` raises `RegistryApplicationInputError` for out-of-scope manual ids, and `test_registry_manual_id_rejects_out_of_scope_domain_manual_with_application_error` proves `ManualId.SOCIEDADES` is rejected at the application boundary.

W62-P306-S1832-VERIFY-001 | PASSED | Remediation verification
The remediation was verified with `uv run --no-sync ruff check src/aeat/application/registry src/aeat/domain/manuals`, `uv run --no-sync ty check src/aeat/application/registry src/aeat/domain/manuals`, `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py -q`, `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/domain/manuals/test_loader.py -q`, and `uv run --no-sync pytest src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py -q`. The final slices passed with 7, 38, and 37 tests respectively.

W62-P306-S1832-REVIEW-002-001 | HIGH | Canonical manual PDFs must be enrolled under the new paths
The first remediation normalized the corpus paths but left the new canonical `source.pdf` files visible as untracked files because `.gitignore` only unignored the old `parte*` paths. A clean repository checkout from that state would contain registry legal paths pointing at absent canonical PDFs. The fix updates `.gitignore` to unignore the canonical `part1` and `part2-deducciones-autonomicas` Renta source PDF paths for 2020 through 2025. The index now records the old `parte*` PDF paths as renames to the canonical `part*` paths, and `git ls-files -o --exclude-standard "corpus/manuals/renta/**/source.pdf"` returns no untracked canonical PDFs.

W62-P306-S1832-REVIEW-002-002 | MEDIUM | Listed manifest-only manual rows must round-trip through `show` and `rules`
The first remediation only proved list-to-verify behavior. The listed manual rows are manifest-backed even when extracted structure is absent, while `show_registry_manual()` and `list_registry_manual_rules()` previously required `structure/manual.json` through the domain loader. The fix keeps the backend explicit: `show_registry_manual()` returns manifest metadata with `structure_available=False`, zero chapters, and zero sections when no extracted structure exists; `list_registry_manual_rules()` returns an extracted-rule report with `structure_available=False` and zero rules for manifest-only rows. Section lookup still raises `RegistryApplicationInputError` when a caller requests a section without extracted structure. The new real-behavior tests feed listed rows into `show_registry_manual()` and `list_registry_manual_rules()`.

W62-P306-S1832-VERIFY-002 | PASSED | Second remediation verification
The second remediation was verified with `uv run --no-sync ruff check src/aeat/application/registry src/aeat/domain/manuals --fix`, `uv run --no-sync ty check src/aeat/application/registry src/aeat/domain/manuals`, `uv run --no-sync pytest src/aeat/application/registry/test_corpus.py -q`, `uv run --no-sync pytest src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_loader.py src/aeat/application/registry/test_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py -q`, `uv run --no-sync ruff check src/aeat/application/registry src/aeat/domain/manuals src/aeat/entrypoints/cli/_registry_corpus.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/entrypoints/cli/test_backend_boundary.py`, and `uv run --no-sync ty check src/aeat/application/registry src/aeat/domain/manuals src/aeat/entrypoints/cli/_registry_corpus.py`. The final broad slice passed with 50 tests.
