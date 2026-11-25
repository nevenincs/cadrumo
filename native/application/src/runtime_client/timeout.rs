use std::time::{Duration, Instant};

/// One absolute last-resort timeout for a signal-driven course of work.
#[derive(Clone, Copy, Debug)]
pub struct TimeoutWait {
    pub(super) deadline: Instant,
}

impl TimeoutWait {
    pub fn new() -> Self {
        Self::with_timeout(Duration::from_secs(
            cadrumo_platform::DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS,
        ))
    }

    pub fn with_timeout(deadline: Duration) -> Self {
        Self {
            deadline: Instant::now() + deadline,
        }
    }

    pub fn deadline(self) -> Instant {
        self.deadline
    }
}

impl Default for TimeoutWait {
    fn default() -> Self {
        Self::new()
    }
}
