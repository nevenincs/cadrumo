//! The local AI server, supervised for the manager's whole life.
//!
//! The component engine installs the local AI program; the manager runs the one server
//! every surface and profile uses. While the program is set up the server listens on the
//! fixed loopback address the package's environment declaration gives it, is restarted
//! after a crash, is stopped and held off while an engine replaces or removes the
//! program, and is stopped when the manager quits, closes, is uninstalled or its session
//! ends. On Windows each server process is created suspended and placed in a
//! kill-on-close job of its own before any of its code runs, so nothing it starts
//! outlives its stop. On Linux and macOS each server is created into a process group of
//! its own whose guardian ends the whole group once the server has stopped or the manager
//! has ended (see `cadrumo_platform::process_scope`); what the server starts stays in that
//! group unless it moves itself out.
//!
//! The supervision runs on a thread of its own, because starting or stopping a server
//! can take seconds that the manager's own events must not wait for. The manager only
//! asks it to stop, resume or retry; dropping the host stops the server and waits for the
//! thread, and should the manager end without that, crashing or killed, the job or the
//! group's guardian ends the server with it.
//!
//! The server is installation-wide public software outside custody: the manager hands it
//! no profile, credential or tax data. A copy of the program installed outside Cadrumo is
//! never started, stopped or changed.

use crate::contract::{COMPONENT_PINS, LOCAL_AI_ADDRESS};
#[cfg(unix)]
use cadrumo_application::provisioning::local_ai::program::ProcessGroup;
use cadrumo_application::provisioning::{
    items::Locations,
    local_ai::{
        program::{Containment, Program},
        supervision::{ServerState, ServerSupervisor},
    },
    pins::{ComponentPins, Platform},
    proxy::ProxySettings,
};
use std::{
    net::SocketAddr,
    path::Path,
    sync::{
        Arc, Condvar, Mutex,
        mpsc::{self, RecvTimeoutError},
    },
    thread::JoinHandle,
    time::{Duration, Instant},
};

/// How often the supervision looks at the server between scheduled restarts: for a
/// crash, a requested program change, or a program newly set up.
pub const PACE: Duration = Duration::from_secs(1);

/// The fixed address the package declares for the local AI server.
pub fn server_address() -> Option<SocketAddr> {
    LOCAL_AI_ADDRESS
        .parse::<SocketAddr>()
        .ok()
        .filter(|address| address.ip().is_loopback())
}

enum Command {
    Stop,
    Resume,
    Retry,
    Shutdown,
}

/// The last state the supervision published, and how many looks it has taken.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Published {
    pub state: ServerState,
    pub looks: u64,
}

type Shared = Arc<(Mutex<Published>, Condvar)>;

/// The manager's local AI server, supervised on its own thread.
pub struct LocalAiHost {
    commands: mpsc::Sender<Command>,
    published: Shared,
    stop_requested: bool,
    worker: Option<JoinHandle<()>>,
}

impl LocalAiHost {
    /// The server of the package at `package_root` for the components under
    /// `storage_root`; `None` when the build carries no local AI program for this
    /// platform or its pins cannot be read, so there is nothing to run.
    pub fn for_package(package_root: &Path, storage_root: &Path) -> Option<Self> {
        let pins = ComponentPins::load(&package_root.join(COMPONENT_PINS))
            .ok()?
            .program?;
        let program =
            Program::new(&pins, Platform::current()?, Locations::under(storage_root)).ok()??;
        // A proxy setting the engine cannot use leaves the server to reach the registry
        // directly, where the engine's own preflight reports the network.
        let proxy = ProxySettings::from_settings(|name| std::env::var(name).ok())
            .ok()
            .flatten();
        let supervisor = ServerSupervisor::new(
            program,
            server_address()?,
            containment(),
            Box::new(|name: &str| std::env::var_os(name)),
            proxy,
        )
        .ok()?;
        Self::supervise(supervisor).ok()
    }

    /// Runs `supervisor` on a thread of its own until the host is dropped.
    pub fn supervise(supervisor: ServerSupervisor) -> std::io::Result<Self> {
        let (commands, received) = mpsc::channel();
        let published: Shared = Arc::new((
            Mutex::new(Published {
                state: supervisor.state(),
                looks: 0,
            }),
            Condvar::new(),
        ));
        let shared = Arc::clone(&published);
        let worker = std::thread::Builder::new()
            .name("cadrumo-local-ai".into())
            .spawn(move || run(supervisor, &received, &shared))?;
        Ok(Self {
            commands,
            published,
            stop_requested: false,
            worker: Some(worker),
        })
    }

