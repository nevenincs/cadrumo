---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S28'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# parse each bundled oracle payload through a strict typed model so the declared source_kind token actually hydrates and an unknown token refuses at the boundary, removing the last untyped mapping read in the grounding fold

## Scope

- `src/cadrumo/domain/calculations/registry/_external_grounding.py`
- `src/cadrumo/core/_external_oracle_corpus.py`
- `src/cadrumo/domain/calculations/registry/tests/test_external_oracle_payload_boundary.py`

## Description

The claim this Step closes: `ExternalOracleCorpus` documented that its
`aeat_manual_worked_example` member was byte-identical to the `source_kind`
token stored in the manual-oracle payloads, "so a stored token hydrates to its
member and an unknown token is refused at the boundary rather than silently
reclassified". Nothing read that token. `_read_oracle_payload` decoded each file
with `json.loads` and pulled `modelo`, `filing_year`, and
`expected_by_casilla_id` off the resulting mapping with bare `.get()` calls;
the corpus was assigned purely from the directory-to-enum map. A payload
declaring the other corpus, or any garbage string, was classified by which
folder it sat in, and `evidence_corpora` reported a provenance the figures did
not have. Nothing was refused anywhere.

- Add `_coerce_external_oracle_corpus` and the `ExternalOracleCorpusValue`
  annotated alias, following the registry's established boundary-hydration
  idiom (`InputKindValue`, `RevisionReviewStatusField`): a stored JSON string
  coerces to its enum member, and an unrecognised token raises
  `RegistryValidationError` enumerating the accepted set. Strict pydantic mode
  refuses a bare string outright, so without the coercer the enum could not be
  a field type at all — which is why the hydration claim had never been wired.
- Add three strict frozen models. `BundledOraclePayload` carries the genuine
  intersection of both corpora, the evidence locator and the expected-value
  map. `ManualWorkedExamplePayload` declares every attribution axis this corpus
  actually stores, `source_kind` among them, all required.
  `RentaWebOpenReplayPayload` declares the simulator's rendered labels and its
  as-observed figures, and models modelo, filing year, and `source_kind` as
  optional with no value-bearing default, because that corpus declares none of
  the three. A default would have answered the cross-check with the very token
  it verifies.
- Add `_parse_oracle_payload`, which routes each file through its corpus's
  model and then cross-checks the hydrated token against the directory the file
  was found in, refusing a contradiction by name. The refusal quotes both the
  declared token and the directory, so the diagnostic states the disagreement
  rather than the conclusion.
- Rewrite `_read_oracle_payload` to consume the parsed model. Every payload is
  parsed first, including one the filename cannot attribute: a file the fold
  cannot place is still a file whose contents must be well-formed, and
  validating only the attributable ones would leave the boundary open exactly
  where least is known. The filename stays the attribution key; widening
  attribution to the declared fields is Step S25's decision, not this one.
- Correct the enum docstring to describe what the code now does, and correct
  the S05 exec record, which asserted the hydration as landed when it was not.

The `source_kind` axis is now load-bearing in three independent ways: an
unknown token fails hydration, a known token contradicting its directory fails
the cross-check, and an omitted token fails the manual corpus's required field.
Each is a refusal, none a warning.

## Outcome

Both refusals reproduce against a real bundled payload with one field mutated.
Contradicting token:

```
RegistryValidationError: modelo-100-2020-estimacion-directa-simplificada.json:
declared source_kind 'renta_web_open_replay' contradicts the corpus directory
'manual_oracles', which holds the 'aeat_manual_worked_example' corpus
```

Unrecognised token:

```
RegistryValidationError: ... does not satisfy ManualWorkedExamplePayload:
1 validation error for ManualWorkedExamplePayload
source_kind
  Value error, source_kind 'hand_computed_by_the_author' is not a recognised
  ExternalOracleCorpus member; expected one of ['renta_web_open_replay',
  'aeat_manual_worked_example']
```

The same file with its original token loads to
`ExternalOracleEvidence(corpus=AEAT_MANUAL_WORKED_EXAMPLE, modelo='100',
filing_year=2020, casilla_ids=('0226',))`, so each refusal is caused by the
mutated field and not by a fixture that was broken to begin with.

