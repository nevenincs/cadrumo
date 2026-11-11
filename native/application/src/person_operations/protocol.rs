use super::failure::{Failure, Outcome};

use super::timestamps::utc_isoformat;
use crate::canonical_json::canonical_json;
use crate::value::Sha256Digest;
use serde_json::{Map, Value, json};
use std::collections::BTreeSet;

pub(super) const PROJECTION_PAGE_BYTES: usize = 32_768;
pub(super) const PROJECTION_PAGE_MAX_ENCODED: usize = 4 * PROJECTION_PAGE_BYTES.div_ceil(3);
/// The longest document the relay carries either way: a settled result it
/// assembles from pages, and a payload or financial input it submits, in
/// bytes of compact JSON. A submission too large for one runtime frame is
/// streamed to the runtime's staging, which takes no more than this.
pub const PROJECTION_DOCUMENT_MAX_BYTES: usize = 16_777_216;
pub(super) const SUBJECT_REF_MAX_CHARS: usize = 256;
/// The product's one public schema for a refused or failed operation's
/// recorded detail: its registered code, message key, scrubbed context and
/// any typed precondition verdict. No definition contract names it.
pub(super) const ERROR_DETAIL_SCHEMA_ID: &str = "operation.error_detail";
pub(super) const ERROR_DETAIL_SCHEMA_VERSION: u64 = 1;
pub(super) const ERROR_DETAIL_SCHEMA_FINGERPRINT: &str =
    "423ca2a97d535add54e123c197e8afe800c6f93c7a3d94d2030230bf7d985b4e";

/// The runtime's transport refusals: it failed rather than denied, so the
/// relay names none of them and answers `unavailable`.
pub(super) const RUNTIME_REFUSAL_CODES: [&str; 12] = [
    "runtime_unavailable",
    "runtime_endpoint_not_ready",
    "runtime_owner_busy",
    "runtime_endpoint_untrusted",
    "runtime_peer_untrusted",
    "runtime_version_mismatch",
    "runtime_root_mismatch",
    "runtime_invalid_frame",
    "runtime_connection_closed",
    "runtime_timeout",
    "runtime_draining",
    "runtime_containment_unavailable",
];
pub(super) const REPLY_KINDS: [&str; 7] = [
    "operation_submitted",
    "operation_acknowledged",
    "operation_observed",
    "operation_contract",
    "operation_projected",
    "operation_page",
    "operation_managed",
];
pub(super) const ENVELOPE: [&str; 4] = ["kind", "request_id", "runtime_boot_id", "connection_id"];
pub(super) const SECRET_REQUIREMENT_KEYS: [&str; 5] = [
    "identity",
    "interaction_id",
    "revision",
    "secret_kind",
    "expires_at",
];
pub(super) const SECRET_IDENTITY_KEYS: [&str; 3] = ["operation_id", "definition_id", "subject_ref"];

pub(super) const LIFECYCLES: [&str; 8] = [
    "created",
    "queued",
    "running",
    "waiting_for_interaction",
    "waiting_for_external",
    "cancellation_requested",
    "settling",
    "terminal",
];
pub(super) const TERMINAL_CONDITIONS: [&str; 6] = [
    "succeeded",
    "refused",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
];
pub(super) const OBSERVATION_REFUSALS: [&str; 6] = [
    "unsupported_operation_observation_version",
    "unknown_operation",
    "cursor_ahead",
    "invalid_cursor",
    "definition_contract_mismatch",
    "observation_unavailable",
];
pub(super) const RESULT_REFUSALS: [&str; 8] = [
    "unsupported_result_projection_version",
    "unknown_operation",
    "operation_not_terminal",
    "operation_not_successful",
    "stale_operation_revision",
    "definition_contract_mismatch",
    "result_schema_mismatch",
    "result_projection_unavailable",
];
pub(super) const RESPONSE_REFUSALS: [&str; 5] = [
    "unsupported_response_control_version",
    "unknown_operation",
    "response_not_pending",
    "stale_operation_revision",
    "response_authority_unavailable",
];
pub(super) const CANCELLATION_REFUSALS: [&str; 6] = [
    "unsupported_cancellation_version",
    "unknown_operation",
    "stale_operation_revision",
    "operation_terminal",
    "cancellation_unsupported",
    "cancellation_unavailable",
];
pub(super) const PROFILE_VIEW_REFUSALS: [&str; 3] =
    ["stale_revision", "item_too_large", "projection_unavailable"];
