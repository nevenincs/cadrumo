use super::failure::{Failure, Outcome};
use super::protocol::{
    CANCELLATION_REFUSALS, Contract, ERROR_DETAIL_SCHEMA_FINGERPRINT, ERROR_DETAIL_SCHEMA_ID,
    ERROR_DETAIL_SCHEMA_VERSION, Observed, PROJECTION_DOCUMENT_MAX_BYTES, PROJECTION_PAGE_BYTES,
    PROJECTION_PAGE_MAX_ENCODED, Projection, Review, SECRET_IDENTITY_KEYS, SECRET_REQUIREMENT_KEYS,
    SUBJECT_REF_MAX_CHARS, closed, content_hash, contract, count, definition_id, dotted, envelope,
    flag, hex64, members, nullable_utc, observed, one_of, refusal_code, request_hex64,
    schema_identity, succeeded, text, version_one,
};
use super::sensitive::sent_then_wiped;
use super::transport::{Held, remaining};
use crate::canonical_json::canonical_json;
use crate::runtime_client::framing::MAXIMUM_FRAME_BYTES;
use crate::runtime_client::{
    events::{Event, Pushed},
    framing::base64_decode,
    refusal::Refusal,
};
use crate::value::Sha256Digest;
use serde_json::{Map, Value, json};
use std::sync::mpsc;
use std::time::Instant;
use zeroize::Zeroizing;

