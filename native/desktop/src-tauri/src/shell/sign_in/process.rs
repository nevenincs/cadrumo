use super::failure;
use cadrumo_application::{
    diagnostics::{
        Diagnostics,
        helper::{HelperKind, HelperOutcome, HelperTiming},
    },
    error::application::{ApplicationError, ErrorCode, Result},
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
/// Profile enrollment includes calibration and storage work. Its separate
/// deadline preserves the existing handling of an indeterminate outcome when
/// a child stops part-way. Command performance is measured separately.
pub const CREATION_DEADLINE: Duration = Duration::from_secs(300);
/// Existing admission bound for reads waiting behind another read.
/// A child's own deadline starts when it does.
const SLOT_WAIT: Duration = Duration::from_secs(330);
const PENDING_READERS: usize = 8;

fn milliseconds(duration: Duration) -> u64 {
    duration.as_millis().min(u128::from(u64::MAX)) as u64
}

struct Measurement {
    process: Option<u64>,
    started: Instant,
    timing: HelperTiming,
}
impl Measurement {
    fn new(kind: HelperKind) -> Self {
        Self {
            process: None,
            started: Instant::now(),
            timing: HelperTiming {
                helper_kind: kind,
                outcome: HelperOutcome::AdmissionRefused,
                admission_wait_ms: 0,
                spawn_ms: None,
                execution_ms: None,
                cleanup_ms: None,
                output_join_ms: None,
                total_ms: 0,
            },
        }
    }
}

/// Record even a phase that returns early, without changing its error precedence.
struct PhaseTimer<'a> {
    elapsed: &'a mut Option<u64>,
    started: Instant,
}
impl<'a> PhaseTimer<'a> {
    fn new(elapsed: &'a mut Option<u64>) -> Self {
        Self {
            elapsed,
            started: Instant::now(),
        }
    }
}
impl Drop for PhaseTimer<'_> {
    fn drop(&mut self) {
        *self.elapsed = Some(milliseconds(self.started.elapsed()));
    }
}

#[derive(Default)]
struct Active {
    busy: bool,
    pending_readers: usize,
    child: Option<Child>,
    process: Option<u64>,
}

#[derive(Default)]
struct Lane {
    active: Mutex<Active>,
    changed: Condvar,
}

#[derive(Default)]
pub struct Children {
    // The same gate fences both lanes and excludes publication of a late child.
    closed: Mutex<bool>,
    read: Lane,
    mutation: Lane,
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

    fn lane(&self, kind: HelperKind) -> &Lane {
        match kind {
            HelperKind::Read => &self.read,
            HelperKind::Mutation => &self.mutation,
        }
    }

    fn is_closed(&self) -> Result<bool> {
        self.closed
            .lock()
            .map(|closed| *closed)
            .map_err(|_| failure(ErrorCode::LockPoisoned))
    }

    fn wake_all(&self) {
        self.read.changed.notify_all();
        self.mutation.changed.notify_all();
    }

    fn diagnose(&self, process: Option<u64>, error: ApplicationError) {
        if let Some(process) = process {
            self.diagnostics.failure_for(process, error);
        } else {
            self.diagnostics.failure(error);
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
            Err(error) => Err(error),
        }
    }
    /// Permanently fence both lanes, then kill and reap each owned child.
    pub fn stop(&self) -> Result<()> {
        self.close_with(|active| self.settle_active(active))
    }

