//! The supervised runner: one long-lived launcher child for as long as the
//! agent may serve, unlike the sign-in runner's short calls. The child and
//! everything it starts live in a kill-on-close Job Object, so they end with
//! this host however it ends. Standard input carries the bearer and then stays
//! open: closing it is the stop request.

use super::launcher::{self, Event, LINE_LIMIT};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process::status::{ProcessPhase, ProcessRole},
};
use std::{
    io::{Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::Arc,
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

/// How long the launcher has to stop its agent and exit after its standard
/// input closes, before the job ends it.
pub const STOP_GRACE: Duration = Duration::from_secs(10);
/// How long the job's ended processes have to finish exiting.
#[cfg(windows)]
const SETTLE_BOUND: Duration = Duration::from_secs(10);

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Cli)
}

/// What the launcher's standard output said, in order.
#[derive(Debug, PartialEq, Eq)]
pub enum Signal {
    Event(Event),
    /// A line outside the protocol. Nothing it says is acted on.
    Violation,
    /// Standard output closed: the launcher and everything holding its
    /// output have ended.
    Ended,
}

/// How a stopped launcher ended.
#[derive(Debug, PartialEq, Eq)]
pub enum Ending {
    /// It exited within its grace after its standard input closed.
    Exited(Option<i32>),
    /// It overran its grace and the job ended it.
    Terminated,
}

/// A running launcher. Dropping it closes the job, which ends every process
/// still in it.
pub struct Supervised {
    child: Child,
    stdin: Option<ChildStdin>,
    #[cfg(windows)]
    job: cadrumo_manager::process_job::ProcessJob,
    process: u64,
    threads: Vec<JoinHandle<()>>,
    diagnostics: Arc<Diagnostics>,
}

/// Starts `command` contained, writes the bearer frame, and reports each
/// output line to `signals` from a reader thread.
#[cfg(windows)]
pub fn start(
    mut command: Command,
    bearer: &str,
    signals: impl Fn(Signal) + Send + 'static,
    diagnostics: Arc<Diagnostics>,
) -> Result<Supervised> {
    use cadrumo_manager::process_job::{CREATE_SUSPENDED, ProcessJob};
    use std::os::windows::process::CommandExt;

    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .creation_flags(CREATE_NO_WINDOW | CREATE_SUSPENDED);
    let job =
        ProcessJob::new().map_err(|cause| failure(ErrorCode::SpawnFailed).caused_by(cause))?;
    let mut child = command.spawn().map_err(|cause| {
        let error = failure(ErrorCode::SpawnFailed).caused_by(cause);
        diagnostics.spawn_failure(ProcessRole::Cli, error.clone());
        error
    })?;
    if let Err(cause) = job.adopt_suspended(&child) {
        // The child is still suspended: none of its code has run.
        let _ = child.kill();
        let _ = child.wait();
        let error = failure(ErrorCode::SpawnFailed).caused_by(cause);
        diagnostics.spawn_failure(ProcessRole::Cli, error.clone());
        return Err(error);
    }
    let process = diagnostics.start(child.id(), ProcessRole::Cli);
    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    let mut supervised = Supervised {
        stdin: child.stdin.take(),
        child,
        job,
        process,
        threads: Vec::new(),
        diagnostics,
    };
    let (Some(stdout), Some(stderr)) = (stdout, stderr) else {
        supervised.abandon(failure(ErrorCode::SpawnFailed));
        return Err(failure(ErrorCode::SpawnFailed));
    };
    supervised
        .threads
        .push(thread::spawn(move || read_events(stdout, signals)));
    // Diagnostics carry no content, so standard error is read only to keep
    // the launcher from blocking on a full pipe.
    supervised
        .threads
        .push(thread::spawn(move || discard(stderr)));
    let frame = launcher::bearer_frame(bearer);
    let written = supervised
        .stdin
        .as_mut()
        .ok_or_else(|| failure(ErrorCode::WriteFailed))
        .and_then(|stdin| {
            stdin
                .write_all(&frame)
                .and_then(|()| stdin.flush())
                .map_err(|cause| failure(ErrorCode::WriteFailed).caused_by(cause))
        });
    if let Err(error) = written {
        supervised.abandon(error.clone());
        return Err(error);
    }
    Ok(supervised)
}

/// Nothing else contains a child's descendants, so no other platform starts one.
#[cfg(not(windows))]
pub fn start(
    _command: Command,
    _bearer: &str,
    _signals: impl Fn(Signal) + Send + 'static,
    _diagnostics: Arc<Diagnostics>,
) -> Result<Supervised> {
    Err(failure(ErrorCode::UnsupportedPlatform))
}

