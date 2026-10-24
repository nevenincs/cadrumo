//! The person's runtime session the window holds, and the one request protocol
//! every consumer speaks to it.
use cadrumo_application::error::application::{
    ApplicationError, ChildRefusal, ErrorCode, Operation, Result,
};
use serde_json::{Value, json};
#[cfg(test)]
use std::time::Duration;
use std::{
    io::Write,
    sync::{Arc, Mutex},
};

#[cfg(windows)]
mod native;
#[cfg(test)]
mod scripted;

/// The longest request line the holder reads, before its newline.
pub const REQUEST_LIMIT: usize = 16_383;

/// The size of a value's compact JSON encoding, counted without keeping it.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Encoded {
    pub bytes: usize,
    pub chars: usize,
}
impl Write for Encoded {
    fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
        self.bytes += buffer.len();
        // Every character's encoding has exactly one byte that is not a
        // continuation byte.
        self.chars += buffer.iter().filter(|b| (**b & 0xc0) != 0x80).count();
        Ok(buffer.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}
pub fn encoded(value: &Value) -> Encoded {
    let mut size = Encoded::default();
    // Writing a JSON value to a counter cannot fail.
    let _ = serde_json::to_writer(&mut size, value);
    size
}

/// Whether `document` fits one request line once its request id is added.
/// A request that does not is refused before it is written, and that refusal
/// loses the bridge: check first.
pub fn request_fits(document: &Value) -> bool {
    let Some(fields) = document.as_object() else {
        return false;
    };
    // `"request_id":"` and `"` around a 36-character id, after a comma
    // unless it is the only member.
    let id = 14 + 36 + 1 + usize::from(!fields.is_empty());
    encoded(document).bytes + id <= REQUEST_LIMIT
}

/// Overwrites every text in `value` in place, for a request that carried
/// private input.
pub fn wipe(value: &mut Value) {
    match value {
        Value::String(text) => zeroize::Zeroize::zeroize(text),
        Value::Array(items) => items.iter_mut().for_each(wipe),
        Value::Object(fields) => fields.values_mut().for_each(wipe),
        _ => {}
    }
}

fn failed(reason: &'static str) -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli).with_reason(reason)
}

pub fn request_id() -> Result<String> {
    let mut bytes = [0u8; 16];
    getrandom::fill(&mut bytes).map_err(|error| {
        failed("request_id_entropy").caused_by(std::io::Error::other(error.to_string()))
    })?;
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    let hex: String = bytes.iter().map(|b| format!("{b:02x}")).collect();
    Ok(format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    ))
}

/// What the runtime pushed to the held session: only a reason to read again
/// through an exchange, never a value or an authority.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PersonEvent {
    LanguageChanged,
    RecordsChanged,
    AttendanceChanged,
    /// A registered operation this session relayed may have advanced.
    OperationChanged,
    Retired,
}

pub type PersonEvents = tokio::sync::broadcast::Sender<PersonEvent>;

/// The events slot a bridge routes the runtime's pushes into, once the window observes them.
type EventSlot = Arc<Mutex<Option<PersonEvents>>>;

/// What a sign-out through the held session left behind.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SignedOut {
    /// The profile's persisted automation setting, which a sign-out keeps; not access.
    pub automation_enabled: Option<bool>,
    /// Whether an issued key can still admit; `None` when the runtime could not say.
    pub automation_access_remains: Option<bool>,
}

/// What answers a held person's requests, in the document protocol the
/// runtime's `session hold` command speaks: the window's own runtime session,
/// or a test's scripted holder. Pushes reach the events slot it was given.
trait Bridge: Send {
    /// Sends `request`, which carries its request id, and returns its reply,
    /// or why no reply arrived.
    fn exchange(&mut self, request: &Value) -> Result<Value>;
    /// Whether the bridge can still carry a request.
    fn is_open(&mut self) -> bool;
    /// Gives the session up after an exchange lost step with it.
    fn fence(&mut self);
    /// Signs the person out of the profile everywhere through this session.
    fn sign_out(&mut self) -> Result<SignedOut>;
    #[cfg(test)]
    fn scripted(&self) -> Option<&scripted::ScriptedHold> {
        None
    }
    #[cfg(test)]
    fn scripted_mut(&mut self) -> Option<&mut scripted::ScriptedHold> {
        None
    }
}

/// The person's runtime session the window holds, shared by every consumer.
pub struct Person {
    bridge: Box<dyn Bridge>,
    events: EventSlot,
    // Whether the last exchange's error was a refusal of that very request.
    refused_in_step: bool,
    failure: tokio::sync::watch::Sender<Option<ApplicationError>>,
    pub identity: Value,
}

