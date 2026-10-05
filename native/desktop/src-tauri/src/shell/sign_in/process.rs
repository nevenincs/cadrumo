use super::failure;
use cadrumo_application::error::application::{ErrorCode, Result};
use std::{
    io::{Read, Write},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

const OUTPUT_LIMIT: usize = 64 * 1024;
const DEADLINE: Duration = Duration::from_secs(30);

#[derive(Default)]
struct Active {
    closed: bool,
    busy: bool,
    child: Option<Child>,
}

#[derive(Default)]
pub struct Children {
    active: Mutex<Active>,
}

pub struct Output {
    pub success: bool,
    pub stdout: Zeroizing<Vec<u8>>,
    pub stderr: Zeroizing<Vec<u8>>,
}

impl Children {
    /// Permanently fence new commands, kill the current child and reap it.
    pub fn stop(&self) -> Result<()> {
        let mut active = self
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        active.closed = true;
        if let Some(child) = active.child.as_mut() {
            settle(child)?;
        }
        Ok(())
    }

    pub fn run(&self, command: Command, secret: Option<Zeroizing<Vec<u8>>>) -> Result<Output> {
        self.execute(command, secret, false)
    }

    /// Status is read-only: wait for the current command without replaying it.
    pub fn read(&self, command: Command) -> Result<Output> {
        self.execute(command, None, true)
    }

    fn execute(
        &self,
        mut command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        wait_for_slot: bool,
    ) -> Result<Output> {
        let start = Instant::now();
        command
            .stdin(if secret.is_some() {
                Stdio::piped()
            } else {
                Stdio::null()
            })
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }
        let (stdin, stdout, stderr) = {
            let mut active = loop {
                let active = self
                    .active
                    .lock()
                    .map_err(|_| failure(ErrorCode::LockPoisoned))?;
                if active.closed {
                    return Err(failure(ErrorCode::SessionUnavailable));
                }
                if start.elapsed() >= DEADLINE {
                    return Err(failure(ErrorCode::TimedOut));
                }
                if !active.busy {
                    break active;
                }
                if !wait_for_slot {
                    return Err(failure(ErrorCode::QueueFull));
                }
                drop(active);
                thread::sleep(Duration::from_millis(10));
            };
            let mut child = command
                .spawn()
                .map_err(|_| failure(ErrorCode::SpawnFailed))?;
            let pipes = (
                child.stdin.take(),
                child.stdout.take().unwrap(),
                child.stderr.take().unwrap(),
            );
            active.busy = true;
            active.child = Some(child);
            pipes
        };
        let overflow = AtomicBool::new(false);
        let outcome = thread::scope(|scope| {
            let writer = scope.spawn(move || -> Result<()> {
                if let (Some(mut stdin), Some(secret)) = (stdin, secret) {
                    // Exactly one payload, followed by EOF; never retry login.
                    stdin
                        .write_all(&secret)
                        .map_err(|_| failure(ErrorCode::WriteFailed))?;
                }
                Ok(())
            });
            let out = scope.spawn(|| read(stdout, &overflow));
            let err = scope.spawn(|| read(stderr, &overflow));
            let status = self.wait(&overflow, start);
            // Always terminate/reap before joining pipe threads, including limit,
            // timeout and window-close paths. No child bytes enter diagnostics.
            let cleanup = {
                let mut active = self
                    .active
                    .lock()
                    .map_err(|_| failure(ErrorCode::LockPoisoned))?;
                active.child.as_mut().map(settle).transpose()
            };
            let written = writer.join().map_err(|_| failure(ErrorCode::Panic))?;
            let stdout = out.join().map_err(|_| failure(ErrorCode::Panic))?;
            let stderr = err.join().map_err(|_| failure(ErrorCode::Panic))?;
            cleanup?;
            let success = status?;
            // Refusal envelopes are still useful when the child exited before
            // consuming stdin. Successful login must have consumed the write.
            if success {
                written?;
            }
            Ok(Output {
                success,
                stdout: stdout?,
                stderr: stderr?,
            })
        });
        let mut active = self
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        // Retain cleanup ownership if reaping could not be confirmed. A later
        // close retries it, and another command cannot replace the child.
        if active
            .child
            .as_mut()
            .is_some_and(|child| child.try_wait().ok().flatten().is_some())
        {
            active.child = None;
            active.busy = false;
        }
        outcome
    }

    fn wait(&self, overflow: &AtomicBool, start: Instant) -> Result<bool> {
        loop {
            let mut active = self
                .active
                .lock()
                .map_err(|_| failure(ErrorCode::LockPoisoned))?;
            if active.closed {
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            if overflow.load(Ordering::Acquire) {
                return Err(failure(ErrorCode::OutputLimit));
            }
            if let Some(status) = active
                .child
                .as_mut()
                .unwrap()
                .try_wait()
                .map_err(|_| failure(ErrorCode::CleanupFailed))?
            {
                return Ok(status.success());
            }
            if start.elapsed() >= DEADLINE {
                return Err(failure(ErrorCode::TimedOut));
            }
            drop(active);
            thread::sleep(Duration::from_millis(10));
        }
    }
}

fn settle(child: &mut Child) -> Result<()> {
    if child
        .try_wait()
        .map_err(|_| failure(ErrorCode::CleanupFailed))?
        .is_none()
    {
        child
            .kill()
            .map_err(|_| failure(ErrorCode::CleanupFailed))?;
    }
    child
        .wait()
        .map_err(|_| failure(ErrorCode::CleanupFailed))?;
    Ok(())
}

fn read(mut pipe: impl Read, overflow: &AtomicBool) -> Result<Zeroizing<Vec<u8>>> {
    let mut output = Zeroizing::new(Vec::with_capacity(OUTPUT_LIMIT));
    let mut buffer = Zeroizing::new([0u8; 4096]);
    loop {
        let count = pipe
            .read(&mut *buffer)
            .map_err(|_| failure(ErrorCode::ReadFailed))?;
        if count == 0 {
            return Ok(output);
        }
        if output.len() + count > OUTPUT_LIMIT {
            overflow.store(true, Ordering::Release);
            return Err(failure(ErrorCode::OutputLimit));
        }
        output.extend_from_slice(&buffer[..count]);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_reader_refuses_output_above_the_limit() {
        let overflow = AtomicBool::new(false);
        assert_eq!(
            read(&vec![0; OUTPUT_LIMIT][..], &overflow).unwrap().len(),
            OUTPUT_LIMIT
        );
        assert_eq!(
            read(&vec![0; OUTPUT_LIMIT + 1][..], &overflow)
                .unwrap_err()
                .code,
            ErrorCode::OutputLimit
        );
        assert!(overflow.load(Ordering::Acquire));
    }

    #[cfg(windows)]
    fn powershell(script: &str) -> Command {
        let root = std::env::var_os("SystemRoot").unwrap();
        let mut command = Command::new(
            std::path::Path::new(&root).join("System32/WindowsPowerShell/v1.0/powershell.exe"),
        );
        command.args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ]);
        command
    }

    #[cfg(windows)]
    #[test]
    fn real_child_receives_one_secret_and_eof_without_output_logging() {
        let children = Children::default();
        let output = children
            .run(
                powershell("$value=[Console]::In.ReadToEnd(); [Console]::Out.Write($value)"),
                Some(Zeroizing::new(b"secret-channel-probe".to_vec())),
            )
            .unwrap();
        assert!(output.success);
        assert_eq!(&*output.stdout, b"secret-channel-probe");
        assert!(output.stderr.is_empty());
        assert!(children.active.lock().unwrap().child.is_none());
    }

    #[cfg(windows)]
    #[test]
    fn status_waits_for_a_real_child_without_replaying_a_password() {
        let children = Children::default();
        thread::scope(|scope| {
            let mutation = scope.spawn(|| children.run(
                powershell("$value=[Console]::In.ReadToEnd(); Start-Sleep -Milliseconds 600; [Console]::Out.Write($value)"),
                Some(Zeroizing::new(b"one-password".to_vec())),
            ));
            let deadline = Instant::now() + Duration::from_secs(5);
            while children.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < deadline);
                thread::sleep(Duration::from_millis(10));
            }
            let status =
                scope.spawn(|| children.read(powershell("[Console]::Out.Write('status')")));
            assert_eq!(
                children
                    .run(
                        powershell("exit 0"),
                        Some(Zeroizing::new(b"duplicate".to_vec()))
                    )
                    .err()
                    .unwrap()
                    .code,
                ErrorCode::QueueFull
            );
            assert_eq!(&*mutation.join().unwrap().unwrap().stdout, b"one-password");
            assert_eq!(&*status.join().unwrap().unwrap().stdout, b"status");
        });
        assert!(children.active.lock().unwrap().child.is_none());
    }

    #[cfg(windows)]
    #[test]
    fn close_reaps_a_real_blocked_child_and_fences_new_commands() {
        let children = Children::default();
        thread::scope(|scope| {
            let running = scope.spawn(|| children.run(powershell("Start-Sleep -Seconds 60"), None));
            let deadline = Instant::now() + Duration::from_secs(5);
            while children.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < deadline);
                thread::sleep(Duration::from_millis(10));
            }
            let start = Instant::now();
            let queued = scope.spawn(|| children.read(powershell("exit 0")));
            children.stop().unwrap();
            assert!(running.join().unwrap().is_err());
            assert_eq!(
                queued.join().unwrap().err().unwrap().code,
                ErrorCode::SessionUnavailable
            );
            assert!(start.elapsed() < Duration::from_secs(5));
        });
        assert!(children.active.lock().unwrap().child.is_none());
        assert!(children.run(powershell("exit 0"), None).is_err());
    }

    #[cfg(windows)]
    #[test]
    fn real_flood_is_bounded_and_the_child_is_reaped() {
        let children = Children::default();
        let result = children.run(
            powershell("while ($true) { [Console]::Out.Write(('x' * 8192)) }"),
            None,
        );
        assert_eq!(result.err().unwrap().code, ErrorCode::OutputLimit);
        assert!(children.active.lock().unwrap().child.is_none());
    }
}
