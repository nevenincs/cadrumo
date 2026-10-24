//! Registered operations and the profile language for a person session this
//! process holds on its own runtime connection.
//!
//! A desktop window once carried these through its Python session-hold child.
//! The relay names no definition, subject or wording: the window names a
//! definition, a subject and a typed request, and the runtime's registered
//! operation validation decides whether the session may submit it. The relay
//! then passes back what the runtime publishes: an operation's observation,
//! its settled result or refusal document, a pending review with the digest of
//! exactly what it showed, an answer bound to that digest, and a cancellation
//! at the observed revision. Documents pass unchanged, so the product that
//! registered an operation owns its meaning and its words.
//!
//! The language read and set run the registered `user-profile.view` and
//! `user-profile.field-mutation` operations to settlement, observing again on
//! the runtime's `operation_changed` cue for the held session instead of on a
//! timer.
//!
//! Requests, reply checks and refusal codes follow the Python client. That
//! client validated each reply against the product's typed models; here the
//! fields the client relies on and their cross-checks are verified, and a
//! definition contract must reproduce its own digest. Digests use the
//! product's canonical JSON: sorted keys, compact separators, unescaped UTF-8
//! and Python's spelling of numbers.

use crate::runtime_client::{
    Admitted, Event, Pushed, Refusal, SessionExchange, base64_decode, request_id,
};
use crate::value::Sha256Digest;
use serde_json::{Map, Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::mpsc,
    time::{Duration, Instant, SystemTime},
};
use zeroize::{Zeroize, Zeroizing};

/// One budget for a whole relay action, every exchange included.
const RELAY_BUDGET: Duration = Duration::from_secs(120);
/// The budget of one profile view read and of one profile mutation.
const PROFILE_BUDGET: Duration = Duration::from_secs(60);
const RELAY_EVENT_PAGE: u64 = 64;
const PROFILE_VIEW_EVENT_PAGE: u64 = 32;
const PROFILE_MUTATION_EVENT_PAGE: u64 = 1;
const MAX_WATCHED: usize = 16;
/// The longest relayed payload, in characters of its compact JSON.
pub const MAX_PAYLOAD_TEXT: usize = 12_288;
const MAXIMUM_FRAME_BYTES: usize = 64 * 1024;
const PROJECTION_PAGE_BYTES: usize = 32_768;
const PROJECTION_PAGE_MAX_ENCODED: usize = 4 * PROJECTION_PAGE_BYTES.div_ceil(3);
/// The longest settled document the relay assembles from result pages.
pub const PROJECTION_DOCUMENT_MAX_BYTES: usize = 16_777_216;
const SUBJECT_REF_MAX_CHARS: usize = 256;
const PROFILE_VIEW: &str = "user-profile.view";
const PROFILE_FIELD_MUTATION: &str = "user-profile.field-mutation";
const PROFILE_FIELD_MUTATION_RESULT: &str = "user-profile.field-mutation.result";
const OUTPUT_LANGUAGE_PATH: &str = "preferences.output_language";
const OUTPUT_LANGUAGES: [&str; 4] = ["es", "en", "ca", "hu"];
const PROFILE_VIEW_MAX_ITEMS: u64 = 128;
const PROFILE_VIEW_MAX_PAGES: usize = 512;

/// The runtime's transport refusals: it failed rather than denied, so the
/// relay names none of them and answers `unavailable`.
const RUNTIME_REFUSAL_CODES: [&str; 12] = [
    "runtime_unavailable",
    "runtime_endpoint_not_ready",
    "runtime_owner_busy",
    "runtime_endpoint_untrusted",
    "runtime_peer_untrusted",
    "runtime_version_mismatch",
    "runtime_root_mismatch",
    "runtime_invalid_frame",
    "runtime_connection_closed",
    "runtime_deadline_exceeded",
    "runtime_draining",
    "runtime_containment_unavailable",
];
const REPLY_KINDS: [&str; 7] = [
    "operation_submitted",
    "operation_acknowledged",
    "operation_observed",
    "operation_contract",
    "operation_projected",
    "operation_page",
    "operation_managed",
];
const ENVELOPE: [&str; 4] = ["kind", "request_id", "runtime_boot_id", "connection_id"];

const LIFECYCLES: [&str; 8] = [
    "created",
    "queued",
    "running",
    "waiting_for_interaction",
    "waiting_for_external",
    "cancellation_requested",
    "settling",
    "terminal",
];
const TERMINAL_CONDITIONS: [&str; 6] = [
    "succeeded",
    "refused",
    "failed",
    "cancelled",
    "timed_out",
    "interrupted",
];
const OBSERVATION_REFUSALS: [&str; 6] = [
    "unsupported_operation_observation_version",
    "unknown_operation",
    "cursor_ahead",
    "invalid_cursor",
    "definition_contract_mismatch",
    "observation_unavailable",
];
const RESULT_REFUSALS: [&str; 8] = [
    "unsupported_result_projection_version",
    "unknown_operation",
    "operation_not_terminal",
    "operation_not_successful",
    "stale_operation_revision",
    "definition_contract_mismatch",
    "result_schema_mismatch",
    "result_projection_unavailable",
];
const RESPONSE_REFUSALS: [&str; 5] = [
    "unsupported_response_control_version",
    "unknown_operation",
    "response_not_pending",
    "stale_operation_revision",
    "response_authority_unavailable",
];
const CANCELLATION_REFUSALS: [&str; 6] = [
    "unsupported_cancellation_version",
    "unknown_operation",
    "stale_operation_revision",
    "operation_terminal",
    "cancellation_unsupported",
    "cancellation_unavailable",
];
const PROFILE_VIEW_REFUSALS: [&str; 3] =
    ["stale_revision", "item_too_large", "projection_unavailable"];
const PROFILE_VIEW_PAGE_KINDS: [&str; 7] = [
    "facts",
    "preferences",
    "issues",
    "readiness_issues",
    "overview",
    "status",
    "questions",
];
const PROFILE_SETUP_STATES: [&str; 2] = ["incomplete", "complete"];

const CONTRACT_KEYS: [&str; 26] = [
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
const CONTRACT_DEFAULTED: [&str; 2] = ["manifest_version", "transient_financial_operand"];
/// The contract members that are sets: their digest spells them sorted.
const CONTRACT_SETS: [&str; 4] = [
    "interaction_kinds",
    "owned_resources",
    "permitted_effects",
    "refusal_detail_codes",
];
const CONTRACT_POLICIES: [&str; 10] = [
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
const PROJECTION_KEYS: [&str; 29] = [
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
const PROJECTION_DEFAULTED: [&str; 3] = [
    "observation_version",
    "financial_operand_pending",
    "financial_operand_cancelled_before_delivery",
];
const REVIEW_PENDING_KEYS: [&str; 8] = [
    "disposition",
    "operation_id",
    "interaction_id",
    "revision",
    "presentation_code",
    "response_schema",
    "expires_at",
    "review_reference",
];
const REVIEW_REFERENCE_KEYS: [&str; 6] = [
    "operation_id",
    "interaction_id",
    "revision",
    "review_projection_schema",
    "definition_contract_digest",
    "expires_at",
];
const UNSUPPORTED_PENDING_KEYS: [&str; 7] = [
    "disposition",
    "interaction_kind",
    "interaction_id",
    "revision",
    "presentation_code",
    "unsupported_code",
    "expires_at",
];
const EVENT_PAGE_KEYS: [&str; 8] = [
    "observation_version",
    "operation_id",
    "anchor_cursor",
    "requested_cursor",
    "status",
    "events",
    "next_cursor",
    "restart_cursor",
];
const PROFILE_VIEW_PAGE_KEYS: [&str; 13] = [
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
const PROFILE_VIEW_PAGE_REQUIRED: [&str; 10] = [
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

/// Each relay action and the request members it takes beside `request_id` and `action`.
pub const RELAY_ACTION_KEYS: [(&str, &[&str]); 7] = [
    (
        "operation_submit",
        &["definition_id", "subject_ref", "payload"],
    ),
    (
        "operation_financial_submit",
        &["definition_id", "subject_ref", "input"],
    ),
    ("operation_observe", &["operation_id", "after_cursor"]),
    ("operation_result", &["operation_id"]),
    ("operation_review", &["operation_id"]),
    (
        "operation_respond",
        &[
            "operation_id",
            "interaction_id",
            "revision",
            "review_digest",
            "decision",
        ],
    ),
    ("operation_cancel", &["operation_id", "expected_revision"]),
];

/// Why a relay action or a language read or set did not answer.
#[derive(Debug)]
pub enum RelayFailure {
    /// The relay's closed refusal; the session keeps holding. A busy subject
    /// names the operation that holds it. The code `unavailable` is never a
    /// decision: the runtime, its transport or a reply failed, so a mutation
    /// it carried may have committed.
    Refused {
        code: String,
        holder_operation_id: Option<String>,
    },
    /// A malformed request: the session answers `invalid` and ends.
    Invalid,
    /// The runtime, its transport or a reply failed: the session answers
    /// `unavailable` and ends. The refusal says which, for the log.
    Unavailable(Refusal),
}

/// The profile's saved output language and the revision it was read at.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProfileLanguage {
    /// `es`, `en`, `ca` or `hu`; `None` when the profile saved none.
    pub language: Option<String>,
    pub record_revision: u64,
    pub content_digest: String,
}

/// A failure before it is answered: a closed refusal, the runtime's failure,
/// or a malformed request.
#[derive(Debug)]
enum Failure {
    Refused {
        code: String,
        holder_operation_id: Option<String>,
    },
    Runtime(Refusal),
    Invalid,
}

type Outcome<T> = Result<T, Failure>;

impl Failure {
    fn code(code: &str) -> Self {
        Self::Refused {
            code: code.to_owned(),
            holder_operation_id: None,
        }
    }

    fn frame() -> Self {
        Self::Runtime(Refusal::InvalidFrame)
    }

    /// A relay answers every runtime failure with its closed `unavailable`.
    fn relayed(self) -> RelayFailure {
        match self {
            Self::Refused {
                code,
                holder_operation_id,
            } => RelayFailure::Refused {
                code,
                holder_operation_id,
            },
            Self::Runtime(_) => RelayFailure::Refused {
                code: "unavailable".to_owned(),
                holder_operation_id: None,
            },
            Self::Invalid => RelayFailure::Invalid,
        }
    }

    /// A language read or set has no closed refusal: any failure ends the session.
    fn held(self) -> RelayFailure {
        match self {
            Self::Refused {
                code,
                holder_operation_id,
            } => RelayFailure::Unavailable(Refusal::Denied {
                code,
                sign_in: None,
                holder_operation_id,
            }),
            Self::Runtime(refusal) => RelayFailure::Unavailable(refusal),
            Self::Invalid => RelayFailure::Invalid,
        }
    }
}

impl From<Refusal> for Failure {
    fn from(refusal: Refusal) -> Self {
        match refusal {
            Refusal::Denied {
                code,
                holder_operation_id,
                ..
            } if !RUNTIME_REFUSAL_CODES.contains(&code.as_str()) => Self::Refused {
                code,
                holder_operation_id,
            },
            other => Self::Runtime(other),
        }
    }
}

/// The registered operations one held person session submitted and still follows.
#[derive(Debug, Default)]
pub struct OperationRelay {
    watched: BTreeSet<String>,
}

impl OperationRelay {
    pub fn new() -> Self {
        Self::default()
    }

    /// Whether a cue may matter: an operation this relay observed is unsettled.
    pub fn watching(&self) -> bool {
        !self.watched.is_empty()
    }

    /// Runs one relay action for the held session and returns its reply's own
    /// members: `kind` and what the action names, without the session's
    /// coordinates, which the caller stamps. `request` is the parent's request;
    /// its `request_id` and `action` are not read.
    pub fn handle(
        &mut self,
        connection: &dyn SessionExchange,
        session: &Admitted,
        action: &str,
        request: &Map<String, Value>,
    ) -> Result<Map<String, Value>, RelayFailure> {
        let held = Held {
            connection,
            session,
        };
        let deadline = Instant::now() + RELAY_BUDGET;
        self.run(&held, action, request, deadline)
            .map_err(Failure::relayed)
    }

    fn run(
        &mut self,
        held: &Held,
        action: &str,
        request: &Map<String, Value>,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        if action == "operation_submit" {
            return self.submit(held, request, deadline);
        }
        if action == "operation_financial_submit" {
            return self.submit_financial(held, request, deadline);
        }
        let operation_id = argument_text(request, "operation_id")?;
        match action {
            "operation_observe" => {
                let after_cursor = argument_count(request, "after_cursor")?;
                let observation = self.observe(held, operation_id, after_cursor, deadline)?;
                Ok(members(json!({
                    "kind": "operation_observed",
                    "observation": Value::Object(observation.document),
                })))
            }
            "operation_result" => self.result(held, operation_id, deadline),
            "operation_review" => {
                let (pending, document) = self.review(held, operation_id, deadline)?;
                let review_digest = content_hash(&Value::Object(document.clone()));
                Ok(members(json!({
                    "kind": "operation_review",
                    "operation_id": operation_id,
                    "interaction_id": pending.interaction_id,
                    "revision": pending.revision,
                    "expires_at": pending.expires_at,
                    "review_digest": review_digest,
                    "document": Value::Object(document),
                })))
            }
            "operation_respond" => self.respond(held, operation_id, request, deadline),
            "operation_cancel" => {
                let expected_revision = argument_count(request, "expected_revision")?;
                cancel(held, operation_id, expected_revision, deadline)
            }
            _ => Err(Failure::Invalid),
        }
    }

    fn watch(&mut self, projection: &Projection) {
        if projection.terminal {
            self.watched.remove(&projection.operation_id);
        } else if self.watched.contains(&projection.operation_id)
            || self.watched.len() < MAX_WATCHED
        {
            self.watched.insert(projection.operation_id.clone());
        }
    }

    fn submit(
        &mut self,
        held: &Held,
        request: &Map<String, Value>,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let payload = request.get("payload").ok_or(Failure::Invalid)?;
        if !payload.is_object() {
            return Err(Failure::Invalid);
        }
        // A payload can carry private input, such as an account's IBAN: its
        // encoding and the request that carried it are overwritten once sent.
        let payload_json = Zeroizing::new(compact_json(payload));
        if payload_json.chars().count() > MAX_PAYLOAD_TEXT {
            return Err(Failure::Invalid);
        }
        let definition_id = argument_text(request, "definition_id")?;
        let subject_ref = argument_text(request, "subject_ref")?;
        let operation_id = submit(held, definition_id, subject_ref, &payload_json, deadline)?.0;
        self.started(held, operation_id, deadline)
    }

    /// Hands the parent's input to the runtime once, as its financial input,
    /// and starts the operation. The runtime refuses a definition whose
    /// contract takes no financial operand, so the relay names none; the
    /// encoded input and the request that carried it are overwritten once sent.
    fn submit_financial(
        &mut self,
        held: &Held,
        request: &Map<String, Value>,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let input = request.get("input").ok_or(Failure::Invalid)?;
        if !input.is_object() {
            return Err(Failure::Invalid);
        }
        let definition = argument_text(request, "definition_id")?;
        let subject_ref = argument_text(request, "subject_ref")?;
        let subject_length = subject_ref.chars().count();
        if !definition_id(definition) || !(1..=SUBJECT_REF_MAX_CHARS).contains(&subject_length) {
            return Err(Failure::frame());
        }
        let input_json = Zeroizing::new(compact_json(input));
        let reply = held.exchange_wiping(
            "operation_financial_input",
            json!({
                "definition_id": definition,
                "subject_ref": subject_ref,
                "payload_json": input_json.as_str(),
                "idempotency_key": null,
            }),
            deadline,
        )?;
        drop(input_json);
        let operation_id = submitted_receipt(&reply)?.0;
        self.started(held, operation_id, deadline)
    }

    fn started(
        &mut self,
        held: &Held,
        operation_id: String,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        start(held, &operation_id, deadline)?;
        if self.watched.len() < MAX_WATCHED {
            self.watched.insert(operation_id.clone());
        }
        Ok(members(json!({
            "kind": "operation_submitted",
            "operation_id": operation_id,
        })))
    }

    fn observe(
        &mut self,
        held: &Held,
        operation_id: &str,
        after_cursor: u64,
        deadline: Instant,
    ) -> Outcome<Observation> {
        let wire_id = request_hex64(operation_id).ok_or_else(Failure::frame)?;
        let Observed::Success(observation) =
            observe_once(held, wire_id, after_cursor, RELAY_EVENT_PAGE, deadline)?
        else {
            return Err(Failure::code("unavailable"));
        };
        if observation.projection.operation_id != operation_id {
            return Err(Failure::code("unavailable"));
        }
        self.watch(&observation.projection);
        Ok(*observation)
    }

    fn result(
        &mut self,
        held: &Held,
        operation_id: &str,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let projection = self.observe(held, operation_id, 0, deadline)?.projection;
        let contract = &projection.contract;
        // A refusal its definition declares carries a detail document, read the same way as a result.
        let documented = projection.result_ref.is_some()
            || (projection.terminal_condition.as_deref() == Some("refused")
                && projection
                    .refusal_ref
                    .as_ref()
                    .is_some_and(|reference| contract.refusal_detail_codes.contains(reference)));
        let schema = match &contract.result_schema {
            Some(schema) if projection.terminal && documented => schema.clone(),
            _ => return Err(Failure::code("no_result")),
        };
        let document = read_result_document(held, &result_request(&projection, &schema), deadline)?;
        if document.get("result_schema") != Some(&schema)
            || text(&document, "definition_contract_digest") != Some(contract.digest.as_str())
        {
            return Err(Failure::code("unavailable"));
        }
        Ok(members(json!({
            "kind": "operation_result",
            "operation_id": operation_id,
            "definition_id": projection.definition_id,
            "document": Value::Object(document),
        })))
    }

    fn review(
        &mut self,
        held: &Held,
        operation_id: &str,
        deadline: Instant,
    ) -> Outcome<(Review, Map<String, Value>)> {
        let Pending::Review(pending) = self
            .observe(held, operation_id, 0, deadline)?
            .projection
            .pending
        else {
            return Err(Failure::code("not_pending"));
        };
        let reply = held.exchange(
            "operation_review",
            json!({"review": {"review_projection_version": 1, "reference": pending.reference}}),
            deadline,
        )?;
        if text(&reply, "kind") != Some("operation_projected") {
            return Err(Failure::code("not_pending"));
        }
        let projected = projected(&reply)?;
        if projected.operation_id != pending.operation_id
            || projected.projection_kind != "review"
            || text(&projected.document, "outcome") != Some("success")
        {
            return Err(Failure::code("not_pending"));
        }
        let reference = &pending.reference;
        if projected.document.get("projection_schema") != reference.get("review_projection_schema")
            || projected.document.get("definition_contract_digest")
                != reference.get("definition_contract_digest")
        {
            return Err(Failure::code("unavailable"));
        }
        Ok((pending, projected.document))
    }

    fn respond(
        &mut self,
        held: &Held,
        operation_id: &str,
        request: &Map<String, Value>,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let decision = match request.get("decision").ok_or(Failure::Invalid)? {
            Value::String(decision) if decision == "apply" || decision == "reject" => {
                decision.clone()
            }
            _ => return Err(Failure::Invalid),
        };
        let interaction_id = argument_text(request, "interaction_id")?;
        let revision = argument_count(request, "revision")?;
        let review_digest = argument_text(request, "review_digest")?;
        // Read the review again: an answer approves exactly the document the person saw.
        let (pending, document) = self.review(held, operation_id, deadline)?;
        if pending.interaction_id != interaction_id || pending.revision != revision {
            return Err(Failure::code("not_pending"));
        }
        if content_hash(&Value::Object(document)) != review_digest {
            return Err(Failure::code("review_changed"));
        }
        let actor_ref = format!("session:{}", held.session.session_id);
        if !actor_reference(&actor_ref) {
            return Err(Failure::frame());
        }
        let mut control = members(json!({
            "response_control_version": 1,
            "operation_id": pending.operation_id,
            "interaction_id": pending.interaction_id,
            "revision": pending.revision,
            "actor_ref": actor_ref,
        }));
        let reply = held.exchange(
            "operation_manage",
            json!({"management": Value::Object(control.clone())}),
            deadline,
        )?;
        let document = managed(&reply, &pending.operation_id)?;
        if text(document, "outcome") == Some("refused") {
            let code = refusal_code(document, "response_control_version", &RESPONSE_REFUSALS)?;
            return Err(Failure::code(&code));
        }
        let intents = response_control(document, &pending)?;
        if !intents.contains(&decision) {
            return Err(Failure::code("response_authority_required"));
        }
        control.insert("response_action".into(), decision.clone().into());
        control.insert("responded_at".into(), utc_now().into());
        if decision == "reject" {
            control.insert("reason_code".into(), Value::Null);
        }
        let reply = held.exchange(
            "operation_manage",
            json!({"management": Value::Object(control)}),
            deadline,
        )?;
        let document = managed(&reply, &pending.operation_id)?;
        if text(document, "outcome") == Some("refused") {
            let code = refusal_code(document, "response_control_version", &RESPONSE_REFUSALS)?;
            return Err(Failure::code(&code));
        }
        response_accepted(document, &pending, &decision)?;
        Ok(members(json!({
            "kind": "operation_responded",
            "operation_id": operation_id,
            "decision": decision,
        })))
    }
}

/// Reads the profile's saved output language through the registered
/// exact-profile view, within `deadline` and the view's own budget.
pub fn read_profile_language(
    connection: &dyn SessionExchange,
    session: &Admitted,
    deadline: Instant,
) -> Result<ProfileLanguage, RelayFailure> {
    read_language(
        &Held {
            connection,
            session,
        },
        deadline,
    )
    .map_err(Failure::held)
}

/// Sets only the output language through the guarded field mutation at the
/// revision just read, then reads it again. `language` must be `es`, `en`,
/// `ca` or `hu`.
pub fn set_profile_language(
    connection: &dyn SessionExchange,
    session: &Admitted,
    language: &str,
    deadline: Instant,
) -> Result<ProfileLanguage, RelayFailure> {
    if !OUTPUT_LANGUAGES.contains(&language) {
        return Err(RelayFailure::Invalid);
    }
    let held = Held {
        connection,
        session,
    };
    set_language(&held, language, deadline).map_err(Failure::held)
}

/// The held session's connection, for exchanges under its exact coordinates.
struct Held<'a> {
    connection: &'a dyn SessionExchange,
    session: &'a Admitted,
}

impl Held<'_> {
    /// Sends `action` with `fields` under the held session and returns a reply
    /// of a registered operation kind; a refusal is the runtime's.
    fn exchange(
        &self,
        action: &str,
        fields: Value,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let request = self.request(action, fields, deadline)?;
        self.send(&request, deadline)
    }

    /// As [`Held::exchange`], for a request carrying private input: every
    /// text the request held is overwritten once it is sent, sent or not.
    fn exchange_wiping(
        &self,
        action: &str,
        fields: Value,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let mut request = self.request(action, fields, deadline)?;
        sent_then_wiped(&mut request, |request| self.send(request, deadline))
    }

    fn request(&self, action: &str, fields: Value, deadline: Instant) -> Outcome<Value> {
        remaining(deadline)?;
        let mut request = members(json!({
            "action": action,
            "request_id": request_id(),
            "profile_id": self.session.profile_id,
            "session_id": self.session.session_id,
        }));
        request.extend(members(fields));
        Ok(Value::Object(request))
    }

    fn send(&self, request: &Value, deadline: Instant) -> Outcome<Map<String, Value>> {
        let encoded = Zeroizing::new(canonical_json(request));
        if encoded.len() > MAXIMUM_FRAME_BYTES {
            return Err(Failure::frame());
        }
        drop(encoded);
        let reply = self.connection.exchange(request, deadline)?;
        match text(&reply, "kind") {
            Some(kind) if REPLY_KINDS.contains(&kind) => Ok(reply),
            _ => Err(Failure::frame()),
        }
    }

    fn subject(&self) -> String {
        format!("profile:{}", self.session.profile_id)
    }
}

fn remaining(deadline: Instant) -> Outcome<Duration> {
    let left = deadline.saturating_duration_since(Instant::now());
    if left.is_zero() {
        return Err(Failure::Runtime(Refusal::DeadlineExceeded));
    }
    Ok(left)
}

fn members(value: Value) -> Map<String, Value> {
    match value {
        Value::Object(members) => members,
        _ => Map::new(),
    }
}

fn text<'a>(document: &'a Map<String, Value>, key: &str) -> Option<&'a str> {
    document.get(key).and_then(Value::as_str)
}

