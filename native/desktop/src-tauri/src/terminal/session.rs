//! One PTY child with its input, output and exit workers.
//!
//! Output flows to a frame sink under credit backpressure. A finisher thread
//! owns the child: after it exits the finisher closes the PTY, joins the
//! reader and writer, and only then reports `exited`, so the exit frame never
//! overtakes output. Settlement requests a stop, kills the child and waits a
//! bounded time for the finisher; workers that miss the deadline stay owned.
//! A frame the sink cannot deliver means nothing observes the session any
//! more, so the session stops itself the same way.
use super::{
    credit::{Admission, Credit},
    frame::Frame,
};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process::status::{ProcessPhase, ProcessRole},
};
use portable_pty::{ChildKiller, CommandBuilder, MasterPty, PtySize, native_pty_system};
use std::{
    collections::BTreeMap,
    ffi::OsString,
    io::{Read, Write},
    path::PathBuf,
    sync::{
        Arc, Mutex, MutexGuard,
        atomic::{AtomicBool, Ordering},
        mpsc::{self, RecvTimeoutError, SyncSender, TrySendError},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

/// PTY output is read and delivered in chunks of at most this size.
pub const CHUNK: usize = 8192;
/// Pending input writes per session.
pub const INPUT_QUEUE: usize = 8;
/// The largest single input write.
pub const INPUT_LIMIT: usize = 64 * 1024;
/// The bound on settling one session.
pub const SETTLE_TIMEOUT: Duration = Duration::from_secs(3);

/// Receives encoded frames in send order.
pub type Sink = Arc<dyn Fn(Vec<u8>) -> Result<()> + Send + Sync>;

pub fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Terminal)
}

pub fn size(cols: u16, rows: u16) -> Result<PtySize> {
    if !(2..=1000).contains(&cols) || !(2..=1000).contains(&rows) {
        return Err(failure(ErrorCode::InvalidArguments));
    }
    Ok(PtySize {
        rows,
        cols,
        pixel_width: 0,
        pixel_height: 0,
    })
}

/// A fully resolved child launch: absolute program, arguments, directory and
/// the complete environment, never merged with the host's own.
pub struct Program {
    pub executable: PathBuf,
    pub arguments: Vec<OsString>,
    pub directory: PathBuf,
    pub environment: BTreeMap<OsString, OsString>,
    pub role: ProcessRole,
}

type Master = Arc<Mutex<Option<Box<dyn MasterPty + Send>>>>;

type Killer = Box<dyn ChildKiller + Send + Sync>;

/// State shared between the session handle and its workers.
struct Shared {
    process: u64,
    credit: Credit,
    input_stopped: AtomicBool,
    stop_requested: AtomicBool,
    exited: AtomicBool,
    write_error: Mutex<Option<ApplicationError>>,
    /// Terminates the child when a worker abandons the session.
    killer: Mutex<Killer>,
}

impl Shared {
    fn new(killer: Killer, process: u64) -> Self {
        Self {
            process,
            credit: Credit::default(),
            input_stopped: AtomicBool::new(false),
            stop_requested: AtomicBool::new(false),
            exited: AtomicBool::new(false),
            write_error: Mutex::new(None),
            killer: Mutex::new(killer),
        }
    }

    fn write_error(&self) -> MutexGuard<'_, Option<ApplicationError>> {
        self.write_error.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Stops the session from inside a worker after its output could not be
    /// delivered: input and output stop and a running child is terminated.
    /// The finisher then reports the session as terminated and joins every
    /// worker, so the registry settles it without waiting.
    fn abandon(&self, diagnostics: &Diagnostics) {
        if self.stop_requested.swap(true, Ordering::AcqRel) {
            return;
        }
        self.input_stopped.store(true, Ordering::Release);
        self.credit.stop();
        if !self.exited.load(Ordering::Acquire)
            && let Err(error) = self.killer.lock().unwrap_or_else(|e| e.into_inner()).kill()
        {
            diagnostics.failure_for(
                self.process,
                failure(ErrorCode::CleanupFailed).caused_by(error),
            );
        }
    }
}

#[derive(Default)]
struct Workers {
    reader: Option<JoinHandle<()>>,
    writer: Option<JoinHandle<()>>,
}

