# aeat-data-manuals

Corpus source binaries — the AEAT/BOE práctico **manuals** — for the
[`aeat`](https://github.com/wgergely/aeat) Spanish-tax toolkit.

The slim `aeat` runtime wheel excludes the corpus source binaries — the AEAT and
BOE manuals (`*.pdf`) and workbooks (`*.xls`/`*.xlsx`) — that make up roughly 94%
of its weight. Those binaries are split across two sub-cap companion
distributions so each stays under PyPI's 100 MB per-file cap without a size
grant:

- **`aeat-data-manuals`** (this package) ships `corpus/manuals`.
- **`aeat-data-official`** ships `corpus/aeat_official` and `corpus/normatives`.

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

`aeat-data-manuals` is version-locked to the `aeat` distribution: it and its
sibling `aeat-data-official` ship at the same version as `aeat`, enforced by a
parity gate in the `aeat` test suite. Install a version that matches your
installed `aeat`.

## License

Apache-2.0.
