//! Typed process lifecycle and bounded, memory-only stream capture.
use serde::Serialize;
use std::{
    collections::VecDeque,
    time::{SystemTime, UNIX_EPOCH},
};

#[derive(Clone, Copy, Debug, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ProcessRole {
    Environment,
    SignIn,
    ManagerDispatch,
    Cli,
    Tui,
    /// The packaged interpreter as an interactive REPL.
    Repl,
    /// The platform's interactive system shell.
    Console,
}
#[derive(Clone, Copy, Debug, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ProcessPhase {
    Running,
    Exited,
    Terminated,
    Failed,
}
#[derive(Clone, Copy, Debug, Serialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Stream {
    Stdout,
    Stderr,
    Terminal,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessStatus {
    pub id: u64,
    pub pid: u32,
    pub role: ProcessRole,
    pub phase: ProcessPhase,
    pub started_ms: u64,
    pub finished_ms: Option<u64>,
    pub exit_code: Option<i32>,
    pub stdout_bytes: u64,
    pub stderr_bytes: u64,
    pub terminal_bytes: u64,
}
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OutputChunk {
    pub sequence: u64,
    pub process: u64,
    pub stream: Stream,
    pub bytes: Vec<u8>,
}

pub fn timestamp_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .min(u128::from(u64::MAX)) as u64
}

#[derive(Default)]
pub struct Tracker {
    pub processes: VecDeque<ProcessStatus>,
    pub output: VecDeque<OutputChunk>,
    next_process: u64,
    sequence: u64,
    buffered: usize,
    pub dropped_bytes: u64,
}
impl Tracker {
    pub fn start(&mut self, pid: u32, role: ProcessRole) -> u64 {
        self.next_process += 1;
        if self.processes.len() == 128 {
            self.processes.pop_front();
        }
        self.processes.push_back(ProcessStatus {
            id: self.next_process,
            pid,
            role,
            phase: ProcessPhase::Running,
            started_ms: timestamp_ms(),
            finished_ms: None,
            exit_code: None,
            stdout_bytes: 0,
            stderr_bytes: 0,
            terminal_bytes: 0,
        });
        self.next_process
    }
    pub fn finish(&mut self, id: u64, code: Option<i32>, phase: ProcessPhase) {
        if let Some(status) = self.processes.iter_mut().find(|p| p.id == id)
            && status.finished_ms.is_none()
        {
            status.phase = phase;
            status.exit_code = code;
            status.finished_ms = Some(timestamp_ms());
        }
    }
    pub fn capture(&mut self, id: u64, stream: Stream, bytes: &[u8]) {
        if let Some(status) = self.processes.iter_mut().find(|p| p.id == id) {
            let count = match stream {
                Stream::Stdout => &mut status.stdout_bytes,
                Stream::Stderr => &mut status.stderr_bytes,
                Stream::Terminal => &mut status.terminal_bytes,
            };
            *count = count.saturating_add(bytes.len() as u64);
        }
        const LIMIT: usize = 256 * 1024;
        let retained = &bytes[bytes.len().saturating_sub(LIMIT)..];
        self.dropped_bytes += (bytes.len() - retained.len()) as u64;
        while self.buffered + retained.len() > LIMIT || self.output.len() >= 512 {
            if let Some(old) = self.output.pop_front() {
                self.buffered -= old.bytes.len();
                self.dropped_bytes += old.bytes.len() as u64;
            } else {
                break;
            }
        }
        self.sequence += 1;
        self.buffered += retained.len();
        self.output.push_back(OutputChunk {
            sequence: self.sequence,
            process: id,
            stream,
            bytes: retained.to_vec(),
        });
    }
}
