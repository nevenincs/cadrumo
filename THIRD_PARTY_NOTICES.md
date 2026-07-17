# Third-party notices

Attribution notices for third-party components whose licences carry an
attribution obligation into this distribution. Dependency licences for
ordinary Python packages are declared by those packages themselves; this file
records the obligations that are NOT discharged by package metadata alone.

## Corpus search: embedding model lineage

The optional semantic half of the bundled-corpus search (the `aeat[search]`
extra) uses the **potion-multilingual-128M** static embedding model by the
Minish Lab, distributed under the **MIT licence**
(https://huggingface.co/minishlab/potion-multilingual-128M). The model is
downloaded at runtime by the user's environment; no model weights ship in
this distribution.

Model lineage attribution:

- potion-multilingual-128M is distilled with **Model2Vec** (MIT,
  https://github.com/MinishLab/model2vec) from **BAAI/bge-m3** (MIT,
  https://huggingface.co/BAAI/bge-m3).
- The distillation corpus is **C4** (Colossal Clean Crawled Corpus), made
  available by the Allen Institute for AI under the **ODC-BY 1.0** licence
  (https://huggingface.co/datasets/allenai/c4). ODC-BY requires this
  attribution notice; the C4 dataset itself is neither shipped nor
  redistributed by this project.

The corpus embedding VECTORS shipped as package data are outputs computed by
this project from its own bundled legal corpus (BOE/AEAT public legal texts)
using the model above; they contain no third-party model weights.

## Corpus search: lexical stack

- **SQLite FTS5** — public-domain SQLite, via the Python standard library.
- **snowballstemmer** — BSD-3-Clause
  (https://github.com/snowballstem/snowball). The Spanish Snowball stemming
  algorithm is used for the lexical fallback column of the corpus index.