pub(super) const PROFILE_VIEW_PAGE_KINDS: [&str; 7] = [
    "facts",
    "preferences",
    "issues",
    "readiness_issues",
    "overview",
    "status",
    "questions",
];
pub(super) const PROFILE_SETUP_STATES: [&str; 2] = ["incomplete", "complete"];

pub(super) const CONTRACT_KEYS: [&str; 26] = [
    "manifest_version",
    "definition_id",
    "action_reference",
    "request_schema",
    "subject_reference",
    "result_schema",
    "refusal_detail_codes",
    "review_projection_schema",
    "interaction_response_schema",
    "workspace_refresh_target_schema",
    "interaction_kinds",
    "request_storage",
    "durability",
    "cancellation",
    "deadline",
    "replay",
    "baseline",
    "sensitive_input",
    "conflict_scope",
    "owned_resources",
    "permitted_effects",
    "close_policy",
    "reconciliation_policy",
    "ephemeral_secret_required",
    "transient_financial_operand",
    "definition_contract_digest",
];
/// The contract members with a default, which a document may leave out.
pub(super) const CONTRACT_DEFAULTED: [&str; 2] =
    ["manifest_version", "transient_financial_operand"];
/// The contract members that are sets: their digest spells them sorted.
pub(super) const CONTRACT_SETS: [&str; 4] = [
    "interaction_kinds",
    "owned_resources",
    "permitted_effects",
    "refusal_detail_codes",
];
pub(super) const CONTRACT_POLICIES: [&str; 10] = [
    "request_storage",
    "durability",
    "cancellation",
    "deadline",
    "replay",
    "baseline",
    "sensitive_input",
    "conflict_scope",
    "close_policy",
    "reconciliation_policy",
];
pub(super) const PROJECTION_KEYS: [&str; 29] = [
    "observation_version",
    "operation_id",
    "definition_id",
    "subject_ref",
    "revision",
    "anchor_cursor",
    "definition_contract",
    "contract_set_digest",
    "lifecycle",
    "terminal_condition",
    "effect",
    "phase_code",
    "started_at",
    "updated_at",
    "progress",
    "close_policy",
    "cancellation",
    "cancellable_now",
    "financial_operand_pending",
    "financial_operand_cancelled_before_delivery",
    "cancellation_requested",
    "cancellation_acknowledged",
    "execution_deadline_at",
    "cleanup_deadline_at",
    "pending_interaction",
    "result_ref",
    "refusal_ref",
    "failure_error_code",
    "diagnostic_ref",
];
pub(super) const PROJECTION_DEFAULTED: [&str; 3] = [
    "observation_version",
    "financial_operand_pending",
    "financial_operand_cancelled_before_delivery",
];
pub(super) const REVIEW_PENDING_KEYS: [&str; 8] = [
    "disposition",
    "operation_id",
    "interaction_id",
    "revision",
    "presentation_code",
    "response_schema",
    "expires_at",
    "review_reference",
];
pub(super) const REVIEW_REFERENCE_KEYS: [&str; 6] = [
    "operation_id",
    "interaction_id",
    "revision",
    "review_projection_schema",
    "definition_contract_digest",
    "expires_at",
];
pub(super) const UNSUPPORTED_PENDING_KEYS: [&str; 7] = [
    "disposition",
    "interaction_kind",
    "interaction_id",
    "revision",
    "presentation_code",
    "unsupported_code",
    "expires_at",
];
pub(super) const EVENT_PAGE_KEYS: [&str; 8] = [
    "observation_version",
    "operation_id",
    "anchor_cursor",
    "requested_cursor",
    "status",
    "events",
    "next_cursor",
    "restart_cursor",
];
pub(super) const PROFILE_VIEW_PAGE_KEYS: [&str; 13] = [
    "profile_id",
    "page_kind",
    "outcome",
    "refusal_code",
    "record_revision",
    "content_digest",
    "setup_state",
    "schema_version",
    "valid",
    "cursor",
    "next_cursor",
    "total_items",
    "items",
];
pub(super) const PROFILE_VIEW_PAGE_REQUIRED: [&str; 10] = [
    "profile_id",
    "page_kind",
    "outcome",
    "record_revision",
    "content_digest",
    "setup_state",
    "schema_version",
    "valid",
    "cursor",
    "total_items",
];
pub(super) fn members(value: Value) -> Map<String, Value> {
    match value {
        Value::Object(members) => members,
        _ => Map::new(),
    }
}

