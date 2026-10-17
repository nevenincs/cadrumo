//! Bounded bridge to the verified installed desktop runtime session.
use cadrumo_application::error::application::{
    ApplicationError, ChildRefusal, ErrorCode, Operation, Result,
};
use serde_json::{Value, json};
use std::{
    io::{BufRead, BufReader, Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex, mpsc},
    thread,
    time::Duration,
};

/// Diagnostic standard error kept from the bridge child; its registered error
/// document is the only part ever read back.
const STDERR_LIMIT: usize = 64 * 1024;

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
    AttendanceChanged,
    Retired,
}

pub type PersonEvents = tokio::sync::broadcast::Sender<PersonEvent>;

/// The event a pushed line names, or none for a reply.
fn pushed(value: &Value) -> Option<Option<PersonEvent>> {
    match value["kind"].as_str() {
        Some("runtime_event") => Some(match value["event"].as_str() {
            Some("profile_language_changed") => Some(PersonEvent::LanguageChanged),
            Some("attendance_changed") => Some(PersonEvent::AttendanceChanged),
            _ => None,
        }),
        Some("session_retired") => Some(Some(PersonEvent::Retired)),
        _ => None,
    }
}

pub struct Person {
    child: Child,
    stdin: Option<ChildStdin>,
    received: mpsc::Receiver<Option<Value>>,
    stderr: Arc<Mutex<Vec<u8>>>,
    stderr_closed: mpsc::Receiver<()>,
    events: Arc<Mutex<Option<PersonEvents>>>,
    // Whether the last exchange's error was a refusal of that very request.
    refused_in_step: bool,
    pub identity: Value,
}

impl Person {
    #[cfg(test)]
    pub(crate) fn child_id(&self) -> u32 {
        self.child.id()
    }

