---
tags:
  - '#audit'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:cc057d7902ed8d0eab3cbda3bcd6150afd95682052c2e1c21b7a89eba4056ccb'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# `modelo-localization-cascade` audit: `implementation safety and intent`

## Scope

Review W01.P01.S01, W01.P01.S02, W01.P02.S03, and W01.P02.S04 against the
authorizing plan, ADR, and research. Audit the read-only source fingerprint,
supported revision inventory, resolved matrix, canonical candidates,
classification, strict records, real behavior tests, and the explicit boundary
against production mutation.

## Findings

### source-contract | low | No actionable safety or intent findings

The implementation stays within `dev/registry/migration`, uses the public
registry loader and source descriptors, records content-only deterministic
fingerprints, refuses source drift, and exposes no production write path. The
tests exercise the real bundled tree and a real temporary filesystem without
fakes, patches, skips, xfails, or tautological business logic. Focused Ruff and
pytest validation passed.

### resolved-matrix | low | No actionable safety or intent findings

S02 reads the current public loader's materialized label/help behavior for every
supported modelo, revision, casilla, locale, and field. It binds the rows to the
S01 fingerprint, checks the corpus before and after loading and row construction,
validates complete deterministic coordinates, and writes nothing to the source
tree or live registry. The tests assert the real measured population,
root/revision precedence, Spanish label fallback, absent help behavior, and
unchanged source metadata. Ruff, basedpyright, and six focused integration tests
passed. No critical, high, or medium findings were identified.

### canonical-candidates | low | No actionable safety or intent findings

S03 derives candidates only from the S02 matrix and the declared occurrence
identity. Declared continuity ids use the accepted continuity address; all
other occurrences remain revision-exact. Logical key validation preserves
compound colon-bearing casilla ids without weakening filesystem fingerprint
validation. Locale is kept outside semantic identity, and no repeated-id or
text inference is introduced. The focused real-behavior tests passed after
covering both exact and grounded addresses. No critical, high, or medium
findings were identified.

### candidate-classification | low | No actionable safety or intent findings

S04 classifies only from declared continuity presence and repeated
Modelo/casilla occurrence across supported revisions. Grounded rows retain
their source continuity id; ungrounded single-revision rows remain exact; and
repeated ungrounded rows receive only a migration-local provisional group
token. The S03 canonical address is never rewritten and no label, number, or
text heuristic can promote identity. The measured classification partition and
incomplete-provisional-state refusal are covered by real bundled-corpus tests.
No critical, high, or medium findings were identified.

### source-manifest | low | No actionable safety or intent findings

S05 binds every manifest observation to the pinned corpus fingerprint and the
real schema or loader-winning locale source. It preserves raw and old resolved
values, fallback and leaf state, normalized and source hashes, measured drift,
review status, and an empty emitted target. The unresolved register is derived
only from continuity candidates and does not promote provisional ids. The
bundled-corpus tests prove the measured 126,192-row seal, 2,354 unresolved
groups, placeholder-state counts, source ownership, tamper refusal, and
read-only behavior. No critical, high, or medium findings were identified.

The open pre-emission review gate is intentional: mirrored-help and key-echo
leaves need explicit delete-versus-migrate adjudication, and year-embedded
label families need an explicit parameterized-label decision before emission.

## Recommendations

Keep the S01 fingerprint, S02 matrix, S03 candidate addresses, and S04
classification immutable inputs to manifest generation. Keep the S05 source
manifest and unresolved register sealed evidence. Do not promote provisional
groups, emit catalogues, compare parity, or mutate production in this step.
Complete the pre-emission placeholder and year-parameterization review gate
before any staging emitter hardens a representation.

### pre-emission-review | low | No actionable safety or intent findings

The pre-emission register is a strict, frozen, source-manifest-bound record. It
does not write the registry, stage output, or mutate the old reader. Every
mirrored and key-echo placeholder receives an explicit delete-versus-migrate
disposition while parity retains the captured old value. The register exposes
the measured 9,477 mirrored-help debt as 9,453 mirrored leaves plus 24 help key
echoes, and separately counts the 24 label key echoes.