impl Person {
    /// Holds the session the window's own connection admitted for its profile.
    #[cfg(windows)]
    pub(crate) fn native(
        connection: Arc<dyn cadrumo_application::runtime_client::SessionExchange>,
        pushed: std::sync::mpsc::Receiver<cadrumo_application::runtime_client::Pushed>,
        admitted: cadrumo_application::runtime_client::Admitted,
        persisted: Option<bool>,
    ) -> Result<Self> {
        let events = EventSlot::default();
        let (session, identity) =
            native::NativeSession::start(connection, pushed, admitted, persisted, events.clone())?;
        let profile = identity["profile_id"]
            .as_str()
            .unwrap_or_default()
            .to_owned();
        Self::held(
            Box::new(session),
            events,
            identity,
            &profile,
            5 + usize::from(persisted.is_some()),
        )
    }

    /// A scripted holder's person, whose replies are awaited within `reply_limit`.
    #[cfg(test)]
    pub(crate) fn hold_answering_within(
        command: std::process::Command,
        profile: &str,
        reply_limit: Duration,
    ) -> Result<Self> {
        let events = EventSlot::default();
        let (hold, identity) = scripted::ScriptedHold::start(command, reply_limit, events.clone())?;
        Self::held(Box::new(hold), events, identity, profile, 5)
    }

    #[cfg(test)]
    pub(crate) fn scripted(command: std::process::Command, profile: &str) -> Result<Self> {
        Self::hold_answering_within(command, profile, Duration::from_secs(140))
    }

    #[cfg(test)]
    pub(crate) fn child_id(&self) -> u32 {
        self.bridge.scripted().map_or(0, |hold| hold.child.id())
    }

    #[cfg(test)]
    fn scripted_mut(&mut self) -> &mut scripted::ScriptedHold {
        self.bridge
            .scripted_mut()
            .expect("a scripted holder's person")
    }

    #[cfg(any(windows, test))]
    fn held(
        bridge: Box<dyn Bridge>,
        events: EventSlot,
        identity: Value,
        profile: &str,
        members: usize,
    ) -> Result<Self> {
        let person = Self {
            bridge,
            events,
            refused_in_step: false,
            failure: tokio::sync::watch::Sender::new(None),
            identity,
        };
        if person.identity["kind"] == "session_refused" {
            return Err(person.refused("person_hold_refused", &person.identity.clone()));
        }
        person.require_held(profile, members)?;
        if members == 6 && !person.identity["session_persisted"].is_boolean() {
            return Err(failed("person_hold_identity_shape"));
        }
        Ok(person)
    }

    /// Whether the window's sign-in left a stored receipt for the other frontends.
    pub fn session_persisted(&self) -> bool {
        self.identity["session_persisted"] == true
    }

    #[cfg(any(windows, test))]
    fn require_held(&self, profile: &str, members: usize) -> Result<()> {
        if !self
            .identity
            .as_object()
            .is_some_and(|object| object.len() == members)
            || self.identity["kind"] != "session_held"
            || self.identity["profile_id"] != profile
            || ["session_id", "runtime_boot_id", "connection_id"]
                .iter()
                .any(|key| {
                    !self.identity[key]
                        .as_str()
                        .is_some_and(crate::shell::agent_access::wire::is_uuid)
                })
        {
            return Err(failed("person_hold_identity_shape"));
        }
        Ok(())
    }

    fn refused(&self, reason: &'static str, answer: &Value) -> ApplicationError {
        // The refusal line carries its own report: nothing waits on standard error.
        failed(reason).caused_by(ChildRefusal::answered(answer))
    }

    /// From now on, each push from the runtime reaches `events`; the window then
    /// reads language and attendance when they change instead of on a timer.
    pub fn observe_events(&mut self, events: PersonEvents) -> Result<()> {
        *self.events.lock().unwrap_or_else(|e| e.into_inner()) = Some(events);
        self.exchange(json!({"action": "observe_events"}))
            .map(|_| ())
    }

    /// Whether the session can still carry a request: no earlier exchange lost
    /// it and it has not ended.
    pub fn is_open(&mut self) -> bool {
        self.failure.borrow().is_none() && self.bridge.is_open()
    }

    /// Shared consumers must stop using a failed exchange even while the
    /// session is still finishing its last request.
    pub fn failures(&self) -> tokio::sync::watch::Receiver<Option<ApplicationError>> {
        self.failure.subscribe()
    }

