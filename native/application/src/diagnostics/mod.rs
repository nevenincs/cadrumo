pub mod helper;
pub mod lifecycle;
pub mod logging;
pub mod panic;
pub mod service;
pub mod webview;

use crate::{
    diagnostics::{
        helper::{HelperResult, HelperTiming},
        lifecycle::LifecycleFact,
        logging::{LogFile, LogPaths},
        panic::PanicFact,
        service::ServiceFact,
        webview::WebviewFailure,
    },
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process::status::{
        OutputChunk, ProcessPhase, ProcessRole, ProcessStatus, Stream, Tracker, timestamp_ms,
    },
};
use serde::{Deserialize, Serialize};
use std::{
    collections::VecDeque,
    io::Write,
    path::{Path, PathBuf},
    sync::{Mutex, MutexGuard, TryLockError},
};

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EventKind {
    HostStarted,
    StageStarted,
    StageCompleted,
    HeadlessSelected,
    GuiSelected,
    ChildStarted,
    ChildExited,
    ChildTerminated,
    HelperTiming,
    HelperResult,
    ServiceEvent,
    Failure,
    HostStopped,
    WindowCloseRequested,
    HostExitRequested,
    Panic,
}
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DiagnosticSource {
    #[default]
    Desktop,
    Manager,
    Installer,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HostStage {
    Admission,
    Environment,
    Manager,
    Window,
    Shutdown,
    JobEscape,
    Instance,
    Storage,
    Package,
    Session,
    Supervision,
    Agent,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum HostOutcome {
    Ready,
    AlreadyRunning,
    Dispatched,
    SkippedUnmanaged,
    Unavailable,
}
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Event {
    pub sequence: u64,
    pub source: DiagnosticSource,
    pub timestamp_ms: u64,
    pub host_pid: u32,
    pub kind: EventKind,
    pub process: Option<u64>,
    pub failure: Option<ApplicationError>,
    pub status: Option<ProcessStatus>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stage: Option<HostStage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<ProcessRole>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub outcome: Option<HostOutcome>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub host_exit_code: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lifecycle: Option<LifecycleFact>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub webview_failure: Option<WebviewFailure>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub helper_timing: Option<HelperTiming>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub helper_result: Option<HelperResult>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub service: Option<ServiceFact>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub panic: Option<PanicFact>,
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub paths: Option<LogPaths>,
    pub log_failure: Option<ApplicationError>,
    pub events: Vec<Event>,
    pub processes: Vec<ProcessStatus>,
    pub output: Vec<OutputChunk>,
    pub dropped_bytes: u64,
}
#[derive(Default)]
struct State {
    first_event_ms: Option<u64>,
    file: Option<LogFile>,
    // One incomplete configuration attempt; the ring remains the replay source.
    pending_replay: Option<Replay>,
    log_failure: Option<ApplicationError>,
    events: VecDeque<Event>,
    tracker: Tracker,
    next_event: u64,
}
struct Replay {
    current: PathBuf,
    through: u64,
}
#[derive(Default)]
struct Context {
    stage: Option<HostStage>,
    role: Option<ProcessRole>,
    outcome: Option<HostOutcome>,
    host_exit_code: Option<i32>,
    lifecycle: Option<LifecycleFact>,
    webview_failure: Option<WebviewFailure>,
    helper_timing: Option<HelperTiming>,
    helper_result: Option<HelperResult>,
    service: Option<ServiceFact>,
}
#[derive(Default)]
pub struct Diagnostics {
    state: Mutex<State>,
    source: DiagnosticSource,
    // The panic path reads this without the state lock, which the panicking
    // code may hold; configuration is its only writer.
    panic_log: Mutex<Option<PathBuf>>,
}
impl Diagnostics {
    /// The first event of this process, retained even after the event ring wraps.
    pub fn started_ms(&self) -> u64 {
        self.state
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .first_event_ms
            .unwrap_or_else(timestamp_ms)
    }
    pub fn new(source: DiagnosticSource) -> Self {
        Self {
            source,
            ..Self::default()
        }
    }
    pub fn configure(&self, directory: &Path, max_bytes: u64, backups: u32) -> Result<()> {
        let file = LogFile::new(directory, max_bytes, backups)?;
        self.configure_log(file)
    }
    pub fn configure_file(&self, current: &Path, max_bytes: u64, backups: u32) -> Result<()> {
        self.configure_log(LogFile::for_file(current, max_bytes, backups)?)
    }
    fn configure_log(&self, file: LogFile) -> Result<()> {
        let mut state = self.state.lock().map_err(|_| poisoned())?;
        if state
            .file
            .as_ref()
            .is_some_and(|active| active.paths.current == file.paths.current)
        {
            // Final environment projection may repeat the early startup sink.
            // Update its rotation policy without replaying records already written.
            *self.panic_log.lock().unwrap_or_else(|e| e.into_inner()) =
                Some(file.paths.current.clone());
            state.file = Some(file);
            state.pending_replay = None;
            return Ok(());
        }
        let State {
            events,
            pending_replay,
            ..
        } = &mut *state;
        let replay = pending_replay.get_or_insert_with(|| Replay {
            current: file.paths.current.clone(),
            through: 0,
        });
        if replay.current != file.paths.current {
            replay.current = file.paths.current.clone();
            replay.through = 0;
        }
        for event in events {
            if event.sequence > replay.through {
                file.append(event)?;
                replay.through = event.sequence;
            }
        }
        let current = file.paths.current.clone();
        state.file = Some(file);
        state.pending_replay = None;
        *self.panic_log.lock().unwrap_or_else(|e| e.into_inner()) = Some(current);
        Ok(())
    }
    pub fn event(&self, kind: EventKind, process: Option<u64>, failure: Option<ApplicationError>) {
        self.record(kind, process, failure, Context::default());
    }
    fn record(
        &self,
        kind: EventKind,
        process: Option<u64>,
        failure: Option<ApplicationError>,
        context: Context,
    ) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        state.next_event += 1;
        let status =
            process.and_then(|id| state.tracker.processes.iter().find(|p| p.id == id).cloned());
        if let Some(error) = &failure
            && error.code == ErrorCode::LogUnavailable
        {
            state.log_failure = Some(error.clone());
        }
        let event = Event {
            sequence: state.next_event,
            source: self.source,
            timestamp_ms: timestamp_ms(),
            host_pid: std::process::id(),
            kind,
            process,
            failure,
            role: context
                .role
                .or_else(|| status.as_ref().map(|status| status.role)),
            status,
            stage: context.stage,
            outcome: context.outcome,
            host_exit_code: context.host_exit_code,
            lifecycle: context.lifecycle,
            webview_failure: context.webview_failure,
            helper_timing: context.helper_timing,
            helper_result: context.helper_result,
            service: context.service,
            panic: None,
        };
        state.first_event_ms.get_or_insert(event.timestamp_ms);
        if let Some(file) = &state.file {
            state.log_failure = file.append(&event).err();
        }
        if state.events.len() == 512 {
            state.events.pop_front();
        }
        state.events.push_back(event);
    }
    /// The panic hook's record. It runs on the panicking thread before unwinding,
    /// so it never waits for a diagnostics lock: the event ring is joined only when its lock
    /// is free, and the line is appended straight to the configured file without
    /// rotation. Without a file, or when the file refuses, the line goes to
    /// standard error, which never carries the payload.
    pub fn panicked(&self, fact: PanicFact) {
        let mut event = Event {
            sequence: 0,
            source: self.source,
            timestamp_ms: timestamp_ms(),
            host_pid: std::process::id(),
            kind: EventKind::Panic,
            process: None,
            failure: None,
            status: None,
            stage: None,
            role: None,
            outcome: None,
            host_exit_code: None,
            lifecycle: None,
            webview_failure: None,
            helper_timing: None,
            helper_result: None,
            service: None,
            panic: Some(fact),
        };
        if let Some(mut state) = try_guard(&self.state) {
            state.next_event += 1;
            event.sequence = state.next_event;
            state.first_event_ms.get_or_insert(event.timestamp_ms);
            if state.events.len() == 512 {
                state.events.pop_front();
            }
            state.events.push_back(event.clone());
        }
        let mut line = serde_json::to_vec(&event)
            .unwrap_or_else(|_| br#"{"kind":"panic","panic":null}"#.to_vec());
        line.push(b'\n');
        let written = try_guard(&self.panic_log)
            .and_then(|current| current.clone())
            .is_some_and(|current| logging::append_unrotated(&current, &line).is_ok());
        if !written {
            let _ = std::io::stderr().write_all(&line);
        }
    }
    /// A panic that a boundary contained; the hook has already recorded where it
    /// was raised, this records which operation it ended.
    pub fn contained_panic(&self, stage: Option<HostStage>, operation: Operation) {
        self.record(
            EventKind::Failure,
            None,
            Some(ApplicationError::new(ErrorCode::Panic, operation)),
            Context {
                stage,
                ..Context::default()
            },
        );
    }
    pub fn helper_result(
        &self,
        process: Option<u64>,
        fact: HelperResult,
        failure: Option<ApplicationError>,
    ) {
        // Count privately captured output without retaining any of its bytes.
        {
            let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
            if let Some(status) = state
                .tracker
                .processes
                .iter_mut()
                .find(|p| Some(p.id) == process)
            {
                status.stdout_bytes = fact.stdout_bytes;
                status.stderr_bytes = fact.stderr_bytes;
            }
        }
        self.record(
            EventKind::HelperResult,
            process,
            failure,
            Context {
                role: Some(ProcessRole::SignIn),
                helper_result: Some(fact),
                ..Context::default()
            },
        );
    }
    pub fn helper_timing(&self, process: Option<u64>, fact: HelperTiming) {
        self.record(
            EventKind::HelperTiming,
            process,
            None,
            Context {
                role: Some(ProcessRole::SignIn),
                helper_timing: Some(fact),
                ..Context::default()
            },
        );
    }
    pub fn service(&self, process: Option<u64>, fact: ServiceFact) {
        self.record(
            EventKind::ServiceEvent,
            process,
            None,
            Context {
                service: Some(fact),
                ..Context::default()
            },
        );
    }
    pub fn failure(&self, error: ApplicationError) {
        self.event(EventKind::Failure, None, Some(error));
    }
    pub fn failure_for(&self, process: u64, error: ApplicationError) {
        self.event(EventKind::Failure, Some(process), Some(error));
    }
    pub fn spawn_failure(&self, role: ProcessRole, error: ApplicationError) {
        self.record(
            EventKind::Failure,
            None,
            Some(error),
            Context {
                role: Some(role),
                ..Context::default()
            },
        );
    }
    pub fn host_event(&self, kind: EventKind, stage: HostStage) {
        self.record(
            kind,
            None,
            None,
            Context {
                stage: Some(stage),
                ..Context::default()
            },
        );
    }
    pub fn host_outcome(&self, stage: HostStage, outcome: HostOutcome) {
        self.record(
            EventKind::StageCompleted,
            None,
            None,
            Context {
                stage: Some(stage),
                outcome: Some(outcome),
                ..Context::default()
            },
        );
    }
    pub fn host_failure(&self, stage: HostStage, error: ApplicationError) {
        self.record(
            EventKind::Failure,
            None,
            Some(error),
            Context {
                stage: Some(stage),
                ..Context::default()
            },
        );
    }
    pub fn host_stopped(&self, code: i32) {
        self.record(
            EventKind::HostStopped,
            None,
            None,
            Context {
                stage: Some(HostStage::Shutdown),
                host_exit_code: Some(code),
                ..Context::default()
            },
        );
    }
    pub fn webview_failure(&self, fact: WebviewFailure) {
        let code = match fact {
            WebviewFailure::ProcessFailed { .. } => ErrorCode::WebviewProcessFailed,
            WebviewFailure::MonitorUnavailable { .. } => ErrorCode::WebviewMonitorUnavailable,
        };
        self.record(
            EventKind::Failure,
            None,
            Some(ApplicationError::new(code, Operation::Webview)),
            Context {
                stage: Some(HostStage::Window),
                webview_failure: Some(fact),
                ..Context::default()
            },
        );
    }
    pub fn lifecycle(
        &self,
        kind: EventKind,
        stage: HostStage,
        fact: LifecycleFact,
        failure: Option<ApplicationError>,
    ) {
        self.record(
            kind,
            None,
            failure,
            Context {
                stage: Some(stage),
                lifecycle: Some(fact),
                ..Context::default()
            },
        );
    }
    pub fn start(&self, pid: u32, role: ProcessRole) -> u64 {
        let id = self
            .state
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .tracker
            .start(pid, role);
        self.event(EventKind::ChildStarted, Some(id), None);
        id
    }
    pub fn finish(&self, id: u64, code: Option<i32>, phase: ProcessPhase) {
        self.state
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .tracker
            .finish(id, code, phase);
        self.event(
            if phase == ProcessPhase::Terminated {
                EventKind::ChildTerminated
            } else {
                EventKind::ChildExited
            },
            Some(id),
            if phase == ProcessPhase::Failed || (phase == ProcessPhase::Exited && code != Some(0)) {
                Some(ApplicationError::new(
                    ErrorCode::ChildFailed,
                    Operation::Launch,
                ))
            } else {
                None
            },
        );
    }
    /// Record byte totals only; terminal contents never enter diagnostic capture.
    pub fn count(&self, id: u64, stream: Stream, bytes: usize) {
        self.state
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .tracker
            .count(id, stream, bytes);
    }
    pub fn capture(&self, id: u64, stream: Stream, bytes: &[u8]) {
        self.state
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .tracker
            .capture(id, stream, bytes);
    }
    pub fn snapshot(&self, after: u64) -> Snapshot {
        let state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        Snapshot {
            paths: state.file.as_ref().map(|f| f.paths.clone()),
            log_failure: state.log_failure.clone(),
            events: state.events.iter().cloned().collect(),
            processes: state.tracker.processes.iter().cloned().collect(),
            output: state
                .tracker
                .output
                .iter()
                .filter(|o| o.sequence > after)
                .cloned()
                .collect(),
            dropped_bytes: state.tracker.dropped_bytes,
        }
    }
}
/// A guard only when it is free now; a poisoned lock still yields its data.
fn try_guard<T>(lock: &Mutex<T>) -> Option<MutexGuard<'_, T>> {
    match lock.try_lock() {
        Ok(guard) => Some(guard),
        Err(TryLockError::Poisoned(poisoned)) => Some(poisoned.into_inner()),
        Err(TryLockError::WouldBlock) => None,
    }
}
fn poisoned() -> ApplicationError {
    ApplicationError::new(ErrorCode::LockPoisoned, Operation::Logging)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;

    fn fact() -> PanicFact {
        PanicFact::new(Some(std::panic::Location::caller()), Some("t"), 1, None)
    }

    fn panic_lines(directory: &Path) -> usize {
        std::fs::read_to_string(directory.join("cadrumo-native.jsonl"))
            .unwrap_or_default()
            .lines()
            .filter(|line| line.contains("\"kind\":\"panic\""))
            .count()
    }

    #[test]
    fn a_held_or_poisoned_state_lock_never_stops_the_panic_record() {
        let directory = tempfile::tempdir().unwrap();
        let diagnostics = Arc::new(Diagnostics::default());
        diagnostics.configure(directory.path(), 1 << 20, 1).unwrap();
        {
            // The panicking code itself may hold the state lock.
            let _held = diagnostics.state.lock().unwrap();
            diagnostics.panicked(fact());
        }
        assert_eq!(panic_lines(directory.path()), 1);
        assert!(diagnostics.snapshot(0).events.is_empty());
        let poisoner = diagnostics.clone();
        std::thread::spawn(move || {
            let _held = poisoner.state.lock().unwrap();
            panic!("poison the state lock");
        })
        .join()
        .unwrap_err();
        diagnostics.panicked(fact());
        assert_eq!(panic_lines(directory.path()), 2);
        let events = diagnostics.snapshot(0).events;
        assert!(matches!(
            events.last().map(|e| e.kind),
            Some(EventKind::Panic)
        ));
    }
}