    fn close_with(&self, mut settle_current: impl FnMut(&mut Active) -> Result<()>) -> Result<()> {
        let mut first_error: Option<ApplicationError> = None;
        let mut closed = self.closed.lock().unwrap_or_else(|poisoned| {
            first_error = Some(failure(ErrorCode::LockPoisoned));
            poisoned.into_inner()
        });
        *closed = true;
        drop(closed);
        // Never acquire a lane or perform diagnostic I/O while holding the fence.
        self.wake_all();
        if let Some(error) = &first_error {
            self.diagnose(None, error.clone());
        }
        for lane in [&self.read, &self.mutation] {
            let mut poisoned_error = None;
            let mut active = lane.active.lock().unwrap_or_else(|poisoned| {
                poisoned_error = Some(failure(ErrorCode::LockPoisoned));
                poisoned.into_inner()
            });
            if let Some(error) = poisoned_error {
                self.diagnose(active.process, error.clone());
                first_error.get_or_insert(error);
            }
            if let Err(error) = settle_current(&mut active) {
                self.diagnose(active.process, error.clone());
                first_error.get_or_insert(error);
            }
            drop(active);
            lane.changed.notify_all();
        }
        self.wake_all();
        first_error.map_or(Ok(()), Err)
    }

    pub fn run(&self, command: Command, secret: Option<Zeroizing<Vec<u8>>>) -> Result<Output> {
        self.execute(
            command,
            secret,
            HelperKind::Mutation,
            Duration::ZERO,
            DEADLINE,
        )
    }

