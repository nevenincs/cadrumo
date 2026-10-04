//! Log records, source state, the bounded ring and paced delivery to
//! subscribers.
use super::format::Level;
use cadrumo_application::{error::application::ApplicationError, process::status::ProcessRole};
use serde::Serialize;
use std::{
    collections::VecDeque,
    time::{Duration, Instant},
};

pub const RING: usize = 10_000;
pub const BACKLOG: usize = 5_000;
/// At most ten batches per second per subscription.
pub const BATCH_INTERVAL: Duration = Duration::from_millis(100);
/// One batch can carry the whole backlog.
pub const BATCH_RECORDS: usize = BACKLOG;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub struct ProcessRef {
    pub role: ProcessRole,
    pub pid: u32,
}

/// A record before the ring numbers it. `source` is an open enumeration.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Entry {
    pub source: &'static str,
    pub timestamp: String,
    pub timestamp_ms: Option<u64>,
    pub level: Option<Level>,
    pub logger: Option<String>,
    pub message: String,
    pub detail: Option<String>,
    pub process: Option<ProcessRef>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogRecord {
    pub seq: u64,
    pub source: &'static str,
    pub timestamp: String,
    pub timestamp_ms: Option<u64>,
    pub level: Option<Level>,
    pub logger: Option<String>,
    pub message: String,
    pub detail: Option<String>,
    pub process: Option<ProcessRef>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceKind {
    /// The log file or one of its rotations exists and was read.
    Available,
    /// No log file exists yet; distinct from an existing empty file.
    Missing,
    /// A log file exists but could not be read; `failure` says why.
    Unreadable,
}

#[derive(Clone, Serialize)]
pub struct LogSourceState {
    pub kind: SourceKind,
    /// The log file the state describes.
    pub detail: String,
    pub failure: Option<ApplicationError>,
}

impl LogSourceState {
    fn same(&self, other: &Self) -> bool {
        self.kind == other.kind
            && self.detail == other.detail
            && self.failure.as_ref().map(|f| (f.code, f.operation))
                == other.failure.as_ref().map(|f| (f.code, f.operation))
    }
}

#[derive(Clone, Serialize)]
pub struct LogBatch {
    pub records: Vec<LogRecord>,
    /// Records this subscription lost to ring overflow since its previous batch.
    pub dropped: u64,
    pub state: LogSourceState,
}

pub type Sink = Box<dyn Fn(LogBatch) -> bool + Send>;

struct Subscriber {
    id: u64,
    sink: Sink,
    next: u64,
    last_sent: Option<Instant>,
    sent_state: Option<LogSourceState>,
    dropped: u64,
}

/// The record ring and its subscriptions.
pub struct Aggregate {
    ring: VecDeque<LogRecord>,
    next_seq: u64,
    subscribers: Vec<Subscriber>,
    next_subscription: u64,
    pub state: LogSourceState,
}

/// Subscriptions beyond this evict the oldest; a reloaded shell that never
/// unsubscribed cannot accumulate them.
const SUBSCRIBERS: usize = 8;

impl Aggregate {
    pub fn new(state: LogSourceState) -> Self {
        Self {
            ring: VecDeque::with_capacity(RING),
            next_seq: 1,
            subscribers: Vec::new(),
            next_subscription: 1,
            state,
        }
    }

    pub fn push(&mut self, entry: Entry) {
        if self.ring.len() == RING {
            self.ring.pop_front();
        }
        self.ring.push_back(LogRecord {
            seq: self.next_seq,
            source: entry.source,
            timestamp: entry.timestamp,
            timestamp_ms: entry.timestamp_ms,
            level: entry.level,
            logger: entry.logger,
            message: entry.message,
            detail: entry.detail,
            process: entry.process,
        });
        self.next_seq += 1;
    }

    fn oldest(&self) -> u64 {
        self.ring.front().map_or(self.next_seq, |record| record.seq)
    }

    /// Starts a subscription whose first batch is the last [`BACKLOG`] records.
    pub fn subscribe(&mut self, sink: Sink) -> u64 {
        if self.subscribers.len() == SUBSCRIBERS {
            self.subscribers.remove(0);
        }
        let id = self.next_subscription;
        self.next_subscription += 1;
        self.subscribers.push(Subscriber {
            id,
            sink,
            next: self
                .oldest()
                .max(self.next_seq.saturating_sub(BACKLOG as u64)),
            last_sent: None,
            sent_state: None,
            dropped: 0,
        });
        id
    }

    pub fn unsubscribe(&mut self, id: u64) -> bool {
        let before = self.subscribers.len();
        self.subscribers.retain(|subscriber| subscriber.id != id);
        self.subscribers.len() != before
    }

    pub fn clear_subscriptions(&mut self) {
        self.subscribers.clear();
    }

    /// Sends each due subscription one batch of what it has not seen. A
    /// subscription receives no batch within [`BATCH_INTERVAL`] of its last
    /// one, and none when nothing changed. A sink that refuses ends it.
    pub fn deliver(&mut self, now: Instant) {
        let oldest = self.oldest();
        let mut subscribers = std::mem::take(&mut self.subscribers);
        subscribers.retain_mut(|subscriber| {
            if subscriber
                .last_sent
                .is_some_and(|sent| now.saturating_duration_since(sent) < BATCH_INTERVAL)
            {
                return true;
            }
            if subscriber.next < oldest {
                subscriber.dropped += oldest - subscriber.next;
                subscriber.next = oldest;
            }
            let skip = usize::try_from(subscriber.next - oldest).unwrap_or(usize::MAX);
            let records: Vec<LogRecord> = self
                .ring
                .iter()
                .skip(skip)
                .take(BATCH_RECORDS)
                .cloned()
                .collect();
            let changed = subscriber
                .sent_state
                .as_ref()
                .is_none_or(|sent| !sent.same(&self.state));
            if records.is_empty() && !changed && subscriber.dropped == 0 {
                return true;
            }
            if let Some(last) = records.last() {
                subscriber.next = last.seq + 1;
            }
            let batch = LogBatch {
                records,
                dropped: std::mem::take(&mut subscriber.dropped),
                state: self.state.clone(),
            };
            subscriber.last_sent = Some(now);
            subscriber.sent_state = Some(self.state.clone());
            (subscriber.sink)(batch)
        });
        self.subscribers = subscribers;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    fn entry(message: &str) -> Entry {
        Entry {
            source: "python",
            timestamp: String::new(),
            timestamp_ms: None,
            level: None,
            logger: None,
            message: message.to_owned(),
            detail: None,
            process: None,
        }
    }

    fn available() -> LogSourceState {
        LogSourceState {
            kind: SourceKind::Available,
            detail: "cadrumo.log".into(),
            failure: None,
        }
    }

    type Received = Arc<Mutex<Vec<LogBatch>>>;

    fn collector() -> (Sink, Received) {
        let received: Received = Arc::default();
        let into = received.clone();
        (
            Box::new(move |batch| {
                into.lock().unwrap().push(batch);
                true
            }),
            received,
        )
    }

    #[test]
    fn ring_keeps_the_newest_records_and_backlog_starts_within_them() {
        let mut aggregate = Aggregate::new(available());
        for index in 0..RING + 2_500 {
            aggregate.push(entry(&index.to_string()));
        }
        assert_eq!(aggregate.ring.len(), RING);
        assert_eq!(aggregate.oldest(), 2_501);
        let (sink, received) = collector();
        aggregate.subscribe(sink);
        aggregate.deliver(Instant::now());
        let batches = received.lock().unwrap();
        assert_eq!(batches.len(), 1);
        let records = &batches[0].records;
        assert_eq!(records.len(), BACKLOG);
        assert_eq!(records[0].seq, (RING + 2_500 - BACKLOG + 1) as u64);
        assert_eq!(records.last().unwrap().message, (RING + 2_499).to_string());
        assert!(
            records
                .windows(2)
                .all(|pair| pair[1].seq == pair[0].seq + 1)
        );
        assert_eq!(batches[0].dropped, 0);
    }

    #[test]
    fn overflow_between_batches_is_counted_as_dropped() {
        let mut aggregate = Aggregate::new(available());
        let (sink, received) = collector();
        aggregate.subscribe(sink);
        let start = Instant::now();
        aggregate.deliver(start);
        for index in 0..RING + 1_234 {
            aggregate.push(entry(&index.to_string()));
        }
        aggregate.deliver(start + BATCH_INTERVAL);
        aggregate.deliver(start + BATCH_INTERVAL * 2);
        let batches = received.lock().unwrap();
        assert_eq!(batches.len(), 3);
        assert_eq!(batches[1].dropped, 1_234);
        assert_eq!(batches[1].records[0].message, "1234");
        assert_eq!(batches[2].dropped, 0);
        let delivered = batches.iter().map(|b| b.records.len()).sum::<usize>() as u64;
        assert_eq!(delivered + batches[1].dropped, (RING + 1_234) as u64);
    }

    #[test]
    fn batches_are_paced_and_only_sent_on_change() {
        let mut aggregate = Aggregate::new(available());
        let (sink, received) = collector();
        let id = aggregate.subscribe(sink);
        let start = Instant::now();
        aggregate.deliver(start);
        aggregate.push(entry("a"));
        aggregate.deliver(start + BATCH_INTERVAL / 2);
        assert_eq!(received.lock().unwrap().len(), 1);
        aggregate.deliver(start + BATCH_INTERVAL);
        assert_eq!(received.lock().unwrap().len(), 2);
        aggregate.deliver(start + BATCH_INTERVAL * 3);
        assert_eq!(received.lock().unwrap().len(), 2, "unchanged sends nothing");
        aggregate.state = LogSourceState {
            kind: SourceKind::Missing,
            ..available()
        };
        aggregate.deliver(start + BATCH_INTERVAL * 4);
        let batches = received.lock().unwrap();
        assert_eq!(batches.len(), 3, "a state change is delivered");
        assert!(batches[2].records.is_empty());
        assert_eq!(batches[2].state.kind, SourceKind::Missing);
        drop(batches);
        assert!(aggregate.unsubscribe(id));
        assert!(!aggregate.unsubscribe(id));
    }

    #[test]
    fn refusing_sinks_end_and_excess_subscriptions_evict_the_oldest() {
        let mut aggregate = Aggregate::new(available());
        aggregate.subscribe(Box::new(|_| false));
        aggregate.deliver(Instant::now());
        assert!(aggregate.subscribers.is_empty());
        let ids: Vec<u64> = (0..SUBSCRIBERS + 1)
            .map(|_| aggregate.subscribe(Box::new(|_| true)))
            .collect();
        assert_eq!(aggregate.subscribers.len(), SUBSCRIBERS);
        assert!(!aggregate.unsubscribe(ids[0]));
        assert!(aggregate.unsubscribe(ids[SUBSCRIBERS]));
    }
}
