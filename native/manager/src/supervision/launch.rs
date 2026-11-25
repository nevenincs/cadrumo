//! What the manager launches and how: the packaged single-process runtime host.
//!
//! The target is the Cadrumo binary `P/cadrumo` of a versioned package root `P` in its runtime
//! role, so the runtime is the same image as the window and Windows groups them as one
//! application; its interpreter stays `P/python`. A development launcher that relaunches
//! itself would leave the stop signal with the wrong process, so the manager never launches
//! one. The fixture test mode may name a fixture image instead; release builds refuse that
//! mode.

use super::environment::{ManagedLocations, runtime_environment};
use super::json::is_hex64;
use cadrumo_application::role::Role;
use std::env;
use std::io;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::OnceLock;

/// A started runtime and what keeps it contained for as long as the supervisor holds it.
pub(crate) struct Launched {
    pub(crate) child: Child,
    /// Dropped once the supervisor has observed the runtime's exit: on Linux and macOS
    /// this ends whatever the runtime left in its process group.
    pub(crate) containment: Box<dyn Send>,
}

/// File stem of the Cadrumo binary at the package root, which runs the runtime role.
pub const RUNTIME_IMAGE_STEM: &str = "cadrumo";

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
    /// The role the image runs as; a fixture image has none.
    role: Option<Role>,
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
            .field("role", &self.role)
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
        target.role = Some(Role::Runtime);
        Ok(target)
    }

    /// The runtime role of a real package for the fixture test mode, which keeps the
    /// isolated root and admission of a fixture.
    #[cfg(any(test, feature = "fixture-test-mode"))]
    pub fn packaged_fixture(
        package_root: &Path,
        storage_root: PathBuf,
        storage_identity: String,
        expected_version: String,
    ) -> Result<Self, LaunchRefusal> {
        let mut target = Self::new(
            runtime_image(package_root),
            storage_root,
            storage_identity,
            expected_version,
        )?;
        target.role = Some(Role::Runtime);
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
            role: None,
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

    /// The package root of an installed runtime; a fixture target has none.
    pub fn package_root(&self) -> Option<&Path> {
        self.package_root.as_deref()
    }

    pub fn storage_identity(&self) -> &str {
        &self.storage_identity
    }

    pub fn expected_version(&self) -> &str {
        &self.expected_version
    }

    /// The arguments before the runtime's own: the role the image runs as.
    pub fn role_arguments(&self) -> &'static [&'static str] {
        match self.role {
            Some(role) => role.arguments(),
            None => &[],
        }
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
    pub(crate) fn spawn(&self) -> io::Result<Launched> {
        let mut command = Command::new(&self.image);
        command
            .args(self.role_arguments())
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
            let child = cadrumo_application::process::creation::run(|| command.spawn())?;
            Ok(Launched {
                child,
                containment: Box::new(()),
            })
        }
        #[cfg(unix)]
        {
            // The runtime is created into a process scope of its own: a group apart from
            // the terminal's job control whose guardian ends it, and what the runtime
            // started in it, when this process drops the scope or ends however it ends.
            let scope = cadrumo_platform::process_scope::ProcessScope::new()?;
            scope.join(&mut command)?;
            let child = command.spawn()?;
            Ok(Launched {
                child,
                containment: Box::new(scope),
            })
        }
        #[cfg(not(any(windows, unix)))]
        {
            Ok(Launched {
                child: command.spawn()?,
                containment: Box::new(()),
            })
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

/// The Cadrumo binary at a versioned package root, which runs the runtime role.
pub fn runtime_image(package_root: &Path) -> PathBuf {
    package_root
        .join(RUNTIME_IMAGE_STEM)
        .with_extension(env::consts::EXE_EXTENSION)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contract::INSTALLATION_CONTRACT;

    fn absolute(path: &str) -> PathBuf {
        if cfg!(windows) {
            PathBuf::from(format!("C:\\{path}"))
        } else {
            PathBuf::from(format!("/{path}"))
        }
    }

    #[test]
    fn the_runtime_image_is_the_desktop_application_image_at_the_package_root() {
        let image = runtime_image(&absolute("cadrumo"));
        assert_eq!(image.parent(), Some(absolute("cadrumo").as_path()));
        let contract: serde_json::Value = serde_json::from_str(INSTALLATION_CONTRACT).unwrap();
        let desktop = contract["layout"]["application_images"]
            .as_array()
            .unwrap()
            .iter()
            .find(|image| image["desktop"] == true)
            .expect("the layout declares the desktop image");
        assert_eq!(desktop["name"], RUNTIME_IMAGE_STEM);
        assert_eq!(desktop["placement"], ".");
    }

    #[test]
    fn only_a_packaged_runtime_runs_as_the_runtime_role() {
        let packaged = LaunchTarget::packaged_fixture(
            &absolute("cadrumo"),
            absolute("data"),
            "a".repeat(64),
            "1.2.3".into(),
        )
        .unwrap();
        assert_eq!(packaged.image(), runtime_image(&absolute("cadrumo")));
        assert_eq!(packaged.role_arguments(), ["--role", "runtime"]);
        let fixture = LaunchTarget::fixture(
            absolute("fixture"),
            absolute("data"),
            "a".repeat(64),
            "1.2.3".into(),
        )
        .unwrap();
        assert!(fixture.role_arguments().is_empty());
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
                ("SYSTEMROOT".into(), r"C:\Windows".into()),
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
            assert!(first.iter().any(|(key, value)| {
                key == name
                    && Path::new(value)
                        .components()
                        .eq(package.join(AUTHORITY).components())
            }));
        }
        let second = target
            .prepare_environment([("PATH".into(), "later-os-path".into())])
            .unwrap();
        assert_eq!(&first, second);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    mod containment {
        use super::*;
        use std::io::{BufRead, BufReader, Read};
        use std::os::unix::fs::PermissionsExt;
        use std::time::{Duration, Instant};

        const HOST_HELPER: &str = "CADRUMO_MANAGER_RUNTIME_HOST";
        const BOUND: Duration = Duration::from_secs(10);

        /// A stand-in runtime that records its pid beneath the root it is given, then only
        /// waits; it ignores the hangup an orphaned group is sent, so only a kill ends it.
        const RUNTIME: &str = "#!/bin/sh\n\
                               trap '' HUP\n\
                               echo $$ > \"$2/runtime-pid\"\n\
                               exec /bin/sleep 600\n";

        fn scratch(label: &str) -> PathBuf {
            let nanos = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = env::temp_dir().canonicalize().unwrap().join(format!(
                "cadrumo-manager-{label}-{}-{nanos}",
                std::process::id()
            ));
            std::fs::create_dir_all(&path).unwrap();
            path
        }

        fn target(root: &Path) -> LaunchTarget {
            let image = root.join("runtime.sh");
            std::fs::write(&image, RUNTIME).unwrap();
            std::fs::set_permissions(&image, std::fs::Permissions::from_mode(0o755)).unwrap();
            LaunchTarget::fixture(image, root.join("storage"), "a".repeat(64), "1.0".into())
                .unwrap()
        }

        fn runtime_pid(root: &Path) -> i32 {
            let record = root.join("storage").join("runtime-pid");
            let deadline = Instant::now() + BOUND;
            loop {
                if let Some(pid) = std::fs::read_to_string(&record)
                    .ok()
                    .and_then(|text| text.trim().parse().ok())
                {
                    return pid;
                }
                assert!(Instant::now() < deadline, "the runtime never started");
                std::thread::sleep(Duration::from_millis(10));
            }
        }

        fn signal(name: &str, pid: i32) -> bool {
            Command::new("/bin/kill")
                .args([format!("-{name}"), pid.to_string()])
                .stderr(Stdio::null())
                .status()
                .unwrap()
                .success()
        }

        fn running(pid: i32) -> bool {
            // Signal 0 only probes for the process and delivers nothing.
            signal("0", pid)
        }

        fn group_of(pid: u32) -> u32 {
            let output = Command::new("/bin/ps")
                .args(["-o", "pgid=", "-p", &pid.to_string()])
                .output()
                .unwrap();
            String::from_utf8(output.stdout)
                .unwrap()
                .trim()
                .parse()
                .unwrap()
        }

        fn ends_within_bound(pid: i32) {
            let deadline = Instant::now() + BOUND;
            while running(pid) {
                assert!(Instant::now() < deadline, "runtime {pid} outlived its host");
                std::thread::sleep(Duration::from_millis(10));
            }
        }

        /// The child-process mode: a supervisor host that starts the runtime, says so,
        /// and holds it until it is killed.
        #[test]
        fn runtime_host_helper() {
            let Some(root) = env::var_os(HOST_HELPER) else {
                return;
            };
            let launched = target(Path::new(&root)).spawn().unwrap();
            runtime_pid(Path::new(&root));
            println!("launched");
            let _held = launched;
            let mut sink = Vec::new();
            let _ = io::stdin().read_to_end(&mut sink);
            std::process::exit(0);
        }

        #[test]
        fn a_runtime_ends_when_its_supervisor_host_is_killed() {
            let root = scratch("runtime-host");
            let mut host = Command::new(env::current_exe().unwrap())
                .args([
                    "--exact",
                    "supervision::launch::tests::containment::runtime_host_helper",
                    "--nocapture",
                    "--test-threads=1",
                ])
                .env(HOST_HELPER, &root)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
                .unwrap();
            let mut stdout = BufReader::new(host.stdout.take().unwrap());
            let mut line = String::new();
            while !line.contains("launched") {
                line.clear();
                assert_ne!(
                    stdout.read_line(&mut line).unwrap(),
                    0,
                    "the host ended early"
                );
            }
            let pid = runtime_pid(&root);
            assert!(running(pid));
            // The runtime is in its guardian's group, apart from the host's.
            let runtime_group = group_of(u32::try_from(pid).unwrap());
            assert!(runtime_group > 0);
            assert_ne!(runtime_group, group_of(host.id()));
            assert_ne!(i32::try_from(runtime_group).unwrap(), pid);
            host.kill().unwrap();
            host.wait().unwrap();
            ends_within_bound(pid);
            std::fs::remove_dir_all(root).unwrap();
        }

        #[test]
        fn a_runtime_that_exited_on_its_own_releases_its_containment() {
            let root = scratch("runtime-clean");
            let Launched {
                mut child,
                containment,
            } = target(&root).spawn().unwrap();
            let pid = runtime_pid(&root);
            // A drained runtime exits on its own before the supervisor lets go of it.
            assert!(signal("TERM", pid));
            child.wait().unwrap();
            drop(containment);
            assert!(!running(pid));
            std::fs::remove_dir_all(root).unwrap();
        }
    }
}
