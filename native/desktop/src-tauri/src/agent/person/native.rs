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
use crate::agent::recovery::{
    RECOVERING,
    rebind::{Course, Recovery, follow},
};
use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    person_operations::{
        OperationRelay, PROJECTION_DOCUMENT_MAX_BYTES, ProfileLanguage, RELAY_ACTION_KEYS,
        RelayFailure, read_profile_language, set_profile_language,
    },
    runtime_client::{
        Admitted, CUSTODY_RECOVERING, Event, Frontend, Pushed, Refusal, SessionExchange,
        human_sign_out, rebind_password,
    },
    view_stream::attach::{ViewAttachGrant, view_attach},
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
const EXCHANGE: Duration =
    Duration::from_secs(cadrumo_platform::DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS);
/// The longest reply: the longest document the relay assembles, and one
/// runtime frame for the reply around it.
const REPLY_LIMIT: usize = PROJECTION_DOCUMENT_MAX_BYTES + 64 * 1024;
/// The denial of an uncertain OS observation: it refuses the request but keeps the session.
const OS_SESSION_UNAVAILABLE: &str = "os_session_unavailable";

/// What the event router and the requests share.
#[derive(Default)]
struct Shared {
    admission_changed: Arc<tokio::sync::Notify>,
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
    timeout_deadline: Option<Instant>,
    connection: Option<Arc<dyn SessionExchange>>,
    admitted: Admitted,
    shared: Arc<Shared>,
    relay: OperationRelay,
    language: Option<ProfileLanguage>,
    /// What keeps the session through a loss of the profile's worker.
    recovery: Recovery,
    /// The losses the session has been through, as the connection's reader sees them.
    course: Arc<Course>,
}

impl NativeSession {
    /// Holds `admitted` on `connection` and routes into `events` the pushes
    /// `pushed` receives, subscribed before the sign-in so none in between is
    /// lost; returns the session and its held line. `recovery` is how the
    /// session is kept when the runtime suspends it.
    pub(super) fn start(
        connection: Arc<dyn SessionExchange>,
        pushed: mpsc::Receiver<Pushed>,
        admitted: Admitted,
        persisted: Option<bool>,
        events: EventSlot,
        recovery: Recovery,
    ) -> Result<(Self, Value)> {
        let shared = Arc::new(Shared::default());
        shared.language_dirty.store(true, Ordering::Release);
        let course = Arc::new(Course::default());
        let routing = Routing {
            admitted: admitted.clone(),
            shared: shared.clone(),
            course: course.clone(),
            recovery: recovery.clone(),
            connection: Arc::downgrade(&connection),
        };
        thread::Builder::new()
            .name("person-session-events".into())
            .spawn(move || route(&pushed, &routing, &events))
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
                timeout_deadline: None,
                connection: Some(connection),
                admitted,
                shared,
                relay: OperationRelay::new(),
                language: None,
                recovery,
                course,
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
        let deadline = self
            .timeout_deadline
            .map_or(Instant::now() + within, |deadline| {
                deadline.min(Instant::now() + within)
            });
        connection.exchange(request, deadline)
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
        if refusal.is_custody_recovering() {
            return self.recovering(request_id);
        }
        self.refuse(request_id, "unavailable", Some(refusal.code()), true)
    }

