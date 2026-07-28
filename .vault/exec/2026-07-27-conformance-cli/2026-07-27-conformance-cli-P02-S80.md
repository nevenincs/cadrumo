---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S80'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# lift the export-format closed set from a bare Literal on the export-layout schema to a core StrEnum so the per-modelo support matrix and the per-revision conformance fold compare enum members rather than each re-spelling the same tokens

## Scope

- `src/cadrumo/core`
- `src/cadrumo/domain/calculations/registry`
- `src/cadrumo/application/filing`
- `src/cadrumo/application/modelo`
- `src/cadrumo/application/registry`
- `src/cadrumo/adapters/outbound/aeat`
- `docs/api`

## Description

- Declare the closed set as a core StrEnum with the exact tokens the registry
  TOML already stores.
- Type the export-layout field on it and hydrate the TOML token explicitly at
  the registry boundary, since registry models validate strictly.
- Route all nineteen consumer sites through the members, production and test.
- Regenerate the API stubs and stage only the two naming the new module.
- Land the move, the consumers, the facade entry and the stubs in one atomic
  explicit-pathspec commit with a clean collect immediately before it.
- Add the boundary proofs the relocation itself could not carry.

## Outcome

### Why a Literal grows a copy at every call site

The value set was a bare `Literal` on the layout model, and the consequence is
mechanical rather than stylistic: a `Literal` has no home a consumer can import,
so a consumer that needs to compare against it has no option except to re-spell
it. Roughly twenty sites did, across the registry, filing, modelo, adapter and
conformance packages.

That is not a tidiness complaint. Two of those sites computed the SAME
per-modelo capability booleans from those literals, in two different packages,
and the pair had already diverged before anyone noticed. Retiring the duplicate
closed the fork at the function level and left it standing at the literal level,
which is exactly the residue the ruling that opened this Step named. One enum in
`core` is the durable fix: there is now a single declaration a consumer imports,
so the accepted set and every branch on it cannot drift apart.

### The lift is behaviour-preserving, and hydration had to become explicit

Member values are byte-identical to the tokens the registry TOML already stores,
so no manifest changed and a member compares, hashes and JSON-serialises exactly
as the string it replaces. That property is what made a nineteen-site sweep safe
to do in one commit.

It also created the one real surprise. Registry models validate in STRICT mode,
so pydantic does NOT coerce a bare `"fixed_width"` into the enum it spells, and
the first run of the change failed to load the bundled tree at all. Hydration is
therefore an explicit boundary coercion, in the same `Annotated` +
`BeforeValidator` shape the input-kind axis beside it already uses, with a
refusal that names the accepted set rather than leaving an author with a bare
type error. This is where the registry-authority rule puts it: the TOML stays
free-form text, the compiled objects carry typed members.

### The naming decision

Deliberately `ExportLayoutFormat`, not `ExportFormat`. The filing surface already
ships `DeclaracionExportFormat` — the operator-facing catalogue of export
PRODUCTS, whose values are hyphenated (`fichero-boe`, `xml-dictionary`) — and
`core` already ships `OutputFormat` for the CLI's own text-versus-JSON rendering
switch. Three same-shaped vocabularies naming three different subjects is a trap,
and `ExportFormat` would have sat between two of them with nothing in the name to
say which. The module docstring names all three and says what separates them, so
the next author does not have to re-derive the distinction.

### The compiled cache needed nothing

A new core type embedded in a compiled registry object has to reach the
compiled-cache key or a pre-change cache could be served after it. It does,
without enrolment: the embedded-foreign-type set is derived from the compiled
models' own annotations and unwraps `Annotated` to the underlying class, so the
new enum enrols itself and its defining file's bytes fold into the key. That is
the property the earlier derivation Step bought, doing its job on the first
change that needed it.

### Verification

The relocation itself has no assertion that can distinguish it from what it
replaced, and this is the trap the change carries: a `StrEnum` member compares
and hashes equal to its own value, so every `==` and every `in` check in the
existing suite passes identically whether the field holds a member or a string.
The suite was therefore blind to the lift, and would have stayed blind to its
removal.

Three cases close that, and the discriminating one asserts on `type(...) is`
over the real bundled registry, with both shapes asserted present so it cannot
pass over an empty or single-shape tree. Restoring the bare `Literal` flips four:

```
E   assert all(<genexpr>)   # type(item) is ExportLayoutFormat
FAILED ...::test_the_bundled_registry_hydrates_every_layout_format_to_a_member
FAILED ...::test_the_stored_token_still_hydrates_to_its_member
FAILED ...::test_xml_dictionary_layout_skips_record_encoding_check
FAILED ...::test_layout_with_mixed_canonical_encodings_rejected
4 failed, 3 passed in 25.64s
```

The unrecognised-token refusal correctly does NOT flip: the bare `Literal`
refused an unknown token too, naming its own members. Its docstring says so
rather than claiming a discrimination it does not make — the enum's contribution
there is a single home the accepted set is read from, not the existence of a
refusal.

Hydration proved against the real tree before anything was committed:

```
hydrated formats: {ExportLayoutFormat.XML_DICTIONARY, ExportLayoutFormat.FIXED_WIDTH}
all enum members: True
```

Every touched suite, and the relocation's own gate:

```
8 layout / support-matrix / parity / record-spec modules   119 passed in 168.15s
conformance profile + both export suites                    62 passed in  54.42s
export layout module after the proofs added                  7 passed in  19.93s

uv run --no-sync pytest --collect-only -q
15062/18420 tests collected   (immediately before the relocation commit)
15065/18423 tests collected   (after the proofs)

uv run --no-sync python -m dev.docs.apidocs scaffold --check -> exit=0
uv run --no-sync ruff format --check src/cadrumo -> 4261 files already formatted
uv run --no-sync ty check src -> All checks passed!
```

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator
direction; the service is stopped and its index is broken. It was neither
started, restarted, reindexed nor probed. Grounding was whole-file reads of the
layout schema, the shipped support matrix and the conformance composer, plus
ripgrep sweeps for both tokens and for every `layout.format` comparison across
the shipped tree and the developer tooling.

DEVIATION from the one-commit-per-Step contract, taken deliberately. The
relocation landed as one atomic explicit-pathspec commit, as the relocation rule
requires, and the boundary proofs landed as a second. They should have been one
commit; when that was noticed the relocation was already HEAD, and amending on a
shared branch risks rewriting a peer commit that lands in the interval, which is
a categorically worse outcome than an extra commit. The tree is coherent at both
commits.

`ruff check src/cadrumo` reports one unused import in a profile-bundle CLI module
a peer is mid-edit on. It is not a file this Step touched and was left alone. The
docstring core-struct link gate reds on two `entrypoints/cli` modules for missing
cross-references, both owned by a recent peer refactor of the overview and
profile surfaces; neither is a file this Step touched and neither imports the new
enum. Both are recorded here as peer-owned rather than absorbed.

The generated-stub scaffold verb is tree-wide and left sixty other stubs marked
modified with empty content diffs — a line-ending artefact whose fix is an open
Step in this plan. Only the two stubs naming the new core module were staged;
the rest were left for their owner.

Four scripted edits round-tripped source through Python text I/O and rewrote LF
terminators to CRLF, invisibly to `git diff`. They were caught by the staging
warning, normalised back to LF against their HEAD blobs, and re-staged before the
commit. One revert of the mutation probe failed with an OSError while another
process held the schema file; it was retried until the write landed and the diff
was confirmed empty before the tree was re-verified.
