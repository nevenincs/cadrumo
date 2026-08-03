---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:20747819f32f93986c141a26be181c98f479dfab3bbc0610f4b7a4ea73b34664'
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-plan]]'
  - '[[2026-08-03-canonical-storage-management-honesty-review-audit]]'
  - '[[2026-08-03-canonical-storage-management-semantic-duplication-burndown-reference]]'
  - '[[2026-08-03-canonical-storage-management-enforcement-gates-reference]]'
---

# `canonical-storage-management` audit: `self duplication review`

## Scope

The campaign exists to eliminate duplicate authorities over on-disk names. This
audit holds the campaign's own output to that standard: is the code it added
unique, unshadowed, and canonically homed, or did removing three authorities
create new ones?

Audited at `HEAD` `c16bb9a0ae`, with the working tree noted where it differs
(the campaign is still executing; the ADR, the plan, thirty-odd exec records and
a seventh gate are uncommitted). Subject: the core taxonomy module, the three
resolution entry points, the extracted path-definitions module, the six landed
gates plus the rewritten settings-lifecycle gate, the three test helper modules,
the storage-management service, and the campaign's vault corpus.

Method was semantic discovery first. Ten `vaultspec-rag --type code` probes were
run by behaviour and domain noun, never by symbol name: resolving a storage
location for a category; joining the data root with a relative directory name;
resolving one profile bucket's directory; declaring on-disk layout as a template
with placeholders; compiling an angle-bracket template into a regular
expression; summing bytes under a directory; deleting regenerable caches to
reclaim space; listing every location with its size; deciding where the
application stores data per operating system; refusing a path that escapes its
parent; and computing a drift digest over the data root. Every candidate was
then confirmed with `rg`, by reading the site, and — for the two shape findings
— by executing the real resolvers. Probe coverage and its one structural blind
spot are stated in the last finding.

The substitutability pre-filter was applied before any convergence verdict. Two
candidates were downgraded by it and are recorded as `CONSTRAINT-DIVERGENT`
rather than as duplication.

## Findings

### grammar-root-token-is-polysemous | high | Three blob grammars anchor `<root>` at a different directory than every other grammar, and the campaign's new agreement gate reads all of them as if they were the same anchor

`STORAGE_PATH_DEFINITIONS` in
`src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py` declares
every filesystem shape against a `<root>` token. Sixteen of the nineteen
filesystem entries mean the storage root by it, and the module says so: the
`secret_index` comment at line 200 reasons that spelling `<root>/secrets/` out
directly makes the grammar "consistent with every other `<root>`-anchored entry
here". Three entries are not consistent with it. `blob_manifest` (line 230),
`blob_content_plaintext` (line 247) and `blob_content_ciphertext` (line 253)
anchor `<root>` at the blob store's own `root_dir`, which production sets to
`cadrumo_blob_store_dir` at
`src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py:72` —
itself already `<storage_root>/blobs`, the `BLOBS` taxonomy member. The
conformance test at
`src/cadrumo/adapters/persistence/storage/blob_store/tests/test_blob_content_shape_conformance.py:42`
passes `root=store.root_dir`, confirming the reading; the outbound conformance
test at
`src/cadrumo/adapters/outbound/storage/tests/test_local_provider_object_shape_conformance.py:58`
passes the full storage root. The helper's own docstring in
`src/cadrumo/tests/_storage_path_grammar.py:104` concedes the ambiguity — "the
helper does not assume which" — so no consumer can compute an absolute path from
a grammar.

Executed against the live resolvers, `storage_path(StorageCategory.BLOBS)`
returns `...\cadrumo\storage\blobs` and `_BLOB_STORE_DIRNAME` (parsed off the
grammar at `_blob_store.py:83`) appends `blobs` again, so the real directory is
`...\cadrumo\storage\blobs\blobs`. The new gate
`src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py:68`
strips `<root>`, extracts the literal run `blobs`, and finds it in
`_KNOWN_DIRECTORY_SUBPATHS` because `StorageCategory.BLOBS.subpath` is also
`blobs`. The two spellings agree only because two different anchors happen to
share a name — precisely the conflation the taxonomy's own `StorageScope`
docstring warns about for `blobs` and `audit`, reintroduced one layer up. The
gate therefore certifies an agreement it did not verify, and worse, it would
mislead under the exact scenario it was built for: renaming
`StorageCategory.BLOBS.subpath` reds the gate pointing at the three blob
grammars, and editing a blob grammar to satisfy it changes `_BLOB_STORE_DIRNAME`
and relocates every blob on disk. Verdict `CONVERGE`.