impl Supervised {
    /// Closes standard input, waits up to `grace` for the launcher to exit,
    /// and ends the job either way, so nothing it started outlives it.
    pub fn stop(mut self, grace: Duration) -> Result<Ending> {
        drop(self.stdin.take());
        let started = Instant::now();
        let mut ending = None;
        while started.elapsed() < grace {
            match self.child.try_wait() {
                Ok(Some(status)) => {
                    ending = Some(Ending::Exited(status.code()));
                    break;
                }
                Ok(None) => thread::sleep(Duration::from_millis(20)),
                Err(cause) => {
                    let error = failure(ErrorCode::CleanupFailed).caused_by(cause);
                    self.abandon(error.clone());
                    return Err(error);
                }
            }
        }
        let terminated = self.terminate();
        let ending = ending.unwrap_or(Ending::Terminated);
        let reaped = self
            .child
            .wait()
            .map_err(|cause| failure(ErrorCode::CleanupFailed).caused_by(cause));
        // Every writer of the pipes has ended, so the readers reach their end.
        for reader in self.threads.drain(..) {
            let _ = reader.join();
        }
        let phase = match ending {
            Ending::Exited(_) => ProcessPhase::Exited,
            Ending::Terminated => ProcessPhase::Terminated,
        };
        let code = reaped.as_ref().ok().and_then(|status| status.code());
        self.diagnostics.finish(self.process, code, phase);
        terminated?;
        reaped?;
        Ok(ending)
    }

    #[cfg(windows)]
    fn terminate(&self) -> Result<()> {
        let cleanup = |cause| failure(ErrorCode::CleanupFailed).caused_by(cause);
        self.job.terminate().map_err(cleanup)?;
        // Termination is asynchronous: a process the job ended can still be
        // exiting when the call returns. Stopped means the job is empty.
        let deadline = Instant::now() + SETTLE_BOUND;
        while self.job.active_processes().map_err(cleanup)? != 0 {
            if Instant::now() >= deadline {
                return Err(failure(ErrorCode::CleanupFailed));
            }
            thread::sleep(Duration::from_millis(10));
        }
        Ok(())
    }

    #[cfg(not(windows))]
    fn terminate(&self) -> Result<()> {
        Ok(())
    }

    /// Ends the job after a failure, records it, and reaps what it can.
    fn abandon(&mut self, error: ApplicationError) {
        drop(self.stdin.take());
        let _ = self.terminate();
        let code = self.child.wait().ok().and_then(|status| status.code());
        for reader in self.threads.drain(..) {
            let _ = reader.join();
        }
        self.diagnostics.failure_for(self.process, error);
        self.diagnostics
            .finish(self.process, code, ProcessPhase::Terminated);
    }

    #[cfg(test)]
    pub fn id(&self) -> u32 {
        self.child.id()
    }
}

/// Reads bounded lines and reports each as its event, a violation, and at
/// last the end. After a violation the rest is read and dropped.
fn read_events(mut pipe: impl Read, signals: impl Fn(Signal)) {
    let mut line = Vec::with_capacity(256);
    let mut buffer = [0u8; 4096];
    let mut violated = false;
    loop {
        let count = match pipe.read(&mut buffer) {
            Ok(0) | Err(_) => break,
            Ok(count) => count,
        };
        if violated {
            continue;
        }
        for &byte in &buffer[..count] {
            if byte == b'\n' {
                match launcher::decode(&line) {
                    Ok(event) => signals(Signal::Event(event)),
                    Err(_) => {
                        signals(Signal::Violation);
                        violated = true;
                        break;
                    }
                }
                line.clear();
            } else if line.len() > LINE_LIMIT {
                signals(Signal::Violation);
                violated = true;
                break;
            } else {
                line.push(byte);
            }
        }
    }
    // A last line without its terminator is not an event either.
    if !violated && !line.is_empty() {
        signals(Signal::Violation);
    }
    signals(Signal::Ended);
}

