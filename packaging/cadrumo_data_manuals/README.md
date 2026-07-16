# cadrumo-data-manuals

Corpus source binaries — the AEAT/BOE práctico **manuals** — for the
[`cadrumo`](https://github.com/cadrumo/cadrumo) Spanish-tax toolkit.

The command-bearing `cadrumo` wheel excludes the corpus source binaries — the
AEAT and BOE manuals (`*.pdf`) and workbooks (`*.xls`/`*.xlsx`) — that make up
roughly 94% of its weight. Those binaries are split across two sub-cap data
distributions so each stays under PyPI's 100 MB per-file cap without a size
grant:

- **`cadrumo-data-manuals`** (this package) ships `corpus/manuals`.
- **`cadrumo-data-official`** ships `corpus/aeat_official` and `corpus/normatives`.

Both ship subtrees of the same `cadrumo_data` implicit namespace package under a
mirrored `cadrumo_data/_data/corpus` tree, so `importlib.resources.files("cadrumo_data")`
spans both installed portions.

At runtime `cadrumo` resolves a corpus binary from its own package tree first and
then from these data distributions, so a full source checkout and an installed
three-wheel cohort read the corpus identically. The binaries feed the always-on
registry integrity hash chain and `aeat app registry` verification. An incomplete
cohort fails integrity checks; Cadrumo does not support a degraded CLI install
without both data distributions.

## Install

Install Cadrumo normally. Its base dependency metadata pins and installs both
data distributions at the exact matching version:

```
pip install cadrumo
```

## Versioning

`cadrumo-data-manuals` is version-locked to the `cadrumo` distribution. It and
its sibling `cadrumo-data-official` ship at the same version as `cadrumo`,
enforced by release and packaging gates. Direct installation is only for
artifact inspection; command-bearing installs should install `cadrumo`.

## License

Apache-2.0.
