//! Desktop-host records: the host's diagnostics events, and nothing else.
//!
//! Only `Diagnostics` events are read. Captured process output, which can hold
//! terminal bytes, is never requested from the snapshot.
use super::{
    format::Level,
    record::{Entry, ProcessRef},
};
use cadrumo_application::diagnostics::{Diagnostics, Event, EventKind};

pub const SOURCE: &str = "host";
const LOGGER: &str = "desktop";

/// Tracks which diagnostics events were already turned into records.
///
/// The diagnostics ring keeps its newest events and has no sequence numbers,
/// so new events are the part of the current ring past its longest overlap
/// with the previous one. Identical events that also share a millisecond can
/// make that overlap longer than the real one once the ring is full.
#[derive(Default)]
pub struct HostEvents {
    previous: Vec<String>,
}

impl HostEvents {
    pub fn poll(&mut self, diagnostics: &Diagnostics) -> Vec<Entry> {
        // A cursor past every output chunk keeps captured output out.
        let events = diagnostics.snapshot(u64::MAX).events;
        let keys: Vec<String> = events
            .iter()
            .map(|event| serde_json::to_string(event).unwrap_or_default())
            .collect();
        let fresh = fresh(&self.previous, &keys);
        self.previous = keys;
        events[fresh..].iter().map(entry).collect()
    }
}

/// The index in `current` where events unseen in `previous` begin.
fn fresh(previous: &[String], current: &[String]) -> usize {
    (0..=previous.len().min(current.len()))
        .rev()
        .find(|overlap| previous[previous.len() - overlap..] == current[..*overlap])
        .unwrap_or(0)
}

fn token(kind: EventKind) -> String {
    serde_json::to_value(kind)
        .ok()
        .and_then(|value| value.as_str().map(str::to_owned))
        .unwrap_or_default()
}

fn entry(event: &Event) -> Entry {
    let mut message = token(event.kind);
    if let Some(status) = &event.status {
        message.push_str(&format!(
            ": {} pid {}",
            serde_json::to_value(status.role)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default(),
            status.pid
        ));
        if let Some(code) = status.exit_code {
            message.push_str(&format!(", exit code {code}"));
        }
    }
    if let Some(failure) = &event.failure {
        message.push_str(&format!(
            ": {} during {}: {}",
            serde_json::to_value(failure.code)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default(),
            serde_json::to_value(failure.operation)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_default(),
            failure.message
        ));
    }
    let level = match event.kind {
        EventKind::Failure => Level::Error,
        EventKind::ChildTerminated => Level::Warning,
        EventKind::ChildExited
            if event
                .status
                .as_ref()
                .is_some_and(|status| status.exit_code != Some(0)) =>
        {
            Level::Warning
        }
        _ => Level::Info,
    };
    Entry {
        source: SOURCE,
        timestamp: utc(event.timestamp_ms),
        timestamp_ms: Some(event.timestamp_ms),
        level: Some(level),
        logger: Some(LOGGER.to_owned()),
        message,
        detail: None,
        process: event.status.as_ref().map(|status| ProcessRef {
            role: status.role,
            pid: status.pid,
        }),
    }
}

/// RFC 3339 UTC text with milliseconds for epoch milliseconds.
fn utc(epoch_ms: u64) -> String {
    let days = epoch_ms / 86_400_000;
    let rest = epoch_ms % 86_400_000;
    // Civil date from days since 1970-01-01 (Howard Hinnant's algorithm).
    let z = days as i64 + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + i64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}.{:03}Z",
        rest / 3_600_000,
        rest / 60_000 % 60,
        rest / 1_000 % 60,
        rest % 1_000
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::{
        error::application::{ApplicationError, ErrorCode, Operation},
        process::status::{ProcessPhase, ProcessRole, Stream},
    };

    fn keys(values: &[&str]) -> Vec<String> {
        values.iter().map(|value| (*value).to_owned()).collect()
    }

    #[test]
    fn overlap_finds_appended_and_shifted_events() {
        assert_eq!(fresh(&[], &keys(&["a"])), 0);
        assert_eq!(fresh(&keys(&["a", "b"]), &keys(&["a", "b", "c"])), 2);
        assert_eq!(fresh(&keys(&["a", "b", "c"]), &keys(&["b", "c", "d"])), 2);
        assert_eq!(fresh(&keys(&["a", "b"]), &keys(&["a", "b"])), 2);
        assert_eq!(fresh(&keys(&["a", "a"]), &keys(&["a", "a", "a"])), 2);
        assert_eq!(fresh(&keys(&["a", "b"]), &keys(&["x", "y"])), 0);
    }

    #[test]
    fn utc_text_matches_known_instants() {
        assert_eq!(utc(0), "1970-01-01T00:00:00.000Z");
        assert_eq!(utc(951_782_400_000), "2000-02-29T00:00:00.000Z");
        assert_eq!(utc(1_791_117_001_042), "2026-10-04T12:30:01.042Z");
        assert_eq!(utc(4_107_542_399_999), "2100-02-28T23:59:59.999Z");
    }

    #[test]
    fn events_become_records_once_and_captured_output_never_does() {
        let diagnostics = Diagnostics::default();
        let mut host = HostEvents::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        let id = diagnostics.start(4242, ProcessRole::Tui);
        diagnostics.capture(id, Stream::Terminal, b"PTY-PAYLOAD-7f3a");
        diagnostics.capture(id, Stream::Stdout, b"STDOUT-PAYLOAD-7f3a");
        let first = host.poll(&diagnostics);
        assert_eq!(
            first.iter().map(|e| e.message.as_str()).collect::<Vec<_>>(),
            ["host_started", "child_started: tui pid 4242"]
        );
        assert!(host.poll(&diagnostics).is_empty());
        diagnostics.finish(id, Some(3), ProcessPhase::Exited);
        diagnostics.failure(ApplicationError::new(
            ErrorCode::SpawnFailed,
            Operation::Terminal,
        ));
        let second = host.poll(&diagnostics);
        assert_eq!(second.len(), 2);
        assert_eq!(second[0].message, "child_exited: tui pid 4242, exit code 3");
        assert_eq!(second[0].level, Some(Level::Warning));
        assert_eq!(
            second[0].process,
            Some(ProcessRef {
                role: ProcessRole::Tui,
                pid: 4242
            })
        );
        assert_eq!(
            second[1].message,
            "failure: spawn_failed during terminal: The child process could not be started"
        );
        assert_eq!(second[1].level, Some(Level::Error));
        for entry in first.iter().chain(&second) {
            assert_eq!(entry.source, SOURCE);
            assert!(entry.timestamp_ms.is_some() && entry.timestamp.ends_with('Z'));
            assert!(!format!("{entry:?}").contains("7f3a"));
        }
    }

    #[test]
    fn full_diagnostics_ring_yields_only_new_events() {
        let diagnostics = Diagnostics::default();
        let mut host = HostEvents::default();
        for pid in 0..600 {
            diagnostics.start(pid, ProcessRole::Cli);
        }
        assert_eq!(host.poll(&diagnostics).len(), 512);
        diagnostics.start(9_999, ProcessRole::Cli);
        let fresh = host.poll(&diagnostics);
        assert_eq!(fresh.len(), 1);
        assert_eq!(fresh[0].message, "child_started: cli pid 9999");
    }
}
