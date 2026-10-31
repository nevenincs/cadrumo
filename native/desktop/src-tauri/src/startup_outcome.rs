//! A durable, payload-free record of a launch that ends before the regular startup log
//! exists: handed off to an open window, open in another session, timed out waiting for the
//! instance lock, or refused before the host could log.
//!
//! The record names a closed outcome, the typed reason code, the stage, the process id, the
//! time and the digest identity of the storage root. It never carries paths, arguments,
//! environment values or error messages. It lands in the declared log directory of the root the
//! launch selects, or of the per-user installed default when the selected root cannot be
//! resolved; a launch with neither stays on its standard error.

use crate::{
    environment::Parent,
    shell::single_instance::Admission,
    startup_logging::{Contract, environment_value},
};
use cadrumo_application::{
    diagnostics::{HostStage, logging::LogFile},
    error::application::{ApplicationError, ErrorCode, Result},
    process::status::timestamp_ms,
};
use cadrumo_platform::storage::{create_storage_root, resolve_storage_root_with};
use serde::Serialize;
use std::{path::PathBuf, time::Duration};

/// The file of records, beside the regular logs.
pub const FILE_NAME: &str = "cadrumo-startup-outcomes.jsonl";

/// How a launch ended before it had a log of its own.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    /// An open window of this root accepted activation and this launch exited.
    HandedOff,
    /// The window of this root is open in another session of the account.
    OpenInOtherSession,
    /// The instance lock was not released within the relaunch patience.
    TimedOut,
    /// The launch was refused before the host could log.
    Refused,
}

impl Outcome {
    /// The outcome a failed launch step reports.
    pub fn of_failure(error: &ApplicationError) -> Self {
        if error.code == ErrorCode::TimedOut {
            Self::TimedOut
        } else {
            Self::Refused
        }
    }
}

/// Which root the record was written under.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RootSelection {
    /// The root the launch's environment selects.
    Selected,
    /// The per-user installed default, because the selected root could not be resolved.
    InstalledDefault,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct Record {
    schema: u32,
    event: &'static str,
    outcome: Outcome,
    reason: Option<ErrorCode>,
    stage: HostStage,
    pid: u32,
    timestamp_ms: u64,
    root_identity: Option<String>,
    root: RootSelection,
}

/// The outcome an admission ends the launch with, or `None` when the launch goes on.
pub fn of_admission(admission: &Result<Admission>) -> Option<(Outcome, Option<ErrorCode>)> {
    match admission {
        Ok(Admission::Activated) => Some((Outcome::HandedOff, None)),
        Ok(Admission::OpenInOtherSession) => Some((Outcome::OpenInOtherSession, None)),
        Ok(Admission::Primary(_) | Admission::Headless) => None,
        Err(error) => Some((Outcome::of_failure(error), Some(error.code))),
    }
}

/// Records the outcome of this launch, once, and returns the file written.
pub fn record(
    parent: &Parent,
    outcome: Outcome,
    stage: HostStage,
    reason: Option<ErrorCode>,
) -> Result<PathBuf> {
    let contract = Contract::current()?;
    let (root, selection) = resolve(parent)?;
    let directory = contract.log_directory(&root)?;
    let record = Record {
        schema: 1,
        event: "startup_outcome",
        outcome,
        reason,
        stage,
        pid: std::process::id(),
        timestamp_ms: timestamp_ms(),
        root_identity: cadrumo_application::instance_scope::storage_scope(&root).ok(),
        root: selection,
    };
    let (max_bytes, backups) = contract.log_bounds();
    let file = LogFile::for_file(&directory.join(FILE_NAME), max_bytes, backups)?;
    append(&file, &record)?;
    Ok(file.paths.current)
}

/// The root to record under, created owner-only when absent.
fn resolve(parent: &Parent) -> Result<(PathBuf, RootSelection)> {
    let unavailable = |error: std::io::Error| {
        ApplicationError::new(
            ErrorCode::LogUnavailable,
            cadrumo_application::error::application::Operation::Logging,
        )
        .caused_by(error)
    };
    let (resolved, selection) =
        match resolve_storage_root_with(&|name| environment_value(parent, name)) {
            Ok(resolved) => (resolved, RootSelection::Selected),
            Err(_) => {
                let without_override = |name: &str| {
                    (name != cadrumo_platform::ROOT_VARIABLE)
                        .then(|| environment_value(parent, name))
                        .flatten()
                };
                let resolved = resolve_storage_root_with(&without_override)
                    .map_err(|error| unavailable(std::io::Error::from(error)))?;
                (resolved, RootSelection::InstalledDefault)
            }
        };
    create_storage_root(&resolved.root).map_err(unavailable)?;
    Ok((resolved.root, selection))
}

