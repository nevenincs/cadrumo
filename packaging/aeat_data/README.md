# aeat-data

Corpus source binaries for the [`aeat`](https://github.com/wgergely/aeat)
Spanish-tax toolkit.

The slim `aeat` runtime wheel excludes the corpus source binaries — the AEAT and
BOE manuals (`*.pdf`) and workbooks (`*.xls`/`*.xlsx`) — that make up roughly 94%
of its weight. This companion distribution ships exactly those binaries under a
mirrored `aeat_data/_data/corpus` tree.

At runtime `aeat` resolves a corpus binary from its own package tree first and
then from this companion, so a full source checkout and a split install read the
corpus identically. The binaries feed the always-on registry integrity hash
chain and the opt-in `aeat app registry` verification verbs; without this
companion those surfaces degrade with a loud advisory naming the
`aeat-cli[corpus-sources]` install hint, never silently.

## Install

Prefer the extra on the main package, which pins this companion at a matching
version:

```
pip install "aeat[corpus-sources]"
```

## Versioning

`aeat-data` is version-locked to the `aeat` distribution: both ship at the same
version, enforced by a parity gate in the `aeat` test suite. Install a version
of `aeat-data` that matches your installed `aeat`.

## License

Apache-2.0.
