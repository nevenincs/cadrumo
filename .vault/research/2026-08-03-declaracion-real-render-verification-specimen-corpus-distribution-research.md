---
tags:
  - '#research'
  - '#declaracion-real-render-verification'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ff87c2cbe9aef212c7df52a305ec46a4fb9143a2bccd3c84eaa504dca82a15ef'
related:
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
---

# `declaracion-real-render-verification` research: `specimen corpus distribution measurements`

Whether the `declaracion_pdf` verification specimen corpus should ship to installed
users turns on four measurable questions: what the corpus physically is, which code
actually consumes it, what the gate reading it asserts, and whether that assertion can
yield any information on an installed build.

All counts below were measured on 2026-08-03 against `HEAD` of `main` in this
worktree, by direct file walk and by `tomllib` parse of the registry, never inferred
from a directory listing. Re-derive before relying on any of them. No test suite was
run: the box was saturated and the dispatch prohibited pytest, so every behavioural
claim is a static reading of the code, not an observation of it executing.

## Findings

### The gated specimen set is entirely synthetic; zero `real_corpus` artefacts sit in it

All 60 sidecarred specimens under `src/cadrumo/tests/fixtures/justificantes/<modelo>/`
declare `"provenance": "synthetic_generated"`, confirmed both in the working tree and
at `HEAD`. None declares `real_corpus`. Nine declare `"role": "parser_anchor"`, and
those nine span exactly Modelos 100 (3), 111 (4), 190 (1) and 390 (1).

Three further PDFs sit unsidecarred at the `justificantes/` root
(`modelo_100_2025A.pdf`, `modelo_130_2026Q1.pdf`, `modelo_303_2026Q1.pdf`), outside the
per-modelo directories the gate reads and therefore outside the gated set.

The corpus is 63 PDFs. The directory totals 1010 KiB; the PDF bytes alone are 272 KiB,
the remainder being JSON sidecars.

This is the measurement that dissolves the licensing and redaction objection: nothing
in the gated set is a sanitised real AEAT document, so no taxpayer identity and no AEAT
document rights ride along with it.

A staleness worth flagging rather than silently correcting. Both the governing ADR and
the static route audit under this feature describe "nine `real_corpus` specimens"
spanning those same four modelos. That is no longer true of the tree: the nine
artefacts at those coordinates declare `synthetic_generated` and carry
`role = parser_anchor`. The ADR itself records that specimens carrying unredacted
taxpayer identity were withdrawn and replaced with synthetic ones, and
`src/cadrumo/adapters/inbound/sanitizer/tests/test_residual_identity_absence.py:137`
states the justificante directory "held no real specimen at all" after that
replacement. The count of nine and the modelo set survive in both documents while the
provenance they attach to does not. Which of the two axes each document meant is not
recoverable from the documents themselves.

### The four committed `real_corpus` artefacts live outside this corpus and are already wheel-excluded

Tree-wide, exactly four committed artefacts declare `"provenance": "real_corpus"`, all
under `src/cadrumo/application/ledger/tests/_evidence_corpus/`: two Wikimedia Commons
invoice images, a scanned Commons invoice, and a ZUGFeRD EN16931 sample. They are
third-party licensed material (the Commons sidecars carry `"licence": "Public domain"`
with source URLs) belonging to the ledger evidence corpus, not to `declaracion_pdf`
verification. The existing `src/cadrumo/**/tests/**` wheel exclusion already covers
them.

`src/cadrumo/adapters/inbound/sanitizer/tests/test_residual_identity_absence.py:131`
discovers real-provenance artefacts by walking the whole package and reading each
sidecar, so that scope is data-driven rather than directory-scoped: a future
`real_corpus` artefact enrols in the identity scan wherever it lands.

### A second, distinct corpus carries AEAT-published facsimiles

`src/cadrumo/tests/fixtures/manual_annexes/` holds 7 artefacts declaring
`"provenance": "aeat_published_facsimile"` for Modelos 303 and 390, totalling 1652 KiB.
This is a third provenance class and a different directory from the one the specimen
gate reads. It is consumed by
`src/cadrumo/adapters/inbound/declaracion/tests/test_real_render_extraction_coverage.py`,
not by the registry-build gate. Any distribution question therefore has two candidate
scopes rather than one, and the facsimile scope carries the AEAT document-rights
question the synthetic scope does not.

### The consumer set is six modules, but the root is derived ONCE and threaded as a parameter

