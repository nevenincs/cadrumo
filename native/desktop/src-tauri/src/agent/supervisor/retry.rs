use super::protocol::State;
use super::{Shared, lock};
use cadrumo_application::diagnostics::service::AgentRefusal as Refusal;
use cadrumo_application::diagnostics::service::ServiceFact;
use std::time::{Duration, Instant};

/// Initial retry delay; later failures back off, up to three retries.
pub(super) const RETRY: Duration = Duration::from_secs(30);

/// A failed service gets three automatic retries. The last refusal remains
/// visible until an explicit retry, sign-in/profile change or host reopen.
#[derive(Default)]
pub(super) struct RetryBudget {
    pub(super) failures: u32,
    pub(super) after: Option<Instant>,
    pub(super) refusal: Option<Refusal>,
    pub(super) stopped: bool,
}

impl RetryBudget {
    pub(super) fn waiting(&self) -> bool {
        self.stopped || self.failures >= 4 || self.after.is_some_and(|at| Instant::now() < at)
    }

    pub(super) fn timeout(&mut self) {
        self.stopped = true;
        self.after = None;
        self.refusal = Some(Refusal::Timeout);
    }

    pub(super) fn failed(&mut self, shared: &Shared) {
        if let State::Refused { code } = lock(&shared.status).state {
            self.refusal = Some(code);
        }
        self.failures = self.failures.saturating_add(1);
        if self.failures >= 4 {
            self.after = None;
            shared.diagnostics.service(
                None,
                ServiceFact::AgentRetryExhausted {
                    attempts: self.failures,
                },
            );
        } else {
            let delay = shared.retry.saturating_mul(1 << (self.failures - 1));
            self.after = Some(Instant::now() + delay);
            shared.diagnostics.service(
                None,
                ServiceFact::AgentRetryScheduled {
                    delay_ms: delay.as_millis().try_into().unwrap_or(u64::MAX),
                },
            );
        }
    }
}
