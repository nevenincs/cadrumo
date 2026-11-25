use super::failure::{Failure, Outcome, RelayFailure};
use super::lifecycle::{
    Upload, cancel, deliver_secret, describe, error_detail_schema, managed, observe_once,
    projected, read_result_document, response_accepted, response_control, result_request, start,
    submit, submitted_receipt,
};
use super::protocol::{
    Observation, Observed, PROJECTION_DOCUMENT_MAX_BYTES, Pending, Projection, RESPONSE_REFUSALS,
    Review, SUBJECT_REF_MAX_CHARS, actor_reference, argument_count, argument_text, content_hash,
    definition_id, members, refusal_code, request_hex64, text,
};
use super::timestamps::utc_now;
use super::transport::Held;
use crate::canonical_json::compact_json;
use crate::runtime_client::{
    connection::SessionExchange, framing::MAXIMUM_SECRET_BYTES, session::Admitted,
};
use serde_json::{Map, Value, json};
use std::collections::BTreeSet;
use std::time::{Duration, Instant};
use zeroize::Zeroizing;

/// One budget for a whole relay action, every exchange included.
pub(super) const RELAY_BUDGET: Duration = Duration::from_secs(120);
pub(super) const RELAY_EVENT_PAGE: u64 = 64;
pub(super) const MAX_WATCHED: usize = 16;

/// Each relay action and the request members it takes beside `request_id` and `action`.
pub const RELAY_ACTION_KEYS: [(&str, &[&str]); 8] = [
    (
        "operation_submit",
        &["definition_id", "subject_ref", "payload"],
    ),
    // `secret` is the exact text of the secret frame, 1 to `MAXIMUM_SECRET_BYTES`
    // bytes, in the form the definition's executor parses.
    (
        "operation_secret_submit",
        &["definition_id", "subject_ref", "payload", "secret"],
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
/// The registered operations one held person session submitted and still follows.
#[derive(Debug, Default)]
pub struct OperationRelay {
    pub(super) watched: BTreeSet<String>,
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
        if action == "operation_secret_submit" {
            return self.submit_secret(held, request, deadline);
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
        if payload_json.len() > PROJECTION_DOCUMENT_MAX_BYTES {
            return Err(Failure::Invalid);
        }
        let definition_id = argument_text(request, "definition_id")?;
        let subject_ref = argument_text(request, "subject_ref")?;
        let submitted = submit(held, definition_id, subject_ref, &payload_json, deadline)?;
        self.started(held, submitted.without_secret()?, deadline)
    }

    /// Submits a definition whose contract requires an ephemeral secret and
    /// hands the runtime `secret` on its secret frame, then starts the
    /// operation. Nothing is submitted for a definition that takes no secret,
    /// nothing is sent on the secret frame unless the runtime names exactly
    /// this submission's wait and says it is ready, and the operation does not
    /// start unless the runtime acknowledges the secret. A request that
    /// fails after the secret was written has an unknown outcome.
    fn submit_secret(
        &mut self,
        held: &Held,
        request: &Map<String, Value>,
        deadline: Instant,
    ) -> Outcome<Map<String, Value>> {
        let payload = request.get("payload").ok_or(Failure::Invalid)?;
        if !payload.is_object() {
            return Err(Failure::Invalid);
        }
        // The secret is only borrowed from the parent's request, which the
        // parent overwrites once the exchange ends.
        let secret = match request.get("secret") {
            Some(Value::String(secret)) if (1..=MAXIMUM_SECRET_BYTES).contains(&secret.len()) => {
                secret
            }
            _ => return Err(Failure::Invalid),
        };
        let payload_json = Zeroizing::new(compact_json(payload));
        if payload_json.len() > PROJECTION_DOCUMENT_MAX_BYTES {
            return Err(Failure::Invalid);
        }
        let definition = argument_text(request, "definition_id")?;
        let subject_ref = argument_text(request, "subject_ref")?;
        let subject_length = subject_ref.chars().count();
        if !definition_id(definition) || !(1..=SUBJECT_REF_MAX_CHARS).contains(&subject_length) {
            return Err(Failure::frame());
        }
        if !describe(held, definition, deadline)?.ephemeral_secret_required {
            return Err(Failure::code("secret_not_required"));
        }
        let submitted = submit(held, definition, subject_ref, &payload_json, deadline)?;
        drop(payload_json);
        let requirement = submitted.requirement_for(definition, subject_ref)?;
        deliver_secret(held, requirement, &submitted.operation_id, secret, deadline)?;
        self.started(held, submitted.operation_id, deadline)
    }

    /// Hands the parent's input to the runtime once, streamed as its financial
    /// input, and starts the operation. The runtime refuses a definition
    /// whose contract takes no financial operand, so the relay names none;
    /// the encoded input is overwritten once sent.
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
        if !(2..=PROJECTION_DOCUMENT_MAX_BYTES).contains(&input_json.len()) {
            return Err(Failure::Invalid);
        }
        let reply = held.streamed(
            definition,
            subject_ref,
            &input_json,
            Upload::Financial,
            deadline,
        )?;
        drop(input_json);
        let operation_id = submitted_receipt(&reply)?.without_secret()?;
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
        let stopped = matches!(
            projection.terminal_condition.as_deref(),
            Some("refused" | "failed")
        );
        let schema = match &contract.result_schema {
            Some(schema) if projection.terminal && documented => schema.clone(),
            // Any other stop carries the detail its executor recorded, where it recorded one.
            _ if projection.terminal && stopped => error_detail_schema(),
            _ => return Err(Failure::code("no_result")),
        };
        let document = read_result_document(held, &result_request(&projection, &schema), deadline)?;
        if text(&document, "outcome") == Some("refused") && schema == error_detail_schema() {
            return Err(Failure::code("no_result"));
        }
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