/// Concurrent launches contend for the file's lock; a short bounded wait settles them.
fn append(file: &LogFile, record: &Record) -> Result<()> {
    const ATTEMPTS: u32 = 40;
    const PAUSE: Duration = Duration::from_millis(25);
    let mut last = None;
    for _ in 0..ATTEMPTS {
        match file.append(record) {
            Ok(()) => return Ok(()),
            Err(error) => last = Some(error),
        }
        std::thread::sleep(PAUSE);
    }
    Err(last.expect("at least one attempt ran"))
}

/// The closed, payload-free text the person is shown for `outcome`.
pub fn notice(outcome: Outcome, reason: Option<ErrorCode>) -> Option<(&'static str, String)> {
    match outcome {
        Outcome::HandedOff => None,
        Outcome::OpenInOtherSession => Some((
            "Cadrumo is open in another session",
            "Cadrumo is already open in another login session of this account. Switch to that session."
                .into(),
        )),
        Outcome::TimedOut => Some((
            "Cadrumo is still closing",
            "The previous Cadrumo window did not finish closing in time. Wait a moment and open Cadrumo again."
                .into(),
        )),
        Outcome::Refused => Some((
            "Cadrumo could not start",
            format!(
                "Reason: {}. The startup record in the Cadrumo logs folder has the details.",
                reason.map_or_else(|| "unknown".to_owned(), token)
            ),
        )),
    }
}

/// The protocol token of `code`.
fn token(code: ErrorCode) -> String {
    serde_json::to_value(code)
        .ok()
        .and_then(|value| value.as_str().map(str::to_owned))
        .unwrap_or_else(|| "unknown".to_owned())
}

/// Shows `notice` to the person where the platform can display one before any window exists
/// and the launch has no terminal of its own. Returns whether a notice was shown.
pub fn present(title: &str, message: &str) -> bool {
    #[cfg(target_os = "macos")]
    {
        use std::io::IsTerminal;
        if std::io::stderr().is_terminal() {
            return false;
        }
        // The text travels as script arguments, never inside the script.
        std::process::Command::new("/usr/bin/osascript")
            .args([
                "-e",
                "on run argv",
                "-e",
                "display alert (item 1 of argv) message (item 2 of argv) giving up after 120",
                "-e",
                "end run",
                title,
                message,
            ])
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .is_ok_and(|status| status.success())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = (title, message);
        false
    }
}

