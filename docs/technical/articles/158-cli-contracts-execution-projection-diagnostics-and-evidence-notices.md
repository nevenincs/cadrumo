# CLI contracts, execution projection, diagnostics and evidence notices

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-158` · **Topic:** [Operator interfaces, part 1: command graph and principal workflows](../topics/operator-interfaces-part-1.md)

<!-- preserved:article -->
## Scope and capability

This chunk contains 30 CLI modules, 5,716 source lines and 47,530 measured proxy tokens. Every assigned line range was read across nine bounded pages; there are no unread portions. This is static inspection of the supplied snapshot: no application imports, execution or behavioral tests were performed, and declared contracts are not evidence that their callers enforce them end to end.

The chunk combines the command-spec runtime with typed operator outputs. Operators can run read-only local diagnostics, inspect recorded profile history, declare and list capital goods, and use profile-specific tax workflows. Live verification commands capture NIF-IVA or TGVI/GROI checks and expose list/show/latest views of the locally stored observations; the two capture handlers are distinct from those history readers (verify handlers (`src/cadrumo/entrypoints/cli/_app_live_verify_cli.py`), NIF-IVA and TGVI capture (`src/cadrumo/entrypoints/cli/_app_live_verify_cli.py`)). Their command declarations distinguish profile-local reads from profile-bound network capture (verify command specs (`src/cadrumo/entrypoints/cli/_app_live_verify_command_specs.py`)).

The “quickfile” path assembles a profile-bound workflow that reports readiness, calculation and verification stages, then writes a local export artifact at a caller-supplied path. Its result projection reports stage statuses and an export receipt with path, byte count and digest; it does not embed the exported bytes. The handler refuses a missing output path and exits nonzero when the workflow does not complete (quickfile handler (`src/cadrumo/entrypoints/cli/_app_quickfile.py`), quickfile result payloads (`src/cadrumo/entrypoints/cli/_app_quickfile_payloads.py`), quickfile command declarations (`src/cadrumo/entrypoints/cli/_app_quickfile_command_specs.py`)). The local surface describes a filing handoff, while the actual terminal artifact here is a local export; this chunk does not establish AEAT submission.

The capital-goods CLI declares one IVA investment record through a profile-bound application function and projects its record, effective deduction and register count; its list command presents the profile register (handlers (`src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py`), result schemas (`src/cadrumo/entrypoints/cli/_bienes_inversion_payloads.py`)). Profile payloads also cover append-only bucket history, declared descendants and average-workforce years. The descendant projection retains tax-driving fields, typed monthly childcare rows and a registry-owned relationship token. Its wire validators mirror canonical rules for unique months, mutually exclusive annual/monthly nursery expenses, relationship/date coherence, birth-relative chronology, future-date refusal and a later-start/work-months invariant (descendant payload (`src/cadrumo/entrypoints/cli/_config_descendiente_payloads.py`)). Bucket history has a typed event row with closed event/object enums, UTC time, payload version and object identifiers rather than accepting an unvalidated dictionary (bucket-history payload (`src/cadrumo/entrypoints/cli/_config_bucket_history_payloads.py`)).

The config help and quarantine payloads are read-oriented projections. Quarantine rows expose namespace counts but omit object keys, ciphertext, plaintext, taxpayer identifiers and bucket IDs (quarantine payload (`src/cadrumo/entrypoints/cli/_config_quarantine_payloads.py`)). Quarantine payloads are projection claims; command-policy and application behavior still need cross-layer verification.

## How the command boundary works

The immutable parameter declarations validate names, option aliases, environment-variable tokens, flag combinations, and consistency among local transport locus, shape and role. Secret-channel annotations are constrained: stdin channels must be boolean options, descriptor channels integer options, and a single option cannot be both machine-secret and profile-secret. The root profile-secret contract and leaf machine-secret contract require exactly one stdin and one file-descriptor channel; machine-secret variants also name distinct model targets and option conditions (parameter specs (`src/cadrumo/entrypoints/cli/_command_parameter_contracts.py`), secret contracts (`src/cadrumo/entrypoints/cli/_command_secret_contracts.py`)). Recovery-handoff metadata declares a write descriptor and read-verification descriptor, fields, byte ceiling, strict-object and duplicate/extra/missing-field rules, closure, reserved descriptors and Windows bootstrap behavior. These are validated declarations; actual descriptor parsing and custody are outside this chunk.

The runtime compiles the command graph into demand-loaded Typer nodes. It resolves public deferred targets only when selected, materializes options/defaults from the spec, skips structural ancestor callbacks after a child is invoked, and applies profile preflight before terminal work. Commands declaring registry or encrypted-fact authority run in a governed-fact scope; read-only commands use a summary-inventory snapshot. A declared live write is refused before preflight or target import, and staged machine-secret payloads are cleared in the preflight path's `finally` block (target resolver (`src/cadrumo/entrypoints/cli/_command_target.py`), runtime scope and invocation (`src/cadrumo/entrypoints/cli/_command_runtime.py`), dispatch (`src/cadrumo/entrypoints/cli/_command_runtime.py`), app builder (`src/cadrumo/entrypoints/cli/_command_runtime.py`)). Execution policy declarations relate capabilities, side effects, destructive operations, handoffs, live writes and storage routes, with implied capabilities such as AEAT implying network (policy value (`src/cadrumo/entrypoints/cli/_command_policy.py`), policy validators (`src/cadrumo/entrypoints/cli/_command_policy_validation.py`)).

Bootstrap exemptions keep selected first-run, recovery, discovery, configuration-only and supplied-artifact commands reachable without an active profile. The registry stores a criterion, explanatory note, optional cited verbs/tests, and optional descendant subtree; the source explicitly says the note is not verified. The matcher applies prefix matching, so correctness depends on the separate structural gate that checks the exemption records and current command tree; that gate is not in this chunk (exemption data (`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`), matcher (`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`)). The separate argument-only refusal checks the work-create command before profile gating and gives a foral tax-region refusal precedence over a generic unsupported-model response (refusal (`src/cadrumo/entrypoints/cli/_argument_only_refusals.py`)); its dispatch position is also outside this chunk.

## Knowledge, trust and safety

Operator dates are restricted to ISO-8601 through the shared core parser, and required/optional amounts use the canonical decimal grammar. JSON money fields remain strings to avoid float rounding, but annotated wire types validate canonical syntax, sign and optional bounds (date parser (`src/cadrumo/entrypoints/cli/_date_parsing.py`), decimal input parser (`src/cadrumo/entrypoints/cli/_decimal_parsing.py`), decimal wire types (`src/cadrumo/entrypoints/cli/_decimal_wire.py`)). Registry-derived string annotations are validated inside an indexed-authority operation, and the runtime opens a pinned governed-fact scope for commands whose policy declares the relevant capabilities. These mechanisms make authority explicit in this layer; their generation pinning and persistence effects depend on the referenced registry/profile modules.

Evidence notices preserve materially different extraction outcomes instead of collapsing them: contradiction and ambiguity are warnings, while missing, uncorroborated, absent and self-reported anchors have separate informational shapes. Candidate values, anchors, field names and explanatory notes are included in notice messages/context; fallback notices carry the cause, unread fields and potentially reader error type. This provides actionable provenance, but it also means these notices can contain invoice-derived data and must be handled under the CLI's output and logging policy (field notices (`src/cadrumo/entrypoints/cli/_evidence_field_notices.py`), fallback notices (`src/cadrumo/entrypoints/cli/_evidence_field_notices.py`)). The code derives degraded outcomes by excluding the two successful outcomes, so a newly added enum member is surfaced by default.

## Implementation assessment and follow-up

The strongest implementation choice is one graph-owned command contract feeding both runtime construction and policy gates, with typed output schemas that often reassert canonical invariants at the wire boundary. The runtime also puts live-write refusal ahead of target import, while the secret-channel contracts describe value-free payload shapes rather than storing secret values in command metadata.

A concrete local validation gap remains in two enum-dispatch validators. `validate_result_schema` looks up a validator by state but does nothing when the value is unknown; because `ResultSchemaSpec.__post_init__` delegates directly to it and dataclass annotations do not coerce values, a caller can construct a result schema with an invalid string state and bypass all three shape checks (result-schema dispatcher (`src/cadrumo/entrypoints/cli/_command_structure_validation.py`), result-schema model (`src/cadrumo/entrypoints/cli/_command_shared_contracts.py`)). Similarly, `validate_parameter_default` obtains no failure entry for an unknown kind and accepts it; the runtime then treats every non-required/non-literal kind as a factory and raises an invariant error if no factory exists (default validator (`src/cadrumo/entrypoints/cli/_command_policy_validation.py`), default model (`src/cadrumo/entrypoints/cli/_command_shared_contracts.py`), runtime projection (`src/cadrumo/entrypoints/cli/_command_runtime.py`)). These are confirmed permissive constructor behaviors, not by themselves reachable product defects: graph values may come only from trusted, statically typed Python declarations, and that producer/admission path is outside this chunk. Synthesis should check that bounded path and any independent graph checks before assigning impact. A focused verification can assert that unknown states fail at construction and valid states retain their existing shape rules.

Cross-layer review should verify the exemption validator and root callback ordering, the placement of argument-only refusals, profile preflight/auth and recovery descriptor processing, command graph declarations for live verification/quickfile, and output/log retention for evidence notices. This chunk contains no behavioral test implementation; static contracts alone cannot certify those interactions.

## Complete assigned-file coverage

All 30 manifest files are linked below; every assigned line was read.

- _app_live_rendering.py (`src/cadrumo/entrypoints/cli/_app_live_rendering.py`)
- _app_live_verify_cli.py (`src/cadrumo/entrypoints/cli/_app_live_verify_cli.py`)
- _app_live_verify_command_specs.py (`src/cadrumo/entrypoints/cli/_app_live_verify_command_specs.py`)
- _app_live_verify_payloads.py (`src/cadrumo/entrypoints/cli/_app_live_verify_payloads.py`)
- _app_quickfile.py (`src/cadrumo/entrypoints/cli/_app_quickfile.py`)
- _app_quickfile_command_specs.py (`src/cadrumo/entrypoints/cli/_app_quickfile_command_specs.py`)
- _app_quickfile_payloads.py (`src/cadrumo/entrypoints/cli/_app_quickfile_payloads.py`)
- _argument_only_refusals.py (`src/cadrumo/entrypoints/cli/_argument_only_refusals.py`)
- _bienes_inversion_cli.py (`src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py`)
- _bienes_inversion_payloads.py (`src/cadrumo/entrypoints/cli/_bienes_inversion_payloads.py`)
- _bootstrap_exempt.py (`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`)
- _command_parameter_contracts.py (`src/cadrumo/entrypoints/cli/_command_parameter_contracts.py`)
- _command_parameter_validation.py (`src/cadrumo/entrypoints/cli/_command_parameter_validation.py`)
- _command_policy.py (`src/cadrumo/entrypoints/cli/_command_policy.py`)
- _command_policy_validation.py (`src/cadrumo/entrypoints/cli/_command_policy_validation.py`)
- _command_runtime.py (`src/cadrumo/entrypoints/cli/_command_runtime.py`)
- _command_secret_contracts.py (`src/cadrumo/entrypoints/cli/_command_secret_contracts.py`)
- _command_shared_contracts.py (`src/cadrumo/entrypoints/cli/_command_shared_contracts.py`)
- _command_structure_validation.py (`src/cadrumo/entrypoints/cli/_command_structure_validation.py`)
- _command_target.py (`src/cadrumo/entrypoints/cli/_command_target.py`)
- _config_bucket_history_payloads.py (`src/cadrumo/entrypoints/cli/_config_bucket_history_payloads.py`)
- _config_descendiente_payloads.py (`src/cadrumo/entrypoints/cli/_config_descendiente_payloads.py`)
- _config_help_payloads.py (`src/cadrumo/entrypoints/cli/_config_help_payloads.py`)
- _config_plantilla_media_payloads.py (`src/cadrumo/entrypoints/cli/_config_plantilla_media_payloads.py`)
- _config_quarantine_payloads.py (`src/cadrumo/entrypoints/cli/_config_quarantine_payloads.py`)
- _date_parsing.py (`src/cadrumo/entrypoints/cli/_date_parsing.py`)
- _decimal_parsing.py (`src/cadrumo/entrypoints/cli/_decimal_parsing.py`)
- _decimal_wire.py (`src/cadrumo/entrypoints/cli/_decimal_wire.py`)
- _diagnostics_payloads.py (`src/cadrumo/entrypoints/cli/_diagnostics_payloads.py`)
- _evidence_field_notices.py (`src/cadrumo/entrypoints/cli/_evidence_field_notices.py`)
<!-- /preserved:article -->
