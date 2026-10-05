//! What the manager launches and how: the packaged single-process runtime host.
//!
//! The target is `P/bin/cadrumo-runtime` of a versioned package root `P`, whose interpreter
//! stays `P/python`. A development launcher that relaunches itself would leave the stop
//! signal with the wrong process, so the manager never launches one. The fixture test mode
//! may name a fixture image instead; release builds refuse that mode.

use super::environment::{ManagedLocations, runtime_environment};
use super::json::is_hex64;
use crate::contract::NATIVE;
use std::env;
use std::io;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::OnceLock;

/// File stem of the packaged runtime host among the declared console entrypoints.
pub const RUNTIME_IMAGE_STEM: &str = "cadrumo-runtime";

/// `CREATE_NO_WINDOW`: the runtime gets a console of its own, hidden, which the stop signal
/// targets. `CREATE_NEW_PROCESS_GROUP` is never used; it would ignore Ctrl+C.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const MAXIMUM_VERSION_CHARACTERS: usize = 64;

/// Why a launch target was refused before anything ran.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LaunchRefusal {
    RelativePath,
    StorageIdentity,
    Version,
}

/// The exact runtime invocation the core starts and restarts.
#[derive(Clone, PartialEq, Eq)]
pub struct LaunchTarget {
    image: PathBuf,
    storage_root: PathBuf,
    storage_identity: String,
    expected_version: String,
    package_root: Option<PathBuf>,
    environment: OnceLock<Vec<(std::ffi::OsString, std::ffi::OsString)>>,
}

impl std::fmt::Debug for LaunchTarget {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // Even a filtered child environment is not diagnostic output.
        formatter
            .debug_struct("LaunchTarget")
            .field("image", &self.image)
            .field("storage_root", &self.storage_root)
            .field("storage_identity", &self.storage_identity)
            .field("expected_version", &self.expected_version)
            .field("package_root", &self.package_root)
            .finish_non_exhaustive()
    }
}

impl LaunchTarget {
    /// The runtime host of the package whose default locations were resolved once.
    pub fn installed(
        locations: &ManagedLocations,
        storage_identity: String,
        expected_version: String,
    ) -> Result<Self, LaunchRefusal> {
        let mut target = Self::new(
            runtime_image(locations.package_root()),
            locations.storage_root().to_path_buf(),
            storage_identity,
            expected_version,
        )?;
        target.package_root = Some(locations.package_root().to_path_buf());
        Ok(target)
    }

    /// A fixture image speaking the supervised protocol, for the fixture test mode only.
    #[cfg(any(test, feature = "fixture-test-mode"))]
    pub fn fixture(
        image: PathBuf,
        storage_root: PathBuf,
        storage_identity: String,
        expected_version: String,
    ) -> Result<Self, LaunchRefusal> {
        Self::new(image, storage_root, storage_identity, expected_version)
    }

    fn new(
        image: PathBuf,
        storage_root: PathBuf,
        storage_identity: String,
        expected_version: String,
    ) -> Result<Self, LaunchRefusal> {
        if !image.is_absolute() || !storage_root.is_absolute() {
            return Err(LaunchRefusal::RelativePath);
        }
        if !is_hex64(&storage_identity) {
            return Err(LaunchRefusal::StorageIdentity);
        }
        let mut target = Self {
            image,
            storage_root,
            storage_identity,
            expected_version: String::new(),
            package_root: None,
            environment: OnceLock::new(),
        };
        target.set_expected_version(expected_version)?;
        Ok(target)
    }

    /// Replace the version the runtime must report, after a re-probe.
    pub fn set_expected_version(&mut self, version: String) -> Result<(), LaunchRefusal> {
        let length = version.chars().count();
        if !(1..=MAXIMUM_VERSION_CHARACTERS).contains(&length) || version.contains('\0') {
            return Err(LaunchRefusal::Version);
        }
        self.expected_version = version;
        Ok(())
    }

    pub fn image(&self) -> &Path {
        &self.image
    }

    pub fn storage_root(&self) -> &Path {
        &self.storage_root
    }

    pub fn storage_identity(&self) -> &str {
        &self.storage_identity
    }

    pub fn expected_version(&self) -> &str {
        &self.expected_version
    }

    /// The runtime's arguments, in order.
    pub fn arguments(&self) -> [&std::ffi::OsStr; 7] {
        [
            "--storage-root".as_ref(),
            self.storage_root.as_os_str(),
            "--storage-identity".as_ref(),
            self.storage_identity.as_ref(),
            "--expected-version".as_ref(),
            self.expected_version.as_ref(),
            "--supervised".as_ref(),
        ]
    }

    /// Start the runtime with the allow-list environment and the protocol on its stdio.
    pub(crate) fn spawn(&self) -> io::Result<Child> {
        let mut command = Command::new(&self.image);
        command
            .args(self.arguments())
            .env_clear()
            .envs(
                self.prepare_environment(env::vars_os())?
                    .iter()
                    .map(|(name, value)| (name, value)),
            )
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        if let Some(directory) = self.image.parent() {
            // The runtime's root never depends on the working directory; the image's own
            // directory exists for as long as the image does.
            command.current_dir(directory);
        }
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(CREATE_NO_WINDOW);
            // No process may start while this process is attached to a runtime console.
            let _quiescent = super::windows::console_quiescent();
            command.spawn()
        }
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            // Terminal job-control signals for the manager never reach the runtime.
            command.process_group(0);
            command.spawn()
        }
        #[cfg(not(any(windows, unix)))]
        {
            command.spawn()
        }
    }

    /// Prepare directories at first launch and keep only the canonical filtered output.
    /// Failed preparation is retryable; later launches reuse the pinned child snapshot.
    fn prepare_environment(
        &self,
        inherited: impl IntoIterator<Item = (std::ffi::OsString, std::ffi::OsString)>,
    ) -> io::Result<&Vec<(std::ffi::OsString, std::ffi::OsString)>> {
        if let Some(environment) = self.environment.get() {
            return Ok(environment);
        }
        let environment =
            runtime_environment(&self.storage_root, self.package_root.as_deref(), inherited)?;
        Ok(self.environment.get_or_init(|| environment))
    }
}

