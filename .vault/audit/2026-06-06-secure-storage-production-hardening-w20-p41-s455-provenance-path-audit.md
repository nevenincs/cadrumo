---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
modified: '2026-06-06'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# S455 provenance path audit

## S455-001 | MEDIUM | Parser records persisted local source paths

Prior declaración, justificante, and borrador parse outputs stored local source paths in `source_pdf_path`. Those records can cross persistence and review boundaries, so the source filename and directory were too sensitive for a production-hardened secure-storage backend.

Status: resolved. Parser-produced records now use digest-derived `.secure-source/<sha256>.pdf` references while retaining `source_pdf_sha256` as the stable integrity coordinate.

## S455-002 | MEDIUM | Justificante dispatch cache keyed successful reads by resolved path

The justificante backend dispatch cache previously included the resolved filesystem path in the successful cache key. That made source locations reachable through process inspection and private cache introspection.

Status: resolved. The cache is now bounded manually and keyed by source digest, backend, byte count, and mtime.

## S455-003 | LOW | Borrador detection failure included raw source path

The unrecognised Modelo 100 artefact error interpolated the input path into the message.

Status: resolved. The detection error now uses the shared `<input-pdf>` source label and has regression coverage.

## S455-004 | INFO | Sanitizer replacement hashes are contributor-local audit metadata

The sanitizer stores `real_sha256` for cleartext token replacements inside sanitization results. Search found no production application persistence path for these rows; they are part of contributor-local fixture sanitization evidence and tests already assert cleartext absence.

Status: accepted for S455. If sanitization sidecars are promoted into runtime storage later, replace `real_sha256` with non-reversible local references before that promotion.
