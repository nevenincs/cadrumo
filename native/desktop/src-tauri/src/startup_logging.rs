//! Persist startup failures before the fallible Python environment projection.
//!
//! Location authority stays with the generated contract and native root resolver.
//! Member overrides whose semantics belong to Settings defer file setup to it.

use crate::environment::Parent;
use cadrumo_application::diagnostics::Diagnostics;

#[cfg(windows)]
use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    value::RelativePath,
};
#[cfg(windows)]
use serde::Deserialize;
#[cfg(windows)]
use std::path::{Path, PathBuf};

#[cfg(windows)]
#[derive(Deserialize)]
struct Contract {
    desktop_defaults: Defaults,
    storage_environment_allowlist: Vec<String>,
}

#[cfg(windows)]
#[derive(Deserialize)]
struct Defaults {
    logs: RelativePath,
    log_max_bytes: u64,
    log_backups: u32,
}

/// Called after instance admission and before package/interpreter validation.
/// A refused location records only the safe typed failure and remains buffered.
pub fn configure(parent: &Parent, diagnostics: &Diagnostics) {
    #[cfg(windows)]
    {
        let outcome: Result<()> = (|| {
            let contract: Contract =
                serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
                    .map_err(|error| unavailable().caused_by(error))?;
            let executable =
                std::env::current_exe().map_err(|error| unavailable().caused_by(error))?;
            if let Some(directory) = location(&executable, parent, &contract)? {
                diagnostics.configure(
                    &directory,
                    contract.desktop_defaults.log_max_bytes,
                    contract.desktop_defaults.log_backups,
                )?;
            }
            Ok(())
        })();
        if let Err(error) = outcome {
            diagnostics.failure(error);
        }
    }
    #[cfg(not(windows))]
    let _ = (parent, diagnostics);
}

#[cfg(windows)]
fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::LogUnavailable, Operation::Logging)
}

#[cfg(windows)]
fn location(executable: &Path, parent: &Parent, contract: &Contract) -> Result<Option<PathBuf>> {
    use cadrumo_platform::{
        ROOT_VARIABLE,
        storage::{detect_mode, resolve_storage_root_with, validated_absolute_path},
    };
    if parent.environment.iter().any(|(key, value)| {
        contract.storage_environment_allowlist.iter().any(|name| {
            key.to_string_lossy().eq_ignore_ascii_case(name)
                && !name.eq_ignore_ascii_case(ROOT_VARIABLE)
                && !value.to_string_lossy().trim().is_empty()
        })
    }) {
        return Ok(None);
    }
    let lookup = |name: &str| {
        parent
            .environment
            .iter()
            .rev()
            .find(|(key, _)| key.to_string_lossy().eq_ignore_ascii_case(name))
            .map(|(_, value)| value.clone())
    };
    let evidence = detect_mode(executable)
        .map_err(|error| unavailable().caused_by(std::io::Error::other(error)))?;
    let root = resolve_storage_root_with(&evidence, &lookup)
        .map_err(|error| unavailable().caused_by(std::io::Error::from(error)))?
        .root;
    let directory = validated_absolute_path(&contract.desktop_defaults.logs.under(&root))
        .map_err(|error| unavailable().caused_by(std::io::Error::from(error)))?;
    Ok(Some(directory))
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::EventKind;
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    struct Scratch(PathBuf);

    impl Scratch {
        fn new() -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "cadrumo-startup-logging-{}-{nanos}",
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

    fn contract() -> Contract {
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap()
    }

    fn parent(root: &Path) -> Parent {
        Parent {
            environment: vec![(
                cadrumo_platform::ROOT_VARIABLE.into(),
                root.as_os_str().to_owned(),
            )],
            working_directory: root.to_owned(),
        }
    }

    #[test]
    fn a_projection_failure_is_written_before_the_projection_can_run() {
        let scratch = Scratch::new();
        let parent = parent(&scratch.0.join("storage"));
        let diagnostics = Diagnostics::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        configure(&parent, &diagnostics);
        let paths = diagnostics.snapshot(u64::MAX).paths.unwrap();
        let expected = location(&std::env::current_exe().unwrap(), &parent, &contract())
            .unwrap()
            .unwrap();
        assert_eq!(paths.current.parent(), Some(expected.as_path()));
        diagnostics.failure(
            ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment)
                .caused_by(std::io::Error::other("synthetic-private-projection-output")),
        );
        let log = fs::read_to_string(&paths.current).unwrap();
        assert!(log.contains("environment_failed"));
        assert!(!log.contains("synthetic-private-projection-output"));
        configure(&parent, &diagnostics);
        assert_eq!(fs::read_to_string(paths.current).unwrap(), log);
    }

    #[test]
    fn member_overrides_remain_with_python_without_opening_a_default_log() {
        let scratch = Scratch::new();
        let mut parent = parent(&scratch.0.join("storage"));
        parent
            .environment
            .push(("CADRUMO_LOG_DIR".into(), "custom-logs".into()));
        let diagnostics = Diagnostics::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        configure(&parent, &diagnostics);
        assert!(diagnostics.snapshot(u64::MAX).paths.is_none());
        assert!(!scratch.0.join("storage").exists());
    }

    #[test]
    fn refused_roots_are_safe_and_do_not_use_the_working_directory_as_a_fallback() {
        let scratch = Scratch::new();
        let mut parent = parent(Path::new("C:relative-private-root-canary"));
        parent.working_directory = scratch.0.clone();
        let diagnostics = Diagnostics::default();
        configure(&parent, &diagnostics);
        let snapshot = diagnostics.snapshot(u64::MAX);
        assert!(snapshot.paths.is_none());
        assert_eq!(snapshot.events.len(), 1);
        assert_eq!(
            snapshot.events[0].failure.as_ref().unwrap().code,
            ErrorCode::LogUnavailable
        );
        let serialized = serde_json::to_string(&snapshot).unwrap();
        assert!(!serialized.contains("relative-private-root-canary"));
        assert_eq!(fs::read_dir(&scratch.0).unwrap().count(), 0);
    }
}
