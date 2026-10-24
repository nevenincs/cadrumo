//! The held person's registered-operation relay, shared by the host modules
//! that submit through it: submission, observation until a projection
//! settles, the result read, and the closed failure codes the window maps to
//! its own words. No operation's meaning lives here.
use crate::agent::person::{HeldPerson, PersonEvent};
use cadrumo_application::error::application::ApplicationError;
use serde::Serialize;
use serde_json::{Value, json};
use std::{sync::Mutex, time::Duration};

/// How long a submitted operation is followed before its outcome is unknown.
pub(crate) const SETTLE_LIMIT: Duration = Duration::from_secs(90);

#[derive(Debug, Serialize)]
pub struct Failure {
    pub(crate) code: &'static str,
    pub(crate) operation_id: Option<String>,
    /// The runtime's closed refusal code, where one was given.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) reason: Option<String>,
}
impl Failure {
    pub(crate) fn new(code: &'static str) -> Self {
        Self {
            code,
            operation_id: None,
            reason: None,
        }
    }
}
impl From<ApplicationError> for Failure {
    fn from(_: ApplicationError) -> Self {
        Self::new("unavailable")
    }
}
pub(crate) type Result<T> = std::result::Result<T, Failure>;
pub(crate) fn lock<T>(value: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|e| e.into_inner())
}
pub(crate) fn protocol() -> Failure {
    Failure::new("unavailable")
}

pub(crate) async fn identity(person: &HeldPerson) -> Result<Value> {
    let person = person.clone();
    // The same mutex is held by blocking IPC exchanges. Never wait on it
    // on a Tokio executor thread: that can also starve the read's timer.
    Ok(super::blocking(move || Ok(lock(&person).identity.clone())).await?)
}
pub(crate) async fn profile_of(person: &HeldPerson) -> Result<String> {
    Ok(identity(person).await?["profile_id"]
        .as_str()
        .ok_or_else(protocol)?
        .to_owned())
}
pub(crate) async fn call(person: &HeldPerson, request: Value) -> Result<Value> {
    let person = person.clone();
    Ok(super::blocking(move || lock(&person).exchange(request)).await?)
}

/// A request whose text is overwritten when it is dropped, sent or not. Its
/// value can be borrowed but never moved out, so no unwiped copy outlives it.
pub(crate) struct Wiped(pub(crate) Value);
/// Says that a request is there, never what it holds.
impl std::fmt::Debug for Wiped {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str("Wiped(..)")
    }
}
impl Drop for Wiped {
    fn drop(&mut self) {
        cadrumo_application::person_operations::wipe(&mut self.0);
    }
}

/// The JSON object a command's raw body carries, for private input that
/// never travels as an ordinary argument. The body is read from a copy that
/// is overwritten once parsed, and anything but an object within `limit`
/// bytes is refused.
pub(crate) fn wiped_body(body: &tauri::ipc::InvokeBody, limit: usize) -> Result<Wiped> {
    let tauri::ipc::InvokeBody::Raw(bytes) = body else {
        return Err(Failure::new("invalid"));
    };
    // A derived reader also takes an array of fields: only an object is read.
    if bytes.len() > limit || bytes.trim_ascii_start().first() != Some(&b'{') {
        return Err(Failure::new("invalid"));
    }
    let copied = zeroize::Zeroizing::new(bytes.to_vec());
    let parsed = serde_json::from_slice(&copied).map_err(|_| Failure::new("invalid"))?;
    let read = Wiped(parsed);
    if !read.0.is_object() {
        return Err(Failure::new("invalid"));
    }
    Ok(read)
}
pub(crate) async fn call_wiping(person: &HeldPerson, request: Wiped) -> Result<Value> {
    let person = person.clone();
    Ok(super::blocking(move || {
        let mut request = request;
        lock(&person).exchange_wiping(&mut request.0)
    })
    .await?)
}

/// One operation this host submitted, as the relay names it.
pub(crate) struct Relayed<'a> {
    pub(crate) person: &'a HeldPerson,
    pub(crate) operation: String,
    pub(crate) definition: &'a str,
    pub(crate) subject: String,
}

pub(crate) fn subject(profile: &str) -> String {
    format!("profile:{profile}")
}

/// Submits `payload` for `definition` and answers the operation id. A refused
/// submission is `refused` with the relay's code; one whose answer was lost
/// is `unknown` for a mutation, which may have been admitted.
pub(crate) async fn submit(
    person: &HeldPerson,
    definition: &str,
    subject: &str,
    payload: Value,
    mutation: bool,
) -> Result<String> {
    let submitted = call(
        person,
        json!({"action":"operation_submit", "definition_id":definition,
        "subject_ref":subject, "payload":payload}),
    )
    .await;
    accepted(submitted, mutation)
}

/// The submission request for `payload`, which is moved into it, not copied.
pub(crate) fn submission(definition: &str, subject: &str, payload: Value) -> Wiped {
    let mut request = Wiped(
        json!({"action":"operation_submit", "definition_id":definition,
        "subject_ref":subject, "payload":null}),
    );
    request.0["payload"] = payload;
    request
}

/// The relay ends the held session for a payload over its own bound, so the
/// host refuses one well before it: number spellings can differ between the
/// two JSON encoders by a character or two.
const PAYLOAD_HEADROOM: usize = 256;
/// The longest payload, in bytes of compact JSON, the host sends: the
/// document the native relay carries, less the headroom.
pub(crate) const PAYLOAD_LIMIT: usize =
    cadrumo_application::person_operations::PROJECTION_DOCUMENT_MAX_BYTES - PAYLOAD_HEADROOM;

