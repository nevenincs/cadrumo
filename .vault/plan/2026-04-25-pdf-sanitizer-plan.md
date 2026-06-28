---
tags:
  - '#plan'
  - '#pdf-sanitizer'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-pdf-sanitizer-adr]]"
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-25-aeat-verify-plan]]"
  - "[[2026-04-25-aeat-verify-adr]]"
  - "[[2026-04-24-aeat-verify-reference]]"
---



# `pdf-sanitizer` `pdf-sanitizer-phased-delivery` plan

Phased delivery plan for `aeat.adapters.inbound.sanitizer` — the first-class PDF
sanitiser that the parent `aeat-verify` ADR's W1 phase 4 now depends
on. Phases run sequentially. Each phase ends with a focused commit.
Code review runs after every phase; the final phase gates on
adversarial-absence tests passing on the first committed sanitised
fixtures.

## Status legend

- `pending` — not started
- `running` — in progress
- `done` — code committed, review passed
- `blocked` — waiting on a sibling phase

## Phase status (point-in-time)

- Phase 1 — `done` (commit `e58f2d2`)
- Phase 2 — `done` (commit `6f9cb48`)
- Phase 3 — `done` (commit `aa3c801`)
- Phase 4 — `done` (commit `efcaed5`)
- Phase 5 — `done` (commit `184898c`)
- Phase 6 — `done` (commit `8e528d9`)
- Phase 7 — `done` (commit `460965a`)
- Phase 8 — `done` (commit `cf6ce32`)
- Phase 9 — `partial`. Pipeline runs end-to-end on the 2022 IRPF
  capture (`scratch/sanitizer-validation/`): 19 replacement edits,
  9 mapping entries verified, deterministic output. Committing
  fixtures into `tests/fixtures/justificantes/` is operator-gated
  on enumerating every PII surface (monetary casillas, free-text
  fields) in each declaration. See `2026-04-26-aeat-verify-audit`
  for the closure path.

## Tasks

### Phase 1 — Skeleton + records

Produce the strict-frozen pydantic v2 record types and the package
skeleton. No PDF logic yet.

1. Add `pikepdf>=10.0.0` to `pyproject.toml` `dependencies`. Run
   `uv lock --upgrade-package pikepdf` to refresh the lockfile.
2. Create `src/aeat/adapters/inbound/sanitizer/__init__.py` with public re-exports
   (currently bare; populated phase-by-phase).
3. Create `src/aeat/adapters/inbound/sanitizer/_records.py` with:
   - `_ReplacementBase` (`SecretStr` real, `str` synthetic,
     `surface_label`).
   - `NifReplacement`, `NameReplacement`, `AddressReplacement`,
     `ExpedienteReplacement`, `CsvReplacement`, `NrcReplacement`,
     `IbanReplacement`, `ImporteReplacement`,
     `ArbitraryReplacement` — each with synthetic-shape validators
     reusing the project's existing validator helpers
     (`aeat.validators.nif_letter`, etc.).
   - `TokenMap` aggregating all replacement tuples.
   - `Replacement`, `ScrubbedSurface`, `SanitizationWarning`,
     `DeterminismFlags`, `SanitizationResult`.
4. Create `src/aeat/adapters/inbound/sanitizer/_errors.py` — `SanitizationError`,
   `SanitizerSourceParseError`, `SignaturePresentError`,
   `AlreadySanitizedError`, `UnknownSurfaceError`, all inheriting
   `aeat.core.errors.AeatError`.
5. Create `src/aeat/adapters/inbound/sanitizer/test_records.py`:
   - `model_config` correctness (frozen, extra=forbid, strict).
   - `SecretStr` repr-leak guard (`repr(token_map)` does NOT
     contain any cleartext NIF / name / etc.).
   - Each `*Replacement` synthetic validator round-trips a known-
     valid synthetic and rejects a known-invalid one.
   - `TokenMap` accepts empty tuples for every category.
6. Run `uv run pytest src/aeat/adapters/inbound/sanitizer/test_records.py -m unit`.
7. Commit: `feat(sanitizer): records skeleton + token-map (#239)`.

### Phase 2 — Determinism flags + save helper

Lock byte-stable output before any rewrite logic.

