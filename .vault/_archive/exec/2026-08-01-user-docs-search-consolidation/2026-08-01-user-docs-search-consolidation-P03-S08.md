---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4281c95b342031e5177a5e186e7a0686f4d68f4cd6825e7e8e6a61849349c572'
step_id: 'S08'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

## Description

- Ground the per-root recall seam with vaultspec-rag semantic searches over the active ADR, plan, deployment-parity execution record, production injector, and existing built-site gate.
- Read the existing built-site parity gate and its registry-backed record projections before editing.
- Add a bounded real-projection casilla probe to the existing browser/Pagefind gate, using the casilla title and every declared localized description as query terms on every root.

## Outcome

The built-site source gate now covers both halves of the multilingual recall contract: the existing concept probe and a new casilla probe. The casilla probe reuses `_materialise_records()` and `_bounded_to_sample()`, obtains one real `casilla` `SearchRecord`, and asserts that its canonical target is returned for the title and each available `OutputLanguage` description on every `en`, `es`, `ca`, and `hu` root. It exercises the production injector's all-language content blob through the same `pagefind.js` browser path the reader uses.

This is source coverage only. It does not establish that a built artefact or deployed root currently passes, and it does not close P03.S08 because the gate has not been run and the live-root re-probe remains deferred.

## Notes

- Static verification passed with Ruff, Python AST parsing, and `git diff --check` for the scoped test file.
- No tests, builds, Pagefind compilation, browser/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run.
- Shared worktree changes outside the scoped gate were preserved; nothing was staged, committed, reset, stashed, or cleaned.
- Grounding used the working `vaultspec-rag` CLI code-search route because the codebase alias route remains rejected; the VaultSpec semantic search also confirmed the governing locale-capability contract.

The casilla helper was tightened to select only a real bounded record carrying all four `OutputLanguage` descriptions; missing locale data now fails the probe-selection gate instead of being silently omitted.

### 2026-08-05 current source/artifact boundary re-audit

Fresh vaultspec-rag grounding over the sweep runner, committed relevance input assembler, per-root recall contract, and P03.S08 execution evidence confirms that the source seam is present: the sweep runner launders live RAG hits through the typed resolver, while the P03.S08 gate probes the production Pagefind path with a real casilla record and all available localized descriptions across the four roots.

The remaining requirement is evidence from a newly built artifact and the authorized per-root/live-root run. The committed relevance file is consumed by the Rung-2 input assembler rather than regenerated implicitly, so no source change or sweep was justified here. P03.S08 remains open. No tests, builds, Pagefind compilation, browser/runtime probes, generated artifacts, live sweeps, reindexing, model downloads, or deployment were run.

### 2026-08-06 authorized multilingual build continuation

Strict user-document builds were attempted for en, es, ca, and hu. Each stopped on the same five known sequence/product divergences before the Pagefind post-build stage: profile-setup history ordering, correct-review history expectation, Modelo 100 export authority absence, the Modelo 303 verification-report localized divergence, and the Renta assembly localized-help divergence. The locale source projection and parity tests are green, but no locale build is represented as green or deployable. The build outputs were not repaired by refreshing goldens or inventing authoritative source data.

### 2026-08-06 authorized built-site locale and per-root Pagefind proof

Fresh vaultspec-rag grounding over the localized legal-reference renderer, locale catalogue gates, and the deployment-parity source contract established the following evidence boundary.

