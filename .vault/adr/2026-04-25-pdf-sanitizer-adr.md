---
tags:
  - '#adr'
  - '#pdf-sanitizer'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-pdf-sanitizer-research]]"
  - "[[2026-04-25-aeat-verify-research]]"
  - "[[2026-04-25-aeat-verify-adr]]"
  - "[[2026-04-25-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-reference]]"
---



# `pdf-sanitizer` adr: `pdf-sanitizer-architecture-and-api` | (**status:** `accepted`)

## Problem Statement

The `aeat-verify` ADR locked phase 4 of the per-modelo verify loop —
"sanitise a real AEAT PDF, commit the result as a fixture" — to a
`pikepdf`-based token-replacement helper at `scripts/sanitize_
justificante.py`. That shape is wrong for three reasons:

1. A loose script is not testable, not reusable, not refactor-safe,
   and not auditable. PII redaction is the most security-sensitive
   transformation the project performs; it must live in a typed,
   tested, namespaced module with a stable public API.
2. The parent ADR's surface enumeration covers only 3 of the 20 PII
   surfaces a real AEAT justificante carries (per the prior-art
   research). The remainder are CVE-class historical failure modes
   (Manafort, NSA Russia memo, AstraZeneca) and must be touched
   defensively even on captures where the surface is empty today.
3. The parent ADR claims "deterministic pure function" without
   naming the `pikepdf.Pdf.save` flags that actually deliver
   determinism. Without those flags, "fixture diff review" is
   non-actionable because the byte stream drifts on every save.

This ADR promotes the sanitiser to a first-class subpackage,
`aeat.adapters.inbound.sanitizer`, with a typed pydantic v2 API, a CLI bridge, an
explicit threat model, and a security-grade test suite. It overrides
the parent ADR's "Sanitiser" section in full.

## Considerations

Inputs come from the linked research and the empirical capture
characterisation. Salient findings:

- **Library choice is licence-dominated, not capability-dominated.**
  `PyMuPDF` is the only library with a redaction-shaped API out of
  the box; it is AGPL-3.0 and incompatible with the project's
  Apache-2.0 distribution without a paid commercial relicence. Hard
  rule-out. `pikepdf` (MPL-2.0, QPDF-bundled, cp313 wheels for every
  developer + CI platform) is the only remaining viable primary.
  `pypdf` (BSD-3) survives as the fallback. `pdfrw` is unmaintained
  since 2017 and shells out to qpdf for compressed streams.
- **Strategy is forced by the deep extractor's contract.** Phase 5
  of the parent loop runs a per-modelo casilla extractor against the
  sanitised fixture. Blackout-redaction (`PyMuPDF.apply_redactions`)
  deletes text from the extraction layer — the extractor stops
  parsing. Synthetic re-render loses every layout cue the extractor
  uses for column-split detection. Token replacement preserving the
  original `Tm` matrices is the only strategy that lets the same
  extractor exercise both the live PDF and the committed fixture.
- **The threat model is passive, not active.** We are defending
  against (a) a code reviewer scanning a PR diff, (b) an attacker
  cloning the public repo and running `pdftotext`/`pdfgrep`/
  `pdfdetach`/`exiftool` over fixtures, (c) a contributor reusing a
  fixture in a public demo. We are not defending against an
  adversary with build-pipeline access. This bounds the scope: no
  cryptographic erasure proofs, no post-quantum considerations, no
  detection layer.
- **Detection is out of scope.** Microsoft Presidio is the canonical
  PII-detection framework. It pulls spaCy + tesseract + heavy NER
  models. We do not need detection because we have a bounded,
  declarative input mapping per capture. The operator names the real
  values; the sanitiser performs the transformation. Adding
  detection would be feature creep that hides bugs (e.g. NER misses
  silently produce leaks).
- **Determinism is non-negotiable.** Without byte-stable output, we
  cannot assert "the sanitised fixture I committed matches the
  sanitiser's output" in CI, and PR review of fixture diffs becomes
  non-actionable. The research names the exact `pikepdf.Pdf.save`
  flag set that produces byte-stable output across runs.
- **Token-map sourcing is per-capture, not project-default.**
  Real-NIF-bearing maps must never be committed to git. A
  per-capture YAML at `scratch/.../sanitizer-mapping.yaml`
  (gitignored) keeps the cleartext exclusively in the operator's
  local working tree.

## Constraints

Inherited from the parent `aeat-verify` ADR and the project
mandate, explicitly re-affirmed:

- **Apache-2.0 redistribution licence.** Every runtime dependency
  must be permissively licensed. AGPL is a non-starter without
  explicit user sign-off and a commercial relicence.
