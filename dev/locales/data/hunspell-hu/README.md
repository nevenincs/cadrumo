# Hungarian spelling data

`hu_HU.aff` and `hu_HU.dic` are the unmodified Magyar Ispell 1.8 files from
LibreOffice dictionaries at the revision and SHA-256 digests in `source.json`.
They are checked locally before parsing; no network access is needed at audit
time. The upstream copyright and license notice is in `UPSTREAM-README.txt`;
this copy is distributed under MPL-2.0, whose text is in `MPL-2.0.txt`.

The npm normalization of this same dictionary merges some words with their
morphological metadata and encodes characters as entities. It therefore misses
valid inflections and accepts concatenations such as `őketén`. Retaining the
original files avoids inferring repairs from individual words.