/// Records `outcome`, then shows the person its notice. Best effort: a launch that cannot
/// record keeps its standard error report.
pub fn conclude(
    parent: &Parent,
    outcome: Outcome,
    stage: HostStage,
    reason: Option<ErrorCode>,
) -> Option<PathBuf> {
    let written = record(parent, outcome, stage, reason).ok();
    if let Some((title, message)) = notice(outcome, reason) {
        present(title, &message);
    }
    written
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::error::application::Operation;
    use std::{
        fs,
        path::Path,
        time::{SystemTime, UNIX_EPOCH},
    };

    struct Scratch(PathBuf);

    impl Scratch {
        fn new() -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            // Resolved, since a root reached through a link is refused.
            let path = fs::canonicalize(std::env::temp_dir())
                .unwrap()
                .join(format!(
                    "cadrumo-startup-outcome-{}-{nanos}",
                    std::process::id()
                ));
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn parent(variables: &[(&str, &Path)]) -> Parent {
        Parent {
            environment: variables
                .iter()
                .map(|(name, value)| ((*name).into(), value.as_os_str().to_owned()))
                .collect(),
            working_directory: std::env::temp_dir(),
        }
    }

    fn lines(file: &Path) -> Vec<serde_json::Value> {
        fs::read_to_string(file)
            .unwrap()
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect()
    }

    #[test]
    fn failures_classify_by_their_code_and_admissions_by_their_outcome() {
        let timed_out = ApplicationError::new(ErrorCode::TimedOut, Operation::Launch);
        let foreign = ApplicationError::new(ErrorCode::InstanceLockForeign, Operation::Launch);
        assert_eq!(Outcome::of_failure(&timed_out), Outcome::TimedOut);
        assert_eq!(Outcome::of_failure(&foreign), Outcome::Refused);
        assert_eq!(
            of_admission(&Ok(Admission::Activated)),
            Some((Outcome::HandedOff, None))
        );
        assert_eq!(
            of_admission(&Ok(Admission::OpenInOtherSession)),
            Some((Outcome::OpenInOtherSession, None))
        );
        assert_eq!(of_admission(&Ok(Admission::Headless)), None);
        assert_eq!(
            of_admission(&Err(timed_out)),
            Some((Outcome::TimedOut, Some(ErrorCode::TimedOut)))
        );
    }

    #[test]
    fn a_notice_names_the_reason_for_each_ended_launch_but_never_for_a_handoff() {
        assert!(notice(Outcome::HandedOff, None).is_none());
        for (outcome, reason) in [
            (Outcome::OpenInOtherSession, None),
            (Outcome::TimedOut, Some(ErrorCode::TimedOut)),
            (Outcome::Refused, Some(ErrorCode::LogUnavailable)),
        ] {
            assert!(notice(outcome, reason).is_some(), "{outcome:?}");
        }
        let (_, message) = notice(Outcome::Refused, Some(ErrorCode::LogUnavailable)).unwrap();
        assert!(message.contains("log_unavailable"), "{message}");
    }

    #[test]
    fn records_append_under_the_selected_root_and_carry_no_path() {
        let scratch = Scratch::new();
        let root = scratch.0.join("storage");
        let parent = parent(&[(cadrumo_platform::ROOT_VARIABLE, &root)]);
        let first = record(
            &parent,
            Outcome::Refused,
            HostStage::Package,
            Some(ErrorCode::LogUnavailable),
        )
        .unwrap();
        let second = record(&parent, Outcome::HandedOff, HostStage::Admission, None).unwrap();
        assert_eq!(first, second);
        assert!(first.starts_with(&root));
        let records = lines(&first);
        assert_eq!(records.len(), 2);
        assert_eq!(records[0]["reason"], "log_unavailable");
        assert_eq!(records[0]["stage"], "package");
        assert_eq!(records[1]["outcome"], "handed_off");
        assert_eq!(records[0]["rootIdentity"], records[1]["rootIdentity"]);
        let text = fs::read_to_string(&first).unwrap();
        assert!(!text.contains(root.to_str().unwrap()), "{text}");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = fs::metadata(&first).unwrap().permissions().mode() & 0o777;
            assert_eq!(mode, 0o600);
        }
    }

    #[cfg(unix)]
    #[test]
    fn an_unresolvable_selected_root_falls_back_to_the_installed_default() {
        let scratch = Scratch::new();
        let home = scratch.0.join("home");
        fs::create_dir_all(&home).unwrap();
        let relative = Path::new("relative-private-root-canary");
        let parent = parent(&[(cadrumo_platform::ROOT_VARIABLE, relative), ("HOME", &home)]);
        let file = record(&parent, Outcome::Refused, HostStage::Package, None).unwrap();
        assert!(file.starts_with(&home), "{}", file.display());
        let records = lines(&file);
        assert_eq!(records[0]["root"], "installed_default");
        assert!(!fs::read_to_string(&file).unwrap().contains("canary"));
    }

    #[test]
    fn a_launch_with_no_resolvable_root_reports_a_typed_failure_and_writes_nothing() {
        let scratch = Scratch::new();
        let relative = Path::new("relative-private-root-canary");
        let parent = parent(&[(cadrumo_platform::ROOT_VARIABLE, relative)]);
        // No home or application-data base either, so no default exists to fall back to.
        let error = record(&parent, Outcome::Refused, HostStage::Package, None);
        if cfg!(unix) {
            assert_eq!(error.unwrap_err().code, ErrorCode::LogUnavailable);
        }
        assert_eq!(fs::read_dir(&scratch.0).unwrap().count(), 0);
    }
}
