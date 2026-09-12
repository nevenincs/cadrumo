"""Directory-level integrity manifest for CORPUS-class on-disk data.

The substrate's :class:`SensitivityClass.CORPUS` policy mandates
SHA-256 integrity tracking for plaintext-at-rest reference material.
This module is the canonical implementation: a single manifest model
covers every file under a corpus root with a per-file SHA-256 + size
record, plus a self-attesting ``manifest_sha256`` so a manifest-only
tamper is detectable.

Manifests are plaintext JSON on disk (corpus material is plaintext;
the manifest is the integrity gate, not the secrecy gate). Per-record
fields are validated against path-traversal at construction.

There is no human CLI for corpus verification. Consumers import manifest and
bundle operations from their defining modules; this package initializer is
inert. The same operations own manifest regeneration after an intentional
corpus update.

This module also builds and verifies distributable corpus *bundles*: a
single ``.zip`` archive carrying every corpus file plus an embedded
:class:`CorpusManifest` (see :func:`build_corpus_bundle` and
:func:`verify_corpus_bundle`), for offline installation of the bundled
corpus checksummed against its own manifest.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
