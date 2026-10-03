# External-service constants, field provenance, and filing producers

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-113` · **Topic:** [Core authority and shared controls](../topics/core-authority-and-shared-controls.md)

<!-- preserved:article -->
## Scope and method

This chunk contains nine files totaling 2,310 lines, 126,256 bytes, and 34,966 measured proxy tokens. I read all seven assigned pages. It centralizes immutable external-service constants, field provenance vocabularies, filesystem change-time and permission helpers, history-discovery signals, and producer identities for filing-export values. This is static analysis only; AEAT portal behavior, Windows ACL behavior, and registry-to-producer coverage were not exercised.

## External constants and portal surfaces

`external_constants.py` loads a packaged TOML mirror into strict frozen Pydantic models. It groups AEAT domains, route fragments, Cl@ve selectors, notification filters, portal paths, action-pattern labels, Google OAuth scopes, MIME types, encodings, and language values. Parsing is local and cached; loading does not access storage or call a provider. Main sections are validated on load, and portal path entries must be absolute-path fragments. The volatile Pre303/IVA-wallet section is intentionally staged as raw data and validates into a strict model on first use, so a broken wallet selector does not prevent unrelated commands from reading the registry. external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.toml (`src/cadrumo/core/external_constants.toml`)

The data file carries current route selectors and marker strings for Cl@ve Móvil and Permanente, Pre303 and wallet navigation, Sede pages, oracles, and model filing portals. It also records the notifications query’s ten-year lookback and the `vernotif` detail action. The accompanying text says that the action can serve an unread notification and legally complete service, so the reader is intended to use it only for rows AEAT already marks read; the constant itself cannot enforce that condition. Similarly, `AeatLiveSafety` action-pattern lists describe reviewed action categories but explicitly do not authorize writes. A deployment still depends on the calling adapters’ gates and on selectors remaining current as AEAT changes its pages. external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.py (`src/cadrumo/core/external_constants.py`) external_constants.toml (`src/cadrumo/core/external_constants.toml`) external_constants.toml (`src/cadrumo/core/external_constants.toml`)

## Evidence provenance and history semantics

`FieldOrigin` records how each proposed value was obtained: structured bytes, text extraction/rules, vision, mapped table cells, operator entry, or deterministic derivation. `FieldGroundingOutcome` separately records which verification ran and what it found: independent reconciliation, source anchoring, no anchor, ambiguity, or contradiction. Neither axis is a numeric confidence score. This lets consumers distinguish exact parsing from model transcription and distinguish a checked value from one that merely lacks a failed check. `FieldRole` defines the closed vocabulary for tabular columns, including distinct invoice and bank-statement roles; an unknown column stays `UNMAPPED` and is reported rather than copied under a guessed meaning. field_origin.py (`src/cadrumo/core/field_origin.py`) field_grounding.py (`src/cadrumo/core/field_grounding.py`) field_role.py (`src/cadrumo/core/field_role.py`)

`FiledHistoryDiscoverySignal` preserves whether a `(modelo, year)` pair came from profile applicability or AEAT’s offered register options. Profile applicability can support a completeness warning when no declaration is found. The AEAT option list is not proven taxpayer-specific, so it only widens the walk and must not be described as confirmed filing coverage. This keeps a zero-row result tied to the strength of the discovery evidence. filed_history_discovery_signal.py (`src/cadrumo/core/filed_history_discovery_signal.py`)

## Filesystem controls and producer-key inventory

`file_permissions.py` restricts directories to the operator account: mode `0700` on POSIX and a protected Windows DACL with inherited grants for descendants. The public helper is best-effort and logs/swallow failures; this interface returns no success status, so a caller cannot establish from its return value that the requested hardening succeeded. `file_change_time_ns` uses Windows `FILE_BASIC_INFO.ChangeTime` because Windows `stat().st_ctime` is creation time, while other platforms use `st_ctime_ns`; this is a metadata signal for immutable-file admission, not a content digest. file_permissions.py (`src/cadrumo/core/file_permissions.py`) file_permissions.py (`src/cadrumo/core/file_permissions.py`) file_permissions.py (`src/cadrumo/core/file_permissions.py`) file_change_time.py (`src/cadrumo/core/file_change_time.py`) file_change_time.py (`src/cadrumo/core/file_change_time.py`)

`FilingProducerKey` is a large closed identity set for values supplied to the export boundary. Its semantic keys distinguish presenter, taxpayer and declaration contact; selected accounts; amendment flags; and model-specific parties and form facts. The Modelo 360 and IRNR families keep different address and payment/refund account shapes where their official forms impose different fields. The enum therefore helps prevent a registry layout from sourcing a value from the wrong role or shape. It is an identity vocabulary, however, not proof that a runtime producer supplies each identity. The file itself documents that 200 of 238 pre-existing keys have no runtime producer, so the declared registry/export contract materially exceeds wired producer coverage. This is a concrete integration gap to keep visible when assessing filing completeness. filing_producer_key.py (`src/cadrumo/core/filing_producer_key.py`) filing_producer_key.py (`src/cadrumo/core/filing_producer_key.py`) filing_producer_key.py (`src/cadrumo/core/filing_producer_key.py`)

Other small contracts include strict bytes-to-hex producer identities and a complete-write descriptor helper that loops over short OS writes and refuses no-progress results. Those primitives support persistence and cryptographic callers but do not themselves define storage policy. filing_producer_key.py (`src/cadrumo/core/filing_producer_key.py`) descriptor_write.py (`src/cadrumo/core/descriptor_write.py`)

## Assessment

The strongest design choices are typed, import-light external configuration; lazy isolation of the most volatile portal surface; durable provenance for individual extracted fields; conservative treatment of uncertain history coverage; and semantic producer keys that preserve form-specific distinctions. The main operational risks visible here are the gap between enumerated producer keys and runtime value supply, best-effort permission hardening with no result channel, and portal markers that must track an external site. The external constants and legal annotations have not been checked against live AEAT services in this static pass, and the key-coverage claim needs comparison with the actual producer registrations and current supported registry revisions.

## Complete assigned-file coverage

- external_constants.py (`src/cadrumo/core/external_constants.py`) — lines 1–547
- external_constants.toml (`src/cadrumo/core/external_constants.toml`) — lines 1–305
- field_grounding.py (`src/cadrumo/core/field_grounding.py`) — lines 1–77
- field_origin.py (`src/cadrumo/core/field_origin.py`) — lines 1–81
- field_role.py (`src/cadrumo/core/field_role.py`) — lines 1–142
- file_change_time.py (`src/cadrumo/core/file_change_time.py`) — lines 1–91
- file_permissions.py (`src/cadrumo/core/file_permissions.py`) — lines 1–225
- filed_history_discovery_signal.py (`src/cadrumo/core/filed_history_discovery_signal.py`) — lines 1–55
- filing_producer_key.py (`src/cadrumo/core/filing_producer_key.py`) — lines 1–787
<!-- /preserved:article -->
