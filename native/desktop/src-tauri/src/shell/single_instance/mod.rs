//! One desktop window per user and storage root, across installed versions and
//! paths.
//!
//! The lock key is the application identifier of the generated Tauri
//! configuration, the product identity family with its channel suffix,
//! scoped to the storage root the launch selects by that root's storage
//! identity. Neither the install path nor the version enters it, so every
//! installed version of one channel on one root shares the lock, while a
//! launch on another root holds a lock of its own and opens its own window.
//! A second GUI launch on a root hands activation to that root's open window
//! and exits; a newer version launched while an older window is open on the
//! same root activates that window, and the switch completes when the user
//! closes it. The headless CLI passthrough never takes or contends for the
//! lock.
//!
//! The lock spans all of the user's sessions. A window can be brought
//! forward only in its own session, so a launch in another session sends
//! no request: it reports that the window is open in another session and
//! exits.
//!
//! An activation request carries nothing from the second instance: the
//! holder learns only that a request arrived, and answers by restoring and
//! focusing its window.
use crate::launch::Mode;
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use serde::Deserialize;
use std::sync::{Arc, Mutex, OnceLock};
use tauri::{Config, Manager, Runtime, Window};

#[cfg(windows)]
use cadrumo_platform::desktop::{InstanceClaim, InstanceLock, claim_instance};
#[cfg(unix)]
mod posix;
#[cfg(unix)]
use posix::{InstanceClaim, InstanceLock, claim_instance};

/// How long a second launch waits for the open window to acknowledge it, or
/// for a closing one to release the lock: the declared shutdown budget, so a
/// relaunch during a slow close succeeds.
const PATIENCE: std::time::Duration = cadrumo_application::shutdown::RELAUNCH_PATIENCE;

/// The generated configuration the Tauri context is compiled from, read here
/// before the context exists so the claim precedes all per-user state.
const CONFIGURATION: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/tauri.conf.json"));

/// What the launch may do once its mode is known.
pub enum Admission {
    /// The CLI passthrough, which runs without the lock.
    Headless,
    /// This launch holds the lock and opens the window.
    Primary(Primary),
    /// Another window holds the lock and accepted activation; this launch
    /// exits with 0.
    Activated,
    /// Another window holds the lock in another session of this user, which
    /// cannot be activated from here. The launch reported it on standard
    /// error and exits with 0.
    OpenInOtherSession,
}

/// The standard error line of a launch whose window is open in another
/// session. A protocol token, not operator text.
const OTHER_SESSION_REPORT: &str = "{\"outcome\":\"open_in_other_session\"}";

/// The held instance lock. Dropping it releases the lock.
pub struct Primary {
    _lock: InstanceLock,
    activation: Arc<Activation>,
}

/// Activation requests as the window's lifetime allows them.
#[derive(Default)]
struct Activation {
    state: Mutex<State>,
}

enum State {
    /// No window yet; remembers whether a request arrived meanwhile.
    Waiting {
        pending: bool,
    },
    Attached(Box<dyn Fn() + Send>),
    /// The application is closing; requests wait for the lock instead.
    Closed,
}

impl Default for State {
    fn default() -> Self {
        State::Waiting { pending: false }
    }
}

impl Activation {
    /// Answers one request, returning whether it was accepted.
    fn request(&self) -> bool {
        let Ok(mut state) = self.state.lock() else {
            return false;
        };
        match &mut *state {
            State::Waiting { pending } => {
                *pending = true;
                true
            }
            State::Attached(focus) => {
                focus();
                true
            }
            State::Closed => false,
        }
    }

    /// Routes requests to `focus`, answering one that arrived before.
    fn attach(&self, focus: Box<dyn Fn() + Send>) {
        let Ok(mut state) = self.state.lock() else {
            return;
        };
        match &*state {
            State::Closed => {}
            State::Waiting { pending } => {
                if *pending {
                    focus();
                }
                *state = State::Attached(focus);
            }
            State::Attached(_) => *state = State::Attached(focus),
        }
    }

