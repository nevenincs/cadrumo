//! A durable, payload-free record of a close that ended changes the window had submitted
//! before they reported, so the next window can say that their outcome is unknown.
//!
//! The runtime's operation journal is the authority on what happened to each change: it
//! records the work a stop cut short as interrupted, with an unknown effect where the
//! work had begun. This record only remembers that the person was not told. It names
//! each change by its closed command identity and never carries operands, paths,
//! arguments or messages. A close that settled everything writes nothing; the next
//! window reports a pending record once and marks it reported.

use crate::app::Commands;
use cadrumo_application::{
    diagnostics::logging::LogFile,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    process::status::timestamp_ms,
};
use serde::{Deserialize, Serialize};
use std::{
    io::Read,
    path::{Path, PathBuf},
    sync::Arc,
};
use tauri::State;

/// The file of records, beside the regular logs.
pub const FILE_NAME: &str = "cadrumo-close-outcomes.jsonl";

/// The command identity of a change relayed over the window's own person session.
pub const PROFILE_RELAY: &str = "profile_relay";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Outcome {
    /// The close ended changes before they reported.
    ChangesInterrupted,
    /// A later window told the person about the last such close.
    Reported,
}

#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Record {
    schema: u32,
    event: String,
    outcome: Outcome,
    #[serde(default)]
    changes: Vec<String>,
    pid: u32,
    timestamp_ms: u64,
}

impl Record {
    fn new(outcome: Outcome, changes: Vec<String>) -> Self {
        Self {
            schema: 1,
            event: "close_outcome".into(),
            outcome,
            changes,
            pid: std::process::id(),
            timestamp_ms: timestamp_ms(),
        }
    }
}

/// Where close outcomes are kept for one storage root's log directory.
#[derive(Clone)]
pub struct CloseOutcomes {
    file: LogFile,
}

impl CloseOutcomes {
    pub fn new(log_directory: &Path, max_bytes: u64, backups: u32) -> Result<Self> {
        Ok(Self {
            file: LogFile::for_file(&log_directory.join(FILE_NAME), max_bytes, backups)?,
        })
    }

    fn path(&self) -> &PathBuf {
        &self.file.paths.current
    }

    /// Records that this close ended `changes` before they reported. Nothing is written
    /// when there were none.
    pub fn interrupted(&self, changes: &[&'static str]) -> Result<()> {
        if changes.is_empty() {
            return Ok(());
        }
        let changes = changes.iter().map(|change| (*change).to_owned()).collect();
        self.file
            .append(&Record::new(Outcome::ChangesInterrupted, changes))
    }

    /// How many changes the last close ended unreported, marking them reported so a
    /// later window does not say so again. Zero when the last close settled everything
    /// or its report was already given.
    pub fn take_unreported(&self) -> Result<usize> {
        let Some(last) = self.last()? else {
            return Ok(0);
        };
        if last.outcome != Outcome::ChangesInterrupted {
            return Ok(0);
        }
        self.file
            .append(&Record::new(Outcome::Reported, Vec::new()))?;
        Ok(last.changes.len())
    }

    /// The newest readable record; an unreadable line is skipped rather than guessed at.
    fn last(&self) -> Result<Option<Record>> {
        let file = match std::fs::File::open(self.path()) {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(unavailable().caused_by(error)),
        };
        // Rotation keeps the current file below its bound; never read past it.
        let mut text = String::new();
        file.take(LIMIT)
            .read_to_string(&mut text)
            .map_err(|error| unavailable().caused_by(error))?;
        Ok(text
            .lines()
            .rev()
            .find_map(|line| serde_json::from_str::<Record>(line).ok()))
    }
}

/// How many changes the previous close of this root's window ended before they reported,
/// once: the window says their outcome is unknown. A window without a log directory has
/// nothing to report.
#[tauri::command]
async fn previous_close(outcomes: State<'_, Option<Arc<CloseOutcomes>>>) -> Result<usize> {
    let Some(outcomes) = outcomes.inner().clone() else {
        return Ok(0);
    };
    tauri::async_runtime::spawn_blocking(move || outcomes.take_unreported())
        .await
        .map_err(|error| {
            ApplicationError::new(ErrorCode::Panic, Operation::Webview).caused_by(error)
        })?
}

pub fn commands<R: tauri::Runtime>() -> Commands<R> {
    crate::app::commands![previous_close]
}

/// The most this reader takes from the current file.
const LIMIT: u64 = 1024 * 1024;

fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::LogUnavailable, Operation::Logging)
}

/// The close outcomes of `launch`'s storage root, or `None` when its log directory or
/// bounds cannot be resolved: such a window keeps no record and reports none.
pub fn of(launch: &crate::environment::Launch) -> Option<Arc<CloseOutcomes>> {
    let directory = launch.log_file.parent()?;
    let (max_bytes, backups) = crate::startup_logging::Contract::current()
        .ok()?
        .log_bounds();
    CloseOutcomes::new(directory, max_bytes, backups)
        .ok()
        .map(Arc::new)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);

    impl Scratch {
        fn new() -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::fs::canonicalize(std::env::temp_dir())
                .unwrap()
                .join(format!(
                    "cadrumo-close-outcome-{}-{nanos}",
                    std::process::id()
                ));
            std::fs::create_dir_all(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn an_interrupted_close_is_reported_once_by_the_next_window() {
        let scratch = Scratch::new();
        let outcomes = CloseOutcomes::new(&scratch.0, 64 * 1024, 1).unwrap();
        assert_eq!(outcomes.take_unreported().unwrap(), 0);
        outcomes
            .interrupted(&["config.profile.create", PROFILE_RELAY])
            .unwrap();
        // A second window on the same root reads the same file.
        let next = CloseOutcomes::new(&scratch.0, 64 * 1024, 1).unwrap();
        assert_eq!(next.take_unreported().unwrap(), 2);
        assert_eq!(next.take_unreported().unwrap(), 0);
        let text = std::fs::read_to_string(scratch.0.join(FILE_NAME)).unwrap();
        assert!(text.contains("\"changes\":[\"config.profile.create\",\"profile_relay\"]"));
        assert!(
            text.lines()
                .last()
                .unwrap()
                .contains("\"outcome\":\"reported\"")
        );
    }

    #[test]
    fn a_close_that_settled_everything_writes_nothing_and_leaves_an_earlier_report_given() {
        let scratch = Scratch::new();
        let outcomes = CloseOutcomes::new(&scratch.0, 64 * 1024, 1).unwrap();
        outcomes.interrupted(&[]).unwrap();
        assert!(!scratch.0.join(FILE_NAME).exists());
        outcomes.interrupted(&["config.profile.create"]).unwrap();
        assert_eq!(outcomes.take_unreported().unwrap(), 1);
        outcomes.interrupted(&[]).unwrap();
        assert_eq!(outcomes.take_unreported().unwrap(), 0);
    }

    #[test]
    fn an_unreadable_line_is_skipped_for_the_record_before_it() {
        let scratch = Scratch::new();
        let outcomes = CloseOutcomes::new(&scratch.0, 64 * 1024, 1).unwrap();
        outcomes.interrupted(&["config.profile.create"]).unwrap();
        let path = scratch.0.join(FILE_NAME);
        let mut text = std::fs::read_to_string(&path).unwrap();
        text.push_str("{not a record\n");
        std::fs::write(&path, text).unwrap();
        assert_eq!(outcomes.take_unreported().unwrap(), 1);
    }
}
