//! The person's session held on the window's own runtime connection.
//!
//! The runtime's `session hold` command once carried these requests for the
//! window as a Python child. The same requests run here on the connection the
//! window signed in or resumed on, and answer in that command's documents, so
//! every consumer keeps one protocol: the reply each request names, a
//! `session_refused` with the hold's code, and `session_retired` once the
//! runtime ends the session. A refusal the hold ended on ends this session
//! too: the connection closes, and the runtime ends the session it carried.
use super::{Bridge, EventSlot, PersonEvent, SignedOut, failed};
use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    person_operations::{
        OperationRelay, PROJECTION_DOCUMENT_MAX_BYTES, ProfileLanguage, RELAY_ACTION_KEYS,
        RelayFailure, read_profile_language, set_profile_language,
    },
    runtime_client::{Admitted, Event, Pushed, Refusal, SessionExchange, human_sign_out},
};
use serde_json::{Map, Value, json};
use std::{
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

/// The runtime's bound on one exchange, and on each relayed action.
const EXCHANGE: Duration = Duration::from_secs(120);
/// The runtime's bound on admitting a service under the person's session.
const ADMISSION: Duration = Duration::from_secs(10);
/// The longest reply: the longest document the relay assembles, and one
/// runtime frame for the reply around it.
const REPLY_LIMIT: usize = PROJECTION_DOCUMENT_MAX_BYTES + 64 * 1024;
/// The denial of an uncertain OS observation: it refuses the request but keeps the session.
const OS_SESSION_UNAVAILABLE: &str = "os_session_unavailable";

/// What the event router and the requests share.
#[derive(Default)]
struct Shared {
    /// The window asked for pushes: each cue becomes a person event.
    observing: AtomicBool,
    /// An operation this session relayed is unsettled, so its cues matter.
    watching: AtomicBool,
    /// The language changed since it was last read.
    language_dirty: AtomicBool,
    /// The runtime ended this session, or the connection ended.
    retired: AtomicBool,
    /// The window gave the session up itself: its connection's end is no retirement.
    released: AtomicBool,
}

pub(super) struct NativeSession {
    connection: Option<Arc<dyn SessionExchange>>,
    admitted: Admitted,
    shared: Arc<Shared>,
    relay: OperationRelay,
    language: Option<ProfileLanguage>,
}

impl NativeSession {
    /// Holds `admitted` on `connection` and routes into `events` the pushes
    /// `pushed` receives, subscribed before the sign-in so none in between is
    /// lost; returns the session and its held line.
    pub(super) fn start(
        connection: Arc<dyn SessionExchange>,
        pushed: mpsc::Receiver<Pushed>,
        admitted: Admitted,
        persisted: Option<bool>,
        events: EventSlot,
    ) -> Result<(Self, Value)> {
        let shared = Arc::new(Shared::default());
        shared.language_dirty.store(true, Ordering::Release);
        let (routed, profile, session, closing) = (
            shared.clone(),
            admitted.profile_id.clone(),
            admitted.session_id.clone(),
            Arc::downgrade(&connection),
        );
        thread::Builder::new()
            .name("person-session-events".into())
            .spawn(move || route(&pushed, &profile, &session, &routed, &events, &closing))
            .map_err(|error| failed("person_events_spawn").caused_by(error))?;
        let mut identity = json!({
            "kind": "session_held",
            "profile_id": admitted.profile_id,
            "session_id": admitted.session_id,
            "runtime_boot_id": admitted.runtime_boot_id,
            "connection_id": admitted.connection_id,
        });
        if let Some(persisted) = persisted {
            identity["session_persisted"] = json!(persisted);
        }
        Ok((
            Self {
                connection: Some(connection),
                admitted,
                shared,
                relay: OperationRelay::new(),
                language: None,
            },
            identity,
        ))
    }

    fn connection(&self) -> Result<&Arc<dyn SessionExchange>> {
        self.connection
            .as_ref()
            .ok_or_else(|| failed("person_bridge_closed"))
    }

    /// The runtime request `action` names for this session, with `fields`.
    fn request(&self, action: &str, request_id: &str, fields: Value) -> Value {
        let mut request = json!({
            "action": action,
            "request_id": request_id,
            "profile_id": self.admitted.profile_id,
            "session_id": self.admitted.session_id,
        });
        if let (Some(request), Value::Object(fields)) = (request.as_object_mut(), fields) {
            request.extend(fields);
        }
        request
    }

    fn ask(
        &self,
        request: &Value,
        within: Duration,
    ) -> std::result::Result<Map<String, Value>, Refusal> {
        let connection = self.connection.as_ref().ok_or(Refusal::ConnectionClosed)?;
        connection.exchange(request, Instant::now() + within)
    }

    /// The reply a request the runtime answered for this session carries:
    /// the same document, naming the request.
    fn stamped(&self, request_id: &str, fields: Map<String, Value>) -> Value {
        let mut reply = json!({
            "request_id": request_id,
            "profile_id": self.admitted.profile_id,
            "session_id": self.admitted.session_id,
            "runtime_boot_id": self.admitted.runtime_boot_id,
            "connection_id": self.admitted.connection_id,
        });
        if let Some(reply) = reply.as_object_mut() {
            reply.extend(fields);
        }
        reply
    }

    /// The hold's refusal of `request_id`; with `ends`, the session ends with it.
    fn refuse(&mut self, request_id: &str, code: &str, cause: Option<&str>, ends: bool) -> Value {
        if ends {
            self.end();
        }
        let mut refused =
            json!({"kind": "session_refused", "request_id": request_id, "code": code});
        if let Some(cause) = cause {
            // The protocol names the runtime's code as the report's reason, never a message.
            refused["report"] = json!({"status": "error", "error": {"context": {"reason": cause}}});
        }
        refused
    }

    /// What the hold answered for a request whose runtime work failed: the
    /// session's loss when the runtime ended it, otherwise an ending refusal.
    fn failed_request(&mut self, request_id: &str, refusal: &Refusal) -> Value {
        if self.shared.retired.load(Ordering::Acquire) {
            return self.retired();
        }
        self.refuse(request_id, "unavailable", Some(refusal.code()), true)
    }

    fn retired(&mut self) -> Value {
        self.end();
        json!({"kind": "session_retired", "profile_id": self.admitted.profile_id})
    }

    fn end(&mut self) {
        self.shared.released.store(true, Ordering::Release);
        // The last owner of the connection closes it; the runtime ends its session.
        self.connection = None;
    }

    /// A status the runtime answered must be this session's own.
    fn own_status(&self, reply: &Map<String, Value>) -> bool {
        let status = &reply.get("status").cloned().unwrap_or(Value::Null);
        reply.get("kind").and_then(Value::as_str) == Some("profile_status")
            && (status["session_id"].is_null() || status["session_id"] == self.admitted.session_id)
            && (status["profile_id"].is_null() || status["profile_id"] == self.admitted.profile_id)
    }

    fn answer(&mut self, request: &Value) -> Value {
        let request_id = request["request_id"]
            .as_str()
            .unwrap_or_default()
            .to_owned();
        if self.shared.retired.load(Ordering::Acquire) {
            return self.retired();
        }
        let action = request["action"].as_str().unwrap_or_default();
        let keys: &[&str] = match action {
            "service_admission" => &["recipient_connection_id", "service_id"],
            "attendance_decision" => &["attendance_id", "approve"],
            "language_set" => &["language"],
            "present_destination" => &["destination", "params"],
            "observe_events"
            | "status"
            | "activity"
            | "attendance_inventory"
            | "language_read"
            | "language_observe" => &[],
            _ => match RELAY_ACTION_KEYS
                .iter()
                .find(|(relayed, _)| *relayed == action)
            {
                Some((_, keys)) => keys,
                None => return self.refuse(&request_id, "invalid", None, true),
            },
        };
        let named = request.as_object().is_some_and(|fields| {
            fields.len() == 2 + keys.len()
                && ["request_id", "action"]
                    .iter()
                    .chain(keys)
                    .all(|key| fields.contains_key(*key))
        });
        if !named {
            return self.refuse(&request_id, "invalid", None, true);
        }
        match action {
            "observe_events" => {
                // From here on each push is also an event of its own.
                self.shared.observing.store(true, Ordering::Release);
                json!({
                    "kind": "events_observed",
                    "request_id": request_id,
                    "runtime_boot_id": self.admitted.runtime_boot_id,
                    "connection_id": self.admitted.connection_id,
                })
            }
            "status" => self.status(&request_id),
            "activity" => self.activity(&request_id),
            "service_admission" => self.service_admission(&request_id, request),
            "attendance_inventory" => {
                let asked = self.request(action, &request_id, json!({}));
                self.passed_through(&request_id, &asked, EXCHANGE)
            }
            "attendance_decision" => {
                let (Some(attendance_id), Some(approve)) = (
                    request["attendance_id"].as_str().filter(|id| is_uuid(id)),
                    request["approve"].as_bool(),
                ) else {
                    return self.refuse(&request_id, "invalid", None, true);
                };
                let asked = self.request(
                    action,
                    &request_id,
                    json!({"attendance_id": attendance_id, "approve": approve}),
                );
                self.passed_through(&request_id, &asked, EXCHANGE)
            }
            "present_destination" => self.present(&request_id, request),
            "language_read" | "language_observe" | "language_set" => {
                self.language(&request_id, action, request)
            }
            _ => self.relayed(&request_id, action, request),
        }
    }

    fn status(&mut self, request_id: &str) -> Value {
        let asked = self.request("session_status", request_id, json!({}));
        match self.ask(&asked, EXCHANGE) {
            Ok(reply) if self.own_status(&reply) => Value::Object(reply),
            Ok(_) => self.failed_request(request_id, &Refusal::InvalidFrame),
            Err(refusal) => self.failed_request(request_id, &refusal),
        }
    }

    fn activity(&mut self, request_id: &str) -> Value {
        let asked = self.request("session_activity", request_id, json!({}));
        let denial = match self.ask(&asked, EXCHANGE) {
            Ok(reply) if self.own_status(&reply) => match reply["status"]["denial"].as_str() {
                None => return Value::Object(reply),
                Some(denial) => denial.to_owned(),
            },
            Ok(_) => return self.failed_request(request_id, &Refusal::InvalidFrame),
            Err(Refusal::Denied { code, .. }) => code,
            Err(refusal) => return self.failed_request(request_id, &refusal),
        };
        self.denied(request_id, &denial)
    }

    /// The hold's answer to a request the runtime denied for the person: an
    /// uncertain OS observation keeps the session, anything else ends it.
    fn denied(&mut self, request_id: &str, denial: &str) -> Value {
        if denial == OS_SESSION_UNAVAILABLE {
            return self.refuse(request_id, "unavailable", None, false);
        }
        if self.shared.retired.load(Ordering::Acquire) {
            return self.retired();
        }
        self.refuse(request_id, "inactive", None, true)
    }

    fn service_admission(&mut self, request_id: &str, request: &Value) -> Value {
        let (Some(recipient), Some(service_id)) = (
            request["recipient_connection_id"]
                .as_str()
                .filter(|id| is_uuid(id)),
            request["service_id"].as_str(),
        ) else {
            return self.refuse(request_id, "invalid", None, true);
        };
        let checked = self.request(
            "session_status",
            &cadrumo_application::runtime_client::request_id(),
            json!({}),
        );
        let current = match self.ask(&checked, EXCHANGE) {
            Ok(reply) if self.own_status(&reply) => reply,
            Ok(_) => return self.failed_request(request_id, &Refusal::InvalidFrame),
            Err(refusal) => return self.failed_request(request_id, &refusal),
        };
        match current["status"]["denial"].as_str() {
            // An uncertain OS observation refuses this admission but keeps the held sign-in.
            Some(OS_SESSION_UNAVAILABLE) => {
                return self.refuse(request_id, "unavailable", None, false);
            }
            Some(_) => return self.refuse(request_id, "inactive", None, true),
            None if current["status"]["session_id"].is_null() => {
                return self.refuse(request_id, "inactive", None, true);
            }
            None => {}
        }
        let asked = self.request(
            "service_admission",
            request_id,
            json!({"recipient_connection_id": recipient, "service_id": service_id}),
        );
        self.passed_through(request_id, &asked, ADMISSION)
    }

    /// The runtime's own reply to `asked`, which names this request.
    fn passed_through(&mut self, request_id: &str, asked: &Value, within: Duration) -> Value {
        match self.ask(asked, within) {
            Ok(reply) => Value::Object(reply),
            Err(refusal) => self.failed_request(request_id, &refusal),
        }
    }

    fn present(&mut self, request_id: &str, request: &Value) -> Value {
        let params = &request["params"];
        let Some(destination) = request["destination"]
            .as_str()
            .filter(|destination| crate::shell::presentation::admitted_value(destination, params))
        else {
            return self.refuse(request_id, "invalid", None, true);
        };
        let asked = self.request(
            "present_destination",
            request_id,
            json!({"destination": destination, "params": params}),
        );
        let reply = match self.ask(&asked, EXCHANGE) {
            Ok(reply) => reply,
            Err(Refusal::Denied { code, .. }) => return self.denied(request_id, &code),
            Err(refusal) => return self.failed_request(request_id, &refusal),
        };
        let delivered = reply.get("delivered").and_then(Value::as_u64);
        if reply.get("kind").and_then(Value::as_str) != Some("presentation_delivered")
            || reply.get("destination").and_then(Value::as_str) != Some(destination)
            || reply.get("params") != Some(params)
            || delivered.is_none()
        {
            return self.failed_request(request_id, &Refusal::InvalidFrame);
        }
        let mut fields = Map::new();
        fields.insert("kind".into(), json!("destination_presented"));
        fields.insert("destination".into(), json!(destination));
        fields.insert("params".into(), params.clone());
        fields.insert("delivered".into(), json!(delivered));
        self.stamped(request_id, fields)
    }

    fn language(&mut self, request_id: &str, action: &str, request: &Value) -> Value {
        let wanted = match action {
            "language_set" => match request["language"]
                .as_str()
                .filter(|language| crate::shell::language::supported(language))
            {
                Some(language) => Some(language.to_owned()),
                None => return self.refuse(request_id, "invalid", None, true),
            },
            _ => None,
        };
        let cached = action == "language_observe"
            && self.language.is_some()
            && !self.shared.language_dirty.load(Ordering::Acquire);
        if !cached {
            // Cleared before reading, so a change meanwhile leaves it dirty.
            self.shared.language_dirty.store(false, Ordering::Release);
            let read = match self.connection() {
                Ok(connection) => {
                    let connection = connection.clone();
                    let deadline = Instant::now() + EXCHANGE;
                    match &wanted {
                        Some(language) => set_profile_language(
                            connection.as_ref(),
                            &self.admitted,
                            language,
                            deadline,
                        ),
                        None => {
                            read_profile_language(connection.as_ref(), &self.admitted, deadline)
                        }
                    }
                }
                Err(_) => Err(RelayFailure::Unavailable(Refusal::ConnectionClosed)),
            };
            match read {
                Ok(language) => self.language = Some(language),
                Err(failure) => {
                    self.shared.language_dirty.store(true, Ordering::Release);
                    return self.relay_failed(request_id, failure);
                }
            }
        }
        let (language, record_revision) = self.language.as_ref().map_or((None, 0), |read| {
            (read.language.clone(), read.record_revision)
        });
        let mut fields = Map::new();
        fields.insert("kind".into(), json!("profile_language"));
        fields.insert("language".into(), json!(language));
        fields.insert("record_revision".into(), json!(record_revision));
        self.stamped(request_id, fields)
    }

    fn relayed(&mut self, request_id: &str, action: &str, request: &Value) -> Value {
        let (Ok(connection), Some(fields)) = (self.connection().cloned(), request.as_object())
        else {
            return self.refuse(request_id, "unavailable", None, true);
        };
        let handled = self
            .relay
            .handle(connection.as_ref(), &self.admitted, action, fields);
        self.shared
            .watching
            .store(self.relay.watching(), Ordering::Release);
        match handled {
            Ok(fields) => self.stamped(request_id, fields),
            Err(RelayFailure::Refused {
                code,
                holder_operation_id,
            }) => {
                // A relay refusal is the operation's answer; the session stays held.
                let mut fields = Map::new();
                fields.insert("kind".into(), json!("operation_refused"));
                fields.insert("code".into(), json!(code));
                fields.insert("holder_operation_id".into(), json!(holder_operation_id));
                self.stamped(request_id, fields)
            }
            Err(failure) => self.relay_failed(request_id, failure),
        }
    }

    /// The hold's ending refusal for a relayed or language request that failed.
    fn relay_failed(&mut self, request_id: &str, failure: RelayFailure) -> Value {
        match failure {
            RelayFailure::Invalid => self.refuse(request_id, "invalid", None, true),
            RelayFailure::Unavailable(refusal) => self.failed_request(request_id, &refusal),
            RelayFailure::Refused { code, .. } => {
                if self.shared.retired.load(Ordering::Acquire) {
                    return self.retired();
                }
                self.refuse(request_id, "unavailable", Some(&code), true)
            }
        }
    }
}

impl Drop for NativeSession {
    fn drop(&mut self) {
        self.end();
    }
}

impl Bridge for NativeSession {
    fn exchange(&mut self, request: &Value) -> Result<Value> {
        if self.connection.is_none() {
            return Err(failed("person_bridge_closed"));
        }
        let reply = self.answer(request);
        // No pipe bounds a reply any more; the relay's own document bound does.
        if super::encoded(&reply).bytes > REPLY_LIMIT {
            self.end();
            return Err(failed("person_reply_too_large"));
        }
        Ok(reply)
    }

    fn is_open(&mut self) -> bool {
        self.connection.is_some() && !self.shared.retired.load(Ordering::Acquire)
    }

    fn fence(&mut self) {
        self.end();
    }

    fn sign_out(&mut self) -> Result<SignedOut> {
        let connection = self.connection()?.clone();
        let out = human_sign_out(
            connection.as_ref(),
            &self.admitted,
            Instant::now() + EXCHANGE,
        )
        .map_err(|refusal| {
            ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                .with_reason("person_sign_out_refused")
                .caused_by(refusal)
        })?;
        Ok(SignedOut {
            automation_enabled: out.automation_enabled,
            automation_access_remains: out.automation_access_remains,
        })
    }
}

fn is_uuid(text: &str) -> bool {
    crate::shell::agent_access::wire::is_uuid(text)
}

/// Routes the runtime's pushes for the held session into person events, as
/// the hold did: cues only for this session, an operation's cue only while
/// one it relayed is unsettled, and each only once the window observes.
fn route(
    pushed: &mpsc::Receiver<Pushed>,
    profile: &str,
    session: &str,
    shared: &Shared,
    events: &EventSlot,
    connection: &std::sync::Weak<dyn SessionExchange>,
) {
    // A push the runtime could not have meant for this session ends the
    // connection, and the runtime ends the session it carried.
    let violated = || {
        if let Some(connection) = connection.upgrade() {
            connection.close();
        }
    };
    let send = |event: PersonEvent| {
        if let Some(events) = events.lock().unwrap_or_else(|e| e.into_inner()).as_ref() {
            let _ = events.send(event);
        }
    };
    for Pushed {
        event,
        profile_id,
        session_id,
    } in pushed
    {
        let own = session_id.as_deref() == Some(session);
        let cue = match event {
            Event::SignInChanged | Event::LifecycleNotice => continue,
            Event::Disconnected => break,
            // A frontend never holds a service lease, and a push for another
            // profile could not have been meant for it: the connection is not
            // the one the window signed in on.
            _ if profile_id.as_deref() != Some(profile) => {
                violated();
                break;
            }
            Event::ServiceLeaseChanged | Event::ModelRunRequested => {
                violated();
                break;
            }
            Event::SessionRetired { .. } if own => break,
            Event::SessionRetired { .. }
            | Event::AttendanceAnswered
            | Event::PresentationRequested { .. } => continue,
            Event::LanguageChanged if own => {
                shared.language_dirty.store(true, Ordering::Release);
                PersonEvent::LanguageChanged
            }
            Event::RecordsChanged if own => PersonEvent::RecordsChanged,
            Event::AttendanceChanged if own => PersonEvent::AttendanceChanged,
            Event::OperationChanged if own && shared.watching.load(Ordering::Acquire) => {
                PersonEvent::OperationChanged
            }
            _ => continue,
        };
        if shared.observing.load(Ordering::Acquire) {
            send(cue);
        }
    }
    shared.retired.store(true, Ordering::Release);
    // As when the hold exited: a session the window gave up retires nobody
    // else's waits on the shared events.
    if !shared.released.load(Ordering::Acquire) {
        send(PersonEvent::Retired);
    }
}

#[cfg(test)]
mod tests {
    use super::super::{Person, PersonEvent};
    use super::*;
    use std::{collections::VecDeque, sync::Mutex};
    use tokio::sync::broadcast::{self, error::TryRecvError};

    const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";
    const SESSION: &str = "22345678-1234-4234-8234-123456789abc";
    const BOOT: &str = "32345678-1234-4234-8234-123456789abc";
    const CONNECTION: &str = "42345678-1234-4234-8234-123456789abc";
    const OTHER: &str = "52345678-1234-4234-8234-123456789abc";
    const OPERATION: &str = "ab00000000000000000000000000000000000000000000000000000000000001";

    /// Driven by the Python runtime lifecycle test while its MCP invocation
    /// and attendance parent remain live. No scripted SessionExchange is used.
    #[test]
    fn native_setup_review_runtime_fixture() {
        use cadrumo_application::runtime_client::{Cohort, Connection, Endpoint, Frontend};
        use std::{fs, path::Path};

        let Some(config_path) = std::env::var_os("CADRUMO_DESKTOP_REVIEW_RUNTIME_FIXTURE") else {
            return;
        };
        let bytes = fs::read(config_path).unwrap();
        assert!(bytes.len() <= 16 * 1024);
        let config: Value = serde_json::from_slice(&bytes).unwrap();
        let field = |name: &str| config[name].as_str().unwrap();
        let endpoint = Endpoint::of(Path::new(field("storage_root"))).unwrap();
        let deadline = Instant::now() + Duration::from_secs(120);
        let connection = Arc::new(
            Connection::open(
                &endpoint,
                &Cohort {
                    product_version: "test".into(),
                    authority_generation: None,
                },
                deadline,
            )
            .unwrap(),
        );
        let pushed = connection.subscribe_scoped();
        let admitted = connection
            .login_password(
                field("profile_id"),
                Frontend::Desktop,
                field("password").as_bytes(),
                false,
                deadline,
            )
            .unwrap();
        let (mut session, identity) = NativeSession::start(
            connection,
            pushed,
            admitted,
            None,
            Arc::new(Mutex::new(None)),
        )
        .unwrap();
        let operation = field("operation_id");
        let claimable = |session: &mut NativeSession, id: &str| {
            let listed = session
                .exchange(&json!({"request_id": id, "action": "operation_review_claimable"}))
                .unwrap();
            assert_eq!(listed["kind"], "operation_reviews_claimable", "{listed}");
            listed["operation_ids"].clone()
        };
        let listed_before = claimable(&mut session, "fixture-list-before");
        let review = session.exchange(&json!({
            "request_id": "fixture-review", "action": "operation_review", "operation_id": operation,
        })).unwrap();
        assert_eq!(review["kind"], "operation_review", "{review}");
        assert_eq!(review["operation_id"], operation);
        assert!(review["document"].is_object());
        let claimed = session.exchange(&json!({
            "request_id": "fixture-claim", "action": "operation_review_claim", "operation_id": operation,
            "interaction_id": review["interaction_id"], "revision": review["revision"],
            "review_digest": review["review_digest"],
        })).unwrap();
        assert_eq!(claimed["kind"], "operation_review_claimed", "{claimed}");
        let listed_claimed = claimable(&mut session, "fixture-list-claimed");
        assert_eq!(claimed["interaction_id"], review["interaction_id"]);
        assert_eq!(
            claimed["revision"].as_u64().unwrap(),
            review["revision"].as_u64().unwrap() + 1
        );
        let responded = session.exchange(&json!({
            "request_id": "fixture-reject", "action": "operation_respond", "operation_id": operation,
            "interaction_id": claimed["interaction_id"], "revision": claimed["revision"],
            "review_digest": claimed["review_digest"], "decision": "reject",
        })).unwrap();
        assert_eq!(responded["kind"], "operation_responded", "{responded}");
        assert_eq!(responded["decision"], "reject");
        // Keep the verified claimant alive until the real supervisor settles.
        loop {
            assert!(Instant::now() < deadline, "setup did not settle");
            let observed = session
                .exchange(&json!({
                    "request_id": "fixture-observe", "action": "operation_observe",
                    "operation_id": operation, "after_cursor": 0,
                }))
                .unwrap();
            assert_eq!(observed["kind"], "operation_observed", "{observed}");
            if observed["observation"]["projection"]["lifecycle"] == "terminal" {
                break;
            }
            thread::sleep(Duration::from_millis(20));
        }
        let listed_after = claimable(&mut session, "fixture-list-after");
        fs::write(
            field("output_file"),
            serde_json::to_vec(&json!({
                "identity": identity, "review": review, "claimed": claimed, "responded": responded,
                "listed_before": listed_before, "listed_claimed": listed_claimed,
                "listed_after": listed_after,
            }))
            .unwrap(),
        )
        .unwrap();
    }

    /// What the fake runtime answers to the next request.
    enum Answer {
        Reply(Value),
        Denied(&'static str),
        Closed,
    }

    /// A runtime connection that answers from a script and records each request.
    #[derive(Default)]
    struct Runtime {
        script: Mutex<VecDeque<Answer>>,
        asked: Mutex<Vec<Value>>,
        /// What was written on the secret frame, each only after the runtime
        /// answered a request for it with `secret_ready`.
        secrets: Mutex<Vec<Vec<u8>>>,
        pushes: Mutex<Option<mpsc::Sender<Pushed>>>,
        closed: AtomicBool,
    }

    impl Runtime {
        fn answering(script: impl IntoIterator<Item = Answer>) -> Arc<Self> {
            Arc::new(Self {
                script: Mutex::new(script.into_iter().collect()),
                ..Self::default()
            })
        }

        fn asked(&self) -> Vec<Value> {
            self.asked.lock().unwrap().clone()
        }

        fn push(&self, event: Event, session: &str) {
            self.push_for(PROFILE, event, session);
        }

        fn push_for(&self, profile: &str, event: Event, session: &str) {
            let sender = self.pushes.lock().unwrap().clone().unwrap();
            sender
                .send(Pushed {
                    event,
                    profile_id: Some(profile.into()),
                    session_id: Some(session.into()),
                })
                .unwrap();
        }
    }

    impl Runtime {
        /// The next scripted answer to `request`.
        fn answer(&self, request: &Value) -> std::result::Result<Map<String, Value>, Refusal> {
            match self.script.lock().unwrap().pop_front() {
                Some(Answer::Reply(mut reply)) => {
                    reply["request_id"] = request["request_id"].clone();
                    reply["runtime_boot_id"] = json!(BOOT);
                    reply["connection_id"] = json!(CONNECTION);
                    Ok(reply.as_object().unwrap().clone())
                }
                Some(Answer::Denied(code)) => Err(Refusal::denied(code)),
                Some(Answer::Closed) | None => Err(Refusal::ConnectionClosed),
            }
        }
    }

    impl SessionExchange for Runtime {
        fn exchange(
            &self,
            request: &Value,
            _: Instant,
        ) -> std::result::Result<Map<String, Value>, Refusal> {
            self.asked.lock().unwrap().push(request.clone());
            self.answer(request)
        }

        /// As the connection does: the secret is written only after the
        /// runtime answers the request with `secret_ready`.
        fn exchange_with_secret(
            &self,
            request: &Value,
            secret: &[u8],
            _: Instant,
        ) -> std::result::Result<Map<String, Value>, Refusal> {
            self.asked.lock().unwrap().push(request.clone());
            let ready = self.answer(request)?;
            if ready.get("kind").and_then(Value::as_str) != Some("secret_ready") {
                return Err(Refusal::InvalidFrame);
            }
            self.secrets.lock().unwrap().push(secret.to_vec());
            self.answer(request)
        }

        /// Records the upload's header with the text it streamed, after
        /// checking its length as the runtime's staging does.
        fn exchange_streamed(
            &self,
            request: &Value,
            payload: &[u8],
            deadline: Instant,
        ) -> std::result::Result<Map<String, Value>, Refusal> {
            assert_eq!(request["descriptor"]["byte_count"], payload.len());
            let mut recorded = request.clone();
            recorded["streamed"] = json!(String::from_utf8(payload.to_vec()).unwrap());
            self.exchange(&recorded, deadline)
        }

        fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
            let (sender, receiver) = mpsc::channel();
            *self.pushes.lock().unwrap() = Some(sender);
            receiver
        }

        fn close(&self) {
            self.closed.store(true, Ordering::Release);
        }
    }

    fn admitted() -> Admitted {
        Admitted {
            profile_id: PROFILE.into(),
            session_id: SESSION.into(),
            connection_id: CONNECTION.into(),
            runtime_boot_id: BOOT.into(),
            expires_at: None,
            session_persisted: Some(true),
            signed_out_profile_ids: Vec::new(),
        }
    }

    fn person(runtime: &Arc<Runtime>) -> Person {
        let pushed = runtime.subscribe_scoped();
        Person::native(runtime.clone(), pushed, admitted(), Some(true)).unwrap()
    }

    fn status(session: &str, denial: Value) -> Answer {
        Answer::Reply(json!({
            "kind": "profile_status",
            "status": {
                "profile_id": PROFILE,
                "session_id": session,
                "connected": true,
                "credential_authenticated": true,
                "profile_bound": true,
                "session_expires_at": "2026-10-24T12:00:00Z",
                "denial": denial,
            },
        }))
    }

    /// Waits, within a deadline, until `done` holds.
    fn eventually(done: impl Fn() -> bool) {
        let deadline = Instant::now() + Duration::from_secs(10);
        while !done() {
            assert!(Instant::now() < deadline, "the router never acted");
            thread::sleep(Duration::from_millis(5));
        }
    }

    /// The next event the window hears, within a deadline.
    fn next(
        heard: &mut broadcast::Receiver<PersonEvent>,
    ) -> std::result::Result<PersonEvent, TryRecvError> {
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            match heard.try_recv() {
                Err(TryRecvError::Empty) if Instant::now() < deadline => {
                    thread::sleep(Duration::from_millis(5));
                }
                heard => return heard,
            }
        }
    }

    #[test]
    fn the_held_line_names_the_admitted_session_and_whether_it_was_stored() {
        let runtime = Runtime::answering([]);
        let held = person(&runtime);
        assert_eq!(
            held.identity,
            json!({
                "kind": "session_held",
                "profile_id": PROFILE,
                "session_id": SESSION,
                "runtime_boot_id": BOOT,
                "connection_id": CONNECTION,
                "session_persisted": true,
            })
        );
        assert!(held.session_persisted());
        let resumed = Person::native(
            runtime.clone(),
            runtime.subscribe_scoped(),
            admitted(),
            None,
        )
        .unwrap();
        assert!(resumed.identity.get("session_persisted").is_none());
        assert!(
            runtime.asked().is_empty(),
            "holding asks the runtime nothing"
        );
    }

    #[test]
    fn status_and_activity_are_this_sessions_own_runtime_requests() {
        let runtime =
            Runtime::answering([status(SESSION, Value::Null), status(SESSION, Value::Null)]);
        let mut held = person(&runtime);
        let reply = held.exchange(json!({"action": "status"})).unwrap();
        assert_eq!(reply["status"]["session_id"], SESSION);
        held.exchange(json!({"action": "activity"})).unwrap();
        let asked = runtime.asked();
        for (request, action) in asked.iter().zip(["session_status", "session_activity"]) {
            let mut keys: Vec<_> = request.as_object().unwrap().keys().collect();
            keys.sort();
            assert_eq!(keys, ["action", "profile_id", "request_id", "session_id"]);
            assert_eq!(request["action"], action);
            assert_eq!(request["profile_id"], PROFILE);
            assert_eq!(request["session_id"], SESSION);
        }
    }

    #[test]
    fn another_sessions_status_ends_the_session_as_an_unavailable_refusal() {
        let runtime = Runtime::answering([status(OTHER, Value::Null)]);
        let mut held = person(&runtime);
        let error = held.exchange(json!({"action": "status"})).unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("person_request_refused"));
        assert!(!held.is_open());
    }

    #[test]
    fn an_uncertain_os_observation_refuses_activity_but_keeps_the_session() {
        let runtime = Runtime::answering([
            status(SESSION, json!("os_session_unavailable")),
            status(SESSION, Value::Null),
            Answer::Denied("session_expired"),
        ]);
        let mut held = person(&runtime);
        let refused = held.exchange(json!({"action": "activity"})).unwrap_err();
        assert_eq!(refused.reason.as_deref(), Some("person_request_refused"));
        assert!(held.is_open());
        assert!(held.failures().borrow().is_none());
        held.exchange(json!({"action": "activity"})).unwrap();
        // Any other denial ends the session, as the hold did.
        let ended = held.exchange(json!({"action": "activity"})).unwrap_err();
        assert_eq!(ended.reason.as_deref(), Some("person_request_refused"));
        assert!(!held.is_open());
    }

    #[test]
    fn a_service_is_admitted_only_after_the_session_is_checked() {
        let recipient = OTHER;
        let connected = Answer::Reply(json!({
            "kind": "service_connected",
            "profile_id": PROFILE,
            "service_id": "cadrumo-agent-service",
            "lease": {
                "lease_id": "62345678-1234-4234-8234-123456789abc",
                "session_id": "72345678-1234-4234-8234-123456789abc",
                "parent_session_id": SESSION,
                "runtime_boot_id": BOOT,
                "profile_id": PROFILE,
                "connection_id": recipient,
                "service_id": "cadrumo-agent-service",
                "descriptor_digest": "a".repeat(64),
            },
        }));
        let runtime = Runtime::answering([status(SESSION, Value::Null), connected]);
        let mut held = person(&runtime);
        let reply = held
            .exchange(json!({
                "action": "service_admission",
                "recipient_connection_id": recipient,
                "service_id": "cadrumo-agent-service",
            }))
            .unwrap();
        assert_eq!(reply["kind"], "service_connected");
        let asked = runtime.asked();
        assert_eq!(asked[0]["action"], "session_status");
        assert_eq!(asked[1]["action"], "service_admission");
        assert_eq!(asked[1]["recipient_connection_id"], recipient);
        assert_eq!(asked[1]["service_id"], "cadrumo-agent-service");
        assert_eq!(asked[1]["session_id"], SESSION);
        assert_ne!(asked[0]["request_id"], asked[1]["request_id"]);

        let denied = Runtime::answering([status(SESSION, json!("profile_locked"))]);
        let mut held = person(&denied);
        held.exchange(json!({
            "action": "service_admission",
            "recipient_connection_id": recipient,
            "service_id": "cadrumo-agent-service",
        }))
        .unwrap_err();
        assert_eq!(
            denied.asked().len(),
            1,
            "no admission is asked of an inactive session"
        );
        assert!(!held.is_open());
    }

    const TRANSACTION: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    #[test]
    fn a_view_is_presented_only_for_the_registers_tui_views() {
        let select = json!({"select": TRANSACTION});
        let delivered = Answer::Reply(json!({
            "kind": "presentation_delivered",
            "destination": "ledger",
            "params": select,
            "delivered": 2,
        }));
        let runtime = Runtime::answering([delivered]);
        let mut held = person(&runtime);
        let reply = held
            .exchange(
                json!({"action": "present_destination", "destination": "ledger", "params": select}),
            )
            .unwrap();
        assert_eq!(reply["kind"], "destination_presented");
        assert_eq!(reply["params"], select);
        assert_eq!(reply["delivered"], 2);
        assert_eq!(reply["session_id"], SESSION);
        assert_eq!(runtime.asked()[0]["destination"], "ledger");
        assert_eq!(runtime.asked()[0]["params"], select);
        // A view only the window implements is never asked of the runtime.
        held.exchange(
            json!({"action": "present_destination", "destination": "calendar", "params": {}}),
        )
        .unwrap_err();
        assert_eq!(
            runtime.asked().len(),
            1,
            "a view no TUI implements is never asked for"
        );
        assert!(!held.is_open());
    }

    #[test]
    fn a_view_with_an_undeclared_parameter_is_never_asked_for() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        held.exchange(json!({"action": "present_destination", "destination": "ledger", "params": {"zoom": "2"}}))
            .unwrap_err();
        assert!(runtime.asked().is_empty());
    }

    #[test]
    fn a_delivery_that_echoes_other_parameters_is_refused() {
        let delivered = Answer::Reply(json!({
            "kind": "presentation_delivered",
            "destination": "ledger",
            "params": {"select": TRANSACTION},
            "delivered": 1,
        }));
        let runtime = Runtime::answering([delivered]);
        let mut held = person(&runtime);
        held.exchange(
            json!({"action": "present_destination", "destination": "ledger", "params": {}}),
        )
        .unwrap_err();
        assert_eq!(runtime.asked().len(), 1);
        assert!(!held.is_open());
    }

    #[test]
    fn a_lost_connection_ends_the_session_as_an_unavailable_refusal() {
        let runtime = Runtime::answering([Answer::Closed]);
        let mut held = person(&runtime);
        let error = held
            .exchange(json!({"action": "attendance_inventory"}))
            .unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("person_request_refused"));
        assert!(!held.is_open());
        let later = held.exchange(json!({"action": "status"})).unwrap_err();
        // The ended session answers nothing more: the request fails before it is asked.
        assert_eq!(later.reason.as_deref(), Some("person_action_status"));
        assert_eq!(
            runtime.asked().len(),
            1,
            "nothing is asked of a lost session"
        );
    }

    #[test]
    fn a_reply_beyond_the_relays_document_bound_ends_the_session() {
        let padded = |length: usize| {
            Answer::Reply(json!({
                "kind": "attendance_inventory",
                "profile_id": PROFILE,
                "session_expires_at": "2026-10-24T12:00:00Z",
                "candidates": [],
                "padding": "a".repeat(length),
            }))
        };
        // A settled ledger period's list is some hundreds of kilobytes, far
        // past the one frame the Python hold could write.
        let runtime = Runtime::answering([padded(300 * 1024), padded(REPLY_LIMIT)]);
        let mut held = person(&runtime);
        let reply = held
            .exchange(json!({"action": "attendance_inventory"}))
            .unwrap();
        assert_eq!(reply["padding"].as_str().map(str::len), Some(300 * 1024));
        assert!(held.is_open());
        let error = held
            .exchange(json!({"action": "attendance_inventory"}))
            .unwrap_err();
        assert_eq!(
            error.reason.as_deref(),
            Some("person_action_attendance_inventory")
        );
        assert!(!held.is_open());
    }

    #[test]
    fn a_request_naming_other_keys_ends_the_session_unasked() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        held.exchange(json!({"action": "status", "extra": true}))
            .unwrap_err();
        assert!(runtime.asked().is_empty());
        assert!(!held.is_open());
    }

    #[test]
    fn nothing_reaches_the_window_before_it_observes() {
        let runtime = Runtime::answering([]);
        let pushed = runtime.subscribe_scoped();
        let (events, mut heard) = broadcast::channel(8);
        let (session, _) = NativeSession::start(
            runtime.clone(),
            pushed,
            admitted(),
            None,
            Arc::new(std::sync::Mutex::new(Some(events))),
        )
        .unwrap();
        session
            .shared
            .language_dirty
            .store(false, Ordering::Release);
        runtime.push(Event::RecordsChanged, SESSION);
        runtime.push(Event::LanguageChanged, SESSION);
        // The router acts on pushes in order: once the language is dirty, both were read.
        eventually(|| session.shared.language_dirty.load(Ordering::Acquire));
        assert!(matches!(heard.try_recv(), Err(TryRecvError::Empty)));
    }

    #[test]
    fn cues_reach_the_window_only_for_this_session_once_it_observes() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let (events, mut heard) = broadcast::channel(8);
        held.observe_events(events).unwrap();
        runtime.push(Event::RecordsChanged, OTHER);
        runtime.push(Event::LanguageChanged, SESSION);
        // No operation this session relayed is unsettled, so its cue is not passed on.
        runtime.push(Event::OperationChanged, SESSION);
        runtime.push(Event::AttendanceChanged, SESSION);
        runtime.push(Event::RecordsChanged, SESSION);
        assert_eq!(next(&mut heard), Ok(PersonEvent::LanguageChanged));
        assert_eq!(next(&mut heard), Ok(PersonEvent::AttendanceChanged));
        assert_eq!(next(&mut heard), Ok(PersonEvent::RecordsChanged));
    }

    #[test]
    fn retirement_ends_the_session_and_the_next_request_is_session_loss() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let (events, mut heard) = broadcast::channel(8);
        held.observe_events(events).unwrap();
        let retired = || Event::SessionRetired {
            kind: "session_retired".into(),
            reason: "signed_out".into(),
        };
        runtime.push(retired(), OTHER);
        runtime.push(Event::RecordsChanged, SESSION);
        assert_eq!(next(&mut heard), Ok(PersonEvent::RecordsChanged));
        assert!(
            held.is_open(),
            "another session's retirement is not this one's"
        );
        runtime.push(retired(), SESSION);
        assert_eq!(next(&mut heard), Ok(PersonEvent::Retired));
        assert!(!held.is_open());
        assert!(
            !runtime.closed.load(Ordering::Acquire),
            "the runtime ended it"
        );
        let error = held.exchange(json!({"action": "status"})).unwrap_err();
        assert_eq!(error.code, ErrorCode::SessionUnavailable);
        assert_eq!(error.reason.as_deref(), Some("person_session_retired"));
        assert!(runtime.asked().is_empty());
    }

    #[test]
    fn a_push_meant_for_no_session_of_this_window_closes_its_connection() {
        for violation in [
            (OTHER, Event::RecordsChanged),
            (PROFILE, Event::ServiceLeaseChanged),
            (PROFILE, Event::ModelRunRequested),
        ] {
            let runtime = Runtime::answering([]);
            let held = person(&runtime);
            let (events, mut heard) = broadcast::channel(8);
            *held.events.lock().unwrap() = Some(events);
            runtime.push_for(violation.0, violation.1, SESSION);
            assert_eq!(next(&mut heard), Ok(PersonEvent::Retired));
            assert!(runtime.closed.load(Ordering::Acquire));
        }
    }

    #[test]
    fn a_session_the_window_gives_up_retires_nobody() {
        let runtime = Runtime::answering([]);
        let held = person(&runtime);
        let (events, mut heard) = broadcast::channel(8);
        *held.events.lock().unwrap() = Some(events);
        let pushes = runtime.pushes.lock().unwrap().clone().unwrap();
        drop(held);
        // The connection's end reaches the router after the window let go.
        let _ = pushes.send(Pushed {
            event: Event::Disconnected,
            profile_id: None,
            session_id: None,
        });
        // The router ends, and with it the last sender: nothing was heard first.
        assert_eq!(next(&mut heard), Err(TryRecvError::Closed));
    }

    fn submit() -> Value {
        json!({
            "action": "operation_submit",
            "definition_id": "ledger.list",
            "subject_ref": format!("profile:{PROFILE}"),
            "payload": {"period": "2026-Q3"},
        })
    }

    #[test]
    fn a_relayed_operation_answers_in_the_session_and_its_cues_follow() {
        let runtime = Runtime::answering([
            Answer::Reply(json!({
                "kind": "operation_submitted",
                "receipt": {"submission_version": 1, "operation_id": OPERATION, "secret_requirement": null},
            })),
            Answer::Reply(json!({"kind": "operation_acknowledged", "operation_id": OPERATION})),
        ]);
        let mut held = person(&runtime);
        let (events, mut heard) = broadcast::channel(8);
        held.observe_events(events).unwrap();
        let reply = held.exchange(submit()).unwrap();
        assert_eq!(reply["kind"], "operation_submitted");
        assert_eq!(reply["operation_id"], OPERATION);
        assert_eq!(reply["session_id"], SESSION);
        assert_eq!(reply["connection_id"], CONNECTION);
        let asked = runtime.asked();
        assert_eq!(asked[0]["action"], "operation_submit");
        assert_eq!(asked[1]["action"], "operation_start");
        // An operation this session relayed is unsettled: its cue now reaches the window.
        runtime.push(Event::OperationChanged, SESSION);
        assert_eq!(next(&mut heard), Ok(PersonEvent::OperationChanged));
    }

    const CREDENTIAL: &str = "auth.credential.save";
    const SECRET: &str = r#"{"password":"horse-staple-7f3a"}"#;
    const SECRET_WORD: &str = "horse-staple-7f3a";

    fn secret_submit() -> Value {
        json!({
            "action": "operation_secret_submit",
            "definition_id": CREDENTIAL,
            "subject_ref": format!("profile:{PROFILE}"),
            "payload": {"provider": "certificate"},
            "secret": SECRET,
        })
    }

    #[test]
    fn a_secret_submission_reaches_the_runtime_on_the_secret_frame_and_the_request_keeps_no_text() {
        let description: Value = serde_json::from_str(include_str!(
            "../../../../../application/tests/data/auth-credential-save-description.json"
        ))
        .unwrap();
        let wait = json!({
            "identity": {
                "operation_id": OPERATION,
                "definition_id": CREDENTIAL,
                "subject_ref": format!("profile:{PROFILE}"),
            },
            "interaction_id": "d".repeat(64),
            "revision": 0,
            "secret_kind": "auth.credential.password",
            "expires_at": "2026-10-27T10:05:00Z",
        });
        let runtime = Runtime::answering([
            Answer::Reply(description),
            Answer::Reply(json!({
                "kind": "operation_submitted",
                "receipt": {"submission_version": 1, "operation_id": OPERATION, "secret_requirement": wait},
            })),
            Answer::Reply(json!({"kind": "secret_ready"})),
            Answer::Reply(json!({"kind": "operation_acknowledged", "operation_id": OPERATION})),
            Answer::Reply(json!({"kind": "operation_acknowledged", "operation_id": OPERATION})),
        ]);
        let mut held = person(&runtime);
        let mut request = secret_submit();
        let reply = held.exchange_wiping(&mut request).unwrap();
        assert_eq!(reply["kind"], "operation_submitted");
        assert_eq!(reply["operation_id"], OPERATION);
        assert_eq!(reply["session_id"], SESSION);
        assert!(!reply.to_string().contains(SECRET_WORD));
        // The window's request is overwritten once sent, secret included.
        assert!(!request.to_string().contains(SECRET_WORD));
        assert_eq!(request["secret"], "");
        // Only the secret frame carried it, and the operation started after it.
        assert_eq!(
            *runtime.secrets.lock().unwrap(),
            [SECRET.as_bytes().to_vec()]
        );
        let asked = runtime.asked();
        assert!(!serde_json::to_string(&asked).unwrap().contains(SECRET_WORD));
        let actions: Vec<_> = asked.iter().map(|sent| sent["action"].clone()).collect();
        assert_eq!(
            actions,
            [
                "operation_contract",
                "operation_submit",
                "operation_secret",
                "operation_start"
            ]
        );
        assert!(held.is_open());
    }

    #[test]
    fn a_refused_secret_submission_is_the_operations_answer_and_sends_no_secret() {
        let runtime = Runtime::answering([Answer::Denied("operation_denied")]);
        let mut held = person(&runtime);
        let mut request = secret_submit();
        let refused = held.exchange_wiping(&mut request).unwrap();
        assert_eq!(refused["kind"], "operation_refused");
        assert_eq!(refused["code"], "operation_denied");
        assert!(!request.to_string().contains(SECRET_WORD));
        assert!(runtime.secrets.lock().unwrap().is_empty());
        assert!(held.is_open());
    }

    #[test]
    fn a_secret_submission_naming_other_keys_ends_the_session_unasked() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let mut request = secret_submit();
        request.as_object_mut().unwrap().remove("secret");
        held.exchange_wiping(&mut request).unwrap_err();
        assert!(runtime.asked().is_empty());
        assert!(!held.is_open());
    }

    /// The edit baselines real Modelo 303 and 347 forms admitted, as the
    /// product's form read answered them.
    fn admitted_baselines() -> [(&'static str, Value); 2] {
        let baseline = |envelope: &str| {
            let read: Value = serde_json::from_str(envelope).unwrap();
            let baseline = read["admitted_baseline"].clone();
            assert!(baseline.is_object());
            baseline
        };
        [
            (
                "303",
                baseline(include_str!(
                    "../../../../frontend/src/dev/fixtures/modelo/modelo-303-1T-en.json"
                )),
            ),
            (
                "347",
                baseline(include_str!(
                    "../../../../frontend/src/dev/fixtures/modelo/modelo-347-0A-en.json"
                )),
            ),
        ]
    }

    #[test]
    fn an_edit_of_a_real_baseline_reaches_the_runtime_whole_in_preflight_renewal_and_apply() {
        for (modelo, baseline) in admitted_baselines() {
            let unit = baseline["work_unit_id"].as_str().unwrap().to_owned();
            let input = json!({"input_version": 2, "submission": {"edit_contract_version": 1,
                "baseline": baseline, "mutation_family": "scalar",
                "scalar_intents": [{"value": "1234.56"}]}});
            let renewal = json!({"profile_id": PROFILE, "baseline": baseline,
                "output_language": "en"});
            let steps = [
                ("modelo.edit.preflight", "input", &input),
                ("modelo.edit.renew", "payload", &renewal),
                ("modelo.edit.apply", "input", &input),
            ];
            let runtime = Runtime::answering(steps.iter().flat_map(|_| {
                [
                    Answer::Reply(json!({
                        "kind": "operation_submitted",
                        "receipt": {"submission_version": 1, "operation_id": OPERATION,
                            "secret_requirement": null},
                    })),
                    Answer::Reply(
                        json!({"kind": "operation_acknowledged", "operation_id": OPERATION}),
                    ),
                ]
            }));
            let mut held = person(&runtime);
            for (definition, member, body) in steps {
                let action = if member == "input" {
                    "operation_financial_submit"
                } else {
                    "operation_submit"
                };
                let mut request =
                    json!({"action": action, "definition_id": definition, "subject_ref": unit});
                request[member] = body.clone();
                let reply = held.exchange_wiping(&mut request).unwrap();
                assert_eq!(
                    reply["kind"], "operation_submitted",
                    "{modelo} {definition}"
                );
                assert!(
                    !request.to_string().contains(&unit),
                    "the request is overwritten once sent"
                );
            }
            assert!(held.is_open());
            let asked = runtime.asked();
            assert_eq!(asked.len(), 6);
            for (index, (definition, member, body)) in steps.iter().enumerate() {
                let sent = &asked[2 * index];
                assert_eq!(sent["definition_id"], *definition);
                assert_eq!(sent["subject_ref"], unit);
                // Whole: the runtime is handed exactly the window's document.
                let text = sent["streamed"]
                    .as_str()
                    .or_else(|| sent["payload_json"].as_str())
                    .unwrap();
                assert_eq!(&serde_json::from_str::<Value>(text).unwrap(), *body);
                if *member == "input" || modelo == "303" {
                    // An operand always, and a 303 renewal too large for one
                    // frame, reach the runtime's staging streamed.
                    assert_eq!(
                        sent["action"], "operation_submit_payload",
                        "{modelo} {definition}"
                    );
                }
                assert_eq!(asked[2 * index + 1]["action"], "operation_start");
            }
        }
    }

    #[test]
    fn a_request_beyond_the_relays_document_is_refused_before_the_runtime_is_asked() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let mut request = submit();
        request["payload"] = json!({"rows": "a".repeat(PROJECTION_DOCUMENT_MAX_BYTES + 64 * 1024)});
        let error = held.exchange_wiping(&mut request).unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("person_request_too_large"));
        assert_eq!(
            request["payload"]["rows"], "",
            "a refused request is overwritten too"
        );
        assert!(runtime.asked().is_empty());
    }

    #[test]
    fn a_relay_refusal_is_the_operations_answer_and_keeps_the_session() {
        let runtime = Runtime::answering([Answer::Denied("subject_busy"), Answer::Closed]);
        let mut held = person(&runtime);
        let busy = held.exchange(submit()).unwrap();
        assert_eq!(busy["kind"], "operation_refused");
        assert_eq!(busy["code"], "subject_busy");
        assert!(held.is_open());
        // A lost runtime inside the relay is the operation's `unavailable`, as the hold answered.
        let lost = held.exchange(submit()).unwrap();
        assert_eq!(lost["code"], "unavailable");
        assert!(held.is_open());
    }

    #[test]
    fn a_malformed_relayed_request_ends_the_session_unasked() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let mut request = submit();
        request["payload"] = json!(["not", "an", "object"]);
        let error = held.exchange(request).unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("person_request_refused"));
        assert!(!held.is_open());
        assert!(runtime.asked().is_empty());
    }

    #[test]
    fn a_language_outside_the_products_ends_the_session_unasked() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        held.exchange(json!({"action": "language_set", "language": "fr"}))
            .unwrap_err();
        assert!(!held.is_open());
        assert!(runtime.asked().is_empty());
    }

    #[test]
    fn a_language_read_the_runtime_cannot_answer_ends_the_session() {
        let runtime = Runtime::answering([Answer::Closed]);
        let mut held = person(&runtime);
        let error = held
            .exchange(json!({"action": "language_observe"}))
            .unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("person_request_refused"));
        assert!(!held.is_open());
        assert_eq!(runtime.asked()[0]["action"], "operation_contract");
    }

    #[test]
    fn a_sign_out_is_asked_on_this_session() {
        let signed_out = Answer::Reply(json!({
            "kind": "human_signed_out",
            "session_ids": [SESSION],
            "receipt_removed": true,
            "keychain_removed": true,
            "automation_enabled": false,
            "automation_access_remains": null,
        }));
        let runtime = Runtime::answering([signed_out]);
        let mut held = person(&runtime);
        let out = held.sign_out().unwrap();
        assert_eq!(out.automation_enabled, Some(false));
        assert_eq!(out.automation_access_remains, None);
        let asked = runtime.asked();
        assert_eq!(asked[0]["action"], "human_sign_out");
        assert_eq!(asked[0]["session_id"], SESSION);
    }
}
