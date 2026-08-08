---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:d7f71e92eee8d9a998b06765ae7a556416ec158ca5ab4fb9a7c83c690394e579'
step_id: 'S82'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Measure whether fewer fields per call outperforms all fields at once at the design-target tier, resolving the S2 call-shape question by a recorded comparison at fixed key hash and tier rather than by assertion

## Scope

- `dev`

## Description

- Verify the corpus key hash matches the value the comparison must be fixed at.
- Establish whether both arms of the comparison can be constructed against the
  current tree.
- Probe the design-target tier configuration and the gated cloud route.
- Record the comparison as NOT RESOLVED rather than substituting an assertion for
  the measurement the Step exists to make.

## Outcome

**This Step is NOT delivered and the plan row stays unchecked. No comparison was
recorded, and none is asserted.** The Step's own contract is that the call-shape
question is resolved by measurement and never by assertion, so reporting a
direction here without a run would defeat the row rather than close it.

Corpus key sha256 verified as
`e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593`
(890052 bytes), equal to the value the comparison is required to be fixed at.
Tree `d6f28f5394`.

### The blocking finding: one of the two arms does not exist

**The all-fields arm exists; the fewer-fields arm has no code path.** The
extraction prompt compiler emits every declared field contract on every call.
Its field-line renderer takes no arguments, and neither compiler entry point
accepts a field selection — one takes a period, the other takes resolved
authority values. There are 18 field contracts and the prompt carries all 18,
always.

So a split-call arm cannot be constructed without adding a field-subset parameter
to the prompt compiler. That is a code change, it is unscoped, and it sits on a
seam active peer lanes hold. This Step did not make it: the row asks for a
measurement, not for a compiler change, and taking one unilaterally on a contended
surface is the wrong trade.

**This falsifies the plan's sequencing premise.** The parallelization note states
that S82 rides the S36 harness run at the design-target tier. Riding that run
yields the all-fields arm only, because the all-fields arm is the only shape the
compiler can emit. S82 is blocked on a compiler capability, not merely on the
harness run it was sequenced behind.

### The design-target tier is configured correctly

Provider ANTHROPIC with mapping, text and vision models all resolving to
`claude-haiku-4-5` — the Haiku-class cloud design proxy, which the harness's own
tier vocabulary marks baseline-eligible. The tier is not the obstacle.

### The environment cannot execute either arm

Two further blockers, probed rather than inferred. No cloud credential exists:
the Anthropic, OpenAI and Gemini key settings all resolve unset. And no bucket
session can be unlocked, the one profile reporting `setup_incomplete`, so a call
refuses at the profile-bound response cache before a request is built.

Local inference was not attempted. The operator recorded 1.83 GiB free VRAM
against a 4 GiB threshold, and an overflow would destroy concurrent work across
every agent in this tree.

### What resolving this Step now requires

Three preconditions, in order. A field-subset parameter on the extraction prompt
compiler, so the fewer-fields arm can be built at all. A credential and an
unlocked profile, so either arm can run. Then both arms at the same key hash and
the same tier, scoring fabrication on null-truth as a hard error in both, with
call count and token cost reported beside quality. The corpus carries 302
documents and the fabrication-trap slots are re-derivable from the key at run
time; no denominator here should be inherited from this record.

## Verification

Key pinning, which is the one precondition that did hold:

    key sha256   e2db6a499f6f0ffafa4cf44084f433962dd3f8a0f6f0a65facaf7df07bb38593
    key bytes    890052

Arm constructability, against the current tree:

    build sig : (*, period: 'Period') -> 'CompiledInvoiceExtractionPrompt'
    render sig: (*, values: 'InvoiceExtractionAuthorityValues') -> 'CompiledInvoiceExtractionPrompt'
    _field_lines sig: () -> 'str'
    field contracts: 18

No signature admits a field subset, so the fewer-fields arm is unconstructable.

Tier and route:

    cadrumo_llm_provider           = ANTHROPIC
    cadrumo_llm_cloud_mapping_model= claude-haiku-4-5
    cadrumo_llm_anthropic_api_key  = UNSET
    cadrumo_llm_openai_api_key     = UNSET
    cadrumo_llm_gemini_api_key     = UNSET

A live call on the gated cloud route, showing where it stops:

    constructed; decided_by = llm:anthropic-column-role-map:claude-haiku-4-5
    FAILED: StorageValidationError
    storage runtime is not ready for profile-bound storage: no active bucket
    session; run `aeat config login NAME` to unlock a profile before invoking
    profile-bound storage.

## Notes

- **No consent token was minted and none was needed for what ran.** Nothing
  reached a transport, so no evidence left the host. Separately, the column-role
  mapping request declares `evidence_derived` False by design — what crosses that
  seam is the file's header vocabulary and never a cell value — so the
  taxpayer-evidence consent gate does not govern the mapping call in the first
  place. The gate was neither disabled, bypassed nor weakened.
- No figure of any kind is reported for the call-shape question. A direction
  reasoned from the prompt's shape would read exactly like a measured one in six
  months, which is the failure this row was written to prevent.
