# cadrumo-data-manuals

This Cadrumo corpus companion ships source binaries under `corpus/manuals`.
It preserves their bytes and mirrored resource paths. Derived text and metadata
remain in the command-bearing `cadrumo` distribution.

The three mandatory companions partition the complete corpus binary set:

- `cadrumo-data-manuals`: `corpus/manuals`.
- `cadrumo-data-official`: `corpus/aeat_official` and `corpus/eu_official`.
- `cadrumo-data-normatives`: `corpus/normatives`.

Each stays below the existing 100 MB per-artifact limit. All contribute disjoint
portions of the implicit `cadrumo_data` namespace under
`cadrumo_data/_data/corpus`, with no namespace `__init__.py`.

Install `cadrumo` normally; its dependencies install all three companions at
the exact matching version. The root and every companion ship together.

The Apache-2.0 license covers packaging and derived work. The accompanying
NOTICE preserves attribution and the separate status of official source texts.
