mod ipc;

use crate::{app::Commands, environment::Launch};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process::status::{ProcessPhase, ProcessRole, Stream},
};
use portable_pty::{Child, CommandBuilder, MasterPty, PtySize, native_pty_system};
use serde::Serialize;
use std::{
    io::{Read, Write},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver, RecvTimeoutError, SyncSender, TryRecvError, TrySendError},
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
use tauri::{Runtime, plugin::TauriPlugin};

pub fn plugin<R: Runtime>(_launch: &Launch) -> TauriPlugin<R> {
    tauri::plugin::Builder::new("cadrumo-terminal").build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    ipc::commands()
}

const CHUNK: usize = 8192;
const QUEUE: usize = 8;
fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Terminal)
}
const STOP_TIMEOUT: Duration = Duration::from_secs(3);

#[derive(Default)]
struct Workers {
    reader: Option<JoinHandle<()>>,
    writer: Option<JoinHandle<()>>,
    closer: Option<JoinHandle<()>>,
}

impl Workers {
    fn reap_finished(&mut self) -> Result<bool> {
        for worker in [&mut self.reader, &mut self.writer, &mut self.closer] {
            if worker.as_ref().is_some_and(JoinHandle::is_finished) {
                worker
                    .take()
                    .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
                    .join()
                    .map_err(|_| failure(ErrorCode::Panic))?;
            }
        }
        Ok(self.reader.is_none() && self.writer.is_none() && self.closer.is_none())
    }

