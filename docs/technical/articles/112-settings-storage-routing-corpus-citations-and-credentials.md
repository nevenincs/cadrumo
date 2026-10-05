# Settings, storage routing, corpus citations, and credentials

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-112` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 23 core modules totaling 4,565 lines, 203,304 bytes, and 44,332 measured proxy tokens. I read all nine bounded pages, including the complete settings facade and its field mixins. The chunk covers application configuration, storage-root and database routing, human confirmation and discrepancy vocabularies, corpus citation anchoring, directory traversal, credential assessment, document-shape classification, signing, and export completeness metadata. This is static analysis only; no provider, filesystem, AEAT, Google, or LLM flow was executed.

## Settings, privacy posture, and storage routing

`Settings` is the environment authority for runtime configuration, while `override_settings` provides a context-local in-process override. The model explicitly drops dotenv loading and filters `CADRUMO_ACTIVE_PROFILE` out of environment input; profile choice comes from the durable pointer or an in-process `--profile`/test override. The settings cache is keyed by the pointer’s selected/absent state and transition revision, so an account switch changes the effective database route without making every `load_settings()` reconstruct all fields and paths. Root overrides discard derived paths and let them resolve again under the new root; explicit values and the model’s `model_fields_set` are preserved for route classification. An independent authority-root settings reader avoids requiring profile storage merely to locate published registry authority. config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`)

The settings surface is broad but carries security-relevant defaults. Secret passphrases, API keys, certificate passwords, and Cl@ve credentials are `SecretStr` values; blank optional secret inputs become unset. Off-host evidence reading defaults off and requires deployment permission plus per-invocation acknowledgement, with a categorical gestor-mode block. These fields define the posture for consumers rather than implementing every call-site gate in this chunk. config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config.py (`src/cadrumo/core/config.py`) config_live_tests.py (`src/cadrumo/core/config_live_tests.py`)

LLM configuration provides distinct local/cloud model settings by role, plus local runtime memory floor, contention margin, refusal on unmeasurable headroom by default, and single-request concurrency by default. This makes routing and resource cost tunable per job rather than forcing every caller through one global model choice. Integration mixins define Google Drive vault naming and reject the retired product’s vault folder, financial store paths, model-runtime endpoints, and explicit positive timeouts. config_llm_fields.py (`src/cadrumo/core/config_llm_fields.py`) config_runtime_fields.py (`src/cadrumo/core/config_runtime_fields.py`) config_integration_fields.py (`src/cadrumo/core/config_integration_fields.py`) config_timeouts.py (`src/cadrumo/core/config_timeouts.py`)

Storage root resolution uses captured inputs for a pure platform-specific user-data path and does not inspect whether the application runs from a checkout. A developer can set the root explicitly. Detecting retired `aeat` state is refusal-only: this layer will not open, adopt, migrate, or delete the old database or state directory. Storage-route classification distinguishes explicit URLs, the cold root fallback, and a selected profile’s bucket database; application write guards consume the classification rather than independently parsing URLs. config_state_root.py (`src/cadrumo/core/config_state_root.py`) config_state_root.py (`src/cadrumo/core/config_state_root.py`) config_state_root.py (`src/cadrumo/core/config_state_root.py`) config_storage_route.py (`src/cadrumo/core/config_storage_route.py`) config_storage_route.py (`src/cadrumo/core/config_storage_route.py`) config_storage_route.py (`src/cadrumo/core/config_storage_route.py`) config_support.py (`src/cadrumo/core/config_support.py`)

## Evidence, review, and corpus handling

The confirmation vocabulary separates deterministic blockers from non-blocking advisories and maps every blocker to an operator action. Actions record whether a person chose among captured candidates, supplied a value absent from the page, or attested that a finding was acceptable after review. The taxonomy intentionally has no “waive” or bulk bypass member. `DraftDiscrepancyKind` names checks over parsed values, not a model’s self-assessed confidence, and `ConfirmationBlockReason` distinguishes arithmetic closure, identity, direction, regime, territory, party attribution, and invoice-class failures. confirmation_gate.py (`src/cadrumo/core/confirmation_gate.py`) confirmation_gate.py (`src/cadrumo/core/confirmation_gate.py`) confirmation_gate.py (`src/cadrumo/core/confirmation_gate.py`) draft_discrepancy.py (`src/cadrumo/core/draft_discrepancy.py`)

`corpus_text.py` normalizes bundled legal text and resolves citations to exactly one extracted sidecar unit. It prefers literal/exact anchors, then carefully constrained single-unit, article-point, and structural-heading resolution; missing or duplicate candidates raise typed errors instead of returning an entire unrelated document. It also enumerates dated redaction marks without treating source order as recency, since the two BOE payload shapes use opposite orderings. The normalizer and cache operate over bundled legal material, while `required_text` is a later verification condition, not a selection shortcut. corpus_text.py (`src/cadrumo/core/corpus_text.py`) corpus_text.py (`src/cadrumo/core/corpus_text.py`) corpus_text.py (`src/cadrumo/core/corpus_text.py`) corpus_text.py (`src/cadrumo/core/corpus_text.py`) corpus_text.py (`src/cadrumo/core/corpus_text.py`)