    /// The hold's answer to a request while the runtime keeps the session
    /// suspended: refused, and still held, because the person is not signed
    /// out and the session can come back on this connection.
    fn recovering(&mut self, request_id: &str) -> Value {
        self.refuse(request_id, RECOVERING, Some(CUSTODY_RECOVERING), false)
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
            "service_admission" | "service_admission_begin" => {
                &["recipient_connection_id", "service_id"]
            }
            "service_admission_status" | "service_admission_cancel" => {
                &["recipient_connection_id", "service_id", "admission_id"]
            }
            "attendance_decision" => &["attendance_id", "approve"],
            "language_set" => &["language"],
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
            "service_admission_begin" => {
                let asked = self.request("service_admission", &request_id, json!({
                    "recipient_connection_id": request["recipient_connection_id"], "service_id": request["service_id"],
                }));
                self.passed_through(&request_id, &asked, EXCHANGE)
            }
            "service_admission_status" | "service_admission_cancel" => {
                let asked = self.request(action, &request_id, json!({
                    "recipient_connection_id": request["recipient_connection_id"], "service_id": request["service_id"],
                    "admission_id": request["admission_id"],
                }));
                self.passed_through(&request_id, &asked, EXCHANGE)
            }
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
            "language_read" | "language_observe" | "language_set" => {
                self.language(&request_id, action, request)
            }
            _ => self.relayed(&request_id, action, request),
        }
    }

    fn status(&mut self, request_id: &str) -> Value {
        let asked = self.request("session_status", request_id, json!({}));
        match self.ask(&asked, EXCHANGE) {
            Ok(reply) if self.own_status(&reply) => match denial(&reply) {
                Some(CUSTODY_RECOVERING) => self.recovering(request_id),
                _ => Value::Object(reply),
            },
            Ok(_) => self.failed_request(request_id, &Refusal::InvalidFrame),
            Err(refusal) => self.failed_request(request_id, &refusal),
        }
    }

    fn activity(&mut self, request_id: &str) -> Value {
        let asked = self.request("session_activity", request_id, json!({}));
        let denied = match self.ask(&asked, EXCHANGE) {
            Ok(reply) if self.own_status(&reply) => match denial(&reply) {
                None => return Value::Object(reply),
                Some(denied) => denied.to_owned(),
            },
            Ok(_) => return self.failed_request(request_id, &Refusal::InvalidFrame),
            Err(Refusal::Denied { code, .. }) => code,
            Err(refusal) => return self.failed_request(request_id, &refusal),
        };
        self.denied(request_id, &denied)
    }

    /// The hold's answer to a request the runtime denied for the person: an
    /// uncertain OS observation or a suspension keeps the session, anything
    /// else ends it.
    fn denied(&mut self, request_id: &str, denial: &str) -> Value {
        if denial == OS_SESSION_UNAVAILABLE {
            return self.refuse(request_id, "unavailable", None, false);
        }
        if denial == CUSTODY_RECOVERING {
            return self.recovering(request_id);
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
        match denial(&current) {
            // An uncertain OS observation refuses this admission but keeps the held sign-in.
            Some(OS_SESSION_UNAVAILABLE) => {
                return self.refuse(request_id, "unavailable", None, false);
            }
            // A suspended session admits no service until it is back.
            Some(CUSTODY_RECOVERING) => return self.recovering(request_id),
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
        self.passed_through(request_id, &asked, EXCHANGE)
    }

    /// The runtime's own reply to `asked`, which names this request.
    fn passed_through(&mut self, request_id: &str, asked: &Value, within: Duration) -> Value {
        match self.ask(asked, within) {
            Ok(reply) => Value::Object(reply),
            Err(Refusal::Denied { code, .. })
                if asked["action"]
                    .as_str()
                    .is_some_and(|action| action.starts_with("service_admission"))
                    && !matches!(
                        code.as_str(),
                        "authentication_required"
                            | "session_inactive"
                            | "session_expired"
                            | "profile_locked"
                            | "os_locked"
                    ) =>
            {
                self.refuse(
                    request_id,
                    if code == "subject_busy" {
                        "busy"
                    } else {
                        "unavailable"
                    },
                    Some(&code),
                    false,
                )
            }
            Err(refusal) => self.failed_request(request_id, &refusal),
        }
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
    fn timeout_deadline(&mut self, deadline: Option<Instant>) {
        self.timeout_deadline = deadline;
    }
    fn admission_changed(&self) -> Option<Arc<tokio::sync::Notify>> {
        Some(self.shared.admission_changed.clone())
    }
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

    fn view_attach(
        &mut self,
        operation_id: &str,
        deadline: Instant,
    ) -> std::result::Result<ViewAttachGrant, Refusal> {
        if self.shared.retired.load(Ordering::Acquire) {
            return Err(Refusal::ConnectionClosed);
        }
        let connection = self.connection.as_ref().ok_or(Refusal::ConnectionClosed)?;
        view_attach(connection.as_ref(), &self.admitted, operation_id, deadline)
    }

    fn rebind_password(&mut self, password: &[u8]) -> std::result::Result<(), Refusal> {
        if self.shared.retired.load(Ordering::Acquire) {
            return Err(Refusal::ConnectionClosed);
        }
        let connection = self.connection.as_ref().ok_or(Refusal::ConnectionClosed)?;
        rebind_password(
            connection.as_ref(),
            &self.admitted,
            Frontend::Desktop,
            password,
            Instant::now() + EXCHANGE,
        )?;
        // The loss is over: the next one is presented afresh, and the window
        // stops saying it waits without waiting for the runtime's cue.
        self.course.ended();
        self.recovery.custody.clear(&self.admitted.session_id);
        Ok(())
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

/// The denial a status reply names, if it names one.
fn denial(reply: &Map<String, Value>) -> Option<&str> {
    reply.get("status")?.get("denial")?.as_str()
}

/// What the router of the held session's pushes works with.
struct Routing {
    admitted: Admitted,
    shared: Arc<Shared>,
    course: Arc<Course>,
    recovery: Recovery,
    connection: std::sync::Weak<dyn SessionExchange>,
}

/// Routes the runtime's pushes for the held session into person events, as
/// the hold did: cues only for this session, an operation's cue only while
/// one it relayed is unsettled, and each only once the window observes. A cue
/// that names no session is the runtime asking this connection to read where
/// its session stands, which is how a suspended one is found.
fn route(pushed: &mpsc::Receiver<Pushed>, routing: &Routing, events: &EventSlot) {
    let Routing {
        admitted,
        shared,
        course,
        recovery,
        connection,
    } = routing;
    let (profile, session) = (admitted.profile_id.as_str(), admitted.session_id.as_str());
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
            Event::LifecycleNotice => continue,
            Event::SignInChanged => {
                follow(course, connection, admitted, recovery);
                continue;
            }
            Event::ProfileLoginChanged { .. } => continue,
            Event::ServiceAdmissionChanged if own && profile_id.as_deref() == Some(profile) => {
                shared.admission_changed.notify_one();
                continue;
            }
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
    // Gone for good: the window no longer waits for a session that cannot come back.
    recovery.custody.clear(session);
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
    use crate::agent::recovery::{Custody, Reconnecting, is_recovering, rebind::Proof};
    use cadrumo_application::runtime_client::ResumeRefusal;
    use std::{collections::VecDeque, sync::Mutex};
    use tokio::sync::broadcast::{self, error::TryRecvError};

    const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";
    const SESSION: &str = "22345678-1234-4234-8234-123456789abc";
    const BOOT: &str = "32345678-1234-4234-8234-123456789abc";
    const CONNECTION: &str = "42345678-1234-4234-8234-123456789abc";
    const OTHER: &str = "52345678-1234-4234-8234-123456789abc";
    const OPERATION: &str = "ab00000000000000000000000000000000000000000000000000000000000001";

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
        pushes: Mutex<Vec<mpsc::Sender<Pushed>>>,
        closed: AtomicBool,
        admission_work: Option<Duration>,
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

        /// The cue the runtime sends a connection whose session it suspended or
        /// returned: it names neither profile nor session.
        fn cue(&self) {
            self.publish(Pushed {
                event: Event::SignInChanged,
                profile_id: None,
                session_id: None,
            });
        }

        fn push_for(&self, profile: &str, event: Event, session: &str) {
            self.publish(Pushed {
                event,
                profile_id: Some(profile.into()),
                session_id: Some(session.into()),
            });
        }

        fn publish(&self, pushed: Pushed) {
            self.pushes
                .lock()
                .unwrap()
                .retain(|sender| sender.send(pushed.clone()).is_ok());
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
            deadline: Instant,
        ) -> std::result::Result<Map<String, Value>, Refusal> {
            self.asked.lock().unwrap().push(request.clone());
            if request["action"] == "service_admission"
                && self
                    .admission_work
                    .is_some_and(|work| deadline.saturating_duration_since(Instant::now()) < work)
            {
                return Err(Refusal::Timeout);
            }
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
            self.pushes.lock().unwrap().push(sender);
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

    /// The stored sign-in as the runtime sees it presented: what the window
    /// shows at the moment each presentation goes out, on the connection it
    /// is given. The test holds the proof.
    struct Stored {
        custody: Custody,
        shown_when_offered: Mutex<Vec<Option<Reconnecting>>>,
    }

    impl Proof for Stored {
        fn present(
            &self,
            exchange: &dyn SessionExchange,
            session: &Admitted,
            deadline: Instant,
        ) -> std::result::Result<(), ResumeRefusal> {
            self.shown_when_offered
                .lock()
                .unwrap()
                .push(self.custody.reconnecting());
            rebind_password(
                exchange,
                session,
                Frontend::Desktop,
                b"stored-proof",
                deadline,
            )
            .map(|_| ())
            .map_err(ResumeRefusal::Runtime)
        }
    }

    impl Stored {
        fn offered(&self) -> Vec<Option<Reconnecting>> {
            self.shown_when_offered.lock().unwrap().clone()
        }
    }

    fn recovery() -> (Recovery, Arc<Stored>) {
        let custody = Custody::default();
        let stored = Arc::new(Stored {
            custody: custody.clone(),
            shown_when_offered: Mutex::new(Vec::new()),
        });
        (
            Recovery {
                custody,
                proof: stored.clone(),
            },
            stored,
        )
    }

    fn person_recovering(runtime: &Arc<Runtime>, recovery: Recovery) -> Person {
        let pushed = runtime.subscribe_scoped();
        Person::native(runtime.clone(), pushed, admitted(), Some(true), recovery).unwrap()
    }

    fn person(runtime: &Arc<Runtime>) -> Person {
        person_recovering(runtime, recovery().0)
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

    /// The status of the session while the runtime keeps it suspended.
    fn suspended() -> Answer {
        Answer::Reply(json!({
            "kind": "profile_status",
            "status": {
                "profile_id": PROFILE,
                "session_id": SESSION,
                "connected": true,
                "credential_authenticated": false,
                "profile_bound": true,
                "session_expires_at": "2026-10-24T12:00:00Z",
                "denial": "custody_recovering",
                "recovery_remaining_seconds": 90,
            },
        }))
    }

    fn secret_ready() -> Answer {
        Answer::Reply(json!({"kind": "secret_ready"}))
    }

    fn actions(runtime: &Runtime) -> Vec<String> {
        runtime
            .asked()
            .iter()
            .map(|asked| asked["action"].as_str().unwrap().to_owned())
            .collect()
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
            recovery().0,
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
        // Model an admission beyond the former two-minute phase cap without making
        // the test sleep: a short wire budget refuses before doing that work.
        let runtime = Arc::new(Runtime {
            script: Mutex::new(VecDeque::from([status(SESSION, Value::Null), connected])),
            admission_work: Some(Duration::from_secs(121)),
            ..Runtime::default()
        });
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
    fn a_pending_service_admission_releases_the_person_for_an_independent_read() {
        let runtime = Runtime::answering([
            Answer::Reply(json!({
                "kind":"service_admission_pending", "profile_id":PROFILE,
                "service_id":"cadrumo-agent-service", "admission_id":OTHER, "cancelled":false,
            })),
            status(SESSION, Value::Null),
        ]);
        let mut held = person(&runtime);
        let pending = held
            .exchange(json!({
                "action":"service_admission_begin", "recipient_connection_id":OTHER,
                "service_id":"cadrumo-agent-service",
            }))
            .unwrap();
        assert_eq!(pending["kind"], "service_admission_pending");
        assert_eq!(
            held.exchange(json!({"action":"status"})).unwrap()["kind"],
            "profile_status"
        );
        let asked = runtime.asked();
        assert_eq!(asked[0]["action"], "service_admission");
        assert_eq!(asked[1]["action"], "session_status");
        assert!(held.is_open());
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
            recovery().0,
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
        drop(held);
        // The connection's end reaches the router after the window let go.
        runtime.publish(Pushed {
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

    const WAITING: Option<Reconnecting> = Some(Reconnecting {
        password_required: false,
    });
    const PASSWORD: Option<Reconnecting> = Some(Reconnecting {
        password_required: true,
    });

    #[test]
    fn a_suspended_session_presents_the_stored_sign_in_once_on_its_own_connection() {
        let runtime = Runtime::answering([
            suspended(),
            secret_ready(),
            status(SESSION, Value::Null),
            status(SESSION, Value::Null),
        ]);
        let (recovery, stored) = recovery();
        let custody = recovery.custody.clone();
        let held = person_recovering(&runtime, recovery);
        // The runtime cues at the suspension and again at the rebind; the
        // router reads them in order, so the second read begins after the first ended.
        runtime.cue();
        runtime.cue();
        eventually(|| actions(&runtime).len() == 3);
        assert_eq!(
            actions(&runtime),
            ["session_status", "profile_login", "session_status"]
        );
        // The proof went out on the connection that holds the session, under its id.
        let asked = runtime.asked();
        assert_eq!(asked[0]["session_id"], SESSION);
        assert_eq!(asked[1]["profile_id"], PROFILE);
        assert_eq!(asked[1]["method"], "password");
        assert_eq!(*runtime.secrets.lock().unwrap(), [b"stored-proof".to_vec()]);
        // The wait was shown before the proof went out, and not after it was accepted.
        assert_eq!(stored.offered(), [WAITING]);
        eventually(|| custody.reconnecting().is_none());
        assert!(held.failures().borrow().is_none());
    }

    #[test]
    fn a_refused_stored_sign_in_is_not_offered_again_and_the_password_rebinds_the_same_session() {
        let runtime = Runtime::answering([
            suspended(),
            secret_ready(),
            Answer::Denied("credential_rejected"),
            suspended(),
            secret_ready(),
            status(SESSION, Value::Null),
        ]);
        let (recovery, stored) = recovery();
        let custody = recovery.custody.clone();
        let mut held = person_recovering(&runtime, recovery);
        runtime.cue();
        // Cued again within the same loss: the window reads and offers nothing.
        runtime.cue();
        eventually(|| runtime.script.lock().unwrap().len() == 2);
        assert_eq!(custody.reconnecting(), PASSWORD);
        assert_eq!(stored.offered(), [WAITING]);
        assert!(held.is_open());
        // The person's password goes out on this same connection, for this same session.
        held.rebind_password(b"the-password").unwrap();
        let asked = runtime.asked();
        assert_eq!(
            actions(&runtime),
            [
                "session_status",
                "profile_login",
                "session_status",
                "profile_login"
            ]
        );
        assert_eq!(asked[3]["method"], "password");
        assert_eq!(asked[3]["persist_receipt"], true);
        assert_eq!(asked[3]["profile_id"], PROFILE);
        assert_eq!(
            *runtime.secrets.lock().unwrap(),
            [b"stored-proof".to_vec(), b"the-password".to_vec()]
        );
        assert_eq!(custody.reconnecting(), None);
        assert!(held.is_open());
        assert!(held.failures().borrow().is_none());
    }

    #[test]
    fn a_password_the_runtime_admits_as_another_session_is_no_rebind() {
        let runtime = Runtime::answering([
            suspended(),
            secret_ready(),
            Answer::Denied("credential_rejected"),
            secret_ready(),
            status(OTHER, Value::Null),
            secret_ready(),
            Answer::Denied("credential_rejected"),
        ]);
        let (recovery, _) = recovery();
        let custody = recovery.custody.clone();
        let mut held = person_recovering(&runtime, recovery);
        runtime.cue();
        eventually(|| custody.reconnecting() == PASSWORD);
        let other = held.rebind_password(b"the-password").unwrap_err();
        assert_eq!(other.code(), "session_mismatch");
        let rejected = held.rebind_password(b"wrong").unwrap_err();
        assert_eq!(rejected.code(), "credential_rejected");
        // Refused, the session stays held and still waits for a password.
        assert_eq!(custody.reconnecting(), PASSWORD);
        assert!(held.is_open());
    }

    #[test]
    fn requests_while_the_session_is_suspended_are_refused_and_never_end_it() {
        let runtime = Runtime::answering([
            suspended(),
            suspended(),
            suspended(),
            Answer::Denied("custody_recovering"),
            Answer::Denied("custody_recovering"),
            status(SESSION, Value::Null),
        ]);
        let mut held = person(&runtime);
        for action in ["status", "activity"] {
            let refused = held.exchange(json!({ "action": action })).unwrap_err();
            assert_eq!(refused.reason.as_deref(), Some("person_request_refused"));
            assert!(is_recovering(&refused), "{action}");
            assert!(held.is_open());
        }
        // No service is admitted under a session that grants nothing.
        let admission = held
            .exchange(json!({
                "action": "service_admission",
                "recipient_connection_id": OTHER,
                "service_id": "cadrumo-agent-service",
            }))
            .unwrap_err();
        assert!(is_recovering(&admission));
        assert_eq!(actions(&runtime).last().unwrap(), "session_status");
        assert!(held.is_open());
        // A language read the runtime refuses for the same reason is refused alike.
        let language = held
            .exchange(json!({"action": "language_observe"}))
            .unwrap_err();
        assert!(is_recovering(&language));
        assert!(held.is_open());
        // An operation's own refusal is the operation's answer, as for any denial.
        let relayed = held.exchange(submit()).unwrap();
        assert_eq!(relayed["kind"], "operation_refused");
        assert_eq!(relayed["code"], "custody_recovering");
        assert!(held.is_open());
        // Once it is back the same session answers again.
        let back = held.exchange(json!({"action": "status"})).unwrap();
        assert_eq!(back["status"]["session_id"], SESSION);
        assert!(held.failures().borrow().is_none());
    }

    #[test]
    fn the_end_of_the_window_retires_the_session_and_the_wait_is_over() {
        let runtime = Runtime::answering([
            suspended(),
            secret_ready(),
            Answer::Denied("credential_rejected"),
        ]);
        let (recovery, _) = recovery();
        let custody = recovery.custody.clone();
        let mut held = person_recovering(&runtime, recovery);
        let (events, mut heard) = broadcast::channel(8);
        held.observe_events(events).unwrap();
        runtime.cue();
        eventually(|| custody.reconnecting() == PASSWORD);
        runtime.push(
            Event::SessionRetired {
                kind: "session_retired".into(),
                reason: "custody_unavailable".into(),
            },
            SESSION,
        );
        assert_eq!(next(&mut heard), Ok(PersonEvent::Retired));
        assert_eq!(custody.reconnecting(), None);
        assert!(!held.is_open());
    }

    #[test]
    fn a_status_naming_another_session_is_never_answered_with_a_proof() {
        let runtime = Runtime::answering([status(OTHER, Value::Null)]);
        let (recovery, stored) = recovery();
        let custody = recovery.custody.clone();
        let mut held = person_recovering(&runtime, recovery);
        runtime.cue();
        eventually(|| actions(&runtime).len() == 1);
        assert_eq!(custody.reconnecting(), None);
        assert!(stored.offered().is_empty());
        assert!(held.is_open());
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