- **Strict-frozen pydantic v2.** Every record `frozen=True`,
  `extra="forbid"`, `strict=True`. `StrEnum` for closed enumerations.
  `Decimal` for monetary values. UTC tz-aware datetimes. The
  `mode: Literal["read"]` boundary marker from the parent ADR is
  *not* applicable here (the sanitiser is a transformation, not a
  boundary record); the strict-frozen discipline still is.
- **Read-only mandate (parent ADR).** The sanitiser does not
  authenticate, does not call AEAT, does not read or write live
  state. Its inputs are bytes; its output is bytes. Layer 3 of the
  parent's write-guard ("`test_no_write_surface.py` per
  subpackage") applies — the new subpackage ships a test that
  greps for forbidden mutation verbs in the public API surface.
- **No mocks on security-load-bearing tests.** The adversarial
  absence test runs against the real (sanitised) bytes; the
  determinism test runs the real sanitiser twice. The round-trip
  parse test runs the real `parse_justificante` against the
  sanitised PDF. Mocking any of these collapses the test to
  tautology.
- **Cleartext PII is never logged, never persisted in the
  `SanitizationResult`, never written to the report JSON, never
  emitted to the CLI's stdout/stderr.** Replacements record
  `real_sha256`, never the cleartext. The `TokenMap.real` field is
  `pydantic.SecretStr` so accidental `repr()` does not leak.
- **PDF/A conformance is not preserved.** Rewriting `Tj` operands
  necessarily breaks PDF/A-1B's content/XMP alignment. The
  sanitiser drops the `pdfaid:*` claim from XMP rather than leaving
  a false claim.
- **Determinism is enforced at the API surface.** The public
  `sanitize_pdf` is a pure function: `(bytes, TokenMap) -> bytes` is
  byte-for-byte stable across runs and across processes. No
  filesystem side effects, no `time.now()` reads, no env-var reads
  inside the function body.

## Implementation

### Subpackage layout

`src/aeat/adapters/inbound/sanitizer/` ships:

- `__init__.py` — public re-exports: `sanitize_pdf`, `TokenMap`,
  `SanitizationResult`, `Replacement`, `ScrubbedSurface`,
  `SanitizationWarning`, `DeterminismFlags`, `SanitizationError` and
  its subclasses.
- `_records.py` — strict-frozen pydantic v2 records (`TokenMap`
  family, `Replacement`, `SanitizationResult`, `DeterminismFlags`,
  `SanitizationWarning`, `ScrubbedSurface`).
- `_pipeline.py` — top-level orchestrator implementing the 8-step
  order of operations from the research.
- `_dynamic.py` — strip dynamic surfaces (attachments, JS,
  annotations, OpenAction/AA, OCG, AcroForm).
- `_metadata.py` — DocInfo + XMP scrub.
- `_streams.py` — content-stream walk + operand-aware token replace
  (literal + hex + ActualText).
- `_structtree.py` — StructTree drop / scrub.
- `_determinism.py` — the named save flags + verification helpers.
- `_errors.py` — `SanitizationError` hierarchy inheriting
  `aeat.core.errors.AeatError`.
- `_logging.py` (or use `aeat.core.logging.get_logger(__name__)`
  directly) — never logs cleartext, only `real_sha256` + synthetic.
- `test_records.py`, `test_pipeline.py`, `test_streams.py`,
  `test_metadata.py`, `test_determinism.py`,
  `test_no_write_surface.py`, `test_adversarial_absence.py`,
  `test_round_trip.py` — colocated unit tests.
- CLI bridge under `src/aeat/entrypoints/cli/sanitize/__init__.py` registering
  `aeat sanitize {pdf, prepare-map, verify, check}`.

### Public API (locked)

```
sanitize_pdf(
    source: bytes | Path,
    mapping: TokenMap,
    *,
    drop_attachments: bool = True,
    drop_javascript: bool = True,
    drop_annotations: bool = True,
    drop_outlines: bool = True,
    drop_optional_content_groups: bool = True,
    drop_struct_tree: bool = True,
    drop_acroform: bool = False,
    scrub_docinfo: bool = True,
    scrub_xmp: bool = True,
    scrub_xmp_strategy: Literal["delete", "rewrite"] = "delete",
    refuse_if_already_sanitized: bool = True,
) -> SanitizationResult
```

The function is a pure transformation. It accepts `bytes` or a
`pathlib.Path` whose contents are read once at the top of the
function; it returns a `SanitizationResult` whose `output_bytes`
field carries the sanitised PDF. The CLI shell writes `output_bytes`
to disk; the library never does.

### `TokenMap` — declarative input