    pub fn hold(mut command: Command, profile: &str) -> Result<Self> {
        command
            .args(["session", "hold", "--profile-id", profile])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000);
        }
        let mut child = command.spawn().map_err(|error| {
            ApplicationError::new(ErrorCode::SpawnFailed, Operation::Cli)
                .with_reason("person_hold_spawn")
                .caused_by(error)
        })?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| failed("person_hold_stdin_missing"))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| failed("person_hold_stdout_missing"))?;
        let child_stderr = child
            .stderr
            .take()
            .ok_or_else(|| failed("person_hold_stderr_missing"))?;
        let stderr = Arc::new(Mutex::new(Vec::new()));
        let (stderr_done, stderr_closed) = mpsc::sync_channel(1);
        let collected = stderr.clone();
        thread::spawn(move || {
            let mut reader = child_stderr;
            let mut chunk = [0u8; 4096];
            while let Ok(count @ 1..) = reader.read(&mut chunk) {
                let mut kept = collected.lock().unwrap_or_else(|e| e.into_inner());
                // The newest bytes hold the final error document.
                kept.extend_from_slice(&chunk[..count]);
                if kept.len() > STDERR_LIMIT {
                    let excess = kept.len() - STDERR_LIMIT;
                    kept.drain(..excess);
                }
            }
            let _ = stderr_done.send(());
        });
        let (sender, received) = mpsc::sync_channel(2);
        let events: Arc<Mutex<Option<PersonEvents>>> = Arc::new(Mutex::new(None));
        let routed = events.clone();
        thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                let mut line = Vec::with_capacity(1024);
                let count = reader
                    .by_ref()
                    .take(1024 * 1024 + 1)
                    .read_until(b'\n', &mut line);
                let value = match count {
                    Ok(1..=1_048_576) if line.last() == Some(&b'\n') => {
                        serde_json::from_slice::<Value>(&line).ok()
                    }
                    _ => None,
                };
                if let Some(push) = value.as_ref().and_then(pushed) {
                    if let Some(event) = push
                        && let Some(events) =
                            routed.lock().unwrap_or_else(|e| e.into_inner()).as_ref()
                    {
                        let _ = events.send(event);
                    }
                    // A push is never a reply; a retirement still ends the stream as before.
                    if push != Some(PersonEvent::Retired) {
                        continue;
                    }
                }
                let ended = value.is_none();
                if sender.send(value).is_err() || ended {
                    break;
                }
            }
        });
        let mut person = Self {
            child,
            stdin: Some(stdin),
            received,
            stderr,
            stderr_closed,
            events,
            refused_in_step: false,
            identity: Value::Null,
        };
        person.identity = person.read()?;
        if person.identity["kind"] == "session_refused" {
            return Err(person.refused("person_hold_refused", &person.identity.clone()));
        }
        if !person
            .identity
            .as_object()
            .is_some_and(|object| object.len() == 5)
            || person.identity["kind"] != "session_held"
            || person.identity["profile_id"] != profile
            || ["session_id", "runtime_boot_id", "connection_id"]
                .iter()
                .any(|key| {
                    !person.identity[key]
                        .as_str()
                        .is_some_and(crate::shell::agent_access::wire::is_uuid)
                })
        {
            return Err(failed("person_hold_identity_shape"));
        }
        Ok(person)
    }

    fn read(&mut self) -> Result<Value> {
        match self.received.recv_timeout(Duration::from_secs(12)) {
            Ok(Some(value)) => Ok(value),
            Ok(None) => Err(self.with_child_report(failed("person_reply_unreadable"))),
            Err(error @ mpsc::RecvTimeoutError::Timeout) => {
                Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Cli)
                    .with_reason("person_reply_timeout")
                    .caused_by(error))
            }
            Err(error) => {
                Err(self.with_child_report(failed("person_reply_stream_ended").caused_by(error)))
            }
        }
    }

    /// The child's own registered error document, for a reply stream that
    /// ended without a refusal line to carry it.
    ///
    /// The holder closes standard error only by exiting, so its close is the
    /// event this waits for; the deadline only bounds a child that ended its
    /// replies but hangs instead of exiting.
    fn child_report(&self) -> Option<ChildRefusal> {
        let _ = self.stderr_closed.recv_timeout(Duration::from_secs(2));
        let kept = self.stderr.lock().unwrap_or_else(|e| e.into_inner());
        ChildRefusal::reported(&kept)
    }

    fn with_child_report(&self, error: ApplicationError) -> ApplicationError {
        match self.child_report() {
            Some(report) if error.causes.is_empty() => error.caused_by(report),
            _ => error,
        }
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

    /// Whether the bridge can still carry a request: no earlier exchange lost
    /// it and the holder has not ended.
    pub fn is_open(&mut self) -> bool {
        self.stdin.is_some() && matches!(self.child.try_wait(), Ok(None))
    }

    pub fn exchange(&mut self, mut document: Value) -> Result<Value> {
        self.refused_in_step = false;
        let reply = self.exchange_once(&mut document);
        if reply.is_err() && !self.refused_in_step {
            // A missed or malformed reply loses this half-duplex bridge. No
            // later call may replay a decision or consume its delayed reply.
            // A refusal of this very request leaves it in step: a hold that
            // survives one, as for an uncertain OS observation, keeps the
            // person's session, and one that ends is seen closed.
            drop(self.stdin.take());
        }
        reply
    }

    fn exchange_once(&mut self, document: &mut Value) -> Result<Value> {
        let id = request_id()?;
        document["request_id"] = json!(id);
        let mut bytes = serde_json::to_vec(document)
            .map_err(|error| failed("person_request_encode").caused_by(error))?;
        if bytes.len() > 16_383 {
            return Err(failed("person_request_too_large"));
        }
        bytes.push(b'\n');
        let stdin = self
            .stdin
            .as_mut()
            .ok_or_else(|| failed("person_bridge_closed"))?;
        stdin
            .write_all(&bytes)
            .and_then(|()| stdin.flush())
            .map_err(|error| {
                ApplicationError::new(ErrorCode::WriteFailed, Operation::Cli)
                    .with_reason("person_request_write")
                    .caused_by(error)
            })?;
        let reply = self.read()?;
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
            Some("observe_events") => reply["kind"] == "events_observed",
            _ => false,
        };
        if !valid {
            return Err(failed("person_reply_shape_invalid"));
        }
        Ok(reply)
    }
}