- The production legal projection fix trims only trailing whitespace in the RST presentation of authored `required_text`; registry data is unchanged. Focused legal-renderer tests returned `2 passed`; legal anchor parity returned `3 passed`; Ruff and basedpyright returned clean.
- The real localized Sphinx user-scope matrix returned `3 passed in 320.96s`, covering es, ca, and hu. The preceding isolated docs-root failure was corrected by passing the authoritative repository root into the legal generator; the generated legal pages then passed docutils warnings-as-errors in every target locale.
- The bounded real Pagefind/deployment-parity artefact run returned `17 passed in 324.70s`. It built and read en, es, ca, and hu roots through production Pagefind, proved each root's own language index carries the corpus with count parity, exposed every decided record kind, and recalled one real concept and one real casilla by every declared language term through the browser path.
- The separate translation-completeness gate remains red in all three targets: six failures total (22 incomplete/fuzzy page catalogues and five machine-text dash-policy entries per language). The catalogue-drift checks passed. No catalogue refresh or translation authoring was performed because those failures are outside the search-consolidation renderer/injection change and would require a separate docs-localization tranche.

The built-site multilingual half is now proven. The live-root re-probe and deployment remain unperformed by authorization; P03.S08 stays open pending the deployed-root evidence owned by P04.S12/S13.

### 2026-08-06 current full strict preflight timeout

The current full strict preflight command, `uv run --no-sync python -m dev.docs.build --strict docs/conf.py`, ran for 304.372 seconds and exited with code 124 from the command timeout before returning an actionable build failure or a green result. This is an unverified timeout boundary, not evidence for changing source, refreshing golden artifacts, closing the gate, or publishing deployment. AWS STS authentication remains expired, so the live deployment proof is still unavailable.

### 2026-08-06 current strict build legal-corpus failure

The longer retry of `uv run --no-sync python -m dev.docs.build --strict docs/conf.py` reached Sphinx `builder-inited` and exited with code 1. Registry validation failed before page generation because 39 legal references could not resolve exactly one bundled corpus unit for their declared anchors, including Ley 35/2006 arts. 68.1-68.5, Orden HAC 56/2024 art. 1, Orden HAP 1732/2014 art. 2, Ley 37/1992 and several other Ordenes/RD references. This is an actionable legal-corpus data gate; no resolver fallback, source invention, artifact promotion, or deployment was performed.

### 2026-08-06 current strict build sequence-golden failure

The current strict retry cleared the registry legal-corpus validation after the bounded resolver and sidecar repair. It then reached the sequence-golden gate and exited with code 1 on nine divergences caused by concurrent peer changes (invoice option requirements, category ordering, profile-history ordering, ledger split behavior, and localized registry output). This is not a legal-search failure; the step remains open until a later full build is green.

### 2026-08-06 current four-locale Pagefind parity recheck

Fresh vaultspec-rag grounding over the localized build and deployment-parity contracts was followed by the corrected real integration selector:

- `uv run --no-sync pytest -q dev/docs/tests/test_deployment_search_parity.py` collected zero tests under the repository default marker filter; this was treated as unverified.
- `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` returned `25 passed in 473.55s`.

The run exercised the current production Pagefind/deployment-parity path for the English, Spanish, Catalan, and Hungarian roots and proved local per-root search parity. It does not close P03.S08: strict full builds remain a separate red gate and no live deployment/root probe was performed.

### 2026-08-06 current four-locale integration parity recheck

After the current scoped sweep-plumbing change, the explicit integration selector was rerun:

- `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` returned `25 passed in 392.01s`.
- The run exercised the local English, Spanish, Catalan, and Hungarian Pagefind/deployment-parity path.

This confirms the local four-locale parity boundary remains green. It does not close P03.S08: strict full builds remain a separate red gate, and no live deployment or live-root probe was performed.

### 2026-08-06 four-locale built-site parity rerun

The explicit integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` completed with `25 passed in 465.35s (0:07:45)`. The behavioural build/probe covered the English, Spanish, Catalan, and Hungarian roots (`en`, `es`, `ca`, `hu`). This is fresh built-site evidence only: the live root probes and deployment proof remain outstanding, so P03.S08 stays open.

### 2026-08-07 current shared-tree four-locale parity rerun

After fresh supported vaultspec-rag grounding over the per-root Pagefind contract, the real integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` completed with `25 passed in 541.71s (0:09:01)`. The production local build/probe covered all four roots: `en`, `es`, `ca`, and `hu`, including per-root corpus/index parity and localized concept/casilla recall.

