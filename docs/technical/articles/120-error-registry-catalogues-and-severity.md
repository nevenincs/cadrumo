# Error registry catalogues and severity

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-120` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 11 registry and severity modules totaling 3,221 physical lines, 111,650 bytes, and 22,899 measured `o200k_base` proxy tokens. All five pages were read, covering the complete core/domain/entrypoint registry shards, the final catalogue aggregator, and the shared severity enum. This is static analysis only: error paths were not executed, and the mappings do not prove that their owning call sites raise the declared classes.

## Capability represented by the registry

The main product capability here is a cross-layer catalogue that maps exception qualified names to stable error codes, categories, retryability, translation keys, and optional public-message policy. The assembled declaration tuple imports domain, adapter, CLI/TUI entrypoint, core, and application rows in a fixed order. The core error API consumes this tuple on first lookup and performs duplicate checks during registration; this chunk supplies the layer data and its assembly, while the rendering contract itself is in the adjacent error-code modules. Combined layer imports and ordering (`src/cadrumo/core/errors/registry/declared_codes.py`) Core declarations (`src/cadrumo/core/errors/registry/_core.py`) Domain shard aggregator (`src/cadrumo/core/errors/registry/_domain.py`) Entrypoint declarations (`src/cadrumo/core/errors/registry/_entrypoints.py`)

The domain catalogue spans bucket operations, profile state and custody, invoice/ledger/transaction errors, tax-form calculations and filing, evidence and reconciliation, inventory, and authority-registry integrity. The rows distinguish ordinary failure from refusal, integrity breach, unavailable dependency, and lock/conflict; for example, profile snapshot hash mismatch and authority-store corruption are integrity errors, while unsupported or terminal Modelo conditions are refusals. The catalogue also includes adapter-originated sealed-archive errors and application-originated ledger conditions within the domain-layer shard. These are reporting classifications, not proof that the underlying operation has the claimed enforcement or recovery behavior. Bucket and persistence classifications (`src/cadrumo/core/errors/registry/_domain_part1.py`) Profile integrity and Modelo lifecycle examples (`src/cadrumo/core/errors/registry/_domain_part3.py`) Authority-store integrity errors (`src/cadrumo/core/errors/registry/_domain_part4.py`) Ledger evidence classifications (`src/cadrumo/core/errors/registry/_domain_part1.py`)

The core shard also gives stable classifications to access-gate outcomes, profile-pointer and corpus-manifest errors, localization failures, output-schema faults, observability errors, and shared error bases. In particular, the declared catalog distinguishes a permanent live-submit refusal from a live-read opt-in refusal; the declarations show how these are presented but do not themselves implement the access gate. Core access-gate error mappings (`src/cadrumo/core/errors/registry/_core.py`) Corpus-manifest integrity mappings (`src/cadrumo/core/errors/registry/_core_part2.py`)

The entrypoint shards cover CLI boundary failures and TUI navigation/module-argument failures. They encode terminal errors such as unknown destination, unavailable destination, failed command group resolution, or an operation that remains running. The call sites and user interaction are outside this chunk, so these records cannot establish whether the interface recovers, retries, or offers a useful next action. CLI boundary types (`src/cadrumo/core/errors/registry/_entrypoints.py`) TUI navigation outcomes (`src/cadrumo/core/errors/registry/_entrypoints_part2.py`)

## Data and trust boundaries

The catalogue is code-authored metadata. It contains exception names, stable IDs, categories, translation keys, booleans, and optional runbook references; it is not an external legal authority or a calculation source. Names such as “authority store” or “profile snapshot mismatch” identify error families only. Correctness of the legal rules, calculations, persistence checks, and detection logic belongs to the modules that raise these exceptions and cannot be inferred from the registry entries.

Selected rows set `public_message_from_registry=True`, which lets the adjacent renderer prefer the catalogued public translation instead of exception diagnostic text. That is a useful explicit policy hook for sensitive or domain-specific refusals, but it is not set on every row. Safety of other rendered messages therefore depends on the renderer and exception constructors; the companion error-rendering report documents a conditional unsanitized-message path. Examples with public-message policy (`src/cadrumo/core/errors/registry/_core.py`) A domain refusal with registry-owned wording (`src/cadrumo/core/errors/registry/_domain_part3.py`)

All registry declarations in this chunk set `runbook_id=None`; no `runbook_id` assignment with another value occurs in the reviewed shards. The shared error record supports this optional field, but the rows here provide no linked runbook reference for operators. This is a completeness limitation rather than proof that no external documentation exists. Core row metadata (`src/cadrumo/core/errors/registry/_core.py`) Shared error-code field (`src/cadrumo/core/errors/error_codes.py`)

## Implementation assessment

The catalogue's main strength is that it gives broad application and domain failures one machine-readable vocabulary. Shard aggregation keeps ownership organized by layer, and the adjacent loader's duplicate checks mean collisions are refused rather than resolved by import order. The static mapping covers both low-level integrity errors and actionable operator refusals, making it suitable for stable CLI/automation reporting when the exception wiring and translation keys are maintained together.

There is a local severity-ordering ambiguity. `BaseSeverity` says it carries the `INFO < WARNING < ERROR` contract, but it subclasses `StrEnum` and defines only lowercase string values; it supplies no explicit rank or ordering method. Native comparisons/sorting of these string-valued members therefore follow lexical text order, in which `"warning"` sorts after `"error"`, opposite the documented severity relation. This is a concrete mismatch if consumers use `<`, `>`, or ordinary sorting as a severity order; no consumer is included in this chunk, so call-site impact remains unverified. If ordering is part of the contract, define an explicit rank or comparison strategy and cover it with a focused test. Severity contract and string values (`src/cadrumo/core/errors/severity.py`)

This chunk contains no tests or exception-raising call sites. Static inspection cannot certify registry completeness against all subclasses, translation-key coverage, retry classification at consumers, or that the domain rules behind each named refusal/integrity error are accurate. Useful synthesis follow-up is to compare these rows to exception declarations and i18n resources, inspect consumers for severity comparisons, and decide whether the optional runbook field should be populated for high-impact operator failures.

## Complete assigned-file coverage

- errors/registry/_core.py (`src/cadrumo/core/errors/registry/_core.py`) — lines 1–413
- errors/registry/_core_part2.py (`src/cadrumo/core/errors/registry/_core_part2.py`) — lines 1–50
- errors/registry/_domain.py (`src/cadrumo/core/errors/registry/_domain.py`) — lines 1–24
- errors/registry/_domain_part1.py (`src/cadrumo/core/errors/registry/_domain_part1.py`) — lines 1–790
- errors/registry/_domain_part2.py (`src/cadrumo/core/errors/registry/_domain_part2.py`) — lines 1–930
- errors/registry/_domain_part3.py (`src/cadrumo/core/errors/registry/_domain_part3.py`) — lines 1–602
- errors/registry/_domain_part4.py (`src/cadrumo/core/errors/registry/_domain_part4.py`) — lines 1–80
- errors/registry/_entrypoints.py (`src/cadrumo/core/errors/registry/_entrypoints.py`) — lines 1–122
- errors/registry/_entrypoints_part2.py (`src/cadrumo/core/errors/registry/_entrypoints_part2.py`) — lines 1–151
- errors/registry/declared_codes.py (`src/cadrumo/core/errors/registry/declared_codes.py`) — lines 1–28
- errors/severity.py (`src/cadrumo/core/errors/severity.py`) — lines 1–31
<!-- /preserved:article -->