Gates. The new `test_external_oracle_payload_boundary.py` carries ten cases and
is marked `unit`, so it is selected by the repository's default lane
(`-m 'unit and not external_tool and not os_keychain'`) rather than sitting in a
lane nothing runs: `10 passed in 0.42s`. The pre-existing grounding gate was
`3 passed in 3.66s` before the change and `3 passed in 3.43s` after, with both
honesty directions and the payload-accounting assertion untouched; the
attribution logic, the finding kinds, and the emitted rows are unchanged.

Two anti-tautology mutations flip real assertions. Deleting the corpus
cross-check yields `2 failed, 8 passed`, failing exactly the two
contradiction cases and nothing else. Relaxing `source_kind` on the manual
model back to optional yields `1 failed, 9 passed`, failing exactly the
omission case. Neither mutation kills the fixture floors, so the cases pin
behaviour rather than merely proving the code was reached.

Behaviour neutrality was proved by direct comparison rather than by the fold's
summary numbers, because a peer landed a corpus rename mid-run. A probe read
every payload on disk twice, once through the retired `.get()` logic and once
through the new reader, and compared the full attributed-evidence and
attribution-gap tuples: `compared 21 payloads on disk; zero divergences`. The
one payload known to be malformed against its corpus convention parses cleanly
under the strict model in both its current and its pre-rename form, the latter
still yielding the identical `payload_name_lacks_modelo_and_filing_year` gap.
No payload collides with the model, and none was edited.

Checkers are clean on all three files: `ruff format --check` reports
`3 files already formatted`, `ruff check` reports `All checks passed!`, `ty`
reports `All checks passed!`, and `pyright` reports
`0 errors, 0 warnings, 0 informations`. `apidocs scaffold --check` reports
`Stub tree is conformant. No drift detected.` — no source module was added, so
no stub was generated or staged. The relative-import gate exits 0.

## Notes

The semantic discovery gate was waived by the operator for this campaign: the
`vaultspec-rag` index is broken and the service stopped, so no semantic probe
was run and none was attempted. Grounding was `rg` plus whole-file reads of the
fold, the core enum, both corpora, the existing gate, and the registry's
existing enum-hydration idiom.

Pyright rejected the first design. The payload models originally shared one
base declaring every attribution axis as optional, with each corpus's model
narrowing what it required. That is legal pydantic but trips
`reportIncompatibleVariableOverride` and `reportGeneralTypeIssues` on eight
fields under the project's strict domain configuration. The shipped shape keeps
only the true intersection on the base and declares each corpus's axes on its
own model, with a union alias for the reader — no field is overridden, and the
model reads more honestly for it.

The step ran alongside two live peers in the same corpus. Step S30 staged its
rename of the M303 prorrata payload mid-verification, which moved the fold's
inventory from twenty attributed payloads and one recorded gap to twenty-one
and none. That movement is S30's, not this Step's, which is why the equivalence
probe above is the behaviour proof rather than the summary counts; the counts
were measured either side of a corpus that changed underneath them. S30 also
holds a docstring edit on the grounding gate, touching neither honesty
direction. Nothing under `manual_oracles` or the M303 registry tree was
modified here.

One failure appeared in the scoped registry run and was not this Step's:
`test_registry_disk_cache_loader_fingerprint.py::test_an_enum_reached_only_through_a_literal_is_derived`
raised `AttributeError: type object 'AuthProviderKind' has no attribute
'GOOGLE'` at `1 failed, 3080 passed`. It does not reproduce in isolation and
the module was itself being edited in the shared index during the run, so it is
a peer mid-run race on an auth-provider surface unrelated to oracle grounding;
a later re-run of that module together with the fold's consumer was
`39 passed`.

The code landed inside `33129cc83f`, an operator-directed sweep commit of all
in-flight work that swept the shared index while this Step was verifying, not a
commit authored here. All four files were confirmed byte-identical between the
working tree and that commit afterwards, and both gates were re-run at the
post-sweep HEAD and stayed green.
