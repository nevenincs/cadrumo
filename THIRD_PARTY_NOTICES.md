# Third-party notices

Attribution notices for third-party components whose licences carry an
attribution obligation into this distribution. Dependency licences for
ordinary Python packages are declared by those packages themselves; this file
records the obligations that are NOT discharged by package metadata alone.

## Corpus search: retrieval stack

The bundled-corpus search is lexical and fully offline. It uses no embedding
model, downloads nothing, and produces no vectors, so no model-lineage
attribution arises from it.

- **SQLite FTS5** — public-domain SQLite, via the Python standard library.
- **snowballstemmer** — BSD-3-Clause
  (https://github.com/snowballstem/snowball). The Spanish Snowball stemming
  algorithm backs the stemmed column of the corpus and command indexes.

## Runtime dependency licence disclosure

The `cadrumo` distribution contains only this project's own code
(Apache-2.0). It does not vendor or bundle any third-party package; declared
dependencies are resolved and installed separately by the user's installer
from PyPI under their own licences. Two declared dependencies carry
non-permissive licences and are disclosed here explicitly:

- **ofxtools** — GPL-3.0-only (https://github.com/csingley/ofxtools). An
  OPTIONAL dependency, gated behind the `ofx` extra
  (`pip install cadrumo[ofx]`), backing the OFX/QFX bank-statement import
  provider; a bare-core install carries no strong-copyleft dependency at all.
  Apache-2.0 is one-way compatible with GPL-3.0, so a combined installation
  is lawful; however, anyone who redistributes `cadrumo` TOGETHER WITH the
  installed `ofx` extra (a container image, a frozen binary, a vendored
  bundle) must comply with the GPL-3.0 for the combined work. This project
  itself ships no such combined artifact: the PyPI wheels contain no
  third-party code, and optional dependencies are resolved on the user's
  machine.
- **pikepdf** — MPL-2.0 (https://github.com/pikepdf/pikepdf), used for PDF
  sanitisation. MPL-2.0 is a file-level licence; it imposes obligations only
  on modified MPL-covered files, none of which this project modifies or
  ships. `certifi` (MPL-2.0, transitive via httpx) is in the same category.

Every other declared dependency (direct and transitive) carries a permissive
licence (MIT, BSD, Apache-2.0, ISC, PSF, Zlib, or equivalent) as recorded in
its own package metadata.

## Bundled AEAT / BOE corpus: reuse of public-sector information

The corpus under `src/cadrumo/_data/corpus/` (and its companion distributions
`cadrumo-data-manuals` and `cadrumo-data-official`) reproduces official Spanish
public-sector documents: consolidated legal texts from the Boletín Oficial
del Estado (BOE) and manuals, diseños de registro, and workbooks published
by the Agencia Estatal de Administración Tributaria (AEAT).

- Legal and regulatory texts (leyes, reales decretos, órdenes, resoluciones)
  are excluded from copyright protection by Article 13 of the Spanish
  intellectual-property law (Real Decreto Legislativo 1/1996, TRLPI).
- AEAT- and BOE-published documents are reused as public-sector information
  under Ley 37/2007 on the reuse of public-sector information and the
  publishing bodies' general reuse terms: the source and publication are
  identified per document (see the registry `source_refs` and the corpus
  sidecar metadata), the content is not altered, and no official status,
  sponsorship, or endorsement is claimed or implied.
- The Apache-2.0 licence of this repository and of the data distributions
  covers the project's own packaging, structure, extraction, and derived
  works (registry TOML, extracted text, indexes). It does not —
  and cannot — relicense the underlying official documents, which remain
  governed by the public-sector rules above and remain attributed to their
  publishing bodies.

## Documentation web fonts

The documentation site under `docs/_static/` self-hosts subset `.woff2`
builds of the following typefaces, each distributed under the
**SIL Open Font License 1.1** (https://openfontlicense.org):

- **Hanken Grotesk** — Copyright 2020 The Hanken Grotesk Project Authors
  (https://github.com/marcologous/hanken-grotesk).
- **Instrument Serif** — Copyright 2022 The Instrument Serif Project Authors
  (https://github.com/Instrument/instrument-serif).
- **JetBrains Mono** — Copyright 2020 The JetBrains Mono Project Authors
  (https://github.com/JetBrains/JetBrainsMono).

The README demo recording uses **Cascadia Mono** (SIL OFL 1.1); its licence
text ships alongside the font under `docs/_static/readme/fonts/`.