pub(super) fn text<'a>(document: &'a Map<String, Value>, key: &str) -> Option<&'a str> {
    document.get(key).and_then(Value::as_str)
}

/// A non-empty text member of the parent's request.
pub(super) fn argument_text<'a>(request: &'a Map<String, Value>, key: &str) -> Outcome<&'a str> {
    match request.get(key) {
        Some(Value::String(value)) if !value.is_empty() => Ok(value),
        _ => Err(Failure::Invalid),
    }
}

/// A non-negative integer member of the parent's request; a boolean or a
/// fraction is not a count.
pub(super) fn argument_count(request: &Map<String, Value>, key: &str) -> Outcome<u64> {
    request
        .get(key)
        .and_then(Value::as_u64)
        .ok_or(Failure::Invalid)
}

pub(super) fn is_hex64(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

/// An operation id the parent named, as its request model strips and checks it.
pub(super) fn request_hex64(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    is_hex64(trimmed).then_some(trimmed)
}

pub(super) fn hex64<'a>(document: &'a Map<String, Value>, key: &str) -> Outcome<&'a str> {
    text(document, key)
        .filter(|value| is_hex64(value))
        .ok_or_else(Failure::frame)
}

pub(super) fn count(document: &Map<String, Value>, key: &str) -> Outcome<u64> {
    document
        .get(key)
        .and_then(Value::as_u64)
        .ok_or_else(Failure::frame)
}

pub(super) fn flag(document: &Map<String, Value>, key: &str) -> Outcome<bool> {
    document
        .get(key)
        .and_then(Value::as_bool)
        .ok_or_else(Failure::frame)
}

pub(super) fn nullable_text(document: &Map<String, Value>, key: &str) -> Outcome<Option<String>> {
    match document.get(key) {
        Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => Ok(Some(value.clone())),
        _ => Err(Failure::frame()),
    }
}

pub(super) fn one_of<'a>(
    document: &'a Map<String, Value>,
    key: &str,
    values: &[&str],
) -> Outcome<&'a str> {
    text(document, key)
        .filter(|value| values.contains(value))
        .ok_or_else(Failure::frame)
}

/// Whether `document` names only `allowed` members and every `required` one.
pub(super) fn closed(document: &Map<String, Value>, allowed: &[&str], required: &[&str]) -> bool {
    document.keys().all(|key| allowed.contains(&key.as_str()))
        && required.iter().all(|key| document.contains_key(*key))
}

/// Whether a version literal with a default of 1 is absent or 1.
pub(super) fn version_one(document: &Map<String, Value>, key: &str) -> bool {
    document
        .get(key)
        .is_none_or(|value| value.as_u64() == Some(1))
}

/// Requires a reply of `kind` carrying exactly `fields` beside its envelope.
pub(super) fn envelope(reply: &Map<String, Value>, kind: &str, fields: &[&str]) -> Outcome<()> {
    let allowed: Vec<&str> = ENVELOPE.iter().chain(fields).copied().collect();
    if text(reply, "kind") != Some(kind) || !closed(reply, &allowed, fields) {
        return Err(Failure::frame());
    }
    Ok(())
}

/// `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$` with at least `separated` groups after the first.
pub(super) fn dotted(value: &str, separated: usize) -> bool {
    let parts: Vec<&str> = value.split(['.', '_', '-']).collect();
    parts.len() > separated
        && parts[0].starts_with(|first: char| first.is_ascii_lowercase())
        && parts.iter().all(|part| {
            !part.is_empty()
                && part
                    .bytes()
                    .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        })
}

pub(super) fn definition_id(value: &str) -> bool {
    (3..=128).contains(&value.len()) && dotted(value, 0)
}

/// `^[a-z][a-z0-9]*:[a-z0-9][a-z0-9._-]+$`, 3 to 128 characters.
pub(super) fn actor_reference(value: &str) -> bool {
    let Some((kind, name)) = value.split_once(':') else {
        return false;
    };
    (3..=128).contains(&value.len())
        && kind.starts_with(|first: char| first.is_ascii_lowercase())
        && kind
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        && name.len() >= 2
        && name.starts_with(|first: char| first.is_ascii_lowercase() || first.is_ascii_digit())
        && name.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || b"._-".contains(&byte)
        })
}

