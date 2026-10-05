pub mod logging;

use crate::{
    diagnostics::logging::{LogFile, LogPaths},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process::status::{
        OutputChunk, ProcessPhase, ProcessRole, ProcessStatus, Stream, Tracker, timestamp_ms,
    },
};
use serde::Serialize;
use std::{collections::VecDeque, path::Path, sync::Mutex};

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EventKind {
    HostStarted,
    HeadlessSelected,
    GuiSelected,
    ChildStarted,
    ChildExited,
    ChildTerminated,
    Failure,
    HostStopped,
}
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Event {
    pub timestamp_ms: u64,
    pub host_pid: u32,
    pub kind: EventKind,
    pub process: Option<u64>,
    pub failure: Option<ApplicationError>,
    pub status: Option<ProcessStatus>,
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
    log_failure: Option<ApplicationError>,
    events: VecDeque<Event>,
    tracker: Tracker,
}
#[derive(Default)]
pub struct Diagnostics {
    state: Mutex<State>,
}
impl Diagnostics {
    pub fn configure(&self, directory: &Path, max_bytes: u64, backups: u32) -> Result<()> {
        let file = LogFile::new(directory, max_bytes, backups)?;
        let mut state = self.state.lock().map_err(|_| poisoned())?;
        for event in &state.events {
            file.append(event)?;
        }
        state.file = Some(file);
        Ok(())
    }
    pub fn event(&self, kind: EventKind, process: Option<u64>, failure: Option<ApplicationError>) {
        let mut state = self.state.lock().unwrap_or_else(|e| e.into_inner());
        let event = Event {
            timestamp_ms: timestamp_ms(),
            host_pid: std::process::id(),
            kind,
            process,
            failure,
            status: process
                .and_then(|id| state.tracker.processes.iter().find(|p| p.id == id).cloned()),
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
        if error.code == ErrorCode::LogUnavailable {
            self.state
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .log_failure = Some(error.clone());
        }
        self.event(EventKind::Failure, None, Some(error));
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