    /// Signs the person out of the profile everywhere through this session.
    pub fn sign_out(&mut self) -> Result<SignedOut> {
        self.bridge.sign_out()
    }

    pub fn exchange(&mut self, mut document: Value) -> Result<Value> {
        self.exchange_in(&mut document)
    }

    /// As [`Person::exchange`], for a request that carries private input:
    /// its text is overwritten once the exchange ends, whether or not it was
    /// sent.
    pub fn exchange_wiping(&mut self, document: &mut Value) -> Result<Value> {
        let reply = self.exchange_in(document);
        wipe(document);
        reply
    }

    fn exchange_in(&mut self, document: &mut Value) -> Result<Value> {
        if let Some(error) = self.failure.borrow().as_ref() {
            return Err(failed("person_bridge_closed").caused_by(error.clone()));
        }
        self.refused_in_step = false;
        let reply = self.exchange_once(document);
        if let Err(error) = &reply
            && !self.refused_in_step
        {
            // A missed or malformed reply loses this half-duplex session. No
            // later call may replay a decision or consume its delayed reply.
            // A refusal of this very request leaves it in step: a session that
            // survives one, as for an uncertain OS observation, stays held,
            // and one that ends is seen closed.
            self.bridge.fence();
            self.failure.send_replace(Some(error.clone()));
        }
        reply
    }
    fn exchange_once(&mut self, document: &mut Value) -> Result<Value> {
        let id = request_id()?;
        document["request_id"] = json!(id);
        let length = encoded(document).bytes;
        if length > REQUEST_LIMIT {
            return Err(failed("person_request_too_large"));
        }
        let reply = self.bridge.exchange(document).map_err(|error| {
            // Name only the closed protocol action, never arguments or profile
            // data, so a timeout identifies which runtime path was waiting.
            let action = document["action"].as_str().unwrap_or("unknown");
            let reason = match action {
                "status" => Some("person_action_status"),
                "activity" => Some("person_action_activity"),
                "service_admission" => Some("person_action_service_admission"),
                "attendance_inventory" => Some("person_action_attendance_inventory"),
                "attendance_decision" => Some("person_action_attendance_decision"),
                "language_read" => Some("person_action_language_read"),
                "language_observe" => Some("person_action_language_observe"),
                "language_set" => Some("person_action_language_set"),
                "present_destination" => Some("person_action_present_destination"),
                "observe_events" => Some("person_action_observe_events"),
                "operation_submit" => Some("person_action_operation_submit"),
                "operation_financial_submit" => Some("person_action_operation_financial_submit"),
                "operation_observe" => Some("person_action_operation_observe"),
                "operation_result" => Some("person_action_operation_result"),
                "operation_review" => Some("person_action_operation_review"),
                "operation_respond" => Some("person_action_operation_respond"),
                "operation_cancel" => Some("person_action_operation_cancel"),
                _ => None,
            };
            if let Some(reason) = reason {
                ApplicationError::new(error.code, Operation::Cli)
                    .with_reason(reason)
                    .caused_by(error)
            } else {
                error
            }
        })?;
        // Retirement is an unsolicited terminal event, so it has no request
        // correlation key. Preserve session loss instead of diagnosing it as
        // a malformed reply. exchange() still closes and fences this bridge.
        if reply["kind"] == "session_retired" {
            if reply["profile_id"] != self.identity["profile_id"] {
                return Err(failed("person_reply_identity_mismatch"));
            }
            return Err(
                ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
                    .with_reason("person_session_retired"),
            );
        }
        self.refused_in_step = reply["kind"] == "session_refused" && reply["request_id"] == id;
        if reply["kind"] == "session_refused" {
            return Err(self.refused("person_request_refused", &reply));
        }
        if reply["request_id"] != id {
            return Err(failed("person_reply_request_mismatch"));
        }
        if reply["runtime_boot_id"] != self.identity["runtime_boot_id"]
            || reply["connection_id"] != self.identity["connection_id"]
        {
            return Err(failed("person_reply_identity_mismatch"));
        }
        let valid = match document["action"].as_str() {
            // Noting activity answers with the session's status after the renewal.
            Some("status" | "activity") => {
                reply["kind"] == "profile_status"
                    && reply["status"]["profile_id"] == self.identity["profile_id"]
                    && reply["status"]["session_id"] == self.identity["session_id"]
                    && reply["status"]["connected"] == true
                    && reply["status"]["credential_authenticated"] == true
                    && reply["status"]["profile_bound"] == true
                    && reply["status"]["session_expires_at"].is_string()
                    && reply["status"]["denial"].is_null()
            }
            Some("service_admission") => {
                reply["kind"] == "service_connected"
                    && reply["profile_id"] == self.identity["profile_id"]
                    && reply["service_id"] == document["service_id"]
                    && reply["lease"]["parent_session_id"] == self.identity["session_id"]
                    && reply["lease"]["runtime_boot_id"] == self.identity["runtime_boot_id"]
                    && reply["lease"]["profile_id"] == self.identity["profile_id"]
                    && reply["lease"]["connection_id"] == document["recipient_connection_id"]
                    && reply["lease"]["service_id"] == document["service_id"]
                    && ["lease_id", "session_id"].iter().all(|key| {
                        reply["lease"][key]
                            .as_str()
                            .is_some_and(crate::shell::agent_access::wire::is_uuid)
                    })
                    && reply["lease"]["descriptor_digest"]
                        .as_str()
                        .is_some_and(|digest| {
                            digest.len() == 64
                                && digest
                                    .bytes()
                                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
                        })
            }
            Some("attendance_inventory") => {
                reply["kind"] == "attendance_inventory"
                    && reply["profile_id"] == self.identity["profile_id"]
                    && reply["session_expires_at"].is_string()
                    && reply["candidates"].as_array().is_some_and(|candidates| {
                        candidates.len() <= 8
                            && candidates.iter().all(|candidate| {
                                candidate["attendance_id"]
                                    .as_str()
                                    .is_some_and(crate::shell::agent_access::wire::is_uuid)
                                    && candidate["expires_at"].is_string()
                                    && candidate["scope"].is_object()
                            })
                    })
            }
            Some("attendance_decision") => {
                reply["kind"] == "attendance_decided"
                    && reply["attendance_id"] == document["attendance_id"]
                    && reply["approved"] == document["approve"]
            }
            Some("language_read" | "language_observe" | "language_set") => {
                language_reply(&self.identity, &reply)
            }
            Some("present_destination") => presented_reply(&self.identity, document, &reply),
            Some("observe_events") => reply["kind"] == "events_observed",
            // The caller parses a relayed document itself; here only its kind and session are checked.
            Some(action) => relay_reply(&self.identity, action, &reply),
            _ => false,
        };
        if !valid {
            return Err(failed("person_reply_shape_invalid"));
        }
        Ok(reply)
    }
}