/// `^sha256:(?:[0-9a-f]{12}|[0-9a-f]{64})$`
pub(super) fn diagnostic_reference(value: &str) -> bool {
    value.strip_prefix("sha256:").is_some_and(|digest| {
        (digest.len() == 12 || digest.len() == 64)
            && digest
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

/// A UUID as the product compares it: case, hyphens, braces and the URN
/// prefix do not matter.
pub(super) fn uuid_key(value: &str) -> Option<String> {
    let value = value.strip_prefix("urn:uuid:").unwrap_or(value);
    let value = value
        .strip_prefix('{')
        .and_then(|inner| inner.strip_suffix('}'))
        .unwrap_or(value);
    let key: String = value
        .chars()
        .filter(|character| *character != '-')
        .map(|character| character.to_ascii_lowercase())
        .collect();
    (key.len() == 32 && key.bytes().all(|byte| byte.is_ascii_hexdigit())).then_some(key)
}

pub(super) fn same_uuid(left: &str, right: &str) -> bool {
    uuid_key(left).is_some_and(|key| Some(key) == uuid_key(right))
}

/// A public schema identity: its id, version and fingerprint, nothing else.
pub(super) fn schema_identity(value: &Value) -> bool {
    let Some(identity) = value.as_object() else {
        return false;
    };
    let keys = ["schema_id", "schema_version", "schema_fingerprint"];
    closed(identity, &keys, &keys)
        && text(identity, "schema_id")
            .is_some_and(|id| (3..=160).contains(&id.chars().count()) && dotted(id, 1))
        && identity
            .get("schema_version")
            .and_then(Value::as_u64)
            .is_some_and(|version| version >= 1)
        && text(identity, "schema_fingerprint").is_some_and(is_hex64)
}

pub(super) fn nullable_schema(document: &Map<String, Value>, key: &str) -> Outcome<Option<Value>> {
    match document.get(key) {
        Some(Value::Null) => Ok(None),
        Some(value) if schema_identity(value) => Ok(Some(value.clone())),
        _ => Err(Failure::frame()),
    }
}

/// A closed refusal document's code: `version` is its version member and
/// `codes` the refusals its request may answer.
pub(super) fn refusal_code(
    document: &Map<String, Value>,
    version: &str,
    codes: &[&str],
) -> Outcome<String> {
    let allowed = [
        "outcome",
        version,
        "code",
        "requested_version",
        "supported_version",
        "diagnostic_ref",
    ];
    let requested = match document.get("requested_version") {
        Some(Value::Null) => true,
        Some(value) => value.as_u64().is_some_and(|version| version >= 1),
        None => false,
    };
    let diagnostic = match document.get("diagnostic_ref") {
        Some(Value::Null) => true,
        Some(Value::String(reference)) => diagnostic_reference(reference),
        _ => false,
    };
    if !closed(
        document,
        &allowed,
        &["code", "requested_version", "diagnostic_ref"],
    ) || text(document, "outcome") != Some("refused")
        || !version_one(document, version)
        || !version_one(document, "supported_version")
        || !requested
        || !diagnostic
    {
        return Err(Failure::frame());
    }
    one_of(document, "code", codes).map(str::to_owned)
}

/// A success document's `outcome`, which defaults to `success`.
pub(super) fn succeeded(document: &Map<String, Value>) -> bool {
    document
        .get("outcome")
        .is_none_or(|outcome| outcome.as_str() == Some("success"))
}

/// One registered definition's public contract, checked against its own digest.
#[derive(Clone, Debug)]
pub(super) struct Contract {
    /// The contract with its defaults filled and its sets sorted, for equality.
    pub(super) normalized: Value,
    pub(super) definition_id: String,
    pub(super) digest: String,
    pub(super) request_schema: Value,
    pub(super) result_schema: Option<Value>,
    pub(super) review_projection_schema: Option<Value>,
    pub(super) interaction_response_schema: Option<Value>,
    pub(super) refusal_detail_codes: Vec<String>,
    pub(super) interaction_kinds: Vec<String>,
    /// Whether a submission waits for a secret before it may start.
    pub(super) ephemeral_secret_required: bool,
}

pub(super) fn contract(value: &Value) -> Outcome<Contract> {
    let document = value.as_object().ok_or_else(Failure::frame)?;
    let required: Vec<&str> = CONTRACT_KEYS
        .iter()
        .filter(|key| !CONTRACT_DEFAULTED.contains(key))
        .copied()
        .collect();
    if !closed(document, &CONTRACT_KEYS, &required) {
        return Err(Failure::frame());
    }
    let mut normalized = document.clone();
    normalized
        .entry("manifest_version")
        .or_insert_with(|| json!(4));
    normalized
        .entry("transient_financial_operand")
        .or_insert(Value::Null);
    for key in CONTRACT_SETS {
        let items = normalized
            .get(key)
            .and_then(Value::as_array)
            .ok_or_else(Failure::frame)?;
        let set = items
            .iter()
            .map(|item| item.as_str().map(str::to_owned))
            .collect::<Option<BTreeSet<String>>>()
            .ok_or_else(Failure::frame)?;
        normalized.insert(
            key.to_owned(),
            Value::Array(set.into_iter().map(Value::String).collect()),
        );
    }
    let definition = text(&normalized, "definition_id")
        .filter(|id| definition_id(id))
        .ok_or_else(Failure::frame)?
        .to_owned();
    let digest = hex64(&normalized, "definition_contract_digest")?.to_owned();
    let request_schema = normalized
        .get("request_schema")
        .filter(|schema| schema_identity(schema))
        .cloned()
        .ok_or_else(Failure::frame)?;
    let result_schema = nullable_schema(&normalized, "result_schema")?;
    let review_projection_schema = nullable_schema(&normalized, "review_projection_schema")?;
    let interaction_response_schema = nullable_schema(&normalized, "interaction_response_schema")?;
    nullable_schema(&normalized, "workspace_refresh_target_schema")?;
    let strings = |key: &str| -> Vec<String> {
        normalized
            .get(key)
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_owned)
                    .collect()
            })
            .unwrap_or_default()
    };
    let refusal_detail_codes = strings("refusal_detail_codes");
    let interaction_kinds = strings("interaction_kinds");
    let shaped = normalized.get("manifest_version").and_then(Value::as_u64) == Some(4)
        && CONTRACT_POLICIES
            .iter()
            .all(|key| normalized.get(*key).is_some_and(Value::is_string))
        && normalized
            .get("ephemeral_secret_required")
            .is_some_and(Value::is_boolean)
        && normalized
            .get("action_reference")
            .is_some_and(|reference| reference.is_null() || reference.is_object())
        && normalized
            .get("subject_reference")
            .is_some_and(Value::is_object)
        && normalized
            .get("transient_financial_operand")
            .is_some_and(|operand| operand.is_null() || operand.is_object())
        && (refusal_detail_codes.is_empty() || result_schema.is_some());
    if !shaped {
        return Err(Failure::frame());
    }
    let mut governed = normalized.clone();
    governed.remove("definition_contract_digest");
    if content_hash(&Value::Object(governed)) != digest {
        return Err(Failure::frame());
    }
    let ephemeral_secret_required =
        normalized.get("ephemeral_secret_required") == Some(&Value::Bool(true));
    Ok(Contract {
        normalized: Value::Object(normalized),
        definition_id: definition,
        digest,
        request_schema,
        result_schema,
        review_projection_schema,
        interaction_response_schema,
        refusal_detail_codes,
        interaction_kinds,
        ephemeral_secret_required,
    })
}