    fn close(&self) {
        if let Ok(mut state) = self.state.lock() {
            *state = State::Closed;
        }
    }
}

/// The activation state of this process's held lock, for the shell plugin.
static ACTIVATION: OnceLock<Arc<Activation>> = OnceLock::new();

fn invalid() -> ApplicationError {
    ApplicationError::new(ErrorCode::InvalidArguments, Operation::Launch)
}

#[derive(Deserialize)]
struct Identity {
    identifier: String,
}

/// The family of a generated configuration: its application identifier,
/// which carries the identity family and channel. Nothing else in the
/// configuration enters the lock key; the storage root completes it.
fn family_of(configuration: &str) -> Result<String> {
    serde_json::from_str::<Identity>(configuration)
        .map(|identity| identity.identifier)
        .map_err(|e| invalid().caused_by(e))
}

fn family() -> Result<String> {
    family_of(CONFIGURATION)
}

/// The lock key of `family` for the storage root this process's environment
/// selects. The root is created when absent, so a first launch has an
/// identity to claim under.
fn root_key(family: &str) -> Result<String> {
    let environment = || ApplicationError::new(ErrorCode::EnvironmentFailed, Operation::Launch);
    let root = cadrumo_platform::storage::resolve_storage_root()
        .map_err(|e| environment().caused_by(std::io::Error::from(e)))?
        .root;
    cadrumo_application::instance_scope::scoped_to_root(family, &root)
        .map_err(|e| environment().caused_by(e))
}

/// Admits a launch in `mode`. The GUI claims the lock before any other
/// per-user state is opened; the CLI passthrough returns at once.
pub fn admit(mode: &Mode) -> Result<Admission> {
    admit_with(mode, || root_key(&family()?))
}

fn admit_with(mode: &Mode, key: impl FnOnce() -> Result<String>) -> Result<Admission> {
    admit_within(mode, key, PATIENCE)
}

fn admit_within(
    mode: &Mode,
    key: impl FnOnce() -> Result<String>,
    patience: std::time::Duration,
) -> Result<Admission> {
    if matches!(mode, Mode::Cli(_) | Mode::Health { .. }) {
        return Ok(Admission::Headless);
    }
    let admission = claim_within(&key()?, patience)?;
    if let Admission::Primary(primary) = &admission
        && ACTIVATION.set(primary.activation.clone()).is_err()
    {
        return Err(invalid());
    }
    Ok(admission)
}

#[cfg(test)]
fn claim(family: &str) -> Result<Admission> {
    claim_within(family, PATIENCE)
}

fn claim_within(family: &str, patience: std::time::Duration) -> Result<Admission> {
    admitted(
        claim_instance(family, patience),
        &mut std::io::stderr().lock(),
    )
}

/// The admission a lock claim grants, reporting a window open in another
/// session on `report`.
fn admitted(
    claim: std::io::Result<InstanceClaim>,
    report: &mut dyn std::io::Write,
) -> Result<Admission> {
    let unavailable = || ApplicationError::new(ErrorCode::DesktopUnavailable, Operation::Launch);
    match claim {
        Ok(InstanceClaim::Activated) => Ok(Admission::Activated),
        Ok(InstanceClaim::OtherSession) => {
            // Best effort: a launch without a console has nowhere to report.
            let _ = writeln!(report, "{OTHER_SESSION_REPORT}");
            Ok(Admission::OpenInOtherSession)
        }
        Ok(InstanceClaim::Primary(mut lock)) => {
            let activation = Arc::new(Activation::default());
            let requests = activation.clone();
            lock.serve(move || requests.request())
                .map_err(|e| unavailable().caused_by(e))?;
            Ok(Admission::Primary(Primary {
                _lock: lock,
                activation,
            }))
        }
        Err(e) if e.kind() == std::io::ErrorKind::TimedOut => {
            Err(ApplicationError::new(ErrorCode::TimedOut, Operation::Launch).caused_by(e))
        }
        Err(e) if foreign(&e) => Err(ApplicationError::new(
            ErrorCode::InstanceLockForeign,
            Operation::Launch,
        )
        .caused_by(e)),
        Err(e) => Err(unavailable().caused_by(e)),
    }
}

