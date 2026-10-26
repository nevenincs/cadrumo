---
tags:
  - '#audit'
  - '#bundled-data-consumers'
date: '2026-08-15'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:954d010c708de0506c62f1c38bd1d9628466989999da1a7ee163d5544e000e26'
related: []
---

# `bundled-data-consumers` audit: `Bundled _data consumer audit`

## Scope

Every subtree of the bundled package-data root `src/cadrumo/_data/` was matched
to an actual runtime consumer, to settle a concern that docs-generated or
superseded material had been compiled into production. Five subtrees were
audited: `registry/`, `corpus/`, `manual_corpus_text/`, `terminology/` and
`agent/`. Consumption was traced through the three bundled-data seams in
The retired module (`bundled_path`, `packaged_data`,
`resolve_corpus_binary`), through registry `corpus_ref` grounding strings, and
through directory-scanning loaders. Reference integrity was then verified
programmatically rather than by inspection.

## Findings

### bundled-data-consumers | low | Every _data subtree has a genuine production consumer

All five subtrees resolve to live readers. `registry/` is loaded whole by
`ValidatedRegistryAuthority` from roughly twenty call sites. `terminology/concepts/`
is read by the retired module and surfaced by
the MCP terminology search tool. `manual_corpus_text/` is read by
The retired module. `agent/` is
scanned by the retired module. Within `corpus/`, `normatives/html` is
scanned by the lexical index, `aeat_official` backs the einvoice record schemas and
several core code tables, `manuals` is catalogue-driven, and `manual_oracles` plus
`parity_replays` back external grounding. No superseded or docs-generated tree was
found in production data.

### bundled-data-consumers | medium | Indirect corpus_ref consumers are invisible to path grepping

`corpus/eu_official` and `corpus/facturae` carry no Python path reference anywhere
in the tree and appear orphaned under direct-reference search. They are in fact
consumed indirectly, as `corpus_ref` grounding targets declared in
`registry/aeat/legal/iva-rates.toml` and `registry/aeat/iva/country_names.toml`.
Any future sweep that condemns bundled data on absence of a Python reference will
delete live regulatory grounding. Bundled-data reachability must be assessed
across all three mechanisms: direct path, registry grounding reference, and
directory scan.

### bundled-data-consumers | low | Reference and sidecar integrity are clean

All 633 assigned `corpus_ref` fields across the registry resolve to existing
files; zero dangle. All 1,324 `.extracted.md` and `.extracted.json` companions
have a parent source; zero orphaned. All 117 `manual_corpus_text` sidecars have a
source in `corpus/`; zero orphaned. The 39 source binaries carrying no
`.extracted.*` companion are covered instead by `manual_corpus_text` and gated by
the corpus sidecar-freshness suite, so they are not a gap.

### bundled-data-consumers | low | Stale product name in five harness docstrings

Five docstrings described the bundled harness root as `aeat/_data/agent/`. The
Python package is `cadrumo`; `aeat` names only the CLI executable, so the path was
never correct. Corrected in the retired module,
The retired module and the agent harness test.

### bundled-data-consumers | low | Obsolete placeholder and build residue in the data tree

`registry/aeat/authorization.d/.gitkeep` declared itself as keeping an empty
directory tracked, but the directory now holds thirty per-modelo enrollment
fragments. Its default-deny note is already the governing principle documented in
The retired module, so the file was removed without
losing the statement. Four orphaned bytecode files from crashed parallel runs were
also cleared from the corpus test cache directory.

### bundled-data-consumers | low | Shipped-tree test reached a private dev symbol

The retired test imported the
private `_extract_raw_text` from `dev/corpus/extract_manual_corpus_text.py`. The
gate legitimately needs that exact extraction to prove committed sidecars still
equal current output, so the symbol was promoted to the public `extract_raw_text`
rather than the reach being removed. The test tree placement itself is compliant
and excluded from both wheel and sdist; only the private reach was a defect.

## Recommendations

Treat bundled-data reachability as a three-mechanism question. A future audit or
cleanup sweep must check direct path references, registry `corpus_ref` grounding,
and directory-scanning loaders before concluding that any bundled file is
unreferenced; two of the corpus subtrees are reachable only through the second
mechanism.

Preserve the separation this campaign established between shipped product data and
build-time development inputs. Four docs-search artifacts that no runtime consumer
read were relocated out of the package data tree in the same change; the remaining
contents of `_data/` are all runtime-consumed, and new build-time inputs belong
beside their owning harness under `dev/` rather than in `_data/`.

No architecturally significant decision arises from this audit; no follow-on ADR is
required.
