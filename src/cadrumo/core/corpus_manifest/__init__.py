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

There is no human CLI for corpus verification. This module's API is the
whole surface: :func:`build_corpus_manifest`, :func:`verify_corpus_manifest`,
and :func:`save_corpus_manifest`, re-exported through
``cadrumo.adapters.persistence.storage`` and driven programmatically by its
consumers. The same API owns manifest regeneration after an intentional
corpus update.

This module also builds and verifies distributable corpus *bundles*: a
single ``.zip`` archive carrying every corpus file plus an embedded
:class:`CorpusManifest` (see :func:`build_corpus_bundle` and
:func:`verify_corpus_bundle`), for offline installation of the bundled
corpus checksummed against its own manifest. The SHA-256 manifest alone is
an integrity gate, not an authenticity gate; :mod:`._bundle_signing`
(re-exported here) adds the Ed25519 authenticity layer on top -- see
:func:`sign_corpus_bundle` and :func:`verify_corpus_bundle_signature`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
