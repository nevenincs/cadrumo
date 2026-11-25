//! The time bounds of an orderly shutdown, shared by the component that waits and the
//! components that spend the time.
//!
//! One owner keeps a second launch's patience derived from the budgets it waits out
//! instead of a separate number that drifts from them.

use crate::error::application::{ApplicationError, ErrorCode};
use std::time::Duration;

/// The reason a closing host gives its own refusals and the clients it ended. A refusal
/// with it is an expected shutdown outcome, never a failure of the work it refused.
pub const HOST_CLOSING: &str = "host_closing";

/// Whether `error` is a closing host's own refusal.
pub fn is_host_closing(error: &ApplicationError) -> bool {
    error.code == ErrorCode::SessionUnavailable && error.reason.as_deref() == Some(HOST_CLOSING)
}

/// How long a stopping runtime may take: its drain plus its own watchdog, with margin.
pub const RUNTIME_DRAIN_BOUND: Duration = Duration::from_secs(25);

/// How long the desktop waits for its supervisor to settle after a close request.
pub const SUPERVISOR_CLOSE_BOUND: Duration = Duration::from_secs(35);

/// How long a closing desktop lets a change it already submitted reach its terminal
/// receipt before it ends that client and drains the runtime. It is the runtime's own
/// drain bound, so a quit never gives admitted work less time than a runtime stop does;
/// what is still running afterwards is the runtime's to settle and record.
pub const OPERATION_SETTLE_BOUND: Duration = RUNTIME_DRAIN_BOUND;

/// The longest a closing window can still hold the per-user instance lock: the settle
/// window for submitted changes, then the supervisor's close bound followed by a runtime
/// drain that began just after it. A relaunch during shutdown waits this long for the
/// lock instead of giving up first.
pub const RELAUNCH_PATIENCE: Duration = OPERATION_SETTLE_BOUND
    .saturating_add(SUPERVISOR_CLOSE_BOUND)
    .saturating_add(RUNTIME_DRAIN_BOUND);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_relaunch_outwaits_the_settle_window_the_close_and_the_drain_it_follows() {
        assert!(RELAUNCH_PATIENCE > OPERATION_SETTLE_BOUND + SUPERVISOR_CLOSE_BOUND);
        assert!(RELAUNCH_PATIENCE > RUNTIME_DRAIN_BOUND);
        assert_eq!(RELAUNCH_PATIENCE, Duration::from_secs(85));
    }

    #[test]
    fn only_a_closing_hosts_own_refusal_is_an_expected_shutdown_outcome() {
        use crate::error::application::Operation;
        let closing = ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli)
            .with_reason(HOST_CLOSING);
        assert!(is_host_closing(&closing));
        // The same code for another reason, or without one, is still a failure.
        let unavailable = ApplicationError::new(ErrorCode::SessionUnavailable, Operation::Cli);
        assert!(!is_host_closing(&unavailable));
        assert!(!is_host_closing(
            &unavailable.clone().with_reason("person_resume_refused")
        ));
        let other =
            ApplicationError::new(ErrorCode::TimedOut, Operation::Cli).with_reason(HOST_CLOSING);
        assert!(!is_host_closing(&other));
    }
}
