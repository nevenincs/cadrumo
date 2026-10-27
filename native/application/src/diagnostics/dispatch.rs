//! Diagnostic I/O owns its own thread and never borrows the event-ring lock.

use super::{Event, Replay, State, logging::LogFile};
use crate::error::application::{ApplicationError, ErrorCode, Operation};
use serde::Serialize;
use std::{
    sync::{
        Arc, Mutex,
        atomic::{AtomicU64, Ordering},
        mpsc::{self, SyncSender},
    },
    thread,
    time::Duration,
};

enum Work {
    Configure(LogFile, Vec<Event>),
    Append(Box<Event>),
    Flush(SyncSender<()>),
}
impl Work {
    fn weight(&self) -> u64 {
        match self {
            Self::Configure(_, events) => events.len() as u64 + 1,
            Self::Append(_) => 1,
            Self::Flush(_) => 0,
        }
    }
}

#[derive(Clone, Copy, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeliveryStatus {
    pub accepted: u64,
    pub completed: u64,
    pub dropped: u64,
    pub failed: u64,
    pub retained_events: u64,
}

#[derive(Default)]
struct Counters {
    accepted: AtomicU64,
    completed: AtomicU64,
    dropped: AtomicU64,
    failed: AtomicU64,
    retained_events: AtomicU64,
}

pub(super) struct LogWriter {
    sender: SyncSender<Work>,
    counters: Arc<Counters>,
}

impl LogWriter {
    pub(super) fn new(state: Arc<Mutex<State>>) -> Self {
        let (sender, receiver) = mpsc::sync_channel::<Work>(4096);
        let counters = Arc::new(Counters::default());
        let worker_counters = counters.clone();
        let _ = thread::Builder::new()
            .name("diagnostic-file".into())
            .spawn(move || {
                let mut file: Option<LogFile> = None;
                let mut replay: Option<Replay> = None;
                let mut deferred = None;
                while let Some(work) = deferred.take().or_else(|| receiver.recv().ok()) {
                    let mut count = 1;
                    let mut weight = work.weight();
                    let result = match work {
                        Work::Configure(target, events) => {
                            let result = configure(&mut file, &mut replay, target, &events);
                            let mut state = state.lock().unwrap_or_else(|error| error.into_inner());
                            state.file = file.clone();
                            state.log_failure = result.as_ref().err().cloned();
                            result
                        }
                        Work::Append(event) => {
                            let mut batch = vec![*event];
                            while batch.len() < 64 {
                                match receiver.try_recv() {
                                    Ok(Work::Append(event)) => batch.push(*event),
                                    Ok(other) => {
                                        deferred = Some(other);
                                        break;
                                    }
                                    Err(_) => break,
                                }
                            }
                            count = batch.len() as u64;
                            weight = count;
                            let result = file
                                .as_ref()
                                .map_or(Ok(()), |file| file.append_batch(&batch));
                            if file.is_some() {
                                state
                                    .lock()
                                    .unwrap_or_else(|error| error.into_inner())
                                    .log_failure = result.as_ref().err().cloned();
                            }
                            result
                        }
                        Work::Flush(done) => {
                            let _ = done.try_send(());
                            continue;
                        }
                    };
                    if result.is_err() {
                        worker_counters.failed.fetch_add(count, Ordering::Relaxed);
                    }
                    worker_counters
                        .retained_events
                        .fetch_sub(weight, Ordering::Relaxed);
                    worker_counters
                        .completed
                        .fetch_add(count, Ordering::Release);
                }
            });
        Self { sender, counters }
    }

