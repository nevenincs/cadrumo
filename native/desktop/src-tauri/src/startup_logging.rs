//! Persist startup failures before the fallible Python environment projection.
//!
//! Location authority stays with the generated contract and native root resolver:
//! the log directory is a declared path beneath the storage root.

use crate::environment::Parent;
use cadrumo_application::diagnostics::Diagnostics;

use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    value::RelativePath,
};
use serde::Deserialize;
use std::path::{Path, PathBuf};

#[derive(Deserialize)]
struct Contract {
    desktop_defaults: Defaults,
}

#[derive(Deserialize)]
struct Defaults {
    logs: RelativePath,
    log_max_bytes: u64,
    log_backups: u32,
}

/// Called after instance admission and before package/interpreter validation.
/// A refused location records only the safe typed failure and remains buffered.
pub fn configure(parent: &Parent, diagnostics: &Diagnostics) {
    match std::env::current_exe() {
        Ok(executable) => configure_for(&executable, parent, diagnostics),
        Err(error) => diagnostics.failure(unavailable().caused_by(error)),
    }
}

/// Configure startup logging for the host at `executable`, whose location decides
/// whether it is installed or a development build.
fn configure_for(executable: &Path, parent: &Parent, diagnostics: &Diagnostics) {
    let outcome: Result<()> = (|| {
        let contract: Contract =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
                .map_err(|error| unavailable().caused_by(error))?;
        let directory = location(executable, parent, &contract)?;
        diagnostics.configure(
            &directory,
            contract.desktop_defaults.log_max_bytes,
            contract.desktop_defaults.log_backups,
        )?;
        Ok(())
    })();
    if let Err(error) = outcome {
        diagnostics.failure(error);
    }
}

fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::LogUnavailable, Operation::Logging)
}

fn location(executable: &Path, parent: &Parent, contract: &Contract) -> Result<PathBuf> {
    use cadrumo_platform::storage::{
        detect_mode, resolve_storage_root_with, validated_absolute_path,
    };
    // Variable names are case-insensitive on Windows only.
    let lookup = |name: &str| {
        parent
            .environment
            .iter()
            .rev()
            .find(|(key, _)| {
                if cfg!(windows) {
                    key.to_string_lossy().eq_ignore_ascii_case(name)
                } else {
                    key.as_os_str() == name
                }
            })
            .map(|(_, value)| value.clone())
    };
    let evidence = detect_mode(executable)
        .map_err(|error| unavailable().caused_by(std::io::Error::other(error)))?;
    let root = resolve_storage_root_with(&evidence, &lookup)
        .map_err(|error| unavailable().caused_by(std::io::Error::from(error)))?
        .root;
    validated_absolute_path(&contract.desktop_defaults.logs.under(&root))
        .map_err(|error| unavailable().caused_by(std::io::Error::from(error)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::{EventKind, delivery_wait::delivered};
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
            // Resolved, since a root reached through a link is refused.
            let path = fs::canonicalize(std::env::temp_dir())
                .unwrap()
                .join(format!(
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

    /// A host inside a scratch package, so mode detection never depends on where the test
    /// binary itself was built: a Debug test build bakes its development root and a release
    /// one reads the package manifest; the parent's root override selects the root in both.
    fn packaged_host(scratch: &Scratch) -> PathBuf {
        let package = scratch.0.join("package");
        let manifest = cadrumo_platform::MODE_PACKAGE_MANIFEST
            .split('/')
            .fold(package.clone(), |path, part| path.join(part));
        fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        fs::write(manifest, "{}").unwrap();
        package.join(format!("cadrumo{}", std::env::consts::EXE_SUFFIX))
    }

    #[test]
    fn a_projection_failure_is_written_before_the_projection_can_run() {
        let scratch = Scratch::new();
        let host = packaged_host(&scratch);
        let parent = parent(&scratch.0.join("storage"));
        let diagnostics = Diagnostics::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        configure_for(&host, &parent, &diagnostics);
        // The writer publishes the file's paths and replays buffered events.
        delivered(&diagnostics);
        let paths = diagnostics.snapshot(u64::MAX).paths.unwrap();
        let expected = location(&host, &parent, &contract()).unwrap();
        assert_eq!(paths.current.parent(), Some(expected.as_path()));
        diagnostics.failure(
            ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Environment)
                .caused_by(std::io::Error::other("synthetic-private-projection-output")),
        );
        delivered(&diagnostics);
        let log = fs::read_to_string(&paths.current).unwrap();
        assert!(log.contains("environment_failed"));
        assert!(!log.contains("synthetic-private-projection-output"));
        configure_for(&host, &parent, &diagnostics);
        delivered(&diagnostics);
        assert_eq!(fs::read_to_string(paths.current).unwrap(), log);
    }

    #[test]
    fn a_retired_log_directory_override_does_not_move_the_startup_log() {
        let scratch = Scratch::new();
        let host = packaged_host(&scratch);
        let mut parent = parent(&scratch.0.join("storage"));
        parent
            .environment
            .push(("CADRUMO_LOG_DIR".into(), "custom-logs".into()));
        let diagnostics = Diagnostics::default();
        diagnostics.event(EventKind::HostStarted, None, None);
        configure_for(&host, &parent, &diagnostics);
        delivered(&diagnostics);
        let paths = diagnostics.snapshot(u64::MAX).paths.unwrap();
        let expected = location(&host, &parent, &contract()).unwrap();
        assert_eq!(paths.current.parent(), Some(expected.as_path()));
        assert!(expected.starts_with(scratch.0.join("storage")));
        assert!(!scratch.0.join("storage").join("custom-logs").exists());
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