    /// Run a mutation under the caller's existing command-specific deadline.
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
            Duration::ZERO,
            deadline,
        )
    }

    /// Read-only commands wait only for another read, independently of mutations.
    pub fn read(&self, command: Command) -> Result<Output> {
        self.execute(command, None, HelperKind::Read, SLOT_WAIT, DEADLINE)
    }

    fn admit(&self, kind: HelperKind, slot_wait: Duration) -> Result<MutexGuard<'_, Active>> {
        let asked = Instant::now();
        let lane = self.lane(kind);
        let mut active = lane
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        let mut pending = false;
        loop {
            let closed = match self.is_closed() {
                Ok(closed) => closed,
                Err(error) => {
                    Self::release_pending(&mut active, &mut pending);
                    lane.changed.notify_all();
                    return Err(error);
                }
            };
            if closed {
                Self::release_pending(&mut active, &mut pending);
                lane.changed.notify_all();
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            if pending && asked.elapsed() >= slot_wait {
                Self::release_pending(&mut active, &mut pending);
                lane.changed.notify_all();
                return Err(failure(ErrorCode::CliWaitTimedOut));
            }
            if !active.busy {
                Self::release_pending(&mut active, &mut pending);
                return Ok(active);
            }
            if kind == HelperKind::Mutation {
                // A second mutation never queues a password or retries it.
                return Err(failure(ErrorCode::CliBusy));
            }
            if !pending {
                if active.pending_readers >= PENDING_READERS {
                    return Err(failure(ErrorCode::CliBusy));
                }
                active.pending_readers += 1;
                pending = true;
                lane.changed.notify_all();
            }
            let remaining = slot_wait.saturating_sub(asked.elapsed());
            if remaining.is_zero() {
                Self::release_pending(&mut active, &mut pending);
                lane.changed.notify_all();
                return Err(failure(ErrorCode::CliWaitTimedOut));
            }
            match lane.changed.wait_timeout(active, remaining) {
                Ok((next, _)) => active = next,
                Err(poisoned) => {
                    let (mut active, _) = poisoned.into_inner();
                    Self::release_pending(&mut active, &mut pending);
                    lane.changed.notify_all();
                    return Err(failure(ErrorCode::LockPoisoned));
                }
            }
        }
    }

    fn release_pending(active: &mut Active, pending: &mut bool) {
        if *pending {
            active.pending_readers -= 1;
            *pending = false;
        }
    }

    fn execute(
        &self,
        command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        kind: HelperKind,
        slot_wait: Duration,
        deadline: Duration,
    ) -> Result<Output> {
        let mut measurement = Measurement::new(kind);
        let outcome =
            self.execute_measured(command, secret, kind, slot_wait, deadline, &mut measurement);
        if outcome.is_ok() {
            measurement.timing.outcome = HelperOutcome::Completed;
        }
        measurement.timing.total_ms = milliseconds(measurement.started.elapsed());
        self.diagnostics
            .helper_timing(measurement.process, measurement.timing);
        outcome
    }

    fn execute_measured(
        &self,
        mut command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        kind: HelperKind,
        slot_wait: Duration,
        deadline: Duration,
        measurement: &mut Measurement,
    ) -> Result<Output> {
        let lane = self.lane(kind);
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
            let admission_started = Instant::now();
            let admission = self.admit(kind, slot_wait);
            let mut active = match admission {
                Ok(active) => active,
                Err(error) => {
                    measurement.timing.admission_wait_ms =
                        milliseconds(admission_started.elapsed());
                    // No OS spawn was attempted. Only the closed admission
                    // refusal leaves this boundary, never command or password.
                    self.diagnostics.failure(error.clone());
                    return Err(error);
                }
            };
            // Lane -> fence is the only acquisition order. Publication is
            // atomic with the shared fence; no diagnostic I/O holds this gate.
            let fence = match self.closed.lock() {
                Ok(fence) => fence,
                Err(poisoned) => {
                    drop(poisoned);
                    measurement.timing.admission_wait_ms =
                        milliseconds(admission_started.elapsed());
                    let error = failure(ErrorCode::LockPoisoned);
                    self.diagnostics.failure(error.clone());
                    return Err(error);
                }
            };
            measurement.timing.admission_wait_ms = milliseconds(admission_started.elapsed());
            if *fence {
                drop(fence);
                let error = failure(ErrorCode::SessionUnavailable);
                self.diagnostics.failure(error.clone());
                return Err(error);
            }
            measurement.timing.outcome = HelperOutcome::SpawnFailed;
            let spawn_started = Instant::now();
            let spawned = command.spawn();
            measurement.timing.spawn_ms = Some(milliseconds(spawn_started.elapsed()));
            let child = match spawned {
                Ok(child) => child,
                Err(cause) => {
                    drop(fence);
                    let error = failure(ErrorCode::SpawnFailed).caused_by(cause);
                    self.diagnostics
                        .spawn_failure(ProcessRole::SignIn, error.clone());
                    lane.changed.notify_all();
                    return Err(error);
                }
            };
            let start = Instant::now();
            let pid = child.id();
            active.busy = true;
            active.child = Some(child);
            drop(fence);
            let child = active.child.as_mut().unwrap();
            let pipes = (
                child.stdin.take(),
                child.stdout.take().unwrap(),
                child.stderr.take().unwrap(),
            );
            let process = self.diagnostics.start(pid, ProcessRole::SignIn);
            measurement.process = Some(process);
            measurement.timing.outcome = HelperOutcome::ExecutionFailed;
            active.process = Some(process);
            lane.changed.notify_all();
            (process, pipes.0, pipes.1, pipes.2, start)
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
            let status = self.wait(lane, &overflow, start, deadline);
            measurement.timing.execution_ms = Some(milliseconds(start.elapsed()));
            // Always terminate/reap before joining pipe threads, including limit,
            // timeout and window-close paths. No child bytes enter diagnostics.
            let cleanup = {
                let _timer = PhaseTimer::new(&mut measurement.timing.cleanup_ms);
                let mut active = lane
                    .active
                    .lock()
                    .map_err(|_| failure(ErrorCode::LockPoisoned))?;
                self.settle_active(&mut active)
            };
            let (written, stdout, stderr) = {
                let _timer = PhaseTimer::new(&mut measurement.timing.output_join_ms);
                let written = writer.join().map_err(|_| failure(ErrorCode::Panic))?;
                let stdout = out.join().map_err(|_| failure(ErrorCode::Panic))?;
                let stderr = err.join().map_err(|_| failure(ErrorCode::Panic))?;
                (written, stdout, stderr)
            };
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
        let mut active = lane
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
            active.busy = false;
            lane.changed.notify_all();
        }
        if let Err(error) = &outcome {
            self.diagnostics.failure_for(process, error.clone());
        }
        outcome
    }

    fn wait(
        &self,
        lane: &Lane,
        overflow: &AtomicBool,
        start: Instant,
        deadline: Duration,
    ) -> Result<ExitStatus> {
        loop {
            // Release the fence before acquiring a lane, also on shutdown.
            if self.is_closed()? {
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            let mut active = lane
                .active
                .lock()
                .map_err(|_| failure(ErrorCode::LockPoisoned))?;
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
    fn timing_milliseconds_saturate_and_early_phase_errors_still_record_elapsed() {
        assert_eq!(milliseconds(Duration::MAX), u64::MAX);
        assert_eq!(milliseconds(Duration::from_micros(999)), 0);
        let mut elapsed = None;
        let mut fail = || -> Result<()> {
            let _timer = PhaseTimer::new(&mut elapsed);
            Err(failure(ErrorCode::Panic))
        };
        let outcome = fail();
        assert_eq!(outcome.unwrap_err().code, ErrorCode::Panic);
        assert!(elapsed.is_some());
    }

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
        assert!(children.mutation.active.lock().unwrap().child.is_none());
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
    fn status_reads_independently_and_duplicate_mutations_never_replay_a_password() {
        let children = Children::default();
        thread::scope(|scope| {
            let mutation = scope.spawn(|| children.run(
                powershell("$value=[Console]::In.ReadToEnd(); Start-Sleep -Milliseconds 600; [Console]::Out.Write($value)"),
                Some(Zeroizing::new(b"one-password".to_vec())),
            ));
            let deadline = Instant::now() + Duration::from_secs(5);
            while children.mutation.active.lock().unwrap().child.is_none() {
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
        assert!(children.mutation.active.lock().unwrap().child.is_none());
        assert!(children.read.active.lock().unwrap().child.is_none());
    }

    #[cfg(windows)]
    #[test]
    fn close_reaps_a_real_blocked_child_and_fences_new_commands() {
        let children = Children::default();
        thread::scope(|scope| {
            let running = scope.spawn(|| children.run(powershell("Start-Sleep -Seconds 60"), None));
            let deadline = Instant::now() + Duration::from_secs(5);
            while children.mutation.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < deadline);
                thread::sleep(Duration::from_millis(10));
            }
            let start = Instant::now();
            children.stop().unwrap();
            let stopped_read = children.read(powershell("exit 0"));
            assert!(running.join().unwrap().is_err());
            assert_eq!(
                stopped_read.err().unwrap().code,
                ErrorCode::SessionUnavailable
            );
            assert!(start.elapsed() < Duration::from_secs(5));
        });
        assert!(children.mutation.active.lock().unwrap().child.is_none());
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
        assert!(children.mutation.active.lock().unwrap().child.is_none());
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Terminated);
        assert!(snapshot.events.iter().any(|event| {
            event.process == Some(snapshot.processes[0].id)
                && event
                    .failure
                    .as_ref()
                    .is_some_and(|error| error.code == ErrorCode::TimedOut)
        }));
        let timed = snapshot.events.last().unwrap();
        assert_eq!(timed.process, Some(snapshot.processes[0].id));
        let timing = timed.helper_timing.unwrap();
        assert_eq!(timing.outcome, HelperOutcome::ExecutionFailed);
        assert!(timing.execution_ms.unwrap() >= 400);
        assert!(timing.cleanup_ms.is_some() && timing.output_join_ms.is_some());
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
    fn a_queued_read_waits_for_another_read_and_then_has_its_whole_deadline() {
        let children = Children::default();
        thread::scope(|scope| {
            let slow = scope.spawn(|| {
                children.read(powershell(
                    "Start-Sleep -Seconds 4; [Console]::Out.Write('made')",
                ))
            });
            let seen = Instant::now() + Duration::from_secs(5);
            while children.read.active.lock().unwrap().child.is_none() {
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
            let slow = scope.spawn(|| children.read(powershell("Start-Sleep -Seconds 3")));
            let seen = Instant::now() + Duration::from_secs(5);
            while children.read.active.lock().unwrap().child.is_none() {
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
        assert!(children.read.active.lock().unwrap().child.is_none());
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
        assert!(children.mutation.active.lock().unwrap().child.is_none());
    }
}

#[cfg(all(test, windows))]
mod admission_tests;