1. Create `src/aeat/adapters/inbound/sanitizer/_determinism.py` with
   `apply_save_flags(pdf: pikepdf.Pdf, target: BinaryIO) ->
   DeterminismFlags`. Wraps `pdf.save(target, deterministic_id=
   True, compress_streams=True, object_stream_mode=ObjectStream
   Mode.preserve, linearize=False, recompress_flate=False,
   static_id=False)`. Returns the flags applied for capture into
   `SanitizationResult`.
2. Create `src/aeat/adapters/inbound/sanitizer/test_determinism.py`:
   - Synthesise a tiny PDF in-test with `pikepdf` (no fixture
     dep). Sanitise it through `apply_save_flags` twice. Assert
     `output_a == output_b` byte-for-byte.
   - Sanitise it through bare `pdf.save()` without flags; assert
     output is **not** byte-equal across runs (validates the
     baseline non-determinism).
3. Run the test.
4. Commit: `feat(sanitizer): determinism flags + byte-stable save
   (#239)`.

### Phase 3 — Static metadata scrub

DocInfo + XMP wipe.

1. Create `src/aeat/adapters/inbound/sanitizer/_metadata.py` with
   `scrub_docinfo(pdf: pikepdf.Pdf) -> ScrubbedSurface` and
   `scrub_xmp(pdf: pikepdf.Pdf, *, strategy: Literal["delete",
   "rewrite"]) -> tuple[ScrubbedSurface, tuple[
   SanitizationWarning, ...]]`.
2. Create `src/aeat/adapters/inbound/sanitizer/test_metadata.py`:
   - Synthesise an in-test PDF with `Title`, `Subject`, `Author`,
     `Keywords`, `Creator`, `Producer`, `CreationDate`, `ModDate`
     populated. Run `scrub_docinfo`. Assert all keys absent on
     reload.
   - Synthesise an in-test PDF with an XMP packet claiming
     `pdfaid:part=1`. Run `scrub_xmp(strategy="delete")`. Assert
     `Root.Metadata` absent.
   - `strategy="rewrite"`: assert PII-bearing keys cleared and the
     `pdfaid:*` claim dropped.
3. Run the test.
4. Commit: `feat(sanitizer): docinfo + xmp scrub (#239)`.

### Phase 4 — Dynamic-surface strip

Attachments, JS, annotations, OpenAction, AA, OCG, AcroForm,
thumbnails, outlines, page labels, structtree.

1. Create `src/aeat/adapters/inbound/sanitizer/_dynamic.py`. One function per
   surface. Each returns a `ScrubbedSurface` with a count.
2. Create `src/aeat/adapters/inbound/sanitizer/_structtree.py` with
   `drop_struct_tree(pdf: pikepdf.Pdf) -> tuple[ScrubbedSurface,
   tuple[SanitizationWarning, ...]]` — drops the entire tree and
   emits a `structtree_dropped_lossy` warning.
3. Create `src/aeat/adapters/inbound/sanitizer/test_dynamic.py`:
   - In-test PDF with one embedded file, one JS action on
     `OpenAction`, one annotation, one OCG. Run each scrub
     function in turn. Assert each surface absent on reload.
4. Run the test.
5. Commit: `feat(sanitizer): dynamic-surface strip (attachments,
   JS, annotations, ocg, structtree) (#239)`.

### Phase 5 — Content-stream rewrite

The token-replace engine.

1. Create `src/aeat/adapters/inbound/sanitizer/_streams.py` with:
   - `_decode_string_operand(operand: pikepdf.String) ->
     tuple[str, Literal["literal", "hex"]]` — encoding-aware
     decode (PDFDocEncoding for literals, cp1252 for hex).
   - `_encode_string_operand(text: str, encoding: Literal[
     "literal", "hex"]) -> pikepdf.String` — preserves the
     original encoding choice.
   - `apply_token_map_to_page(page: pikepdf.Page, mapping:
     TokenMap) -> tuple[Replacement, ...]` — `parse_content_
     stream`, walk for `Tj` / `TJ` / `'` / `"` operators, replace
     operands, `unparse_content_stream`, replace the page's
     content stream via `Pdf.make_stream`.