### worst-case-object-path-omits-the-namespace-segment | high | Two declarations of the deepest on-disk object path disagree by nineteen characters, the anti-tautology test reproduces the omission, and the planned remedy does not fix it

`WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH` at `src/cadrumo/core/paths.py:111`
computes the deepest suffix the bucket and outbound-storage layout can append
below a configured root as
`\buckets\<uuid-36>\blobs\<hmac-8>--<label-64>.meta.json`. The campaign's own
`local_provider_object_sidecar` grammar, pinned against a real write, declares
`<root>/buckets/<bucket_id>/blobs/<namespace>/<hmac_prefix>--<label>.meta.json`.
The literal omits the `<namespace>` directory. The provider genuinely creates it:
`src/cadrumo/adapters/outbound/storage/_local.py:176` and `:292` write into
`self._root / namespace`, and the factory hands it the bucket's `blobs_dir`.
Measured, the constant is 136 and the true suffix for the observed
`ledger_transaction` namespace is 155 — `windows_storage_root_long_path_margin`
overstates headroom by nineteen characters, and the preflight refusal at
`src/cadrumo/application/preflight.py:349` can therefore accept a storage root
from which a real outbound write exceeds the legacy `MAX_PATH` ceiling.

The site is pre-existing, but three things make it the campaign's to own. The
campaign declared the authoritative competing shape, so this is now a live
disagreement between two declarations rather than one undocumented literal. The
test that was written to prevent exactly this, at
`src/cadrumo/core/tests/test_paths.py:190-220` — labelled "Anti-tautology guard"
and recomputing the suffix from the real constants "so a change to either shape
is caught here instead of silently under-counting the margin" — reproduces the
same omission and is green, so nothing detects it. And plan step `W01.P03.S26`,
still open, proposes re-pointing the constant onto the core bucket-layout
members; performed as written that swaps literals for constants and leaves the
missing segment missing. Verdict `CONVERGE`, and the plan row needs rewording
before it is executed.

### node-kind-declared-twice-in-two-layers | medium | Two enums answer file-versus-directory for the same hierarchy, share both string values, and nothing relates them

`StorageNodeKind` in `src/cadrumo/core/_storage_taxonomy.py:60` declares
`directory` and `file`. `StoragePathKind` in
`src/cadrumo/adapters/persistence/storage/_namespace_taxonomy.py:69` declares
`directory`, `file`, `logical_sql` and `blob_object` — byte-identical values for
the two shared members. Both classify nodes of the one on-disk hierarchy, and
the directory-agreement gate consumes both in a single comparison: it reads
`kind: StoragePathKind` to decide whether a grammar's terminal component is a
directory, and matches the result against members whose `node_kind` is a
`StorageNodeKind`. No module and no test imports both names; there is no parity
gate, so the two can drift on the shared members with nothing to catch it.

The substitutability pre-filter blocks a straight merge, so this is
`CONSTRAINT-DIVERGENT` rather than duplication to collapse. `StoragePathKind`'s
extra members are adapter-layer concepts core does not own; core must not import
adapters; and a `StrEnum` that already has members cannot be extended, so
`StoragePathKind` cannot subclass `StorageNodeKind`. The actionable remedy is not
convergence but declaration: state the relationship in both docstrings and add a
parity gate asserting the shared members' values stay equal — the same treatment
the campaign gave every other pair of spellings it could not physically merge.

### relocation-shipped-a-compatibility-re-export-bridge | medium | The extraction left `_namespace_registry` re-exporting names it no longer declares, by explicit design, and the liveness claims now point at the bridge

