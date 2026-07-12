# aeat-data-official

Corpus source binaries — the **official** AEAT diseños de registro / workbooks
and normative PDFs — for the [`aeat`](https://github.com/wgergely/aeat)
Spanish-tax toolkit.

The slim `aeat` runtime wheel excludes the corpus source binaries — the AEAT and
BOE manuals (`*.pdf`) and workbooks (`*.xls`/`*.xlsx`) — that make up roughly 94%
of its weight. Those binaries are split across two sub-cap companion
distributions so each stays under PyPI's 100 MB per-file cap without a size
grant:

- **`aeat-data-official`** (this package) ships `corpus/aeat_official` and
  `corpus/normatives`.
- **`aeat-data-manuals`** ships `corpus/manuals`.

Both ship subtrees of the same `aeat_data` implicit namespace package under a
mirrored `aeat_data/_data/corpus` tree, so `importlib.resources.files("aeat_data")`
spans both installed portions.

At runtime `aeat` resolves a corpus binary from its own package tree first and
then from these companions, so a full source checkout and a split install read
the corpus identically. The binaries feed the always-on registry integrity hash
chain and the opt-in `aeat app registry` verification verbs; without both
companions those surfaces degrade with a loud advisory naming the
`aeat-cli[corpus-sources]` install hint, never silently.

## Install

Prefer the extra on the main package, which pins both companions at a matching
version and installs them together:

```
pip install "aeat-cli[corpus-sources]"
```

## Versioning

`aeat-data-official` is version-locked to the `aeat` distribution: it and its
sibling `aeat-data-manuals` ship at the same version as `aeat`, enforced by a
parity gate in the `aeat` test suite. Install a version that matches your
installed `aeat`.

## License

Apache-2.0.

## Licence and reuse of official content

The Apache-2.0 licence of this distribution covers the project's packaging,
file layout, and derived metadata — not the underlying official documents.
The corpus binaries reproduce official Spanish public-sector documents
(BOE consolidated legal texts; AEAT manuals, diseños de registro, and
workbooks). Legal and regulatory texts are excluded from copyright by
Article 13 TRLPI (Real Decreto Legislativo 1/1996); AEAT/BOE publications
are reused as public-sector information under Ley 37/2007 and the
publishing bodies' general reuse terms: sources are identified per document,
content is unaltered, and no official status or endorsement is claimed.
This distribution is published by an independent project with no relation
to the AEAT. See the repository's `THIRD_PARTY_NOTICES.md` and `NOTICE`.