/// A non-empty text member of the parent's request.
fn argument_text<'a>(request: &'a Map<String, Value>, key: &str) -> Outcome<&'a str> {
    match request.get(key) {
        Some(Value::String(value)) if !value.is_empty() => Ok(value),
        _ => Err(Failure::Invalid),
    }
}

/// A non-negative integer member of the parent's request; a boolean or a
/// fraction is not a count.
fn argument_count(request: &Map<String, Value>, key: &str) -> Outcome<u64> {
    request
        .get(key)
        .and_then(Value::as_u64)
        .ok_or(Failure::Invalid)
}

fn is_hex64(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

/// An operation id the parent named, as its request model strips and checks it.
fn request_hex64(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    is_hex64(trimmed).then_some(trimmed)
}

fn hex64<'a>(document: &'a Map<String, Value>, key: &str) -> Outcome<&'a str> {
    text(document, key)
        .filter(|value| is_hex64(value))
        .ok_or_else(Failure::frame)
}

fn count(document: &Map<String, Value>, key: &str) -> Outcome<u64> {
    document
        .get(key)
        .and_then(Value::as_u64)
        .ok_or_else(Failure::frame)
}

fn flag(document: &Map<String, Value>, key: &str) -> Outcome<bool> {
    document
        .get(key)
        .and_then(Value::as_bool)
        .ok_or_else(Failure::frame)
}

fn nullable_text(document: &Map<String, Value>, key: &str) -> Outcome<Option<String>> {
    match document.get(key) {
        Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => Ok(Some(value.clone())),
        _ => Err(Failure::frame()),
    }
}

fn one_of<'a>(document: &'a Map<String, Value>, key: &str, values: &[&str]) -> Outcome<&'a str> {
    text(document, key)
        .filter(|value| values.contains(value))
        .ok_or_else(Failure::frame)
}

/// Whether `document` names only `allowed` members and every `required` one.
fn closed(document: &Map<String, Value>, allowed: &[&str], required: &[&str]) -> bool {
    document.keys().all(|key| allowed.contains(&key.as_str()))
        && required.iter().all(|key| document.contains_key(*key))
}

/// Whether a version literal with a default of 1 is absent or 1.
fn version_one(document: &Map<String, Value>, key: &str) -> bool {
    document
        .get(key)
        .is_none_or(|value| value.as_u64() == Some(1))
}

/// Requires a reply of `kind` carrying exactly `fields` beside its envelope.
fn envelope(reply: &Map<String, Value>, kind: &str, fields: &[&str]) -> Outcome<()> {
    let allowed: Vec<&str> = ENVELOPE.iter().chain(fields).copied().collect();
    if text(reply, "kind") != Some(kind) || !closed(reply, &allowed, fields) {
        return Err(Failure::frame());
    }
    Ok(())
}

