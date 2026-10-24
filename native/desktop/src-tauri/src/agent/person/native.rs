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
        OperationRelay, ProfileLanguage, RELAY_ACTION_KEYS, RelayFailure, read_profile_language,
        set_profile_language,
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
/// The longest reply, as one line with its newline: one runtime frame and the newline.
const REPLY_LINE_LIMIT: usize = 64 * 1024 + 1;
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
    /// Holds `admitted` on `connection` and routes its pushes into `events`;
    /// returns the session and its held line.
    pub(super) fn start(
        connection: Arc<dyn SessionExchange>,
        admitted: Admitted,
        persisted: Option<bool>,
        events: EventSlot,
    ) -> Result<(Self, Value)> {
        let shared = Arc::new(Shared::default());
        shared.language_dirty.store(true, Ordering::Release);
        let pushed = connection.subscribe_scoped();
        let (routed, profile, session) = (
            shared.clone(),
            admitted.profile_id.clone(),
            admitted.session_id.clone(),
        );
        thread::Builder::new()
            .name("person-session-events".into())
            .spawn(move || route(&pushed, &profile, &session, &routed, &events))
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
            "present_destination" => &["destination"],
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
        let Some(destination) = request["destination"]
            .as_str()
            .filter(|destination| crate::shell::presentation::DESTINATIONS.contains(destination))
        else {
            return self.refuse(request_id, "invalid", None, true);
        };
        let asked = self.request(
            "present_destination",
            request_id,
            json!({"destination": destination}),
        );
        let reply = match self.ask(&asked, EXCHANGE) {
            Ok(reply) => reply,
            Err(Refusal::Denied { code, .. }) => return self.denied(request_id, &code),
            Err(refusal) => return self.failed_request(request_id, &refusal),
        };
        let delivered = reply.get("delivered").and_then(Value::as_u64);
        if reply.get("kind").and_then(Value::as_str) != Some("presentation_delivered")
            || reply.get("destination").and_then(Value::as_str) != Some(destination)
            || delivered.is_none()
        {
            return self.failed_request(request_id, &Refusal::InvalidFrame);
        }
        let mut fields = Map::new();
        fields.insert("kind".into(), json!("destination_presented"));
        fields.insert("destination".into(), json!(destination));
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
        // The hold ended rather than write a reply line longer than one
        // runtime frame; consumers page their reads within that bound.
        if super::encoded(&reply).bytes + 1 > REPLY_LINE_LIMIT {
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
) {
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
            _ if profile_id.as_deref() != Some(profile) => break,
            Event::ServiceLeaseChanged | Event::ModelRunRequested => break,
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

    const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";
    const SESSION: &str = "22345678-1234-4234-8234-123456789abc";
    const BOOT: &str = "32345678-1234-4234-8234-123456789abc";
    const CONNECTION: &str = "42345678-1234-4234-8234-123456789abc";
    const OTHER: &str = "52345678-1234-4234-8234-123456789abc";

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
        pushes: Mutex<Option<mpsc::Sender<Pushed>>>,
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
            let sender = self.pushes.lock().unwrap().clone().unwrap();
            sender
                .send(Pushed {
                    event,
                    profile_id: Some(PROFILE.into()),
                    session_id: Some(session.into()),
                })
                .unwrap();
        }
    }

    impl SessionExchange for Runtime {
        fn exchange(
            &self,
            request: &Value,
            _: Instant,
        ) -> std::result::Result<Map<String, Value>, Refusal> {
            self.asked.lock().unwrap().push(request.clone());
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

        fn subscribe_scoped(&self) -> mpsc::Receiver<Pushed> {
            let (sender, receiver) = mpsc::channel();
            *self.pushes.lock().unwrap() = Some(sender);
            receiver
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
        Person::native(runtime.clone(), admitted(), Some(true)).unwrap()
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

    /// Waits for the event router to act on what was pushed.
    fn settle() {
        thread::sleep(Duration::from_millis(100));
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
        let resumed = Person::native(runtime.clone(), admitted(), None).unwrap();
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

    #[test]
    fn a_page_is_presented_only_for_the_runtimes_vocabulary() {
        let delivered = Answer::Reply(json!({
            "kind": "presentation_delivered",
            "destination": "ledger",
            "delivered": 2,
        }));
        let runtime = Runtime::answering([delivered]);
        let mut held = person(&runtime);
        let reply = held
            .exchange(json!({"action": "present_destination", "destination": "ledger"}))
            .unwrap();
        assert_eq!(reply["kind"], "destination_presented");
        assert_eq!(reply["delivered"], 2);
        assert_eq!(reply["session_id"], SESSION);
        held.exchange(json!({"action": "present_destination", "destination": "elsewhere"}))
            .unwrap_err();
        assert_eq!(
            runtime.asked().len(),
            1,
            "an unknown page is never asked for"
        );
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
    fn a_reply_longer_than_one_frame_ends_the_session_as_the_hold_did() {
        let oversized = Answer::Reply(json!({
            "kind": "attendance_inventory",
            "profile_id": PROFILE,
            "session_expires_at": "2026-10-24T12:00:00Z",
            "candidates": [],
            "padding": "a".repeat(64 * 1024),
        }));
        let runtime = Runtime::answering([oversized]);
        let mut held = person(&runtime);
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
    fn cues_reach_the_window_only_for_this_session_once_it_observes() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let (events, mut heard) = tokio::sync::broadcast::channel(8);
        *held.events.lock().unwrap() = Some(events.clone());
        runtime.push(Event::RecordsChanged, SESSION);
        settle();
        assert!(
            heard.try_recv().is_err(),
            "nothing is pushed before the window observes"
        );
        held.observe_events(events).unwrap();
        runtime.push(Event::RecordsChanged, OTHER);
        runtime.push(Event::LanguageChanged, SESSION);
        // No operation this session relayed is unsettled, so its cue is not passed on.
        runtime.push(Event::OperationChanged, SESSION);
        runtime.push(Event::AttendanceChanged, SESSION);
        settle();
        assert_eq!(heard.try_recv().unwrap(), PersonEvent::LanguageChanged);
        assert_eq!(heard.try_recv().unwrap(), PersonEvent::AttendanceChanged);
        assert!(heard.try_recv().is_err());
    }

    #[test]
    fn retirement_ends_the_session_and_the_next_request_is_session_loss() {
        let runtime = Runtime::answering([]);
        let mut held = person(&runtime);
        let (events, mut heard) = tokio::sync::broadcast::channel(8);
        *held.events.lock().unwrap() = Some(events);
        runtime.push(
            Event::SessionRetired {
                kind: "session_retired".into(),
                reason: "signed_out".into(),
            },
            OTHER,
        );
        settle();
        assert!(
            held.is_open(),
            "another session's retirement is not this one's"
        );
        runtime.push(
            Event::SessionRetired {
                kind: "session_retired".into(),
                reason: "signed_out".into(),
            },
            SESSION,
        );
        settle();
        assert_eq!(heard.try_recv().unwrap(), PersonEvent::Retired);
        assert!(!held.is_open());
        let error = held.exchange(json!({"action": "status"})).unwrap_err();
        assert_eq!(error.code, ErrorCode::SessionUnavailable);
        assert_eq!(error.reason.as_deref(), Some("person_session_retired"));
        assert!(runtime.asked().is_empty());
    }

    #[test]
    fn a_session_the_window_gives_up_retires_nobody() {
        let runtime = Runtime::answering([]);
        let held = person(&runtime);
        let (events, mut heard) = tokio::sync::broadcast::channel(8);
        *held.events.lock().unwrap() = Some(events);
        let pushes = runtime.pushes.lock().unwrap().clone().unwrap();
        drop(held);
        // The connection's end reaches the router after the window let go.
        let _ = pushes.send(Pushed {
            event: Event::Disconnected,
            profile_id: None,
            session_id: None,
        });
        settle();
        assert!(heard.try_recv().is_err());
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
