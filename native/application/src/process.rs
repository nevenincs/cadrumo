//! CLI stream relay. Standard output remains a byte-for-byte operator result channel.
use crate::{
    child::ChildConfiguration,
    diagnostics::Diagnostics,
    failure::{Failure, FailureCode, Operation, Result},
    tracking::{ProcessPhase, ProcessRole, Stream},
};
use std::{
    ffi::OsString,
    io::{Read, Write},
    process::{Child, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};

struct OwnedChild {
    child: Child,
    diagnostics: Arc<Diagnostics>,
    id: u64,
    finished: bool,
}
impl Drop for OwnedChild {
    fn drop(&mut self) {
        if !self.finished {
            let result = match self.child.try_wait() {
                Ok(Some(status)) => Ok(status),
                _ => {
                    let killed = self.child.kill();
                    let waited = self.child.wait();
                    killed.and(waited)
                }
            };
            self.diagnostics.finish(
                self.id,
                result.as_ref().ok().and_then(|s| s.code()),
                if result.is_ok() {
                    ProcessPhase::Terminated
                } else {
                    ProcessPhase::Failed
                },
            );
            if let Err(error) = result {
                self.diagnostics
                    .failure(fail(FailureCode::CleanupFailed).caused_by(error));
            }
        }
    }
}
fn fail(code: FailureCode) -> Failure {
    Failure::new(code, Operation::Cli)
}

pub fn passthrough(
    configuration: &ChildConfiguration,
    arguments: &[OsString],
    diagnostics: Arc<Diagnostics>,
    cancelled: Arc<AtomicBool>,
) -> Result<i32> {
    let child = configuration
        .command()
        .args(arguments)
        .stdin(Stdio::inherit())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| fail(FailureCode::SpawnFailed).caused_by(e))?;
    let id = diagnostics.start(child.id(), ProcessRole::Cli);
    let mut owned = OwnedChild {
        child,
        diagnostics: diagnostics.clone(),
        id,
        finished: false,
    };
    let stdout = owned
        .child
        .stdout
        .take()
        .ok_or_else(|| fail(FailureCode::ReadFailed))?;
    let stderr = owned
        .child
        .stderr
        .take()
        .ok_or_else(|| fail(FailureCode::ReadFailed))?;
    let (sender, receiver) = mpsc::channel();
    let out_sender = sender.clone();
    let out_diagnostics = diagnostics.clone();
    let output = thread::spawn(move || {
        let _ = out_sender.send(relay(
            stdout,
            std::io::stdout(),
            &out_diagnostics,
            id,
            Stream::Stdout,
        ));
    });
    let errors = thread::spawn(move || {
        let _ = sender.send(relay(
            stderr,
            std::io::stderr(),
            &diagnostics,
            id,
            Stream::Stderr,
        ));
    });
    let mut ended = 0;
    let mut status = None;
    let mut drain_deadline = None;
    let mut cancellation_deadline = None;
    loop {
        if cancelled.load(Ordering::Acquire) && cancellation_deadline.is_none() {
            cancellation_deadline = Some(Instant::now() + Duration::from_millis(500));
        }
        if status.is_none() {
            status = owned
                .child
                .try_wait()
                .map_err(|e| fail(FailureCode::CleanupFailed).caused_by(e))?;
            if status.is_some() {
                drain_deadline = Some(Instant::now() + Duration::from_secs(5));
            }
        }
        if cancellation_deadline.is_some_and(|deadline| Instant::now() >= deadline)
            && status.is_none()
        {
            owned
                .child
                .kill()
                .map_err(|e| fail(FailureCode::CleanupFailed).caused_by(e))?;
        }
        if ended == 2 && status.is_some() {
            break;
        }
        if drain_deadline.is_some_and(|deadline| Instant::now() >= deadline) {
            return Err(fail(FailureCode::TimedOut));
        }
        match receiver.recv_timeout(Duration::from_millis(20)) {
            Ok(result) => {
                result?;
                ended += 1;
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) if ended == 2 => {
                thread::sleep(Duration::from_millis(20));
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => return Err(fail(FailureCode::Panic)),
        }
    }
    output.join().map_err(|_| fail(FailureCode::Panic))?;
    errors.join().map_err(|_| fail(FailureCode::Panic))?;
    let status = status.ok_or_else(|| fail(FailureCode::CleanupFailed))?;
    owned.finished = true;
    let code = exit_code(status);
    owned
        .diagnostics
        .finish(id, Some(code), ProcessPhase::Exited);
    Ok(code)
}

fn relay(
    mut reader: impl Read,
    mut writer: impl Write,
    diagnostics: &Diagnostics,
    id: u64,
    stream: Stream,
) -> Result<()> {
    let mut buffer = [0; 8192];
    loop {
        let size = match reader.read(&mut buffer) {
            Ok(size) => size,
            Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(fail(FailureCode::ReadFailed).caused_by(error)),
        };
        if size == 0 {
            return Ok(());
        }
        diagnostics.capture(id, stream, &buffer[..size]);
        writer
            .write_all(&buffer[..size])
            .and_then(|()| writer.flush())
            .map_err(|e| fail(FailureCode::WriteFailed).caused_by(e))?;
    }
}
pub fn exit_code(status: std::process::ExitStatus) -> i32 {
    #[cfg(unix)]
    {
        use std::os::unix::process::ExitStatusExt;
        status
            .code()
            .unwrap_or_else(|| 128 + status.signal().unwrap_or(1))
    }
    #[cfg(not(unix))]
    {
        status.code().unwrap_or(1)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn relay_preserves_binary_bytes_and_records_stream_counts() {
        let diagnostics = Diagnostics::default();
        let id = diagnostics.start(123, ProcessRole::Cli);
        let payload: Vec<u8> = (0..256).cycle().take(300_000).map(|n| n as u8).collect();
        let mut output = Vec::new();
        relay(&payload[..], &mut output, &diagnostics, id, Stream::Stdout).unwrap();
        assert_eq!(output, payload);
        let snapshot = diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].stdout_bytes, 300_000);
        assert!(snapshot.dropped_bytes > 0);
    }

    #[test]
    fn relay_reports_broken_destination_without_exposing_payload() {
        struct Broken;
        impl Write for Broken {
            fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
                Err(std::io::Error::new(
                    std::io::ErrorKind::BrokenPipe,
                    "private error",
                ))
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Ok(())
            }
        }
        let diagnostics = Diagnostics::default();
        let id = diagnostics.start(123, ProcessRole::Cli);
        let error = relay(
            &b"private output"[..],
            Broken,
            &diagnostics,
            id,
            Stream::Stderr,
        )
        .unwrap_err();
        assert_eq!(error.code, FailureCode::WriteFailed);
        assert!(!serde_json::to_string(&error).unwrap().contains("private"));
    }
}
