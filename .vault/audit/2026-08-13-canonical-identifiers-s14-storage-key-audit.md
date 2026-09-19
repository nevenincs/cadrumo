---
tags:
  - '#audit'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:02dc0f3940213478b5167f31a9b418610a5c177226c345c306c93ed71151f65b'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# `canonical-identifiers` audit: `S14 storage-key audit`

## Scope

Read-only review of the CSV-addressed secure-object route required by
`W02.P03.S14`. The review covers `JustificanteRepository.extract_identifier`,
the shared `SecureBoundRepository` save/load/enumeration paths, the registered
`JUSTIFICANTE_METADATA_NAMESPACE` grammar, and the nearby live-capture
snapshot route needed to distinguish payload coexistence from key derivation.

The production target remained unchanged. Existing real encrypted-storage
contracts were exercised rather than a synthetic replacement.

## Findings

### csv-natural-key-single-home | low | One registered namespace derives a key from CSV

`JustificanteRepository.extract_identifier` returns `payload.csv` unchanged.
The inherited write, targeted load, identifier enumeration, and payload
enumeration all use that same natural identifier in the
`cadrumo.domain.justificante.metadata` namespace. Its sole registered grammar
is `{csv}`. The SQL column stores the deterministic HMAC digest of that one
natural key, and the payload AEAD binds the same digest. Those cryptographic
derivations are encodings of the one row identity, not additional CSV key
grammars.

The nearby live-capture snapshot stores CSV in its encrypted payload but keys
the row as `justificante-capture-snapshot:{bucket_id}:{snapshot_id}`. Its
snapshot id is derived from the filing axis and the PDF content digest, not
CSV. It therefore remains outside the CSV-key inventory.

The key has one forward-lookup asymmetry for `W08` to adjudicate: writes use the
already-normalised `AeatCsv` payload value, while two targeted reads accept a
plain external evidence reference and pass it to `load` without uppercasing.
A lowercase spelling can therefore miss the stored uppercase key and produce a
false missing-evidence refusal. This audit records the defect as input to the
explicit key-composition decision; `S14` is an enumeration row and does not
change that read contract.

## Recommendations

- `W08.P12`/`S51` should treat `{csv}` in
  `JUSTIFICANTE_METADATA_NAMESPACE` as the one CSV natural-key grammar.
  Any key-composition decision applies through that registry authority; it
  must not create a CSV-specific parallel composer or treat snapshot ids,
  HMAC digests, AEAD associated data, or secure-reference strings as
  separately CSV-derived storage keys.
- `W08.P12` must decide the read-side normalization defect together with that
  one grammar, so every keyed read composes the same canonical value as the
  write path rather than introducing a second CSV-key normalizer.
- Preserve the existing real-storage identity checks: targeted load compares
  the requested natural key with the decrypted payload identity, and
  namespace enumeration recomputes the digest from that identity before
  yielding it.