/// `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$` with at least `separated` groups after the first.
fn dotted(value: &str, separated: usize) -> bool {
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

fn definition_id(value: &str) -> bool {
    (3..=128).contains(&value.len()) && dotted(value, 0)
}

/// `^[a-z][a-z0-9]*:[a-z0-9][a-z0-9._-]+$`, 3 to 128 characters.
fn actor_reference(value: &str) -> bool {
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
fn diagnostic_reference(value: &str) -> bool {
    value.strip_prefix("sha256:").is_some_and(|digest| {
        (digest.len() == 12 || digest.len() == 64)
            && digest
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

/// A UUID as the product compares it: case, hyphens, braces and the URN
/// prefix do not matter.
fn uuid_key(value: &str) -> Option<String> {
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

fn same_uuid(left: &str, right: &str) -> bool {
    uuid_key(left).is_some_and(|key| Some(key) == uuid_key(right))
}

/// A public schema identity: its id, version and fingerprint, nothing else.
fn schema_identity(value: &Value) -> bool {
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

fn nullable_schema(document: &Map<String, Value>, key: &str) -> Outcome<Option<Value>> {
    match document.get(key) {
        Some(Value::Null) => Ok(None),
        Some(value) if schema_identity(value) => Ok(Some(value.clone())),
        _ => Err(Failure::frame()),
    }
}

/// A closed refusal document's code: `version` is its version member and
/// `codes` the refusals its request may answer.
fn refusal_code(document: &Map<String, Value>, version: &str, codes: &[&str]) -> Outcome<String> {
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
fn succeeded(document: &Map<String, Value>) -> bool {
    document
        .get("outcome")
        .is_none_or(|outcome| outcome.as_str() == Some("success"))
}

/// One registered definition's public contract, checked against its own digest.
#[derive(Clone, Debug)]
struct Contract {
    /// The contract with its defaults filled and its sets sorted, for equality.
    normalized: Value,
    definition_id: String,
    digest: String,
    request_schema: Value,
    result_schema: Option<Value>,
    review_projection_schema: Option<Value>,
    interaction_response_schema: Option<Value>,
    refusal_detail_codes: Vec<String>,
    interaction_kinds: Vec<String>,
}

fn contract(value: &Value) -> Outcome<Contract> {
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
    })
}

/// A pending interaction, as an operation's projection publishes it.
#[derive(Clone, Debug)]
enum Pending {
    None,
    Review(Review),
    Unsupported { kind: String, revision: u64 },
}

/// A review awaiting the person's answer, and the reference that reads it.
#[derive(Clone, Debug)]
struct Review {
    operation_id: String,
    interaction_id: String,
    revision: u64,
    /// When the review expires, spelled as the Python `isoformat`.
    expires_at: Option<String>,
    reference: Map<String, Value>,
    response_schema: Value,
}

/// The current state of one operation.
#[derive(Clone, Debug)]
struct Projection {
    operation_id: String,
    definition_id: String,
    subject_ref: String,
    revision: u64,
    terminal: bool,
    terminal_condition: Option<String>,
    pending: Pending,
    result_ref: Option<String>,
    refusal_ref: Option<String>,
    failure_error_code: Option<String>,
    contract: Contract,
}

/// A successful observation: its document as published and its projection.
struct Observation {
    document: Map<String, Value>,
    projection: Projection,
}

enum Observed {
    Success(Box<Observation>),
    /// The runtime refused the observation with this code.
    Refused(String),
}

fn nullable_utc(document: &Map<String, Value>, key: &str) -> Outcome<Option<String>> {
    match document.get(key) {
        Some(Value::Null) => Ok(None),
        Some(Value::String(value)) => utc_isoformat(value).map(Some).ok_or_else(Failure::frame),
        _ => Err(Failure::frame()),
    }
}

fn pending(value: Option<&Value>) -> Outcome<Pending> {
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

fn projection(value: Option<&Value>) -> Outcome<Projection> {
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

fn observed(reply: &Map<String, Value>) -> Outcome<Observed> {
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

fn observe_once(
    held: &Held,
    operation_id: &str,
    after_cursor: u64,
    page_limit: u64,
    deadline: Instant,
) -> Outcome<Observed> {
    let reply = held.exchange(
        "operation_observe",
        json!({"observation": {
            "observation_version": 1,
            "operation_id": operation_id,
            "after_cursor": after_cursor,
            "page_limit": page_limit,
        }}),
        deadline,
    )?;
    observed(&reply)
}

/// Submits one registered request; returns the operation id and whether the
/// receipt asks for no secret.
fn submit(
    held: &Held,
    definition: &str,
    subject_ref: &str,
    payload_json: &str,
    deadline: Instant,
) -> Outcome<(String, bool)> {
    let subject_length = subject_ref.chars().count();
    if !definition_id(definition)
        || !(1..=SUBJECT_REF_MAX_CHARS).contains(&subject_length)
        || payload_json.chars().count() < 2
    {
        return Err(Failure::frame());
    }
    let reply = held.exchange_wiping(
        "operation_submit",
        json!({
            "definition_id": definition,
            "subject_ref": subject_ref,
            "payload_json": payload_json,
            "idempotency_key": null,
        }),
        deadline,
    )?;
    submitted_receipt(&reply)
}

/// The operation id of an `operation_submitted` reply, and whether its receipt
/// asks for no secret.
fn submitted_receipt(reply: &Map<String, Value>) -> Outcome<(String, bool)> {
    envelope(reply, "operation_submitted", &["receipt"])?;
    let receipt = reply
        .get("receipt")
        .and_then(Value::as_object)
        .filter(|receipt| {
            closed(
                receipt,
                &["submission_version", "operation_id", "secret_requirement"],
                &["operation_id", "secret_requirement"],
            ) && version_one(receipt, "submission_version")
        })
        .ok_or_else(Failure::frame)?;
    let secret_free = match receipt.get("secret_requirement") {
        Some(Value::Null) => true,
        Some(Value::Object(_)) => false,
        _ => return Err(Failure::frame()),
    };
    Ok((hex64(receipt, "operation_id")?.to_owned(), secret_free))
}

/// Admits a submitted operation; the acknowledgement is not settlement.
fn start(held: &Held, operation_id: &str, deadline: Instant) -> Outcome<()> {
    let reply = held.exchange(
        "operation_start",
        json!({"operation_id": operation_id}),
        deadline,
    )?;
    envelope(&reply, "operation_acknowledged", &["operation_id"])?;
    if hex64(&reply, "operation_id")? != operation_id {
        return Err(Failure::frame());
    }
    Ok(())
}

/// The document of an `operation_managed` reply for `operation_id`.
fn managed<'a>(
    reply: &'a Map<String, Value>,
    operation_id: &str,
) -> Outcome<&'a Map<String, Value>> {
    envelope(reply, "operation_managed", &["operation_id", "document"])?;
    if hex64(reply, "operation_id")? != operation_id {
        return Err(Failure::frame());
    }
    reply
        .get("document")
        .and_then(Value::as_object)
        .ok_or_else(Failure::frame)
}

struct Projected {
    operation_id: String,
    projection_kind: String,
    document: Map<String, Value>,
}

fn projected(reply: &Map<String, Value>) -> Outcome<Projected> {
    envelope(
        reply,
        "operation_projected",
        &["operation_id", "projection_kind", "document"],
    )?;
    Ok(Projected {
        operation_id: hex64(reply, "operation_id")?.to_owned(),
        projection_kind: one_of(reply, "projection_kind", &["result", "review"])?.to_owned(),
        document: reply
            .get("document")
            .and_then(Value::as_object)
            .cloned()
            .ok_or_else(Failure::frame)?,
    })
}

/// The intents a response-control success permits the session, for exactly `pending`.
fn response_control(document: &Map<String, Value>, pending: &Review) -> Outcome<Vec<String>> {
    let keys = [
        "outcome",
        "response_control_version",
        "operation_id",
        "interaction_id",
        "revision",
        "available",
        "permitted_intents",
    ];
    if !closed(document, &keys, &keys[2..])
        || !succeeded(document)
        || !version_one(document, "response_control_version")
    {
        return Err(Failure::frame());
    }
    let intents = document
        .get("permitted_intents")
        .and_then(Value::as_array)
        .ok_or_else(Failure::frame)?
        .iter()
        .map(|intent| {
            intent
                .as_str()
                .filter(|intent| ["apply", "reject"].contains(intent))
                .map(str::to_owned)
        })
        .collect::<Option<Vec<String>>>()
        .ok_or_else(Failure::frame)?;
    let available = flag(document, "available")?;
    if available == intents.is_empty()
        || hex64(document, "operation_id")? != pending.operation_id
        || hex64(document, "interaction_id")? != pending.interaction_id
        || count(document, "revision")? != pending.revision
    {
        return Err(Failure::frame());
    }
    Ok(intents)
}

/// Requires the success that consumed exactly this answer.
fn response_accepted(
    document: &Map<String, Value>,
    pending: &Review,
    decision: &str,
) -> Outcome<()> {
    let keys = [
        "outcome",
        "response_control_version",
        "operation_id",
        "interaction_id",
        "revision",
        "response_action",
    ];
    if !closed(document, &keys, &keys[2..])
        || !succeeded(document)
        || !version_one(document, "response_control_version")
        || hex64(document, "operation_id")? != pending.operation_id
        || hex64(document, "interaction_id")? != pending.interaction_id
        || count(document, "revision")? != pending.revision
        || one_of(document, "response_action", &["apply", "reject"])? != decision
    {
        return Err(Failure::frame());
    }
    Ok(())
}

fn cancel(
    held: &Held,
    operation_id: &str,
    expected_revision: u64,
    deadline: Instant,
) -> Outcome<Map<String, Value>> {
    let wire_id = request_hex64(operation_id).ok_or_else(Failure::frame)?;
    let reply = held.exchange(
        "operation_manage",
        json!({"management": {
            "cancellation_version": 1,
            "operation_id": wire_id,
            "expected_revision": expected_revision,
        }}),
        deadline,
    )?;
    let document = managed(&reply, operation_id)?;
    if text(document, "outcome") == Some("refused") {
        let code = refusal_code(document, "cancellation_version", &CANCELLATION_REFUSALS)?;
        return Err(Failure::code(&code));
    }
    let keys = [
        "outcome",
        "cancellation_version",
        "operation_id",
        "revision",
        "cancellation_requested",
        "cancellation_acknowledged",
    ];
    let requested = document
        .get("cancellation_requested")
        .is_none_or(|requested| requested.as_bool() == Some(true));
    if !closed(
        document,
        &keys,
        &["operation_id", "revision", "cancellation_acknowledged"],
    ) || !succeeded(document)
        || !version_one(document, "cancellation_version")
        || !requested
    {
        return Err(Failure::frame());
    }
    hex64(document, "operation_id")?;
    count(document, "revision")?;
    flag(document, "cancellation_acknowledged")?;
    Ok(members(json!({
        "kind": "operation_cancel_requested",
        "operation_id": operation_id,
    })))
}

fn result_request(projection: &Projection, schema: &Value) -> Value {
    json!({
        "result_projection_version": 1,
        "operation_id": projection.operation_id,
        "terminal_revision": projection.revision,
        "definition_contract_digest": projection.contract.digest,
        "result_schema": schema,
    })
}

/// One page of a settled document: its range, the whole document's size and
/// digest, and its bytes.
struct Page {
    offset: usize,
    total: usize,
    digest: String,
    bytes: Zeroizing<Vec<u8>>,
}

fn page(value: Option<&Value>) -> Outcome<Page> {
    let keys = ["offset", "total_bytes", "document_digest", "encoded"];
    let document = value
        .and_then(Value::as_object)
        .filter(|page| closed(page, &keys, &keys))
        .ok_or_else(Failure::frame)?;
    let offset = usize::try_from(count(document, "offset")?).map_err(|_| Failure::frame())?;
    let total = usize::try_from(count(document, "total_bytes")?).map_err(|_| Failure::frame())?;
    let encoded = text(document, "encoded").ok_or_else(Failure::frame)?;
    if offset >= PROJECTION_DOCUMENT_MAX_BYTES
        || !(2..=PROJECTION_DOCUMENT_MAX_BYTES).contains(&total)
        || !(4..=PROJECTION_PAGE_MAX_ENCODED).contains(&encoded.chars().count())
    {
        return Err(Failure::frame());
    }
    let digest = hex64(document, "document_digest")?.to_owned();
    let bytes = Zeroizing::new(base64_decode(encoded).ok_or_else(Failure::frame)?);
    if offset >= total || bytes.len() != PROJECTION_PAGE_BYTES.min(total - offset) {
        return Err(Failure::frame());
    }
    Ok(Page {
        offset,
        total,
        digest,
        bytes,
    })
}

/// Collects one settled result document page by page, each page released
/// under current authority and pinned to the first page's digest.
fn read_result_document(
    held: &Held,
    result: &Value,
    deadline: Instant,
) -> Outcome<Map<String, Value>> {
    let operation_id = result
        .get("operation_id")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let mut collected = Zeroizing::new(Vec::new());
    let mut digest: Option<String> = None;
    let mut total: Option<usize> = None;
    while total.is_none_or(|total| collected.len() < total) {
        remaining(deadline)?;
        let offset = collected.len();
        let reply = held.exchange(
            "operation_result_page",
            json!({
                "result": result,
                "page": {"offset": offset, "expected_digest": digest},
            }),
            deadline,
        )?;
        envelope(&reply, "operation_page", &["operation_id", "page"])?;
        let page = page(reply.get("page"))?;
        if hex64(&reply, "operation_id")? != operation_id
            || page.offset != offset
            || digest.as_ref().is_some_and(|digest| *digest != page.digest)
        {
            return Err(Failure::frame());
        }
        remaining(deadline)?;
        if total.is_some_and(|total| total != page.total) {
            return Err(Failure::frame());
        }
        digest = Some(page.digest);
        total = Some(page.total);
        collected.extend_from_slice(&page.bytes);
    }
    if Some(collected.len()) != total
        || Some(Sha256Digest::of(&collected[..]).to_string()) != digest
    {
        return Err(Failure::frame());
    }
    let document = match serde_json::from_slice::<Value>(&collected) {
        Ok(Value::Object(document)) => document,
        _ => return Err(Failure::frame()),
    };
    // Re-encoding refuses what canonical bytes cannot spell, a repeated member included.
    if canonical_json(&Value::Object(document.clone())).as_bytes() != collected.as_slice() {
        return Err(Failure::frame());
    }
    remaining(deadline)?;
    Ok(document)
}

/// The members of a settled result's success envelope: its schema, its
/// contract digest and its projection.
fn result_success(document: &Map<String, Value>) -> Outcome<(&Value, &str, &Value)> {
    let keys = [
        "outcome",
        "result_projection_version",
        "result_schema",
        "definition_contract_digest",
        "projection",
    ];
    if !closed(document, &keys, &keys[2..])
        || !succeeded(document)
        || !version_one(document, "result_projection_version")
    {
        return Err(Failure::frame());
    }
    let schema = document
        .get("result_schema")
        .filter(|schema| schema_identity(schema))
        .ok_or_else(Failure::frame)?;
    let digest = hex64(document, "definition_contract_digest")?;
    Ok((schema, digest, &document["projection"]))
}

/// Whether `pushed` is a reason to observe the held session's operation again.
fn cues(pushed: &Pushed, session_id: &str) -> bool {
    match pushed.event {
        Event::OperationChanged => pushed.session_id.as_deref() == Some(session_id),
        Event::Disconnected => true,
        _ => false,
    }
}

/// Waits for the held session's next operation cue or the deadline, whichever comes first.
fn wait_for_cue(
    cues_from: &mpsc::Receiver<Pushed>,
    session_id: &str,
    deadline: Instant,
) -> Outcome<()> {
    loop {
        let left = deadline.saturating_duration_since(Instant::now());
        if left.is_zero() {
            return Ok(());
        }
        match cues_from.recv_timeout(left) {
            Ok(pushed) if cues(&pushed, session_id) => return Ok(()),
            Ok(_) => {}
            Err(mpsc::RecvTimeoutError::Timeout) => return Ok(()),
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return Err(Failure::Runtime(Refusal::ConnectionClosed));
            }
        }
    }
}

/// Observes a started operation until it is terminal, observing again on each
/// cue. Nothing is subscribed until the first observation finds it unsettled;
/// the observation after subscribing runs at once, so nothing between the two
/// is missed, and earlier cues are forgotten before each later observation.
fn await_terminal(
    held: &Held,
    operation_id: &str,
    page_limit: u64,
    deadline: Instant,
    check: impl Fn(&Projection) -> Outcome<()>,
) -> Outcome<Projection> {
    let mut armed: Option<mpsc::Receiver<Pushed>> = None;
    loop {
        remaining(deadline)?;
        if let Some(receiver) = &armed {
            while receiver.try_recv().is_ok() {}
        }
        let projection = match observe_once(held, operation_id, 0, page_limit, deadline)? {
            Observed::Success(observation) => observation.projection,
            Observed::Refused(code) => return Err(Failure::code(&code)),
        };
        check(&projection)?;
        if projection.terminal {
            return Ok(projection);
        }
        if let Some(receiver) = &armed {
            wait_for_cue(receiver, &held.session.session_id, deadline)?;
        } else {
            armed = Some(held.connection.subscribe_scoped());
        }
    }
}

/// Requires a successful settlement; any other names its refusal, failure or condition.
fn settled(projection: &Projection) -> Outcome<()> {
    match projection.terminal_condition.as_deref() {
        Some("succeeded") => Ok(()),
        Some(condition) => {
            let code = projection
                .refusal_ref
                .as_deref()
                .filter(|code| !code.is_empty())
                .or(projection
                    .failure_error_code
                    .as_deref()
                    .filter(|code| !code.is_empty()))
                .unwrap_or(condition);
            Err(Failure::code(code))
        }
        None => Err(Failure::frame()),
    }
}

/// Discovers a definition's current contract and checks its request schema's fingerprint.
fn describe(held: &Held, definition: &str, deadline: Instant) -> Outcome<Contract> {
    let reply = held.exchange(
        "operation_contract",
        json!({"definition_id": definition}),
        deadline,
    )?;
    envelope(
        &reply,
        "operation_contract",
        &["contract", "request_json_schema"],
    )?;
    let contract = contract(&reply["contract"])?;
    let schema = reply
        .get("request_json_schema")
        .filter(|schema| schema.is_object())
        .ok_or_else(Failure::frame)?;
    if contract.definition_id != definition
        || contract
            .request_schema
            .get("schema_fingerprint")
            .and_then(Value::as_str)
            != Some(content_hash(schema).as_str())
    {
        return Err(Failure::frame());
    }
    Ok(contract)
}

/// The facts one profile view page pins: every page of a read must agree.
#[derive(Clone, Debug, PartialEq, Eq)]
struct Pin {
    record_revision: u64,
    content_digest: String,
    setup_state: String,
    schema_version: u64,
    valid: bool,
}

/// One page of the profile's preferences.
struct ViewPage {
    profile_id: String,
    page_kind: String,
    refusal_code: Option<String>,
    pin: Pin,
    cursor: u64,
    next_cursor: Option<u64>,
    /// Each fact's path and value.
    facts: Vec<(String, String)>,
}

fn view_page(value: &Value) -> Outcome<ViewPage> {
    let document = value
        .as_object()
        .filter(|page| closed(page, &PROFILE_VIEW_PAGE_KEYS, &PROFILE_VIEW_PAGE_REQUIRED))
        .ok_or_else(Failure::frame)?;
    let refusal_code = match document.get("refusal_code") {
        None | Some(Value::Null) => None,
        Some(_) => Some(one_of(document, "refusal_code", &PROFILE_VIEW_REFUSALS)?.to_owned()),
    };
    let next_cursor = match document.get("next_cursor") {
        None | Some(Value::Null) => None,
        Some(_) => Some(count(document, "next_cursor")?),
    };
    let facts = match document.get("items") {
        None => Vec::new(),
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                let item = item.as_object()?;
                let keys = ["kind", "path", "value"];
                (closed(item, &keys, &keys) && text(item, "kind") == Some("fact")).then_some(())?;
                Some((
                    text(item, "path")?.to_owned(),
                    text(item, "value")?.to_owned(),
                ))
            })
            .collect::<Option<Vec<_>>>()
            .ok_or_else(Failure::frame)?,
        Some(_) => return Err(Failure::frame()),
    };
    let page = ViewPage {
        profile_id: text(document, "profile_id")
            .filter(|id| uuid_key(id).is_some())
            .ok_or_else(Failure::frame)?
            .to_owned(),
        page_kind: one_of(document, "page_kind", &PROFILE_VIEW_PAGE_KINDS)?.to_owned(),
        refusal_code,
        pin: Pin {
            record_revision: count(document, "record_revision")?,
            content_digest: hex64(document, "content_digest")?.to_owned(),
            setup_state: one_of(document, "setup_state", &PROFILE_SETUP_STATES)?.to_owned(),
            schema_version: count(document, "schema_version")?,
            valid: flag(document, "valid")?,
        },
        cursor: count(document, "cursor")?,
        next_cursor,
        facts,
    };
    let total = count(document, "total_items")?;
    let listed = page.facts.len() as u64;
    let shaped = page.pin.record_revision >= 1
        && page.pin.schema_version >= 1
        && match one_of(document, "outcome", &["page", "refused"])? {
            "refused" => page.refusal_code.is_some() && listed == 0 && page.next_cursor.is_none(),
            _ => {
                let next = page.cursor + listed;
                page.refusal_code.is_none()
                    && next <= total
                    && (page.cursor >= total || listed > 0)
                    && page.next_cursor == (next < total).then_some(next)
                    // Only preferences carry facts alone, and they disclose only the language.
                    && page.page_kind == "preferences"
                    && total <= 1
                    && page.facts.iter().all(|(path, _)| path == OUTPUT_LANGUAGE_PATH)
            }
        };
    if !shaped {
        return Err(Failure::frame());
    }
    Ok(page)
}

/// The view request, spelled as the product's request model serializes it.
fn view_request(profile_id: &str, cursor: u64, pin: Option<&Pin>) -> String {
    let (revision, digest) = match pin {
        Some(pin) => (
            pin.record_revision.to_string(),
            json_string(&pin.content_digest),
        ),
        None => ("null".to_owned(), "null".to_owned()),
    };
    format!(
        "{{\"profile_id\":{},\"page_kind\":\"preferences\",\"cursor\":{cursor},\"limit\":{PROFILE_VIEW_MAX_ITEMS},\"expected_revision\":{revision},\"expected_content_digest\":{digest},\"output_language\":\"es\"}}",
        json_string(profile_id)
    )
}

/// Pins the first page, or refuses a page from another revision.
fn next_pin(pin: Option<Pin>, page: &Pin) -> Outcome<Pin> {
    match pin {
        None => Ok(page.clone()),
        Some(pin) if pin == *page => Ok(pin),
        Some(_) => Err(Failure::code("stale_revision")),
    }
}

/// Reads one preferences page as its own registered view operation.
fn read_view_page(
    held: &Held,
    contract: &Contract,
    payload: &str,
    cursor: u64,
    deadline: Instant,
) -> Outcome<ViewPage> {
    let subject = held.subject();
    let (operation_id, secret_free) = submit(held, PROFILE_VIEW, &subject, payload, deadline)?;
    if !secret_free {
        return Err(Failure::frame());
    }
    start(held, &operation_id, deadline)?;
    let projection = await_terminal(
        held,
        &operation_id,
        PROFILE_VIEW_EVENT_PAGE,
        deadline,
        |state| {
            if state.operation_id != operation_id
                || state.definition_id != PROFILE_VIEW
                || state.subject_ref != subject
            {
                return Err(Failure::frame());
            }
            Ok(())
        },
    )?;
    settled(&projection)?;
    let schema = contract
        .result_schema
        .clone()
        .filter(|_| contract.definition_id == PROFILE_VIEW)
        .ok_or_else(Failure::frame)?;
    let reply = held.exchange(
        "operation_result",
        json!({"result": {
            "result_projection_version": 1,
            "operation_id": operation_id,
            "terminal_revision": projection.revision,
            "definition_contract_digest": contract.digest,
            "result_schema": schema,
        }}),
        deadline,
    )?;
    let projected = projected(&reply)?;
    // The product client checks a refused envelope with a strict Python-mode
    // model whose enum code a plain string never satisfies, so it surfaces as
    // a malformed reply rather than as its code.
    if projected.operation_id != operation_id
        || projected.projection_kind != "result"
        || text(&projected.document, "outcome") == Some("refused")
    {
        return Err(Failure::frame());
    }
    let (result_schema, digest, projection) = result_success(&projected.document)?;
    let page = view_page(projection)?;
    if *result_schema != schema || digest != contract.digest {
        return Err(Failure::frame());
    }
    if !same_uuid(&page.profile_id, &held.session.profile_id)
        || page.page_kind != "preferences"
        || page.cursor != cursor
    {
        return Err(Failure::frame());
    }
    if let Some(code) = &page.refusal_code {
        return Err(Failure::code(code));
    }
    Ok(page)
}

fn set_language(held: &Held, language: &str, deadline: Instant) -> Outcome<ProfileLanguage> {
    let current = read_language(held, deadline)?;
    mutate_language(held, &current, language, deadline)?;
    read_language(held, deadline)
}

fn read_language(held: &Held, deadline: Instant) -> Outcome<ProfileLanguage> {
    let deadline = deadline.min(Instant::now() + PROFILE_BUDGET);
    let contract = describe(held, PROFILE_VIEW, deadline)?;
    let mut pin: Option<Pin> = None;
    let mut pages = 0;
    let mut cursor = 0;
    let mut saved: Option<String> = None;
    loop {
        remaining(deadline)?;
        if pages >= PROFILE_VIEW_MAX_PAGES {
            return Err(Failure::Runtime(Refusal::DeadlineExceeded));
        }
        let payload = view_request(&held.session.profile_id, cursor, pin.as_ref());
        let page = read_view_page(held, &contract, &payload, cursor, deadline)?;
        pin = Some(next_pin(pin, &page.pin)?);
        pages += 1;
        if saved.is_none() {
            saved = page
                .facts
                .iter()
                .find(|(path, _)| path == OUTPUT_LANGUAGE_PATH)
                .map(|(_, value)| value.clone());
        }
        match page.next_cursor {
            None => break,
            Some(next) if next <= cursor => return Err(Failure::frame()),
            Some(next) => cursor = next,
        }
    }
    let pin = pin.ok_or_else(Failure::frame)?;
    if saved
        .as_deref()
        .is_some_and(|language| !OUTPUT_LANGUAGES.contains(&language))
    {
        return Err(Failure::Invalid);
    }
    Ok(ProfileLanguage {
        language: saved,
        record_revision: pin.record_revision,
        content_digest: pin.content_digest,
    })
}

/// Writes the language through the field mutation guarded by `current`'s revision.
fn mutate_language(
    held: &Held,
    current: &ProfileLanguage,
    language: &str,
    deadline: Instant,
) -> Outcome<()> {
    let deadline = deadline.min(Instant::now() + PROFILE_BUDGET);
    let contract = describe(held, PROFILE_FIELD_MUTATION, deadline)?;
    let schema = contract
        .result_schema
        .clone()
        .filter(|schema| {
            schema.get("schema_id").and_then(Value::as_str) == Some(PROFILE_FIELD_MUTATION_RESULT)
        })
        .ok_or_else(Failure::frame)?;
    let subject = held.subject();
    let payload = format!(
        "{{\"profile_id\":{},\"expected_revision\":{},\"expected_content_digest\":{},\"path\":{},\"value\":{}}}",
        json_string(&held.session.profile_id),
        current.record_revision,
        json_string(&current.content_digest),
        json_string(OUTPUT_LANGUAGE_PATH),
        json_string(language),
    );
    let (operation_id, secret_free) =
        submit(held, &contract.definition_id, &subject, &payload, deadline)?;
    if !secret_free {
        return Err(Failure::frame());
    }
    start(held, &operation_id, deadline)?;
    let projection = await_terminal(
        held,
        &operation_id,
        PROFILE_MUTATION_EVENT_PAGE,
        deadline,
        |state| {
            if state.operation_id != operation_id
                || state.definition_id != contract.definition_id
                || state.subject_ref != subject
                || state.contract.normalized != contract.normalized
            {
                return Err(Failure::frame());
            }
            Ok(())
        },
    )?;
    settled(&projection)?;
    let document = read_result_document(held, &result_request(&projection, &schema), deadline)?;
    if text(&document, "outcome") == Some("refused") {
        let code = refusal_code(&document, "result_projection_version", &RESULT_REFUSALS)?;
        return Err(Failure::code(&code));
    }
    let (result_schema, digest, projection) = result_success(&document)?;
    // Only the field mutation's own projection has exactly these members.
    let keys = ["profile_id", "record_revision"];
    let accepted = projection
        .as_object()
        .filter(|projection| closed(projection, &keys, &keys))
        .ok_or_else(Failure::frame)?;
    let revision = count(accepted, "record_revision")?;
    let profile_id = text(accepted, "profile_id").ok_or_else(Failure::frame)?;
    if *result_schema != schema
        || digest != contract.digest
        || !same_uuid(profile_id, &held.session.profile_id)
        || revision < 1
        || revision < current.record_revision
    {
        return Err(Failure::frame());
    }
    Ok(())
}

fn content_hash(value: &Value) -> String {
    Sha256Digest::of(canonical_json(value).as_bytes()).to_string()
}

/// The product's canonical JSON: sorted keys, compact separators, unescaped
/// UTF-8, numbers as Python spells them.
/// Overwrites every text of `value` in place, then leaves it null.
/// Sends `request` through `send` and then overwrites every text it held,
/// whether or not it was sent.
fn sent_then_wiped<R>(request: &mut Value, send: impl FnOnce(&Value) -> R) -> R {
    let reply = send(request);
    wipe(request);
    reply
}

fn wipe(value: &mut Value) {
    match value {
        Value::String(text) => text.zeroize(),
        Value::Array(items) => items.iter_mut().for_each(wipe),
        Value::Object(members) => members.values_mut().for_each(wipe),
        _ => {}
    }
    *value = Value::Null;
}

fn canonical_json(value: &Value) -> String {
    let mut out = String::new();
    write_json(value, true, &mut out);
    out
}

/// Compact JSON in the document's own member order, as Python's
/// `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` writes it.
fn compact_json(value: &Value) -> String {
    let mut out = String::new();
    write_json(value, false, &mut out);
    out
}

fn json_string(value: &str) -> String {
    let mut out = String::new();
    write_string(value, &mut out);
    out
}

fn write_json(value: &Value, sorted: bool, out: &mut String) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(flag) => out.push_str(if *flag { "true" } else { "false" }),
        Value::Number(number) => {
            if let Some(integer) = number.as_i64() {
                out.push_str(&integer.to_string());
            } else if let Some(integer) = number.as_u64() {
                out.push_str(&integer.to_string());
            } else {
                write_float(number.as_f64().unwrap_or_default(), out);
            }
        }
        Value::String(text) => write_string(text, out),
        Value::Array(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_json(item, sorted, out);
            }
            out.push(']');
        }
        Value::Object(members) => {
            let ordered: Vec<(&String, &Value)> = if sorted {
                members
                    .iter()
                    .collect::<BTreeMap<_, _>>()
                    .into_iter()
                    .collect()
            } else {
                members.iter().collect()
            };
            out.push('{');
            for (index, (key, item)) in ordered.into_iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_string(key, out);
                out.push(':');
                write_json(item, sorted, out);
            }
            out.push('}');
        }
    }
}

