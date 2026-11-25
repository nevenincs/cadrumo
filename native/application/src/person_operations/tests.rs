use super::failure::{Failure, RelayFailure};
use super::lifecycle::error_detail_schema;
use super::profile_language::{
    OUTPUT_LANGUAGE_PATH, Pin, ProfileLanguage, next_pin, read_profile_language,
    set_profile_language, view_request,
};
use super::protocol::{
    ERROR_DETAIL_SCHEMA_FINGERPRINT, PROJECTION_DOCUMENT_MAX_BYTES, PROJECTION_PAGE_BYTES,
    SUBJECT_REF_MAX_CHARS, content_hash, contract, members, text, uuid_key,
};
use super::relay::{MAX_WATCHED, OperationRelay};
use super::sensitive::{sent_then_wiped, wipe};
use super::timestamps::{utc_isoformat, utc_text};
use crate::canonical_json::{canonical_json, compact_json};
use crate::runtime_client::framing::MAXIMUM_FRAME_BYTES;
use crate::runtime_client::{
    connection::SessionExchange,
    events::{Event, Pushed},
    framing::MAXIMUM_SECRET_BYTES,
    refusal::Refusal,
    session::Admitted,
};
use crate::value::Sha256Digest;
use serde_json::{Map, Value, json};
use std::collections::BTreeSet;
use std::sync::mpsc;
use std::time::{Duration, Instant};

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
    /// What was written on the secret frame, each only after the runtime
    /// answered a request for it with `secret_ready`.
    secrets: Mutex<Vec<Vec<u8>>>,
    subscribers: Mutex<Vec<mpsc::Sender<Pushed>>>,
}

impl Fake {
    fn new(steps: Vec<Step>) -> Self {
        Self {
            steps: Mutex::new(steps.into()),
            sent: Mutex::new(Vec::new()),
            secrets: Mutex::new(Vec::new()),
            subscribers: Mutex::new(Vec::new()),
        }
    }

