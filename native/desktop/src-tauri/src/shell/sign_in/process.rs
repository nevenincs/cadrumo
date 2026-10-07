use super::failure;
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ErrorCode, Result},
    process::status::{ProcessPhase, ProcessRole},
};
use std::{
    io::{Read, Write},
    process::{Child, Command, ExitStatus, Stdio},
    sync::{
        Arc, Condvar, Mutex, MutexGuard,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

const OUTPUT_LIMIT: usize = 64 * 1024;
const DEADLINE: Duration = Duration::from_secs(30);
/// How long the creation of a profile may run. The product derives the
/// profile's key from its password, deliberately slowly: asked directly, a
/// creation takes about half a minute. A child killed part-way would leave
/// the person not knowing whether the profile exists.
pub const CREATION_DEADLINE: Duration = Duration::from_secs(300);
/// How long a read waits for the command that is running: as long as the
/// slowest of them may take. Its own deadline starts when it does.
const SLOT_WAIT: Duration = Duration::from_secs(330);
const MUTATION_WAIT: Duration = Duration::from_secs(30);
const PENDING_READERS: usize = 8;

#[derive(Clone, Copy, Eq, PartialEq)]
enum HelperKind {
    Read,
    Mutation,
}

#[derive(Default)]
struct Active {
    closed: bool,
    busy: Option<HelperKind>,
    pending_mutation: bool,
    pending_readers: usize,
    child: Option<Child>,
    process: Option<u64>,
}

#[derive(Default)]
pub struct Children {
    active: Mutex<Active>,
    changed: Condvar,
    diagnostics: Arc<Diagnostics>,
}

pub struct Output {
    pub success: bool,
    pub stdout: Zeroizing<Vec<u8>>,
    pub stderr: Zeroizing<Vec<u8>>,
}

impl Children {
    pub fn new(diagnostics: Arc<Diagnostics>) -> Self {
        Self {
            diagnostics,
            ..Self::default()
        }
    }

    fn settle_active(&self, active: &mut Active) -> Result<()> {
        let outcome = active.child.as_mut().map(settle).transpose();
        match outcome {
            Ok(Some((status, phase))) => {
                if let Some(process) = active.process.take() {
                    self.diagnostics.finish(process, status.code(), phase);
                }
                Ok(())
            }
            Ok(None) => Ok(()),
            Err(error) => {
                if let Some(process) = active.process {
                    self.diagnostics.failure_for(process, error.clone());
                }
                Err(error)
            }
        }
    }
    /// Permanently fence new commands, kill the current child and reap it.
    pub fn stop(&self) -> Result<()> {
        self.close_with(|active| self.settle_active(active))
    }

    fn close_with(&self, settle_current: impl FnOnce(&mut Active) -> Result<()>) -> Result<()> {
        // Also wake poisoned-lock waiters if acquiring the fence itself fails.
        self.changed.notify_all();
        let mut active = self
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        active.closed = true;
        active.pending_mutation = false;
        self.changed.notify_all();
        let outcome = settle_current(&mut active);
        drop(active);
        // Cleanup failure must not strand admission waiters behind the fence.
        self.changed.notify_all();
        outcome
    }

    pub fn run(&self, command: Command, secret: Option<Zeroizing<Vec<u8>>>) -> Result<Output> {
        self.execute(
            command,
            secret,
            HelperKind::Mutation,
            MUTATION_WAIT,
            DEADLINE,
        )
    }

    /// A command that is slow by design, under a deadline of its own.
    pub fn run_within(
        &self,
        command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        deadline: Duration,
    ) -> Result<Output> {
        self.execute(
            command,
            secret,
            HelperKind::Mutation,
            MUTATION_WAIT,
            deadline,
        )
    }

    /// Status is read-only: wait for the current command without replaying it.
    pub fn read(&self, command: Command) -> Result<Output> {
        self.execute(command, None, HelperKind::Read, SLOT_WAIT, DEADLINE)
    }

    fn admit(&self, kind: HelperKind, slot_wait: Duration) -> Result<MutexGuard<'_, Active>> {
        let asked = Instant::now();
        let mut active = self
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        let mut pending = None;
        loop {
            if active.closed {
                Self::release_pending(&mut active, &mut pending);
                self.changed.notify_all();
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            if pending.is_some() && asked.elapsed() >= slot_wait {
                Self::release_pending(&mut active, &mut pending);
                self.changed.notify_all();
                return Err(failure(ErrorCode::CliWaitTimedOut));
            }
            if active.busy.is_none()
                && (!active.pending_mutation || pending == Some(HelperKind::Mutation))
            {
                Self::release_pending(&mut active, &mut pending);
                return Ok(active);
            }
            if pending.is_none() {
                match kind {
                    HelperKind::Mutation => {
                        // A password waits only behind one read, never behind
                        // another mutation or an already reserved mutation.
                        if active.busy != Some(HelperKind::Read) || active.pending_mutation {
                            return Err(failure(ErrorCode::CliBusy));
                        }
                        active.pending_mutation = true;
                    }
                    HelperKind::Read => {
                        if active.pending_readers >= PENDING_READERS {
                            return Err(failure(ErrorCode::CliBusy));
                        }
                        active.pending_readers += 1;
                    }
                }
                pending = Some(kind);
                self.changed.notify_all();
            }
            let remaining = slot_wait.saturating_sub(asked.elapsed());
            if remaining.is_zero() {
                Self::release_pending(&mut active, &mut pending);
                self.changed.notify_all();
                return Err(failure(ErrorCode::CliWaitTimedOut));
            }
            match self.changed.wait_timeout(active, remaining) {
                Ok((next, _)) => active = next,
                Err(poisoned) => {
                    let (mut active, _) = poisoned.into_inner();
                    Self::release_pending(&mut active, &mut pending);
                    self.changed.notify_all();
                    return Err(failure(ErrorCode::LockPoisoned));
                }
            }
        }
    }

    fn release_pending(active: &mut Active, pending: &mut Option<HelperKind>) {
        match pending.take() {
            Some(HelperKind::Read) => active.pending_readers -= 1,
            Some(HelperKind::Mutation) => active.pending_mutation = false,
            None => {}
        }
    }

    fn execute(
        &self,
        mut command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        kind: HelperKind,
        slot_wait: Duration,
        deadline: Duration,
    ) -> Result<Output> {
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
        let (process, stdin, stdout, stderr, start) = {
            let mut active = match self.admit(kind, slot_wait) {
                Ok(active) => active,
                Err(error) => {
                    // No OS spawn was attempted. Only the closed admission
                    // refusal leaves this boundary, never command or password.
                    self.diagnostics.failure(error.clone());
                    return Err(error);
                }
            };
            let mut child = command.spawn().map_err(|cause| {
                let error = failure(ErrorCode::SpawnFailed).caused_by(cause);
                self.diagnostics
                    .spawn_failure(ProcessRole::SignIn, error.clone());
                self.changed.notify_all();
                error
            })?;
            let start = Instant::now();
            let process = self.diagnostics.start(child.id(), ProcessRole::SignIn);
            let pipes = (
                process,
                child.stdin.take(),
                child.stdout.take().unwrap(),
                child.stderr.take().unwrap(),
                start,
            );
            active.busy = Some(kind);
            active.child = Some(child);
            active.process = Some(process);
            self.changed.notify_all();
            pipes
        };
        // The child's own time, from its start: not the wait for its turn.
        let overflow = AtomicBool::new(false);
        let outcome: Result<Output> = thread::scope(|scope| {
            let writer = scope.spawn(move || -> Result<()> {
                if let (Some(mut stdin), Some(secret)) = (stdin, secret) {
                    // Exactly one payload, followed by EOF; never retry login.
                    stdin
                        .write_all(&secret)
                        .map_err(|cause| failure(ErrorCode::WriteFailed).caused_by(cause))?;
                }
                Ok(())
            });
            let out = scope.spawn(|| read(stdout, &overflow));
            let err = scope.spawn(|| read(stderr, &overflow));
            let status = self.wait(&overflow, start, deadline);
            // Always terminate/reap before joining pipe threads, including limit,
            // timeout and window-close paths. No child bytes enter diagnostics.
            let cleanup = {
                let mut active = self
                    .active
                    .lock()
                    .map_err(|_| failure(ErrorCode::LockPoisoned))?;
                self.settle_active(&mut active)
            };
            let written = writer.join().map_err(|_| failure(ErrorCode::Panic))?;
            let stdout = out.join().map_err(|_| failure(ErrorCode::Panic))?;
            let stderr = err.join().map_err(|_| failure(ErrorCode::Panic))?;
            cleanup?;
            let success = status?.success();
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
        if let Some(status) = active
            .child
            .as_mut()
            .and_then(|child| child.try_wait().ok().flatten())
        {
            if let Some(process) = active.process.take() {
                self.diagnostics
                    .finish(process, status.code(), ProcessPhase::Exited);
            }
            active.child = None;
            active.busy = None;
            self.changed.notify_all();
        }
        if let Err(error) = &outcome {
            self.diagnostics.failure_for(process, error.clone());
        }
        outcome
    }

    fn wait(
        &self,
        overflow: &AtomicBool,
        start: Instant,
        deadline: Duration,
    ) -> Result<ExitStatus> {
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
                .map_err(|cause| failure(ErrorCode::CleanupFailed).caused_by(cause))?
            {
                return Ok(status);
            }
            if start.elapsed() >= deadline {
                return Err(failure(ErrorCode::TimedOut));
            }
            drop(active);
            thread::sleep(Duration::from_millis(10));
        }
    }
}

fn settle(child: &mut Child) -> Result<(ExitStatus, ProcessPhase)> {
    let running = child
        .try_wait()
        .map_err(|cause| failure(ErrorCode::CleanupFailed).caused_by(cause))?
        .is_none();
    if running {
        child
            .kill()
            .map_err(|cause| failure(ErrorCode::CleanupFailed).caused_by(cause))?;
    }
    let status = child
        .wait()
        .map_err(|cause| failure(ErrorCode::CleanupFailed).caused_by(cause))?;
    Ok((
        status,
        if running {
            ProcessPhase::Terminated
        } else {
            ProcessPhase::Exited
        },
    ))
}

fn read(mut pipe: impl Read, overflow: &AtomicBool) -> Result<Zeroizing<Vec<u8>>> {
    let mut output = Zeroizing::new(Vec::with_capacity(OUTPUT_LIMIT));
    let mut buffer = Zeroizing::new([0u8; 4096]);
    loop {
        let count = pipe
            .read(&mut *buffer)
            .map_err(|cause| failure(ErrorCode::ReadFailed).caused_by(cause))?;
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
    pub(super) fn powershell(script: &str) -> Command {
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
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes.len(), 1);
        assert_eq!(snapshot.processes[0].role, ProcessRole::SignIn);
        assert_eq!(snapshot.processes[0].exit_code, Some(0));
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Exited);
        assert!(snapshot.output.is_empty());
        assert!(
            !serde_json::to_string(&snapshot.events)
                .unwrap()
                .contains("secret-channel-probe")
        );
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
                ErrorCode::CliBusy
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
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Terminated);
        assert!(snapshot.output.is_empty());
    }

    #[cfg(windows)]
    #[test]
    fn a_child_is_given_its_own_deadline_and_reaped_when_it_passes() {
        let children = Children::default();
        // Longer than the one it is given: stopped, reaped, and said so.
        let start = Instant::now();
        let late = children.run_within(
            powershell("Start-Sleep -Seconds 60"),
            None,
            Duration::from_millis(400),
        );
        assert_eq!(late.err().unwrap().code, ErrorCode::TimedOut);
        assert!(start.elapsed() < Duration::from_secs(10));
        assert!(children.active.lock().unwrap().child.is_none());
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Terminated);
        assert!(snapshot.events.iter().any(|event| {
            event.process == Some(snapshot.processes[0].id)
                && event
                    .failure
                    .as_ref()
                    .is_some_and(|error| error.code == ErrorCode::TimedOut)
        }));
        // Within the one it is given: it runs to its end.
        let output = children
            .run_within(
                powershell("Start-Sleep -Milliseconds 900; [Console]::Out.Write('made')"),
                None,
                Duration::from_secs(30),
            )
            .unwrap();
        assert_eq!(&*output.stdout, b"made");
    }

    #[cfg(windows)]
    #[test]
    fn a_read_waits_out_a_slow_command_and_then_has_its_whole_deadline() {
        let children = Children::default();
        thread::scope(|scope| {
            let slow = scope.spawn(|| {
                children.run_within(
                    powershell("Start-Sleep -Seconds 4; [Console]::Out.Write('made')"),
                    None,
                    Duration::from_secs(60),
                )
            });
            let seen = Instant::now() + Duration::from_secs(5);
            while children.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < seen);
                thread::sleep(Duration::from_millis(10));
            }
            // Its deadline is shorter than the wait for its turn.
            let read = children.execute(
                powershell("[Console]::Out.Write('status')"),
                None,
                HelperKind::Read,
                Duration::from_secs(60),
                Duration::from_secs(3),
            );
            assert_eq!(&*read.unwrap().stdout, b"status");
            assert_eq!(&*slow.join().unwrap().unwrap().stdout, b"made");
        });
        // And it does not wait for its turn beyond the bound it was given.
        thread::scope(|scope| {
            let slow = scope.spawn(|| children.run(powershell("Start-Sleep -Seconds 3"), None));
            let seen = Instant::now() + Duration::from_secs(5);
            while children.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < seen);
                thread::sleep(Duration::from_millis(10));
            }
            let read = children.execute(
                powershell("[Console]::Out.Write('status')"),
                None,
                HelperKind::Read,
                Duration::from_millis(300),
                Duration::from_secs(30),
            );
            assert_eq!(read.err().unwrap().code, ErrorCode::CliWaitTimedOut);
            assert!(slow.join().unwrap().is_ok());
        });
        assert!(children.active.lock().unwrap().child.is_none());
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

#[cfg(all(test, windows))]
mod admission_tests;