/// Whether a claim failed because another account placed an object under
/// one of the lock's names first. On Windows the names are predictable, and
/// the platform refuses an object this user does not own, cannot open with
/// full access, or that has another type under the lock name, as permission
/// denied. On POSIX that kind means the instance directory is open to other
/// accounts or was replaced, which is a different refusal.
fn foreign(error: &std::io::Error) -> bool {
    cfg!(windows) && error.kind() == std::io::ErrorKind::PermissionDenied
}

/// Refuses a running configuration whose identity differs from the one the
/// lock was claimed under.
pub fn verify(config: &Config) -> Result<()> {
    if ACTIVATION.get().is_some() && config.identifier != family()? {
        return Err(invalid());
    }
    Ok(())
}

/// Restores and focuses `window` for each activation request from now on,
/// and once for a request that arrived before it existed.
pub fn attach<R: Runtime>(window: &Window<R>, diagnostics: Arc<Diagnostics>) {
    let Some(activation) = ACTIVATION.get() else {
        return;
    };
    let main = window
        .app_handle()
        .config()
        .app
        .windows
        .first()
        .is_some_and(|config| config.label == window.label());
    if !main && window.label() != "startup" {
        return;
    }
    let window = window.clone();
    activation.attach(Box::new(move || {
        for result in [window.unminimize(), window.show(), window.set_focus()] {
            if let Err(error) = result {
                diagnostics.failure(
                    ApplicationError::new(ErrorCode::WebviewFailed, Operation::Webview)
                        .caused_by(error),
                );
            }
        }
    }));
}

