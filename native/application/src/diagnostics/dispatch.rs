//! Diagnostic I/O owns its own thread and never borrows the event-ring lock.

use super::{
    Event, Replay, State,
    logging::{LogFile, WritePhase},
};
use crate::error::application::{ApplicationError, ErrorCode, Operation};
use serde::Serialize;
use std::{
    sync::{
        Arc, Mutex, MutexGuard,
        atomic::{AtomicU8, AtomicU64, Ordering},
        mpsc::{self, SyncSender},
    },
    thread,
    time::{Duration, Instant},
};

enum Work {
    Configure(LogFile, Vec<Event>),
    Append(Box<Event>),
    Flush(SyncSender<()>, Instant),
}
impl Work {
    fn weight(&self) -> u64 {
        match self {
            Self::Configure(_, events) => events.len() as u64 + 1,
            Self::Append(_) => 1,
            Self::Flush(..) => 0,
        }
    }
}

/// What the writer thread is doing, so a flush that misses its bound names the cost.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum WriterStage {
    /// Waiting for work; a flush that is not answered from here was never scheduled.
    #[default]
    Waiting,
    /// Replaying the event ring into a newly configured file.
    Configure,
    File(WritePhase),
    /// Recording the outcome under the event-ring lock.
    EventRing,
}
impl WriterStage {
    const ALL: [Self; 7] = [
        Self::Waiting,
        Self::Configure,
        Self::File(WritePhase::Open),
        Self::File(WritePhase::Lock),
        Self::File(WritePhase::Write),
        Self::File(WritePhase::Flush),
        Self::EventRing,
    ];
    fn code(self) -> u8 {
        Self::ALL
            .iter()
            .position(|stage| *stage == self)
            .map_or(0, |index| index as u8)
    }
    fn of(code: u8) -> Self {
        Self::ALL
            .get(usize::from(code))
            .copied()
            .unwrap_or_default()
    }
}

/// Microseconds the last appended batch spent in each stage.
#[derive(Clone, Copy, Debug, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BatchTimings {
    pub open_micros: u64,
    pub lock_micros: u64,
    pub write_micros: u64,
    pub flush_micros: u64,
    pub event_ring_micros: u64,
}

#[derive(Clone, Copy, Debug, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeliveryStatus {
    pub accepted: u64,
    pub completed: u64,
    pub dropped: u64,
    pub failed: u64,
    pub retained_events: u64,
    pub stage: WriterStage,
    /// How long the writer has been in `stage`.
    pub stage_micros: u64,
    pub last_batch: BatchTimings,
    /// How long the last answered flush waited in the queue.
    pub last_flush_wait_micros: u64,
}

struct Counters {
    accepted: AtomicU64,
    completed: AtomicU64,
    dropped: AtomicU64,
    failed: AtomicU64,
    retained_events: AtomicU64,
    epoch: Instant,
    stage: AtomicU8,
    stage_entered_micros: AtomicU64,
    /// Indexed by `WriterStage::code`.
    last_batch_micros: [AtomicU64; 7],
    last_flush_wait_micros: AtomicU64,
}
impl Default for Counters {
    fn default() -> Self {
        Self {
            accepted: AtomicU64::default(),
            completed: AtomicU64::default(),
            dropped: AtomicU64::default(),
            failed: AtomicU64::default(),
            retained_events: AtomicU64::default(),
            epoch: Instant::now(),
            stage: AtomicU8::default(),
            stage_entered_micros: AtomicU64::default(),
            last_batch_micros: Default::default(),
            last_flush_wait_micros: AtomicU64::default(),
        }
    }
}
impl Counters {
    fn now_micros(&self) -> u64 {
        u64::try_from(self.epoch.elapsed().as_micros()).unwrap_or(u64::MAX)
    }
}