impl Drop for Person {
    fn drop(&mut self) {
        drop(self.stdin.take());
        // Closed input ends the holder, and it closes standard error only by
        // exiting: that close wakes this, never a polling interval.
        if let Err(mpsc::RecvTimeoutError::Timeout) =
            self.stderr_closed.recv_timeout(Duration::from_secs(2))
        {
            // A stuck bridge cannot keep person authority after its native owner closes.
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

pub type HeldPerson = std::sync::Arc<Mutex<Person>>;

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
    fn pushed_lines_are_events_and_never_replies() {
        assert_eq!(
            pushed(&json!({"kind":"runtime_event","event":"profile_language_changed"})),
            Some(Some(PersonEvent::LanguageChanged))
        );
        assert_eq!(
            pushed(&json!({"kind":"runtime_event","event":"attendance_changed"})),
            Some(Some(PersonEvent::AttendanceChanged))
        );
        // A push this window does not know is still never taken for a reply.
        assert_eq!(
            pushed(&json!({"kind":"runtime_event","event":"later"})),
            Some(None)
        );
        assert_eq!(
            pushed(&json!({"kind":"session_retired","profile_id":"profile"})),
            Some(Some(PersonEvent::Retired))
        );
        assert_eq!(
            pushed(&json!({"kind":"profile_language","request_id":"id"})),
            None
        );
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
        let mut person = Person::hold(powershell(&script), PROFILE).unwrap();
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
        let mut person = Person::hold(powershell(&script), PROFILE).unwrap();
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
        let mut person = Person::hold(powershell(&script), PROFILE).unwrap();
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

    const PROFILE: &str = "12345678-1234-4234-8234-123456789abc";

    #[test]
    fn a_refused_hold_names_the_childs_refusal_reason_frame_and_trace() {
        let report = r#"{"schema_version":"2","command":"session.hold","status":"error","active_profile":null,"notices":[],"error":{"code":"REFUSED_LOCAL_RUNTIME","category":"REFUSED","message":"PRIVATE MESSAGE","trace_id":"0123456789abcdef0123456789abcdef","context":{"reason":"runtime_peer_untrusted","exception_type":"cadrumo_client.contracts.contracts.RefusalError","raised_at":"cadrumo_runtime.host.session_hold:main:9"}}}"#;
        // The report rides on the refusal line; the child keeps standard error open, so nothing may wait on it.
        let script = format!(
            "& {{ [Console]::Out.WriteLine('{{\"kind\":\"session_refused\",\"request_id\":\"{PROFILE}\",\"code\":\"unavailable\",\"report\":{report}}}'); \
             [Console]::Out.Flush(); [Console]::In.ReadLine() | Out-Null; exit 1 }}"
        );
        let error = Person::hold(powershell(&script), PROFILE)
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
        let mut person = Person::hold(powershell(&script), PROFILE).unwrap();
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
    }

    #[test]
    fn distinct_bridge_failures_have_distinct_reasons() {
        let ended = Person::hold(powershell("& { exit 3 }"), PROFILE)
            .err()
            .unwrap();
        assert_eq!(ended.reason.as_deref(), Some("person_reply_unreadable"));
        let shaped = Person::hold(
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
        let spawn = Person::hold(missing, PROFILE).err().unwrap();
        assert_eq!(spawn.code, ErrorCode::SpawnFailed);
        assert_eq!(spawn.reason.as_deref(), Some("person_hold_spawn"));
        assert!(matches!(
            &spawn.causes[..],
            [Cause::Io { io_kind, .. }] if io_kind == "NotFound"
        ));
    }
}