This is current local built-site evidence only. Strict user builds remain a separate red gate, the public `es`, `ca`, and `hu` roots still require live proof, and P03.S08 remains open pending the deployment-side evidence owned by P04.S12/P04.S13. No generated artifact was promoted and no deployment was performed.

#### 2026-08-07 explicit strict locale matrix

The declared `just docs-langs` recipe stopped at the Spanish user-scope build with exit code 1, before reaching the remaining locale loop. The three explicit follow-up commands were then run independently: `just docs-lang en`, `just docs-lang ca`, and `just docs-lang hu`. All four locale builds (`es`, `en`, `ca`, `hu`) reached the sequence-golden gate and failed with the same shared-WIP contract divergences: twelve CLI-sequence failures centered on legal-reference ordering/contents, invoice output additions, and the changed workstation dependency surface. The builds did not reach a green Pagefind/deployable artifact. No sequence goldens, translations, legal data, invoice code, or deployment state were changed; P03.S08 remains open pending a green strict build and live-root evidence.

#### 2026-08-07 current-commit explicit strict locale rerun

After peer commits `85c25a02ca` and `676ade47f6`, the strict locale matrix was rerun on the current checkout. `just docs-langs` stopped at `es` with exit code 1; explicit `just docs-lang en`, `just docs-lang ca`, and `just docs-lang hu` also each exited 1. All four reached the sequence-golden gate and reported the same twelve CLI-sequence divergences, including legal-reference ordering/content drift, profile-history ordering, invoice output additions, and the workstation dependency surface. No locale reached a green deployable build; no goldens, translations, legal data, or peer source were changed. P03.S08 remains open.

### 2026-08-07 current HEAD explicit four-locale strict rerun

The strict locale matrix was rerun against the shared checkout at `HEAD 9e6e552fee`. `just docs-langs` stopped at Spanish with exit code 1; explicit `just docs-lang en`, `just docs-lang ca`, and `just docs-lang hu` also each exited 1. All four reached the sequence-golden gate rather than failing at locale loading or source projection. The common divergences are the expanded legal-reference payload/order, profile-history ordering, invoice output fields (`invoice_class`, `series`, `rectifies_invoice_number`, `recargo_amount`, `iva_category`), and the workstation `model-runtime-hardware-floor` dependency surface; English additionally exposed a Windows log-rotation permission warning during sequence execution. No goldens, translations, legal data, or peer source were changed. No locale reached a green deployable build, so P03.S08 remains open and deployment remains deferred.

### 2026-08-07 locale-run shared-worktree boundary

The locale matrix ran while parallel work advanced the branch from the recorded `9e6e552fee` state to pushed `d24ae2fdee`; the invocations were not a commit-pinned release build. Nevertheless, every observed invocation exited 1 at the sequence-golden gate: `docs-langs` stopped at `es`, and explicit `en`, `ca`, and `hu` each failed. The result is therefore a current shared-worktree red signal, not a claim that one immutable commit was tested. A commit-pinned green four-locale build remains outstanding.

### 2026-08-07 current all-locale local parity rerun

The authorized real-behaviour integration gate `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` completed with `25 passed in 383.05s (0:06:23)`. It exercised the production local Pagefind path for all four build languages: `en`, `es`, `ca`, and `hu`.

This establishes current local per-root parity only. P03.S08 remains open because the strict language builds still have known sequence-golden divergences and the corresponding deployed roots have not been proven reachable; no live result is inferred from this local pass.

### 2026-08-11 formal carry-forward

This row stays OPEN, blocked on both of its halves for two different and separately owned reasons. Both are stated so neither hides behind the other.

