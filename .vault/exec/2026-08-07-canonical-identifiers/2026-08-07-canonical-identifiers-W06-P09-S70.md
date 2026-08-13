---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b177fecd81f286e98d896123fef430fe73ccfb2ab9b8f0005da750a3f121a912'
step_id: 'S70'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# cross-object taxpayer-identity guard on `build_complementaria`

## Scope

- `src/cadrumo/application/filing/_complementaria.py`

## Description

- Confirmed by semantic search that no cross-object taxpayer-identity guard
  exists on the filing path before writing one. The nearest existing guard
  is `_assert_read_belongs_to_this_profile` in
  `src/cadrumo/application/user_profile/_censo_sync.py`, which answers
  ownership of an AEAT censal READ against the active profile and raises
  `CensalIdentityMismatchError`. Different objects, different path,
  different error taxonomy, and its parameter is an `EffectiveFact` — not
  reusable here, so its RULING was mirrored rather than its code. The other
  neighbour, the profile repository's duplicate-tax-id refusal, compares
  profiles at registration, not a filing against the draft it amends.
- Added `_require_one_taxpayer_identity` and called it from
  `build_complementaria` immediately after the existing modelo/period
  coherence check, so it fires BEFORE `_merge_inputs`, before
  `_require_original_registry_snapshot`, and before `build_draft`. A guard
  placed after the merge has already assembled the divergent object.
- Refusal is `ModeloBuilderError` — the same error the sibling
  preconditions in this function raise — carrying an instructive English
  message that names the field and both observed identities, a
  `translated_message` locale key, and a `context` mapping supplying
  `submitted_tax_id` and `draft_tax_id` for the localised rendering.
- Added three locale keys with real values in all four catalogues
  (`en`, `es`, `ca`, `hu`) through `dev.locales set`, then ran `scaffold`
  and `scaffold --check` (all four report ok). No entry was added to the
  intentional-identical allowlist; the twelve values are genuinely
  distinct per locale, using the register the existing filing-error block
  already uses in each language: `complementaria`/`contribuyente` in
  Spanish, `complementària`/`contribuent` in Catalan, and
  `kiegészítő bevallás (complementaria)`/`adózó`/`vázlat` in Hungarian.
- Added four regression tests: the agreeing direction builds and the
  rebuilt draft carries that one identity; a divergent pair refuses with
  both identities in the message and nothing persisted; a blank identity
  refuses; a checksum-invalid identity refuses as unconfirmable rather
  than as a different taxpayer.

## Outcome

COMPLETE. The guard, its four regression tests, and the four locale
catalogues land in one commit. Ten of ten tests in the complementaria
module pass; `ruff check`, `ruff format --check`, `ty` and `pyrefly` are
clean on both changed modules.

### Comparison-semantics ruling: canonicalise the submitted side, then compare

The submitted side is routed through `validate_spanish_tax_id` and the
resulting canonical string is compared for exact equality against the
draft's stored value. This is NOT a second normalisation form: it is the
same authority `SubjectTaxId` runs as its pydantic `AfterValidator`, so
the value being compared is the same canonical, separator-stripped,
checksum-checked form the draft's own field type already produced.

The asymmetry is the reason it is applied on one side only. The draft's
`profile_tax_id` is `SubjectTaxId`-typed on a pydantic model, so a loaded
draft cannot carry a non-canonical or checksum-invalid value; re-running
the validator on it would be idempotent noise, and a branch handling its
failure would be unreachable. The submitted side's `profile_tax_id` is a
`Protocol` attribute, and `@runtime_checkable` confirms only that the
attribute exists by name — never its value — as the `W06.P09.S45` record
established. So the canonicalisation is applied exactly where the
validation is missing.

Routing it through the authority rather than comparing raw strings closes
two opposite failures at once, the same pair the censal ownership guard
records: a malformed identity must not confirm ownership merely by
matching character for character, and one identity written two ways
(`12345678-Z` against `12345678Z`) must not read as two taxpayers. If the
draft side were somehow not canonical, the comparison refuses as a
divergence — fail-closed, never fail-open.

`same_tax_identifier` was considered and rejected. It is deliberately
checksum-free so a non-resident bearer stays comparable; here both sides
are declared Spanish filing subjects typed `SubjectTaxId`, so a malformed
value is corruption of the record rather than a foreign identifier, and
the weaker predicate would accept it.

