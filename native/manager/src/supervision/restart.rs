//! Restart backoff and the crash-loop ceiling on monotonic time.

use std::collections::VecDeque;
use std::time::{Duration, Instant};

/// Why the supervisor restarts a runtime.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RestartClass {
    /// A crash, an unexplained reason code or an exit the manager did not request.
    Unexpected,
    /// The interpreter refused to start, or the image could not be launched.
    LaunchFailure,
    /// No readiness within the ceiling, or a stale heartbeat.
    Hang,
    /// A stop the manager did not initiate: a signal stop, `0` or Ctrl+C before handlers.
    OutsideStop,
    /// The login witness was lost while the manager's own session stays active.
    WitnessLoss,
}

/// Exponential backoff with a ceiling on restarts inside a sliding window.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RestartPolicy {
    /// Delay before the first restart in a window.
    pub initial_backoff: Duration,
    /// Upper bound of any one delay.
    pub maximum_backoff: Duration,
    /// Restarts admitted inside one window; the next restart-worthy exit fails the core.
    pub crash_loop_limit: usize,
    /// Width of the sliding window, measured on monotonic time.
    pub crash_loop_window: Duration,
}

impl Default for RestartPolicy {
    fn default() -> Self {
        Self {
            initial_backoff: Duration::from_secs(1),
            maximum_backoff: Duration::from_secs(60),
            crash_loop_limit: 5,
            crash_loop_window: Duration::from_secs(600),
        }
    }
}

impl RestartPolicy {
    /// The delay before the restart that follows `prior` restarts in the window.
    pub fn backoff(&self, prior: usize) -> Duration {
        let doublings = u32::try_from(prior).unwrap_or(u32::MAX).min(31);
        self.initial_backoff
            .checked_mul(1 << doublings)
            .unwrap_or(self.maximum_backoff)
            .min(self.maximum_backoff)
    }
}

/// Restart instants inside the current window.
#[derive(Debug, Default)]
pub struct RestartHistory {
    recent: VecDeque<Instant>,
}

impl RestartHistory {
    /// Admit one restart at `now` and return its delay, or `None` at the crash-loop ceiling.
    pub fn admit(&mut self, policy: &RestartPolicy, now: Instant) -> Option<Duration> {
        while let Some(&oldest) = self.recent.front() {
            if now.saturating_duration_since(oldest) < policy.crash_loop_window {
                break;
            }
            self.recent.pop_front();
        }
        if self.recent.len() >= policy.crash_loop_limit {
            return None;
        }
        let delay = policy.backoff(self.recent.len());
        self.recent.push_back(now);
        Some(delay)
    }

    /// Forget every earlier restart, after an explicit retry.
    pub fn clear(&mut self) {
        self.recent.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy() -> RestartPolicy {
        RestartPolicy {
            initial_backoff: Duration::from_millis(100),
            maximum_backoff: Duration::from_millis(500),
            crash_loop_limit: 4,
            crash_loop_window: Duration::from_secs(10),
        }
    }

    #[test]
    fn backoff_doubles_up_to_its_maximum() {
        let delays: Vec<_> = (0..6).map(|prior| policy().backoff(prior)).collect();
        assert_eq!(
            delays,
            [100, 200, 400, 500, 500, 500].map(Duration::from_millis)
        );
        assert_eq!(policy().backoff(usize::MAX), Duration::from_millis(500));
    }

    #[test]
    fn the_ceiling_fails_the_restart_after_the_limit_inside_the_window() {
        let start = Instant::now();
        let mut history = RestartHistory::default();
        let delays: Vec<_> = (0..4)
            .map(|step| history.admit(&policy(), start + Duration::from_secs(step)))
            .collect();
        assert_eq!(
            delays,
            [100, 200, 400, 500].map(|ms| Some(Duration::from_millis(ms)))
        );
        assert_eq!(
            history.admit(&policy(), start + Duration::from_secs(4)),
            None
        );
    }

    #[test]
    fn restarts_older_than_the_window_stop_counting() {
        let start = Instant::now();
        let mut history = RestartHistory::default();
        for step in 0..4 {
            history.admit(&policy(), start + Duration::from_secs(step));
        }
        // At 10 s the restart at 0 s has left the window; three remain.
        assert_eq!(
            history.admit(&policy(), start + Duration::from_secs(10)),
            Some(Duration::from_millis(500))
        );
        assert_eq!(
            history.admit(&policy(), start + Duration::from_secs(30)),
            Some(Duration::from_millis(100))
        );
        history.clear();
        assert_eq!(
            history.admit(&policy(), start + Duration::from_secs(31)),
            Some(Duration::from_millis(100))
        );
    }
}
