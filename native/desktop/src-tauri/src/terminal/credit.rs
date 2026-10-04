//! Credit backpressure between the PTY reader and the frontend.
//!
//! The reader counts every delivered output byte; the frontend acknowledges a
//! cumulative offset. Once [`PAUSE`] bytes are unacknowledged the reader stops
//! reading the PTY, so the child blocks on its own write and no byte is dropped.
//! It resumes when fewer than [`RESUME`] bytes remain unacknowledged. A stop
//! request releases a paused reader at once.
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Operation, Result};
use std::{
    sync::{Condvar, Mutex, MutexGuard},
    time::Duration,
};

pub const PAUSE: u64 = 512 * 1024;
pub const RESUME: u64 = 128 * 1024;
/// The longest a paused reader sleeps before rechecking, independent of wakeups.
const RECHECK: Duration = Duration::from_millis(50);

#[derive(Default)]
struct Window {
    sent: u64,
    acked: u64,
    paused: bool,
    stopped: bool,
}

#[derive(Default)]
pub struct Credit {
    window: Mutex<Window>,
    changed: Condvar,
}

/// What the reader does with the bytes it just read.
#[derive(Debug, Eq, PartialEq)]
pub enum Admission {
    Deliver,
    Discard,
}

impl Credit {
    fn lock(&self) -> MutexGuard<'_, Window> {
        // The window holds plain counters that stay consistent on every exit
        // path, so a panic elsewhere cannot leave it half-updated.
        self.window.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Counts `count` bytes about to be delivered, or reports that the session
    /// is stopping and they are discarded.
    pub fn admit(&self, count: usize) -> Admission {
        let mut window = self.lock();
        if window.stopped {
            return Admission::Discard;
        }
        window.sent = window.sent.saturating_add(count as u64);
        if window.sent - window.acked >= PAUSE {
            window.paused = true;
        }
        Admission::Deliver
    }

    /// Records a cumulative acknowledgement. A stale offset changes nothing;
    /// an offset beyond the delivered bytes is refused.
    pub fn acknowledge(&self, offset: u64) -> Result<()> {
        let mut window = self.lock();
        if offset > window.sent {
            return Err(ApplicationError::new(
                ErrorCode::InvalidArguments,
                Operation::Terminal,
            ));
        }
        window.acked = window.acked.max(offset);
        if window.paused && window.sent - window.acked < RESUME {
            window.paused = false;
            self.changed.notify_all();
        }
        Ok(())
    }

    /// Blocks while the reader is paused. Returns once credit is available or
    /// the session is stopping.
    pub fn wait(&self) {
        let mut window = self.lock();
        while window.paused && !window.stopped {
            window = self
                .changed
                .wait_timeout(window, RECHECK)
                .map(|(window, _)| window)
                .unwrap_or_else(|e| e.into_inner().0);
        }
    }

    /// Releases a paused reader; every later read is discarded.
    pub fn stop(&self) {
        self.lock().stopped = true;
        self.changed.notify_all();
    }

    pub fn stopped(&self) -> bool {
        self.lock().stopped
    }

    #[cfg(all(test, feature = "live-package-tests"))]
    pub fn sent(&self) -> u64 {
        self.lock().sent
    }

    #[cfg(test)]
    pub fn paused(&self) -> bool {
        self.lock().paused
    }

    #[cfg(test)]
    pub fn unacknowledged(&self) -> u64 {
        let window = self.lock();
        window.sent - window.acked
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        sync::{Arc, mpsc},
        thread,
        time::Instant,
    };

    const CHUNK: usize = 8192;

    #[test]
    fn reader_pauses_at_the_window_and_resumes_below_the_low_mark() {
        let credit = Credit::default();
        let mut sent = 0u64;
        while !credit.paused() {
            assert_eq!(credit.admit(CHUNK), Admission::Deliver);
            sent += CHUNK as u64;
        }
        assert_eq!(sent, PAUSE);
        // Acks that leave RESUME or more outstanding keep the reader paused.
        credit.acknowledge(sent - RESUME).unwrap();
        assert!(credit.paused());
        credit.acknowledge(sent - RESUME + 1).unwrap();
        assert!(!credit.paused());
        assert_eq!(credit.unacknowledged(), RESUME - 1);
    }

    #[test]
    fn acknowledgements_are_cumulative_and_bounded_by_delivery() {
        let credit = Credit::default();
        credit.admit(100);
        credit.acknowledge(60).unwrap();
        // A late, smaller cumulative offset is stale, not a regression.
        credit.acknowledge(10).unwrap();
        assert_eq!(credit.unacknowledged(), 40);
        let refused = credit.acknowledge(101).unwrap_err();
        assert_eq!(refused.code, ErrorCode::InvalidArguments);
        credit.acknowledge(100).unwrap();
        assert_eq!(credit.unacknowledged(), 0);
    }

    #[test]
    fn every_admitted_byte_is_accounted_without_loss() {
        let credit = Arc::new(Credit::default());
        let (frames, received) = mpsc::channel::<usize>();
        let producer = credit.clone();
        let total = 10 * 1024 * 1024;
        let reader = thread::spawn(move || {
            let mut remaining = total;
            while remaining > 0 {
                producer.wait();
                let count = remaining.min(CHUNK);
                assert_eq!(producer.admit(count), Admission::Deliver);
                frames.send(count).unwrap();
                remaining -= count;
            }
        });
        let mut acked = 0u64;
        let mut peak = 0u64;
        for count in received {
            peak = peak.max(credit.unacknowledged());
            acked += count as u64;
            credit.acknowledge(acked).unwrap();
        }
        reader.join().unwrap();
        assert_eq!(acked, total as u64);
        assert!(peak < PAUSE + CHUNK as u64, "window overran: {peak}");
    }

    #[test]
    fn stop_wakes_a_paused_reader_and_discards_later_reads() {
        let credit = Arc::new(Credit::default());
        credit.admit(PAUSE as usize);
        assert!(credit.paused());
        let waiter = credit.clone();
        let (woke, wake) = mpsc::channel();
        let reader = thread::spawn(move || {
            waiter.wait();
            woke.send(Instant::now()).unwrap();
        });
        thread::sleep(Duration::from_millis(100));
        assert!(
            wake.try_recv().is_err(),
            "a paused reader ran without credit"
        );
        let stopped = Instant::now();
        credit.stop();
        let woken = wake.recv_timeout(Duration::from_secs(3)).unwrap();
        assert!(woken.duration_since(stopped) < Duration::from_secs(1));
        reader.join().unwrap();
        assert_eq!(credit.admit(10), Admission::Discard);
        assert!(credit.stopped());
    }
}