```
class _ReplacementBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    real: SecretStr
    synthetic: str
    surface_label: str

class NifReplacement(_ReplacementBase):
    @field_validator("synthetic")
    @classmethod
    def _validate_nif_shape(cls, v: str) -> str: ...

# similar: NameReplacement, AddressReplacement, ExpedienteReplacement,
# CsvReplacement, NrcReplacement, IbanReplacement, ImporteReplacement,
# ArbitraryReplacement

class TokenMap(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    nif: tuple[NifReplacement, ...] = ()
    name: tuple[NameReplacement, ...] = ()
    address: tuple[AddressReplacement, ...] = ()
    expediente: tuple[ExpedienteReplacement, ...] = ()
    csv: tuple[CsvReplacement, ...] = ()
    nrc: tuple[NrcReplacement, ...] = ()
    iban: tuple[IbanReplacement, ...] = ()
    importe: tuple[ImporteReplacement, ...] = ()
    arbitrary: tuple[ArbitraryReplacement, ...] = ()
```

`SecretStr` ensures that `repr(token_map)` never emits the
cleartext — even into a debugger session or a log line.
Per-subclass synthetic-shape validators run the same checksum / ISO
13616 / Mod-23 logic the project already uses for live values, so
the synthetic round-trips through the production validators.

### `SanitizationResult` — typed output

```
class SanitizationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    output_bytes: bytes
    source_sha256: str
    output_sha256: str
    source_size_bytes: int
    output_size_bytes: int
    sanitizer_version: str
    determinism_flags: DeterminismFlags
    replacements_applied: tuple[Replacement, ...]
    surfaces_scrubbed: tuple[ScrubbedSurface, ...]
    warnings: tuple[SanitizationWarning, ...]
```

`Replacement` carries `real_sha256` (NEVER the cleartext),
`synthetic`, `surface` (`Literal["docinfo_title", "docinfo_subject",
"xmp_dc_title", "content_stream", "annotation_contents",
"structtree_actualtext", ...]`), `surface_index` (e.g.
`(page_index, instruction_index)`), and `encoding` (`Literal[
"literal", "hex", "actualtext", "docinfo_string"]`).

`ScrubbedSurface` carries `surface` and `count`.
`SanitizationWarning` carries a `Literal` `code` and a `detail`
string. Closed enumeration over: `unknown_surface_present`,
`encoding_inferred`, `structtree_dropped_lossy`,
`pdfa_claim_invalidated`, `digital_signature_present_refusing`,
`incremental_update_history_consolidated`,
`source_sha256_already_in_known_sanitized_set`.

### Order of operations (locked)

The 8-step pipeline from the research, locked here verbatim:

1. **Open** the source bytes via `pikepdf.open(io.BytesIO(...))`.
   Refuse if `Root.AcroForm.SigFlags` is set or any signature dict
   is present (raise `SignaturePresentError`). Refuse if
   `source_sha256` is in the known-sanitised set unless
   `refuse_if_already_sanitized=False` (raise
   `AlreadySanitizedError`).
2. **Strip dynamic surfaces** (attachments, JS, annotations,
   OpenAction/AA, OCG, AcroForm field values). Recorded as
   `ScrubbedSurface` rows.
3. **Drop page thumbnails.** One `ScrubbedSurface` row.
4. **Drop bookmarks / outlines / page labels.** Recorded.
5. **Drop StructTreeRoot.** Recorded as a single
   `structtree_dropped_lossy` warning + a `ScrubbedSurface` row,
   because the StructTree may carry accessibility text the
   token-replace would have caught.
6. **Rewrite content streams.** Walk every page,
   `parse_content_stream`, match `Tj` / `TJ` / `'` / `"` operands
   against the token map (handling literal + hex encodings + the
   PDFDocEncoding / cp1252 distinction), reserialise via
   `unparse_content_stream`. Each replacement records a
   `Replacement` row.
7. **Scrub static metadata.** `del pdf.docinfo`,
   `del pdf.Root.Metadata`. Recorded.
8. **Save** with `pdf.save(target, deterministic_id=True,
   compress_streams=True, object_stream_mode=
   ObjectStreamMode.preserve, linearize=False,
   recompress_flate=False, static_id=False)`. Captured into the
   `DeterminismFlags` record.

### CLI bridge

`aeat sanitize` group registered under `src/aeat/entrypoints/cli/sanitize/`,
verbs:

- `aeat sanitize pdf <input> --mapping <path> --output <path>
  [--report <path>] [--allow-already-sanitized]`. Writes the
  output PDF and a sidecar report JSON
  (`SanitizationResult.model_dump_json()`).
