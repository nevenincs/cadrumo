---
tags:
  - '#adr'
  - '#bucket-sealed-archive'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - '[[2026-06-04-bucket-sealed-archive-research]]'
---

# `bucket-sealed-archive` adr: `Sealed-archive format for bucket export/import` | (**status:** `accepted`)

## Problem Statement

`BucketMaintenanceService.export` and `.import` are the two
composition-pattern verbs left without a concrete archive format
after `2026-06-03-cli-workflow-redesign-adr` locked the composition
discipline. The ADR named the format obliquely as "tar.gz with
plaintext header + encrypted payload + recovery wrap"; this ADR
scopes that description into a concrete contract so the
implementation Step can open.

The format must satisfy four constraints. (1) The plaintext header
`ExportArchiveHeader` (already implemented at
`src/aeat/adapters/persistence/storage/bucket/_export_header.py`)
sits at a known archive position so an importer can validate the
bucket identity and manifest digest before touching the encrypted
payload. (2) The encrypted payload carries the serialised
`UserProfilePortableExport` bundle from `serialize_profile_bundle`
without exposing any plaintext beyond the header. (3) Optional
recovery-wrap material accompanies the payload when the operator
opts in, so a bundle exported on one host can be unsealed on
another host that holds the recovery passphrase. (4) The archive
total layout is verifiable byte-by-byte from the header without
trial decryption — a fast-fail path for tampered or wrong-bucket
archives.

## Considerations

The codebase's secure-storage stack already provides every
cryptographic primitive the format needs. The envelope encryption
that wraps every secure-object record (`Envelope[T]` from
`aeat.adapters.persistence.storage.envelope`) is the right pattern
for wrapping the serialised bundle: AES-GCM, versioned, classified.
The KDF parameters in the bucket manifest (`ManifestKdfParams`)
provide the password-derived key material a recovery wrap rehydrates.

Three format candidates were considered:

### Candidate 1: tar.gz with positional members

The plaintext header sits at position 0 as `header.json`; the
encrypted payload sits at position 1 as `payload.bin`; the optional
recovery wrap sits at position 2 as `recovery.wrap`. An importer
streams the tar member list, validates `header.json` against the
`ExportArchiveHeader` schema, then either decrypts payload.bin or
refuses based on header content.

Pro: tar is universally available; the streaming reader can fast-fail
on bad header without buffering the payload.
Con: tar's metadata (timestamps, ownership, permissions) leaks
host-environment information into the archive. Reproducible-build
discipline requires explicitly normalising the metadata at write.

### Candidate 2: custom binary frame format