/// A pending interaction, as an operation's projection publishes it.
#[derive(Clone, Debug)]
pub(super) enum Pending {
    None,
    Review(Review),
    Unsupported { kind: String, revision: u64 },
}

/// A review awaiting the person's answer, and the reference that reads it.
#[derive(Clone, Debug)]
pub(super) struct Review {
    pub(super) operation_id: String,
    pub(super) interaction_id: String,
    pub(super) revision: u64,
    /// When the review expires, spelled as the Python `isoformat`.
    pub(super) expires_at: Option<String>,
    pub(super) reference: Map<String, Value>,
    pub(super) response_schema: Value,
}

/// The current state of one operation.
#[derive(Clone, Debug)]
pub(super) struct Projection {
    pub(super) operation_id: String,
    pub(super) definition_id: String,
    pub(super) subject_ref: String,
    pub(super) revision: u64,
    pub(super) terminal: bool,
    pub(super) terminal_condition: Option<String>,
    pub(super) pending: Pending,
    pub(super) result_ref: Option<String>,
    pub(super) refusal_ref: Option<String>,
    pub(super) failure_error_code: Option<String>,
    pub(super) contract: Contract,
}

/// A successful observation: its document as published and its projection.
pub(super) struct Observation {
    pub(super) document: Map<String, Value>,
    pub(super) projection: Projection,
}