/// Escapes as Python's encoder does without ASCII escaping: quotes,
/// backslashes and control characters only.
fn write_string(text: &str, out: &mut String) {
    out.push('"');
    for character in text.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            control if u32::from(control) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", u32::from(control)));
            }
            other => out.push(other),
        }
    }
    out.push('"');
}

/// A finite float as Python's `repr`: the shortest digits that round-trip,
/// positional from 1e-4 up to below 1e16, else `d.ddde±XX`.
fn write_float(value: f64, out: &mut String) {
    if value == 0.0 {
        out.push_str(if value.is_sign_negative() {
            "-0.0"
        } else {
            "0.0"
        });
        return;
    }
    if value.is_sign_negative() {
        out.push('-');
    }
    let scientific = format!("{:e}", value.abs());
    let (mantissa, exponent) = scientific.split_once('e').unwrap_or((&scientific, "0"));
    let digits: String = mantissa.chars().filter(|digit| *digit != '.').collect();
    let exponent: i32 = exponent.parse().unwrap_or_default();
    let point = exponent + 1;
    let count = digits.len() as i32;
    if !(-3..=16).contains(&point) {
        out.push_str(&digits[..1]);
        if digits.len() > 1 {
            out.push('.');
            out.push_str(&digits[1..]);
        }
        out.push_str(&format!(
            "e{}{:02}",
            if exponent < 0 { '-' } else { '+' },
            exponent.abs()
        ));
    } else if point <= 0 {
        out.push_str("0.");
        out.push_str(&"0".repeat((-point) as usize));
        out.push_str(&digits);
    } else if point >= count {
        out.push_str(&digits);
        out.push_str(&"0".repeat((point - count) as usize));
        out.push_str(".0");
    } else {
        out.push_str(&digits[..point as usize]);
        out.push('.');
        out.push_str(&digits[point as usize..]);
    }
}

