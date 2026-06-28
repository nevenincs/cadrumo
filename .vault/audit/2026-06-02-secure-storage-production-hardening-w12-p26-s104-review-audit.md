---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S104]]'
---

# `secure-storage-production-hardening` Code Review

## S104-001 | LOW | Parser logs exposed filesystem-derived source names

Initial review found that `parse_borrador` logged `path.name` at debug and info level. The parser is a plaintext-exception inbound boundary and does not persist secure-storage data, but PDF basenames may contain taxpayer identifiers or other user-provided private metadata.

Resolution: replace filesystem-derived source names with the stable diagnostic placeholder `source=<input-pdf>` and add a log privacy regression test that renames a generated PDF to a NIF-like basename before parsing. The test asserts emitted log messages do not include the sensitive basename and do include the placeholder.

Status: closed.

## S104-002 | INFO | Boundary classification remains plaintext-exception

Review confirmed that `parse_borrador` composes artefact-kind detection and extractor selection, returns a typed `BorradorObservation`, and does not create a repository, write local side-store state, or bypass secure-storage persistence for application-owned data.

Status: closed.

## S104-003 | INFO | Final review found no high-severity defects

Final review found no HIGH or CRITICAL issues in the scoped S104 slice. The reviewer confirmed the new log privacy regression test is non-tautological because it creates a real generated PDF, renames it to a sensitive-looking basename, runs the parser, and asserts against emitted log messages rather than mirroring implementation logic.

Status: closed.

## S104-004 | LOW | Pre-existing detector error path can expose raw input path

Reviewer noted an adjacent pre-existing concern outside the S104 write scope: artefact-kind detection can format the raw PDF path into a parse error message. This is not a persistence or repository issue, but it is a privacy-hardening follow-up for the broader inbound PDF parser audit.

Status: open follow-up.
