---
tags:
  - '#research'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4b490da172386d54646bee0595a3ff7adae939af8e9773ad0fd2ff394e4101c7'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
  - "[[2026-08-04-canonical-storage-management-void-assertion-class-audit]]"
  - "[[2026-08-30-repo-gate-integrity-wrong-subject-gates-audit]]"
---

# `quality-gate-zero-closure` research: `Measuring assertions that cannot fail`

## Findings

This record exists because the counts it carries are load-bearing for `2026-09-07-quality-gate-zero-closure-blind-green-gates-adr` and were otherwise unrecorded. Measurement ran against the working tree over 2026-09-06 and 2026-09-07 while other sessions committed concurrently, so revisions moved during the sweep; each figure below is the count at the moment it was taken, not a stable population.

**The instruments.** Two AST probes were written and run over every `test_*.py` under `src/cadrumo` and `dev`. The subsumption probe walks each `ast.Assert` whose test is a `BoolOp(Or)`, requires every operand to be exactly one `ast.Compare` with `ast.In` and a string-constant left side, requires all operands to share one `ast.unparse`d haystack, and reports when one needle is a substring of another. The absence probe collects `assert "<literal>" not in <expr>` where the comparator mentions output, then joins each literal against the four locale catalogues and against a corpus of every `.py`, `.yml`, `.toml`, `.json`, `.md` file under `src/` and `dev/`.

**Subsuming disjunction — seven repaired, one residual.** The probe reported five on first run, after two had already been repaired by hand in the same session: `test_config.py:167` (`profile_record_unreadable` subsumed by `unreadable`), `test_config_custody_profile_lifecycle.py:577` (`No active profile` subsumed by `active profile`), `test_ledger_source_jurisdiction_validation.py:139` (a four-operand disjunction where `IRNR` sits inside `TRLIRNR`), `test_period.py:108` (`event-n` / `event`), `test_recargo_equivalencia.py:82` (`Tipos del recargo` / `Tipos`), `test_output_language_typed_consumers.py:57`, and `test_ledger_corpus_journeys.py:364`. One residual remains unrepaired: `test_profile_session_root_resume.py:175` (`'"rows"'` subsuming `'rows'`), which could not be observed because the test skips on this host — the Windows credential store refuses a probe write with `(1312, 'CredRead', 'A specified logon session does not exist')`.

**Self-echoing token — three repaired.** `test_ledger_link_check_verbs.py:40` accepted `"--evidence-id"`, the flag the invocation itself passes, which Click quotes back inside `No such option: --evidence-id`. `test_repair_reset_progress.py:163` accepted `"reset-state"`, which Click quotes back inside `No such command 'reset-state'`. `test_ledger_preflight_verb.py:123` accepted a lowercase `classification=business` alongside the uppercase enum value. Paired control invocations established the discrimination: `ledger link … --evidence-id ev-123` exits 2 with `No such option` present, while the same command without the flag also exits 2 — on a Spanish no-active-profile refusal — with `No such option` absent. Separately, `config repair reset-state --dry-run` exits 2 carrying `No such command`, while the live spelling `config repair reset-progress --dry-run` exits 0 with `reset\tfalse` and no such token, so a re-introduced verb now fails the assertion.

**Absence assertions — the population.** The probe found 420 absence assertions, of which 83 carried a literal appearing nowhere outside the asserting module and 33 were bound to exactly one of the four locale catalogues. Both numbers overstate the defect: `test_ledger_import_folder_partial_success.py:92` asserts `"a_good.csv" not in result.output` for a file the test creates at runtime, which the corpus join cannot see. Adding pin-detection and excluding Click's own untranslated messages reduced 33 to **10** unpinned absence assertions on the product's own English text. Two were repaired: the pair at `test_modelo_source_mesh_calculate.py` (now lines 996 and 1070) and `test_registry_cli.py:300`.

**The sharpest instance.** `test_modelo_source_mesh_calculate.py` asserted `"ADVISORY:" not in text_result.output` under the ambient Spanish locale, while `calculate_source_advisory` renders `'ADVISORY: …'` in `en` and `'AVISO: …'` in `es` (also `AVÍS:` in `ca`, `FIGYELMEZTETÉS:` in `hu`), emitted from `_modelo_rendering.py:250`. The assertion could not fail even if an advisory were surfaced, which is the only thing it exists to detect. Its sibling JSON assertion was already correct, filtering on the stable notice code `modelo.work.calculate.source_advisory`. No test anywhere in the suite asserts that prefix is PRESENT, so the rendering has never been positively exercised in text mode.

**Probe fallibility, measured.** The first locale probe recognised only `--language` and `--output-language` as pinning and reported 17 hits, of which 8 were pinned by `env={"CADRUMO_OUTPUT_LANGUAGE": "en"}` and were false positives. A later reading of `language_argv.py:26` shows the real set is `("--language", "--lang", "--output-language")` plus the environment variable — four forms, not three. Every count above should be read as a floor produced by an instrument whose own blind spots were found only by looking for them.

**Two false starts worth recording.** A first repair asserted the refusal context as `key=value`; the renderer writes `key: value` under a localised `Error.` heading, and the raw English domain message reaches Spanish output unlocalised. A second asserted a title-cased `"Tipos del recargo"`; the BOE excerpt reads `Artículo 161. Tipos.` with lowercase `los tipos del recargo de equivalencia`, so the title-cased operand was the dead half and bare `"Tipos"` was carrying the test. Both were caught by running the assertion, not by reading it.

**What is not decidable.** Well-formed-but-irrelevant remains outside static reach: an assertion that is perfectly shaped and simply not about its subject is indistinguishable, to any probe, from one that is on point. That property is what mutation testing measures directly and is why the governing decision installs mutmut before the detectors rather than after.

## Sources

- `dev/quality/tautological_assertion_scan.py` — the existing trivially-true scanner and the boundary claim this measurement tested.
- `dev/tests/test_tautological_assertion_gate.py` — the scanner's only consumer, sweeping `src/cadrumo` and `dev` with a per-root anti-vacuity floor.
- `dev/tests/test_no_tautology.py` — an independent inline detector over test-control modules; it does not use the scanner above.
- `src/cadrumo/entrypoints/cli/language_argv.py:26` — the four locale-pinning forms.
- `src/cadrumo/locales/{en,es,ca,hu}/cli.yml` — `calculate_source_advisory` prefixes.
- `src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py` — the in-repo pattern for a declaration checked against AST-discovered reality.
- `2026-08-04-canonical-storage-management-void-assertion-class-audit` — the 400/213/13/155 absence-assertion frame and the deferral this work answers.
- `2026-08-30-repo-gate-integrity-wrong-subject-gates-audit` — the origin of the boundary claim, scoped to that audit's own instances.