    /// The last published state.
    pub fn published(&self) -> Published {
        *lock(&self.published.0)
    }

    /// Waits until the supervision publishes a state for which `until` holds.
    pub fn wait_until(&self, until: impl Fn(&Published) -> bool) -> Published {
        let (published, changed) = &*self.published;
        let mut current = lock(published);
        while !until(&current) {
            current = changed
                .wait(current)
                .unwrap_or_else(|error| error.into_inner());
        }
        *current
    }

    /// Stops the server and starts nothing until [`Self::resume`]. Asked once; the stop
    /// itself runs on the supervision's thread.
    pub fn stop(&mut self) {
        if !self.stop_requested {
            self.stop_requested = true;
            let _ = self.commands.send(Command::Stop);
        }
    }

    /// Supervises again after a stop that did not end the manager.
    pub fn resume(&mut self) {
        self.stop_requested = false;
        let _ = self.commands.send(Command::Resume);
    }

    /// Forgets earlier crashes after supervision failed, at the person's Retry.
    pub fn retry(&self) {
        let _ = self.commands.send(Command::Retry);
    }
}

impl Drop for LocalAiHost {
    fn drop(&mut self) {
        let _ = self.commands.send(Command::Shutdown);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}

fn lock(published: &Mutex<Published>) -> std::sync::MutexGuard<'_, Published> {
    published.lock().unwrap_or_else(|error| error.into_inner())
}

fn publish(shared: &Shared, state: ServerState, looked: bool) {
    let (published, changed) = &**shared;
    let mut current = lock(published);
    current.state = state;
    current.looks += u64::from(looked);
    changed.notify_all();
}

/// Looks at the server whenever a look is due and acts on each command as it arrives.
fn run(mut supervisor: ServerSupervisor, commands: &mpsc::Receiver<Command>, shared: &Shared) {
    let mut next = Instant::now();
    loop {
        let now = Instant::now();
        let idle = matches!(
            supervisor.state(),
            ServerState::Stopped | ServerState::Failed
        );
        if !idle && now >= next {
            let state = supervisor.poll(now);
            let paced = now + PACE;
            next = supervisor.next_due().map_or(paced, |due| due.min(paced));
            publish(shared, state, true);
        }
        let idle = matches!(
            supervisor.state(),
            ServerState::Stopped | ServerState::Failed
        );
        let command = if idle {
            commands.recv().map_err(|_| RecvTimeoutError::Disconnected)
        } else {
            commands.recv_timeout(next.saturating_duration_since(Instant::now()))
        };
        match command {
            Ok(Command::Stop) => {
                supervisor.stop();
                publish(shared, supervisor.state(), false);
            }
            Ok(Command::Resume) => {
                supervisor.resume();
                next = Instant::now();
            }
            Ok(Command::Retry) => {
                supervisor.retry();
                next = Instant::now();
            }
            Ok(Command::Shutdown) | Err(RecvTimeoutError::Disconnected) => {
                supervisor.stop();
                publish(shared, supervisor.state(), false);
                return;
            }
            Err(RecvTimeoutError::Timeout) => {}
        }
    }
}

#[cfg(windows)]
fn containment() -> Box<dyn Containment + Send> {
    Box::new(JobContainment)
}

#[cfg(unix)]
fn containment() -> Box<dyn Containment + Send> {
    Box::new(GroupContainment)
}

/// One kill-on-close job per server process, entered before the process runs.
#[cfg(windows)]
pub struct JobContainment;

#[cfg(windows)]
impl Containment for JobContainment {
    fn creation_flags(&self) -> u32 {
        crate::process_job::CREATE_SUSPENDED
    }

    fn contain(&self, child: &std::process::Child) -> std::io::Result<Box<dyn Send>> {
        let job = crate::process_job::ProcessJob::new()?;
        job.adopt_suspended(child)?;
        Ok(Box::new(job))
    }
}

/// One process group per server process, whose guardian ends it with its owner.
#[cfg(unix)]
pub struct GroupContainment;

#[cfg(unix)]
impl Containment for GroupContainment {
    fn open_group(&self) -> std::io::Result<Option<ProcessGroup>> {
        let scope = cadrumo_platform::process_scope::ProcessScope::new()?;
        Ok(Some(ProcessGroup {
            id: scope.group(),
            guard: Box::new(scope),
        }))
    }