pub type HeldPerson = std::sync::Arc<Mutex<Person>>;

/// The generic relay actions of the held session and the reply each answers with.
const RELAY_REPLIES: [(&str, &str); 7] = [
    ("operation_submit", "operation_submitted"),
    ("operation_financial_submit", "operation_submitted"),
    ("operation_observe", "operation_observed"),
    ("operation_result", "operation_result"),
    ("operation_review", "operation_review"),
    ("operation_respond", "operation_responded"),
    ("operation_cancel", "operation_cancel_requested"),
];

/// Whether `reply` answers relay `action` for the held profile and session:
/// its own reply kind, or a closed refusal that keeps the session held.
fn relay_reply(identity: &Value, action: &str, reply: &Value) -> bool {
    RELAY_REPLIES
        .iter()
        .find(|(relayed, _)| *relayed == action)
        .is_some_and(|(_, kind)| {
            (reply["kind"] == *kind
                || (reply["kind"] == "operation_refused" && reply["code"].is_string()))
                && reply["profile_id"] == identity["profile_id"]
                && reply["session_id"] == identity["session_id"]
        })
}

/// Whether `reply` says the runtime passed the requested page to this
/// person's TUIs on the held profile, and how many it reached.
fn presented_reply(identity: &Value, request: &Value, reply: &Value) -> bool {
    reply["kind"] == "destination_presented"
        && reply["profile_id"] == identity["profile_id"]
        && reply["session_id"] == identity["session_id"]
        && reply["destination"] == request["destination"]
        && reply["delivered"].as_u64().is_some()
}

fn language_reply(identity: &Value, reply: &Value) -> bool {
    reply["kind"] == "profile_language"
        && reply["profile_id"] == identity["profile_id"]
        && reply["session_id"] == identity["session_id"]
        && (reply["language"].is_null()
            || reply["language"]
                .as_str()
                .is_some_and(crate::shell::language::supported))
        && reply["record_revision"].as_u64().is_some()
}

#[cfg(test)]
mod language_tests {
    use super::*;

