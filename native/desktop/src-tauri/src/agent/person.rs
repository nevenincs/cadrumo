//! Bounded bridge to the verified installed desktop runtime session.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use serde_json::{Value, json};
use std::{
    io::{BufRead, BufReader, Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Mutex, mpsc},
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

pub struct Person {
    child: Child,
    stdin: Option<ChildStdin>,
    received: mpsc::Receiver<Option<Value>>,
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
