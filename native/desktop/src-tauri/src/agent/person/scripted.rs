//! A scripted holder for tests: a child that speaks the person protocol one
//! JSON line at a time, so a consumer's test scripts the runtime's answers.
use super::{Bridge, EventSlot, PersonEvent, SignedOut, failed};
use cadrumo_application::error::application::{
    ApplicationError, ChildRefusal, ErrorCode, Operation, Result,
};
use serde_json::Value;
use std::{
    io::{BufRead, BufReader, Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex, mpsc},
    thread,
    time::Duration,
};

/// Diagnostic standard error kept from the child; its registered error
/// document is the only part ever read back.
const STDERR_LIMIT: usize = 64 * 1024;

/// The event a pushed line names, or none for a reply.
fn pushed(value: &Value) -> Option<Option<PersonEvent>> {
    match value["kind"].as_str() {
        Some("runtime_event") => Some(match value["event"].as_str() {
            Some("profile_language_changed") => Some(PersonEvent::LanguageChanged),
            Some("profile_records_changed") => Some(PersonEvent::RecordsChanged),
            Some("attendance_changed") => Some(PersonEvent::AttendanceChanged),
            Some("operation_changed") => Some(PersonEvent::OperationChanged),
            _ => None,
        }),
        Some("session_retired") => Some(Some(PersonEvent::Retired)),
        _ => None,
    }
}

pub(crate) struct ScriptedHold {
    pub(crate) child: Child,
    stdin: Option<ChildStdin>,
    received: mpsc::Receiver<Option<Value>>,
    stderr: Arc<Mutex<Vec<u8>>>,
    stderr_closed: mpsc::Receiver<()>,
    pub(crate) reply_limit: Duration,
}

impl ScriptedHold {
    /// Starts `command` and reads the identity line it answers first.
    pub(crate) fn start(
        mut command: Command,
        reply_limit: Duration,
        events: EventSlot,
    ) -> Result<(Self, Value)> {
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000);
        }
        let mut child =
            cadrumo_application::process::creation::run(|| command.spawn()).map_err(|error| {
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
                            events.lock().unwrap_or_else(|e| e.into_inner()).as_ref()
                    {
                        let _ = events.send(event);
                    }
                    // A push is never a reply; a retirement still ends the stream.
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
        let mut hold = Self {
            child,
            stdin: Some(stdin),
            received,
            stderr,
            stderr_closed,
            reply_limit,
        };
        let identity = hold.read()?;
        Ok((hold, identity))
    }

    fn read(&mut self) -> Result<Value> {
        match self.received.recv_timeout(self.reply_limit) {
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
    /// ended without a refusal line to carry it. The child closes standard
    /// error only by exiting; the deadline bounds one that hangs instead.
    fn with_child_report(&self, error: ApplicationError) -> ApplicationError {
        let _ = self.stderr_closed.recv_timeout(Duration::from_secs(2));
        let kept = self.stderr.lock().unwrap_or_else(|e| e.into_inner());
        match ChildRefusal::reported(&kept) {
            Some(report) if error.causes.is_empty() => error.caused_by(report),
            _ => error,
        }
    }
}

impl Bridge for ScriptedHold {
    fn exchange(&mut self, request: &Value) -> Result<Value> {
        let mut bytes = zeroize::Zeroizing::new(
            serde_json::to_vec(request)
                .map_err(|error| failed("person_request_encode").caused_by(error))?,
        );
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
        self.read()
    }

    fn is_open(&mut self) -> bool {
        self.stdin.is_some() && matches!(self.child.try_wait(), Ok(None))
    }

    fn fence(&mut self) {
        drop(self.stdin.take());
    }

    fn sign_out(&mut self) -> Result<SignedOut> {
        Err(failed("person_sign_out_unsupported"))
    }

    fn scripted(&self) -> Option<&ScriptedHold> {
        Some(self)
    }

    fn scripted_mut(&mut self) -> Option<&mut ScriptedHold> {
        Some(self)
    }
}

impl Drop for ScriptedHold {
    fn drop(&mut self) {
        drop(self.stdin.take());
        // Closed input ends the holder, and it closes standard error only by exiting.
        if let Err(mpsc::RecvTimeoutError::Timeout) =
            self.stderr_closed.recv_timeout(Duration::from_secs(2))
        {
            let _ = self.child.kill();
        }
        let _ = self.child.wait();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn pushed_lines_are_events_and_never_replies() {
        assert_eq!(
            pushed(&json!({"kind":"runtime_event","event":"profile_language_changed"})),
            Some(Some(PersonEvent::LanguageChanged))
        );
        assert_eq!(
            pushed(&json!({"kind":"runtime_event","event":"operation_changed"})),
            Some(Some(PersonEvent::OperationChanged))
        );
        assert_eq!(
            pushed(&json!({"kind":"runtime_event","event":"later"})),
            Some(None)
        );
        assert_eq!(
            pushed(&json!({"kind":"session_retired","profile_id":"profile"})),
            Some(Some(PersonEvent::Retired))
        );
        assert_eq!(
            pushed(&json!({"kind":"operation_observed","request_id":"id"})),
            None
        );
    }
}
