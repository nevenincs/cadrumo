//! Log records, source state, the bounded ring and paced delivery to
//! subscribers.
use super::format::Level;
use cadrumo_application::{error::application::ApplicationError, process::status::ProcessRole};
use serde::Serialize;
use std::{
    collections::VecDeque,
    io,
    sync::Arc,
    time::{Duration, Instant},
};

pub const RING: usize = 10_000;
pub const BACKLOG: usize = 5_000;
/// At most ten batches per second per subscription.
pub const BATCH_INTERVAL: Duration = Duration::from_millis(100);
/// Records in one batch at most.
pub const BATCH_RECORDS: usize = BACKLOG;
/// Bytes of one batch's JSON at most, so one delivery stays one bounded
/// script. A larger backlog spreads over several paced batches.
pub const BATCH_BYTES: usize = 1024 * 1024;

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

/// Receives a subscription's batches; returning false ends the subscription.
/// It is called without the ring's lock, on the thread that polls.
pub type Sink = Arc<dyn Fn(LogBatch) -> bool + Send + Sync>;

/// Counts bytes written, to size JSON without building it.
struct Counter(usize);

impl io::Write for Counter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0 += bytes.len();
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

/// The length of `value` as compact JSON, the form a channel sends. A value
/// that cannot be serialized counts as a whole batch, so it travels alone.
fn json_len(value: &impl Serialize) -> usize {
    let mut counter = Counter(0);
    match serde_json::to_writer(&mut counter, value) {
        Ok(()) => counter.0,
        Err(_) => BATCH_BYTES,
    }
}

fn digits(value: u64) -> usize {
    value.checked_ilog10().map_or(1, |log| log as usize + 1)
}

/// A record whose JSON length is known except for its sequence number, so
/// sizing happens before the ring's lock is taken.
pub struct Prepared {
    record: LogRecord,
    bytes: usize,
}

impl Prepared {
    pub fn new(entry: Entry) -> Self {
        let record = LogRecord {
            seq: 0,
            source: entry.source,
            timestamp: entry.timestamp,
            timestamp_ms: entry.timestamp_ms,
            level: entry.level,
            logger: entry.logger,
            message: entry.message,
            detail: entry.detail,
            process: entry.process,
        };
        // The placeholder sequence number is one digit.
        let bytes = json_len(&record).saturating_sub(1);
        Self { record, bytes }
    }
}

struct Stored {
    record: LogRecord,
    /// The record's JSON length.
    bytes: usize,
}

struct Subscriber {
    id: u64,
    sink: Sink,
    /// The next record to send. It is set at the first delivery, so a
    /// subscription that starts before the first poll begins with the backlog.
    next: Option<u64>,
    last_sent: Option<Instant>,
    sent_state: Option<LogSourceState>,
    dropped: u64,
}

/// One batch for one subscription, sent after the ring's lock is released.
pub struct Delivery {
    subscription: u64,
    sink: Sink,
    batch: LogBatch,
}

/// Sends each batch in order and returns the subscriptions whose sink refused.
pub fn send(deliveries: Vec<Delivery>) -> Vec<u64> {
    deliveries
        .into_iter()
        .filter_map(|delivery| (!(delivery.sink)(delivery.batch)).then_some(delivery.subscription))
        .collect()
}

/// The record ring and its subscriptions.
pub struct Aggregate {
    ring: VecDeque<Stored>,
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

    pub fn push(&mut self, prepared: Prepared) {
        if self.ring.len() == RING {
            self.ring.pop_front();
        }
        let Prepared { mut record, bytes } = prepared;
        record.seq = self.next_seq;
        self.ring.push_back(Stored {
            record,
            bytes: bytes + digits(self.next_seq),
        });
        self.next_seq += 1;
    }

    /// Empties the ring; sequence numbers keep increasing.
    pub fn clear_records(&mut self) {
        self.ring.clear();
    }

    fn oldest(&self) -> u64 {
        self.ring
            .front()
            .map_or(self.next_seq, |stored| stored.record.seq)
    }

    /// Whether no subscription exists.
    pub fn idle(&self) -> bool {
        self.subscribers.is_empty()
    }