This was measured rather than assumed, because an ADR scoped to "the gate" would be
wrong if the root were derived independently at several sites. It is not. The
production sites, established by semantic search and confirmed by a targeted `rg` over
`src/cadrumo/domain/calculations/registry/` excluding `tests/`:

- `_source_evidence_fingerprint.py:85` declares `derive_justificante_corpus_candidate`,
  the sole derivation. Its own `_source_evidence_roots` calls it at `:155` to add the
  corpus to the cache-key fingerprint roots.
- `_validate.py:108` is the only other call to that function. `:104` honours an
  explicitly supplied `justificante_corpus_root` instead, `:136` exposes the resolved
  root, `:157` folds it into the cache key, and `:117` and `:281` pass it onward.
- `_validate_revision_sections.py:80`, `:198`, `:249` and `:288` thread the parameter
  through without deriving anything.
- `_validate_record_sections.py:272` receives it and `:303` gates on it being
  non-`None`, dispatching to both checks at `:304` and `:305`.
- `_validate_extraction_profiles.py:14` and `:50` are the two terminal consumers,
  joining `corpus_root / <modelo_id>` at `:35` and `:82`.

So the shape is one derivation and a parameter-threaded chain through five further
modules. `_validate_revision_sections.py` is part of that chain and was absent from the
briefed site list; conversely no site outside this chain derives the path. The earlier
duplicate-derivation pattern this campaign found (the fingerprint path and the validate
path each guessing the repo-shaped location separately) is the condition the uncommitted
`derive_justificante_corpus_candidate` work closed, and the module docstring at
`_source_evidence_fingerprint.py:3` claims exactly that: "the single checkout-gated
derivation ... shared by ... the specimen/round-trip gates ... and this module's own
fingerprint collection."

A decision scoped to the gate is therefore correct on the current tree, provided it
names the derivation function as the binding site rather than the gate.

### One shipped module already consumes a precompiled projection of the corpus

`src/cadrumo/adapters/inbound/sanitizer/fixtures.py` is NOT under a `tests/` directory,
so it matches none of the four wheel exclusion patterns and ships to installed users. It
carries `SANITIZED_SHAS` at `:32`, a frozen set of the SHA-256 digest of every committed
specimen including the three top-level PDFs, and it is load-bearing for a production
guard: `sanitize_pdf` raises `AlreadySanitizedError` when handed bytes whose digest is
in the set.

This refutes the flat claim that the specimen corpus serves no installed consumer. What
it serves is a light precompiled projection, not the bytes. The module docstring at
`:26` records that hand maintenance of that list already failed once (32 of 41 entries
matched no committed fixture and 53 of 62 fixtures were absent, so the guard covered
nine fixtures while reading as though it covered all of them), and it is now regenerated
and pinned against drift by
`src/cadrumo/adapters/inbound/sanitizer/tests/test_sanitized_sha_catalogue.py`.

The corpus therefore already conforms to the project's precompile boundary: the heavy
artefact stays out of the wheel and a light reviewable derivative ships under a
drift gate.

### Only one of the two corpus-dependent checks is live, and its verdict is frozen at build time

`validate_declaracion_pdf_round_trip_gate`
(`src/cadrumo/domain/calculations/registry/_validate_extraction_profiles.py:46`) returns
before reaching `corpus_root` whenever `corpus_round_trip_verified` is set. Parsing the
registry with `tomllib`, all 29 `declaracion_pdf` profiles set it `true` and all 29
carry a `verification_source` (uniformly `synthetic_from_aeat_published_text`), so this
check never consults the corpus for any profile in the current registry.

`validate_declaracion_pdf_specimen_gate` (`:10` in the same module) is therefore the
only live consumer. It skips when `provisional_pending_specimen` is set (1 of 29
profiles) and otherwise requires at least one `*.pdf` under `corpus_root / <modelo_id>`.
All 20 modelos carrying `declaracion_pdf` profiles have a populated specimen directory,
so it passes for all 28 live profiles today.

Both inputs to that verdict, the registry TOML flags and the presence of a per-modelo
specimen directory, are frozen in a release artefact. The verdict on an installed build
is therefore fully determined at build time and identical for every user of that
release. The check's subject is registry-authoring discipline: its docstring frames the
failure it prevents as an author shipping label patterns "not round-trip verified
against a corpus PDF", and its remedy instructs the author to "add a specimen PDF or set
`provisional_pending_specimen = true`". Neither action is available to an installed
user.