- `aeat sanitize prepare-map <input> --output <yaml>`. Runs
  `parse_justificante` against the input, scaffolds a YAML with
  `synthetic:` pre-filled and `real:` left blank (operator fills
  in cleartext locally; YAML stays gitignored).
- `aeat sanitize verify <output> --against <mapping>`. Adversarial
  test: assert no `real:` value occurs anywhere in the output
  bytes. Exits non-zero on any hit.
- `aeat sanitize check <output>`. Structural-integrity check:
  re-opens with `pikepdf`, asserts no warnings, runs
  `parse_justificante` and asserts a valid `Justificante` parse.

The CLI is read-only on AEAT (parent ADR layer 5 inherited): it
never authenticates, never calls AEAT, never reads tokens from
`AEAT_*` env vars.

### Refuse-if-already-sanitised guard

The package ships `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS: frozenset[
str]` — the set of SHA-256 hashes of every committed fixture under
`tests/fixtures/justificantes/`. The pipeline computes the source
SHA at step 1 and refuses with `AlreadySanitizedError` if the
source is already in the set. This makes "accidentally re-sanitise
a fixture" a hard error rather than a silent no-op.

### Test strategy (locked)

Eight test files, all `@pytest.mark.unit`:

1. `test_records.py` — pydantic strict-frozen behaviour, validator
   coverage, `SecretStr` repr-leak guard.
2. `test_pipeline.py` — happy path, refuse-if-signed, refuse-if-
   already-sanitised, `drop_*=False` flag combinations.
3. `test_streams.py` — operand-aware replace: literal-only PDF
   (synthesised in-test, no fixture), hex-only PDF, mixed.
4. `test_metadata.py` — DocInfo + XMP scrub, PDF/A claim removal.
5. `test_determinism.py` — sanitise-twice byte equality on a
   tiny synthesised PDF.
6. `test_no_write_surface.py` — grep test over the public API for
   forbidden verbs (`submit`, `send`, `commit`, `enviar`,
   `presentar`, `firmar`, `radicar`, `remitir`, `modificar`,
   `anular`, `cancelar`, `rechazar`).
7. `test_adversarial_absence.py` — for every committed fixture
   under `tests/fixtures/justificantes/` and every entry in the
   sanitised mapping shipped with that fixture, assert
   `real_value not in raw_pdf_bytes` AND `real_value not in
   pdftotext_output`.
8. `test_round_trip.py` — for every committed fixture, assert
   `parse_justificante(fixture)` returns a valid `Justificante`
   whose `nif`, `csv`, `presented_at` match the synthetic mapping
   values.

Tests 7 and 8 are the load-bearing security gates. They run on
every CI build, no scratch dependency.

### Dependencies

`pikepdf>=10.0.0` becomes a hard runtime dependency of the project,
not an extras-marker. Justification: the sanitiser participates in
the test fixture pipeline, CI must execute the adversarial absence
test, and `pikepdf` wheels are pre-built for every developer + CI
platform (~6 MB Linux, ~12 MB Windows). The cost is bounded; the
benefit is that `pip install aeat` produces a working sanitiser.

`pyproject.toml` updates the `dependencies` array to include
`pikepdf>=10.0.0` and the lockfile picks up the transitive lxml
(already present via other deps; verify on first pin pass).

## Rationale

- **Why a subpackage, not a script.** PII redaction is the
  highest-blast-radius transformation in the codebase. A loose
  script has no ownership, no test enforcement, no refactor safety,
  and no CLI — every invariant must be re-derived ad-hoc on each
  call site. A subpackage with strict-typed records, locked public
  API, colocated unit tests, and a CLI bridge makes the security
  posture observable and the regression surface explicit.
- **Why pikepdf over PyMuPDF.** Licence (MPL-2.0 vs AGPL-3.0). The
  AGPL section 13 obligation propagates to every consumer of an
  AGPL-linked artefact; combining it with the project's Apache-2.0
  redistribution would force every downstream user into AGPL
  source-disclosure. PyMuPDF's redaction-shaped API is also wrong
  for our use case (deletes text from extraction) — but the licence
  is what makes the rule-out hard.
- **Why token-replace over redact-blackout or re-render.** The
  parent ADR's phase 5 deep-extractor regression suite must run
  against the committed fixture. Blackout deletes text from the
  extraction layer; re-render loses layout cues. Only token-replace
  preserves the pixel-equivalent shape of AEAT's real PDF while
  swapping the cleartext.