pub(super) enum Observed {
    Success(Box<Observation>),
    /// The runtime refused the observation with this code.
    Refused(String),
}

pub(super) fn nullable_utc(document: &Map<String, Value>, key: &str) -> Outcome<Option<String>> {
    match document.get(key) {
        Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => utc_isoformat(value).map(Some).ok_or_else(Failure::frame),
        _ => Err(Failure::frame()),
    }
}

pub(super) fn pending(value: Option<&Value>) -> Outcome<Pending> {
    let document = value
        .and_then(Value::as_object)
        .ok_or_else(Failure::frame)?;
    match text(document, "disposition") {
        Some("none") if document.len() == 1 => Ok(Pending::None),
        Some("review_available")
            if closed(document, &REVIEW_PENDING_KEYS, &REVIEW_PENDING_KEYS) =>
        {
            let reference = document
                .get("review_reference")
                .and_then(Value::as_object)
                .filter(|reference| {
                    closed(reference, &REVIEW_REFERENCE_KEYS, &REVIEW_REFERENCE_KEYS)
                })
                .ok_or_else(Failure::frame)?;
            let review = Review {
                operation_id: hex64(document, "operation_id")?.to_owned(),
                interaction_id: hex64(document, "interaction_id")?.to_owned(),
                revision: count(document, "revision")?,
                expires_at: nullable_utc(document, "expires_at")?,
                reference: reference.clone(),
                response_schema: document
                    .get("response_schema")
                    .filter(|schema| schema_identity(schema))
                    .cloned()
                    .ok_or_else(Failure::frame)?,
            };
            let matches = text(document, "presentation_code").is_some()
                && hex64(reference, "operation_id")? == review.operation_id
                && hex64(reference, "interaction_id")? == review.interaction_id
                && count(reference, "revision")? == review.revision
                && nullable_utc(reference, "expires_at")? == review.expires_at
                && reference
                    .get("review_projection_schema")
                    .is_some_and(schema_identity);
            hex64(reference, "definition_contract_digest")?;
            if !matches {
                return Err(Failure::frame());
            }
            Ok(Pending::Review(review))
        }
        Some("unsupported")
            if closed(
                document,
                &UNSUPPORTED_PENDING_KEYS,
                &UNSUPPORTED_PENDING_KEYS,
            ) =>
        {
            hex64(document, "interaction_id")?;
            nullable_utc(document, "expires_at")?;
            if text(document, "presentation_code").is_none()
                || text(document, "unsupported_code").is_none()
            {
                return Err(Failure::frame());
            }
            Ok(Pending::Unsupported {
                kind: one_of(document, "interaction_kind", &["input", "choice"])?.to_owned(),
                revision: count(document, "revision")?,
            })
        }
        _ => Err(Failure::frame()),
    }
}