/// A UTC instant as Python's `datetime.isoformat` spells it once parsed:
/// `YYYY-MM-DDTHH:MM:SS[.ffffff]+00:00`. Only a zero offset is accepted.
fn utc_isoformat(value: &str) -> Option<String> {
    let bytes = value.as_bytes();
    if bytes.len() < 20 || !value.is_ascii() {
        return None;
    }
    let number = |range: std::ops::Range<usize>| -> Option<u32> {
        let part = &value[range];
        part.bytes()
            .all(|byte| byte.is_ascii_digit())
            .then(|| part.parse().ok())
            .flatten()
    };
    let year = number(0..4)?;
    let month = number(5..7)?;
    let day = number(8..10)?;
    let hour = number(11..13)?;
    let minute = number(14..16)?;
    let second = number(17..19)?;
    let separated = bytes[4] == b'-'
        && bytes[7] == b'-'
        && matches!(bytes[10], b'T' | b't' | b' ' | b'_')
        && bytes[13] == b':'
        && bytes[16] == b':';
    let leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    let days = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap => 29,
        2 => 28,
        _ => return None,
    };
    if !separated
        || year == 0
        || !(1..=days).contains(&day)
        || hour > 23
        || minute > 59
        || second > 59
    {
        return None;
    }
    let mut rest = &value[19..];
    let mut micros = 0u32;
    if let Some(fraction) = rest.strip_prefix('.') {
        let digits = fraction.bytes().take_while(u8::is_ascii_digit).count();
        if !(1..=6).contains(&digits) {
            return None;
        }
        let padded = format!("{:0<6}", &fraction[..digits]);
        micros = padded.parse().ok()?;
        rest = &fraction[digits..];
    }
    if !matches!(rest, "Z" | "z" | "+00:00" | "-00:00") {
        return None;
    }
    Some(isoformat(year, month, day, hour, minute, second, micros))
}

fn isoformat(
    year: u32,
    month: u32,
    day: u32,
    hour: u32,
    minute: u32,
    second: u32,
    micros: u32,
) -> String {
    let fraction = if micros == 0 {
        String::new()
    } else {
        format!(".{micros:06}")
    };
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}{fraction}+00:00")
}

/// `seconds` and `micros` after the Unix epoch as the product's models spell
/// a UTC instant on the wire: `YYYY-MM-DDTHH:MM:SS[.ffffff]Z`.
fn utc_text(seconds: u64, micros: u32) -> String {
    let days = (seconds / 86_400) as i64;
    let of_day = seconds % 86_400;
    // Days to a civil date in the proleptic Gregorian calendar.
    let shifted = days + 719_468;
    let era = shifted.div_euclid(146_097);
    let of_era = shifted.rem_euclid(146_097);
    let year_of_era = (of_era - of_era / 1_460 + of_era / 36_524 - of_era / 146_096) / 365;
    let of_year = of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let shifted_month = (5 * of_year + 2) / 153;
    let day = of_year - (153 * shifted_month + 2) / 5 + 1;
    let month = if shifted_month < 10 {
        shifted_month + 3
    } else {
        shifted_month - 9
    };
    let year = year_of_era + era * 400 + i64::from(month <= 2);
    let iso = isoformat(
        year as u32,
        month as u32,
        day as u32,
        (of_day / 3_600) as u32,
        (of_day % 3_600 / 60) as u32,
        (of_day % 60) as u32,
        micros,
    );
    format!("{}Z", iso.trim_end_matches("+00:00"))
}

