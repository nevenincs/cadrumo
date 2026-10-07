pub mod lifecycle;
pub mod logging;
pub mod webview;

use crate::{
    diagnostics::{
        lifecycle::LifecycleFact,
        logging::{LogFile, LogPaths},
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
    path::{Path, PathBuf},
    sync::Mutex,
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
    Failure,
    HostStopped,
}
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DiagnosticSource {
    #[default]
    Desktop,
    Manager,
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
}
#[derive(Default)]
pub struct Diagnostics {
    state: Mutex<State>,
    source: DiagnosticSource,
}
impl Diagnostics {
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
        state.file = Some(file);
        state.pending_replay = None;
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
        };
        if let Some(file) = &state.file
            && let Err(error) = file.append(&event)
        {
            state.log_failure = Some(error);
        }
        if state.events.len() == 512 {
            state.events.pop_front();
        }
        state.events.push_back(event);
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
            None,
        );
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
fn poisoned() -> ApplicationError {
    ApplicationError::new(ErrorCode::LockPoisoned, Operation::Logging)
}