    fn submit(&self, work: Work) -> bool {
        let weight = work.weight();
        // Replay snapshots consume the same budget as individual records.
        if !self.reserve(weight) {
            self.counters.dropped.fetch_add(1, Ordering::Relaxed);
            return false;
        }
        // Count before publishing so a fast consumer cannot finish before admission.
        self.counters.accepted.fetch_add(1, Ordering::Relaxed);
        if self.sender.try_send(work).is_err() {
            self.counters
                .retained_events
                .fetch_sub(weight, Ordering::Relaxed);
            self.counters.accepted.fetch_sub(1, Ordering::Relaxed);
            self.counters.dropped.fetch_add(1, Ordering::Relaxed);
            return false;
        }
        true
    }

    fn reserve(&self, weight: u64) -> bool {
        let mut retained = self.counters.retained_events.load(Ordering::Relaxed);
        loop {
            if retained + weight > 4096 {
                return false;
            }
            match self.counters.retained_events.compare_exchange_weak(
                retained,
                retained + weight,
                Ordering::Relaxed,
                Ordering::Relaxed,
            ) {
                Ok(_) => return true,
                Err(current) => retained = current,
            }
        }
    }

    pub(super) fn configure(&self, file: LogFile, events: Vec<Event>) -> bool {
        self.submit(Work::Configure(file, events))
    }

    pub(super) fn append(&self, event: Event) -> bool {
        self.submit(Work::Append(Box::new(event)))
    }

    pub(super) fn flush(&self, timeout: Duration) -> bool {
        let (sender, receiver) = mpsc::sync_channel(1);
        self.sender.try_send(Work::Flush(sender)).is_ok() && receiver.recv_timeout(timeout).is_ok()
    }

    pub(super) fn status(&self) -> DeliveryStatus {
        DeliveryStatus {
            accepted: self.counters.accepted.load(Ordering::Acquire),
            completed: self.counters.completed.load(Ordering::Acquire),
            dropped: self.counters.dropped.load(Ordering::Relaxed),
            failed: self.counters.failed.load(Ordering::Relaxed),
            retained_events: self.counters.retained_events.load(Ordering::Relaxed),
        }
    }
}

fn configure(
    active: &mut Option<LogFile>,
    pending: &mut Option<Replay>,
    target: LogFile,
    events: &[Event],
) -> Result<(), ApplicationError> {
    if active
        .as_ref()
        .is_some_and(|file| file.paths.current == target.paths.current)
    {
        *active = Some(target);
        *pending = None;
        return Ok(());
    }
    let replay = pending.get_or_insert_with(|| Replay {
        current: target.paths.current.clone(),
        through: 0,
    });
    if replay.current != target.paths.current {
        replay.current = target.paths.current.clone();
        replay.through = 0;
    }
    for event in events {
        if event.sequence > replay.through {
            target.append(event)?;
            replay.through = event.sequence;
        }
    }
    *active = Some(target);
    *pending = None;
    Ok(())
}

pub(super) fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::LogUnavailable, Operation::Logging)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::diagnostics::{Diagnostics, EventKind};
    use std::time::Instant;

    #[test]
    fn repeated_replay_requests_share_the_record_memory_budget() {
        let directory = tempfile::tempdir().unwrap();
        let diagnostics = Diagnostics::default();
        for _ in 0..512 {
            diagnostics.event(EventKind::HostStarted, None, None);
        }
        let state = diagnostics.state.clone();
        let guard = state.lock().unwrap();
        let events: Vec<_> = guard.events.iter().cloned().collect();
        let writer = LogWriter::new(state.clone());
        let file = LogFile::new(directory.path(), 1 << 20, 1).unwrap();
        assert!(writer.configure(file.clone(), Vec::new()));
        let started = Instant::now();
        for _ in 0..100 {
            writer.configure(file.clone(), events.clone());
        }
        assert!(started.elapsed() < Duration::from_secs(1));
        assert!(writer.status().retained_events <= 4096);
        assert!(writer.status().dropped > 0);
        assert!(!writer.flush(Duration::from_millis(10)));
        drop(guard);
        assert!(writer.flush(Duration::from_secs(2)));
        assert_eq!(writer.status().retained_events, 0);
    }
}