    fn contain(&self, _: &std::process::Child) -> std::io::Result<Box<dyn Send>> {
        Ok(Box::new(()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs, path::PathBuf};

    /// A folder of this test's own under the temporary folder, removed when dropped.
    struct Scratch(PathBuf);

    impl Scratch {
        fn new(name: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "cadrumo-manager-local-ai-{name}-{}",
                std::process::id()
            ));
            let _ = fs::remove_dir_all(&path);
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }

        fn path(&self) -> &Path {
            &self.0
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn the_server_address_is_the_declared_loopback_address_and_never_the_publishers_port() {
        let address = server_address().expect("the contract declares a loopback address");
        assert!(address.ip().is_loopback());
        assert_ne!(address.port(), 11434);
        assert!((1024..32768).contains(&address.port()));
    }

    fn package_with_pins(package: &Path) {
        let checkout = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(Path::parent)
            .unwrap();
        let pins = package.join(COMPONENT_PINS);
        fs::create_dir_all(&pins).unwrap();
        for table in ["local_ai_program.toml", "local_ai_models.toml"] {
            fs::copy(
                checkout.join("src/cadrumo/_data/dependencies").join(table),
                pins.join(table),
            )
            .unwrap();
        }
    }

    #[test]
    fn a_package_without_a_program_for_this_platform_runs_no_server() {
        let root = Scratch::new("absent");
        assert!(
            LocalAiHost::for_package(&root.path().join("package"), &root.path().join("state"))
                .is_none()
        );
    }

    #[test]
    fn a_program_not_set_up_is_looked_at_on_its_own_thread_until_the_manager_stops() {
        let root = Scratch::new("paced");
        let package = root.path().join("package");
        package_with_pins(&package);
        let Some(mut host) = LocalAiHost::for_package(&package, &root.path().join("state")) else {
            // The pins carry no archive for this platform.
            assert!(Platform::current().is_none());
            return;
        };
        let first = host.wait_until(|published| published.looks >= 1);
        assert_eq!(first.state, ServerState::NotSetUp);
        host.stop();
        host.stop();
        let stopped = host.wait_until(|published| published.state == ServerState::Stopped);
        host.resume();
        let resumed = host.wait_until(|published| published.looks > stopped.looks);
        assert_eq!(resumed.state, ServerState::NotSetUp);
        drop(host);
        assert!(
            !root
                .path()
                .join("state/components/ollama/server.json")
                .exists(),
            "nothing ran"
        );
    }

    const HELPER_RUNNING: &str = "contained helper running";

    /// The child-process mode: a stand-in that runs until it is ended from outside.
    #[test]
    fn contained_process_helper() {
        if std::env::var_os("CADRUMO_MANAGER_CONTAINED_HELPER").is_none() {
            return;
        }
        let mut sink = Vec::new();
        let _ = std::io::Read::read_to_end(&mut std::io::stdin(), &mut sink);
        println!("{HELPER_RUNNING}");
        loop {
            std::thread::park();
        }
    }

    #[cfg(windows)]
    #[test]
    fn a_contained_server_ends_with_its_job_however_its_owner_lets_go() {
        use std::os::windows::process::CommandExt;
        use std::process::{Command, Stdio};
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let containment = JobContainment;
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "supervision::local_ai::tests::contained_process_helper",
                "--nocapture",
            ])
            .env("CADRUMO_MANAGER_CONTAINED_HELPER", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW | containment.creation_flags())
            .spawn()
            .unwrap();
        let guard = containment.contain(&child).unwrap();
        // Its standard input closes, which this stand-in for a hung server outlives.
        drop(child.stdin.take());
        let mut announced = String::new();
        let mut stdout = std::io::BufReader::new(child.stdout.take().unwrap());
        while !announced.contains(HELPER_RUNNING) {
            let mut line = String::new();
            assert_ne!(
                std::io::BufRead::read_line(&mut stdout, &mut line).unwrap(),
                0,
                "the helper ended before it ran: {announced}"
            );
            announced.push_str(&line);
        }
        assert!(
            matches!(child.try_wait(), Ok(None)),
            "it runs once contained"
        );
        // It never ends by itself, so its end is the job's doing.
        drop(guard);
        child.wait().unwrap();
    }