The built-site half is blocked by a peer regression, not by its own design. The gate materialises real records through the production injector and drives them through the same browser path a reader uses, which requires the authoritative record projection. That projection currently refuses: 889 Spanish casilla labels are declared with null values, every one of them M303, landed by the active M303 registry buildout on 2026-08-10 and 2026-08-11. Spanish is the mandatory source locale, so the refusal is correct behaviour and must not be softened into a skip. The gate cannot run until those labels carry real values.

The deployed half is blocked by the same expired AWS session that holds the two deployment rows, and is deferred by the same operator decision.

The source coverage this row established is unchanged and remains at HEAD: the concept probe and the casilla probe both assert canonical-target recall for the title and each available description on every one of the four language roots. Source coverage is not a passing gate, and this record does not present it as one.

### 2026-08-12 built-site half proven; row stays open on the deployed half

The first of the two blockers recorded above is cleared, and the built-site half of this row is now proven rather than merely covered.

The M303 null Spanish labels are authored, so the authoritative record projection runs. Three defects in this row's own gate file then surfaced and were fixed, all from one root cause: the deploy language set already carries the source language, so English was being driven through the localized-root paths. The per-root fixture keyed builds by language while English publishes at both the default root and its own subroot, so the second build collided on a directory the first had made and every casilla probe errored before asserting anything. The command-agreement gate asserted the language flag for English, which the deploy deliberately omits. And the environment helper had gained a required argument this call site never passed.

With those fixed the gate runs green: 26 passed, covering concept recall by declared terms in any language and casilla recall by declared localized terms, on each of the four language roots, driven through the real browser path against real built artefacts.

The row stays OPEN on its second half. It requires the same probes re-run against the DEPLOYED roots so a CI pass cannot mask a broken live root, and deployment is deferred by operator decision with the `es`, `ca` and `hu` roots currently returning 404. A green built-site gate is precisely what this row says must not be mistaken for a live one.

### 2026-08-12 the deployed-half blocker changed composition; the row is unchanged

The AWS-credential blocker the deployed half depends on through P04.S12/S13 is cleared: `aws sts get-caller-identity` now succeeds. That does not close this row. The live read-only probe is unchanged -- `/docs/` answers 200, `/docs/es/`, `/docs/ca/`, `/docs/hu/` answer 404 -- and P04.S12/S13 remain open on a separate blocker outside this campaign: 29 modules across other campaigns' surfaces still carry no API stub, so the strict full build the publish path runs first has no confirmed green run. The built-site half proven in the entry above is untouched. P03.S08 stays open pending the deployment-side evidence those two rows own.

### 2026-08-13 the built half is green, and the row's stated blocker was a recipe defect

The row's precondition was investigated rather than accepted, and it did not hold as written. It claimed the built half was blocked because "the local build carries only one of the three localized roots" and that "the justfile already declares one recipe per language". Both observations were real. The inference was not.

**The recipes never built language roots at all.** In the build driver, `--language` selects the CATALOGUE and `--out-dir` is the only thing that puts a build in a per-language subdirectory. `docs-lang` and `docs-langs` passed `--language` alone, so each localized build rendered into the canonical English root at `docs/_build/html` and, because `output_root` was `None`, cleared that root's non-canonical entries on the way in. Three languages in sequence therefore overwrote one another in the English root and produced no language root whatsoever. That is exactly the artefact the row observed: an `es` directory holding stale subdirectories and not one rendered page, with no `ca` or `hu` beside it. Confirmed live — a run launched from the recipe was traced to a `sphinx -b html ... docs\_build\html` process, targeting the English root while nominally building Spanish. It was stopped before it reached its write phase, and the English root was verified intact afterwards.

Fixed in `b9441f3f8f`: both recipes now pass `--out-dir docs/_build/html/<lang>`, matching what the deploy publisher has always done, with the reason recorded beside them so the distinction is not re-lost.