    #[test]
    fn a_request_is_sized_as_the_line_it_is_written_as() {
        for document in [
            json!({}),
            json!({"action":"operation_submit","payload":{"text":"\u{20ac}"}}),
        ] {
            let mut written = document.clone();
            written["request_id"] = json!(request_id().unwrap());
            let line = serde_json::to_vec(&written).unwrap().len();
            // Each added `"pad":"..."` member costs nine bytes and its text.
            let pad = REQUEST_LIMIT - line - r#","pad":"""#.len();
            let mut filled = document.clone();
            filled["pad"] = json!("a".repeat(pad));
            assert!(request_fits(&filled), "{document}");
            filled["pad"] = json!("a".repeat(pad + 1));
            assert!(!request_fits(&filled), "{document}");
        }
        assert!(!request_fits(&json!(["not", "an", "object"])));
        let size = encoded(&json!({"text":"\u{20ac}a"}));
        assert_eq!((size.bytes, size.chars), (15, 13));
    }

    #[test]
    fn a_wiped_request_keeps_no_text() {
        let mut document = json!({"payload":{"iban":"ES0000","rows":["a", 1, null]}});
        wipe(&mut document);
        assert_eq!(
            document,
            json!({"payload":{"iban":"","rows":["", 1, null]}})
        );
    }

    #[test]
    fn relay_replies_bind_their_action_profile_and_session() {
        let identity = json!({"profile_id":"profile", "session_id":"session"});
        let reply =
            json!({"kind":"operation_submitted", "profile_id":"profile", "session_id":"session"});
        assert!(relay_reply(&identity, "operation_submit", &reply));
        assert!(!relay_reply(&identity, "operation_observe", &reply));
        assert!(!relay_reply(&identity, "setup_start", &reply));
        let refused = json!({"kind":"operation_refused", "profile_id":"profile", "session_id":"session", "code":"subject_busy"});
        assert!(relay_reply(&identity, "operation_cancel", &refused));
        for (key, value) in [
            ("profile_id", json!("other")),
            ("session_id", json!("other")),
            ("code", json!(null)),
        ] {
            let mut invalid = refused.clone();
            invalid[key] = value;
            assert!(
                !relay_reply(&identity, "operation_cancel", &invalid),
                "{key}"
            );
        }
    }

    #[test]
    fn language_replies_bind_profile_session_and_validate_the_fact() {
        let identity = json!({"profile_id":"profile", "session_id":"session"});
        let reply = json!({"kind":"profile_language", "profile_id":"profile", "session_id":"session", "language":"hu", "record_revision":9});
        assert!(language_reply(&identity, &reply));
        for (key, value) in [
            ("profile_id", json!("other")),
            ("session_id", json!("other")),
            ("language", json!("fr")),
            ("record_revision", json!(-1)),
        ] {
            let mut invalid = reply.clone();
            invalid[key] = value;
            assert!(!language_reply(&identity, &invalid));
        }
        let mut unset = reply;
        unset["language"] = Value::Null;
        assert!(language_reply(&identity, &unset));
    }

    #[test]
    fn presented_replies_bind_profile_session_and_the_asked_destination() {
        let identity = json!({"profile_id":"profile", "session_id":"session"});
        let request = json!({"action":"present_destination", "destination":"aeat_auth"});
        let reply = json!({"kind":"destination_presented", "profile_id":"profile", "session_id":"session", "destination":"aeat_auth", "delivered":0});
        assert!(presented_reply(&identity, &request, &reply));
        for (key, value) in [
            ("kind", json!("profile_status")),
            ("profile_id", json!("other")),
            ("session_id", json!("other")),
            ("destination", json!("ledger")),
            ("delivered", json!(-1)),
            ("delivered", json!(null)),
        ] {
            let mut invalid = reply.clone();
            invalid[key] = value;
            assert!(!presented_reply(&identity, &request, &invalid), "{key}");
        }
    }
}

#[cfg(all(test, windows))]
mod event_tests {
    use super::*;
    use crate::agent::runner::tests::powershell;

    const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";