### The round-trip check's stronger half is unshippable by construction

`corpus_round_trip_verified` is an author assertion that "a parametrized real-corpus
round-trip test exists". Tests are excluded from the wheel by category. Shipping the
specimens would restore the fixture-presence half while leaving the test-existence half
an unverifiable assertion, so a shipped-corpus check would be strictly weaker than the
checkout check rather than equivalent to it.

### Packaging: what the exclusion block says and what the companion channel carries

`pyproject.toml:232` `[tool.hatch.build.targets.wheel]` excludes `src/cadrumo/tests`,
`src/cadrumo/tests/**`, `src/cadrumo/**/tests` and `src/cadrumo/**/tests/**`, on the
in-file rationale that test modules and fixtures "serve no installed consumer" and that
"this payload is shed from the distribution to bound its size".

The same block sheds `src/cadrumo/_data/corpus/**/*.pdf` plus `.docx`, `.xls`, `.xlsm`,
`.xlsx` and `.zip`, recorded in-file as "94% of the wheel's compressed weight". Those
binaries ship instead in the `cadrumo-data-manuals` and `cadrumo-data-official`
companion distributions, installed as mandatory base dependencies under a mirrored
`cadrumo_data/_data/corpus` tree, both pinned to the root version (currently `0.2.2` per
`packaging/cadrumo_data_manuals/pyproject.toml:13`). The stated aim is keeping the slim
wheel "under PyPI's 100 MB cap with no file-size grant on the critical path".

At 272 KiB of PDF bytes (1010 KiB with sidecars, or roughly 2.6 MiB including the
facsimile annexes), the specimen corpus is about three orders of magnitude below the
constraint that motivated that split. Size is not a live objection in either direction.

### The companion locator resolves files, not directories

`resolve_companion_binary` (`src/cadrumo/core/resources/_boundary.py:131`) and
`resolve_corpus_binary` (`:155`) both gate on `_traversable_is_file` (`:109`) and return
a single file `Path` or `None`. Neither resolves a directory, which is the shape the
specimen gate needs, since it joins `corpus_root / <modelo_id>` and then globs. Shipping
through either companion would require a new directory-resolving seam.

`bundled_path` (`:65`) does return a `Path` for a subtree and would resolve a directory
relocated under `src/cadrumo/_data/`, so an in-wheel route needs no new locator, only a
physical relocation out of the excluded `tests/` tree.

### Where a real-vs-synthetic ship guard could attach, and why it cannot be shipped code

The provenance vocabulary and its physical cross-check are concentrated in one module:
`src/cadrumo/tests/fixtures/__init__.py` declares `FIXTURE_PROVENANCE_SYNTHETIC` at
`:38`, `FIXTURE_PROVENANCE_REAL` at `:41` and `RECOGNISED_FIXTURE_PROVENANCES` at `:44`,
exposes the reader `sidecar_provenance` at `:58`, and implements the honesty check
`provenance_mismatches` at `:71`, which cross-checks the declared value against the
`/Producer` DocInfo signature and rejects a `real_corpus` claim on a
generator-signed PDF and a `synthetic_generated` claim on an unsigned one.

The stamping side is `src/cadrumo/tests/fixtures/justificantes/_generate_base.py:190`,
which writes `"provenance": FIXTURE_PROVENANCE_SYNTHETIC` into every generated sidecar,
with `:172` recording that `role` and `provenance` are orthogonal axes per the
verification-fixture-roles decision. The enforcing gate is
`src/cadrumo/domain/calculations/registry/tests/test_verification_source_fixture_metadata.py:126`.

Every one of those sites lives under a `tests/` directory and is wheel-excluded. A guard
preventing a future `real_corpus` anchor from shipping therefore cannot be an assertion
in shipped code; it has to be a checkout-side gate over the packaging manifest, or a
build-time assertion over the built artefact. No such gate exists today, and designing
one was not attempted here.

### A hardened one-way boundary already governs shipped code reading non-shipped paths

`2026-07-27-conformance-cli-adr` rules that every wheel-shipped module under
`src/cadrumo` "must never read `dev/**` paths at runtime", that "everything shipped code
needs lives under `src/cadrumo`", and that the rule scopes to shipped modules because a
wheel-excluded tree's reach "cannot follow the package to an installed user".

