use super::{closing, failure};
use cadrumo_application::{
    diagnostics::{
        Diagnostics,
        helper::{HelperIdentity, HelperKind, HelperOutcome, HelperResult, HelperTiming},
    },
    error::application::{ApplicationError, ErrorCode, Result},
    process::status::{ProcessPhase, ProcessRole},
    shutdown::is_host_closing,
};
use cadrumo_platform::process_exit::ProcessExitWatch;
use std::{
    io::{Read, Write},
    process::{Child, Command, ExitStatus, Stdio},
    sync::{
        Arc, Condvar, Mutex, MutexGuard,
        atomic::{AtomicBool, AtomicU64, Ordering},
    },
    thread,
    time::{Duration, Instant},
};
use zeroize::Zeroizing;

const OUTPUT_LIMIT: usize = 64 * 1024;
pub const TIMEOUT: Duration =
    Duration::from_secs(cadrumo_platform::DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS);
const PENDING_READERS: usize = 8;

fn milliseconds(duration: Duration) -> u64 {
    duration.as_millis().min(u128::from(u64::MAX)) as u64
}

struct Measurement {
    process: Option<u64>,
    stdout_bytes: u64,
    stderr_bytes: u64,
    started: Instant,
    timing: HelperTiming,
}
impl Measurement {
    fn new(kind: HelperKind) -> Self {
        Self {
            process: None,
            stdout_bytes: 0,
            stderr_bytes: 0,
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

/// The monotonic clock for one timeout across admission, spawn and execution.
/// Tests can move it while producer notifications wake the waiters.
#[derive(Default)]
struct Clock {
    #[cfg(test)]
    held: Mutex<Option<Instant>>,
}
impl Clock {
    fn now(&self) -> Instant {
        #[cfg(test)]
        if let Some(held) = *self.held.lock().unwrap_or_else(|e| e.into_inner()) {
            return held;
        }
        Instant::now()
    }
}

#[derive(Default)]
struct Active {
    busy: bool,
    pending_readers: usize,
    child: Option<Child>,
    process: Option<u64>,
    /// What the running child was started for, while it runs.
    identity: Option<HelperIdentity>,
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
    /// Set when the host begins to close: no further change starts, reads go on.
    changes_closed: AtomicBool,
    read: Lane,
    mutation: Lane,
    diagnostics: Arc<Diagnostics>,
    clock: Clock,
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
                    self.diagnostics
                        .finish_helper(process, status.code(), phase);
                }
                Ok(())
            }
            Ok(None) => Ok(()),
            Err(error) => Err(error),
        }
    }
    /// Refuses every further change, then waits until the change already running, if any,
    /// ends by itself or `deadline` passes. Reads are untouched. Returns what the change
    /// still running at `deadline` was started for; [`Children::stop`] then ends it, and
    /// its effect is unknown to this host.
    pub fn settle(&self, deadline: Instant) -> Option<HelperIdentity> {
        self.changes_closed.store(true, Ordering::Release);
        let lane = &self.mutation;
        let mut active = lane.active.lock().unwrap_or_else(|e| e.into_inner());
        // A child that has exited wakes the lane through its exit watch.
        while active.busy {
            let remaining = deadline.saturating_duration_since(self.clock.now());
            if remaining.is_zero() {
                return active.identity;
            }
            active = lane
                .changed
                .wait_timeout(active, remaining)
                .unwrap_or_else(|e| e.into_inner())
                .0;
        }
        None
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

    pub fn run(
        &self,
        identity: HelperIdentity,
        command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
    ) -> Result<Output> {
        self.execute(identity, command, secret, HelperKind::Mutation, TIMEOUT)
    }

    /// Run a mutation under the caller's existing command-specific deadline.
    pub fn run_within(
        &self,
        identity: HelperIdentity,
        command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        deadline: Duration,
    ) -> Result<Output> {
        self.execute(identity, command, secret, HelperKind::Mutation, deadline)
    }

    /// Read-only commands wait only for another read, independently of mutations.
    pub fn read(&self, identity: HelperIdentity, command: Command) -> Result<Output> {
        self.execute(identity, command, None, HelperKind::Read, TIMEOUT)
    }

    fn admit(&self, kind: HelperKind, deadline: Instant) -> Result<MutexGuard<'_, Active>> {
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
            if closed
                || (kind == HelperKind::Mutation && self.changes_closed.load(Ordering::Acquire))
            {
                Self::release_pending(&mut active, &mut pending);
                lane.changed.notify_all();
                return Err(closing());
            }
            if self.clock.now() >= deadline {
                Self::release_pending(&mut active, &mut pending);
                lane.changed.notify_all();
                return Err(failure(ErrorCode::TimedOut).with_reason("runtime_timeout"));
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
            let remaining = deadline.saturating_duration_since(self.clock.now());
            if remaining.is_zero() {
                Self::release_pending(&mut active, &mut pending);
                lane.changed.notify_all();
                return Err(failure(ErrorCode::TimedOut).with_reason("runtime_timeout"));
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
        identity: HelperIdentity,
        command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        kind: HelperKind,
        timeout: Duration,
    ) -> Result<Output> {
        let deadline = self.clock.now() + timeout;
        let mut measurement = Measurement::new(kind);
        let outcome =
            self.execute_measured(identity, command, secret, kind, deadline, &mut measurement);
        {
            let mut fact = match &outcome {
                Ok(output) => {
                    HelperResult::inspect(identity, output.success, &output.stdout, &output.stderr)
                }
                Err(_) => HelperResult::unavailable(
                    identity,
                    measurement.stdout_bytes,
                    measurement.stderr_bytes,
                ),
            };
            fact.stdout_bytes = measurement.stdout_bytes;
            fact.stderr_bytes = measurement.stderr_bytes;
            self.diagnostics.helper_result(
                measurement.process,
                fact,
                outcome.as_ref().err().cloned(),
            );
        }
        match &outcome {
            Ok(output) => {
                measurement.timing.outcome = if output.success {
                    HelperOutcome::Completed
                } else {
                    HelperOutcome::NonzeroExit
                };
            }
            // Refused or ended because the host is closing: an expected outcome.
            Err(error) if is_host_closing(error) => {
                measurement.timing.outcome = HelperOutcome::Interrupted;
            }
            Err(_) => {}
        }
        measurement.timing.total_ms = milliseconds(measurement.started.elapsed());
        self.diagnostics
            .helper_timing(measurement.process, measurement.timing);
        outcome
    }

    fn execute_measured(
        &self,
        identity: HelperIdentity,
        mut command: Command,
        secret: Option<Zeroizing<Vec<u8>>>,
        kind: HelperKind,
        deadline: Instant,
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
        let (process, stdin, stdout, stderr, start, watch, watch_error) = {
            let admission_started = Instant::now();
            let admission = self.admit(kind, deadline);
            let mut active = match admission {
                Ok(active) => active,
                Err(error) => {
                    measurement.timing.admission_wait_ms =
                        milliseconds(admission_started.elapsed());
                    // No OS spawn was attempted. Only the closed admission
                    // refusal leaves this boundary, never command or password.
                    // A closing host's refusal is its timing row, not a failure.
                    if !is_host_closing(&error) {
                        self.diagnostics.failure(error.clone());
                    }
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
                return Err(closing());
            }
            measurement.timing.outcome = HelperOutcome::SpawnFailed;
            let spawn_started = Instant::now();
            // The window's process scope holds the child and what it starts.
            #[cfg(unix)]
            let spawned = cadrumo_application::process::group::place(&mut command)
                .and_then(|()| cadrumo_application::process::creation::run(|| command.spawn()));
            #[cfg(windows)]
            let spawned = cadrumo_application::process::creation::run(|| command.spawn());
            measurement.timing.spawn_ms = Some(milliseconds(spawn_started.elapsed()));
            let mut child = match spawned {
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
            // Register while this exact child is retained and before it is published or reaped.
            let (watch, watch_error) = match ProcessExitWatch::for_child(&child) {
                Ok(watch) => (Some(watch), None),
                Err(error) => match child.try_wait() {
                    Ok(Some(_)) => (None, None),
                    _ => (None, Some(error)),
                },
            };
            let pid = child.id();
            active.busy = true;
            active.child = Some(child);
            active.identity = Some(identity);
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
            (
                process,
                pipes.0,
                pipes.1,
                pipes.2,
                start,
                watch,
                watch_error,
            )
        };
        // Admission and execution consume the same absolute owner timeout.
        let overflow = AtomicBool::new(false);
        let stdout_bytes = AtomicU64::new(0);
        let stderr_bytes = AtomicU64::new(0);
        let observed_error = Mutex::new(watch_error);
        let outcome: Result<Output> = thread::scope(|scope| {
            // Drop before scoped-thread joins on every return path, including failed cleanup.
            let _observation = WatchOwner(watch.as_ref());
            if let Some(watch) = watch.as_ref() {
                let observed_error = &observed_error;
                scope.spawn(move || {
                    if let Err(error) = watch.wait() {
                        *observed_error
                            .lock()
                            .unwrap_or_else(|error| error.into_inner()) = Some(error);
                    }
                    let _active = lane
                        .active
                        .lock()
                        .unwrap_or_else(|error| error.into_inner());
                    lane.changed.notify_all();
                });
            }
            let writer = scope.spawn(move || -> Result<()> {
                if let (Some(mut stdin), Some(secret)) = (stdin, secret) {
                    // Exactly one payload, followed by EOF; never retry login.
                    stdin
                        .write_all(&secret)
                        .map_err(|cause| failure(ErrorCode::WriteFailed).caused_by(cause))?;
                }
                Ok(())
            });
            let wake = || {
                let _active = lane
                    .active
                    .lock()
                    .unwrap_or_else(|error| error.into_inner());
                lane.changed.notify_all();
            };
            let out = {
                let overflow = &overflow;
                let bytes = &stdout_bytes;
                scope.spawn(move || read(stdout, overflow, bytes, wake))
            };
            let err = {
                let overflow = &overflow;
                let bytes = &stderr_bytes;
                scope.spawn(move || read(stderr, overflow, bytes, wake))
            };
            let status = self.wait(lane, &overflow, &observed_error, deadline);
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
            drop(_observation);
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
        measurement.stdout_bytes = stdout_bytes.load(Ordering::Relaxed);
        measurement.stderr_bytes = stderr_bytes.load(Ordering::Relaxed);
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
                    .finish_helper(process, status.code(), ProcessPhase::Exited);
            }
            active.child = None;
            active.identity = None;
            active.busy = false;
            lane.changed.notify_all();
        }
        if let Err(error) = &outcome
            && !is_host_closing(error)
        {
            self.diagnostics.failure_for(process, error.clone());
        }
        outcome
    }

    fn wait(
        &self,
        lane: &Lane,
        overflow: &AtomicBool,
        observed_error: &Mutex<Option<std::io::Error>>,
        deadline: Instant,
    ) -> Result<ExitStatus> {
        let mut active = lane
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        loop {
            if self.is_closed()? {
                return Err(closing());
            }
            if overflow.load(Ordering::Acquire) {
                return Err(failure(ErrorCode::OutputLimit));
            }
            // A snapshot follows a producer wake; this is never a periodic process poll.
            if let Some(status) = active
                .child
                .as_mut()
                .unwrap()
                .try_wait()
                .map_err(|cause| failure(ErrorCode::CleanupFailed).caused_by(cause))?
            {
                return Ok(status);
            }
            if let Some(error) = observed_error
                .lock()
                .unwrap_or_else(|error| error.into_inner())
                .take()
            {
                return Err(failure(ErrorCode::ReadFailed).caused_by(error));
            }
            let remaining = deadline.saturating_duration_since(self.clock.now());
            if remaining.is_zero() {
                return Err(failure(ErrorCode::TimedOut).with_reason("runtime_timeout"));
            }
            active = lane
                .changed
                .wait_timeout(active, remaining)
                .map_err(|_| failure(ErrorCode::LockPoisoned))?
                .0;
        }
    }
}

struct WatchOwner<'a>(Option<&'a ProcessExitWatch>);
impl Drop for WatchOwner<'_> {
    fn drop(&mut self) {
        if let Some(watch) = self.0 {
            let _ = watch.cancel();
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

fn read(
    mut pipe: impl Read,
    overflow: &AtomicBool,
    bytes: &AtomicU64,
    notify: impl Fn(),
) -> Result<Zeroizing<Vec<u8>>> {
    let mut output = Zeroizing::new(Vec::with_capacity(OUTPUT_LIMIT));
    let mut buffer = Zeroizing::new([0u8; 4096]);
    loop {
        let count = pipe
            .read(&mut *buffer)
            .map_err(|cause| failure(ErrorCode::ReadFailed).caused_by(cause))?;
        bytes.fetch_add(count as u64, Ordering::Relaxed);
        if count == 0 {
            return Ok(output);
        }
        if output.len() + count > OUTPUT_LIMIT {
            overflow.store(true, Ordering::Release);
            notify();
            return Err(failure(ErrorCode::OutputLimit));
        }
        output.extend_from_slice(&buffer[..count]);
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    #[cfg(windows)]
    pub(super) const TEST_IDENTITY: HelperIdentity = HelperIdentity {
        command: "config.login",
        executable: cadrumo_application::diagnostics::helper::HelperExecutable::Cli,
    };

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
            read(
                &vec![0; OUTPUT_LIMIT][..],
                &overflow,
                &AtomicU64::new(0),
                || {}
            )
            .unwrap()
            .len(),
            OUTPUT_LIMIT
        );
        assert_eq!(
            read(
                &vec![0; OUTPUT_LIMIT + 1][..],
                &overflow,
                &AtomicU64::new(0),
                || {}
            )
            .unwrap_err()
            .code,
            ErrorCode::OutputLimit
        );
        assert!(overflow.load(Ordering::Acquire));
    }

    #[cfg(unix)]
    const CHANGE: HelperIdentity = HelperIdentity {
        command: "config.profile.create",
        executable: cadrumo_application::diagnostics::helper::HelperExecutable::Cli,
    };

    #[cfg(unix)]
    fn shell(script: &str) -> Command {
        let mut command = Command::new("/bin/sh");
        command.args(["-c", script]);
        command
    }

    /// Returns once the change lane has published its running child.
    #[cfg(unix)]
    fn until_a_change_runs(children: &Children) {
        let deadline = Instant::now() + Duration::from_secs(10);
        while children.mutation.active.lock().unwrap().child.is_none() {
            assert!(Instant::now() < deadline, "the change never started");
            thread::sleep(Duration::from_millis(10));
        }
    }

    #[cfg(unix)]
    fn failures(children: &Children) -> Vec<ApplicationError> {
        children
            .diagnostics
            .snapshot(0)
            .events
            .into_iter()
            .filter(|event| {
                matches!(
                    event.kind,
                    cadrumo_application::diagnostics::EventKind::Failure
                )
            })
            .filter_map(|event| event.failure)
            .collect()
    }

    #[cfg(unix)]
    fn timings(children: &Children) -> Vec<HelperTiming> {
        children
            .diagnostics
            .snapshot(0)
            .events
            .into_iter()
            .filter_map(|event| event.helper_timing)
            .collect()
    }

    #[cfg(unix)]
    #[test]
    fn a_change_that_ends_within_the_settle_window_reports_its_own_outcome() {
        let children = Children::default();
        thread::scope(|scope| {
            let running =
                scope.spawn(|| children.run(CHANGE, shell("sleep 0.3; printf done"), None));
            until_a_change_runs(&children);
            let started = Instant::now();
            assert!(
                children
                    .settle(Instant::now() + Duration::from_secs(20))
                    .is_none()
            );
            // The window ended when the change did, not at its bound.
            assert!(started.elapsed() < Duration::from_secs(10));
            let output = running.join().unwrap().unwrap();
            assert!(output.success);
            assert_eq!(&output.stdout[..], b"done");
        });
        children.stop().unwrap();
        assert!(failures(&children).is_empty());
        assert_eq!(timings(&children)[0].outcome, HelperOutcome::Completed);
    }

    #[cfg(unix)]
    #[test]
    fn a_change_still_running_after_the_settle_window_is_ended_as_an_expected_interruption() {
        let children = Children::default();
        thread::scope(|scope| {
            let running = scope.spawn(|| children.run(CHANGE, shell("sleep 60"), None));
            until_a_change_runs(&children);
            let settled = children.settle(Instant::now() + Duration::from_millis(200));
            assert_eq!(
                settled.map(|identity| identity.command),
                Some(CHANGE.command)
            );
            let started = Instant::now();
            children.stop().unwrap();
            let ended = running.join().unwrap().err().unwrap();
            assert!(is_host_closing(&ended));
            assert!(started.elapsed() < Duration::from_secs(10));
        });
        assert!(failures(&children).is_empty(), "a close is not a failure");
        let timing = timings(&children)[0];
        assert_eq!(timing.helper_kind, HelperKind::Mutation);
        assert_eq!(timing.outcome, HelperOutcome::Interrupted);
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Terminated);
    }

    #[cfg(unix)]
    #[test]
    fn a_settling_window_refuses_new_changes_but_still_answers_reads() {
        let children = Children::default();
        assert!(children.settle(Instant::now()).is_none());
        let refused = children.run(CHANGE, shell("exit 0"), None).err().unwrap();
        assert!(is_host_closing(&refused));
        assert!(
            children
                .read(CHANGE, shell("printf status"))
                .unwrap()
                .success
        );
        children.stop().unwrap();
        let after = children.read(CHANGE, shell("exit 0")).err().unwrap();
        assert!(is_host_closing(&after));
        assert!(failures(&children).is_empty());
        let outcomes: Vec<_> = timings(&children)
            .into_iter()
            .map(|timing| timing.outcome)
            .collect();
        assert_eq!(
            outcomes,
            [
                HelperOutcome::Interrupted,
                HelperOutcome::Completed,
                HelperOutcome::Interrupted
            ]
        );
    }

    /// Bounds only a fixture that never arrives; arriving is the event awaited.
    #[cfg(windows)]
    pub(crate) const HANG_GUARD: Duration = Duration::from_secs(120);

    /// A handshake with one fixture child, apart from its pipes: the child
    /// reports where it has reached and blocks there until the test lets it go.
    #[cfg(windows)]
    pub(crate) struct Gate {
        port: u16,
        accepted: std::sync::mpsc::Receiver<std::net::TcpStream>,
        stream: Option<(std::io::BufReader<std::net::TcpStream>, std::net::TcpStream)>,
    }

    #[cfg(windows)]
    impl Gate {
        pub(crate) fn new() -> Self {
            let listener = std::net::TcpListener::bind(("127.0.0.1", 0)).unwrap();
            let port = listener.local_addr().unwrap().port();
            let (connected, accepted) = std::sync::mpsc::channel();
            thread::spawn(move || {
                if let Ok((stream, _)) = listener.accept() {
                    let _ = connected.send(stream);
                }
            });
            Self {
                port,
                accepted,
                stream: None,
            }
        }

        /// PowerShell defining `Wait-Gate <point>`, which reports `point` and
        /// returns once the test lets it go.
        pub(crate) fn script(&self) -> String {
            format!(
                "function Wait-Gate($point) {{ \
                     if (-not $script:gate) {{ \
                         $script:gate = New-Object System.Net.Sockets.TcpClient('127.0.0.1', {}); \
                         $stream = $script:gate.GetStream(); \
                         $script:gateIn = New-Object System.IO.StreamReader($stream); \
                         $script:gateOut = New-Object System.IO.StreamWriter($stream); \
                         $script:gateOut.AutoFlush = $true }}; \
                     $script:gateOut.WriteLine($point); \
                     if ($script:gateIn.ReadLine() -ne 'go') {{ exit 9 }} }}; ",
                self.port
            )
        }

        /// Returns once the child reports `point`; it stays blocked there.
        pub(crate) fn reached(&mut self, point: &str) {
            use std::io::BufRead;
            if self.stream.is_none() {
                let stream = self
                    .accepted
                    .recv_timeout(HANG_GUARD)
                    .expect("the fixture child never reached its gate");
                stream.set_read_timeout(Some(HANG_GUARD)).unwrap();
                self.stream = Some((std::io::BufReader::new(stream.try_clone().unwrap()), stream));
            }
            let (reader, _) = self.stream.as_mut().unwrap();
            let mut line = String::new();
            reader.read_line(&mut line).unwrap();
            assert_eq!(line.trim_end(), point);
        }

        /// Lets a child that has reached its gate go on.
        pub(crate) fn go(&mut self) {
            let (_, writer) = self.stream.as_mut().expect("let go only once reached");
            writer.write_all(b"go\n").unwrap();
        }
    }

    #[cfg(windows)]
    impl Children {
        /// Holds the clock still, so only the test moves time on.
        fn hold_clock(&self) {
            *self.clock.held.lock().unwrap() = Some(Instant::now());
        }

        /// Moves the held clock on while `lane`'s waiters cannot miss it.
        fn advance(&self, lane: &Lane, by: Duration) {
            let _active = lane.active.lock().unwrap();
            let mut held = self.clock.held.lock().unwrap();
            *held = Some(held.expect("the clock is held") + by);
            lane.changed.notify_all();
        }

        /// Returns once a read is waiting for its turn on the read lane.
        fn until_a_read_queues(&self) {
            let active = self.read.active.lock().unwrap();
            let (_active, waited) = self
                .read
                .changed
                .wait_timeout_while(active, HANG_GUARD, |active| active.pending_readers == 0)
                .unwrap();
            assert!(!waited.timed_out(), "no read ever queued");
        }
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
            "-WindowStyle",
            "Hidden",
            "-Command",
            script,
        ]);
        // A fixture child never opens a console window, whoever spawns it.
        std::os::windows::process::CommandExt::creation_flags(&mut command, 0x0800_0000);
        command
    }

    #[cfg(windows)]
    #[test]
    fn real_child_receives_one_secret_and_eof_without_output_logging() {
        let children = Children::default();
        let output = children
            .run(
                TEST_IDENTITY,
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
        assert_eq!(
            snapshot
                .events
                .iter()
                .find_map(|event| event.helper_timing)
                .unwrap()
                .outcome,
            HelperOutcome::Completed
        );
        assert!(snapshot.output.is_empty());
        assert!(
            !serde_json::to_string(&snapshot.events)
                .unwrap()
                .contains("secret-channel-probe")
        );
    }

    #[cfg(windows)]
    #[test]
    fn nonzero_exit_is_reported_without_discarding_the_sign_in_refusal() {
        use super::super::wire;
        let children = Children::default();
        let envelope = serde_json::json!({
            "schema_version": "2", "command": "config.login", "status": "error",
            "active_profile": "synthetic-private-profile",
            "error": {"code": "REFUSED_CLI", "context": {"reason": "THROTTLED", "seconds": "9"}}
        });
        let script = format!("[Console]::Error.WriteLine('{envelope}'); exit 2");
        let output = children
            .run(TEST_IDENTITY, powershell(&script), None)
            .unwrap();
        assert!(!output.success);
        let wire::SignInResult::Refused { refusal } =
            wire::login(wire::decode("login", &output).unwrap()).unwrap()
        else {
            panic!("canonical refusal must survive nonzero exit");
        };
        assert_eq!(refusal.code, "THROTTLED");
        assert_eq!(refusal.retry_after_seconds, Some(9));
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].exit_code, Some(2));
        let timing = snapshot
            .events
            .iter()
            .find_map(|event| event.helper_timing)
            .unwrap();
        assert_eq!(timing.outcome, HelperOutcome::NonzeroExit);
        // The process tracker still records its nonzero exit; the transport
        // must not turn the useful refusal envelope into an execution error.
        assert!(
            snapshot
                .events
                .iter()
                .filter_map(|event| event.failure.as_ref())
                .all(|error| error.code == ErrorCode::ChildFailed)
        );
        assert!(
            !serde_json::to_string(&snapshot.events)
                .unwrap()
                .contains("synthetic-private-profile")
        );
    }

    #[cfg(windows)]
    #[test]
    fn explicit_mutation_runs_while_the_separate_activity_owner_is_busy() {
        let activity = Children::default();
        let explicit = Children::default();
        thread::scope(|scope| {
            let renewal = scope
                .spawn(|| activity.run(TEST_IDENTITY, powershell("Start-Sleep -Seconds 30"), None));
            let deadline = Instant::now() + Duration::from_secs(5);
            while activity.mutation.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < deadline);
                thread::sleep(Duration::from_millis(10));
            }
            let logout = explicit
                .run(
                    TEST_IDENTITY,
                    powershell("[Console]::Out.Write('logged-out')"),
                    None,
                )
                .unwrap();
            assert_eq!(&*logout.stdout, b"logged-out");
            explicit.stop().unwrap();
            activity.stop().unwrap();
            assert!(renewal.join().unwrap().is_err());
        });
        assert!(activity.mutation.active.lock().unwrap().child.is_none());
        assert!(explicit.mutation.active.lock().unwrap().child.is_none());
    }

    #[cfg(windows)]
    #[test]
    fn status_reads_independently_and_duplicate_mutations_never_replay_a_password() {
        let children = Children::default();
        thread::scope(|scope| {
            let mutation = scope.spawn(|| children.run(TEST_IDENTITY,
                powershell("$value=[Console]::In.ReadToEnd(); Start-Sleep -Milliseconds 600; [Console]::Out.Write($value)"),
                Some(Zeroizing::new(b"one-password".to_vec())),
            ));
            let deadline = Instant::now() + Duration::from_secs(5);
            while children.mutation.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < deadline);
                thread::sleep(Duration::from_millis(10));
            }
            let status = scope.spawn(|| {
                children.read(TEST_IDENTITY, powershell("[Console]::Out.Write('status')"))
            });
            assert_eq!(
                children
                    .run(
                        TEST_IDENTITY,
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
            let running = scope
                .spawn(|| children.run(TEST_IDENTITY, powershell("Start-Sleep -Seconds 60"), None));
            let deadline = Instant::now() + Duration::from_secs(5);
            while children.mutation.active.lock().unwrap().child.is_none() {
                assert!(Instant::now() < deadline);
                thread::sleep(Duration::from_millis(10));
            }
            let start = Instant::now();
            children.stop().unwrap();
            let stopped_read = children.read(TEST_IDENTITY, powershell("exit 0"));
            assert!(running.join().unwrap().is_err());
            assert_eq!(
                stopped_read.err().unwrap().code,
                ErrorCode::SessionUnavailable
            );
            assert!(start.elapsed() < Duration::from_secs(5));
        });
        assert!(children.mutation.active.lock().unwrap().child.is_none());
        assert!(
            children
                .run(TEST_IDENTITY, powershell("exit 0"), None)
                .is_err()
        );
        let snapshot = children.diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Terminated);
        assert!(snapshot.output.is_empty());
    }

    #[cfg(windows)]
    #[test]
    fn a_helper_timeout_contains_the_child_and_preserves_diagnostics() {
        let children = Children::default();
        // Longer than the one it is given: stopped, reaped, and said so.
        let start = Instant::now();
        let late = children.run_within(
            TEST_IDENTITY,
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
        assert!(timing.total_ms >= 400);
        assert!(timing.cleanup_ms.is_some() && timing.output_join_ms.is_some());
        // Within the one it is given: it runs to its end.
        let output = children
            .run_within(
                TEST_IDENTITY,
                powershell("Start-Sleep -Milliseconds 900; [Console]::Out.Write('made')"),
                None,
                Duration::from_secs(30),
            )
            .unwrap();
        assert_eq!(&*output.stdout, b"made");
    }

    #[cfg(windows)]
    #[test]
    fn queued_read_and_execution_consume_the_same_timeout() {
        let children = Children::default();
        children.hold_clock();
        let mut gate = Gate::new();
        let mut executing = Gate::new();
        let script = format!("{}Wait-Gate 'running'", gate.script());
        let queued_script = format!("{}Wait-Gate 'executing'", executing.script());
        thread::scope(|scope| {
            let slow = scope.spawn(|| children.read(TEST_IDENTITY, powershell(&script)));
            gate.reached("running");
            let queued = scope.spawn(|| {
                children.execute(
                    TEST_IDENTITY,
                    powershell(&queued_script),
                    None,
                    HelperKind::Read,
                    Duration::from_secs(8),
                )
            });
            children.until_a_read_queues();
            children.advance(&children.read, Duration::from_secs(4));
            gate.go();
            executing.reached("executing");
            // Four seconds spent awaiting capacity leave four for execution.
            children.advance(&children.read, Duration::from_secs(4));
            let error = queued.join().unwrap().err().unwrap();
            assert_eq!(error.code, ErrorCode::TimedOut);
            assert_eq!(error.reason.as_deref(), Some("runtime_timeout"));
            assert!(slow.join().unwrap().is_ok());
        });
        assert!(children.read.active.lock().unwrap().child.is_none());
    }

    #[cfg(windows)]
    #[test]
    fn a_read_waits_past_the_former_slot_limit_for_the_capacity_signal() {
        let children = Children::default();
        children.hold_clock();
        let mut gate = Gate::new();
        let script = format!("{}Wait-Gate 'running'", gate.script());
        thread::scope(|scope| {
            let slow = scope.spawn(|| children.read(TEST_IDENTITY, powershell(&script)));
            gate.reached("running");
            let queued = scope.spawn(|| {
                children.read(TEST_IDENTITY, powershell("[Console]::Out.Write('status')"))
            });
            children.until_a_read_queues();
            children.advance(&children.read, Duration::from_secs(331));
            gate.go();
            assert_eq!(&*queued.join().unwrap().unwrap().stdout, b"status");
            assert!(slow.join().unwrap().is_ok());
        });
        assert!(children.read.active.lock().unwrap().child.is_none());
    }

    #[cfg(windows)]
    #[test]
    fn real_flood_is_bounded_and_the_child_is_reaped() {
        let children = Children::default();
        let result = children.run(
            TEST_IDENTITY,
            powershell("while ($true) { [Console]::Out.Write(('x' * 8192)) }"),
            None,
        );
        assert_eq!(result.err().unwrap().code, ErrorCode::OutputLimit);
        assert!(children.mutation.active.lock().unwrap().child.is_none());
    }
}

#[cfg(all(test, windows))]
mod admission_tests;