    #[test]
    fn a_push_before_a_reply_reaches_the_events_and_the_reply_still_answers() {
        let identity = json!({
            "kind": "session_held",
            "profile_id": PROFILE,
            "session_id": request_id().unwrap(),
            "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let observed = json!({
            "kind": "events_observed",
            "request_id": "",
            "runtime_boot_id": identity["runtime_boot_id"],
            "connection_id": identity["connection_id"],
        });
        let language = json!({
            "kind": "profile_language",
            "request_id": "",
            "profile_id": PROFILE,
            "session_id": identity["session_id"],
            "runtime_boot_id": identity["runtime_boot_id"],
            "connection_id": identity["connection_id"],
            "language": "es",
            "record_revision": 3,
        });
        let push = json!({"kind":"runtime_event","event":"profile_language_changed"});
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
             $request = [Console]::In.ReadLine() | ConvertFrom-Json; \
             $reply = '{observed}' | ConvertFrom-Json; $reply.request_id = $request.request_id; \
             [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress)); [Console]::Out.Flush(); \
             $request = [Console]::In.ReadLine() | ConvertFrom-Json; \
             [Console]::Out.WriteLine('{push}'); \
             $reply = '{language}' | ConvertFrom-Json; $reply.request_id = $request.request_id; \
             [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress)); [Console]::Out.Flush(); \
             [Console]::In.ReadLine() | Out-Null }}"
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        let (events, mut heard) = tokio::sync::broadcast::channel(4);
        person.observe_events(events).unwrap();
        let reply = person.exchange(json!({"action": "language_read"})).unwrap();
        assert_eq!(reply["language"], "es");
        assert_eq!(heard.try_recv().unwrap(), PersonEvent::LanguageChanged);
    }

    #[test]
    fn activity_is_noted_on_the_held_session_and_only_its_own_status_answers() {
        let identity = json!({
            "kind": "session_held",
            "profile_id": PROFILE,
            "session_id": request_id().unwrap(),
            "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let status = |session: &Value| {
            json!({
                "kind": "profile_status",
                "request_id": "",
                "runtime_boot_id": identity["runtime_boot_id"],
                "connection_id": identity["connection_id"],
                "status": {
                    "profile_id": PROFILE,
                    "session_id": session,
                    "connected": true,
                    "credential_authenticated": true,
                    "profile_bound": true,
                    "session_expires_at": "2026-10-17T06:00:00Z",
                    "denial": null,
                },
            })
        };
        let own = status(&identity["session_id"]);
        let other = status(&json!(request_id().unwrap()));
        // The fake answers only an activity request, so a reply proves which one was sent.
        let answer = |reply: &Value| {
            format!(
                "$request = [Console]::In.ReadLine() | ConvertFrom-Json; \
                 if ($request.action -ne 'activity') {{ exit 9 }}; \
                 $reply = '{reply}' | ConvertFrom-Json; $reply.request_id = $request.request_id; \
                 [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 5)); [Console]::Out.Flush(); "
            )
        };
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); {}{}\
             [Console]::In.ReadLine() | Out-Null }}",
            answer(&own),
            answer(&other)
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        let reply = person.exchange(json!({"action": "activity"})).unwrap();
        assert_eq!(reply["status"]["session_id"], identity["session_id"]);
        let error = person.exchange(json!({"action": "activity"})).unwrap_err();
        assert_eq!(error.code, ErrorCode::ReadFailed);
        assert!(!person.is_open());
    }

    #[test]
    fn a_refusal_of_this_request_keeps_the_bridge_and_the_next_request_is_answered() {
        let identity = json!({
            "kind": "session_held",
            "profile_id": PROFILE,
            "session_id": request_id().unwrap(),
            "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let refused = json!({"kind": "session_refused", "request_id": "", "code": "unavailable"});
        let status = json!({
            "kind": "profile_status",
            "request_id": "",
            "runtime_boot_id": identity["runtime_boot_id"],
            "connection_id": identity["connection_id"],
            "status": {
                "profile_id": PROFILE,
                "session_id": identity["session_id"],
                "connected": true,
                "credential_authenticated": true,
                "profile_bound": true,
                "session_expires_at": "2026-10-17T06:00:00Z",
                "denial": null,
            },
        });
        let answer = |reply: &Value| {
            format!(
                "$request = [Console]::In.ReadLine() | ConvertFrom-Json; \
                 $reply = '{reply}' | ConvertFrom-Json; $reply.request_id = $request.request_id; \
                 [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 5)); [Console]::Out.Flush(); "
            )
        };
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); {}{}\
             [Console]::In.ReadLine() | Out-Null }}",
            answer(&refused),
            answer(&status)
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        // As when the runtime cannot observe the login for a moment: the hold refuses and keeps holding.
        person.exchange(json!({"action": "activity"})).unwrap_err();
        assert!(person.is_open());
        let reply = person.exchange(json!({"action": "activity"})).unwrap();
        assert_eq!(reply["status"]["session_id"], identity["session_id"]);
    }
}

#[cfg(all(test, windows))]
mod failure_tests {
    use super::*;
    use crate::agent::runner::tests::powershell;
    use cadrumo_application::error::application::Cause;
    use std::process::Command;

    const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";