Commit `3a6ce7475d` moved `StoragePathDefinition`, `STORAGE_PATH_DEFINITIONS`
and the eleven bucket and keystore layout constants into
`_storage_path_definitions.py`, then imported them straight back into
`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:24-41`. The
comment at line 50 states the intent: "re-exported below -- so every existing
caller of `from .._namespace_registry import BUCKETS_DIRNAME` (etc.) keeps
working unchanged". One import carries `# noqa: F401 - public re-export`,
confirming at least that name has no local use. Five production modules still
import layout names from the module that no longer declares them:
`bucket/_keystore_paths.py:22`, `bucket/_layout.py:30`, `bucket/_lockfile.py:32`,
`bucket/_manifest_io.py:21`, `bucket/_output_language_hint.py:19`.

The project rule on relocation is unambiguous — the canonical-site move and
every consumer update share one commit, and a re-export is never reintroduced as
a bridge — and the zero-legacy rule bars the shim independently. This is
intra-package, so the cross-package facade rule is not violated and the imports
are not themselves illegal; the defect is that the campaign against "which module
declares this name" shipped a module that answers the question wrongly.

There is a second-order cost the campaign should weigh. Ten bucket and keystore
members in the taxonomy declare
`consumer_module="adapters/persistence/storage/_storage_path_definitions.py"`
(lines 977 through 1083). That module's only use of those members is to bind
module-level constants for re-export. The liveness gate is satisfied by an
attribute load in a pass-through, while the modules that actually write the
bytes go unnamed — so the claim the gate verifies is weaker than the claim its
docstring describes ("a location no module touches cannot be written to").
Retiring the bridge and re-pointing the consumers restores both. Verdict
`CONVERGE`.

### grammar-restates-subpaths-the-same-file-already-interpolates | medium | Fourteen grammars hand-spell a directory the taxonomy declares, and the fix is demonstrated on the adjacent field of the same model

The split between taxonomy `subpath` and definition `grammar` is legitimate at
the concept level: membership with axes versus a parameterised shape that cannot
be enumerated. That defence does not cover the literal directory prefix, which is
not parameterised. Fourteen `STORAGE_PATH_DEFINITIONS` grammars hand-spell a
directory run that a `StorageCategory` already declares — `runs`, `tokens`,
`secrets`, `llm-usage`, `cache/registry-verdict`, `cache/llm-cache`, `buckets`,
`db`, `blobs`, `keystore` and the rest — and the campaign's response was to add a
gate comparing the two spellings rather than to remove one. The brief's
instinct is right: the gate is the evidence of overlap.

What makes this actionable rather than a matter of taste is that the same file
already applies the elimination on the neighbouring field. `segment=` is
populated by `storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath`
and by the `BUCKETS_DIRNAME`-style constants, which are themselves reads off the
taxonomy — so the module demonstrably knows how to interpolate a declared name
into a definition, and does it for `segment` while hand-typing the same name into
`grammar` two lines away. Interpolating the literal runs would make the
directory-agreement gate unnecessary by construction rather than green by
comparison, and would remove the rename hazard that finding one turns into a
mistrap. Verdict `CONVERGE`, lower priority than the two shape findings because
the gate does hold today for the sixteen storage-root-anchored entries.

### adr-r16-excluded-count-is-wrong-again-at-head | RETRACTED | Withdrawn on measurement: R16 was correct at HEAD; this finding measured the working tree and said HEAD

**Retraction, recorded in place rather than by deletion, because the finding was
acted on before it was checked.** The claim below is false as written. At HEAD
`c16bb9a0ae` the taxonomy declares exactly nine fingerprint-excluded members, and
they are exactly the nine `R16` enumerates, in the same order — nine members,
nine fields, ADR says nine. No drift existed.

The error was method, not arithmetic: the count came from `uv run python`, which
imports the working tree. The two extra members it saw,
`CORPUS_TEXT_CACHE_FILE` and `CORPUS_SEARCH_INDEX`, were uncommitted at the time
and are the file leaves a peer was landing during this review. This audit's Scope
states its measurements are anchored at HEAD; for this finding alone that was not
true, and the campaign's own standing discipline on re-reading HEAD before
reporting is what should have caught it.

What survives is a prediction, not a defect. Those two members are excluded
*members* carrying no *settings field*, so once they land the member count
becomes eleven while `FINGERPRINT_EXCLUDED_STORAGE_FIELDS` stays at nine. `R16`
quoted members; the mechanism it governs is keyed by field. The framing fix was
therefore worth making, and was made: within an hour of this retraction `R16` was
amended to state both counts, to verify them at a named commit, and to warn that
their present agreement is not guaranteed to survive the next declaration. That
amendment is correct and is the closing state of this item.