    /// Starts a subscription whose first batches carry the last [`BACKLOG`]
    /// records present at its first delivery.
    pub fn subscribe(&mut self, sink: Sink) -> u64 {
        if self.subscribers.len() == SUBSCRIBERS {
            self.subscribers.remove(0);
        }
        let id = self.next_subscription;
        self.next_subscription += 1;
        self.subscribers.push(Subscriber {
            id,
            sink,
            next: None,
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

    /// Ends the subscriptions whose sink refused a batch.
    pub fn end(&mut self, refused: &[u64]) {
        self.subscribers
            .retain(|subscriber| !refused.contains(&subscriber.id));
    }

    pub fn clear_subscriptions(&mut self) {
        self.subscribers.clear();
    }

    /// Picks one batch for each due subscription from what it has not seen,
    /// up to [`BATCH_RECORDS`] records and [`BATCH_BYTES`] of JSON; the rest
    /// waits for later batches. A subscription receives no batch within
    /// [`BATCH_INTERVAL`] of its last one, and none when nothing changed.
    pub fn deliver(&mut self, now: Instant) -> Vec<Delivery> {
        let oldest = self.oldest();
        let backlog = oldest.max(self.next_seq.saturating_sub(BACKLOG as u64));
        let mut deliveries = Vec::new();
        for subscriber in &mut self.subscribers {
            if subscriber
                .last_sent
                .is_some_and(|sent| now.saturating_duration_since(sent) < BATCH_INTERVAL)
            {
                continue;
            }
            let mut next = subscriber.next.unwrap_or(backlog);
            if next < oldest {
                subscriber.dropped += oldest - next;
                next = oldest;
            }
            let changed = subscriber
                .sent_state
                .as_ref()
                .is_none_or(|sent| !sent.same(&self.state));
            let mut batch = LogBatch {
                records: Vec::new(),
                dropped: subscriber.dropped,
                state: self.state.clone(),
            };
            // The envelope without records, then each record and its comma.
            let mut bytes = json_len(&batch);
            let skip = usize::try_from(next - oldest).unwrap_or(usize::MAX);
            for stored in self.ring.iter().skip(skip) {
                let added = stored.bytes + usize::from(!batch.records.is_empty());
                // A first record always goes, so delivery cannot stall; the
                // tail keeps a file record well below the cap.
                if batch.records.len() == BATCH_RECORDS
                    || (!batch.records.is_empty() && bytes + added > BATCH_BYTES)
                {
                    break;
                }
                bytes += added;
                batch.records.push(stored.record.clone());
            }
            subscriber.next = Some(batch.records.last().map_or(next, |last| last.seq + 1));
            if batch.records.is_empty() && !changed && subscriber.dropped == 0 {
                continue;
            }
            subscriber.dropped = 0;
            subscriber.last_sent = Some(now);
            subscriber.sent_state = Some(self.state.clone());
            deliveries.push(Delivery {
                subscription: subscriber.id,
                sink: subscriber.sink.clone(),
                batch,
            });
        }
        deliveries
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    fn entry(message: &str) -> Prepared {
        Prepared::new(Entry {
            source: "python",
            timestamp: String::new(),
            timestamp_ms: None,
            level: None,
            logger: None,
            message: message.to_owned(),
            detail: None,
            process: None,
        })
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
            Arc::new(move |batch| {
                into.lock().unwrap().push(batch);
                true
            }),
            received,
        )
    }

    /// What the poller does after picking the batches.
    fn deliver(aggregate: &mut Aggregate, now: Instant) {
        let refused = send(aggregate.deliver(now));
        aggregate.end(&refused);
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
        deliver(&mut aggregate, Instant::now());
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
    fn a_subscription_before_any_record_takes_the_backlog_at_its_first_delivery() {
        let mut aggregate = Aggregate::new(available());
        let (sink, received) = collector();
        aggregate.subscribe(sink);
        for index in 0..BACKLOG + 7 {
            aggregate.push(entry(&index.to_string()));
        }
        deliver(&mut aggregate, Instant::now());
        let batches = received.lock().unwrap();
        assert_eq!(batches[0].records.len(), BACKLOG);
        assert_eq!(batches[0].records[0].message, "7");
        assert_eq!(batches[0].dropped, 0);
    }

    #[test]
    fn recorded_sizes_match_the_serialized_records() {
        let mut aggregate = Aggregate::new(available());
        for index in [0, 9, 10, 99_999] {
            aggregate.next_seq = index;
            aggregate.push(entry("tab\tquote\" control\u{1} accent \u{e1}"));
        }
        for stored in &aggregate.ring {
            assert_eq!(
                stored.bytes,
                serde_json::to_string(&stored.record).unwrap().len()
            );
        }
    }

    #[test]
    fn overflow_between_batches_is_counted_as_dropped() {
        let mut aggregate = Aggregate::new(available());
        let (sink, received) = collector();
        aggregate.subscribe(sink);
        let start = Instant::now();
        deliver(&mut aggregate, start);
        for index in 0..RING + 1_234 {
            aggregate.push(entry(&index.to_string()));
        }
        deliver(&mut aggregate, start + BATCH_INTERVAL);
        deliver(&mut aggregate, start + BATCH_INTERVAL * 2);
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
        deliver(&mut aggregate, start);
        aggregate.push(entry("a"));
        deliver(&mut aggregate, start + BATCH_INTERVAL / 2);
        assert_eq!(received.lock().unwrap().len(), 1);
        deliver(&mut aggregate, start + BATCH_INTERVAL);
        assert_eq!(received.lock().unwrap().len(), 2);
        deliver(&mut aggregate, start + BATCH_INTERVAL * 3);
        assert_eq!(received.lock().unwrap().len(), 2, "unchanged sends nothing");
        aggregate.state = LogSourceState {
            kind: SourceKind::Missing,
            ..available()
        };
        deliver(&mut aggregate, start + BATCH_INTERVAL * 4);
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
        aggregate.subscribe(Arc::new(|_| false));
        deliver(&mut aggregate, Instant::now());
        assert!(aggregate.subscribers.is_empty());
        let ids: Vec<u64> = (0..SUBSCRIBERS + 1)
            .map(|_| aggregate.subscribe(Arc::new(|_| true)))
            .collect();
        assert_eq!(aggregate.subscribers.len(), SUBSCRIBERS);
        assert!(!aggregate.unsubscribe(ids[0]));
        assert!(aggregate.unsubscribe(ids[SUBSCRIBERS]));
    }
}