`DocumentShape` classifies bytes by their actual contents. It distinguishes standalone structured invoices and PDFs with embedded XML from scans and text-layer PDFs. Structured SII and VERI*FACTU submissions remain outside the single-invoice set because each is a collection and could otherwise be silently collapsed to one record. `ExportExemptionReason` similarly makes the reason a casilla is not addressed explicit; it distinguishes true record-design absence, internal intermediates, AEAT prefill, indirect binding output, formula-verified downstream output, and a known unmodelled record block. document_shape.py (`src/cadrumo/core/document_shape.py`) document_shape.py (`src/cadrumo/core/document_shape.py`) export_exemption_reason.py (`src/cadrumo/core/export_exemption_reason.py`) estado_casilla_oficial.py (`src/cadrumo/core/estado_casilla_oficial.py`) export_layout_format.py (`src/cadrumo/core/export_layout_format.py`)

The shared directory scanner provides sorted and lazy traversal, explicit file/directory selection, pruning, and predictable missing-root behavior. It closes each directory handle before yielding, refuses ambiguous multi-segment patterns, does not follow directory symlinks, and uses an explicit stack so deep trees do not consume Python recursion depth. `credentials.py` enforces profile-password bounds by Unicode scalar count and strict UTF-8 size, rejects surrogate code points, and returns only finite reasons and numeric metadata; strength is guidance rather than an acceptance rule and the candidate is not retained. `ed25519_signing.py` signs the raw decoded digest bytes, while key custody remains a caller responsibility. directory_scan.py (`src/cadrumo/core/directory_scan.py`) directory_scan.py (`src/cadrumo/core/directory_scan.py`) directory_scan.py (`src/cadrumo/core/directory_scan.py`) directory_scan.py (`src/cadrumo/core/directory_scan.py`) credentials.py (`src/cadrumo/core/credentials.py`) credentials.py (`src/cadrumo/core/credentials.py`) credentials.py (`src/cadrumo/core/credentials.py`) ed25519_signing.py (`src/cadrumo/core/ed25519_signing.py`) ed25519_signing.py (`src/cadrumo/core/ed25519_signing.py`) descriptor_write.py (`src/cadrumo/core/descriptor_write.py`)

Other compact contracts keep domain-specific values from drifting: the country-code alias states length only, separate from registry membership; `DeclaracionIdioma` is AEAT’s four-value declaration-language code and not the UI language; `DescendantRelacion` remains a registry-projected opaque token. `config_support` provides one typed route classification and shared external-constant-backed endpoints, while `config_live_tests` accepts only literal `"1"` for test opt-in. country_code.py (`src/cadrumo/core/country_code.py`) declaracion_idioma.py (`src/cadrumo/core/declaracion_idioma.py`) descendant_relacion.py (`src/cadrumo/core/descendant_relacion.py`) config_support.py (`src/cadrumo/core/config_support.py`) config_live_tests.py (`src/cadrumo/core/config_live_tests.py`)

## Assessment

The strongest design features are the separation of durable profile selection from environment configuration, fail-closed off-host settings, explicit database-route types, content-based document handling, unique citation anchoring, and a confirmation model that preserves human resolution provenance. Main review limits are architectural: settings expose policy but do not prove every consuming service applies it, password strength bands are heuristic advice, and the Ed25519 primitive does not establish custody or key-rotation policy. The code’s static contracts are not evidence of live service behavior; those adapters and their tests need their own review.

## Complete assigned-file coverage

- config.py (`src/cadrumo/core/config.py`) — lines 1–1,216
- config_integration_fields.py (`src/cadrumo/core/config_integration_fields.py`) — lines 1–91
- config_live_tests.py (`src/cadrumo/core/config_live_tests.py`) — lines 1–32
- config_llm_fields.py (`src/cadrumo/core/config_llm_fields.py`) — lines 1–116
- config_runtime_fields.py (`src/cadrumo/core/config_runtime_fields.py`) — lines 1–286
- config_state_root.py (`src/cadrumo/core/config_state_root.py`) — lines 1–226
- config_storage_route.py (`src/cadrumo/core/config_storage_route.py`) — lines 1–185
- config_support.py (`src/cadrumo/core/config_support.py`) — lines 1–225
- config_timeouts.py (`src/cadrumo/core/config_timeouts.py`) — lines 1–108
- confirmation_gate.py (`src/cadrumo/core/confirmation_gate.py`) — lines 1–198
- corpus_text.py (`src/cadrumo/core/corpus_text.py`) — lines 1–563
- country_code.py (`src/cadrumo/core/country_code.py`) — lines 1–56
- credentials.py (`src/cadrumo/core/credentials.py`) — lines 1–138
- declaracion_idioma.py (`src/cadrumo/core/declaracion_idioma.py`) — lines 1–54
- descendant_relacion.py (`src/cadrumo/core/descendant_relacion.py`) — lines 1–19
- descriptor_write.py (`src/cadrumo/core/descriptor_write.py`) — lines 1–31
- directory_scan.py (`src/cadrumo/core/directory_scan.py`) — lines 1–395
- document_shape.py (`src/cadrumo/core/document_shape.py`) — lines 1–121
- draft_discrepancy.py (`src/cadrumo/core/draft_discrepancy.py`) — lines 1–182
- ed25519_signing.py (`src/cadrumo/core/ed25519_signing.py`) — lines 1–121
- estado_casilla_oficial.py (`src/cadrumo/core/estado_casilla_oficial.py`) — lines 1–21
- export_exemption_reason.py (`src/cadrumo/core/export_exemption_reason.py`) — lines 1–119
- export_layout_format.py (`src/cadrumo/core/export_layout_format.py`) — lines 1–62
<!-- /preserved:article -->
