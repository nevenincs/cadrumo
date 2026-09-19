---
tags:
  - '#audit'
  - '#bundled-data-consumers'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:1bfc0da2ca86af5f4dce1188f9ed1d201aa45b609c7d965cb9460871432b861c'
related: []
---

# `bundled-data-consumers` audit: `Bundled _data consumer audit`

## Scope

Every subtree of the bundled package-data root `src/cadrumo/_data/` was matched
to an actual runtime consumer, to settle a concern that docs-generated or
superseded material had been compiled into production. Five subtrees were
audited: `registry/`, `corpus/`, `manual_corpus_text/`, `terminology/` and
`agent/`. Consumption was traced through the three bundled-data seams in
`src/cadrumo/core/resources/_boundary.py` (`bundled_path`, `packaged_data`,
`resolve_corpus_binary`), through registry `corpus_ref` grounding strings, and
through directory-scanning loaders. Reference integrity was then verified
programmatically rather than by inspection.

## Findings

### bundled-data-consumers | low | Every _data subtree has a genuine production consumer

All five subtrees resolve to live readers. `registry/` is loaded whole by
`ValidatedRegistryAuthority` from roughly twenty call sites. `terminology/concepts/`
is read by `src/cadrumo/application/corpus_search/_terminology.py` and surfaced by
the MCP terminology search tool. `manual_corpus_text/` is read by
`src/cadrumo/domain/calculations/registry/_validate_evidence.py`. `agent/` is
scanned by `src/cadrumo/agent/__init__.py`. Within `corpus/`, `normatives/html` is
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
never correct. Corrected in `src/cadrumo/agent/__init__.py`,
`src/cadrumo/entrypoints/mcp/_resources.py`,
`src/cadrumo/entrypoints/mcp/_harness_tools.py` and the agent harness test.

### bundled-data-consumers | low | Obsolete placeholder and build residue in the data tree

`registry/aeat/authorization.d/.gitkeep` declared itself as keeping an empty
directory tracked, but the directory now holds thirty per-modelo enrollment
fragments. Its default-deny note is already the governing principle documented in
`src/cadrumo/core/access_gate/_authorization.py`, so the file was removed without
losing the statement. Four orphaned bytecode files from crashed parallel runs were
also cleared from the corpus test cache directory.

### bundled-data-consumers | low | Shipped-tree test reached a private dev symbol

`src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py` imported the
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