    /// A stand-in for a hung server that also started a runner: each stops itself again
    /// whenever it is resumed and ignores the hangup an orphaned group is sent, so only a
    /// kill ends either. Each says which it is on its standard output.
    #[cfg(unix)]
    const UNENDING: &str = "trap '' HUP\n\
                            if [ \"$1\" = server ]; then /bin/sh -c \"$0\" \"$0\" runner & fi\n\
                            echo \"$1\"\n\
                            while :; do kill -s STOP $$; done\n";

    #[cfg(unix)]
    fn unending_server(group: i32, stdout: std::process::Stdio) -> std::process::Command {
        use std::os::unix::process::CommandExt;
        let mut command = std::process::Command::new("/bin/sh");
        command
            .args(["-c", UNENDING, UNENDING, "server"])
            .stdin(std::process::Stdio::null())
            .stdout(stdout)
            .stderr(std::process::Stdio::null())
            .process_group(group);
        command
    }

    /// Reads `stdout` until both the server and its runner have said they run.
    #[cfg(unix)]
    fn both_running(stdout: &mut impl std::io::BufRead) {
        let mut seen = String::new();
        while !(seen.contains("server\n") && seen.contains("runner\n")) {
            let mut line = String::new();
            assert_ne!(
                stdout.read_line(&mut line).unwrap(),
                0,
                "the stand-ins ended before they ran: {seen}"
            );
            seen.push_str(&line);
        }
    }

    /// Reads `stdout` to its end, which comes only once every process holding it ended.
    #[cfg(unix)]
    fn every_holder_ended(stdout: &mut impl std::io::BufRead) {
        let mut rest = Vec::new();
        std::io::Read::read_to_end(stdout, &mut rest).unwrap();
    }

    #[cfg(unix)]
    const OWNER_HELPER: &str = "CADRUMO_MANAGER_GROUP_OWNER";

    /// The child-process mode: a manager that contains a server as the supervision does,
    /// holds it until its standard input closes, then exits without letting it go.
    #[cfg(unix)]
    #[test]
    fn group_owner_helper() {
        if std::env::var_os(OWNER_HELPER).is_none() {
            return;
        }
        let containment = GroupContainment;
        let group = containment.open_group().unwrap().unwrap();
        let server = unending_server(group.id, std::process::Stdio::inherit())
            .spawn()
            .unwrap();
        let _guard = containment.contain(&server).unwrap();
        let mut sink = Vec::new();
        let _ = std::io::Read::read_to_end(&mut std::io::stdin(), &mut sink);
        // Exiting runs no destructor, so neither the server nor its group is let go.
        std::process::exit(0);
    }

    /// Starts the owner helper, whose standard output the stand-ins it starts share.
    #[cfg(unix)]
    fn owner() -> std::process::Child {
        use std::process::{Command, Stdio};
        Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "supervision::local_ai::tests::group_owner_helper",
                "--nocapture",
                "--test-threads=1",
            ])
            .env(OWNER_HELPER, "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .unwrap()
    }

    #[cfg(unix)]
    #[test]
    fn a_contained_server_and_its_runner_end_when_the_manager_is_killed() {
        let mut manager = owner();
        let mut stdout = std::io::BufReader::new(manager.stdout.take().unwrap());
        both_running(&mut stdout);
        manager.kill().unwrap();
        manager.wait().unwrap();
        every_holder_ended(&mut stdout);
    }

    #[cfg(unix)]
    #[test]
    fn a_contained_server_and_its_runner_end_when_the_manager_exits_without_stopping_it() {
        let mut manager = owner();
        let mut stdout = std::io::BufReader::new(manager.stdout.take().unwrap());
        both_running(&mut stdout);
        drop(manager.stdin.take());
        assert!(manager.wait().unwrap().success());
        every_holder_ended(&mut stdout);
    }

    #[cfg(unix)]
    #[test]
    fn what_a_stopped_server_started_ends_when_its_group_is_let_go() {
        let containment = GroupContainment;
        let group = containment.open_group().unwrap().unwrap();
        let (reader, writer) = std::io::pipe().unwrap();
        let mut server = unending_server(group.id, writer.into()).spawn().unwrap();
        let guard = containment.contain(&server).unwrap();
        let mut stdout = std::io::BufReader::new(reader);
        both_running(&mut stdout);
        // The supervision ends and reaps the server first, as its stop does; the runner
        // outlives it until the group is let go.
        server.kill().unwrap();
        server.wait().unwrap();
        drop(guard);
        drop(group);
        every_holder_ended(&mut stdout);
    }
}
