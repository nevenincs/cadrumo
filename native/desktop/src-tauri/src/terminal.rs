use crate::package::Launch;
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

const CHUNK: usize = 8192;
const QUEUE: usize = 8;
const STOP_TIMEOUT: Duration = Duration::from_secs(3);

#[derive(Default)]
struct Workers {
    reader: Option<JoinHandle<()>>,
    writer: Option<JoinHandle<()>>,
    closer: Option<JoinHandle<()>>,
}

impl Workers {
    fn reap_finished(&mut self) -> Result<bool, String> {
        for worker in [&mut self.reader, &mut self.writer, &mut self.closer] {
            if worker.as_ref().is_some_and(JoinHandle::is_finished) {
                worker
                    .take()
                    .ok_or("Terminal worker ownership is missing")?
                    .join()
                    .map_err(|_| "Terminal worker panicked")?;
            }
        }
        Ok(self.reader.is_none() && self.writer.is_none() && self.closer.is_none())
    }

    fn join_until(&mut self, deadline: Instant) -> Result<(), String> {
        loop {
            if self.reap_finished()? {
                return Ok(());
            }
            if Instant::now() >= deadline {
                return Err(
                    "Terminal workers have not settled before the shutdown deadline".into(),
                );
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
    pub error: Option<String>,
}

enum ReadEvent {
    Bytes(Vec<u8>),
    Error(String),
}

pub struct Session {
    master: Option<Box<dyn MasterPty + Send>>,
    writer: SyncSender<Vec<u8>>,
    write_error: Arc<Mutex<Option<String>>>,
    child: Box<dyn Child + Send + Sync>,
    output: Receiver<ReadEvent>,
    stopped: Arc<AtomicBool>,
    writer_stopped: Arc<AtomicBool>,
    workers: Workers,
    cleanup_error: Option<String>,
    exit_code: Option<u32>,
}

pub fn size(cols: u16, rows: u16) -> Result<PtySize, String> {
    if !(2..=1000).contains(&cols) || !(2..=1000).contains(&rows) {
        return Err("Terminal dimensions are outside 2..1000".into());
    }
    Ok(PtySize {
        rows,
        cols,
        pixel_width: 0,
        pixel_height: 0,
    })
}

impl Session {
    pub fn start(launch: &Launch, cols: u16, rows: u16, args: &[&str]) -> Result<Self, String> {
        let pair = native_pty_system()
            .openpty(size(cols, rows)?)
            .map_err(|e| e.to_string())?;
        let mut command = CommandBuilder::new(launch.child.executable());
        command.env_clear();
        for (key, value) in launch.child.environment() {
            command.env(key, value);
        }
        command.env("TERM", "xterm-256color");
        command.env("COLORTERM", "truecolor");
        command.cwd(&launch.working_directory);
        command.args(args);
        let mut reader = pair.master.try_clone_reader().map_err(|e| e.to_string())?;
        let mut writer = pair.master.take_writer().map_err(|e| e.to_string())?;
        let child = pair
            .slave
            .spawn_command(command)
            .map_err(|e| e.to_string())?;
        drop(pair.slave);
        let (sender, output) = mpsc::sync_channel(QUEUE);
        let stopped = Arc::new(AtomicBool::new(false));
        let (input_sender, input_receiver) = mpsc::sync_channel::<Vec<u8>>(QUEUE);
        let write_error = Arc::new(Mutex::new(None));
        let write_failure = write_error.clone();
        let writer_stopped = Arc::new(AtomicBool::new(false));
        let writer_stop = writer_stopped.clone();
        let writer_worker = thread::spawn(move || {
            while !writer_stop.load(Ordering::Acquire) {
                match input_receiver.recv_timeout(Duration::from_millis(50)) {
                    Ok(bytes) => {
                        if let Err(error) = writer.write_all(&bytes).and_then(|()| writer.flush()) {
                            if let Ok(mut failure) = write_failure.lock() {
                                *failure = Some(error.to_string());
                            }
                            break;
                        }
                    }
                    Err(RecvTimeoutError::Timeout) => continue,
                    Err(RecvTimeoutError::Disconnected) => break,
                }
            }
        });
        let stop = stopped.clone();
        let reader_worker = thread::spawn(move || {
            let mut buffer = [0; CHUNK];
            loop {
                let mut event = match reader.read(&mut buffer) {
                    Ok(0) => break,
                    Ok(count) => ReadEvent::Bytes(buffer[..count].to_vec()),
                    Err(error) => ReadEvent::Error(error.to_string()),
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
        });
        Ok(Self {
            master: Some(pair.master),
            writer: input_sender,
            write_error,
            child,
            output,
            stopped,
            writer_stopped,
            workers: Workers {
                reader: Some(reader_worker),
                writer: Some(writer_worker),
                closer: None,
            },
            cleanup_error: None,
            exit_code: None,
        })
    }

    pub fn input(&mut self, data: &[u8]) -> Result<(), String> {
        if data.len() > 65536 {
            return Err("Terminal input exceeds limit".into());
        }
        self.writer
            .try_send(data.to_vec())
            .map_err(|_| "Terminal input queue is full or closed".into())
    }

    pub fn resize(&self, cols: u16, rows: u16) -> Result<(), String> {
        self.master
            .as_ref()
            .ok_or("TUI has exited")?
            .resize(size(cols, rows)?)
            .map_err(|e| e.to_string())
    }

    pub fn read(&mut self) -> Result<Output, String> {
        let mut bytes = Vec::new();
        let mut error = self.write_error.lock().map_err(|e| e.to_string())?.take();
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
                .map_err(|e| e.to_string())?
                .map(|status| status.exit_code());
            if self.exit_code.is_some() {
                // ConPTY signals EOF only after its master closes. Close on a separate
                // thread while polling drains the bounded output queue.
                self.close_master();
            }
        }
        let joined = self.workers.reap_finished()?;
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

    fn settle(&mut self, deadline: Instant) -> Result<(), String> {
        self.stopped.store(true, Ordering::Release);
        self.writer_stopped.store(true, Ordering::Release);
        if self.exit_code.is_none() {
            self.exit_code = self
                .child
                .try_wait()
                .map_err(|e| e.to_string())?
                .map(|status| status.exit_code());
        }
        if self.exit_code.is_none() {
            self.child.kill().map_err(|e| e.to_string())?;
        }
        // The reader keeps draining (discarding after cancellation) while ConPTY closes.
        self.close_master();
        while self.exit_code.is_none() {
            self.exit_code = self
                .child
                .try_wait()
                .map_err(|e| e.to_string())?
                .map(|status| status.exit_code());
            if self.exit_code.is_none() {
                if Instant::now() >= deadline {
                    return Err("Terminal child has not exited before the shutdown deadline".into());
                }
                thread::sleep(Duration::from_millis(5));
            }
        }
        self.workers.join_until(deadline)
    }

    pub fn stop(&mut self) -> Result<(), String> {
        match self.settle(Instant::now() + STOP_TIMEOUT) {
            Ok(()) => Ok(()),
            Err(error) => {
                let primary = self.cleanup_error.get_or_insert_with(|| error.clone());
                if *primary == error {
                    Err(error)
                } else {
                    Err(format!("{primary}; cleanup retry: {error}"))
                }
            }
        }
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        if let Err(error) = self.stop() {
            // Normal window closure retains the Session on failure. Unexpected host
            // destruction cannot establish joined cleanup; do not report it as success.
            eprintln!("Terminal teardown did not settle: {error}");
        }
    }
}

pub struct TerminalState {
    pub launch: Launch,
    pub session: Mutex<Option<Session>>,
}

impl TerminalState {
    pub fn stop(&self) -> Result<(), String> {
        let mut owned = self.session.lock().map_err(|e| e.to_string())?;
        if let Some(session) = owned.as_mut() {
            session.stop()?;
        }
        owned.take();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(feature = "live-package-tests")]
    use std::path::PathBuf;

    #[cfg(feature = "live-package-tests")]
    fn wait_for(session: &mut Session, needle: &str) -> Vec<u8> {
        let deadline = Instant::now() + Duration::from_secs(45);
        let mut bytes = Vec::new();
        while Instant::now() < deadline {
            let output = session.read().unwrap();
            assert!(output.bytes.len() <= 65536, "unbounded PTY response");
            assert!(output.error.is_none(), "PTY read error: {:?}", output.error);
            if output.bytes.windows(4).any(|bytes| bytes == b"\x1b[6n") {
                session.input(b"\x1b[1;1R").unwrap();
            }
            bytes.extend(output.bytes);
            if String::from_utf8_lossy(&bytes).contains(needle) {
                return bytes;
            }
            assert!(
                output.exit_code.is_none(),
                "child exited before {needle}: {}",
                String::from_utf8_lossy(&bytes)
            );
            thread::sleep(Duration::from_millis(10));
        }
        panic!("no {needle}: {}", String::from_utf8_lossy(&bytes));
    }

    #[test]
    fn dimensions_are_bounded() {
        assert!(size(0, 24).is_err());
        assert!(size(80, 1001).is_err());
        assert!(size(132, 40).is_ok());
    }

    #[test]
    fn unfinished_worker_stays_owned_after_deadline_and_can_be_joined_on_retry() {
        let (release, wait) = mpsc::channel();
        let worker = thread::spawn(move || wait.recv().unwrap());
        let mut workers = Workers {
            reader: Some(worker),
            ..Workers::default()
        };
        let error = workers.join_until(Instant::now()).unwrap_err();
        assert!(error.contains("shutdown deadline"));
        assert!(workers.reader.is_some(), "timed-out worker was detached");
        release.send(()).unwrap();
        workers
            .join_until(Instant::now() + Duration::from_secs(1))
            .unwrap();
        assert!(workers.reader.is_none());
    }

    #[test]
    fn panicked_worker_is_reported_as_cleanup_failure() {
        let mut workers = Workers {
            writer: Some(thread::spawn(|| panic!("controlled worker failure"))),
            ..Workers::default()
        };
        assert_eq!(
            workers
                .join_until(Instant::now() + Duration::from_secs(1))
                .unwrap_err(),
            "Terminal worker panicked",
        );
    }

    #[cfg(feature = "live-package-tests")]
    #[tokio::test]
    async fn packaged_pty_unicode_input_resize_output_exit_and_cleanup() {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let launch = crate::package::resolve(root).await.unwrap();
        assert!(
            !launch
                .child
                .environment()
                .keys()
                .any(|key| key.to_string_lossy().starts_with("PYTHON"))
        );
        let script = "import os,sys,time; print('READY', flush=True); value=input(); print('UNICODE='+value,flush=True); print('SIZE='+str(os.get_terminal_size().columns),flush=True); print('X'*100000,flush=True); print('DONE',flush=True)";
        let mut session = Session::start(&launch, 80, 24, &["-u", "-c", script]).unwrap();
        wait_for(&mut session, "READY");
        session.resize(132, 40).unwrap();
        session.input("á漢字\r".as_bytes()).unwrap();
        let result = wait_for(&mut session, "DONE");
        let result = String::from_utf8_lossy(&result);
        assert!(result.contains("UNICODE=á漢字"));
        assert!(result.contains("SIZE=132"));
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            let output = session.read().unwrap();
            if let Some(code) = output.exit_code {
                assert_eq!(code, 0);
                break;
            }
            assert!(Instant::now() < deadline, "child did not exit");
            thread::sleep(Duration::from_millis(10));
        }
        let mut blocked = Session::start(
            &launch,
            80,
            24,
            &[
                "-u",
                "-c",
                "import time; print('WAITING',flush=True); time.sleep(120)",
            ],
        )
        .unwrap();
        wait_for(&mut blocked, "WAITING");
        let began = Instant::now();
        blocked.stop().unwrap();
        assert!(began.elapsed() < Duration::from_secs(5));
        assert!(blocked.child.try_wait().unwrap().is_some());
        assert!(blocked.workers.reap_finished().unwrap());

        let mut flood = Session::start(&launch, 80, 24, &["-u", "-c",
            "import time; print('FLOOD',flush=True); time.sleep(0.2); print('Z'*10000000,flush=True); time.sleep(120)"]).unwrap();
        wait_for(&mut flood, "FLOOD");
        thread::sleep(Duration::from_millis(500));
        let began = Instant::now();
        flood.stop().unwrap();
        assert!(
            began.elapsed() < Duration::from_secs(5),
            "full output queue blocked cleanup"
        );
        assert!(flood.child.try_wait().unwrap().is_some());
        assert!(flood.workers.reap_finished().unwrap());
    }

    #[cfg(feature = "live-package-tests")]
    #[tokio::test]
    async fn real_packaged_tui_draws_in_the_pty() {
        let root = PathBuf::from(
            std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
        );
        let launch = crate::package::resolve(root).await.unwrap();
        let mut session =
            Session::start(&launch, 120, 40, &["-m", "cadrumo.entrypoints.tui"]).unwrap();
        let output = wait_for(&mut session, "\u{1b}[?1049h");
        assert!(!output.is_empty());
        session.resize(100, 30).unwrap();
        session.input(b"\x1b[B\t").unwrap();
        session.stop().unwrap();
        assert!(session.child.try_wait().unwrap().is_some());
        assert!(session.workers.reap_finished().unwrap());
    }
}