/// Stops accepting activation once the window is going away, so a second
/// launch waits for the lock instead of activating a closing window.
pub fn close() {
    if let Some(activation) = ACTIVATION.get() {
        activation.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{BufRead, BufReader, Read},
        path::PathBuf,
        process::{Command, Stdio},
        sync::{
            atomic::{AtomicUsize, Ordering},
            mpsc,
        },
        time::{SystemTime, UNIX_EPOCH},
    };

    const FAMILY_VARIABLE: &str = "CADRUMO_INSTANCE_TEST_FAMILY";
    const PATIENCE_VARIABLE: &str = "CADRUMO_INSTANCE_TEST_PATIENCE_MS";
    const RECORD_VARIABLE: &str = "CADRUMO_INSTANCE_TEST_RECORD";
    const CLOSING_VARIABLE: &str = "CADRUMO_INSTANCE_TEST_CLOSING_MS";
    /// Marks the helper's reports among the test harness's own output.
    const REPORT: &str = "@instance-report ";

    /// A family no real installation uses, unique to one test.
    fn unique_family(label: &str) -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        format!("test.cadrumo.{label}-{}-{nanos}", std::process::id())
    }

    fn configuration(identifier: &str, version: &str, root: &str) -> String {
        serde_json::json!({
            "productName": "Cadrumo",
            "identifier": identifier,
            "version": version,
            "build": {"frontendDist": format!("{root}/frontend")},
            "bundle": {"icon": [format!("{root}/icons/icon.ico")]},
        })
        .to_string()
    }

    #[test]
    fn the_key_is_the_identifier_and_ignores_version_and_install_path() {
        let old = family_of(&configuration(
            "md.neve.cadrumo",
            "1.4.0",
            "C:/Program Files/Cadrumo/1.4.0",
        ))
        .unwrap();
        let new = family_of(&configuration(
            "md.neve.cadrumo",
            "2.0.1",
            "D:/Users/someone/AppData/Local/Programs/Cadrumo/2.0.1",
        ))
        .unwrap();
        assert_eq!(old, "md.neve.cadrumo");
        assert_eq!(old, new);
        let preview = family_of(&configuration(
            "md.neve.cadrumo.preview",
            "2.0.1",
            "C:/Program Files/Cadrumo/2.0.1",
        ))
        .unwrap();
        assert_ne!(preview, old);
        assert_eq!(
            family_of("{}").unwrap_err().code,
            ErrorCode::InvalidArguments
        );
    }

    #[test]
    fn the_key_is_the_identity_the_application_runs_under() {
        let context: tauri::Context<tauri::test::MockRuntime> =
            tauri::generate_context!(test = true);
        assert_eq!(family().unwrap(), context.config().identifier);
        verify(context.config()).unwrap();
    }

    #[test]
    fn requests_before_the_window_focus_it_once_and_closing_refuses() {
        let activation = Activation::default();
        assert!(activation.request());
        assert!(activation.request());
        let focused = Arc::new(AtomicUsize::new(0));
        let seen = focused.clone();
        activation.attach(Box::new(move || {
            seen.fetch_add(1, Ordering::SeqCst);
        }));
        assert_eq!(focused.load(Ordering::SeqCst), 1);
        assert!(activation.request());
        assert_eq!(focused.load(Ordering::SeqCst), 2);
        activation.close();
        assert!(!activation.request());
        assert_eq!(focused.load(Ordering::SeqCst), 2);
        // A window attached after closing never takes requests again.
        activation.attach(Box::new(|| panic!("attached after close")));
        assert!(!activation.request());
    }

    #[test]
    fn a_window_in_another_session_is_reported_and_the_launch_exits() {
        let mut report = Vec::new();
        let admission = admitted(Ok(InstanceClaim::OtherSession), &mut report).unwrap();
        assert!(matches!(admission, Admission::OpenInOtherSession));
        assert_eq!(
            report,
            format!(
                "{OTHER_SESSION_REPORT}
"
            )
            .as_bytes()
        );
        let parsed: serde_json::Value = serde_json::from_slice(&report).unwrap();
        assert_eq!(parsed["outcome"], "open_in_other_session");
        // An activation in this session reports nothing.
        let mut quiet = Vec::new();
        let admission = admitted(Ok(InstanceClaim::Activated), &mut quiet).unwrap();
        assert!(matches!(admission, Admission::Activated));
        assert!(quiet.is_empty());
        let timed_out = admitted(Err(std::io::ErrorKind::TimedOut.into()), &mut quiet);
        assert_eq!(timed_out.err().unwrap().code, ErrorCode::TimedOut);
        let refused = admitted(Err(std::io::ErrorKind::PermissionDenied.into()), &mut quiet);
        let expected = if cfg!(windows) {
            ErrorCode::InstanceLockForeign
        } else {
            ErrorCode::DesktopUnavailable
        };
        assert_eq!(refused.err().unwrap().code, expected);
        let failed = admitted(Err(std::io::ErrorKind::Other.into()), &mut quiet);
        assert_eq!(failed.err().unwrap().code, ErrorCode::DesktopUnavailable);
    }

    /// Holds an object under the lock name from a separate Windows PowerShell
    /// process, as another account that created it first would, until the
    /// returned process ends.
    #[cfg(windows)]
    fn squat(family: &str, object: &str) -> Running {
        const SCRIPT: &str = r#"
$ErrorActionPreference = 'Stop'
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$name = "Global\$($env:CADRUMO_SQUAT_FAMILY).desktop.$($sid.Value).lock"
$created = $false
if ($env:CADRUMO_SQUAT_OBJECT -eq 'mutex') {
    # This user may only wait on it: no full access, as when another account
    # created it and granted nothing more.
    $security = New-Object Security.AccessControl.MutexSecurity
    $security.AddAccessRule((New-Object Security.AccessControl.MutexAccessRule(
        $sid, [Security.AccessControl.MutexRights]::Synchronize,
        [Security.AccessControl.AccessControlType]::Allow)))
    $held = New-Object Threading.Mutex($false, $name, [ref]$created, $security)
} else {
    $held = New-Object Threading.EventWaitHandle($false,
        [Threading.EventResetMode]::ManualReset, $name, [ref]$created)
}
if (-not $created) { throw "the name already existed" }
[Console]::Out.WriteLine('squatting')
[Console]::Out.Flush()
[void][Console]::In.ReadLine()
$held.Dispose()
"#;
        use std::os::windows::process::CommandExt;
        let root = std::env::var_os("SystemRoot").expect("SystemRoot");
        let powershell =
            PathBuf::from(root).join(r"System32\WindowsPowerShell\v1.0\powershell.exe");
        let mut child = Running(
            Command::new(powershell)
                .args(["-NoProfile", "-NonInteractive", "-Command", SCRIPT])
                .env("CADRUMO_SQUAT_FAMILY", family)
                .env("CADRUMO_SQUAT_OBJECT", object)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::inherit())
                // The squatter never opens a console on the person's screen.
                .creation_flags(0x0800_0000)
                .spawn()
                .unwrap(),
        );
        let mut line = String::new();
        BufReader::new(child.0.stdout.take().unwrap())
            .read_line(&mut line)
            .unwrap();
        assert_eq!(line.trim(), "squatting", "the squatter did not start");
        child
    }

    /// An object another account placed under the lock name first refuses the
    /// launch as held by another account, not as a missing desktop, whether
    /// this user cannot open it fully or it is not a mutex at all.
    #[cfg(windows)]
    #[test]
    fn a_lock_name_another_account_holds_refuses_the_launch_as_foreign() {
        for object in ["mutex", "event"] {
            let family = unique_family(&format!("squat-{object}"));
            let squatter = squat(&family, object);
            let refused = admit_with(&Mode::Gui, || Ok(family.clone()))
                .err()
                .unwrap_or_else(|| panic!("{object}: the launch was admitted"));
            assert_eq!(refused.code, ErrorCode::InstanceLockForeign, "{object}");
            assert_eq!(refused.operation, Operation::Launch);
            drop(squatter);
        }
    }

    #[test]
    fn the_headless_passthrough_never_takes_or_contends_for_the_lock() {
        let family = unique_family("headless");
        let (ready, holding) = mpsc::channel();
        let (release, released) = mpsc::channel::<()>();
        let held = family.clone();
        let holder = std::thread::spawn(move || {
            let Admission::Primary(primary) = claim(&held).unwrap() else {
                panic!("expected the lock");
            };
            let count = Arc::new(AtomicUsize::new(0));
            let seen = count.clone();
            primary.activation.attach(Box::new(move || {
                seen.fetch_add(1, Ordering::SeqCst);
            }));
            ready.send(count).unwrap();
            released.recv().unwrap();
        });
        let activations = holding.recv().unwrap();
        // The passthrough never resolves the key, so it cannot reach the lock.
        for mode in [
            Mode::Cli(vec!["--version".into()]),
            Mode::Health { hold_seconds: 0 },
        ] {
            let headless = admit_with(&mode, || {
                panic!("a headless invocation resolved the lock key")
            })
            .unwrap();
            assert!(matches!(headless, Admission::Headless));
        }
        assert_eq!(activations.load(Ordering::SeqCst), 0);
        // Control: a GUI launch with the same key does contend.
        let gui = admit_with(&Mode::Gui, || Ok(family.clone())).unwrap();
        assert!(matches!(gui, Admission::Activated));
        assert_eq!(activations.load(Ordering::SeqCst), 1);
        release.send(()).unwrap();
        holder.join().unwrap();
    }

    /// Runs as a launched instance when the parent test selects a family:
    /// reports its admission, and while it holds the lock counts the
    /// activation requests until its standard input closes. Its key is the
    /// family scoped to the storage root its environment selects, as a real
    /// launch derives it.
    #[test]
    fn helper() {
        let Ok(family) = std::env::var(FAMILY_VARIABLE) else {
            return;
        };
        let patience = std::env::var(PATIENCE_VARIABLE)
            .ok()
            .and_then(|value| value.parse().ok())
            .map_or(PATIENCE, std::time::Duration::from_millis);
        let admission = admit_within(&Mode::Gui, || root_key(&family), patience);
        // A launch that ends here leaves its record, as the real host does.
        if std::env::var_os(RECORD_VARIABLE).is_some()
            && let Some((outcome, reason)) = crate::startup_outcome::of_admission(&admission)
        {
            let parent = crate::environment::Parent::current().unwrap();
            crate::startup_outcome::record(
                &parent,
                outcome,
                cadrumo_application::diagnostics::HostStage::Admission,
                reason,
            )
            .unwrap();
        }
        match admission {
            Err(error) => println!("{REPORT}error={:?}", error.code),
            Ok(Admission::Activated) => println!("{REPORT}activated"),
            Ok(Admission::OpenInOtherSession) => println!("{REPORT}other_session"),
            Ok(Admission::Headless) => panic!("a GUI launch was admitted headless"),
            Ok(Admission::Primary(_primary)) => {
                let count = Arc::new(AtomicUsize::new(0));
                let seen = count.clone();
                ACTIVATION.get().unwrap().attach(Box::new(move || {
                    seen.fetch_add(1, Ordering::SeqCst);
                }));
                // A window that is closing refuses activation and keeps the lock until
                // it has finished, as a slow shutdown does.
                let closing = std::env::var(CLOSING_VARIABLE)
                    .ok()
                    .and_then(|value| value.parse::<u64>().ok());
                if let Some(milliseconds) = closing {
                    close();
                    println!("{REPORT}primary");
                    std::thread::sleep(std::time::Duration::from_millis(milliseconds));
                    return;
                }
                println!("{REPORT}primary");
                let _ = std::io::stdin().read_to_end(&mut Vec::new());
                println!("{REPORT}activations={}", count.load(Ordering::SeqCst));
            }
        }
    }

    struct Scratch(PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    /// A launched instance that a failed assertion must not leave running.
    struct Running(std::process::Child);
    impl Drop for Running {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    fn launch(
        executable: &PathBuf,
        family: &str,
        root: &std::path::Path,
        stdin: Stdio,
    ) -> std::process::Child {
        launch_with(executable, family, root, stdin, &[])
    }

    fn launch_with(
        executable: &PathBuf,
        family: &str,
        root: &std::path::Path,
        stdin: Stdio,
        environment: &[(&str, &str)],
    ) -> std::process::Child {
        let mut command = Command::new(executable);
        command.envs(environment.iter().copied());
        command
            .args([
                "--exact",
                "shell::single_instance::tests::helper",
                "--nocapture",
                "--test-threads=1",
            ])
            .env(FAMILY_VARIABLE, family)
            .env(cadrumo_platform::ROOT_VARIABLE, root)
            .stdin(stdin)
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        // The helper instance never opens a console on the person's screen.
        #[cfg(windows)]
        std::os::windows::process::CommandExt::creation_flags(&mut command, 0x0800_0000);
        command.spawn().unwrap()
    }

    /// The helper's report on `line`. The test harness may print its own
    /// progress on the same line, before the report.
    fn report(line: &str) -> Option<&str> {
        line.rsplit_once(REPORT).map(|(_, report)| report)
    }

    fn reports(output: &[u8]) -> Vec<String> {
        String::from_utf8_lossy(output)
            .lines()
            .filter_map(|line| report(line).map(str::to_owned))
            .collect()
    }

    /// A scratch directory reached without links, since a root reached
    /// through a link is refused.
    fn scratch(label: &str) -> Scratch {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let scratch = Scratch(
            std::fs::canonicalize(std::env::temp_dir())
                .unwrap()
                .join(format!("cadrumo-{label}-{}-{nanos}", std::process::id())),
        );
        std::fs::create_dir_all(&scratch.0).unwrap();
        scratch
    }

    /// Waits for the launched holder to report that it took the lock.
    fn held(child: &mut Running) -> std::io::Lines<BufReader<std::process::ChildStdout>> {
        let mut lines = BufReader::new(child.0.stdout.take().unwrap()).lines();
        assert!(
            lines
                .by_ref()
                .map_while(|line| line.ok())
                .any(|line| report(&line) == Some("primary")),
            "the instance did not take the lock"
        );
        lines
    }

    /// Two installations of one channel at different paths on one storage
    /// root, standing in for two versions side by side: a launch of the
    /// second activates the first and exits 0, and once the first exits the
    /// second takes the lock.
    #[test]
    fn a_launch_from_another_install_path_activates_the_open_instance() {
        let scratch = scratch("instance");
        let root = scratch.0.join("storage");
        let current = std::env::current_exe().unwrap();
        let installs: Vec<PathBuf> = ["1.4.0", "2.0.1"]
            .iter()
            .map(|version| {
                let directory = scratch.0.join(version);
                std::fs::create_dir_all(&directory).unwrap();
                let executable = directory.join(current.file_name().unwrap());
                std::fs::copy(&current, &executable).unwrap();
                executable
            })
            .collect();
        let family = unique_family("installs");

        let mut first = Running(launch(&installs[0], &family, &root, Stdio::piped()));
        let lines = held(&mut first);

        let second = launch(&installs[1], &family, &root, Stdio::null())
            .wait_with_output()
            .unwrap();
        assert!(second.status.success());
        assert_eq!(reports(&second.stdout), ["activated"]);

        drop(first.0.stdin.take());
        let rest: Vec<String> = lines.map_while(|line| line.ok()).collect();
        assert!(first.0.wait().unwrap().success());
        assert!(
            rest.iter()
                .any(|line| report(line) == Some("activations=1")),
            "{rest:?}"
        );

        let after = launch(&installs[1], &family, &root, Stdio::null())
            .wait_with_output()
            .unwrap();
        assert!(after.status.success());
        assert_eq!(reports(&after.stdout), ["primary", "activations=0"]);
    }

    /// Launches on two storage roots in one session each take a lock of their
    /// own and stay independent, while a further launch on either root,
    /// through another spelling of its path, activates that root's holder only.
    #[test]
    fn launches_on_different_roots_are_independent_and_one_root_hands_off() {
        let scratch = scratch("roots");
        let current = std::env::current_exe().unwrap();
        let family = unique_family("roots");
        let first_root = scratch.0.join("first");
        let second_root = scratch.0.join("second");

        let mut first = Running(launch(&current, &family, &first_root, Stdio::piped()));
        let first_lines = held(&mut first);
        // Another root does not hand off to the open instance: it holds its own lock.
        let mut second = Running(launch(&current, &family, &second_root, Stdio::piped()));
        let second_lines = held(&mut second);

        let again = launch(
            &current,
            &family,
            &scratch.0.join("second").join("..").join("first"),
            Stdio::null(),
        )
        .wait_with_output()
        .unwrap();
        assert!(again.status.success());
        assert_eq!(reports(&again.stdout), ["activated"]);

        drop(second.0.stdin.take());
        let rest: Vec<String> = second_lines.map_while(|line| line.ok()).collect();
        assert!(second.0.wait().unwrap().success());
        assert!(
            rest.iter()
                .any(|line| report(line) == Some("activations=0")),
            "{rest:?}"
        );
        drop(first.0.stdin.take());
        let rest: Vec<String> = first_lines.map_while(|line| line.ok()).collect();
        assert!(first.0.wait().unwrap().success());
        assert!(
            rest.iter()
                .any(|line| report(line) == Some("activations=1")),
            "{rest:?}"
        );
    }

    /// The records the launches on `root` left, oldest first.
    fn startup_records(root: &std::path::Path) -> Vec<serde_json::Value> {
        let file = crate::startup_logging::Contract::current()
            .unwrap()
            .log_directory(root)
            .unwrap()
            .join(crate::startup_outcome::FILE_NAME);
        std::fs::read_to_string(file)
            .unwrap_or_default()
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect()
    }

    /// The second launch hands off to the open window and exits 0; the record it leaves
    /// names the outcome, its own process and the root only by digest.
    #[test]
    fn a_handoff_leaves_a_durable_privacy_safe_record() {
        let scratch = scratch("handoff-record");
        let root = scratch.0.join("storage");
        let current = std::env::current_exe().unwrap();
        let family = unique_family("handoff-record");
        let mut first = Running(launch(&current, &family, &root, Stdio::piped()));
        let _lines = held(&mut first);

        let second = launch_with(
            &current,
            &family,
            &root,
            Stdio::null(),
            &[(RECORD_VARIABLE, "1")],
        );
        let pid = second.id();
        let second = second.wait_with_output().unwrap();
        assert!(second.status.success());
        assert_eq!(reports(&second.stdout), ["activated"]);

        let records = startup_records(&root);
        assert_eq!(records.len(), 1, "{records:?}");
        let record = &records[0];
        assert_eq!(record["event"], "startup_outcome");
        assert_eq!(record["outcome"], "handed_off");
        assert_eq!(record["stage"], "admission");
        assert_eq!(record["reason"], serde_json::Value::Null);
        assert_eq!(record["root"], "selected");
        assert_eq!(record["pid"], pid);
        assert!(record["timestampMs"].as_u64().unwrap() > 0);
        let identity = record["rootIdentity"].as_str().unwrap();
        assert_eq!(identity.len(), 64);
        assert!(identity.bytes().all(|byte| byte.is_ascii_hexdigit()));
        let text = serde_json::to_string(record).unwrap();
        assert!(!text.contains(root.to_str().unwrap()), "{text}");
    }

    /// A holder that never releases the lock times the claim out; the launch reports the
    /// refusal and leaves a record with the typed reason.
    #[test]
    fn a_lock_timeout_leaves_a_record_with_its_reason() {
        let scratch = scratch("timeout-record");
        let root = scratch.0.join("storage");
        let current = std::env::current_exe().unwrap();
        let family = unique_family("timeout-record");
        let mut closing = Running(launch_with(
            &current,
            &family,
            &root,
            Stdio::null(),
            &[(CLOSING_VARIABLE, "30000")],
        ));
        let _lines = held(&mut closing);

        let waiting = launch_with(
            &current,
            &family,
            &root,
            Stdio::null(),
            &[(RECORD_VARIABLE, "1"), (PATIENCE_VARIABLE, "300")],
        )
        .wait_with_output()
        .unwrap();
        assert_eq!(reports(&waiting.stdout), ["error=TimedOut"]);

        let records = startup_records(&root);
        assert_eq!(records.len(), 1, "{records:?}");
        assert_eq!(records[0]["outcome"], "timed_out");
        assert_eq!(records[0]["reason"], "timed_out");
        assert_eq!(records[0]["stage"], "admission");
    }

    /// A launch during a slow close waits for the closing window to release the lock and
    /// then becomes the window, instead of giving up.
    #[test]
    fn a_relaunch_during_a_slow_close_takes_over_when_the_lock_is_released() {
        let scratch = scratch("close-relaunch");
        let root = scratch.0.join("storage");
        let current = std::env::current_exe().unwrap();
        let family = unique_family("close-relaunch");
        let mut closing = Running(launch_with(
            &current,
            &family,
            &root,
            Stdio::null(),
            &[(CLOSING_VARIABLE, "1500")],
        ));
        let _lines = held(&mut closing);

        let started = std::time::Instant::now();
        let relaunch = launch_with(
            &current,
            &family,
            &root,
            Stdio::null(),
            &[(PATIENCE_VARIABLE, "20000")],
        )
        .wait_with_output()
        .unwrap();
        assert!(relaunch.status.success());
        assert_eq!(reports(&relaunch.stdout), ["primary", "activations=0"]);
        assert!(started.elapsed() < std::time::Duration::from_secs(20));
    }

    #[test]
    fn the_relaunch_patience_covers_the_shutdown_and_drain_budgets() {
        use cadrumo_application::shutdown::{RUNTIME_DRAIN_BOUND, SUPERVISOR_CLOSE_BOUND};
        assert!(PATIENCE >= SUPERVISOR_CLOSE_BOUND + RUNTIME_DRAIN_BOUND);
    }
}