    fn join_until(&mut self, deadline: Instant) -> Result<()> {
        loop {
            if self.reap_finished()? {
                return Ok(());
            }
            if Instant::now() >= deadline {
                return Err(failure(ErrorCode::CleanupFailed));
            }
            thread::sleep(Duration::from_millis(5));
        }
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Output {
    pub bytes: Vec<u8>,
    pub exit_code: Option<u32>,
    pub error: Option<ApplicationError>,
}

enum ReadEvent {
    Bytes(Vec<u8>),
    Error(ApplicationError),
}

pub struct Session {
    master: Option<Box<dyn MasterPty + Send>>,
    writer: SyncSender<Vec<u8>>,
    write_error: Arc<Mutex<Option<ApplicationError>>>,
    child: Box<dyn Child + Send + Sync>,
    output: Receiver<ReadEvent>,
    stopped: Arc<AtomicBool>,
    writer_stopped: Arc<AtomicBool>,
    workers: Workers,
    cleanup_error: Option<ApplicationError>,
    exit_code: Option<u32>,
    diagnostics: Arc<Diagnostics>,
    process: u64,
    tracked_exit: bool,
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

impl Session {
    pub fn start(launch: &Launch, cols: u16, rows: u16, args: &[&str]) -> Result<Self> {
        let pair = native_pty_system()
            .openpty(size(cols, rows)?)
            .map_err(|e| failure(ErrorCode::ReadFailed).caused_by(std::io::Error::other(e)))?;
        let mut command = CommandBuilder::new(launch.child.executable());
        command.env_clear();
        for (key, value) in launch.child.environment() {
            command.env(key, value);
        }
        command.env("TERM", "xterm-256color");
        command.env("COLORTERM", "truecolor");
        command.cwd(&launch.working_directory);
        command.args(args);
        let mut reader = pair
            .master
            .try_clone_reader()
            .map_err(|e| failure(ErrorCode::ReadFailed).caused_by(std::io::Error::other(e)))?;
        let mut writer = pair
            .master
            .take_writer()
            .map_err(|e| failure(ErrorCode::WriteFailed).caused_by(std::io::Error::other(e)))?;
        let child = pair
            .slave
            .spawn_command(command)
            .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(std::io::Error::other(e)))?;
        drop(pair.slave);
        let diagnostics = launch.diagnostics.clone();
        let process = diagnostics.start(child.process_id().unwrap_or(0), ProcessRole::Tui);
        let (sender, output) = mpsc::sync_channel(QUEUE);
        let stopped = Arc::new(AtomicBool::new(false));
        let (input_sender, input_receiver) = mpsc::sync_channel::<Vec<u8>>(QUEUE);
        let write_error = Arc::new(Mutex::new(None));
        let write_failure = write_error.clone();
        let writer_stopped = Arc::new(AtomicBool::new(false));
        let writer_stop = writer_stopped.clone();
        // Establish cleanup ownership before worker creation can fail or unwind.
        let mut session = Self {
            master: Some(pair.master),
            writer: input_sender,
            write_error,
            child,
            output,
            stopped: stopped.clone(),
            writer_stopped,
            workers: Workers::default(),
            cleanup_error: None,
            exit_code: None,
            diagnostics: diagnostics.clone(),
            process,
            tracked_exit: false,
        };
        session.workers.writer = Some(
            thread::Builder::new()
                .name("terminal-input".into())
                .spawn(move || {
                    while !writer_stop.load(Ordering::Acquire) {
                        match input_receiver.recv_timeout(Duration::from_millis(50)) {
                            Ok(bytes) => {
                                if let Err(error) =
                                    writer.write_all(&bytes).and_then(|()| writer.flush())
                                {
                                    if let Ok(mut failure) = write_failure.lock() {
                                        *failure = Some(
                                            ApplicationError::new(
                                                ErrorCode::WriteFailed,
                                                Operation::Terminal,
                                            )
                                            .caused_by(error),
                                        );
                                    }
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
        let stop = stopped.clone();
        let captured = diagnostics.clone();
        session.workers.reader = Some(
            thread::Builder::new()
                .name("terminal-output".into())
                .spawn(move || {
                    let mut buffer = [0; CHUNK];
                    loop {
                        let mut event = match reader.read(&mut buffer) {
                            Ok(0) => break,
                            Ok(count) => {
                                captured.capture(process, Stream::Terminal, &buffer[..count]);
                                ReadEvent::Bytes(buffer[..count].to_vec())
                            }
                            Err(error) => {
                                ReadEvent::Error(failure(ErrorCode::ReadFailed).caused_by(error))
                            }
                        };
                        let failed = matches!(event, ReadEvent::Error(_));
                        loop {
                            if stop.load(Ordering::Acquire) {
                                break;
                            }
                            match sender.try_send(event) {
                                Ok(()) => break,
                                Err(TrySendError::Disconnected(_)) => return,
                                Err(TrySendError::Full(pending)) => {
                                    event = pending;
                                    thread::sleep(Duration::from_millis(5));
                                }
                            }
                        }
                        if failed {
                            break;
                        }
                    }
                })
                .map_err(|e| failure(ErrorCode::SpawnFailed).caused_by(e))?,
        );
        Ok(session)
    }

    pub fn input(&mut self, data: &[u8]) -> Result<()> {
        if data.len() > 65536 {
            return Err(failure(ErrorCode::OutputLimit));
        }
        self.writer
            .try_send(data.to_vec())
            .map_err(|_| failure(ErrorCode::QueueFull))
    }

    pub fn resize(&self, cols: u16, rows: u16) -> Result<()> {
        self.master
            .as_ref()
            .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
            .resize(size(cols, rows)?)
            .map_err(|e| failure(ErrorCode::ResizeFailed).caused_by(std::io::Error::other(e)))
    }

    pub fn read(&mut self) -> Result<Output> {
        let mut bytes = Vec::new();
        let mut error = self
            .write_error
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?
            .take();
        let mut eof = false;
        for _ in 0..QUEUE {
            match self.output.try_recv() {
                Ok(ReadEvent::Bytes(chunk)) => bytes.extend(chunk),
                Ok(ReadEvent::Error(message)) => {
                    error = Some(message);
                    break;
                }
                Err(TryRecvError::Empty) => break,
                Err(TryRecvError::Disconnected) => {
                    eof = true;
                    break;
                }
            }
        }
        if self.exit_code.is_none() {
            self.exit_code = self
                .child
                .try_wait()
                .map_err(|e| failure(ErrorCode::ReadFailed).caused_by(std::io::Error::other(e)))?
                .map(|status| status.exit_code());
            if self.exit_code.is_some() {
                // ConPTY signals EOF only after its master closes. Close on a separate
                // thread while polling drains the bounded output queue.
                self.close_master();
            }
        }
        let joined = self.workers.reap_finished()?;
        if self.exit_code.is_some() && eof && joined && !self.tracked_exit {
            self.diagnostics.finish(
                self.process,
                self.exit_code.map(|c| c as i32),
                ProcessPhase::Exited,
            );
            self.tracked_exit = true;
        }
        if let Some(failure) = &error {
            self.diagnostics.failure(failure.clone());
        }
        // Drain the PTY before reporting exit so the final screen is preserved.
        Ok(Output {
            bytes,
            exit_code: if eof && joined { self.exit_code } else { None },
            error,
        })
    }

    fn close_master(&mut self) {
        self.writer_stopped.store(true, Ordering::Release);
        if let Some(master) = self.master.take() {
            self.workers.closer = Some(thread::spawn(move || drop(master)));
        }
    }

    fn settle(&mut self, deadline: Instant) -> Result<()> {
        self.stopped.store(true, Ordering::Release);
        self.writer_stopped.store(true, Ordering::Release);
        if self.exit_code.is_none() {
            self.exit_code = self
                .child
                .try_wait()
                .map_err(|e| failure(ErrorCode::ReadFailed).caused_by(std::io::Error::other(e)))?
                .map(|status| status.exit_code());
        }
        if self.exit_code.is_none() {
            self.child.kill().map_err(|e| {
                failure(ErrorCode::CleanupFailed).caused_by(std::io::Error::other(e))
            })?;
        }
        // The reader keeps draining (discarding after cancellation) while ConPTY closes.
        self.close_master();
        while self.exit_code.is_none() {
            self.exit_code = self
                .child
                .try_wait()
                .map_err(|e| failure(ErrorCode::ReadFailed).caused_by(std::io::Error::other(e)))?
                .map(|status| status.exit_code());
            if self.exit_code.is_none() {
                if Instant::now() >= deadline {
                    return Err(failure(ErrorCode::CleanupFailed));
                }
                thread::sleep(Duration::from_millis(5));
            }
        }
        self.workers.join_until(deadline)
    }

    pub fn stop(&mut self) -> Result<()> {
        match self.settle(Instant::now() + STOP_TIMEOUT) {
            Ok(()) => {
                if !self.tracked_exit {
                    self.diagnostics.finish(
                        self.process,
                        self.exit_code.map(|c| c as i32),
                        ProcessPhase::Terminated,
                    );
                    self.tracked_exit = true;
                }
                Ok(())
            }
            Err(error) => {
                let primary = self.cleanup_error.get_or_insert_with(|| error.clone());
                self.diagnostics.failure(error);
                Err(primary.clone())
            }
        }
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        if let Err(error) = self.stop() {
            // Normal window closure retains the Session on failure. Unexpected host
            // destruction cannot establish joined cleanup; do not report it as success.
            self.diagnostics.failure(error);
        }
    }
}

pub struct TerminalState {
    pub launch: Launch,
    pub session: Mutex<Option<Session>>,
}

impl TerminalState {
    pub fn stop(&self) -> Result<()> {
        let mut owned = self
            .session
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        if let Some(session) = owned.as_mut() {
            session.stop()?;
        }
        owned.take();
        Ok(())
    }
}

#[cfg(test)]
mod tests;