pub(super) fn projection(value: Option<&Value>) -> Outcome<Projection> {
    let document = value
        .and_then(Value::as_object)
        .ok_or_else(Failure::frame)?;
    let required: Vec<&str> = PROJECTION_KEYS
        .iter()
        .filter(|key| !PROJECTION_DEFAULTED.contains(key))
        .copied()
        .collect();
    if !closed(document, &PROJECTION_KEYS, &required)
        || !version_one(document, "observation_version")
    {
        return Err(Failure::frame());
    }
    let contract = contract(&document["definition_contract"])?;
    let lifecycle = one_of(document, "lifecycle", &LIFECYCLES)?;
    let terminal_condition = match document.get("terminal_condition") {
        Some(Value::Null) => None,
        _ => Some(one_of(document, "terminal_condition", &TERMINAL_CONDITIONS)?.to_owned()),
    };
    let projection = Projection {
        operation_id: hex64(document, "operation_id")?.to_owned(),
        definition_id: text(document, "definition_id")
            .filter(|id| definition_id(id))
            .ok_or_else(Failure::frame)?
            .to_owned(),
        subject_ref: text(document, "subject_ref")
            .filter(|subject| (1..=SUBJECT_REF_MAX_CHARS).contains(&subject.chars().count()))
            .ok_or_else(Failure::frame)?
            .to_owned(),
        revision: count(document, "revision")?,
        terminal: lifecycle == "terminal",
        terminal_condition,
        pending: pending(document.get("pending_interaction"))?,
        result_ref: nullable_text(document, "result_ref")?,
        refusal_ref: nullable_text(document, "refusal_ref")?,
        failure_error_code: nullable_text(document, "failure_error_code")?,
        contract,
    };
    count(document, "anchor_cursor")?;
    nullable_utc(document, "updated_at")?.ok_or_else(Failure::frame)?;
    let cancellable_now = flag(document, "cancellable_now")?;
    let contract = &projection.contract;
    let condition = projection.terminal_condition.as_deref();
    let consistent = projection.terminal == condition.is_some()
        && (!projection.terminal
            || (matches!(projection.pending, Pending::None) && !cancellable_now))
        && contract.definition_id == projection.definition_id
        && document.get("close_policy") == contract.normalized.get("close_policy")
        && document.get("cancellation") == contract.normalized.get("cancellation")
        && !(projection.result_ref.is_some() && projection.refusal_ref.is_some())
        && (condition != Some("succeeded") || projection.result_ref.is_some())
        && (condition != Some("refused") || projection.refusal_ref.is_some())
        && (condition == Some("failed") || projection.failure_error_code.is_none())
        && (projection.terminal
            || (projection.result_ref.is_none() && projection.refusal_ref.is_none()));
    let pending_consistent = match &projection.pending {
        Pending::None => true,
        Pending::Unsupported { kind, revision } => {
            lifecycle == "waiting_for_interaction"
                && *revision == projection.revision
                && contract.interaction_kinds.contains(kind)
        }
        Pending::Review(review) => {
            lifecycle == "waiting_for_interaction"
                && review.revision == projection.revision
                && contract
                    .interaction_kinds
                    .iter()
                    .any(|kind| kind == "review")
                && review.operation_id == projection.operation_id
                && text(&review.reference, "definition_contract_digest")
                    == Some(contract.digest.as_str())
                && review.reference.get("review_projection_schema")
                    == contract.review_projection_schema.as_ref()
                && Some(&review.response_schema) == contract.interaction_response_schema.as_ref()
        }
    };
    if !consistent || !pending_consistent {
        return Err(Failure::frame());
    }
    Ok(projection)
}

pub(super) fn observed(reply: &Map<String, Value>) -> Outcome<Observed> {
    envelope(reply, "operation_observed", &["observation"])?;
    let observation = reply
        .get("observation")
        .and_then(Value::as_object)
        .ok_or_else(Failure::frame)?;
    match text(observation, "outcome") {
        Some("refused") => refusal_code(observation, "observation_version", &OBSERVATION_REFUSALS)
            .map(Observed::Refused),
        Some("success") => {
            let keys = ["outcome", "observation_version", "projection", "event_page"];
            if !closed(observation, &keys, &["outcome", "projection", "event_page"])
                || !version_one(observation, "observation_version")
            {
                return Err(Failure::frame());
            }
            let projection = projection(observation.get("projection"))?;
            let page = observation
                .get("event_page")
                .and_then(Value::as_object)
                .filter(|page| closed(page, &EVENT_PAGE_KEYS, &EVENT_PAGE_KEYS[1..]))
                .ok_or_else(Failure::frame)?;
            let anchor = observation
                .get("projection")
                .and_then(Value::as_object)
                .and_then(|projection| projection.get("anchor_cursor"));
            let events = page
                .get("events")
                .and_then(Value::as_array)
                .ok_or_else(Failure::frame)?;
            let anchored = text(page, "operation_id") == Some(projection.operation_id.as_str())
                && page.get("anchor_cursor") == anchor
                && version_one(page, "observation_version")
                && events.iter().all(|event| {
                    event
                        .get("revision")
                        .and_then(Value::as_u64)
                        .is_some_and(|revision| revision <= projection.revision)
                });
            if !anchored {
                return Err(Failure::frame());
            }
            Ok(Observed::Success(Box::new(Observation {
                document: observation.clone(),
                projection,
            })))
        }
        _ => Err(Failure::frame()),
    }
}

pub(super) fn content_hash(value: &Value) -> String {
    Sha256Digest::of(canonical_json(value).as_bytes()).to_string()
}