/// The stages of one unit of work, published as they are entered.
struct StageClock<'a> {
    counters: &'a Counters,
    spent: [u64; 7],
}
impl<'a> StageClock<'a> {
    fn start(counters: &'a Counters, stage: WriterStage) -> Self {
        counters
            .stage_entered_micros
            .store(counters.now_micros(), Ordering::Relaxed);
        counters.stage.store(stage.code(), Ordering::Relaxed);
        Self {
            counters,
            spent: [0; 7],
        }
    }
    fn enter(&mut self, stage: WriterStage) {
        let now = self.counters.now_micros();
        let previous = self.counters.stage.swap(stage.code(), Ordering::Relaxed);
        let entered = self
            .counters
            .stage_entered_micros
            .swap(now, Ordering::Relaxed);
        self.spent[usize::from(previous)] += now.saturating_sub(entered);
    }
    /// Locks the event ring as a stage of its own; a poisoned ring still yields its data.
    fn event_ring<'s>(&mut self, state: &'s Mutex<State>) -> MutexGuard<'s, State> {
        self.enter(WriterStage::EventRing);
        state.lock().unwrap_or_else(|error| error.into_inner())
    }
    fn finish(mut self) {
        self.enter(WriterStage::Waiting);
        for (slot, spent) in self.counters.last_batch_micros.iter().zip(self.spent) {
            slot.store(spent, Ordering::Relaxed);
        }
    }
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
                            let mut clock =
                                StageClock::start(&worker_counters, WriterStage::Configure);
                            let result = configure(&mut file, &mut replay, target, &events);
                            let mut ring = clock.event_ring(&state);
                            ring.file = file.clone();
                            ring.log_failure = result.as_ref().err().cloned();
                            drop(ring);
                            clock.finish();
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
                            let mut clock = StageClock::start(
                                &worker_counters,
                                WriterStage::File(WritePhase::Open),
                            );
                            let result = file.as_ref().map_or(Ok(()), |file| {
                                file.append_batch(&batch, |phase| {
                                    clock.enter(WriterStage::File(phase));
                                })
                            });
                            if file.is_some() {
                                clock.event_ring(&state).log_failure =
                                    result.as_ref().err().cloned();
                            }
                            clock.finish();
                            result
                        }
                        Work::Flush(done, requested) => {
                            worker_counters.last_flush_wait_micros.store(
                                u64::try_from(requested.elapsed().as_micros()).unwrap_or(u64::MAX),
                                Ordering::Relaxed,
                            );
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
        self.sender
            .try_send(Work::Flush(sender, Instant::now()))
            .is_ok()
            && receiver.recv_timeout(timeout).is_ok()
    }

    pub(super) fn status(&self) -> DeliveryStatus {
        let counters = &self.counters;
        let spent = |stage: WriterStage| {
            counters.last_batch_micros[usize::from(stage.code())].load(Ordering::Relaxed)
        };
        DeliveryStatus {
            accepted: counters.accepted.load(Ordering::Acquire),
            completed: counters.completed.load(Ordering::Acquire),
            dropped: counters.dropped.load(Ordering::Relaxed),
            failed: counters.failed.load(Ordering::Relaxed),
            retained_events: counters.retained_events.load(Ordering::Relaxed),
            stage: WriterStage::of(counters.stage.load(Ordering::Relaxed)),
            stage_micros: counters
                .now_micros()
                .saturating_sub(counters.stage_entered_micros.load(Ordering::Relaxed)),
            last_batch: BatchTimings {
                open_micros: spent(WriterStage::File(WritePhase::Open)),
                lock_micros: spent(WriterStage::File(WritePhase::Lock)),
                write_micros: spent(WriterStage::File(WritePhase::Write)),
                flush_micros: spent(WriterStage::File(WritePhase::Flush)),
                event_ring_micros: spent(WriterStage::EventRing),
            },
            last_flush_wait_micros: counters.last_flush_wait_micros.load(Ordering::Relaxed),
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
    use crate::diagnostics::{Diagnostics, EventKind, delivery_wait::delivered};

    /// Only a writer that is hung can outlast this; no healthy one is expected to be near it.
    const HANG: Duration = Duration::from_secs(60);

    /// Waits for the writer to enter `stage`, which depends on when the machine schedules it.
    fn entered(writer: &LogWriter, stage: WriterStage) -> DeliveryStatus {
        let started = Instant::now();
        loop {
            let status = writer.status();
            if status.stage == stage {
                return status;
            }
            assert!(
                started.elapsed() < HANG,
                "writer never entered {stage:?}: {status:?}"
            );
            thread::sleep(Duration::from_millis(1));
        }
    }

    #[test]
    fn a_missed_flush_names_the_stage_the_writer_is_held_in() {
        let directory = tempfile::tempdir().unwrap();
        let file = LogFile::new(directory.path(), 1 << 20, 1).unwrap();
        let diagnostics = Diagnostics::default();
        let state = diagnostics.state.clone();
        let writer = LogWriter::new(state.clone());
        assert!(writer.configure(file.clone(), Vec::new()));
        assert!(writer.flush(HANG));
        assert_eq!(writer.status().stage, WriterStage::Waiting);

        let ring = state.lock().unwrap();
        assert!(writer.configure(file, Vec::new()));
        entered(&writer, WriterStage::EventRing);
        // Held at the ring, the flush is not answered however long it is waited for.
        assert!(!writer.flush(Duration::from_millis(50)));
        let held = writer.status();
        assert_eq!(held.stage, WriterStage::EventRing);
        assert!(held.stage_micros >= 50_000, "{held:?}");
        drop(ring);
        assert!(writer.flush(HANG));
        assert_eq!(writer.status().stage, WriterStage::Waiting);
    }

    #[test]
    fn an_appended_batch_reports_where_its_time_went() {
        let directory = tempfile::tempdir().unwrap();
        let diagnostics = Diagnostics::default();
        diagnostics.configure(directory.path(), 1 << 20, 1).unwrap();
        diagnostics.event(EventKind::HostStarted, None, None);
        delivered(&diagnostics);
        let status = diagnostics.log_delivery_status();
        let spent = status.last_batch;
        assert_eq!(status.stage, WriterStage::Waiting);
        assert!(
            spent.open_micros + spent.lock_micros + spent.write_micros + spent.flush_micros > 0,
            "{status:?}"
        );
    }

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
        let writer = Arc::new(LogWriter::new(state.clone()));
        let file = LogFile::new(directory.path(), 1 << 20, 1).unwrap();
        assert!(writer.configure(file.clone(), Vec::new()));
        // Submitting never waits for the writer, which stays held at the ring until the
        // guard is dropped below; were it to wait, this could not finish.
        let (finished, submitted) = mpsc::sync_channel(1);
        let producer = writer.clone();
        thread::spawn(move || {
            for _ in 0..100 {
                producer.configure(file.clone(), events.clone());
            }
            let _ = finished.send(());
        });
        let submitted = submitted.recv_timeout(HANG);
        assert!(submitted.is_ok(), "submission waited for the held writer");
        assert!(writer.status().retained_events <= 4096);
        assert!(writer.status().dropped > 0);
        assert!(!writer.flush(Duration::from_millis(10)));
        drop(guard);
        assert!(writer.flush(HANG));
        assert_eq!(writer.status().retained_events, 0);
    }
}