2. Create `src/aeat/adapters/inbound/sanitizer/test_streams.py`:
   - Synthesise three in-test PDFs (literal-only, hex-only,
     mixed) with known cleartext. Define a `TokenMap` with one
     `arbitrary` entry. Run `apply_token_map_to_page`. Assert
     no instance of the cleartext anywhere in the page's
     serialised content stream; assert one or more
     `Replacement` rows with the correct `encoding` field.
   - Edge case: the cleartext spans multiple `Tj` operands
     (e.g. AEAT's column-split layout). Document the failure
     mode if span-replace is not implemented; raise an explicit
     warning rather than silently miss.
3. Run the test.
4. Commit: `feat(sanitizer): operand-aware content-stream rewrite
   (#239)`.

### Phase 6 — Pipeline orchestrator + refuse guards

Wire phases 2-5 together with the order of operations from the ADR.

1. Create `src/aeat/adapters/inbound/sanitizer/_pipeline.py` with `sanitize_pdf` —
   the public entry point. Implements the 8-step order from the
   ADR. Carries `refuse_if_already_sanitized` and the
   `drop_*` / `scrub_*` flags through.
2. Create `src/aeat/adapters/inbound/sanitizer/fixtures.py` (stub) with
   `SANITIZED_SHAS: frozenset[str] = frozenset()`. Populated
   later as fixtures land.
3. Create `src/aeat/adapters/inbound/sanitizer/test_pipeline.py`:
   - Happy path on a synthesised PDF: assert
     `SanitizationResult.replacements_applied` non-empty and the
     output is byte-stable across two calls.
   - Refuse-if-signed: synthesise a PDF with `SigFlags=3`; assert
     `SignaturePresentError`.
   - Refuse-if-already-sanitised: pre-populate
     `SANITIZED_SHAS` with the source SHA; assert
     `AlreadySanitizedError`. With
     `refuse_if_already_sanitized=False`, assert the call
     succeeds.
   - Public re-exports test: import every public symbol via
     `from aeat.adapters.inbound.sanitizer import ...`.
4. Update `src/aeat/adapters/inbound/sanitizer/__init__.py` to re-export the
   public surface.
5. Run the test.
6. Commit: `feat(sanitizer): pipeline orchestrator + refuse guards
   (#239)`.

### Phase 7 — CLI bridge

`aeat sanitize` group with `pdf`, `prepare-map`, `verify`, `check`
verbs.

1. Create `src/aeat/entrypoints/cli/sanitize/__init__.py` registering the
   group on the root CLI.
2. Verb implementations under `_pdf.py`, `_prepare_map.py`,
   `_verify.py`, `_check.py`.
3. Forbidden-flag guard: reject any flag literally named
   `--write`, `--submit`, `--send`, `--enviar`, `--presentar`
   etc. Same pattern as `aeat filing reconcile`.
4. Create `src/aeat/entrypoints/cli/sanitize/test_cli.py`:
   - `aeat sanitize pdf --help` lists the four verbs.
   - `aeat sanitize verify` against a fixture with a known
     `real:` value the operator forgot to add to the mapping
     exits non-zero with a clear error.
   - `aeat sanitize prepare-map` against a captured PDF
     produces YAML with `synthetic:` filled and `real:` blank.
   - The CLI is read-only on AEAT (no auth, no http calls,
     no env-var reads under `AEAT_*`).
5. Run the test.
6. Commit: `feat(cli): aeat sanitize bridge for the sanitizer
   subpackage (#239)`.

### Phase 8 — Adversarial absence + round-trip + no-write-surface

The load-bearing security gates.

1. Create `src/aeat/adapters/inbound/sanitizer/test_adversarial_absence.py`:
   - Iterates every committed fixture under
     `tests/fixtures/justificantes/`. For each, loads the
     committed mapping (the fixture sidecar JSON). For every
     `real:` value, asserts `real_value not in raw_pdf_bytes
     (fixture)` AND `real_value not in pdftotext_output
     (fixture)`. Skips cleanly if no fixtures yet committed.
2. Create `src/aeat/adapters/inbound/sanitizer/test_round_trip.py`:
   - Iterates every committed fixture. Asserts
     `parse_justificante(fixture)` returns a valid
     `Justificante` whose `nif`, `csv`, `presented_at` match
     the synthetic mapping. Skips cleanly if no fixtures.
3. Create `src/aeat/adapters/inbound/sanitizer/test_no_write_surface.py`:
   - Greps every `.py` under `src/aeat/adapters/inbound/sanitizer/` and
     `src/aeat/entrypoints/cli/sanitize/` for the forbidden mutation verbs
     (`submit`, `send`, `commit`, `enviar`, `presentar`,
     `firmar`, `radicar`, `remitir`, `modificar`, `anular`,
     `cancelar`, `rechazar`). Whitelist needed for `commit_id`
     etc. — be explicit and narrow.
4. Run all three tests.
5. Commit: `test(sanitizer): adversarial-absence + round-trip +
   no-write-surface guards (#239)`.

### Phase 9 — Integration into `aeat-verify` W1 P4

Sanitise the three real Modelo 100 IRPF captures and commit them
as the first project fixtures.

1. Run `aeat sanitize prepare-map
   scratch/recon-corpus/20260424T184450Z/irpf-2021/justificante.pdf
   --output scratch/.../sanitizer-mapping-2021.yaml`. Operator
   fills in `real:` cleartext locally. Repeat for 2022 and 2023.
2. Run `aeat sanitize pdf` against each capture, producing
   `tests/fixtures/justificantes/100/2021-A.pdf` plus the
   sidecar report JSON. Repeat 2022, 2023.
3. Update `src/aeat/adapters/inbound/sanitizer/fixtures.py`'s `SANITIZED_SHAS`
   with the SHA-256 of each committed sanitised PDF.
4. Run the full sanitiser test suite. Expect:
   - `test_adversarial_absence.py` green (no real value leaks).
   - `test_round_trip.py` green (synthetic NIF / CSV /
     presented_at parse correctly).
   - `test_no_write_surface.py` green.
5. Update the parent `aeat-verify` plan's W1 P4 status from
   `pending` to `done`. Update PR2 (sanitiser tooling) status to
   `done`. Add `[[2026-04-25-pdf-sanitizer-plan]]` to the parent
   plan's `related:` frontmatter.
6. Commit: `chore(fixtures): sanitised modelo 100 IRPF
   2021/2022/2023 fixtures + integration into aeat-verify W1 P4
   (#239)`.

## Parallelization

- Phases run **strictly sequentially.** Each phase has a non-
  trivial dependency on its predecessor (records → save flags →
  metadata → dynamic-strip → content-rewrite → orchestrator →
  CLI → adversarial gates → integration). Parallelising would
  invite drift.
- Within a phase, individual file/test creations can interleave
  but a single executor agent owns the whole phase. Multi-agent
  parallelism within a phase produces merge thrash on the small
  source files.
- Code review is strictly serial: each phase's code review must
  pass before the next phase starts. Critical / High issues
  resolve before progressing.

## Verification

The plan succeeds when, after phase 9 commits:

- `uv run pytest src/aeat/adapters/inbound/sanitizer/ -m unit` is green
  end-to-end.
- `uv run pytest src/aeat/entrypoints/cli/sanitize/ -m unit` is green
  end-to-end.
- The three Modelo 100 IRPF fixtures live under
  `tests/fixtures/justificantes/100/` with their sidecar JSON,
  and their SHA-256 hashes appear in
  `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS`.
- The parent `aeat-verify` plan's W1 P4 row reads `done` and
  PR2 reads `done`.
- `aeat sanitize verify` exits 0 against every committed fixture
  (using the locally-stored real-value mapping).
- A code-review pass (vaultspec-code-reviewer) returns no
  Critical / High issues; any Medium / Low findings have
  documented dispositions in the phase summary record.

Honest caveats to document in the phase summary:

- The adversarial absence test scans for cleartext present in the
  TokenMap. It does not guarantee absence of PII the operator
  forgot to map. Mitigation: `aeat sanitize prepare-map`
  pre-fills every category from the parser output, leaving only
  the `real:` cleartext to fill.
- The no-write-surface grep is a whitelist of substrings; a
  misspelled or paraphrased mutation verb would slip through.
  Mitigation: a code reviewer pass checks the forbidden-verb
  list against any new public function name.
- The fixture sidecar JSON ships the synthetic values; the real
  values stay in the operator's local `scratch/`. A future
  contributor wishing to re-sanitise a fixture from the original
  PDF must obtain the original capture (gitignored) AND the
  per-capture mapping (gitignored). This is by design.
