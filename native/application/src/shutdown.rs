//! The time bounds of an orderly shutdown, shared by the component that waits and the
//! components that spend the time.
//!
//! One owner keeps a second launch's patience derived from the budgets it waits out
//! instead of a separate number that drifts from them.

use std::time::Duration;

/// How long a stopping runtime may take: its drain plus its own watchdog, with margin.
pub const RUNTIME_DRAIN_BOUND: Duration = Duration::from_secs(25);

/// How long the desktop waits for its supervisor to settle after a close request.
pub const SUPERVISOR_CLOSE_BOUND: Duration = Duration::from_secs(35);

/// The longest a closing window can still hold the per-user instance lock: the
/// supervisor's close bound followed by a runtime drain that began just after it. A
/// relaunch during shutdown waits this long for the lock instead of giving up first.
pub const RELAUNCH_PATIENCE: Duration = SUPERVISOR_CLOSE_BOUND.saturating_add(RUNTIME_DRAIN_BOUND);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_relaunch_outwaits_the_close_and_the_drain_it_follows() {
        assert!(RELAUNCH_PATIENCE > SUPERVISOR_CLOSE_BOUND);
        assert!(RELAUNCH_PATIENCE > RUNTIME_DRAIN_BOUND);
        assert_eq!(RELAUNCH_PATIENCE, Duration::from_secs(60));
    }
}