    #[test]
    fn retirement_during_an_exchange_is_session_loss_and_never_a_reply_mismatch() {
        let identity = json!({
            "kind": "session_held",
            "profile_id": PROFILE,
            "session_id": request_id().unwrap(),
            "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let retired = json!({"kind": "session_retired", "profile_id": PROFILE});
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
             $null = [Console]::In.ReadLine(); \
             [Console]::Out.WriteLine('{retired}'); [Console]::Out.Flush(); \
             if ($null -ne [Console]::In.ReadLine()) {{ exit 9 }}; exit 0 }}"
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        let (events, mut heard) = tokio::sync::broadcast::channel(4);
        *person.events.lock().unwrap() = Some(events);
        let failure = person.failures();
        let error = person.exchange(json!({"action": "activity"})).unwrap_err();
        assert_eq!(error.code, ErrorCode::SessionUnavailable);
        assert_eq!(error.reason.as_deref(), Some("person_session_retired"));
        assert_eq!(heard.try_recv().unwrap(), PersonEvent::Retired);
        assert_eq!(failure.borrow().as_ref().unwrap().reason, error.reason);
        assert!(!person.is_open());
        let later = person.exchange(json!({"action": "status"})).unwrap_err();
        assert_eq!(later.reason.as_deref(), Some("person_bridge_closed"));
        assert!(
            person.scripted_mut().child.wait().unwrap().success(),
            "no request was replayed"
        );
    }