fn utc_now() -> String {
    let elapsed = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    utc_text(elapsed.as_secs(), elapsed.subsec_micros())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::VecDeque, sync::Mutex};

    const PROFILE: &str = "11111111-1111-4111-8111-111111111111";
    const SESSION: &str = "22222222-2222-4222-8222-222222222222";
    const OTHER_SESSION: &str = "44444444-4444-4444-8444-444444444444";
    const HOLDER: &str = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    const REQUEST_SCHEMA_TITLE: &str = "Se\u{f1}al \u{fc}n\u{ef}code";
    const REVIEW_DIGEST: &str = "a9bff82c2191be89222e1d7995701734508d51e93d6f0b46e2c738efb3642b17";

    // Contracts the product's own model validates, with digests its
    // `definition_contract_digest` computed; the request schema fingerprint
    // is the product's hash of `{"type": "object", "title": REQUEST_SCHEMA_TITLE}`.
    const VIEW_CONTRACT: &str = r#"{"manifest_version":4,"definition_id":"user-profile.view","action_reference":null,"request_schema":{"schema_id":"user-profile.view.request","schema_version":1,"schema_fingerprint":"4c56a3cc9df747dc300c9f156578a3c6afb6a7f0be460fa47bba9c40d750e92c"},"subject_reference":{"kind":"profile","payload_path":[],"literal":null},"result_schema":{"schema_id":"user-profile.view.result","schema_version":1,"schema_fingerprint":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"},"refusal_detail_codes":[],"review_projection_schema":null,"interaction_response_schema":null,"workspace_refresh_target_schema":null,"interaction_kinds":[],"request_storage":"secure_reference","durability":"recorded","cancellation":"unsupported","deadline":"absent","replay":"idempotent_submit","baseline":"none","sensitive_input":"secure_reference","conflict_scope":"definition_subject","owned_resources":[],"permitted_effects":["updated","none","unknown"],"close_policy":"detach_allowed","reconciliation_policy":"interrupt","ephemeral_secret_required":false,"transient_financial_operand":null,"definition_contract_digest":"4260786ba079f5729599dbb7e5960f20a9fb66a0bfa47b86477169517bf30c3c"}"#;
    const MUTATION_CONTRACT: &str = r#"{"manifest_version":4,"definition_id":"user-profile.field-mutation","action_reference":null,"request_schema":{"schema_id":"user-profile.field-mutation.request","schema_version":1,"schema_fingerprint":"4c56a3cc9df747dc300c9f156578a3c6afb6a7f0be460fa47bba9c40d750e92c"},"subject_reference":{"kind":"profile","payload_path":[],"literal":null},"result_schema":{"schema_id":"user-profile.field-mutation.result","schema_version":1,"schema_fingerprint":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"},"refusal_detail_codes":[],"review_projection_schema":null,"interaction_response_schema":null,"workspace_refresh_target_schema":null,"interaction_kinds":[],"request_storage":"secure_reference","durability":"recorded","cancellation":"unsupported","deadline":"absent","replay":"idempotent_submit","baseline":"none","sensitive_input":"secure_reference","conflict_scope":"definition_subject","owned_resources":[],"permitted_effects":["updated","none","unknown"],"close_policy":"detach_allowed","reconciliation_policy":"interrupt","ephemeral_secret_required":false,"transient_financial_operand":null,"definition_contract_digest":"67c4c552879ab69e85a55623c318b8669747a96f4cd5a3d630487cae7f04de3e"}"#;
    const RELAY_CONTRACT: &str = r#"{"manifest_version":4,"definition_id":"ledger.example-review","action_reference":null,"request_schema":{"schema_id":"ledger.example-review.request","schema_version":1,"schema_fingerprint":"4c56a3cc9df747dc300c9f156578a3c6afb6a7f0be460fa47bba9c40d750e92c"},"subject_reference":{"kind":"profile","payload_path":[],"literal":null},"result_schema":{"schema_id":"ledger.example-review.result","schema_version":1,"schema_fingerprint":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"},"refusal_detail_codes":["REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE"],"review_projection_schema":{"schema_id":"ledger.example-review.review","schema_version":1,"schema_fingerprint":"1111111111111111111111111111111111111111111111111111111111111111"},"interaction_response_schema":{"schema_id":"ledger.example-review.response","schema_version":1,"schema_fingerprint":"2222222222222222222222222222222222222222222222222222222222222222"},"workspace_refresh_target_schema":null,"interaction_kinds":["review"],"request_storage":"secure_reference","durability":"recorded","cancellation":"unsupported","deadline":"absent","replay":"idempotent_submit","baseline":"none","sensitive_input":"secure_reference","conflict_scope":"definition_subject","owned_resources":[],"permitted_effects":["unknown","none","updated"],"close_policy":"detach_allowed","reconciliation_policy":"interrupt","ephemeral_secret_required":false,"transient_financial_operand":null,"definition_contract_digest":"5163af50d7e36bca8e7e2a49cbd7338b03a5f884f18e70d27001f9cde0a9cc95"}"#;
    /// The product registry's own field-mutation contract, as its registration builds it.
    const REGISTERED_MUTATION_CONTRACT: &str = r#"{"manifest_version":4,"definition_id":"user-profile.field-mutation","action_reference":null,"request_schema":{"schema_id":"user-profile.field-mutation.request","schema_version":1,"schema_fingerprint":"fc15896be53c28497cae684bf61678c983767ff39832647304f259079c9965b5"},"subject_reference":{"kind":"profile","payload_path":[],"literal":null},"result_schema":{"schema_id":"user-profile.field-mutation.result","schema_version":1,"schema_fingerprint":"32ea9b0f6f1c505bd6e3124940b48ec4a4b968dc763e9605f4a506f6d21a068d"},"refusal_detail_codes":[],"review_projection_schema":null,"interaction_response_schema":null,"workspace_refresh_target_schema":null,"interaction_kinds":[],"request_storage":"secure_reference","durability":"recorded","cancellation":"unsupported","deadline":"absent","replay":"idempotent_submit","baseline":"none","sensitive_input":"secure_reference","conflict_scope":"definition_subject","owned_resources":[],"permitted_effects":["updated","none","unknown"],"close_policy":"detach_allowed","reconciliation_policy":"interrupt","ephemeral_secret_required":false,"transient_financial_operand":null,"definition_contract_digest":"425fb344c164da0a42366138239a0a226536013a7549025e409aee7c0cb4dbf5"}"#;

    fn view() -> Value {
        serde_json::from_str(VIEW_CONTRACT).unwrap()
    }

    fn mutation() -> Value {
        serde_json::from_str(MUTATION_CONTRACT).unwrap()
    }

    fn relay_contract() -> Value {
        serde_json::from_str(RELAY_CONTRACT).unwrap()
    }

    fn operation() -> String {
        "a".repeat(64)
    }

    fn mutation_operation() -> String {
        "b".repeat(64)
    }

    fn interaction() -> String {
        "d".repeat(64)
    }

    fn session() -> Admitted {
        Admitted {
            profile_id: PROFILE.to_owned(),
            session_id: SESSION.to_owned(),
            connection_id: "33333333-3333-4333-8333-333333333333".to_owned(),
            runtime_boot_id: "55555555-5555-4555-8555-555555555555".to_owned(),
            expires_at: None,
            session_persisted: None,
            signed_out_profile_ids: Vec::new(),
        }
    }

    type Step = (Result<Value, Refusal>, Option<Pushed>);

    /// A runtime that answers from a script, records what it was sent, and
    /// pushes a scripted cue while an exchange is in flight.
    struct Fake {
        steps: Mutex<VecDeque<Step>>,
        sent: Mutex<Vec<Value>>,
        subscribers: Mutex<Vec<mpsc::Sender<Pushed>>>,
    }

    impl Fake {
        fn new(steps: Vec<Step>) -> Self {
            Self {
                steps: Mutex::new(steps.into()),
                sent: Mutex::new(Vec::new()),
                subscribers: Mutex::new(Vec::new()),
            }
        }

        /// What was sent, each request without its request id, which must be a fresh UUID.
        fn sent(&self) -> Vec<Value> {
            let sent = self.sent.lock().unwrap();
            let mut ids = BTreeSet::new();
            sent.iter()
                .map(|request| {
                    let mut request = request.as_object().unwrap().clone();
                    let id = request.remove("request_id").unwrap();
                    let id = id.as_str().unwrap();
                    assert!(uuid_key(id).is_some() && id.len() == 36, "{id}");
                    assert!(ids.insert(id.to_owned()), "a repeated request id");
                    Value::Object(request)
                })
                .collect()
        }

        fn finished(&self) -> bool {
            self.steps.lock().unwrap().is_empty()
        }
    }

    impl SessionExchange for Fake {
        fn close(&self) {}

        fn exchange(
            &self,
            request: &Value,
            _deadline: Instant,
        ) -> Result<Map<String, Value>, Refusal> {
            self.sent.lock().unwrap().push(request.clone());
            let Some((reply, pushed)) = self.steps.lock().unwrap().pop_front() else {
                return Err(Refusal::ConnectionClosed);
            };
            if let Some(pushed) = pushed {
                for subscriber in self.subscribers.lock().unwrap().iter() {
                    let _ = subscriber.send(pushed.clone());
                }
            }
            reply.map(members)
        }

        fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
            let (sender, receiver) = mpsc::channel();
            self.subscribers.lock().unwrap().push(sender);
            receiver
        }
    }

    fn reply(value: Value) -> Step {
        (Ok(value), None)
    }

    fn reply_with_cue(value: Value, session_id: &str) -> Step {
        let cue = Pushed {
            event: Event::OperationChanged,
            profile_id: Some(PROFILE.to_owned()),
            session_id: Some(session_id.to_owned()),
        };
        (Ok(value), Some(cue))
    }

    fn refuse(refusal: Refusal) -> Step {
        (Err(refusal), None)
    }

    fn target(fields: Value) -> Value {
        let mut request = members(json!({"profile_id": PROFILE, "session_id": SESSION}));
        request.extend(members(fields));
        Value::Object(request)
    }

    /// An observation shaped as the product's observation model dumps one.
    fn observation(
        id: &str,
        contract: &Value,
        lifecycle: &str,
        condition: Option<&str>,
        references: (Option<&str>, Option<&str>),
        pending: Value,
    ) -> Value {
        json!({
            "outcome": "success",
            "observation_version": 1,
            "projection": {
                "observation_version": 1,
                "operation_id": id,
                "definition_id": contract["definition_id"],
                "subject_ref": format!("profile:{PROFILE}"),
                "revision": 3,
                "anchor_cursor": 0,
                "definition_contract": contract,
                "contract_set_digest": "9".repeat(64),
                "lifecycle": lifecycle,
                "terminal_condition": condition,
                "effect": "none",
                "phase_code": null,
                "started_at": "2026-10-24T10:00:00Z",
                "updated_at": "2026-10-24T10:00:01.250000Z",
                "progress": null,
                "close_policy": contract["close_policy"],
                "cancellation": contract["cancellation"],
                "cancellable_now": false,
                "financial_operand_pending": false,
                "financial_operand_cancelled_before_delivery": false,
                "cancellation_requested": false,
                "cancellation_acknowledged": false,
                "execution_deadline_at": null,
                "cleanup_deadline_at": null,
                "pending_interaction": pending,
                "result_ref": references.0,
                "refusal_ref": references.1,
                "failure_error_code": null,
                "diagnostic_ref": null,
            },
            "event_page": {
                "observation_version": 1,
                "operation_id": id,
                "anchor_cursor": 0,
                "requested_cursor": 0,
                "status": "caught_up",
                "events": [],
                "next_cursor": 0,
                "restart_cursor": null,
            },
        })
    }

    fn running(id: &str, contract: &Value) -> Value {
        observation(
            id,
            contract,
            "running",
            None,
            (None, None),
            json!({"disposition": "none"}),
        )
    }

    fn succeeded(id: &str, contract: &Value) -> Value {
        observation(
            id,
            contract,
            "terminal",
            Some("succeeded"),
            (Some("result:1"), None),
            json!({"disposition": "none"}),
        )
    }

    fn review_reference() -> Value {
        let contract = relay_contract();
        json!({
            "operation_id": operation(),
            "interaction_id": interaction(),
            "revision": 3,
            "review_projection_schema": contract["review_projection_schema"],
            "definition_contract_digest": contract["definition_contract_digest"],
            "expires_at": "2026-10-24T10:05:00.123000Z",
        })
    }

    fn awaiting_review() -> Value {
        let contract = relay_contract();
        observation(
            &operation(),
            &contract,
            "waiting_for_interaction",
            None,
            (None, None),
            json!({
                "disposition": "review_available",
                "operation_id": operation(),
                "interaction_id": interaction(),
                "revision": 3,
                "presentation_code": "ledger.example.review",
                "response_schema": contract["interaction_response_schema"],
                "expires_at": "2026-10-24T10:05:00.123000Z",
                "review_reference": review_reference(),
            }),
        )
    }

    fn observed(observation: Value) -> Value {
        json!({"kind": "operation_observed", "observation": observation})
    }

    fn submitted(id: &str) -> Value {
        json!({
            "kind": "operation_submitted",
            "receipt": {"submission_version": 1, "operation_id": id, "secret_requirement": null},
        })
    }

    fn acknowledged(id: &str) -> Value {
        json!({"kind": "operation_acknowledged", "operation_id": id})
    }

    fn projected_reply(id: &str, kind: &str, document: Value) -> Value {
        json!({"kind": "operation_projected", "operation_id": id, "projection_kind": kind, "document": document})
    }

    fn managed_reply(id: &str, document: Value) -> Value {
        json!({"kind": "operation_managed", "operation_id": id, "document": document})
    }

    fn contract_reply(contract: Value) -> Value {
        json!({
            "kind": "operation_contract",
            "contract": contract,
            "request_json_schema": {"type": "object", "title": REQUEST_SCHEMA_TITLE},
        })
    }

    fn base64(bytes: &[u8]) -> String {
        const ALPHABET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        let mut encoded = String::new();
        for group in bytes.chunks(3) {
            let bits = group.iter().enumerate().fold(0u32, |bits, (index, byte)| {
                bits | u32::from(*byte) << (16 - 8 * index)
            });
            for index in 0..4 {
                if index <= group.len() {
                    encoded.push(ALPHABET[(bits >> (18 - 6 * index) & 63) as usize] as char);
                } else {
                    encoded.push('=');
                }
            }
        }
        encoded
    }

    /// The pages a runtime releases for `bytes`, 32 KiB each.
    fn pages(id: &str, bytes: &[u8]) -> Vec<Step> {
        let digest = Sha256Digest::of(bytes).to_string();
        bytes
            .chunks(PROJECTION_PAGE_BYTES)
            .enumerate()
            .map(|(index, chunk)| {
                reply(json!({
                    "kind": "operation_page",
                    "operation_id": id,
                    "page": {
                        "offset": index * PROJECTION_PAGE_BYTES,
                        "total_bytes": bytes.len(),
                        "document_digest": digest,
                        "encoded": base64(chunk),
                    },
                }))
            })
            .collect()
    }

    fn result_envelope(contract: &Value, projection: Value) -> Value {
        json!({
            "outcome": "success",
            "result_projection_version": 1,
            "result_schema": contract["result_schema"],
            "definition_contract_digest": contract["definition_contract_digest"],
            "projection": projection,
        })
    }

    fn preferences(revision: u64, language: Option<&str>) -> Value {
        let items: Vec<Value> = language
            .map(
                |language| json!({"kind": "fact", "path": OUTPUT_LANGUAGE_PATH, "value": language}),
            )
            .into_iter()
            .collect();
        json!({
            "profile_id": PROFILE,
            "page_kind": "preferences",
            "outcome": "page",
            "refusal_code": null,
            "record_revision": revision,
            "content_digest": "f".repeat(64),
            "setup_state": "complete",
            "schema_version": 1,
            "valid": true,
            "cursor": 0,
            "next_cursor": null,
            "total_items": items.len(),
            "items": items,
        })
    }

    /// A complete language read: the view contract, one page operation
    /// settling at once, and its result page.
    fn language_read(id: &str, page: Value) -> Vec<Step> {
        vec![
            reply(contract_reply(view())),
            reply(submitted(id)),
            reply(acknowledged(id)),
            reply(observed(succeeded(id, &view()))),
            reply(projected_reply(
                id,
                "result",
                result_envelope(&view(), page),
            )),
        ]
    }

    fn handle(
        fake: &Fake,
        relay: &mut OperationRelay,
        action: &str,
        request: Value,
    ) -> Result<Map<String, Value>, RelayFailure> {
        relay.handle(fake, &session(), action, &members(request))
    }

    fn refused_with(failure: Result<Map<String, Value>, RelayFailure>, expected: &str) {
        match failure {
            Err(RelayFailure::Refused { code, .. }) => assert_eq!(code, expected),
            other => panic!("expected {expected}, got {other:?}"),
        }
    }

    #[test]
    fn canonical_json_spells_documents_as_the_product_does() {
        let sample = "{\"z\": [1, -2, 3.5, 1e16, 1e-05, 0.0001, 123456789.125, -0.0, 1e300, 0.1, 1e15, 2.5e-07, 100.0], \"\u{e9}\": \"\u{f1}and\u{fa} \\\"quoted\\\" \\\\ \\n\\t\\u0001 \\u007f \u{1f600}\", \"A\": {\"nested\": {\"b\": true, \"a\": null, \"\u{ffff}\": [], \"\u{1f600}\": {}}}, \"\u{3a9}\": 18446744073709551615, \"neg\": -9223372036854775808}";
        let document: Value = serde_json::from_str(sample).unwrap();
        // Both values are the product's `canonical_json_bytes` and `content_hash_hex` of `sample`.
        assert_eq!(
            canonical_json(&document),
            "{\"A\":{\"nested\":{\"a\":null,\"b\":true,\"\u{ffff}\":[],\"\u{1f600}\":{}}},\"neg\":-9223372036854775808,\"z\":[1,-2,3.5,1e+16,1e-05,0.0001,123456789.125,-0.0,1e+300,0.1,1000000000000000.0,2.5e-07,100.0],\"\u{e9}\":\"\u{f1}and\u{fa} \\\"quoted\\\" \\\\ \\n\\t\\u0001 \u{7f} \u{1f600}\",\"\u{3a9}\":18446744073709551615}"
        );
        assert_eq!(
            content_hash(&document),
            "bc0e9f39d31a2c6afb9f8a01a269760cfee8b14bd6cbac133b6b600dc0dc1a4e"
        );
        assert_eq!(
            content_hash(&json!({"type": "object", "title": REQUEST_SCHEMA_TITLE})),
            "4c56a3cc9df747dc300c9f156578a3c6afb6a7f0be460fa47bba9c40d750e92c"
        );
    }

    #[test]
    fn a_contract_must_reproduce_its_own_digest() {
        for text in [
            VIEW_CONTRACT,
            MUTATION_CONTRACT,
            RELAY_CONTRACT,
            REGISTERED_MUTATION_CONTRACT,
        ] {
            let value: Value = serde_json::from_str(text).unwrap();
            assert!(contract(&value).is_ok(), "{text}");
            // A set's order is not part of the contract; its members are.
            let mut reordered = value.clone();
            reordered["permitted_effects"] = json!(["none", "unknown", "updated"]);
            assert!(contract(&reordered).is_ok());
            let mut changed = value.clone();
            changed["permitted_effects"] = json!(["none", "updated"]);
            assert!(contract(&changed).is_err());
            let mut changed = value.clone();
            changed["durability"] = json!("ephemeral");
            assert!(contract(&changed).is_err());
            let mut extra = value.clone();
            extra["unexpected"] = json!(true);
            assert!(contract(&extra).is_err());
            // The members with defaults may be left out.
            let mut defaulted = value.as_object().unwrap().clone();
            defaulted.remove("manifest_version");
            defaulted.remove("transient_financial_operand");
            assert!(contract(&Value::Object(defaulted)).is_ok());
        }
    }

    #[test]
    fn instants_are_spelled_as_python_and_the_wire_spell_them() {
        assert_eq!(
            utc_isoformat("2026-10-24T10:05:00.123Z").as_deref(),
            Some("2026-10-24T10:05:00.123000+00:00")
        );
        assert_eq!(
            utc_isoformat("2026-10-24T10:00:00+00:00").as_deref(),
            Some("2026-10-24T10:00:00+00:00")
        );
        for refused in [
            "2026-10-24T10:00:00+01:00",
            "2026-10-24T10:00:00",
            "2026-02-29T10:00:00Z",
            "2026-10-24T10:00:00.1234567Z",
        ] {
            assert_eq!(utc_isoformat(refused), None, "{refused}");
        }
        // Each is Python's `datetime.fromtimestamp(seconds, UTC)`, spelled as the product's models dump it.
        assert_eq!(utc_text(1_792_836_000, 0), "2026-10-24T10:00:00Z");
        assert_eq!(utc_text(951_782_400, 0), "2000-02-29T00:00:00Z");
        assert_eq!(utc_text(4_102_444_799, 0), "2099-12-31T23:59:59Z");
        assert_eq!(utc_text(0, 123_456), "1970-01-01T00:00:00.123456Z");
    }

    #[test]
    fn a_submitted_operation_is_started_and_watched() {
        let fake = Fake::new(vec![
            reply(submitted(&operation())),
            reply(acknowledged(&operation())),
        ]);
        let mut relay = OperationRelay::new();
        let answered = handle(
            &fake,
            &mut relay,
            "operation_submit",
            json!({
                "request_id": "ignored",
                "action": "operation_submit",
                "definition_id": "ledger.example-review",
                "subject_ref": format!("profile:{PROFILE}"),
                "payload": {"a": "\u{f1}", "b": [1, 2.5]},
            }),
        )
        .unwrap();
        assert_eq!(
            Value::Object(answered),
            json!({"kind": "operation_submitted", "operation_id": operation()})
        );
        assert!(relay.watching());
        assert_eq!(
            fake.sent(),
            vec![
                target(json!({
                    "action": "operation_submit",
                    "definition_id": "ledger.example-review",
                    "idempotency_key": null,
                    "payload_json": "{\"a\":\"\u{f1}\",\"b\":[1,2.5]}",
                    "subject_ref": format!("profile:{PROFILE}"),
                })),
                target(json!({"action": "operation_start", "operation_id": operation()})),
            ]
        );
    }

    #[test]
    fn a_submission_is_refused_before_it_is_sent_when_malformed() {
        let request = |payload: Value, definition_id: Value, subject_ref: Value| json!({"definition_id": definition_id, "subject_ref": subject_ref, "payload": payload});
        let subject = json!(format!("profile:{PROFILE}"));
        let definition = json!("ledger.example-review");
        // 12,289 characters of compact JSON; the bound counts characters, not bytes.
        let long = json!({"a": "\u{f1}".repeat(12_289 - 8)});
        for (payload, definition_id, subject_ref) in [
            (long, definition.clone(), subject.clone()),
            (json!([1]), definition.clone(), subject.clone()),
            (json!({}), json!(""), subject.clone()),
            (json!({}), definition.clone(), json!(7)),
        ] {
            let fake = Fake::new(Vec::new());
            let refused = handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_submit",
                request(payload, definition_id, subject_ref),
            );
            assert!(matches!(refused, Err(RelayFailure::Invalid)), "{refused:?}");
            assert!(fake.sent().is_empty());
        }
        // The request model refuses a definition id the hold's own checks admit.
        let fake = Fake::new(Vec::new());
        refused_with(
            handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_submit",
                request(json!({}), json!("Ledger.Bad"), subject.clone()),
            ),
            "unavailable",
        );
        assert!(fake.sent().is_empty());
        // At the bound exactly, the request is sent.
        let fake = Fake::new(vec![
            reply(submitted(&operation())),
            reply(acknowledged(&operation())),
        ]);
        let at_bound = json!({"a": "\u{f1}".repeat(12_288 - 8)});
        assert!(
            handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_submit",
                request(at_bound, definition, subject)
            )
            .is_ok()
        );
    }

    #[test]
    fn financial_input_travels_once_as_the_runtimes_financial_input() {
        let fake = Fake::new(vec![
            reply(submitted(&operation())),
            reply(acknowledged(&operation())),
        ]);
        let mut relay = OperationRelay::new();
        let answered = handle(
            &fake,
            &mut relay,
            "operation_financial_submit",
            json!({
                "definition_id": "ledger.example-review",
                "subject_ref": format!("profile:{PROFILE}"),
                "input": {"input_version": 2, "amount": "1.234,56"},
            }),
        )
        .unwrap();
        assert_eq!(
            Value::Object(answered),
            json!({"kind": "operation_submitted", "operation_id": operation()})
        );
        assert!(relay.watching());
        // Never as an ordinary submission: the runtime's own financial input, then the start.
        assert_eq!(
            fake.sent(),
            vec![
                target(json!({
                    "action": "operation_financial_input",
                    "definition_id": "ledger.example-review",
                    "idempotency_key": null,
                    "payload_json": "{\"amount\":\"1.234,56\",\"input_version\":2}",
                    "subject_ref": format!("profile:{PROFILE}"),
                })),
                target(json!({"action": "operation_start", "operation_id": operation()})),
            ]
        );
    }

    #[test]
    fn financial_input_for_a_definition_that_takes_none_is_the_runtimes_closed_refusal() {
        // The relay names no definition: the runtime refuses one whose contract takes no operand.
        let fake = Fake::new(vec![refuse(Refusal::denied("operation_denied"))]);
        let mut relay = OperationRelay::new();
        refused_with(
            handle(
                &fake,
                &mut relay,
                "operation_financial_submit",
                json!({
                    "definition_id": "ledger.example-review",
                    "subject_ref": format!("profile:{PROFILE}"),
                    "input": {"a": 1},
                }),
            ),
            "operation_denied",
        );
        assert!(!relay.watching());
        assert_eq!(fake.sent().len(), 1);
    }

    #[test]
    fn financial_input_that_is_not_an_object_never_reaches_the_runtime() {
        for input in [json!([1]), json!("1.234,56"), Value::Null] {
            let fake = Fake::new(Vec::new());
            let refused = handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_financial_submit",
                json!({
                    "definition_id": "ledger.example-review",
                    "subject_ref": format!("profile:{PROFILE}"),
                    "input": input,
                }),
            );
            assert!(matches!(refused, Err(RelayFailure::Invalid)), "{refused:?}");
            assert!(fake.sent().is_empty());
        }
    }

    #[test]
    fn a_request_is_sent_whole_and_then_keeps_no_text() {
        let iban = r#"{"iban":"ES9121000418450200051332"}"#;
        let mut request =
            json!({"action": "operation_submit", "payload_json": iban, "rows": [iban]});
        let sent = sent_then_wiped(&mut request, |request| request.clone());
        assert_eq!(sent["payload_json"], iban);
        // Every text was overwritten in place before the request itself was emptied.
        assert_eq!(request, Value::Null);
    }

    #[test]
    fn a_wiped_request_keeps_no_text() {
        let mut request = json!({"payload_json": "{\"amount\":\"9876.54\"}", "nested": ["x", {"y": "z"}], "n": 1});
        wipe(&mut request);
        assert_eq!(request, Value::Null);
    }

    #[test]
    fn a_submission_answers_the_runtime_refusal_and_an_unacknowledged_start() {
        let request = json!({
            "definition_id": "ledger.example-review",
            "subject_ref": format!("profile:{PROFILE}"),
            "payload": {},
        });
        let busy = Fake::new(vec![refuse(Refusal::Denied {
            code: "subject_busy".into(),
            sign_in: None,
            holder_operation_id: Some(HOLDER.into()),
        })]);
        match handle(
            &busy,
            &mut OperationRelay::new(),
            "operation_submit",
            request.clone(),
        ) {
            Err(RelayFailure::Refused {
                code,
                holder_operation_id,
            }) => {
                assert_eq!(code, "subject_busy");
                assert_eq!(holder_operation_id.as_deref(), Some(HOLDER));
            }
            other => panic!("{other:?}"),
        }
        for failure in [
            Refusal::denied("runtime_draining"),
            Refusal::ConnectionClosed,
            Refusal::DeadlineExceeded,
        ] {
            let fake = Fake::new(vec![refuse(failure)]);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_submit",
                    request.clone(),
                ),
                "unavailable",
            );
        }
        let fake = Fake::new(vec![
            reply(submitted(&operation())),
            reply(acknowledged(&"e".repeat(64))),
        ]);
        let mut relay = OperationRelay::new();
        refused_with(
            handle(&fake, &mut relay, "operation_submit", request),
            "unavailable",
        );
        assert!(!relay.watching());
    }

    #[test]
    fn the_relay_watches_at_most_sixteen_unsettled_operations() {
        let ids: Vec<String> = (0..17).map(|index| format!("{index:064x}")).collect();
        let mut relay = OperationRelay::new();
        for id in &ids {
            let fake = Fake::new(vec![reply(submitted(id)), reply(acknowledged(id))]);
            handle(
                &fake,
                &mut relay,
                "operation_submit",
                json!({"definition_id": "ledger.example-review", "subject_ref": "profile:x", "payload": {}}),
            )
            .unwrap();
        }
        assert_eq!(relay.watched.len(), MAX_WATCHED);
        assert!(!relay.watched.contains(&ids[16]));
        // A settled operation leaves the watch, which makes room for one still running.
        let fake = Fake::new(vec![
            reply(observed(succeeded(&ids[0], &view()))),
            reply(observed(running(&ids[16], &view()))),
        ]);
        handle(
            &fake,
            &mut relay,
            "operation_observe",
            json!({"operation_id": ids[0], "after_cursor": 0}),
        )
        .unwrap();
        assert!(!relay.watched.contains(&ids[0]));
        handle(
            &fake,
            &mut relay,
            "operation_observe",
            json!({"operation_id": ids[16], "after_cursor": 0}),
        )
        .unwrap();
        assert!(relay.watched.contains(&ids[16]));
        assert_eq!(relay.watched.len(), MAX_WATCHED);
    }

    #[test]
    fn an_observation_passes_the_published_document_back() {
        let document = running(&operation(), &view());
        let fake = Fake::new(vec![reply(observed(document.clone()))]);
        let mut relay = OperationRelay::new();
        let answered = handle(
            &fake,
            &mut relay,
            "operation_observe",
            json!({"operation_id": operation(), "after_cursor": 5}),
        )
        .unwrap();
        assert_eq!(
            Value::Object(answered),
            json!({"kind": "operation_observed", "observation": document})
        );
        assert!(relay.watching());
        assert_eq!(
            fake.sent(),
            vec![target(json!({
                "action": "operation_observe",
                "observation": {
                    "after_cursor": 5,
                    "observation_version": 1,
                    "operation_id": operation(),
                    "page_limit": 64,
                },
            }))]
        );
    }

    #[test]
    fn an_observation_refuses_a_refused_or_foreign_projection_and_a_malformed_request() {
        let refused = json!({
            "outcome": "refused",
            "observation_version": 1,
            "code": "unknown_operation",
            "requested_version": null,
            "supported_version": 1,
            "diagnostic_ref": null,
        });
        let mut wrong_anchor = running(&operation(), &view());
        wrong_anchor["event_page"]["anchor_cursor"] = json!(1);
        let mut tampered = running(&operation(), &view());
        tampered["projection"]["definition_contract"]["deadline"] = json!("bounded");
        for answer in [
            observed(refused),
            observed(running(&"e".repeat(64), &view())),
            observed(wrong_anchor),
            observed(tampered),
            submitted(&operation()),
        ] {
            let fake = Fake::new(vec![reply(answer)]);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_observe",
                    json!({"operation_id": operation(), "after_cursor": 0}),
                ),
                "unavailable",
            );
        }
        // The request model strips an id it sends, but the reply must name the id asked about.
        let fake = Fake::new(vec![reply(observed(running(&operation(), &view())))]);
        refused_with(
            handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_observe",
                json!({"operation_id": format!(" {}", operation()), "after_cursor": 0}),
            ),
            "unavailable",
        );
        assert_eq!(
            fake.sent()[0]["observation"]["operation_id"],
            json!(operation())
        );
        for request in [
            json!({"operation_id": operation(), "after_cursor": -1}),
            json!({"operation_id": operation(), "after_cursor": "5"}),
            json!({"operation_id": operation(), "after_cursor": true}),
            json!({"operation_id": operation(), "after_cursor": 1.0}),
            json!({"operation_id": "", "after_cursor": 0}),
            json!({"after_cursor": 0}),
        ] {
            let fake = Fake::new(Vec::new());
            let failure = handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_observe",
                request,
            );
            assert!(matches!(failure, Err(RelayFailure::Invalid)), "{failure:?}");
            assert!(fake.sent().is_empty());
        }
        let fake = Fake::new(Vec::new());
        let unknown = handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_detach",
            json!({"operation_id": operation()}),
        );
        assert!(matches!(unknown, Err(RelayFailure::Invalid)));
    }

    #[test]
    fn a_settled_result_is_read_page_by_page() {
        let document = result_envelope(&view(), json!({"text": "\u{f1}".repeat(20_000)}));
        let bytes = canonical_json(&document).into_bytes();
        assert!(bytes.len() > PROJECTION_PAGE_BYTES);
        let digest = Sha256Digest::of(&bytes).to_string();
        let mut steps = vec![reply(observed(succeeded(&operation(), &view())))];
        steps.extend(pages(&operation(), &bytes));
        let fake = Fake::new(steps);
        let mut relay = OperationRelay::new();
        let answered = handle(
            &fake,
            &mut relay,
            "operation_result",
            json!({"operation_id": operation()}),
        )
        .unwrap();
        assert_eq!(
            Value::Object(answered),
            json!({
                "kind": "operation_result",
                "operation_id": operation(),
                "definition_id": "user-profile.view",
                "document": document,
            })
        );
        assert!(!relay.watching());
        let result = json!({
            "definition_contract_digest": view()["definition_contract_digest"],
            "operation_id": operation(),
            "result_projection_version": 1,
            "result_schema": view()["result_schema"],
            "terminal_revision": 3,
        });
        let sent = fake.sent();
        assert_eq!(sent.len(), 3);
        assert_eq!(
            sent[1],
            target(json!({
                "action": "operation_result_page",
                "page": {"expected_digest": null, "offset": 0},
                "result": result,
            }))
        );
        assert_eq!(
            sent[2],
            target(json!({
                "action": "operation_result_page",
                "page": {"expected_digest": digest, "offset": PROJECTION_PAGE_BYTES},
                "result": result,
            }))
        );
    }

    #[test]
    fn a_declared_refusal_has_a_document_and_an_unsettled_operation_none() {
        let contract = relay_contract();
        let refused = observation(
            &operation(),
            &contract,
            "terminal",
            Some("refused"),
            (None, Some("REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE")),
            json!({"disposition": "none"}),
        );
        let document = result_envelope(&contract, json!({"reason": "unavailable"}));
        let mut steps = vec![reply(observed(refused))];
        steps.extend(pages(&operation(), canonical_json(&document).as_bytes()));
        let fake = Fake::new(steps);
        let answered = handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_result",
            json!({"operation_id": operation()}),
        )
        .unwrap();
        assert_eq!(answered["document"], document);

        let undeclared = observation(
            &operation(),
            &view(),
            "terminal",
            Some("refused"),
            (None, Some("REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE")),
            json!({"disposition": "none"}),
        );
        for state in [running(&operation(), &view()), undeclared] {
            let fake = Fake::new(vec![reply(observed(state))]);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_result",
                    json!({"operation_id": operation()}),
                ),
                "no_result",
            );
            assert_eq!(fake.sent().len(), 1);
        }
    }

    #[test]
    fn a_result_document_must_match_its_digest_canonical_form_and_schema() {
        let document = result_envelope(&view(), json!({"text": "\u{f1}".repeat(20_000)}));
        let bytes = canonical_json(&document).into_bytes();
        let mut forged = pages(&operation(), &bytes);
        if let (Ok(second), _) = &mut forged[1] {
            second["page"]["document_digest"] = json!("0".repeat(64));
        }
        let mut other_schema = document.clone();
        other_schema["result_schema"]["schema_version"] = json!(2);
        let cases = [
            forged,
            pages(&operation(), b"{\"a\": 1}"),
            pages(&operation(), b"{\"a\":1,\"a\":1}"),
            pages(&operation(), canonical_json(&other_schema).as_bytes()),
            pages(&"e".repeat(64), &bytes),
        ];
        for case in cases {
            let mut steps = vec![reply(observed(succeeded(&operation(), &view())))];
            steps.extend(case);
            let fake = Fake::new(steps);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_result",
                    json!({"operation_id": operation()}),
                ),
                "unavailable",
            );
        }
    }

    fn review_document() -> Value {
        let contract = relay_contract();
        json!({
            "outcome": "success",
            "review_projection_version": 1,
            "projection_schema": contract["review_projection_schema"],
            "definition_contract_digest": contract["definition_contract_digest"],
            "projection": {"t\u{ed}tulo": "Revisi\u{f3}n", "amount": 12.5, "lines": [{"n": 1}, {"n": 2}]},
        })
    }

    #[test]
    fn a_pending_review_is_read_with_the_digest_of_what_it_showed() {
        let fake = Fake::new(vec![
            reply(observed(awaiting_review())),
            reply(projected_reply(&operation(), "review", review_document())),
        ]);
        let answered = handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_review",
            json!({"operation_id": operation()}),
        )
        .unwrap();
        assert_eq!(
            Value::Object(answered),
            json!({
                "kind": "operation_review",
                "operation_id": operation(),
                "interaction_id": interaction(),
                "revision": 3,
                "expires_at": "2026-10-24T10:05:00.123000+00:00",
                "review_digest": REVIEW_DIGEST,
                "document": review_document(),
            })
        );
        assert_eq!(
            fake.sent()[1],
            target(json!({
                "action": "operation_review",
                "review": {"reference": review_reference(), "review_projection_version": 1},
            }))
        );
    }

    #[test]
    fn a_review_that_is_not_pending_or_does_not_match_is_refused() {
        let refused_document = json!({
            "outcome": "refused",
            "review_projection_version": 1,
            "code": "review_not_pending",
            "requested_version": null,
            "supported_version": 1,
            "diagnostic_ref": null,
        });
        let mut other_schema = review_document();
        other_schema["projection_schema"]["schema_version"] = json!(2);
        let cases = [
            (
                vec![reply(observed(running(&operation(), &relay_contract())))],
                "not_pending",
            ),
            (
                vec![
                    reply(observed(awaiting_review())),
                    reply(projected_reply(&operation(), "review", refused_document)),
                ],
                "not_pending",
            ),
            (
                vec![
                    reply(observed(awaiting_review())),
                    reply(projected_reply(&operation(), "result", review_document())),
                ],
                "not_pending",
            ),
            (
                vec![
                    reply(observed(awaiting_review())),
                    reply(managed_reply(&operation(), review_document())),
                ],
                "not_pending",
            ),
            (
                vec![
                    reply(observed(awaiting_review())),
                    reply(projected_reply(&operation(), "review", other_schema)),
                ],
                "unavailable",
            ),
        ];
        for (steps, code) in cases {
            let fake = Fake::new(steps);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_review",
                    json!({"operation_id": operation()}),
                ),
                code,
            );
        }
    }

    fn control_success(intents: Value) -> Value {
        json!({
            "outcome": "success",
            "response_control_version": 1,
            "operation_id": operation(),
            "interaction_id": interaction(),
            "revision": 3,
            "available": intents.as_array().is_some_and(|intents| !intents.is_empty()),
            "permitted_intents": intents,
        })
    }

    fn response_success(action: &str) -> Value {
        json!({
            "outcome": "success",
            "response_control_version": 1,
            "operation_id": operation(),
            "interaction_id": interaction(),
            "revision": 3,
            "response_action": action,
        })
    }

    fn answer(decision: &str, revision: u64, digest: &str) -> Value {
        json!({
            "operation_id": operation(),
            "interaction_id": interaction(),
            "revision": revision,
            "review_digest": digest,
            "decision": decision,
        })
    }

    fn then(mut steps: Vec<Step>, step: Step) -> Vec<Step> {
        steps.push(step);
        steps
    }

    fn reviewed() -> Vec<Step> {
        vec![
            reply(observed(awaiting_review())),
            reply(projected_reply(&operation(), "review", review_document())),
        ]
    }

    #[test]
    fn an_answer_is_bound_to_the_review_and_to_response_authority() {
        for decision in ["apply", "reject"] {
            let mut steps = reviewed();
            steps.push(reply(managed_reply(
                &operation(),
                control_success(json!(["apply", "reject"])),
            )));
            steps.push(reply(managed_reply(
                &operation(),
                response_success(decision),
            )));
            let fake = Fake::new(steps);
            let answered = handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_respond",
                answer(decision, 3, REVIEW_DIGEST),
            )
            .unwrap();
            assert_eq!(
                Value::Object(answered),
                json!({"kind": "operation_responded", "operation_id": operation(), "decision": decision})
            );
            let control = json!({
                "actor_ref": format!("session:{SESSION}"),
                "interaction_id": interaction(),
                "operation_id": operation(),
                "response_control_version": 1,
                "revision": 3,
            });
            let sent = fake.sent();
            assert_eq!(sent.len(), 4);
            assert_eq!(
                sent[2],
                target(json!({"action": "operation_manage", "management": control}))
            );
            let mut mutation = sent[3]["management"].as_object().unwrap().clone();
            let responded_at = mutation.remove("responded_at").unwrap();
            let responded_at = responded_at.as_str().unwrap();
            assert!(
                responded_at.ends_with('Z') && utc_isoformat(responded_at).is_some(),
                "{responded_at}"
            );
            let mut expected = members(control);
            expected.insert("response_action".into(), json!(decision));
            if decision == "reject" {
                expected.insert("reason_code".into(), Value::Null);
            }
            assert_eq!(mutation, expected);
        }
    }

    #[test]
    fn an_answer_to_another_review_or_without_authority_is_refused() {
        let control_refused = json!({
            "outcome": "refused",
            "response_control_version": 1,
            "code": "response_not_pending",
            "requested_version": null,
            "supported_version": 1,
            "diagnostic_ref": null,
        });
        let mut wrong_action = reviewed();
        wrong_action.push(reply(managed_reply(
            &operation(),
            control_success(json!(["apply"])),
        )));
        wrong_action.push(reply(managed_reply(
            &operation(),
            response_success("reject"),
        )));
        let cases = [
            (
                reviewed(),
                answer("apply", 3, &"0".repeat(64)),
                "review_changed",
            ),
            (reviewed(), answer("apply", 4, REVIEW_DIGEST), "not_pending"),
            (
                then(
                    reviewed(),
                    reply(managed_reply(
                        &operation(),
                        control_success(json!(["reject"])),
                    )),
                ),
                answer("apply", 3, REVIEW_DIGEST),
                "response_authority_required",
            ),
            (
                then(
                    reviewed(),
                    reply(managed_reply(&operation(), control_success(json!([])))),
                ),
                answer("reject", 3, REVIEW_DIGEST),
                "response_authority_required",
            ),
            (
                then(
                    reviewed(),
                    reply(managed_reply(&operation(), control_refused)),
                ),
                answer("apply", 3, REVIEW_DIGEST),
                "response_not_pending",
            ),
            (
                wrong_action,
                answer("apply", 3, REVIEW_DIGEST),
                "unavailable",
            ),
        ];
        for (steps, request, code) in cases {
            let fake = Fake::new(steps);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_respond",
                    request,
                ),
                code,
            );
            assert!(fake.finished());
        }
        for request in [
            answer("maybe", 3, REVIEW_DIGEST),
            answer("apply", 3, ""),
            json!({"operation_id": operation(), "interaction_id": interaction(), "revision": 3, "review_digest": REVIEW_DIGEST}),
        ] {
            let fake = Fake::new(Vec::new());
            let failure = handle(
                &fake,
                &mut OperationRelay::new(),
                "operation_respond",
                request,
            );
            assert!(matches!(failure, Err(RelayFailure::Invalid)), "{failure:?}");
            assert!(fake.sent().is_empty());
        }
    }

    #[test]
    fn a_cancellation_is_requested_at_the_observed_revision() {
        let success = json!({
            "outcome": "success",
            "cancellation_version": 1,
            "operation_id": operation(),
            "revision": 5,
            "cancellation_requested": true,
            "cancellation_acknowledged": false,
        });
        let fake = Fake::new(vec![reply(managed_reply(&operation(), success.clone()))]);
        let answered = handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_cancel",
            json!({"operation_id": operation(), "expected_revision": 4}),
        )
        .unwrap();
        assert_eq!(
            Value::Object(answered),
            json!({"kind": "operation_cancel_requested", "operation_id": operation()})
        );
        assert_eq!(
            fake.sent(),
            vec![target(json!({
                "action": "operation_manage",
                "management": {"cancellation_version": 1, "expected_revision": 4, "operation_id": operation()},
            }))]
        );
        let refused = json!({
            "outcome": "refused",
            "cancellation_version": 1,
            "code": "operation_terminal",
            "requested_version": null,
            "supported_version": 1,
            "diagnostic_ref": "sha256:0123456789ab",
        });
        let mut unrequested = success.clone();
        unrequested["cancellation_requested"] = json!(false);
        for (document, code) in [
            (refused, "operation_terminal"),
            (unrequested, "unavailable"),
        ] {
            let fake = Fake::new(vec![reply(managed_reply(&operation(), document))]);
            refused_with(
                handle(
                    &fake,
                    &mut OperationRelay::new(),
                    "operation_cancel",
                    json!({"operation_id": operation(), "expected_revision": 4}),
                ),
                code,
            );
        }
        let fake = Fake::new(Vec::new());
        let failure = handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_cancel",
            json!({"operation_id": operation()}),
        );
        assert!(matches!(failure, Err(RelayFailure::Invalid)));
    }

    fn view_submission(cursor: u64) -> Value {
        target(json!({
            "action": "operation_submit",
            "definition_id": "user-profile.view",
            "idempotency_key": null,
            // The product's request model, serialized as its client submits it.
            "payload_json": format!("{{\"profile_id\":\"{PROFILE}\",\"page_kind\":\"preferences\",\"cursor\":{cursor},\"limit\":128,\"expected_revision\":null,\"expected_content_digest\":null,\"output_language\":\"es\"}}"),
            "subject_ref": format!("profile:{PROFILE}"),
        }))
    }

    fn view_observation(id: &str, page_limit: u64) -> Value {
        target(json!({
            "action": "operation_observe",
            "observation": {"after_cursor": 0, "observation_version": 1, "operation_id": id, "page_limit": page_limit},
        }))
    }

    #[test]
    fn the_language_is_read_through_the_view_on_the_sessions_cue() {
        let id = operation();
        let fake = Fake::new(vec![
            reply(contract_reply(view())),
            reply(submitted(&id)),
            reply(acknowledged(&id)),
            reply(observed(running(&id, &view()))),
            reply_with_cue(observed(running(&id, &view())), SESSION),
            reply(observed(succeeded(&id, &view()))),
            reply(projected_reply(
                &id,
                "result",
                result_envelope(&view(), preferences(7, Some("ca"))),
            )),
        ]);
        let started = Instant::now();
        let language =
            read_profile_language(&fake, &session(), started + Duration::from_secs(60)).unwrap();
        assert!(started.elapsed() < Duration::from_secs(10));
        assert_eq!(
            language,
            ProfileLanguage {
                language: Some("ca".to_owned()),
                record_revision: 7,
                content_digest: "f".repeat(64),
            }
        );
        assert_eq!(
            fake.sent(),
            vec![
                target(
                    json!({"action": "operation_contract", "definition_id": "user-profile.view"})
                ),
                view_submission(0),
                target(json!({"action": "operation_start", "operation_id": id})),
                view_observation(&id, 32),
                view_observation(&id, 32),
                view_observation(&id, 32),
                target(json!({
                    "action": "operation_result",
                    "result": {
                        "definition_contract_digest": view()["definition_contract_digest"],
                        "operation_id": id,
                        "result_projection_version": 1,
                        "result_schema": view()["result_schema"],
                        "terminal_revision": 3,
                    },
                })),
            ]
        );
    }

    #[test]
    fn a_wait_ends_at_the_deadline_and_ignores_another_sessions_cue() {
        let id = operation();
        let fake = Fake::new(vec![
            reply(contract_reply(view())),
            reply(submitted(&id)),
            reply(acknowledged(&id)),
            reply(observed(running(&id, &view()))),
            reply_with_cue(observed(running(&id, &view())), OTHER_SESSION),
            reply(observed(succeeded(&id, &view()))),
        ]);
        let started = Instant::now();
        let failure =
            read_profile_language(&fake, &session(), started + Duration::from_millis(400));
        assert!(started.elapsed() >= Duration::from_millis(400));
        assert!(
            matches!(
                failure,
                Err(RelayFailure::Unavailable(Refusal::DeadlineExceeded))
            ),
            "{failure:?}"
        );
        // Two observations, then one wait: no polling.
        assert_eq!(fake.sent().len(), 5);
    }

    #[test]
    fn a_language_read_ends_on_a_refused_page_operation_or_value() {
        let mut stale = preferences(7, None);
        stale["outcome"] = json!("refused");
        stale["refusal_code"] = json!("stale_revision");
        let refused_observation = json!({
            "outcome": "refused",
            "observation_version": 1,
            "code": "unknown_operation",
            "requested_version": null,
            "supported_version": 1,
            "diagnostic_ref": null,
        });
        let refused_envelope = json!({
            "outcome": "refused",
            "result_projection_version": 1,
            "code": "operation_not_successful",
            "requested_version": null,
            "supported_version": 1,
            "diagnostic_ref": null,
        });
        let mut foreign = preferences(7, Some("ca"));
        foreign["profile_id"] = json!(OTHER_SESSION);
        let failed = observation(
            &operation(),
            &view(),
            "terminal",
            Some("refused"),
            (None, Some("profile_locked_out")),
            json!({"disposition": "none"}),
        );
        let id = operation();
        let cases: Vec<(Vec<Step>, &str)> = vec![
            (language_read(&id, stale), "stale_revision"),
            (
                vec![
                    reply(contract_reply(view())),
                    reply(submitted(&id)),
                    reply(acknowledged(&id)),
                    reply(observed(refused_observation)),
                ],
                "unknown_operation",
            ),
            (
                vec![
                    reply(contract_reply(view())),
                    reply(submitted(&id)),
                    reply(acknowledged(&id)),
                    reply(observed(failed)),
                ],
                "profile_locked_out",
            ),
            (
                vec![
                    reply(contract_reply(view())),
                    reply(submitted(&id)),
                    reply(acknowledged(&id)),
                    reply(observed(succeeded(&id, &view()))),
                    reply(projected_reply(&id, "result", refused_envelope)),
                ],
                "runtime_invalid_frame",
            ),
            (language_read(&id, foreign), "runtime_invalid_frame"),
            (
                vec![reply(contract_reply(mutation()))],
                "runtime_invalid_frame",
            ),
        ];
        for (steps, code) in cases {
            let fake = Fake::new(steps);
            match read_profile_language(&fake, &session(), Instant::now() + Duration::from_secs(60))
            {
                Err(RelayFailure::Unavailable(refusal)) => assert_eq!(refusal.code(), code),
                other => panic!("expected {code}, got {other:?}"),
            }
            assert!(fake.finished());
        }
        let fake = Fake::new(language_read(&id, preferences(7, Some("fr"))));
        let failure =
            read_profile_language(&fake, &session(), Instant::now() + Duration::from_secs(60));
        assert!(matches!(failure, Err(RelayFailure::Invalid)), "{failure:?}");
        let fake = Fake::new(language_read(&id, preferences(7, None)));
        let unset =
            read_profile_language(&fake, &session(), Instant::now() + Duration::from_secs(60))
                .unwrap();
        assert_eq!(unset.language, None);
    }

    #[test]
    fn every_page_of_one_read_must_share_its_revision() {
        let page = Pin {
            record_revision: 7,
            content_digest: "f".repeat(64),
            setup_state: "complete".into(),
            schema_version: 1,
            valid: true,
        };
        let pinned = next_pin(None, &page).unwrap();
        assert_eq!(next_pin(Some(pinned.clone()), &page).unwrap(), page);
        for changed in [
            Pin {
                record_revision: 8,
                ..page.clone()
            },
            Pin {
                content_digest: "e".repeat(64),
                ..page.clone()
            },
            Pin {
                setup_state: "incomplete".into(),
                ..page.clone()
            },
            Pin {
                schema_version: 2,
                ..page.clone()
            },
            Pin {
                valid: false,
                ..page.clone()
            },
        ] {
            match next_pin(Some(pinned.clone()), &changed) {
                Err(Failure::Refused { code, .. }) => assert_eq!(code, "stale_revision"),
                other => panic!("{other:?}"),
            }
        }
        // A continuation names the pinned revision, as the product's request model spells it.
        assert_eq!(
            view_request(PROFILE, 1, Some(&page)),
            format!(
                "{{\"profile_id\":\"{PROFILE}\",\"page_kind\":\"preferences\",\"cursor\":1,\"limit\":128,\"expected_revision\":7,\"expected_content_digest\":\"{}\",\"output_language\":\"es\"}}",
                "f".repeat(64)
            )
        );
    }

    fn mutation_result(revision: u64) -> Value {
        result_envelope(
            &mutation(),
            json!({"profile_id": PROFILE, "record_revision": revision}),
        )
    }

    fn language_set(result: &Value, terminal: Value) -> Vec<Step> {
        let id = mutation_operation();
        let mut steps = language_read(&operation(), preferences(7, Some("ca")));
        steps.extend([
            reply(contract_reply(mutation())),
            reply(submitted(&id)),
            reply(acknowledged(&id)),
            reply(observed(terminal)),
        ]);
        steps.extend(pages(&id, canonical_json(result).as_bytes()));
        steps
    }

    #[test]
    fn the_language_is_set_at_the_revision_just_read() {
        let id = mutation_operation();
        let mut steps = language_set(&mutation_result(8), succeeded(&id, &mutation()));
        steps.extend(language_read(&operation(), preferences(8, Some("hu"))));
        let fake = Fake::new(steps);
        let language = set_profile_language(
            &fake,
            &session(),
            "hu",
            Instant::now() + Duration::from_secs(60),
        )
        .unwrap();
        assert_eq!(language.language.as_deref(), Some("hu"));
        assert_eq!(language.record_revision, 8);
        let sent = fake.sent();
        assert_eq!(sent.len(), 15);
        assert_eq!(
            sent[5..10],
            [
                target(
                    json!({"action": "operation_contract", "definition_id": "user-profile.field-mutation"})
                ),
                target(json!({
                    "action": "operation_submit",
                    "definition_id": "user-profile.field-mutation",
                    "idempotency_key": null,
                    // The product's field mutation request, serialized as its client submits it.
                    "payload_json": format!("{{\"profile_id\":\"{PROFILE}\",\"expected_revision\":7,\"expected_content_digest\":\"{}\",\"path\":\"preferences.output_language\",\"value\":\"hu\"}}", "f".repeat(64)),
                    "subject_ref": format!("profile:{PROFILE}"),
                })),
                target(json!({"action": "operation_start", "operation_id": id})),
                view_observation(&id, 1),
                target(json!({
                    "action": "operation_result_page",
                    "page": {"expected_digest": null, "offset": 0},
                    "result": {
                        "definition_contract_digest": mutation()["definition_contract_digest"],
                        "operation_id": id,
                        "result_projection_version": 1,
                        "result_schema": mutation()["result_schema"],
                        "terminal_revision": 3,
                    },
                })),
            ]
        );
        assert_eq!(sent[10]["action"], json!("operation_contract"));
    }

    #[test]
    fn a_language_set_refuses_a_stale_foreign_or_unsettled_mutation() {
        let id = mutation_operation();
        let mut changed = mutation_result(9);
        changed["projection"]["changed"] = json!(true);
        let mut foreign = mutation_result(9);
        foreign["projection"]["profile_id"] = json!(OTHER_SESSION);
        let refused = observation(
            &id,
            &mutation(),
            "terminal",
            Some("refused"),
            (None, Some("profile_revision_conflict")),
            json!({"disposition": "none"}),
        );
        // Another valid contract for the same definition: the operation must run under the one discovered.
        let other_contract = succeeded(
            &id,
            &serde_json::from_str(REGISTERED_MUTATION_CONTRACT).unwrap(),
        );
        let cases = [
            (
                language_set(&mutation_result(6), succeeded(&id, &mutation())),
                "runtime_invalid_frame",
            ),
            (
                language_set(&changed, succeeded(&id, &mutation())),
                "runtime_invalid_frame",
            ),
            (
                language_set(&foreign, succeeded(&id, &mutation())),
                "runtime_invalid_frame",
            ),
            (
                language_set(&mutation_result(8), other_contract),
                "runtime_invalid_frame",
            ),
            (
                language_set(&mutation_result(8), refused),
                "profile_revision_conflict",
            ),
        ];
        for (steps, code) in cases {
            let fake = Fake::new(steps);
            match set_profile_language(
                &fake,
                &session(),
                "hu",
                Instant::now() + Duration::from_secs(60),
            ) {
                Err(RelayFailure::Unavailable(refusal)) => assert_eq!(refusal.code(), code),
                other => panic!("expected {code}, got {other:?}"),
            }
        }
        let fake = Fake::new(Vec::new());
        let failure = set_profile_language(
            &fake,
            &session(),
            "fr",
            Instant::now() + Duration::from_secs(60),
        );
        assert!(matches!(failure, Err(RelayFailure::Invalid)));
        assert!(fake.sent().is_empty());
    }
}