/// Refuses a submission the relay could not take, before anything is written
/// to it. A request that is too large is the window's to make smaller; the
/// host never splits one.
pub(crate) fn admit_size(document: &Value) -> Result<()> {
    let fits_payload = crate::agent::person::encoded(&document["payload"]).bytes <= PAYLOAD_LIMIT;
    if !fits_payload || !crate::agent::person::request_fits(document) {
        return Err(Failure::new("too_large"));
    }
    Ok(())
}

/// As [`submit`], for a request built by [`submission`]: its text is
/// overwritten once it is sent.
pub(crate) async fn submit_wiping(
    person: &HeldPerson,
    request: Wiped,
    mutation: bool,
) -> Result<String> {
    accepted(call_wiping(person, request).await, mutation)
}

fn accepted(submitted: Result<Value>, mutation: bool) -> Result<String> {
    let lost = || Failure::new(if mutation { "unknown" } else { "unavailable" });
    let submitted = submitted.map_err(|_| lost())?;
    if submitted["kind"] == "operation_refused" {
        // The relay answers "unavailable" when the runtime's reply was lost
        // after the submission was written: a mutation may have been taken.
        if mutation && submitted["code"] == "unavailable" {
            return Err(lost());
        }
        let mut refused = Failure::new("refused");
        refused.reason = submitted["code"].as_str().map(str::to_owned);
        return Err(refused);
    }
    Ok(submitted["operation_id"]
        .as_str()
        .filter(|id| super::setup::wire::is_hex64(id))
        .ok_or_else(lost)?
        .to_owned())
}

/// The operation's current public projection, checked to be the one submitted.
pub(crate) async fn observe(relayed: &Relayed<'_>) -> Result<Value> {
    let reply = call(
        relayed.person,
        json!({"action":"operation_observe", "operation_id":relayed.operation, "after_cursor":0}),
    )
    .await?;
    let p = &reply["observation"]["projection"];
    if reply["kind"] != "operation_observed"
        || p["operation_id"] != relayed.operation
        || p["definition_id"] != relayed.definition
        || p["subject_ref"] != relayed.subject
    {
        return Err(protocol());
    }
    Ok(p.clone())
}

/// Observes until the operation is terminal or `stop` accepts its projection,
/// waking on the runtime's change cue rather than a timer. Subscribe `events`
/// before submitting: the observe request installs the watch before answering,
/// so a fast settlement cannot lose its wake.
pub(crate) async fn follow(
    events: &mut tokio::sync::broadcast::Receiver<PersonEvent>,
    relayed: &Relayed<'_>,
    stop: impl Fn(&Value) -> bool,
) -> Result<Value> {
    loop {
        let projection = observe(relayed).await?;
        if projection["lifecycle"] == "terminal" || stop(&projection) {
            return Ok(projection);
        }
        loop {
            match events.recv().await {
                Ok(PersonEvent::OperationChanged)
                | Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => break,
                Ok(PersonEvent::Retired)
                | Err(tokio::sync::broadcast::error::RecvError::Closed) => return Err(protocol()),
                _ => {}
            }
        }
    }
}

/// The settled operation's result document, or its declared refusal detail.
pub(crate) async fn result(relayed: &Relayed<'_>) -> Result<Value> {
    let result = call(
        relayed.person,
        json!({"action":"operation_result", "operation_id":relayed.operation}),
    )
    .await?;
    if result["kind"] != "operation_result"
        || result["operation_id"] != relayed.operation
        || result["definition_id"] != relayed.definition
    {
        return Err(protocol());
    }
    Ok(result["document"].clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_raw_body_is_read_only_as_one_bounded_object() {
        let raw = |text: &str| tauri::ipc::InvokeBody::Raw(text.as_bytes().to_vec());
        let read = wiped_body(&raw(r#" {"amount":1234.56,"iban":"ES00"}"#), 64).unwrap();
        assert_eq!(read.0["amount"], 1234.56);
        for refused in [
            raw(r#"["amount",1]"#),
            raw("{"),
            raw(&format!(r#"{{"pad":"{}"}}"#, "a".repeat(64))),
            tauri::ipc::InvokeBody::Json(json!({"amount": 1})),
        ] {
            assert_eq!(wiped_body(&refused, 64).unwrap_err().code, "invalid");
        }
        let mut read = read;
        cadrumo_application::person_operations::wipe(&mut read.0);
        assert_eq!(read.0, json!({"amount": 0, "iban": ""}));
    }

    #[test]
    fn a_request_the_relay_cannot_take_is_refused_before_it_is_written() {
        let request = |payload: Value| {
            submission(
                "family.example",
                "profile:00000000-0000-4000-8000-000000000000",
                payload,
            )
        };
        let near = "a".repeat(PAYLOAD_LIMIT - r#"{"csv_text":""}"#.len());
        assert!(admit_size(&request(json!({ "csv_text": near })).0).is_ok());
        let over = format!("{near}a");
        assert_eq!(
            admit_size(&request(json!({ "csv_text": over })).0)
                .unwrap_err()
                .code,
            "too_large"
        );
        // The bound counts bytes: each of these characters takes three.
        let wide = "\u{20ac}".repeat(near.len() / 3 + 1);
        assert_eq!(
            admit_size(&request(json!({ "csv_text": wide })).0)
                .unwrap_err()
                .code,
            "too_large"
        );
    }
}