    #[test]
    fn a_refused_hold_names_the_childs_refusal_reason_frame_and_trace() {
        let report = r#"{"schema_version":"2","command":"session.hold","status":"error","active_profile":null,"notices":[],"error":{"code":"REFUSED_LOCAL_RUNTIME","category":"REFUSED","message":"PRIVATE MESSAGE","trace_id":"0123456789abcdef0123456789abcdef","context":{"reason":"runtime_peer_untrusted","exception_type":"cadrumo_client.contracts.contracts.RefusalError","raised_at":"cadrumo_runtime.host.session_hold:main:9"}}}"#;
        // The report rides on the refusal line; the child keeps standard error open, so nothing may wait on it.
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{{\"kind\":\"session_refused\",\"request_id\":\"{PROFILE}\",\"code\":\"unavailable\",\"report\":{report}}}'); \
             [Console]::Out.Flush(); [Console]::In.ReadLine() | Out-Null; exit 1 }}"
        );
        let error = Person::scripted(powershell(&script), PROFILE)
            .err()
            .expect("the refused hold fails");
        assert_eq!(error.code, ErrorCode::ReadFailed);
        assert_eq!(error.reason.as_deref(), Some("person_hold_refused"));
        let [Cause::Child(refusal)] = &error.causes[..] else {
            panic!("expected one child refusal, got {:?}", error.causes);
        };
        assert_eq!(refusal.code.as_deref(), Some("unavailable"));
        assert_eq!(refusal.reason.as_deref(), Some("runtime_peer_untrusted"));
        assert_eq!(
            refusal.raised_at.as_deref(),
            Some("cadrumo_runtime.host.session_hold:main:9")
        );
        assert_eq!(
            refusal.trace_id.as_deref(),
            Some("0123456789abcdef0123456789abcdef")
        );
        let serialized = serde_json::to_string(&error).unwrap();
        assert!(!serialized.contains("PRIVATE"));
        assert!(serialized.contains("\"reason\":\"person_hold_refused\""));
    }

    #[test]
    fn a_refusal_the_hold_survives_is_answered_without_waiting_for_a_report() {
        let session = "22345678-1234-4234-8234-123456789abc";
        let identity = format!(
            r#"{{"kind":"session_held","profile_id":"{PROFILE}","session_id":"{session}","runtime_boot_id":"{session}","connection_id":"{session}"}}"#
        );
        // The hold refuses this request, writes no report and keeps holding.
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
             $request = [Console]::In.ReadLine() | ConvertFrom-Json; \
             [Console]::Out.WriteLine((@{{kind='session_refused'; request_id=$request.request_id; code='unavailable'}} | ConvertTo-Json -Compress)); \
             [Console]::Out.Flush(); [Console]::In.ReadLine() | Out-Null }}"
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        let started = std::time::Instant::now();
        let error = person.exchange(json!({"action": "activity"})).unwrap_err();
        // No refusal waits on standard error, which this hold keeps open.
        assert!(
            started.elapsed() < Duration::from_millis(1500),
            "{:?}",
            started.elapsed()
        );
        assert_eq!(error.reason.as_deref(), Some("person_request_refused"));
        let [Cause::Child(refusal)] = &error.causes[..] else {
            panic!("expected one child refusal, got {:?}", error.causes);
        };
        assert_eq!(refusal.code.as_deref(), Some("unavailable"));
        assert_eq!(refusal.trace_id, None);
        assert!(person.is_open());
        assert!(person.failures().borrow().is_none());
    }

    #[test]
    fn a_runtime_reply_after_twelve_seconds_does_not_retire_the_person() {
        let identity = json!({
            "kind": "session_held",
            "profile_id": PROFILE,
            "session_id": request_id().unwrap(),
            "runtime_boot_id": request_id().unwrap(),
            "connection_id": request_id().unwrap(),
        });
        let reply = json!({
            "kind": "events_observed",
            "runtime_boot_id": identity["runtime_boot_id"],
            "connection_id": identity["connection_id"],
        });
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
             foreach ($delay in @(13000, 0)) {{ \
               $request = [Console]::In.ReadLine() | ConvertFrom-Json; \
               Start-Sleep -Milliseconds $delay; \
               $reply = '{reply}' | ConvertFrom-Json; \
               $reply | Add-Member -NotePropertyName request_id -NotePropertyValue $request.request_id; \
               [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress)); [Console]::Out.Flush(); \
             }}; [Console]::In.ReadLine() | Out-Null }}"
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        for _ in 0..2 {
            assert_eq!(
                person
                    .exchange(json!({"action": "observe_events"}))
                    .unwrap()["kind"],
                "events_observed"
            );
            assert!(person.is_open());
            assert!(person.failures().borrow().is_none());
        }
    }

    #[test]
    fn a_timed_out_exchange_notifies_shared_owners_and_keeps_its_original_cause() {
        let session = "22345678-1234-4234-8234-123456789abc";
        let identity = format!(
            r#"{{"kind":"session_held","profile_id":"{PROFILE}","session_id":"{session}","runtime_boot_id":"{session}","connection_id":"{session}"}}"#
        );
        // Withhold the reply until EOF. Any replay would instead reach this
        // child's second read and make it exit unsuccessfully.
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{identity}'); [Console]::Out.Flush(); \
             $null = [Console]::In.ReadLine(); \
             if ($null -ne [Console]::In.ReadLine()) {{ exit 9 }}; exit 0 }}"
        );
        let mut person = Person::scripted(powershell(&script), PROFILE).unwrap();
        person.scripted_mut().reply_limit = Duration::from_millis(50);
        let failure = person.failures();
        assert!(failure.borrow().is_none());
        let error = person
            .exchange(json!({"action": "language_read"}))
            .unwrap_err();
        assert_eq!(error.reason.as_deref(), Some("person_action_language_read"));
        assert_eq!(failure.borrow().as_ref().unwrap().reason, error.reason);
        assert!(!person.is_open());
        let later = person.exchange(json!({"action": "activity"})).unwrap_err();
        assert_eq!(later.reason.as_deref(), Some("person_bridge_closed"));
        assert!(matches!(
            &later.causes[..],
            [Cause::Application { code: ErrorCode::TimedOut, reason: Some(action), .. },
             Cause::Application { code: ErrorCode::TimedOut, reason: Some(reason), .. },
             Cause::TimedOut]
                if action == "person_action_language_read" && reason == "person_reply_timeout"
        ));
        assert!(
            person.scripted_mut().child.wait().unwrap().success(),
            "no request was replayed"
        );
    }

    #[test]
    fn distinct_bridge_failures_have_distinct_reasons() {
        let ended = Person::scripted(powershell("& { exit 3 }"), PROFILE)
            .err()
            .unwrap();
        assert_eq!(ended.reason.as_deref(), Some("person_reply_unreadable"));
        let shaped = Person::scripted(
            powershell(
                "& { [Console]::Out.WriteLine((@{kind='session_held'} | ConvertTo-Json -Compress)) }",
            ),
            PROFILE,
        )
        .err()
        .unwrap();
        assert_eq!(shaped.reason.as_deref(), Some("person_hold_identity_shape"));
        let mut missing = Command::new("cadrumo-test-executable-that-does-not-exist");
        missing.arg("--");
        let spawn = Person::scripted(missing, PROFILE).err().unwrap();
        assert_eq!(spawn.code, ErrorCode::SpawnFailed);
        assert_eq!(spawn.reason.as_deref(), Some("person_hold_spawn"));
        assert!(matches!(
            &spawn.causes[..],
            [Cause::Io { io_kind, .. }] if io_kind == "NotFound"
        ));
    }
}