Year-token entries are admitted only for exact annual revision identifiers whose
embedded year matches the revision, whose one-token template reproduces every
captured value exactly, and whose official-Spanish source is the `es` locale.
Fallback-only non-Spanish rows and mixed authored/fallback families are not
promoted into a parameterized declaration. Ordering, counters, source binding,
and the canonical review digest are strictly validated. Ruff, basedpyright, and
the focused real bundled-corpus integration test passed; no critical, high, or
medium implementation finding was identified.

### migration-validation-boundary | low | Broad folder validation remains corpus-drift limited

The full migration integration folder produced 13 passing tests and one failure
in the pre-existing candidate-classification expectation: it expected 144
grounded rows but observed 3,576 while concurrent registry fragment edits were
active. The moving-source refusal and the later passing focused S18 run show the
reader's drift guard is operating as designed. The peer-owned corpus and its
expectation were left unchanged.

### user-profile-phase | medium | The amended plan still needs a dedicated user-profile phase

The accepted ADR amendment records the load-bearing user-profile schema surface
and requires every non-Modelo natural-language schema surface to be classified
before cutover. The current plan has not yet gained a dedicated user-profile
phase. Sol must amend the architecture-owned plan before later emitter or parity
steps can claim campaign completeness; this S18 implementation intentionally
does not absorb that scope.

### locale-key-grammar | medium | Migration coordinates must not become a second public key syntax

The accepted cascade ADR originally called slash-delimited occurrence paths
canonical localization keys, while the established locale subsystem and the
in-flight user-profile schema localization work derive dotted semantic keys,
enrol them in the shared locale-key scanner, author them through the shared
locale CLI, and resolve them through the shared renderer. The disposable
migration consequently sealed deterministic slash-delimited values in a field
named `canonical_key`. Those values are sound source coordinates, but emitting
them as runtime keys would fork the localization grammar and bypass the
standard locale-key universe.

The governing ADR has been amended in place: Modelo catalogues remain physically
owned beneath each Modelo root, production keys use the dotted
`modelo.schema.*` family, unsafe identity segments use one reversible codec, and
the already sealed slash values remain immutable migration evidence translated
only at emission. No production or migration code was changed by this
reconciliation.

Before emitter work begins, amend the in-flight plan so the S03/S05
`canonical_key` field is described as a migration occurrence address and the
emission phase derives and records a separate standardized dotted target key.
Keep existing source-manifest hashes stable; do not rename or rewrite sealed
records merely for terminology. Add parity gates proving every emitted Modelo
key is discoverable by the shared locale manager, resolves through the shared
renderer, contains no Spanish source prose, and contains no slash-delimited
migration address.

### locale-storage-retirement | high | The prior root-storage reconciliation is superseded

The preceding locale-key finding correctly separates migration coordinates from
standardized dotted keys, but its statement that target catalogues remain
physically beneath each Modelo root is no longer authoritative. The operator has
clarified that every Modelo-local locale file is legacy storage. The target is
the existing shared runtime catalogue family, not a second TOML-backed provider.

The governing ADR now requires atomic per-Modelo enrollment. A Modelo may lose
its legacy files only after its full key universe is enrolled in the shared
locale schema and Spanish-source, translation, revision, rendering, export, and
facade parity have passed against the sealed old behavior. The same scoped
cutover then deletes both Modelo-root and revision-local locale files and removes
localized schema text. Mixed ownership is allowed only between Modelos while the
campaign is incomplete; an enrolled Modelo may never read both layouts.

The team lead must update the in-flight plan before emission: target the shared
catalogues through the standard locale CLI, add a per-Modelo enrollment
certificate and deletion gate, reject both `<modelo>/locales/**` and
`<modelo>/revisions/**/locales/**` after enrollment, and make final closure
delete the legacy reader, `ModeloLocaleManager`, and legacy Modelo locale
commands. Existing source-manifest seals remain unchanged.