### None/absent ruling: refuse, do not pass through

A blank, whitespace-only or absent submitted identity refuses with its own
message rather than passing through. The field is non-optional at both
declaration sites — `ModeloDraft.profile_tax_id` is `SubjectTaxId`, and
`ModeloPresentado.profile_tax_id` is `SubjectTaxId` with `min_length=1` —
so absence is corruption of the record, not an exempt state. A
pass-through would carry a missing identity into the rebuilt draft's
content address, and the eventual failure would surface as a raw pydantic
validation error from inside `build_draft` rather than as a precondition
refusal like every other check in this function.

The draft side gets no absence branch: `SubjectTaxId` refuses an empty
value at the model boundary, so a loaded draft cannot present one, and an
unreachable branch with its own locale key would be unfalsifiable weight.

### Bite proof

Both proofs are runtime monkeypatches applied from throwaway pytest
plugins held OUTSIDE the repository, loaded by `PYTHONPATH` and `-p`.
Nothing under `src` was edited, so no residue could be swept into a peer's
commit.

Proof one neutralises the guard itself by rebinding
`_require_one_taxpayer_identity` to a no-op. All three refusal tests red
and the agreeing-direction test stays green, which also shows that test is
not an artefact of the guard:

```
E   Failed: DID NOT RAISE ModeloBuilderError
FAILED ...::test_divergent_taxpayer_identity_refuses_before_the_amendment_is_built
FAILED ...::test_absent_submitted_taxpayer_identity_refuses_rather_than_passing_through
FAILED ...::test_malformed_submitted_taxpayer_identity_refuses_as_unconfirmable
3 failed, 1 passed
```

Proof two strips only the canonicalisation, rebinding the module-global
`validate_spanish_tax_id` to an identity function so the guard compares
raw declared strings. Exactly one test reds — the one that pins the
ruling — and its message shows the defect the ruling exists to prevent: a
value that names nobody reported as a different taxpayer.

```
E   AssertionError: Regex pattern did not match.
E     Expected regex: 'is not a valid NIF, NIE or CIF'
E     Actual message: "complementaria taxpayer identity diverges: the submitted
      filing declares profile_tax_id '00000000X' and the original draft declares
      '00000000T'; both must name one taxpayer"
1 failed, 3 passed
```

Both plugins were removed after the runs; the tree is unmodified by them.

## Notes

- ABSORBED IN-SCOPE REGRESSION. Every test in the complementaria test
  module was already red at `HEAD` before this work started, unrelated to
  the guard: the commit retiring `JustificanteCsv` onto the canonical
  `AeatCsv` tightened `ModeloPresentado.justificante_csv` to
  `^[A-Z0-9]{8,32}$` and swept thirteen files, but missed this one, so its
  `"CSV-ORIGINAL"` fixture literal no longer validates. Fixed by replacing
  the literal with a named constant carrying a CSV in the shape the type
  declares. The AEAT Código Seguro de Verificación carries no separators,
  so the hyphenated placeholder was never a CSV the record could hold.
- BLOCKED THEN CLEARED. The first two test runs failed tree-wide with
  `RegistryLoadError: ... iva-dana-2024.toml: duplicate catalogue ids
  legal=['real-decreto-ley-7-2024:art-11']`, from an UNTRACKED
  legal-catalogue file a peer was actively authoring (its mtime advanced
  between polls). It was left strictly alone; a later re-run was green
  once the peer settled it. No work of theirs was touched.
- FINDING, DECLINED — out of this row's scope, reported to the plan lead
  rather than absorbed. `build_complementaria` rebuilds the amended draft
  from `original_submission.modelo` while taking `original_draft.period`
  for the same rebuild, mixing the two objects' coordinate axes even
  though a preceding check has already proved both agree. The check makes
  it currently harmless, but it leaves that guard load-bearing for a
  reason its own message does not state. One guard, one function was the
  instruction; widening to the coordinate axes is a separate row.
- The three locale keys are the honest minimum for the three
  distinguishable operator situations — nothing declared, something
  declared that names nobody, and something declared that names somebody
  else. Each needs a different action from the operator, so folding them
  into one key would cost the operator the diagnosis. A side-naming token
  was deliberately not interpolated into any message: an untranslated
  English token inside a localised string is the shape the locale gates
  exist to prevent.
