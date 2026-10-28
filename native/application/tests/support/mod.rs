//! Waiting for the diagnostic writer without expecting any particular speed of it.
//!
//! One source, included by the library's unit tests and by each integration test that reads
//! what the writer delivered; the includer imports `Diagnostics`.

use super::Diagnostics;
use std::time::{Duration, Instant};

/// How long one wait for the writer's answer lasts before its progress is looked at.
const SLICE: Duration = Duration::from_secs(1);
/// How long the writer may complete nothing and enter no stage before it is taken to be hung.
/// Opening a log file has been seen to stall for over 30 s while the machine was saturated, so
/// this is far beyond any stall that ends.
const STALL: Duration = Duration::from_secs(180);

/// Returns once the writer has delivered everything recorded before the call.
///
/// A writer on a busy machine is slow, not wrong, so this waits for as long as it keeps
/// working. It fails only when the writer has completed nothing and entered no stage for
/// `STALL`, and then names the stage it is held in and where its last batch spent its time.
pub fn delivered(diagnostics: &Diagnostics) {
    let mut seen = diagnostics.log_delivery_status();
    let mut moved = Instant::now();
    while !diagnostics.flush_logs(SLICE) {
        let now = diagnostics.log_delivery_status();
        if now.completed != seen.completed
            || now.stage != seen.stage
            || now.stage_micros < seen.stage_micros
        {
            moved = Instant::now();
        }
        assert!(
            moved.elapsed() < STALL,
            "log writer made no progress for {STALL:?}: {now:?}"
        );
        seen = now;
    }
}