pub(super) fn observe_once(
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

/// Submits one registered request and returns what the runtime admitted.
pub(super) fn submit(
    held: &Held,
    definition: &str,
    subject_ref: &str,
    payload_json: &str,
    deadline: Instant,
) -> Outcome<Submitted> {
    let subject_length = subject_ref.chars().count();
    if !definition_id(definition)
        || !(1..=SUBJECT_REF_MAX_CHARS).contains(&subject_length)
        || payload_json.chars().count() < 2
    {
        return Err(Failure::frame());
    }
    let mut request = held.request(
        "operation_submit",
        json!({
            "definition_id": definition,
            "subject_ref": subject_ref,
            "payload_json": payload_json,
            "idempotency_key": null,
        }),
        deadline,
    )?;
    // The exact bytes the connection writes as the frame decide whether one
    // frame carries the request.
    let framed = Zeroizing::new(serde_json::to_vec(&request).map_err(|_| Failure::frame())?).len();
    let reply = if framed <= MAXIMUM_FRAME_BYTES {
        sent_then_wiped(&mut request, |request| held.send(request, deadline))?
    } else {
        // Too large for one runtime frame: the same submission, streamed. The
        // unsent request is overwritten as a sent one is.
        sent_then_wiped(&mut request, |_| ());
        held.streamed(
            definition,
            subject_ref,
            payload_json,
            Upload::Payload,
            deadline,
        )?
    };
    submitted_receipt(&reply)
}

/// What a streamed submission carries.
#[derive(Clone, Copy)]
pub(super) enum Upload {
    /// The registered request, checked against its digest.
    Payload,
    /// The definition's transient financial operand, which has no digest.
    Financial,
}

/// What the runtime admitted for a submission: the operation, and the wait for
/// a secret that its receipt opened, if any.
pub(super) struct Submitted {
    pub(super) operation_id: String,
    pub(super) secret_requirement: Option<Map<String, Value>>,
}

impl Submitted {
    /// The operation's id, when its receipt asks for no secret. A submission
    /// that cannot deliver one would leave the operation waiting unstarted.
    pub(super) fn without_secret(self) -> Outcome<String> {
        match self.secret_requirement {
            None => Ok(self.operation_id),
            Some(_) => Err(Failure::code("secret_required")),
        }
    }

    /// The wait the receipt opened, which must be a well-formed requirement
    /// naming exactly this operation, `definition` and `subject_ref`.
    pub(super) fn requirement_for(
        &self,
        definition: &str,
        subject_ref: &str,
    ) -> Outcome<&Map<String, Value>> {
        let requirement = self
            .secret_requirement
            .as_ref()
            .ok_or_else(Failure::frame)?;
        let identity = requirement
            .get("identity")
            .and_then(Value::as_object)
            .filter(|identity| closed(identity, &SECRET_IDENTITY_KEYS, &SECRET_IDENTITY_KEYS))
            .ok_or_else(Failure::frame)?;
        let secret_kind = text(requirement, "secret_kind");
        let named = text(identity, "operation_id") == Some(self.operation_id.as_str())
            && text(identity, "definition_id") == Some(definition)
            && text(identity, "subject_ref") == Some(subject_ref);
        let shaped = closed(
            requirement,
            &SECRET_REQUIREMENT_KEYS,
            &SECRET_REQUIREMENT_KEYS,
        ) && hex64(requirement, "interaction_id").is_ok()
            && count(requirement, "revision").is_ok()
            && secret_kind.is_some_and(|kind| (3..=64).contains(&kind.len()) && dotted(kind, 0))
            && matches!(nullable_utc(requirement, "expires_at"), Ok(Some(_)));
        if !named || !shaped {
            return Err(Failure::frame());
        }
        Ok(requirement)
    }
}

/// The operation an `operation_submitted` reply admitted.
pub(super) fn submitted_receipt(reply: &Map<String, Value>) -> Outcome<Submitted> {
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
    let secret_requirement = match receipt.get("secret_requirement") {
        Some(Value::Null) => None,
        Some(Value::Object(requirement)) => Some(requirement.clone()),
        _ => return Err(Failure::frame()),
    };
    Ok(Submitted {
        operation_id: hex64(receipt, "operation_id")?.to_owned(),
        secret_requirement,
    })
}

/// Hands `secret` to the wait `requirement` names, on the secret frame the
/// runtime opens once it has accepted exactly that requirement, and requires
/// it to acknowledge the secret for `operation_id`. A refusal before the
/// runtime is ready sends nothing.
pub(super) fn deliver_secret(
    held: &Held,
    requirement: &Map<String, Value>,
    operation_id: &str,
    secret: &str,
    deadline: Instant,
) -> Outcome<()> {
    let request = held.request(
        "operation_secret",
        json!({"requirement": requirement}),
        deadline,
    )?;
    let reply = held
        .connection
        .exchange_with_secret(&request, secret.as_bytes(), deadline)?;
    envelope(&reply, "operation_acknowledged", &["operation_id"])?;
    if hex64(&reply, "operation_id")? != operation_id {
        return Err(Failure::frame());
    }
    Ok(())
}

/// Admits a submitted operation; the acknowledgement is not settlement.
pub(super) fn start(held: &Held, operation_id: &str, deadline: Instant) -> Outcome<()> {
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
pub(super) fn managed<'a>(
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

pub(super) struct Projected {
    pub(super) operation_id: String,
    pub(super) projection_kind: String,
    pub(super) document: Map<String, Value>,
}

pub(super) fn projected(reply: &Map<String, Value>) -> Outcome<Projected> {
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
pub(super) fn response_control(
    document: &Map<String, Value>,
    pending: &Review,
) -> Outcome<Vec<String>> {
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
pub(super) fn response_accepted(
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

pub(super) fn cancel(
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

pub(super) fn error_detail_schema() -> Value {
    json!({
        "schema_id": ERROR_DETAIL_SCHEMA_ID,
        "schema_version": ERROR_DETAIL_SCHEMA_VERSION,
        "schema_fingerprint": ERROR_DETAIL_SCHEMA_FINGERPRINT,
    })
}

pub(super) fn result_request(projection: &Projection, schema: &Value) -> Value {
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
pub(super) struct Page {
    pub(super) offset: usize,
    pub(super) total: usize,
    pub(super) digest: String,
    pub(super) bytes: Zeroizing<Vec<u8>>,
}

pub(super) fn page(value: Option<&Value>) -> Outcome<Page> {
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
pub(super) fn read_result_document(
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
pub(super) fn result_success(document: &Map<String, Value>) -> Outcome<(&Value, &str, &Value)> {
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
pub(super) fn cues(pushed: &Pushed, session_id: &str) -> bool {
    match pushed.event {
        Event::OperationChanged => pushed.session_id.as_deref() == Some(session_id),
        Event::Disconnected => true,
        _ => false,
    }
}

/// Waits for the held session's next operation cue or the deadline, whichever comes first.
pub(super) fn wait_for_cue(
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
pub(super) fn await_terminal(
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
pub(super) fn settled(projection: &Projection) -> Outcome<()> {
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
pub(super) fn describe(held: &Held, definition: &str, deadline: Instant) -> Outcome<Contract> {
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