/// The packaged runtime host below a versioned package root.
pub fn runtime_image(package_root: &Path) -> PathBuf {
    package_root
        .join(NATIVE)
        .join(RUNTIME_IMAGE_STEM)
        .with_extension(env::consts::EXE_EXTENSION)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::ENTRYPOINT_FILES;

    fn absolute(path: &str) -> PathBuf {
        if cfg!(windows) {
            PathBuf::from(format!("C:\\{path}"))
        } else {
            PathBuf::from(format!("/{path}"))
        }
    }

    #[test]
    fn the_runtime_image_is_a_declared_entrypoint_in_the_native_directory() {
        let image = runtime_image(&absolute("cadrumo"));
        assert_eq!(
            image.parent(),
            Some(absolute("cadrumo").join(NATIVE).as_path())
        );
        if cfg!(windows) {
            let name = image.file_name().and_then(|name| name.to_str());
            assert!(
                ENTRYPOINT_FILES.iter().any(|file| Some(*file) == name),
                "{image:?}"
            );
        }
    }

    #[test]
    fn the_invocation_is_the_supervised_contract() {
        let target = LaunchTarget::fixture(
            runtime_image(&absolute("cadrumo")),
            absolute("data"),
            "a".repeat(64),
            "1.2.3".into(),
        )
        .expect("valid target");
        let arguments: Vec<_> = target
            .arguments()
            .iter()
            .map(|argument| argument.to_string_lossy().into_owned())
            .collect();
        assert_eq!(
            arguments,
            [
                "--storage-root".to_owned(),
                absolute("data").to_string_lossy().into_owned(),
                "--storage-identity".to_owned(),
                "a".repeat(64),
                "--expected-version".to_owned(),
                "1.2.3".to_owned(),
                "--supervised".to_owned(),
            ]
        );
    }

    #[test]
    fn malformed_targets_are_refused_before_launch() {
        let root = absolute("cadrumo");
        let refused = |storage: PathBuf, identity: &str, version: &str| {
            LaunchTarget::fixture(
                runtime_image(&root),
                storage,
                identity.into(),
                version.into(),
            )
            .err()
        };
        let identity = "a".repeat(64);
        assert_eq!(
            refused(PathBuf::from("data"), &identity, "1"),
            Some(LaunchRefusal::RelativePath)
        );
        assert_eq!(
            refused(absolute("data"), &"A".repeat(64), "1"),
            Some(LaunchRefusal::StorageIdentity)
        );
        assert_eq!(
            refused(absolute("data"), &identity, ""),
            Some(LaunchRefusal::Version)
        );
        assert_eq!(
            refused(absolute("data"), &identity, &"9".repeat(65)),
            Some(LaunchRefusal::Version)
        );
    }

    #[test]
    fn debug_output_never_discloses_captured_environment() {
        let target = LaunchTarget::fixture(
            absolute("runtime"),
            absolute("storage"),
            "a".repeat(64),
            "1".into(),
        )
        .unwrap();
        target
            .environment
            .set(vec![(
                "SECRET_INPUT".into(),
                "synthetic-private-value".into(),
            )])
            .unwrap();
        let diagnostic = format!("{target:?}");
        assert!(!diagnostic.contains("SECRET_INPUT"));
        assert!(!diagnostic.contains("synthetic-private-value"));
    }

    #[test]
    fn first_launch_retains_only_filtered_values_and_reuses_the_prepared_snapshot() {
        use crate::contract::{AUTHORITY, HOST_INHERITED_ENV, ROOT_VARIABLE};
        let root = std::env::temp_dir().join(format!(
            "cadrumo-manager-lazy-environment-{}",
            std::process::id()
        ));
        assert!(!root.exists());
        let mut target = LaunchTarget::fixture(
            absolute("runtime"),
            root.clone(),
            "a".repeat(64),
            "1".into(),
        )
        .unwrap();
        let package = absolute("package");
        target.package_root = Some(package.clone());
        assert!(target.environment.get().is_none());
        assert!(
            !root.exists(),
            "constructing a target creates no directories"
        );
        let first = target
            .prepare_environment([
                (ROOT_VARIABLE.into(), "discard-this-root".into()),
                ("PYTHONPATH".into(), "discard-this-secret".into()),
                ("PATH".into(), "initial-os-path".into()),
            ])
            .unwrap()
            .clone();
        assert!(root.is_dir());
        assert!(
            !first
                .iter()
                .any(|(_, value)| value == "discard-this-root" || value == "discard-this-secret")
        );
        for name in HOST_INHERITED_ENV {
            assert!(first.contains(&(name.into(), package.join(AUTHORITY).into_os_string())));
        }
        let second = target
            .prepare_environment([("PATH".into(), "later-os-path".into())])
            .unwrap();
        assert_eq!(&first, second);
        std::fs::remove_dir_all(root).unwrap();
    }
}