    fn answer(&self) -> Result<Map<String, Value>, Refusal> {
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

    fn exchange(&self, request: &Value, _deadline: Instant) -> Result<Map<String, Value>, Refusal> {
        self.sent.lock().unwrap().push(request.clone());
        self.answer()
    }

    /// As the connection does: the secret is written only after the
    /// runtime answers the request with `secret_ready`, and the reply
    /// that follows it is the final one.
    fn exchange_with_secret(
        &self,
        request: &Value,
        secret: &[u8],
        _deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        self.sent.lock().unwrap().push(request.clone());
        let ready = self.answer()?;
        if text(&ready, "kind") != Some("secret_ready") {
            return Err(Refusal::InvalidFrame);
        }
        self.secrets.lock().unwrap().push(secret.to_vec());
        self.answer()
    }

    /// Records the upload's header with the bytes it streamed, after
    /// checking them against the header as the runtime's staging does.
    fn exchange_streamed(
        &self,
        request: &Value,
        payload: &[u8],
        deadline: Instant,
    ) -> Result<Map<String, Value>, Refusal> {
        let descriptor = &request["descriptor"];
        assert_eq!(descriptor["byte_count"], payload.len());
        if let Some(digest) = descriptor["payload_digest"].as_str() {
            assert_eq!(digest, Sha256Digest::of(payload).to_string());
        }
        let mut recorded = request.clone();
        recorded["streamed"] = json!(String::from_utf8(payload.to_vec()).unwrap());
        self.exchange(&recorded, deadline)
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
        .map(|language| json!({"kind": "fact", "path": OUTPUT_LANGUAGE_PATH, "value": language}))
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
fn content_hashes_are_the_products_digests_of_canonical_json() {
    let sample = "{\"z\": [1, -2, 3.5, 1e16, 1e-05, 0.0001, 123456789.125, -0.0, 1e300, 0.1, 1e15, 2.5e-07, 100.0], \"\u{e9}\": \"\u{f1}and\u{fa} \\\"quoted\\\" \\\\ \\n\\t\\u0001 \\u007f \u{1f600}\", \"A\": {\"nested\": {\"b\": true, \"a\": null, \"\u{ffff}\": [], \"\u{1f600}\": {}}}, \"\u{3a9}\": 18446744073709551615, \"neg\": -9223372036854775808}";
    let document: Value = serde_json::from_str(sample).unwrap();
    // Both values are the product's `content_hash_hex` of `sample` and of the schema.
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
    // Two bytes past the document in compact JSON; the bound counts bytes.
    let long = json!({"a": "\u{f1}".repeat((PROJECTION_DOCUMENT_MAX_BYTES - 8) / 2 + 1)});
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
    let at_bound = json!({"a": "\u{f1}".repeat((PROJECTION_DOCUMENT_MAX_BYTES - 8) / 2)});
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
    // Never as an ordinary submission: streamed as the runtime's own
    // financial input, which carries no digest, then the start.
    let input = "{\"amount\":\"1.234,56\",\"input_version\":2}";
    assert_eq!(
        fake.sent(),
        vec![
            target(json!({
                "action": "operation_submit_payload",
                "definition_id": "ledger.example-review",
                "idempotency_key": null,
                "descriptor": {"kind": "financial_operand_input", "byte_count": input.len()},
                "subject_ref": format!("profile:{PROFILE}"),
                "streamed": input,
            })),
            target(json!({"action": "operation_start", "operation_id": operation()})),
        ]
    );
}

#[test]
fn a_submission_beyond_one_frame_is_streamed_whole_and_beyond_the_document_is_refused() {
    let submit = |payload: Value| {
        json!({
            "definition_id": "ledger.example-review",
            "subject_ref": format!("profile:{PROFILE}"),
            "payload": payload,
        })
    };
    let wide = json!({"rows": "a".repeat(MAXIMUM_FRAME_BYTES)});
    let fake = Fake::new(vec![
        reply(submitted(&operation())),
        reply(acknowledged(&operation())),
    ]);
    let answered = handle(
        &fake,
        &mut OperationRelay::new(),
        "operation_submit",
        submit(wide.clone()),
    )
    .unwrap();
    assert_eq!(answered["operation_id"], operation());
    let sent = fake.sent();
    let payload = compact_json(&wide);
    assert_eq!(sent[0]["action"], "operation_submit_payload");
    assert_eq!(
        sent[0]["descriptor"],
        json!({
            "byte_count": payload.len(),
            "payload_digest": Sha256Digest::of(payload.as_bytes()).to_string(),
        })
    );
    assert_eq!(sent[0]["streamed"], payload);
    assert!(sent[0].get("payload_json").is_none());
    // Within one frame, a submission is still one document.
    let fake = Fake::new(vec![
        reply(submitted(&operation())),
        reply(acknowledged(&operation())),
    ]);
    handle(
        &fake,
        &mut OperationRelay::new(),
        "operation_submit",
        submit(json!({"a": 1})),
    )
    .unwrap();
    assert_eq!(fake.sent()[0]["action"], "operation_submit");
    // Past the document the relay carries, nothing reaches the runtime.
    let over = "a".repeat(PROJECTION_DOCUMENT_MAX_BYTES);
    for (action, request) in [
        ("operation_submit", submit(json!({"a": over}))),
        (
            "operation_financial_submit",
            json!({
                "definition_id": "ledger.example-review",
                "subject_ref": format!("profile:{PROFILE}"),
                "input": {"a": over},
            }),
        ),
    ] {
        let fake = Fake::new(Vec::new());
        let refused = handle(&fake, &mut OperationRelay::new(), action, request);
        assert!(matches!(refused, Err(RelayFailure::Invalid)), "{action}");
        assert!(fake.sent().is_empty(), "{action}");
    }
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
    let mut request = json!({"action": "operation_submit", "payload_json": iban, "rows": [iban]});
    let sent = sent_then_wiped(&mut request, |request| request.clone());
    assert_eq!(sent["payload_json"], iban);
    // Every value was overwritten in place before the request itself was emptied.
    assert_eq!(request, Value::Null);
}

#[test]
fn a_wiped_request_keeps_no_text_number_or_flag() {
    let mut request = json!({"payload_json": "{\"amount\":\"9876.54\"}",
        "nested": ["x", {"y": "z", "amount": 9876.54}], "n": -12, "count": 7, "apply": true});
    wipe(&mut request);
    assert_eq!(
        request,
        json!({"payload_json": "", "nested": ["", {"y": "", "amount": 0}], "n": 0,
            "count": 0, "apply": false})
    );
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
        recovery_remaining_seconds: None,
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
    // Refused before the worker took it: nothing was done, and the session comes back by itself.
    let recovering = Fake::new(vec![refuse(Refusal::denied("custody_recovering"))]);
    refused_with(
        handle(
            &recovering,
            &mut OperationRelay::new(),
            "operation_submit",
            request.clone(),
        ),
        "custody_recovering",
    );
    for failure in [
        Refusal::denied("runtime_draining"),
        Refusal::ConnectionClosed,
        Refusal::Timeout,
        // The worker was lost while it served the submission: it may have been made.
        Refusal::Unsettled {
            operation_id: None,
            recovery_remaining_seconds: Some(90),
        },
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

/// The product registry's own `auth.credential.save` description, as the
/// runtime answers a contract request for it.
const CREDENTIAL_DESCRIPTION: &str =
    include_str!("../../tests/data/auth-credential-save-description.json");
const CREDENTIAL: &str = "auth.credential.save";
/// The exact text of the secret frame the credential operation parses.
const SECRET: &str = r#"{"password":"horse-staple-7f3a"}"#;
const SECRET_WORD: &str = "horse-staple-7f3a";

fn credential_contract_reply() -> Value {
    serde_json::from_str(CREDENTIAL_DESCRIPTION).unwrap()
}

fn subject() -> String {
    format!("profile:{PROFILE}")
}

/// The wait the runtime opens for a credential submission.
fn requirement(id: &str) -> Value {
    json!({
        "identity": {"operation_id": id, "definition_id": CREDENTIAL, "subject_ref": subject()},
        "interaction_id": interaction(),
        "revision": 0,
        "secret_kind": "auth.credential.password",
        "expires_at": "2026-10-27T10:05:00Z",
    })
}

fn awaiting_secret(id: &str, requirement: Value) -> Value {
    json!({
        "kind": "operation_submitted",
        "receipt": {"submission_version": 1, "operation_id": id, "secret_requirement": requirement},
    })
}

fn secret_ready() -> Value {
    json!({"kind": "secret_ready"})
}

fn credential_request() -> Value {
    json!({
        "definition_id": CREDENTIAL,
        "subject_ref": subject(),
        "payload": {"provider": "certificate"},
        "secret": SECRET,
    })
}

fn secret_submit(
    fake: &Fake,
    relay: &mut OperationRelay,
    request: Value,
) -> Result<Map<String, Value>, RelayFailure> {
    handle(fake, relay, "operation_secret_submit", request)
}

/// The secret is in no document the runtime was sent beside its frame.
fn assert_secret_only_on_its_frame(fake: &Fake) {
    let sent = fake.sent();
    assert!(!serde_json::to_string(&sent).unwrap().contains(SECRET_WORD));
    assert!(!format!("{sent:?}").contains(SECRET_WORD));
}

#[test]
fn a_secret_travels_only_on_the_secret_frame_after_the_runtime_is_ready() {
    let fake = Fake::new(vec![
        reply(credential_contract_reply()),
        reply(awaiting_secret(&operation(), requirement(&operation()))),
        reply(secret_ready()),
        reply(acknowledged(&operation())),
        reply(acknowledged(&operation())),
    ]);
    let mut relay = OperationRelay::new();
    let answered = secret_submit(&fake, &mut relay, credential_request()).unwrap();
    assert_eq!(
        Value::Object(answered.clone()),
        json!({"kind": "operation_submitted", "operation_id": operation()})
    );
    assert!(!format!("{answered:?}").contains(SECRET_WORD));
    assert!(relay.watching());
    assert!(fake.finished());
    // Exactly once, as the frame's own text.
    assert_eq!(*fake.secrets.lock().unwrap(), [SECRET.as_bytes().to_vec()]);
    assert_secret_only_on_its_frame(&fake);
    // The contract is read first; the secret's wait is the one the receipt
    // opened, passed back unchanged; the operation starts last.
    assert_eq!(
        fake.sent(),
        vec![
            target(json!({"action": "operation_contract", "definition_id": CREDENTIAL})),
            target(json!({
                "action": "operation_submit",
                "definition_id": CREDENTIAL,
                "idempotency_key": null,
                "payload_json": "{\"provider\":\"certificate\"}",
                "subject_ref": subject(),
            })),
            target(json!({
                "action": "operation_secret",
                "requirement": requirement(&operation()),
            })),
            target(json!({"action": "operation_start", "operation_id": operation()})),
        ]
    );
}

#[test]
fn a_secret_at_the_frames_bound_is_delivered_and_one_past_it_never_reaches_the_runtime() {
    let wide = "a".repeat(MAXIMUM_SECRET_BYTES);
    let fake = Fake::new(vec![
        reply(credential_contract_reply()),
        reply(awaiting_secret(&operation(), requirement(&operation()))),
        reply(secret_ready()),
        reply(acknowledged(&operation())),
        reply(acknowledged(&operation())),
    ]);
    let mut request = credential_request();
    request["secret"] = json!(wide);
    secret_submit(&fake, &mut OperationRelay::new(), request).unwrap();
    assert_eq!(fake.secrets.lock().unwrap()[0].len(), MAXIMUM_SECRET_BYTES);
    for secret in [json!(format!("{wide}a")), json!(""), json!(7), Value::Null] {
        let fake = Fake::new(Vec::new());
        let mut request = credential_request();
        request["secret"] = secret;
        let refused = secret_submit(&fake, &mut OperationRelay::new(), request);
        assert!(matches!(refused, Err(RelayFailure::Invalid)), "{refused:?}");
        assert!(fake.sent().is_empty());
    }
}

#[test]
fn a_malformed_secret_submission_never_reaches_the_runtime() {
    for (member, value) in [
        ("payload", json!(["provider"])),
        ("payload", Value::Null),
        ("definition_id", json!("")),
        ("subject_ref", json!(7)),
    ] {
        let fake = Fake::new(Vec::new());
        let mut request = credential_request();
        request[member] = value;
        let refused = secret_submit(&fake, &mut OperationRelay::new(), request);
        assert!(matches!(refused, Err(RelayFailure::Invalid)), "{member}");
        assert!(fake.sent().is_empty(), "{member}");
    }
    // The request model refuses what the relay's own checks admit.
    for (member, value) in [
        ("definition_id", json!("Auth.Credential")),
        ("subject_ref", json!("p".repeat(SUBJECT_REF_MAX_CHARS + 1))),
    ] {
        let fake = Fake::new(Vec::new());
        let mut request = credential_request();
        request[member] = value;
        refused_with(
            secret_submit(&fake, &mut OperationRelay::new(), request),
            "unavailable",
        );
        assert!(fake.sent().is_empty(), "{member}");
    }
    let fake = Fake::new(Vec::new());
    let mut request = credential_request();
    request.as_object_mut().unwrap().remove("secret");
    let refused = secret_submit(&fake, &mut OperationRelay::new(), request);
    assert!(matches!(refused, Err(RelayFailure::Invalid)));
    assert!(fake.sent().is_empty());
}

#[test]
fn a_definition_whose_contract_takes_no_secret_is_refused_before_anything_is_submitted() {
    let fake = Fake::new(vec![reply(contract_reply(relay_contract()))]);
    let mut relay = OperationRelay::new();
    let mut request = credential_request();
    request["definition_id"] = json!("ledger.example-review");
    refused_with(
        secret_submit(&fake, &mut relay, request),
        "secret_not_required",
    );
    assert_eq!(
        fake.sent(),
        vec![target(json!({
            "action": "operation_contract",
            "definition_id": "ledger.example-review",
        }))]
    );
    assert!(fake.secrets.lock().unwrap().is_empty());
    assert!(!relay.watching());
}

#[test]
fn a_requirement_that_names_another_submission_is_refused_and_no_secret_is_sent() {
    let other = "e".repeat(64);
    let tampered = |change: &dyn Fn(&mut Value)| {
        let mut wait = requirement(&operation());
        change(&mut wait);
        wait
    };
    for (name, wait) in [
        (
            "another operation",
            tampered(&|wait| wait["identity"]["operation_id"] = json!(other)),
        ),
        (
            "another definition",
            tampered(&|wait| wait["identity"]["definition_id"] = json!("auth.configure")),
        ),
        (
            "another subject",
            tampered(&|wait| wait["identity"]["subject_ref"] = json!("profile:x")),
        ),
        (
            "an undeclared member",
            tampered(&|wait| wait["extra"] = json!(true)),
        ),
        (
            "an undeclared identity member",
            tampered(&|wait| wait["identity"]["extra"] = json!(true)),
        ),
        (
            "no interaction",
            tampered(&|wait| {
                wait.as_object_mut().unwrap().remove("interaction_id");
            }),
        ),
        (
            "a short interaction",
            tampered(&|wait| wait["interaction_id"] = json!("b")),
        ),
        (
            "a fractional revision",
            tampered(&|wait| wait["revision"] = json!(0.5)),
        ),
        (
            "a malformed kind",
            tampered(&|wait| wait["secret_kind"] = json!("Auth Credential")),
        ),
        (
            "an expiry that is no UTC instant",
            tampered(&|wait| wait["expires_at"] = json!("2026-10-27T10:05:00+02:00")),
        ),
        ("no identity", json!({})),
        (
            "none at all",
            // The contract asks for a secret, so a receipt without a wait is not this submission's.
            Value::Null,
        ),
    ] {
        let fake = Fake::new(vec![
            reply(credential_contract_reply()),
            reply(awaiting_secret(&operation(), wait)),
        ]);
        let mut relay = OperationRelay::new();
        let refused = secret_submit(&fake, &mut relay, credential_request());
        assert!(
            !format!("{refused:?}").contains(SECRET_WORD),
            "{name}: the failure names the secret"
        );
        refused_with(refused, "unavailable");
        // The wait was never answered: only the contract and the submission were sent.
        assert_eq!(fake.sent().len(), 2, "{name}");
        assert!(fake.secrets.lock().unwrap().is_empty(), "{name}");
        assert_secret_only_on_its_frame(&fake);
        assert!(!relay.watching(), "{name}");
    }
}

#[test]
fn a_refusal_before_the_runtime_is_ready_sends_no_secret_and_starts_nothing() {
    for (name, ready) in [
        (
            "a refusal of the requirement",
            refuse(Refusal::denied("operation_denied")),
        ),
        (
            "a reply that is not readiness",
            reply(acknowledged(&operation())),
        ),
        ("a lost connection", refuse(Refusal::ConnectionClosed)),
    ] {
        let fake = Fake::new(vec![
            reply(credential_contract_reply()),
            reply(awaiting_secret(&operation(), requirement(&operation()))),
            ready,
        ]);
        let mut relay = OperationRelay::new();
        let refused = secret_submit(&fake, &mut relay, credential_request());
        let code = if name == "a refusal of the requirement" {
            "operation_denied"
        } else {
            "unavailable"
        };
        refused_with(refused, code);
        assert!(fake.secrets.lock().unwrap().is_empty(), "{name}");
        assert_secret_only_on_its_frame(&fake);
        assert!(!relay.watching(), "{name}");
        let actions: Vec<Value> = fake
            .sent()
            .iter()
            .map(|sent| sent["action"].clone())
            .collect();
        assert_eq!(
            actions,
            ["operation_contract", "operation_submit", "operation_secret"],
            "{name}"
        );
    }
}

#[test]
fn an_acknowledgement_of_another_operation_leaves_the_operation_unstarted() {
    let fake = Fake::new(vec![
        reply(credential_contract_reply()),
        reply(awaiting_secret(&operation(), requirement(&operation()))),
        reply(secret_ready()),
        reply(acknowledged(&"e".repeat(64))),
    ]);
    let mut relay = OperationRelay::new();
    refused_with(
        secret_submit(&fake, &mut relay, credential_request()),
        "unavailable",
    );
    // The secret was delivered, so the outcome is unknown, but nothing started.
    assert_eq!(fake.secrets.lock().unwrap().len(), 1);
    assert_eq!(fake.sent().len(), 3);
    assert!(!relay.watching());
    assert_secret_only_on_its_frame(&fake);
}

#[test]
fn a_plain_submission_refuses_a_receipt_that_asks_for_a_secret() {
    let waiting = awaiting_secret(&operation(), requirement(&operation()));
    for (action, member) in [
        ("operation_submit", "payload"),
        ("operation_financial_submit", "input"),
    ] {
        let fake = Fake::new(vec![reply(waiting.clone())]);
        let mut relay = OperationRelay::new();
        let mut request = credential_request();
        request.as_object_mut().unwrap().remove("secret");
        request[member] = request["payload"].take();
        if member == "input" {
            request.as_object_mut().unwrap().remove("payload");
        }
        refused_with(
            handle(&fake, &mut relay, action, request),
            "secret_required",
        );
        // Never started: nothing would deliver the secret it waits for.
        assert_eq!(fake.sent().len(), 1, "{action}");
        assert!(!relay.watching(), "{action}");
    }
}

#[test]
fn a_profile_read_refuses_a_receipt_that_asks_for_a_secret() {
    let fake = Fake::new(vec![
        reply(contract_reply(view())),
        reply(awaiting_secret(&operation(), requirement(&operation()))),
    ]);
    let refused =
        read_profile_language(&fake, &session(), Instant::now() + Duration::from_secs(60));
    assert!(
        matches!(
            refused,
            Err(RelayFailure::Unavailable(Refusal::InvalidFrame))
        ),
        "{refused:?}"
    );
    assert_eq!(fake.sent().len(), 2);
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

    let fake = Fake::new(vec![reply(observed(running(&operation(), &view())))]);
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

fn stopped(condition: &str, refusal: Option<&str>) -> Value {
    observation(
        &operation(),
        &view(),
        "terminal",
        Some(condition),
        (None, refusal),
        json!({"disposition": "none"}),
    )
}

fn error_detail_envelope(projection: Value) -> Value {
    json!({
        "outcome": "success",
        "result_projection_version": 1,
        "result_schema": error_detail_schema(),
        "definition_contract_digest": view()["definition_contract_digest"],
        "projection": projection,
    })
}

#[test]
fn a_stop_its_definition_declares_no_document_for_is_read_as_its_recorded_detail() {
    let detail = error_detail_envelope(json!({
        "detail_version": 1,
        "kind": "registered_error",
        "error_code": "REFUSED_BROWSER_NOT_READY",
        "message_key": "adapters.browser.errors.not_available",
        "context": [],
        "context_entries_omitted": 0,
        "precondition_verdict_json": null,
    }));
    for state in [
        stopped("refused", Some("REFUSED_BROWSER_NOT_READY")),
        stopped("failed", None),
    ] {
        let mut steps = vec![reply(observed(state))];
        steps.extend(pages(&operation(), canonical_json(&detail).as_bytes()));
        let fake = Fake::new(steps);
        let answered = handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_result",
            json!({"operation_id": operation()}),
        )
        .unwrap();
        assert_eq!(answered["document"], detail);
        assert_eq!(
            fake.sent()[1]["result"]["result_schema"],
            json!({
                "schema_id": "operation.error_detail",
                "schema_version": 1,
                "schema_fingerprint": ERROR_DETAIL_SCHEMA_FINGERPRINT,
            })
        );
    }
}

#[test]
fn a_stop_without_a_recorded_detail_has_no_result_and_a_mislabelled_detail_is_refused() {
    let unrecorded = json!({"outcome": "refused", "code": "result_projection_unavailable"});
    let mut steps = vec![reply(observed(stopped("refused", Some("REFUSED_X_Y"))))];
    steps.extend(pages(&operation(), canonical_json(&unrecorded).as_bytes()));
    let fake = Fake::new(steps);
    refused_with(
        handle(
            &fake,
            &mut OperationRelay::new(),
            "operation_result",
            json!({"operation_id": operation()}),
        ),
        "no_result",
    );

    let mislabelled = result_envelope(&view(), json!({"kind": "registered_error"}));
    let mut steps = vec![reply(observed(stopped("refused", Some("REFUSED_X_Y"))))];
    steps.extend(pages(&operation(), canonical_json(&mislabelled).as_bytes()));
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

    let cancelled = stopped("cancelled", None);
    let fake = Fake::new(vec![reply(observed(cancelled))]);
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
            target(json!({"action": "operation_contract", "definition_id": "user-profile.view"})),
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
    let failure = read_profile_language(&fake, &session(), started + Duration::from_millis(400));
    assert!(started.elapsed() >= Duration::from_millis(400));
    assert!(
        matches!(failure, Err(RelayFailure::Unavailable(Refusal::Timeout))),
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
        match read_profile_language(&fake, &session(), Instant::now() + Duration::from_secs(60)) {
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
        read_profile_language(&fake, &session(), Instant::now() + Duration::from_secs(60)).unwrap();
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