The original finding text follows, unedited, so the record shows what was claimed
and how it failed.



Ruling `R16` in the ADR states the excluded set "settled at nine excluded
members, not eight and not merely the old eight plus `cache/registry`", verified
at `HEAD`, and the change log records the correction history as eight, then
eleven, then nine. Executed against the live taxonomy there are eleven excluded
members and nine excluded settings fields: the two file leaves
`corpus-text-cache.file` and `corpus-search-cache.index` are excluded members
that carry no settings field, so both counts are simultaneously defensible and
the ADR names the wrong one. The prior honesty review logged this as
`r16-excluded-member-list-is-stale` and it has drifted again since, which
identifies the root cause as structural rather than clerical — the ruling
counts "members" while the mechanism it governs,
`FINGERPRINT_EXCLUDED_STORAGE_FIELDS`, is keyed by field. The ADR's enumeration
argument is unaffected in substance; only the cardinality it is stated against is
wrong. This is the one place in the corpus where a fact genuinely lives in two
places and has demonstrably drifted three times.

### paths-docstring-cites-the-superseded-declaring-module | low | The margin constant's docstring names `_namespace_registry` as the source it mirrors

`src/cadrumo/core/paths.py:104` documents the constant as mirroring
`cadrumo.adapters.persistence.storage._namespace_registry.BUCKETS_DIRNAME`. The
declaring module is now `_storage_path_definitions.py`; the citation resolves
only through the bridge finding four describes. Commit `1b4cecc31f` swept ten
consumer claims onto the module that now backs them and missed this one. It
should be corrected in the same change as finding two, which touches the same
docstring block.

### scope-is-a-homonym-across-the-two-storage-taxonomies | low | `StorageScope` and `StorageNamespaceScope` name unrelated concepts

`StorageScope` (`_storage_taxonomy.py:73`) is the filesystem anchor a subpath is
relative to. `StorageNamespaceScope` (`_namespace_taxonomy.py:26`) is the custody
scope of a secure-object namespace. Neither is derivable from the other and both
are correctly named for what they do; the second predates the campaign. Recorded
for the reader who greps `Scope` in the storage tree and finds two answers, not
as a defect to fix. Verdict `DELIBERATE`.

### deliberate-separations-re-verified | none | The three separations the review was told not to flag are each still justified, on evidence

`DERIVED_OUTPUT_SUBPATHS` in
`src/cadrumo/core/tests/test_output_dir_state_root.py:79` does restate the
taxonomy's subpaths, and must: deriving it would make the test assert the
taxonomy against itself. Its both-directions gate at line 89 is present, so a
member added or dropped on either side reds. Still an independent oracle.

The five secret-store file members carrying no `settings_field` are correct.
`SECRETS` is `OPERATOR_OVERRIDABLE`, so composing root plus the literal
`secrets/master.key` subpath would silently disagree with any operator override,
exactly as the declaration's comment at `_storage_taxonomy.py:530-539` reasons.
The same argument covers the five `audit/live/*` members and the two cache-file
leaves. Verified, not merely accepted.

The SQL secure-object namespace keys stay separate and the separation is
enforced, not just asserted: `secure_objects_table` is the sole `LOGICAL_SQL`
entry, and both the directory-agreement gate and the grammar compiler filter that
kind out explicitly rather than by accident.

### gate-overlap-and-dead-capability-both-clean | none | No two gates detect the same condition, and nothing the campaign added is unconsumed

Every gate function across the seven modules was read against every other. The
closest pair is genuinely disjoint: `test_storage_default_parity` compares a
pydantic placeholder default in `config.py` against the taxonomy subpath, while
`test_output_dir_state_root` compares an independent hand-written oracle against
the same subpath — different left-hand sides, and the first documents honestly
why its duplicate cannot be removed (pydantic requires a default; deriving it
would close an import cycle). Provenance scans join sites, binding classifies
settings fields, materialisation compares declaration to disk, liveness verifies
consumer claims, fingerprint participation drives a real digest with a positive
control, and directory agreement compares grammar to subpath. No two answer the
same question.

Every public symbol the campaign added has a consumer. All 129 tests across the
eleven gate modules pass in the working tree, so the two gates the honesty
review recorded red at `HEAD` have since been closed.