- **Why declarative TokenMap, not detection.** Detection (Presidio
  / spaCy NER) introduces a probabilistic layer that can silently
  miss a token. Declarative replacement is auditable: every
  replacement is a row in `replacements_applied`, every miss is a
  test failure in `test_adversarial_absence.py`. We trade flexibility
  (operator must enumerate the values) for verifiability (every
  cleartext-to-synthetic edge is enumerated).
- **Why per-capture YAML, not project-default.** A project-default
  mapping under `aeat.adapters.inbound.sanitizer.fixtures.DEFAULT_MAPPING` would
  encode one user's identity into git history. Per-capture YAML
  under `scratch/.../sanitizer-mapping.yaml` (gitignored) keeps
  cleartext exclusively in the operator's local tree and
  structurally prevents accidental commit.
- **Why determinism flags named in this ADR.** The parent ADR
  claims "deterministic pure function" without naming the flags.
  In practice, `pikepdf.Pdf.save` defaults are non-deterministic
  (timestamp-seeded `/ID`, `recompress_flate=True`). Without the
  named flag set, "fixture diff is byte-stable across reruns" is
  not a property of the system — it just happens to hold by
  accident on some runs. Naming the flags makes determinism a
  testable property.
- **Why the 8-step order is locked.** The order matters: dynamic
  surfaces (JS, attachments, OpenAction) before content rewrite,
  because dynamic actions can rewrite content streams (CVE class).
  Content rewrite before metadata scrub, because some XMP-write
  paths in pikepdf re-stamp metadata if they detect a change. Save
  last with the named flags. Every other ordering opens a known
  failure class.
- **Why we drop the StructTreeRoot wholesale.** The Tagged-PDF
  StructTree carries accessibility text (`/ActualText`, `/Alt`,
  `/E`) that may contain PII not captured by the body Tj walk —
  this is the AstraZeneca contract failure mode. Walking and
  scrubbing is more surgical, but the failure consequences are
  asymmetric: a missed scrub is a leak, a dropped tree is just
  loss of accessibility metadata in a test fixture nobody screen-
  reads. Drop > scrub.
- **Why we refuse signed PDFs.** Modifying a digitally-signed PDF
  silently invalidates the signature. The parent ADR's "no writes"
  spirit extends to "no silent integrity-breaking writes". If a
  future modelo's justificante carries a signature, the sanitiser
  refuses; the operator must escalate to human review.

## Consequences

- **New runtime dependency (`pikepdf>=10.0.0`).** Adds ~6-12 MB to
  the install footprint per platform; pinned wheels exist for every
  CI / dev platform; no system QPDF needed.
- **New CLI surface (`aeat sanitize`).** Verified-clean against the
  30 existing CLI groups; no naming collision.
- **New module (`src/aeat/adapters/inbound/sanitizer/`).** ~10 source files,
  ~8 colocated test files, plus the CLI bridge. Subject to the
  parent ADR's per-subpackage write-guard (`test_no_write_surface.py`)
  and the parent's grep-guard pattern (forbidden mutation verbs in
  the public API).
- **Per-capture YAML mapping.** Operators authoring a fixture must
  scaffold a mapping via `aeat sanitize prepare-map`, fill in the
  cleartext locally, and run `aeat sanitize pdf` to produce the
  fixture. The YAML stays under `scratch/` (gitignored). This is
  one extra step in the per-modelo loop's phase 4.
- **Adversarial absence test runs on every CI build.** The cost is
  one PDF re-open + a `pdftotext` call per fixture; sub-second per
  fixture. Acceptable.
- **PDF/A-1B conformance is dropped on sanitised fixtures.** The
  parent ADR's parser regression tests do not assert PDF/A
  conformance, so this is a no-op for the test suite. If a future
  consumer needs PDF/A-conformant fixtures, that's a separate ADR.
- **The parent `aeat-verify` ADR's "Sanitiser" section is
  superseded.** The parent ADR's research-input arrow now flows
  through this ADR's research / ADR / plan triad. The parent plan
  must be amended to reference this sub-feature in PR2 and W1 P4.
- **Determinism is enforceable but not free.** The named save
  flags marginally reduce compression ratio (a few KB per fixture).
  Negligible.
- **The sanitiser's failure modes are loud.** A `pikepdf` parse
  failure on the source bubbles up as `SanitizerSourceParseError`;
  a missed token in `replacements_applied` causes the absence
  test to fail; a determinism regression causes the byte-stable
  test to fail. Silent-leak failure modes are bounded to: (a) PII
  in a surface this ADR does not enumerate (mitigated by the
  20-row PII-surface table from the research), (b) PII that the
  operator did not include in the TokenMap (mitigated by the
  adversarial absence test which scans the *whole* PDF for the
  *whole* TokenMap, including arbitrary entries the operator can
  add for ad-hoc strings).
