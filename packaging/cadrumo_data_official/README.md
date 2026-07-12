# cadrumo-data-official

Corpus source binaries — the **official** AEAT diseños de registro / workbooks
and normative PDFs — for the [`cadrumo`](https://github.com/nevenincs/cadrumo)
Spanish-tax toolkit.

The slim `cadrumo` runtime wheel excludes the corpus source binaries — the AEAT and
BOE manuals (`*.pdf`) and workbooks (`*.xls`/`*.xlsx`) — that make up roughly 94%
of its weight. Those binaries are split across two sub-cap companion
distributions so each stays under PyPI's 100 MB per-file cap without a size
grant:

- **`cadrumo-data-official`** (this package) ships `corpus/aeat_official` and
  `corpus/normatives`.
- **`cadrumo-data-manuals`** ships `corpus/manuals`.

Both ship subtrees of the same `cadrumo_data` implicit namespace package under a
mirrored `cadrumo_data/_data/corpus` tree, so `importlib.resources.files("cadrumo_data")`
spans both installed portions.

At runtime `cadrumo` resolves a corpus binary from its own package tree first and
then from these companions, so a full source checkout and a split install read
the corpus identically. The binaries feed the always-on registry integrity hash
chain and the opt-in `cadrumo app registry` verification verbs; without both
companions those surfaces degrade with a loud advisory naming the
`cadrumo[corpus-sources]` install hint, never silently.

## Install

Prefer the extra on the main package, which pins both companions at a matching
version and installs them together:

```
pip install "cadrumo[corpus-sources]"
```

## Versioning

`cadrumo-data-official` is version-locked to the `cadrumo` distribution: it and its
sibling `cadrumo-data-manuals` ship at the same version as `cadrumo`, enforced by a
parity gate in the `cadrumo` test suite. Install a version that matches your
installed `cadrumo`.

## License

Apache-2.0.