fn discard(mut pipe: impl Read) {
    let mut buffer = [0u8; 4096];
    while matches!(pipe.read(&mut buffer), Ok(count) if count > 0) {}
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use std::sync::Mutex;

    #[test]
    fn output_lines_become_events_and_a_violation_silences_the_rest() {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        read_events(
            &b"{\"event\":\"agent_ready\",\"gateway_port\":5000,\"agent_version\":\"1\",\"lane\":\"development\",\"workspace_root\":\"C:\\\\ws\"}\nnot json\n{\"event\":\"agent_stopped\",\"reason\":\"x\"}\n"[..],
            move |signal| sink.lock().unwrap().push(signal),
        );
        assert_eq!(
            *seen.lock().unwrap(),
            [
                Signal::Event(Event::Ready {
                    gateway_port: 5000,
                    agent_version: "1".into(),
                    workspace_root: r"C:\ws".into()
                }),
                Signal::Violation,
                Signal::Ended
            ]
        );
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        let flood = vec![b'x'; LINE_LIMIT * 3];
        read_events(&flood[..], move |signal| sink.lock().unwrap().push(signal));
        assert_eq!(*seen.lock().unwrap(), [Signal::Violation, Signal::Ended]);
    }

    #[cfg(windows)]
    pub(crate) fn powershell(script: &str) -> Command {
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
    pub(crate) fn alive(pid: u32) -> bool {
        let output = Command::new(
            std::path::Path::new(&std::env::var_os("SystemRoot").unwrap())
                .join("System32/tasklist.exe"),
        )
        .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
        .output()
        .unwrap();
        String::from_utf8_lossy(&output.stdout).contains(&format!("\"{pid}\""))
    }

    /// A real child that reads the bearer line, reports ready, starts a
    /// grandchild, and stops when its standard input ends, unless told to
    /// ignore it.
    #[cfg(windows)]
    pub(crate) fn launcher_script(ignore_end: bool) -> String {
        format!(
            "$line = [Console]::In.ReadLine(); \
             $bearer = ($line | ConvertFrom-Json).bearer; \
             $grandchild = Start-Process -PassThru -WindowStyle Hidden -FilePath $env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds 120'; \
             [Console]::Error.WriteLine('grandchild ' + $grandchild.Id); \
             [Console]::Out.WriteLine('{{\"event\":\"agent_ready\",\"gateway_port\":4000,\"agent_version\":\"' + $bearer.Length + '-' + $grandchild.Id + '\",\"lane\":\"development\",\"workspace_root\":\"C:\\\\lane\\\\ws\"}}'); \
             [Console]::Out.Flush(); \
             {}",
            if ignore_end {
                "Start-Sleep -Seconds 120"
            } else {
                "$null = [Console]::In.ReadToEnd(); [Console]::Out.WriteLine('{\"event\":\"agent_stopped\",\"reason\":\"agent_host_closed\"}'); exit 0"
            }
        )
    }

    /// The bearer length and grandchild id the test launcher reports as its
    /// version.
    #[cfg(windows)]
    pub(crate) fn reported(version: &str) -> (u32, String) {
        let (length, grandchild) = version.split_once('-').unwrap();
        (grandchild.parse().unwrap(), length.to_owned())
    }

    #[cfg(windows)]
    pub(crate) fn ready(seen: &Mutex<Vec<Signal>>) -> (u32, String) {
        let deadline = Instant::now() + Duration::from_secs(30);
        loop {
            if let Some(Signal::Event(Event::Ready { agent_version, .. })) =
                seen.lock().unwrap().first()
            {
                return reported(agent_version);
            }
            assert!(Instant::now() < deadline, "no ready line");
            thread::sleep(Duration::from_millis(20));
        }
    }

    #[cfg(windows)]
    #[test]
    fn a_real_launcher_gets_the_bearer_and_stops_when_its_input_closes() {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        let diagnostics = Arc::new(Diagnostics::default());
        let bearer = "b".repeat(64);
        let running = start(
            powershell(&launcher_script(false)),
            &bearer,
            move |signal| sink.lock().unwrap().push(signal),
            diagnostics.clone(),
        )
        .unwrap();
        // The script reports the bearer's length and its grandchild's id as
        // its version, which keeps both checkable.
        let (grandchild, version) = ready(&seen);
        assert_eq!(version, "64");
        assert!(alive(grandchild));
        assert_eq!(running.stop(STOP_GRACE).unwrap(), Ending::Exited(Some(0)));
        assert!(!alive(grandchild), "the job ends what the launcher started");
        assert_eq!(
            seen.lock().unwrap()[1..],
            [
                Signal::Event(Event::Stopped {
                    reason: "agent_host_closed".into()
                }),
                Signal::Ended
            ]
        );
        let snapshot = diagnostics.snapshot(0);
        assert_eq!(snapshot.processes[0].phase, ProcessPhase::Exited);
        assert!(snapshot.output.is_empty());
        assert!(
            !serde_json::to_string(&snapshot.events)
                .unwrap()
                .contains(&bearer)
        );
    }

    #[cfg(windows)]
    #[test]
    fn a_launcher_that_overruns_its_grace_is_ended_with_its_tree() {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        let diagnostics = Arc::new(Diagnostics::default());
        let running = start(
            powershell(&launcher_script(true)),
            "bearer",
            move |signal| sink.lock().unwrap().push(signal),
            diagnostics.clone(),
        )
        .unwrap();
        let launcher = running.id();
        let (grandchild, _) = ready(&seen);
        let stopping = Instant::now();
        assert_eq!(
            running.stop(Duration::from_millis(500)).unwrap(),
            Ending::Terminated
        );
        assert!(stopping.elapsed() < Duration::from_secs(10));
        assert!(!alive(launcher) && !alive(grandchild));
        assert_eq!(seen.lock().unwrap().last(), Some(&Signal::Ended));
        assert_eq!(
            diagnostics.snapshot(0).processes[0].phase,
            ProcessPhase::Terminated
        );
    }

    #[cfg(windows)]
    #[test]
    fn dropping_a_running_launcher_ends_its_tree() {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = seen.clone();
        let running = start(
            powershell(&launcher_script(true)),
            "bearer",
            move |signal| sink.lock().unwrap().push(signal),
            Arc::new(Diagnostics::default()),
        )
        .unwrap();
        let launcher = running.id();
        let (grandchild, _) = ready(&seen);
        // As when the host itself ends without stopping it: the job's last
        // handle closes.
        drop(running);
        let deadline = Instant::now() + Duration::from_secs(10);
        while alive(launcher) || alive(grandchild) {
            assert!(Instant::now() < deadline, "the tree outlived its job");
            thread::sleep(Duration::from_millis(50));
        }
    }
}
