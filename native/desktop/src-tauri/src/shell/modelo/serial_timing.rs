//! When each Modelo exchange asked for the profile's serial lock, got it and
//! let it go, so a slow window read can be split into its wait for the lock
//! and the time it held it.
//!
//! One line per exchange goes to the host's standard error in debug builds:
//! the exchange's site, its admitted definition, the runtime operation id once
//! known, and three epoch-millisecond times. Nothing from the request or the
//! profile is written. The native logger renders no log arguments, so these
//! lines cannot go through it.
use super::super::user_profile::ProfileHost;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::MutexGuard;

fn epoch_ms() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_millis())
        .unwrap_or(0)
}

/// The serial lock, held with when it was asked for and obtained.
pub(super) struct TimedSerial<'a> {
    site: &'static str,
    definition: &'static str,
    requested_ms: u128,
    acquired_ms: u128,
    operation: Option<String>,
    _serial: MutexGuard<'a, ()>,
}

impl TimedSerial<'_> {
    /// Names the runtime operation this exchange submitted or followed.
    pub(super) fn operation(&mut self, operation: &str) {
        self.operation = Some(operation.to_owned());
    }

    fn line(&self, released_ms: u128) -> String {
        // An operation id is the runtime's opaque hex digest; anything else is
        // not written.
        let operation = self
            .operation
            .as_deref()
            .filter(|id| !id.is_empty() && id.len() <= 128)
            .filter(|id| id.bytes().all(|byte| byte.is_ascii_hexdigit()))
            .unwrap_or("-");
        format!(
            "cadrumo-host modelo serial site={} definition={} operation={} requested_ms={} acquired_ms={} released_ms={}",
            self.site, self.definition, operation, self.requested_ms, self.acquired_ms, released_ms
        )
    }
}

impl Drop for TimedSerial<'_> {
    fn drop(&mut self) {
        if cfg!(debug_assertions) {
            eprintln!("{}", self.line(epoch_ms()));
        }
    }
}

/// Waits for the profile's serial lock as `site` for `definition`.
pub(super) async fn serial<'a>(
    profile: &'a ProfileHost,
    site: &'static str,
    definition: &'static str,
) -> TimedSerial<'a> {
    let requested_ms = epoch_ms();
    let guard = profile.serial().await;
    TimedSerial {
        site,
        definition,
        requested_ms,
        acquired_ms: epoch_ms(),
        operation: None,
        _serial: guard,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::Mutex;

    fn timed<'a>(guard: MutexGuard<'a, ()>, operation: Option<&str>) -> TimedSerial<'a> {
        TimedSerial {
            site: "read",
            definition: "modelo.work.form",
            requested_ms: 1000,
            acquired_ms: 1250,
            operation: operation.map(str::to_owned),
            _serial: guard,
        }
    }

    #[tokio::test]
    async fn a_line_names_the_site_definition_operation_and_three_times() {
        let lock = Mutex::new(());
        let id = "38f9e1ac83371da8a82511853c55d95664f3d6fd57f240ac9ab4c4702f6a7ddb";
        let held = timed(lock.lock().await, Some(id));
        assert_eq!(
            held.line(1900),
            format!(
                "cadrumo-host modelo serial site=read definition=modelo.work.form operation={id} requested_ms=1000 acquired_ms=1250 released_ms=1900"
            )
        );
    }

    #[tokio::test]
    async fn an_operation_that_is_not_a_hex_id_is_not_written() {
        let lock = Mutex::new(());
        for unsafe_id in ["", "12 34", "profile=abc", "ab\ncd", &"a".repeat(129)] {
            let held = timed(lock.lock().await, Some(unsafe_id));
            assert!(held.line(2000).contains(" operation=- "), "{unsafe_id:?}");
        }
        let held = timed(lock.lock().await, None);
        assert!(held.line(2000).contains(" operation=- "));
    }

    #[tokio::test]
    async fn the_lock_is_held_until_the_timing_is_dropped() {
        let lock = Mutex::new(());
        let held = timed(lock.lock().await, None);
        assert!(lock.try_lock().is_err());
        drop(held);
        assert!(lock.try_lock().is_ok());
    }

    #[test]
    fn times_are_epoch_milliseconds() {
        let now = epoch_ms();
        // Thirteen digits: milliseconds, not seconds or microseconds.
        assert!((1_000_000_000_000..10_000_000_000_000).contains(&now));
    }
}