**The gate does not depend on that precondition, by design.** `_root_page_corpus` prefers a real localized root when one exists and otherwise takes the real English pages and retargets the single signal Pagefind reads to decide a page's language, the `<html lang>` attribute. Its docstring states why: the property under test is WHICH index the records land in relative to the pages, the language attribute alone decides that, and the localized Sphinx builds themselves are covered by `test_docs_build_localized`. The probes assert recall of the injected RECORDS, which carry the all-language content blob on every root regardless of the surrounding prose. So the claim is honestly established by the gate as designed.

**Result.** `uv run --no-sync pytest -q -m integration dev/docs/tests/test_deployment_search_parity.py` — **26 passed in 634.49s**. That covers `test_every_root_recalls_a_record_by_its_declared_terms_in_any_language` and `test_every_root_recalls_a_casilla_by_its_declared_localized_terms`, each parametrised over `en`, `es`, `ca` and `hu`, run through real Pagefind indices in a real browser via `pagefind.js`, plus per-root corpus placement, cross-root record-count parity, and per-root kind narrowing.

Two shared-tree conditions were met and re-run rather than triaged as regressions, both outside this campaign's surface and both transient mid-edit states of live peer work: a `RegistryLoadError` on duplicate catalogue ids in an untracked `legal/iva-dana-2024.toml`, and an `ImportError` for `AEAT_THOUSANDS_SEPARATORS` from `cadrumo.core.decimal` during a peer relocation that was mid-write. Neither file was touched. Both resolved on their own and the re-run was clean.

What this does NOT establish: nothing about any deployed root. The original row's second clause — re-probing the deployed roots so a CI pass can never mask a broken live root — is precisely the claim a green built-site run cannot substitute for, and it is now carried by its own row.

### 2026-08-13 honesty review corrections to the entry above

A fresh-context review of this closure returned one HIGH finding that materially corrects the causal account above, plus two clarifications. The closure stands, but the entry above must not be read as complete on its own.

**The recipe defect was not the whole cause, and the recipe fix was not durable.** The full-build orphan sweep resolves every built page's docname against a source under `docs/`, so a page at `html/es/index.html` resolved to a `docs/es/index.md` that has never existed and was unlinked as an orphan. Its skip set covered only asset and infrastructure directories. So every localized root nested in the same tree was emptied by the next apex build — which is a second, sufficient cause of the exact residue this row observed, and it would have undone the recipe fix on the very next `just docs`. The deploy path was safe only by ordering accident, because it happens to build the apex before the language roots. Fixed in `7957b3be2d`: the sweep now exempts a nested per-language site root, deriving the set from the canonical output-language enum rather than a hand-list and deliberately not from the module naming the deploy root set, since that module imports this one. A regression gate asserts the localized roots survive an apex sweep, paired with a genuine orphan in the same tree so a too-wide exemption fails rather than passes vacuously. The exemption was proven load-bearing by clearing it at runtime from outside the repository: with it the localized page survives, without it it is deleted.

**Which corpus the green run measured.** The 26-passed run's subject varies with untracked build output, and the entry above did not say which branch each root took. It is recorded now: the English root read the real built English pages, and `es`, `ca` and `hu` each took the sanctioned retargeted-English fallback, because at run time the language roots held no rendered pages — the very defect this session fixed. The property under test is which index the records land in, decided by the `<html lang>` attribute alone, and the probes assert recall of the injected records, which carry the all-language content blob on every root. The claim therefore stands as made. A follow-up making that provenance self-labelling in the gate's own output is noted in the audit rather than rowed, because the gate's docstring already states the design.

**One prose correction.** The entry above says the localized build "cleared that root's non-canonical entries on the way in". That is wrong as stated: the function it refers to removes stale entries directly under `docs/_build` that are not `html`, and never touches anything inside `html`. The English root was POLLUTED with translated pages, not cleared. The load-bearing half is unaffected and verified — with no output directory the full build's HTML root IS the canonical English root — but the wrong mechanism is precisely what hid the orphan-sweep finding, so it is corrected here rather than left standing.