### probe-coverage-and-its-blind-spot | none | What the eleven probes would and would not have surfaced

The probes reliably surface a second implementation of a behaviour that has a
name — a second byte-summer, a second containment guard, a second state-root
resolver, a second grammar compiler. Each of those returned a single authority,
which is a real result: `directory_byte_total`, `resolve_relative_subpath`,
`_config_state_root`, `_fingerprint`, and the one grammar compiler each own their
concept outright, with `bucket_maintenance` and `observability` already
delegating to the shared byte-summer.

The class the probes would not have surfaced is the one that produced this
audit's two highest findings: a duplication that is not a second *function* but a
second *constant describing the same shape*, where the two sites share no
vocabulary. Nothing in "compile a path template into a regular expression" reaches
a length arithmetic expression in a Windows hardening helper, and nothing in
"resolve a storage location" reaches a grammar string whose `<root>` means a
different directory than its neighbour's. Both were found by reading the declared
shape and asking what production actually writes, then executing it. A selector
that does not match the concept fails in both directions — the campaign's own
lesson — and for shape-versus-shape duplication the working selector is
execution, not search.

## Recommendations

Fix the two shape findings before closure, in that order, because both are
correctness defects rather than hygiene. Declare each grammar's anchor
explicitly — a field on `StoragePathDefinition` naming which directory `<root>`
means — and make the directory-agreement gate skip or re-anchor the entries whose
`<root>` is not the storage root, so it stops certifying a coincidence. Then
correct `WINDOWS_WORST_CASE_OBJECT_PATH_SUFFIX_LENGTH` to include the outbound
namespace segment, derive it from the `local_provider_object_sidecar` grammar
rather than from a literal, and rewrite the recomputation in `test_paths.py` so
it fails against the current value before it passes against the new one. Reword
plan step `W01.P03.S26` first; executed as written it preserves the defect.

Retire the `_namespace_registry` re-export bridge by re-pointing the five bucket
modules at `_storage_path_definitions`, and re-point the ten taxonomy
`consumer_module` claims at the modules that write the bytes, so the liveness
gate verifies what its docstring says it verifies. Add a parity gate over the two
shared `StorageNodeKind` and `StoragePathKind` values and cross-reference the two
docstrings; do not attempt a merge, which the layer direction and `StrEnum`
extension both block. The `R16` recommendation that stood here is **withdrawn and
already satisfied** — see the retraction above: the ruling was correct at HEAD,
and it has since been amended to state both counts and why they can diverge,
which is the durable form of the fix the retracted finding was reaching for.

Interpolating the grammars' literal directory runs off `storage_location(...)`,
as `segment=` already does, is the one recommendation that is optional. It would
retire the directory-agreement gate by construction and remove the rename mistrap
entirely; deferring it is defensible while that gate holds, but the duplication is
real and the campaign's own standard is elimination rather than pinning.

## Verdict

The campaign did not meet its own standard, and the gap is not a technicality.
Judged on its stated purpose — eliminating duplicate authorities over on-disk
names — it removed four (the untyped settings dict, the adapter string
constants, the module-local constants, the unpinned inline copies) and shipped
three new ones: a `<root>` token that means two different directories across one
declaration table, a deepest-path shape declared twice with the two declarations
disagreeing by nineteen characters, and a file-versus-directory enum now declared
in two layers with nothing relating them. It also shipped, deliberately and with
a comment explaining why, exactly the compatibility re-export bridge the project
rules forbid.

The mitigating half is real and should not be lost in the ranking. The
architecture is sound, the layering is clean with no upward import, the service
composes rather than re-implements, the gates are individually well-built with
genuine positive controls and no mutual overlap, nothing added is dead, and the
single-authority probes came back clean on every concept that has a name. The
three deliberate separations are each still justified on evidence rather than on
assertion.

The pattern worth naming is narrower than "the campaign duplicated things". Twice
the campaign chose to *pin* a duplicate rather than *eliminate* it — the grammar
against the subpath, and the settings placeholder against the subpath — and in
the first of those the pin is what created the trap, because the gate now asserts
an agreement it cannot actually see. A gate over two spellings is a weaker
guarantee than one spelling, and it costs a reader more.