The specimen chain is structurally the same: shipped modules
(`_validate_record_sections.py`, `_validate_extraction_profiles.py`) consuming a
wheel-excluded path. The letter of that ruling names `dev/**` and not `tests/**`, so it
is not literally violated, but the principle admits only two consistent resolutions.
Either the path is something shipped code needs, and must ship from a non-excluded
location, or it is not, and the reach must be structurally refused outside a checkout.

`2026-07-31-semantic-search-precompile-boundary-adr` (accepted) draws the same line for
search in its R2: the heavy artefact is regenerated and published but "never committed
and never wheeled", and only laundered light data ships. The `shipped-search-licence-clean`
rule states the committed-versus-generated half of that boundary.

### The uncommitted campaign work already implements the refusal resolution

`derive_justificante_corpus_candidate`
(`src/cadrumo/domain/calculations/registry/_source_evidence_fingerprint.py:85`,
uncommitted at time of writing) gates derivation on `RunMode.CHECKOUT` at `:116` and
returns a typed `JustificanteCorpusUnavailableAdvisory` (`:32`) carrying `run_mode`,
`probed_path` and an operator-safe `reason` whenever the corpus cannot be derived.
`RegistryValidator` exposes it at `_validate.py:136`. The advisory is suppressed when a
caller supplies `justificante_corpus_root` explicitly, treated as a deliberate opt-out
rather than a derivation failure.

This converts a previously silent skip into an introspectable record, without deciding
whether the gap should be closed by shipping.

### The option space the decision must choose between

Three options are live on this evidence. Shipping through a companion distribution
carries the corpus to installed users but needs a new directory-resolving seam, and buys
a check whose verdict is already determined at build time and whose stronger half cannot
ship. Accepting the gap keeps the wheel and the precompile boundary unchanged and relies
on the advisory for visibility, at the cost that nothing re-executes the check on an
installed build. A hybrid shipping only a minimal subset inherits the companion route's
machinery for a fraction of a check that cannot currently fail. The trade-offs are
recorded here; the choice belongs to the decision record.

### Not investigated

Whether the `aeat_published_facsimile` annexes carry a licence posture permitting
redistribution was not established; their sidecars were read for provenance only, and
this is the one open question that could change a facsimile-scoped decision.

No test suite was executed, so gate behaviour is read from source rather than observed.
No wheel was built, so the exclusion patterns' effect on `sanitizer/fixtures.py` is
inferred from the glob patterns rather than confirmed against a built artefact.

Whether any existing CI lane already asserts anything about `declaracion_pdf` specimen
coverage was not determined. Whether consumers outside
`src/cadrumo/domain/calculations/registry/` read the specimen tree at runtime was
checked by `rg` across `src/` and `dev/` and none were found outside `tests/`
directories, but that sweep keyed on the path literal and would miss a consumer
composing the path from parts.

No design was produced for the packaging-manifest guard the real-versus-synthetic
question needs.

## Sources

- `src/cadrumo/tests/fixtures/justificantes/` (63 PDFs, 60 sidecars)
- `src/cadrumo/tests/fixtures/manual_annexes/` (7 facsimile artefacts)
- `src/cadrumo/tests/fixtures/__init__.py:38`, `:41`, `:44`, `:58`, `:71`
- `src/cadrumo/tests/fixtures/justificantes/_generate_base.py:172`, `:190`
- `src/cadrumo/domain/calculations/registry/_source_evidence_fingerprint.py:3`, `:32`, `:85`, `:116`, `:155`
- `src/cadrumo/domain/calculations/registry/_validate.py:104`, `:108`, `:136`, `:157`, `:281`
- `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py:80`, `:198`, `:249`, `:288`
- `src/cadrumo/domain/calculations/registry/_validate_record_sections.py:272`, `:303`
- `src/cadrumo/domain/calculations/registry/_validate_extraction_profiles.py:10`, `:35`, `:46`, `:82`
- `src/cadrumo/domain/calculations/registry/tests/test_verification_source_fixture_metadata.py:126`
- `src/cadrumo/adapters/inbound/sanitizer/fixtures.py:26`, `:32`
- `src/cadrumo/adapters/inbound/sanitizer/tests/test_sanitized_sha_catalogue.py`
- `src/cadrumo/adapters/inbound/sanitizer/tests/test_residual_identity_absence.py:131`, `:137`
- `src/cadrumo/application/ledger/tests/_evidence_corpus/`
- `src/cadrumo/core/resources/_boundary.py:65`, `:109`, `:131`, `:155`
- `pyproject.toml:232`
- `packaging/cadrumo_data_manuals/pyproject.toml:13`