pub struct Session {
    shared: Arc<Shared>,
    input: SyncSender<Vec<u8>>,
    master: Master,
    killer: Box<dyn ChildKiller + Send + Sync>,
    kill_error: Option<ApplicationError>,
    finisher: Option<JoinHandle<Result<()>>>,
    settled: bool,
    diagnostics: Arc<Diagnostics>,
}

fn take_master(master: &Master) -> Option<Box<dyn MasterPty + Send>> {
    master.lock().unwrap_or_else(|e| e.into_inner()).take()
}

/// End of output: ConPTY reports EOF; a Linux PTY master reports EIO once the
/// last slave descriptor closes.
fn end_of_output(error: &std::io::Error) -> bool {
    cfg!(unix) && error.raw_os_error() == Some(5)
}

/// Sends one frame; a frame that cannot be delivered abandons the session.
fn deliver(sink: &Sink, frame: Frame<'_>, shared: &Shared, diagnostics: &Diagnostics) {
    if let Err(error) = frame.encode().and_then(|bytes| sink(bytes)) {
        diagnostics.failure_for(shared.process, error);
        shared.abandon(diagnostics);
    }
}

impl Session {
    pub fn start(
        program: Program,
        cols: u16,
        rows: u16,
        sink: Sink,
        diagnostics: Arc<Diagnostics>,
    ) -> Result<Self> {
        let pair = native_pty_system()
            .openpty(size(cols, rows)?)
            .map_err(|cause| {
                let error = failure(ErrorCode::SpawnFailed).caused_by(std::io::Error::other(cause));
                diagnostics.spawn_failure(program.role, error.clone());
                error
            })?;
        let mut command = CommandBuilder::new(&program.executable);
        command.env_clear();
        for (key, value) in &program.environment {
            command.env(key, value);
        }
        command.env("TERM", "xterm-256color");
        command.env("COLORTERM", "truecolor");
        command.cwd(&program.directory);
        command.args(&program.arguments);
        let mut reader = pair.master.try_clone_reader().map_err(|cause| {
            let error = failure(ErrorCode::ReadFailed).caused_by(std::io::Error::other(cause));
            diagnostics.spawn_failure(program.role, error.clone());
            error
        })?;
        let mut writer = pair.master.take_writer().map_err(|cause| {
            let error = failure(ErrorCode::WriteFailed).caused_by(std::io::Error::other(cause));
            diagnostics.spawn_failure(program.role, error.clone());
            error
        })?;
        let mut child = pair.slave.spawn_command(command).map_err(|cause| {
            let error = failure(ErrorCode::SpawnFailed).caused_by(std::io::Error::other(cause));
            diagnostics.spawn_failure(program.role, error.clone());
            error
        })?;
        drop(pair.slave);
        let pid = child.process_id().unwrap_or(0);
        let process = diagnostics.start(pid, program.role);
        let mut killer = child.clone_killer();
        let master: Master = Arc::new(Mutex::new(Some(pair.master)));
        let shared = Arc::new(Shared::new(child.clone_killer(), process));
        let (deliver_workers, workers) = mpsc::sync_channel::<Workers>(1);
        let finisher = {
            let shared = shared.clone();
            let master = master.clone();
            let sink = sink.clone();
            let diagnostics = diagnostics.clone();
            thread::Builder::new()
                .name("terminal-exit".into())
                .spawn(move || {
                    let status = child.wait();
                    let stopped = shared.stop_requested.load(Ordering::Acquire);
                    shared.exited.store(true, Ordering::Release);
                    shared.input_stopped.store(true, Ordering::Release);
                    // ConPTY reports end of output only once the pseudoconsole
                    // closes; the reader keeps draining meanwhile.
                    drop(take_master(&master));
                    let mut outcome = Ok(());
                    let Workers { reader, writer } = workers.recv().unwrap_or_default();
                    for worker in [reader, writer].into_iter().flatten() {
                        if worker.join().is_err() {
                            outcome = Err(failure(ErrorCode::Panic));
                        }
                    }
                    let code = status.as_ref().ok().map(|status| status.exit_code());
                    let wait_error = status
                        .err()
                        .map(|e| failure(ErrorCode::ReadFailed).caused_by(e));
                    let write_error = shared.write_error().clone();
                    for error in [&wait_error, &write_error].into_iter().flatten() {
                        diagnostics.failure_for(process, error.clone());
                    }
                    if !shared.credit.stopped() {
                        for error in [&wait_error, &write_error].into_iter().flatten() {
                            deliver(&sink, Frame::Failed(error), &shared, &diagnostics);
                        }
                        deliver(&sink, Frame::Exited { code }, &shared, &diagnostics);
                    }
                    let phase = match (&wait_error, stopped) {
                        (Some(_), _) => ProcessPhase::Failed,
                        (None, true) => ProcessPhase::Terminated,
                        (None, false) => ProcessPhase::Exited,
                    };
                    diagnostics.finish(process, code.map(|code| code as i32), phase);
                    outcome
                })
        };
        let finisher = match finisher {
            Ok(finisher) => finisher,
            Err(error) => {
                // Nothing can wait for this child; terminate it and close the PTY.
                if let Err(kill) = killer.kill() {
                    diagnostics
                        .failure_for(process, failure(ErrorCode::CleanupFailed).caused_by(kill));
                }
                drop(take_master(&master));
                diagnostics.finish(process, None, ProcessPhase::Failed);
                let error = failure(ErrorCode::SpawnFailed).caused_by(error);
                diagnostics.failure_for(process, error.clone());
                return Err(error);
            }
        };
        let (input, queued) = mpsc::sync_channel::<Vec<u8>>(INPUT_QUEUE);
        // From here the session owns cleanup: dropping it on any error settles the child.
        let session = Self {
            shared: shared.clone(),
            input,
            master,
            killer,
            kill_error: None,
            finisher: Some(finisher),
            settled: false,
            diagnostics: diagnostics.clone(),
        };
        deliver(&sink, Frame::Started { pid }, &shared, &diagnostics);
        let mut spawned = Workers::default();
        let outcome: Result<()> = (|| {
            let input_shared = shared.clone();
            spawned.writer = Some(
                thread::Builder::new()
                    .name("terminal-input".into())
                    .spawn(move || {
                        while !input_shared.input_stopped.load(Ordering::Acquire) {
                            match queued.recv_timeout(Duration::from_millis(50)) {
                                Ok(bytes) => {
                                    if let Err(error) =
                                        writer.write_all(&bytes).and_then(|()| writer.flush())
                                    {
                                        *input_shared.write_error() =
                                            Some(failure(ErrorCode::WriteFailed).caused_by(error));
                                        break;
                                    }
                                }
                                Err(RecvTimeoutError::Timeout) => continue,
                                Err(RecvTimeoutError::Disconnected) => break,
                            }
                        }
                    })
                    .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(e))?,
            );
            let output_shared = shared.clone();
            let output_diagnostics = diagnostics.clone();
            spawned.reader = Some(
                thread::Builder::new()
                    .name("terminal-output".into())
                    .spawn(move || {
                        let credit = &output_shared.credit;
                        let mut buffer = [0; CHUNK];
                        loop {
                            credit.wait();
                            match reader.read(&mut buffer) {
                                Ok(0) => break,
                                Ok(count) => {
                                    if credit.admit(count) == Admission::Deliver {
                                        deliver(
                                            &sink,
                                            Frame::Data(&buffer[..count]),
                                            &output_shared,
                                            &output_diagnostics,
                                        );
                                    }
                                }
                                Err(error) if error.kind() == std::io::ErrorKind::Interrupted => {}
                                Err(error) if end_of_output(&error) => break,
                                Err(error) => {
                                    let error = failure(ErrorCode::ReadFailed).caused_by(error);
                                    if !credit.stopped() {
                                        deliver(
                                            &sink,
                                            Frame::Failed(&error),
                                            &output_shared,
                                            &output_diagnostics,
                                        );
                                    }
                                    output_diagnostics.failure_for(process, error);
                                    break;
                                }
                            }
                        }
                    })
                    .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(e))?,
            );
            Ok(())
        })();
        // The finisher joins whatever was spawned, even after a failure here.
        if deliver_workers.send(spawned).is_err() {
            session
                .diagnostics
                .failure_for(process, failure(ErrorCode::Panic));
        }
        if let Err(error) = &outcome {
            diagnostics.failure_for(process, error.clone());
        }
        outcome.map(|()| session)
    }

    /// Output bytes counted toward the credit window.
    #[cfg(all(test, feature = "live-package-tests"))]
    pub fn delivered(&self) -> u64 {
        self.shared.credit.sent()
    }

    #[cfg(all(test, feature = "live-package-tests"))]
    pub fn paused(&self) -> bool {
        self.shared.credit.paused()
    }

    /// Whether the session still accepts input and owns a running child.
    pub fn live(&self) -> bool {
        !self.shared.stop_requested.load(Ordering::Acquire)
            && self.finisher.as_ref().is_some_and(|f| !f.is_finished())
    }

    pub fn record<T>(&self, outcome: Result<T>) -> Result<T> {
        if let Err(error) = &outcome
            && error.code != ErrorCode::QueueFull
        {
            self.diagnostics
                .failure_for(self.shared.process, error.clone());
        }
        outcome
    }

    pub fn write(&self, bytes: &[u8]) -> Result<()> {
        if bytes.len() > INPUT_LIMIT {
            return Err(failure(ErrorCode::InvalidArguments));
        }
        if let Some(error) = self.shared.write_error().clone() {
            return Err(error);
        }
        if self.shared.input_stopped.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        if bytes.is_empty() {
            return Ok(());
        }
        self.input
            .try_send(bytes.to_vec())
            .map_err(|error| match error {
                TrySendError::Full(_) => failure(ErrorCode::QueueFull),
                TrySendError::Disconnected(_) => failure(ErrorCode::SessionUnavailable),
            })
    }

    pub fn acknowledge(&self, offset: u64) -> Result<()> {
        self.shared.credit.acknowledge(offset)
    }

    pub fn resize(&self, cols: u16, rows: u16) -> Result<()> {
        let size = size(cols, rows)?;
        self.master
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?
            .as_ref()
            .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
            .resize(size)
            .map_err(|e| failure(ErrorCode::ResizeFailed).caused_by(std::io::Error::other(e)))
    }

    /// Stops output delivery and input, and terminates a running child.
    /// Repeatable: a retry after a missed deadline kills again.
    pub fn request_stop(&mut self) {
        if self.settled {
            return;
        }
        self.shared.stop_requested.store(true, Ordering::Release);
        self.shared.input_stopped.store(true, Ordering::Release);
        // A paused reader resumes and discards, so the PTY drains while it closes.
        self.shared.credit.stop();
        if !self.shared.exited.load(Ordering::Acquire) {
            // A child that exits concurrently can refuse termination; only a
            // missed settlement deadline makes this error the reported cause.
            self.kill_error = self
                .killer
                .kill()
                .err()
                .map(|e| failure(ErrorCode::CleanupFailed).caused_by(e));
        }
    }

    /// Waits until the finisher has joined every worker, or the deadline.
    pub fn await_stop(&mut self, deadline: Instant) -> Result<()> {
        loop {
            if self.settled {
                return Ok(());
            }
            if self.finisher.as_ref().is_none_or(JoinHandle::is_finished) {
                let outcome = match self.finisher.take() {
                    Some(finisher) => finisher
                        .join()
                        .unwrap_or_else(|_| Err(failure(ErrorCode::Panic))),
                    None => Ok(()),
                };
                // Every worker is joined, so cleanup is confirmed even when one
                // of them panicked; that panic is reported, not retried.
                self.settled = true;
                self.kill_error = None;
                if let Err(error) = outcome {
                    self.diagnostics.failure_for(self.shared.process, error);
                }
                return Ok(());
            }
            if Instant::now() >= deadline {
                let error = self
                    .kill_error
                    .clone()
                    .unwrap_or_else(|| failure(ErrorCode::CleanupFailed));
                self.diagnostics
                    .failure_for(self.shared.process, error.clone());
                return Err(error);
            }
            thread::sleep(Duration::from_millis(5));
        }
    }

    pub fn stop(&mut self) -> Result<()> {
        self.request_stop();
        self.await_stop(Instant::now() + SETTLE_TIMEOUT)
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        if let Err(error) = self.stop() {
            // Normal settlement keeps a failed session owned. Unexpected host
            // destruction cannot establish joined cleanup; report it.
            self.diagnostics.failure_for(self.shared.process, error);
        }
    }
}
