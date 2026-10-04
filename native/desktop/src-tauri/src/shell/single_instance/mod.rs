//! One desktop window per user, across installed versions and paths.
//!
//! The lock key is the application identifier of the generated Tauri
//! configuration: the product identity family with its channel suffix.
//! Neither the install path nor the version enters it, so every installed
//! version of one channel shares the lock. A second GUI launch hands
//! activation to the open window and exits; a newer version launched while
//! an older window is open activates that window, and the switch completes
//! when the user closes it. The headless CLI passthrough never takes or
//! contends for the lock.
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
#[cfg(target_os = "linux")]
mod linux;
#[cfg(target_os = "linux")]
use linux::{InstanceClaim, InstanceLock, claim_instance};
/// No other platform runs the GUI, so no lock exists there.
#[cfg(not(any(windows, target_os = "linux")))]
type InstanceLock = std::convert::Infallible;

/// How long a second launch waits for the open window to acknowledge it, or
/// for a closing one to release the lock.
#[cfg(any(windows, target_os = "linux"))]
const PATIENCE: std::time::Duration = std::time::Duration::from_secs(10);

/// The generated configuration the Tauri context is compiled from, read here
/// before the context exists so the claim precedes all per-user state.
const CONFIGURATION: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/tauri.conf.json"));

/// What the launch may do once its mode is known.
pub enum Admission {
    /// The CLI passthrough, which runs without the lock.
    Headless,
    /// This launch holds the lock and opens the window.
    Primary(Primary),
    /// The open window accepted activation; this launch exits with 0.
    Activated,
}

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
    #[cfg(any(windows, target_os = "linux", test))]
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

/// The lock key of a generated configuration: its application identifier,
/// which carries the identity family and channel. Nothing else in the
/// configuration enters it.
fn family_of(configuration: &str) -> Result<String> {
    serde_json::from_str::<Identity>(configuration)
        .map(|identity| identity.identifier)
        .map_err(|e| invalid().caused_by(e))
}

fn family() -> Result<String> {
    family_of(CONFIGURATION)
}

/// Admits a launch in `mode`. The GUI claims the lock before any per-user
/// state is opened; the CLI passthrough returns at once.
pub fn admit(mode: &Mode) -> Result<Admission> {
    admit_with(mode, family)
}

fn admit_with(mode: &Mode, family: impl FnOnce() -> Result<String>) -> Result<Admission> {
    if let Mode::Cli(_) = mode {
        return Ok(Admission::Headless);
    }
    let admission = claim(&family()?)?;
    if let Admission::Primary(primary) = &admission
        && ACTIVATION.set(primary.activation.clone()).is_err()
    {
        return Err(invalid());
    }
    Ok(admission)
}

#[cfg(any(windows, target_os = "linux"))]
fn claim(family: &str) -> Result<Admission> {
    let unavailable = || ApplicationError::new(ErrorCode::DesktopUnavailable, Operation::Launch);
    match claim_instance(family, PATIENCE) {
        Ok(InstanceClaim::Activated) => Ok(Admission::Activated),
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
        Err(e) => Err(unavailable().caused_by(e)),
    }
}

#[cfg(not(any(windows, target_os = "linux")))]
fn claim(_family: &str) -> Result<Admission> {
    Err(ApplicationError::new(
        ErrorCode::UnsupportedPlatform,
        Operation::Launch,
    ))
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
    if !main {
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
        let headless = admit_with(&Mode::Cli(vec!["--version".into()]), || {
            panic!("the headless passthrough resolved the lock key")
        })
        .unwrap();
        assert!(matches!(headless, Admission::Headless));
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
    /// activation requests until its standard input closes.
    #[test]
    fn helper() {
        let Ok(family) = std::env::var(FAMILY_VARIABLE) else {
            return;
        };
        match admit_with(&Mode::Gui, || Ok(family)).unwrap() {
            Admission::Activated => println!("{REPORT}activated"),
            Admission::Headless => panic!("a GUI launch was admitted headless"),
            Admission::Primary(_primary) => {
                let count = Arc::new(AtomicUsize::new(0));
                let seen = count.clone();
                ACTIVATION.get().unwrap().attach(Box::new(move || {
                    seen.fetch_add(1, Ordering::SeqCst);
                }));
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

    fn launch(executable: &PathBuf, family: &str, stdin: Stdio) -> std::process::Child {
        Command::new(executable)
            .args([
                "--exact",
                "shell::single_instance::tests::helper",
                "--nocapture",
                "--test-threads=1",
            ])
            .env(FAMILY_VARIABLE, family)
            .stdin(stdin)
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .unwrap()
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

    /// Two installations of one channel at different paths, standing in for
    /// two versions side by side: a launch of the second activates the first
    /// and exits 0, and once the first exits the second takes the lock.
    #[test]
    fn a_launch_from_another_install_path_activates_the_open_instance() {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let scratch = Scratch(
            std::env::temp_dir().join(format!("cadrumo-instance-{}-{nanos}", std::process::id())),
        );
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

        let mut first = Running(launch(&installs[0], &family, Stdio::piped()));
        let mut lines = BufReader::new(first.0.stdout.take().unwrap()).lines();
        assert!(
            lines
                .by_ref()
                .map_while(|line| line.ok())
                .any(|line| report(&line) == Some("primary")),
            "the first installation did not take the lock"
        );

        let second = launch(&installs[1], &family, Stdio::null())
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

        let after = launch(&installs[1], &family, Stdio::null())
            .wait_with_output()
            .unwrap();
        assert!(after.status.success());
        assert_eq!(reports(&after.stdout), ["primary", "activations=0"]);
    }
}
