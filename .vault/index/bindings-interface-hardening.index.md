---
generated: true
tags:
  - '#index'
  - '#bindings-interface-hardening'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:36efeaebffeeb392312a586097e99ac0882dd41459712e4fce08f6ddb3040b3e'
related:
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-14-bindings-interface-hardening-reference]]'
  - '[[2026-06-14-bindings-interface-hardening-research]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P01-S01]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P01-S02]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P01-S03]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S04]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S05]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S06]]'
  - '[[2026-06-15-bindings-interface-hardening-W01-P02-S07]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P03-S08]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P03-S09]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P03-S10]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P04-S11]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P04-S12]]'
  - '[[2026-06-15-bindings-interface-hardening-W02-P04-S13]]'
  - '[[2026-06-15-bindings-interface-hardening-W03-P05-S14]]'
  - '[[2026-06-15-bindings-interface-hardening-W03-P05-S15]]'
  - '[[2026-06-15-bindings-interface-hardening-W03-P05-S16]]'
  - '[[2026-06-15-bindings-interface-hardening-W03-P06-S18]]'
  - '[[2026-06-15-bindings-interface-hardening-W03-P06-S19]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P07-S20]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P07-S21]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P07-S22]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P08-S23]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P08-S24]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P08-S25]]'
  - '[[2026-06-15-bindings-interface-hardening-W04-P08-S26]]'
  - '[[2026-06-15-bindings-interface-hardening-W05-P09-S27]]'
  - '[[2026-06-15-bindings-interface-hardening-W05-P09-S28]]'
  - '[[2026-06-15-bindings-interface-hardening-W05-P09-S29]]'
  - '[[2026-06-15-bindings-interface-hardening-W05-P10-S30]]'
  - '[[2026-06-15-bindings-interface-hardening-W06-P11-S31]]'
  - '[[2026-06-15-bindings-interface-hardening-W06-P11-S32]]'
  - '[[2026-06-15-bindings-interface-hardening-W06-P12-S33]]'
  - '[[2026-06-15-bindings-interface-hardening-audit]]'
  - '[[2026-06-15-bindings-interface-hardening-plan]]'
---

# `bindings-interface-hardening` feature index

Auto-generated index of all documents tagged with `#bindings-interface-hardening`.

## Documents

### adr

- `2026-06-14-bindings-interface-hardening-adr` - `bindings-interface-hardening` adr: `bindings interface hardening: one validation contract, provenance parity, semantic disambiguation` | (**status:** `accepted`)

### audit

- `2026-06-15-bindings-interface-hardening-audit` - `bindings-interface-hardening` audit: `bindings interface hardening close audit and fresh-context honesty review`

### exec