A fixed-layout binary frame: 4-byte magic (`AESV` for "AEAT Export
Sealed Vault"), 4-byte version, 4-byte header length, header JSON,
4-byte payload length, encrypted payload, 4-byte recovery-wrap
length (0 = absent), recovery wrap bytes.

Pro: zero metadata leakage; entirely self-describing.
Con: introduces a custom format that operators cannot inspect with
standard tools; harder to debug a broken archive.

### Candidate 3: JSON envelope with base64'd encrypted payload

A single JSON document carrying the header, base64-encoded
encrypted payload, and base64-encoded recovery wrap as inline
strings.

Pro: maximally inspectable; one file format the rest of the
codebase already speaks (every secure-object record is a JSON
envelope).
Con: the base64 expansion roughly inflates payload size by 33%;
JSON parsing materialises the full payload string before
decryption; loses streaming.

## Constraints

The archive MUST NOT carry secrets in plaintext. The bucket
manifest (which includes `kdf_params.salt`) is plaintext on disk
inside the bucket directory; the export archive carries the
manifest digest, not the manifest itself. The KDF salt for the
recovery wrap is derived independently per export so two exports
of the same bucket are not bit-identical (preventing trivial
correlation of two archive files to the same bucket).

The archive MUST be importable without trusting the source. The
header carries a signature-free identity (`bucket_id`,
`manifest_digest`) that the importer cross-checks against the
sealed payload's integrity tag. A wrong-bucket archive raises
`BucketImportError` from the existing
`aeat.domain.buckets._errors` catalogue.

The recovery wrap MUST be optional. An operator who exports for
backup on the same host uses the bucket's currently-active KEK to
seal the payload and omits the recovery wrap (header carries
`recovery_wrap_present = False`). An operator who exports for
cross-host migration enrols a recovery passphrase at export time
that the importer prompts for at unseal.

## Implementation

This ADR adopts Candidate 1 (tar.gz with positional members). Tar
is the most operationally familiar format; the metadata-leak
concern is addressable via a thin write helper that pins
timestamps to the export instant and clears ownership / permissions.
Custom binary formats add maintenance burden the operator scenarios
do not justify; full-JSON loses streaming and inflates payload
size.

The archive layout:

```
archive.aeat-bucket.tar.gz
  header.json          (plaintext ExportArchiveHeader, ~256 bytes)
  payload.envelope     (binary Envelope[UserProfilePortableExport]
                        wrapping the serialised bundle, AES-GCM)
  recovery.wrap        (optional, present iff
                        header.recovery_wrap_present is True)
```

Three new modules land under
`src/aeat/adapters/persistence/storage/bucket/`:

- `_sealed_archive_writer.py` exposing
  `write_sealed_archive(target_path, header, payload_envelope,
  recovery_wrap=None)`. Writes the tar.gz with normalised metadata
  (timestamps = header.created_at, mode = 0o400, ownership = 0/0)
  so two exports of the same bucket at different instants differ
  only in the `created_at` timestamp.
- `_sealed_archive_reader.py` exposing
  `read_sealed_archive(source_path) -> SealedArchiveContents` that
  validates the tar layout (exactly two or three named members,
  named in the correct order), strict-validates the header, and
  yields the payload envelope + optional recovery wrap for the
  caller to decrypt.
- `_sealed_archive_errors.py` exposing `SealedArchiveLayoutError`
  / `SealedArchiveHeaderError` / `SealedArchivePayloadError`
  descending from the existing `BucketExportError` /
  `BucketImportError` domain errors (so the
  `BucketMaintenanceService.export` / `.import` callers route them
  through the same boundary the other maintenance verbs use).

The `BucketMaintenanceService.export` composition:

```
serialize_profile_bundle(bucket_id)
  → wrap in Envelope[UserProfilePortableExport] using the bucket's
    active KEK (or a recovery-passphrase-derived KEK when the
    operator opts in)
  → compute manifest digest from the current bucket manifest
  → build ExportArchiveHeader
  → write_sealed_archive(output_path, header, payload_envelope,
                         recovery_wrap)
  → emit BUCKET_EXPORTED
```

The `BucketMaintenanceService.import` composition:

```
read_sealed_archive(source_path)
  → validate header.bucket_id collision against existing live
    profile (refuse unless force_replace=True)
  → derive KEK (active bucket's if header.recovery_wrap_present is
    False; recovery-passphrase prompt if True)
  → decrypt payload envelope → UserProfilePortableExport
  → validate bundle_schema_version against
    SUPPORTED_BUNDLE_SCHEMA_VERSIONS
  → provision target bucket (or reuse existing if force_replace)
  → deserialize_profile_bundle(bundle, target_bucket_id)
  → emit BUCKET_IMPORTED
```

## Rationale

Tar.gz keeps the format inspectable with standard tools (`tar tf`
lists members; the header member can be `tar xf` extracted and
read as JSON) without requiring custom inspection tooling.
Positional members let the reader fast-fail on layout drift
(extra or out-of-order members raise SealedArchiveLayoutError
before any decryption attempt). Metadata normalisation closes the
host-leak concern; the export-time `created_at` is the only varying
field, which matches the existing `ExportArchiveHeader.created_at`
contract.

Two-member-or-three-member layout (with the recovery wrap as the
third) keeps the format extensible: a future archive-schema-version
bump can add new members without breaking older importers that
refuse on extra unknown members. The
`ExportArchiveHeader.archive_schema_version` field already exists;
unknown versions raise `SealedArchiveHeaderError` at the import
boundary.

Routing the new error classes under the existing
`BucketExportError` / `BucketImportError` hierarchy preserves the
single error-catalogue path the rest of the maintenance verbs use.
The CLI boundary `command_error_boundary` already understands the
`BucketMaintenanceError` ancestor; no new error-code registry
entries are needed beyond the new class declarations + their
`ErrorCode` registrations.

## Consequences

The export / import verbs become two focused commits each: writer
+ reader infrastructure lands as preconditions, then each verb
lands its composition method + Pydantic contracts + tests in one
atomic commit per the relocation-atomicity rule.

The metadata-normalisation discipline (timestamps, mode, ownership)
is the maintenance burden of choosing tar over a custom binary
format. It is bounded — a thin `_normalised_tarinfo` helper applies
the normalisation consistently for every archive member — but
future agents adding members must use the helper, not naked
`tarfile.TarInfo`. Codified as the rule slug below.

The recovery-wrap path adds a per-export passphrase prompt to the
CLI surface. The operator-UX implication is that cross-host export
becomes a two-step ritual (prompt for passphrase at export, prompt
for the same passphrase at import on the destination host) instead
of the one-step same-host backup. This matches operator
expectations for the cross-host migration use case.

The decision NOT to ship a JSON-only or custom-binary alternative
forecloses two design paths. JSON's universal inspectability and a
custom binary's zero-metadata-leakage are each gained partially via
the tar.gz + metadata-normalisation hybrid; if a future operator
need forces a different choice, this ADR is superseded rather than
amended.

## Codification candidates

- **Rule slug:** `sealed-archive-metadata-normalisation`.
  **Rule:** Any module that writes members into a sealed-archive
  tar via `tarfile.TarInfo` MUST use the
  `_normalised_tarinfo(name, instant)` helper from
  `aeat.adapters.persistence.storage.bucket._sealed_archive_writer`,
  never construct `TarInfo` directly. The helper pins timestamps,
  mode, and ownership so two same-bucket exports differ only in
  the header's `created_at` field. Held until the writer lands and
  a second tar-bearing module surfaces.
