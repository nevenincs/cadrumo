//! Bounded bridge to the verified installed desktop runtime session.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde_json::{Value, json};
use std::{
    io::{BufRead, BufReader, Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex, mpsc},
    thread,
    time::Duration,
};

fn failed() -> ApplicationError {
    ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
}

pub fn request_id() -> Result<String> {
    let mut bytes = [0u8; 16];
    getrandom::fill(&mut bytes).map_err(|_| failed())?;
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
    events: Arc<Mutex<Option<PersonEvents>>>,
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
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000);
        }
        let mut child = command.spawn().map_err(|_| failed())?;
        let stdin = child.stdin.take().ok_or_else(failed)?;
        let stdout = child.stdout.take().ok_or_else(failed)?;
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
            events,
            identity: Value::Null,
        };
        person.identity = person.read()?;
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
            return Err(failed());
        }
        Ok(person)
    }

    fn read(&mut self) -> Result<Value> {
        self.received
            .recv_timeout(Duration::from_secs(12))
            .map_err(|_| failed())?
            .ok_or_else(failed)
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
        let reply = self.exchange_once(&mut document);
        if reply.is_err() {
            // A missed or malformed reply loses this half-duplex bridge. No
            // later call may replay a decision or consume its delayed reply.
            drop(self.stdin.take());
        }
        reply
    }

    fn exchange_once(&mut self, document: &mut Value) -> Result<Value> {
        let id = request_id()?;
        document["request_id"] = json!(id);
        let mut bytes = serde_json::to_vec(document).map_err(|_| failed())?;
        if bytes.len() > 16_383 {
            return Err(failed());
        }
        bytes.push(b'\n');
        let stdin = self.stdin.as_mut().ok_or_else(failed)?;
        stdin
            .write_all(&bytes)
            .and_then(|()| stdin.flush())
            .map_err(|_| failed())?;
        let reply = self.read()?;
        if reply["request_id"] != id
            || reply["runtime_boot_id"] != self.identity["runtime_boot_id"]
            || reply["connection_id"] != self.identity["connection_id"]
        {
            return Err(failed());
        }
        let valid = match document["action"].as_str() {
            Some("status") => {
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
            return Err(failed());
        }
        Ok(reply)
    }
}

impl Drop for Person {
    fn drop(&mut self) {
        drop(self.stdin.take());
        let deadline = std::time::Instant::now() + Duration::from_secs(2);
        while std::time::Instant::now() < deadline {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                return;
            }
            thread::sleep(Duration::from_millis(20));
        }
        // A stuck bridge cannot keep person authority after its native owner closes.
        let _ = self.child.kill();
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
}