- `2026-06-15-bindings-interface-hardening-W01-P01-S01` - add a BindingAggregationOp StrEnum and a typed BindingAggregation pydantic model in core, then wire the typed aggregation field onto DataBindingDefinition replacing the free-form mapping
- `2026-06-15-bindings-interface-hardening-W01-P01-S02` - replace the ~10 ad-hoc op re-parses with one typed accessor and one declared per-family default, removing the divergent sum-vs-rows silent defaults
- `2026-06-15-bindings-interface-hardening-W01-P01-S03` - add typed-aggregation roundtrip and per-family default tests that fail if the typed op is dropped or a wrong family default is applied
- `2026-06-15-bindings-interface-hardening-W01-P02-S04` - introduce one canonical binding source-kind enum in core reconciling AggregationSourceKind and RowSetGroupingKind, realigning the related_party, atribucion and refund tokens to match enum values
- `2026-06-15-bindings-interface-hardening-W01-P02-S05` - derive every per-family source-kind frozenset from the canonical enum, fix the incomplete LEDGER_BINDING_SOURCE_KINDS, and reconcile every consumer into one accept-or-reject state per the retired-enum rule
- `2026-06-15-bindings-interface-hardening-W01-P02-S06` - wire the dead typed_enum schema field to a real consumer or delete it outright per no-legacy-compatibility, with the deletion test asserting no module reads it
- `2026-06-15-bindings-interface-hardening-W01-P02-S07` - add a taxonomy parity gate asserting the canonical source-kind enum equals the registry binding source set
- `2026-06-15-bindings-interface-hardening-W02-P03-S08` - define one validate(binding)->list[str] validator per source family registered in the single binding dispatch table alongside the selector model
- `2026-06-15-bindings-interface-hardening-W02-P03-S09` - lift the four detail-record family and previous_filing op/fact invariants to registry-build, routing each through selector_as_dict and preserving the underlying pydantic field error in the diagnostic
- `2026-06-15-bindings-interface-hardening-W02-P03-S10` - collapse the near-verbatim invoice and counterpart resolver and validator duplication to one shared implementation parameterised by source kind
- `2026-06-15-bindings-interface-hardening-W02-P04-S11` - run every family validator from the single dispatch table inside the registry-build section validator so all families are checked at snapshot build
- `2026-06-15-bindings-interface-hardening-W02-P04-S12` - add build-time rejection tests per family plus an anti-tautology proof asserting a malformed binding fails at build for each family, not only at resolve
- `2026-06-15-bindings-interface-hardening-W02-P04-S13` - fix any latent malformed registry TOML the new build gate surfaces so the full registry suite collects and builds clean
- `2026-06-15-bindings-interface-hardening-W03-P05-S14` - generalise the IVA unsupported-observation screen into a per-family unrouted-observation screen that flags an unrouted declarable observation for every aggregation family
- `2026-06-15-bindings-interface-hardening-W03-P05-S15` - wire the per-family unrouted-observation advisory diagnostics on the live calculate path so a resolver surfaces an advisory instead of a silent Decimal(0)
- `2026-06-15-bindings-interface-hardening-W03-P05-S16` - add silent-zero refusal tests per family asserting a positive unrouted observation raises an advisory rather than resolving to zero
- `2026-06-15-bindings-interface-hardening-W03-P06-S18` - emit a diagnostic for an unresolved non-formula relation that today produces neither value nor warning at calculate time
- `2026-06-15-bindings-interface-hardening-W03-P06-S19` - add carry-gate parity and relation-diagnostic tests asserting one gate path and a surfaced diagnostic for an unresolved non-formula relation
- `2026-06-15-bindings-interface-hardening-W04-P07-S20` - add legal_refs, source_refs and a typed source kind to ModeloBindingValue at parity with the casilla provenance model, re-reading HEAD and git diff before editing the encrypted boundary
- `2026-06-15-bindings-interface-hardening-W04-P07-S21` - populate the binding-value provenance from the binding definition in the filing builder and drop the hardcoded source=registry binding input free-text string
- `2026-06-15-bindings-interface-hardening-W04-P07-S22` - add a strict save-load-equality roundtrip and an anti-tautology proof that corrupts the persisted provenance and asserts refusal on the encrypted filing-draft boundary
- `2026-06-15-bindings-interface-hardening-W04-P08-S23` - expose the binding provenance on BindingRowPayload and BindingPreviewRowPayload and convert bindings list from the list[dict[str,object]] bag to the typed payload
- `2026-06-15-bindings-interface-hardening-W04-P08-S24` - make bindings list --modelo a registry-derived click.Choice that refuses an unknown code with the accepted-codes set in the error message
- `2026-06-15-bindings-interface-hardening-W04-P08-S25` - replace the --binding numeric-vs-enum try-Decimal-except heuristic with a registry-data-type-driven coercion that rejects a malformed amount instead of reclassifying it as an enum
- `2026-06-15-bindings-interface-hardening-W04-P08-S26` - add documented-command and json-schema conformance tests covering the typed bindings list payload and the --modelo Choice refusal
- `2026-06-15-bindings-interface-hardening-W05-P09-S27` - rename the Google OAuth _profile_binding.py to an active-profile resolver name in one atomic explicit-path relocation commit and run python -m dev.docs.apidocs scaffold
- `2026-06-15-bindings-interface-hardening-W05-P09-S28` - reclassify decimal_from_string out of the _decimal_binding_value binding-value filename in one atomic explicit-path relocation commit and run python -m dev.docs.apidocs scaffold
- `2026-06-15-bindings-interface-hardening-W05-P09-S29` - rename the legal_basis_binding rate-to-BOE verification test concept off the binding word in one atomic explicit-path relocation commit and run python -m dev.docs.apidocs scaffold
- `2026-06-15-bindings-interface-hardening-W05-P10-S30` - give the three source-resolver result types one role-named shared contract or a documented shared role, replacing naming-by-source with naming-by-role
- `2026-06-15-bindings-interface-hardening-W06-P11-S31` - promote the never-promoted registry-resolver-family-extraction and registry-formula-runtime-facade candidates to rules with vaultspec-core vault rule promote from their 2026-06-02 boundary audits
- `2026-06-15-bindings-interface-hardening-W06-P11-S32` - author the five new bindings-interface rules from the ADR codification candidates and propagate them with vaultspec-core sync
- `2026-06-15-bindings-interface-hardening-W06-P12-S33` - run a fresh-context honesty review and close audit per the campaign-close-honesty rule with full-tree owner triage, tracking every surfaced item as a new Step with a verification gate

### plan

- `2026-06-15-bindings-interface-hardening-plan` - `bindings-interface-hardening` plan

### reference

- `2026-06-14-bindings-interface-hardening-reference` - `bindings-interface-hardening` reference: `bindings interface code anchors: validator dispatch, selector models, carrier and CLI payloads`

### research

- `2026-06-14-bindings-interface-hardening-research` - `bindings-interface-hardening` research: `bindings interface: definition, validation, boundary and semantic-spread discovery`
