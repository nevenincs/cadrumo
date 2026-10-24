//! The local AI program: the publisher's portable archive for this platform, installed
//! into the component store under `components/ollama` and run only as the engine's own
//! child.
//!
//! Each pinned version lives in its own folder under `versions`, activated by one pointer
//! as the component store does for every component. The server the engine starts keeps
//! its models in the installation's models folder and its home, settings and temporary
//! files under `components/ollama/home`, listens on a loopback port chosen at start, and
//! is stopped before its version is replaced or removed. While it runs, `server.json`
//! beside the versions names its address for the readers that use it.
//!
//! The server inherits the engine's containment: it is started without a console window
//! and without leaving the engine's job, so an owner that hosts the engine in a
//! kill-on-close job ends the server with it. On an orderly exit the engine unloads any
//! model the server holds, which ends the server's own runner processes, and then ends
//! the server. A copy installed outside Cadrumo is found and reported, never started,
//! changed or removed.
//!
//! Archive bounds were measured on the 0.40.10 archives by streaming each one through its
//! decompressor and summing its members, with each link counted again at its target's
//! size, as extraction places it:
//!
//! | platform    | archive bytes | unpacked bytes | ratio | members |
//! | ----------- | ------------- | -------------- | ----- | ------- |
//! | win-x64     | 1 586 229 413 | 2 230 768 655  | 1.41  | 80      |
//! | linux-x64   | 1 509 264 197 | 5 001 030 082  | 3.31  | 80      |
//! | linux-arm64 | 1 564 567 595 | 3 819 535 364  | 2.44  | 51      |
//! | mac-*       |   181 123 017 |   610 445 869  | 3.37  | 59      |
//!
//! A program archive may unpack to six times its pinned size, about 1.8 times the largest
//! measured ratio, and hold 1024 members, over twelve times the most measured.

use super::{LocalAiError, loopback::Loopback};
use crate::{
    component::{ActiveComponent, Artifact, ComponentStore, QuickInspection},
    error::Error,
    filesystem,
    package::Readiness,
    provisioning::{
        failure::FailureCategory,
        items::{Destination, Locations, PROGRAM_PART},
        pins::{Platform, ProgramPins},
        plan::PlanPart,
        proxy::ProxySettings,
        state::{Observation, StaleReason},
        transfer::Transfer,
    },
    value::HostName,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    ffi::{OsStr, OsString},
    fs,
    io::{BufRead, BufReader, Read},
    net::{Ipv4Addr, SocketAddr, TcpListener},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::mpsc,
    time::Duration,
};

/// How many bytes a program archive may unpack to for each byte it downloads.
pub const UNPACKED_PER_DOWNLOADED_BYTE: u64 = 6;
/// The most members a program archive may hold.
pub const MAX_ARCHIVE_ENTRIES: usize = 1024;
/// The component store's bound on any component's unpacked size.
const STORE_UNPACKED_LIMIT: u64 = 32 * 1024 * 1024 * 1024;
/// Bound for the server to announce that it listens. Exceeding it ends the server.
pub const START_BUDGET: Duration = Duration::from_secs(30);
/// What the program writes on standard error once it accepts connections.
const LISTENING: &str = "Listening on ";
/// The longest standard-error line the engine reads at once.
const LOG_LINE_LIMIT: u64 = 64 * 1024;
/// The running server's record beside the versions.
pub const SERVER_RECORD: &str = "server.json";
const SERVER_RECORD_LIMIT: u64 = 64 * 1024;
/// Windows `CREATE_NO_WINDOW`: the server gets no console window of its own.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// The operating system settings a server needs and is given from the engine's own
/// environment; everything else it is given is set by the engine.
#[cfg(windows)]
const PASSED_THROUGH: &[&str] = &[
    "SystemRoot",
    "SystemDrive",
    "windir",
    "ComSpec",
    "PATH",
    "PATHEXT",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
];
#[cfg(not(windows))]
const PASSED_THROUGH: &[&str] = &["PATH", "LANG", "LC_ALL"];

/// The unpacked-size and member bounds for a program archive of `download_bytes`.
pub fn archive_limits(download_bytes: u64) -> (u64, usize) {
    (
        download_bytes
            .saturating_mul(UNPACKED_PER_DOWNLOADED_BYTE)
            .min(STORE_UNPACKED_LIMIT),
        MAX_ARCHIVE_ENTRIES,
    )
}

/// The record of a server the engine started, read by the programs that use it.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ServerRecord {
    pub schema: u32,
    /// The loopback `host:port` the server answers on.
    pub address: String,
    pub version: String,
    pub executable: PathBuf,
    pub models: PathBuf,
    pub process_id: u32,
}

impl ServerRecord {
    /// The record under `programs`, when one is there and readable.
    pub fn read(programs: &Path) -> Option<Self> {
        let bytes =
            filesystem::bounded_bytes(&programs.join(SERVER_RECORD), SERVER_RECORD_LIMIT).ok()?;
        serde_json::from_slice::<Self>(&bytes)
            .ok()
            .filter(|record| record.schema == 1)
    }

    fn loopback(&self) -> Option<Loopback> {
        Loopback::new(self.address.parse().ok()?).ok()
    }
}

/// Everything one server start runs: the program, its arguments and its whole
/// environment, never merged with the engine's.
#[derive(Clone, Debug)]
pub struct ServeCommand {
    pub executable: PathBuf,
    pub arguments: Vec<OsString>,
    pub environment: BTreeMap<OsString, OsString>,
    pub working_directory: PathBuf,
    pub address: SocketAddr,
}

/// A server the engine started. Dropping it stops it.
#[derive(Debug)]
pub struct Server {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    loopback: Loopback,
    version: String,
    executable: PathBuf,
    record: PathBuf,
}

impl Server {
    pub fn address(&self) -> SocketAddr {
        self.loopback.address()
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    pub fn executable(&self) -> &Path {
        &self.executable
    }

    pub fn process_id(&self) -> Option<u32> {
        self.child.as_ref().map(Child::id)
    }

    pub fn loopback(&self) -> Loopback {
        self.loopback
    }

    /// A server the test process answers for itself at `address`, with no child.
    #[cfg(test)]
    pub(crate) fn attached(address: SocketAddr, version: &str) -> Self {
        Self {
            child: None,
            stdin: None,
            loopback: Loopback::new(address).unwrap(),
            version: version.to_owned(),
            executable: PathBuf::new(),
            record: PathBuf::new(),
        }
    }

    /// Starts `command` and waits for the program to announce that it listens, then for
    /// it to answer with `version`. A program that exits, stays silent past
    /// [`START_BUDGET`] or answers otherwise is ended and reads `program_not_running`.
    fn spawn(command: ServeCommand, version: &str, record: PathBuf) -> Result<Self, LocalAiError> {
        let mut process = Command::new(&command.executable);
        process
            .args(&command.arguments)
            .current_dir(&command.working_directory)
            .env_clear()
            .envs(&command.environment)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            process.creation_flags(CREATE_NO_WINDOW);
        }
        let mut child = crate::process::creation::run(|| process.spawn())
            .map_err(|_| LocalAiError::Failed(FailureCategory::ProgramNotRunning))?;
        let stdin = child.stdin.take();
        let mut server = Self {
            child: Some(child),
            stdin,
            loopback: Loopback::new(command.address)?,
            version: version.to_owned(),
            executable: command.executable,
            record,
        };
        let announced = server.announced();
        let answered = announced
            && server
                .answers_version()
                .is_some_and(|found| found == version);
        if !answered {
            server.halt();
            return Err(LocalAiError::Failed(FailureCategory::ProgramNotRunning));
        }
        Ok(server)
    }

    /// Reads the program's standard error on a thread of its own until it announces that
    /// it listens, it exits, or the start budget ends; the thread then keeps reading and
    /// discarding, so the program never blocks on a full pipe.
    fn announced(&mut self) -> bool {
        let Some(stderr) = self.child.as_mut().and_then(|child| child.stderr.take()) else {
            return false;
        };
        let (sender, receiver) = mpsc::channel::<bool>();
        let reader = std::thread::Builder::new()
            .name("cadrumo-local-ai-log".into())
            .spawn(move || {
                let mut reader = BufReader::new(stderr);
                let mut waiting = Some(sender);
                let mut line = Vec::new();
                loop {
                    line.clear();
                    match (&mut reader)
                        .take(LOG_LINE_LIMIT)
                        .read_until(b'\n', &mut line)
                    {
                        Ok(0) | Err(_) => break,
                        Ok(_) => {
                            let listening = line
                                .windows(LISTENING.len())
                                .any(|window| window == LISTENING.as_bytes());
                            if listening && let Some(sender) = waiting.take() {
                                let _ = sender.send(true);
                            }
                        }
                    }
                }
            });
        if reader.is_err() {
            return false;
        }
        receiver.recv_timeout(START_BUDGET).unwrap_or(false)
    }

    /// The version the server reports, when it answers.
    fn answers_version(&self) -> Option<String> {
        let (status, body) = self.loopback.get("/api/version").ok()?;
        if status != 200 {
            return None;
        }
        let value: serde_json::Value = serde_json::from_slice(&body).ok()?;
        value["version"].as_str().map(str::to_owned)
    }

    /// Asks the server to unload every model it holds, which ends its runners, and then
    /// ends the server and removes its record. Safe to call more than once.
    fn halt(&mut self) {
        let Some(mut child) = self.child.take() else {
            return;
        };
        if matches!(child.try_wait(), Ok(None)) {
            unload_all(self.loopback);
        }
        drop(self.stdin.take());
        let _ = child.kill();
        let _ = child.wait();
        if ServerRecord::read(self.record.parent().unwrap_or(Path::new("")))
            .is_some_and(|record| record.process_id == child.id())
        {
            let _ = fs::remove_file(&self.record);
        }
    }
}

impl Drop for Server {
    fn drop(&mut self) {
        self.halt();
    }
}

/// Unloads every model a server reports loaded; a server that does not answer is left
/// to the termination that follows.
fn unload_all(loopback: Loopback) {
    let Ok((200, body)) = loopback.get("/api/ps") else {
        return;
    };
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(&body) else {
        return;
    };
    let names: Vec<String> = value["models"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|model| model["name"].as_str().map(str::to_owned))
        .collect();
    for name in names {
        let request = serde_json::json!({ "model": name, "keep_alive": 0 });
        let _ = loopback.post("/api/generate", request.to_string().as_bytes());
    }
}

/// What a test starts in the program's place: its arguments and the environment it adds.
#[cfg(test)]
pub(crate) struct ServeOverride {
    pub arguments: Vec<OsString>,
    pub environment: Vec<(OsString, OsString)>,
}

/// The pinned local AI program on this platform, where it is installed, and the server
/// this engine runs from it.
pub struct Program {
    store: ComponentStore,
    artifact: Artifact,
    version: String,
    hosts: Vec<HostName>,
    locations: Locations,
    server: Option<Server>,
    /// The arguments and extra environment a test runs its stand-in program with.
    #[cfg(test)]
    pub(crate) serve_override: Option<ServeOverride>,
}

impl Program {
    /// The program the pins name for `platform`, installed under `locations`; `None` when
    /// the pins carry no archive for it, so the program is not in this build.
    pub fn new(
        pins: &ProgramPins,
        platform: Platform,
        locations: Locations,
    ) -> Result<Option<Self>, Error> {
        let Some(pin) = pins.for_platform(platform) else {
            return Ok(None);
        };
        let (root, id) = match (
            locations.programs.parent(),
            locations.programs.file_name().and_then(OsStr::to_str),
        ) {
            (Some(root), Some(id)) => (root.to_path_buf(), id.to_owned()),
            _ => return Err(Error::Invalid("local AI program folder".into())),
        };
        let (max_unpacked_bytes, max_entries) = archive_limits(pin.download_bytes);
        Ok(Some(Self {
            store: ComponentStore::new(root, platform.as_str().into())?,
            artifact: Artifact {
                id,
                revision: pins.version.clone(),
                target: platform.as_str().into(),
                sha256: pin.sha256.clone(),
                archive_bytes: pin.download_bytes,
                max_unpacked_bytes,
                max_entries,
                executable: pin.executable.clone(),
                url: Some(pin.url.to_string()),
                format: pin.format,
            },
            version: pins.version.clone(),
            hosts: pins.hosts.iter().cloned().collect(),
            locations,
            server: None,
            #[cfg(test)]
            serve_override: None,
        }))
    }

    pub fn artifact(&self) -> &Artifact {
        &self.artifact
    }

    pub fn version(&self) -> &str {
        &self.version
    }

    pub fn locations(&self) -> &Locations {
        &self.locations
    }

    /// The program's part of the local AI plan: the pinned archive, from the pinned
    /// hosts, into the program's own folder, with nothing installed outside Cadrumo.
    pub fn plan_part(&self) -> PlanPart {
        PlanPart {
            part_id: PROGRAM_PART.into(),
            download_bytes: Some(self.artifact.archive_bytes),
            source_hosts: self.hosts.clone(),
            destination: Some(Destination::LocalAiProgram),
            installs_outside_program: false,
            target_version: Some(self.version.clone()),
            advisories: Vec::new(),
        }
    }

    /// The quick check: the active version, its receipt and its executable's bytes, with
    /// no network and no start.
    pub fn observe_quick(&self) -> Observation {
        match self.store.inspect_quick(&self.artifact) {
            Ok(QuickInspection::Active(_)) => Observation::Present { note: None },
            Ok(QuickInspection::Other { .. }) => Observation::Differs {
                stale: StaleReason::ProgramTooOld,
                note: None,
            },
            Ok(QuickInspection::Missing) => Observation::Absent,
            Ok(QuickInspection::Damaged) => Observation::Failed(FailureCategory::DamagedDownload),
            Err(_) => Observation::Unreadable,
        }
    }

    /// The full check: every installed file against its receipt, then a server started
    /// from it that answers with the pinned version. The server keeps running.
    pub fn observe_full(
        &mut self,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Observation {
        let quick = self.observe_quick();
        if quick != (Observation::Present { note: None }) {
            return quick;
        }
        match self.store.inspect(&self.artifact) {
            Ok(inspection) if matches!(inspection.readiness, Readiness::Ready) => {}
            Ok(_) => return Observation::Failed(FailureCategory::DamagedDownload),
            Err(_) => return Observation::Unreadable,
        }
        match self.start(ambient, proxy) {
            Ok(_) => Observation::Present { note: None },
            Err(error) => Observation::Failed(error.category()),
        }
    }

    /// Downloads and activates the pinned version unless it is already active, stopping
    /// the server this engine runs first so no version is replaced under it.
    pub fn install(
        &mut self,
        transfer: &mut Transfer<'_>,
    ) -> Result<ActiveComponent, LocalAiError> {
        if let QuickInspection::Active(active) = self.store.inspect_quick(&self.artifact)? {
            return Ok(active);
        }
        self.stop();
        Ok(self.store.download_and_activate(&self.artifact, transfer)?)
    }

    /// Removes every version but the active one, once the pinned version verified. A
    /// server this engine runs from a superseded version is stopped first; one another
    /// engine runs refuses the removal as busy.
    pub fn prune(&mut self) -> Result<(), LocalAiError> {
        let QuickInspection::Active(active) = self.store.inspect_quick(&self.artifact)? else {
            return Err(LocalAiError::Failed(FailureCategory::ProgramMissing));
        };
        if self
            .server
            .as_ref()
            .is_some_and(|server| server.executable != active.executable)
        {
            self.stop();
        }
        self.refuse_foreign_server()?;
        Ok(self.store.prune(&self.artifact)?)
    }

    /// Removes every installed version. The server this engine runs is stopped first; a
    /// server another engine still runs refuses the removal as busy.
    pub fn remove(&mut self) -> Result<(), LocalAiError> {
        self.stop();
        self.refuse_foreign_server()?;
        Ok(self.store.remove(&self.artifact.id)?)
    }

    /// Busy while a server this engine did not start still answers at the recorded
    /// address; a record no server answers for is left by an engine that is gone, and
    /// is removed.
    fn refuse_foreign_server(&self) -> Result<(), LocalAiError> {
        let Some(record) = ServerRecord::read(&self.locations.programs) else {
            return Ok(());
        };
        if self
            .server
            .as_ref()
            .is_some_and(|server| server.process_id() == Some(record.process_id))
        {
            return Ok(());
        }
        let answering = record
            .loopback()
            .is_some_and(|loopback| loopback.get("/api/version").is_ok());
        if answering {
            return Err(LocalAiError::Engine(Error::Busy));
        }
        Ok(remove_record(&self.locations.programs)?)
    }

    /// The server this engine runs, when one is running.
    pub fn server(&self) -> Option<&Server> {
        self.server.as_ref()
    }

    /// Starts the server from the active pinned version, unless this engine already runs
    /// it. `ambient` reads the engine's own environment for the operating system settings
    /// the server is given; `proxy` is the operator's proxy for the models it downloads.
    pub fn start(
        &mut self,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Result<&Server, LocalAiError> {
        if self.server.is_some() {
            return self
                .server
                .as_ref()
                .ok_or(LocalAiError::Failed(FailureCategory::ProgramNotRunning));
        }
        let QuickInspection::Active(active) = self.store.inspect_quick(&self.artifact)? else {
            return Err(LocalAiError::Failed(FailureCategory::ProgramMissing));
        };
        let command = self.serve_command(&active, ambient, proxy)?;
        self.start_with(command)
    }

    /// The command a start of `active` runs: `serve` on a free loopback port, with the
    /// models, home and temporary folders under the installation's storage root.
    fn serve_command(
        &self,
        active: &ActiveComponent,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Result<ServeCommand, LocalAiError> {
        let address = free_loopback_address()?;
        let home = &self.locations.ollama_home;
        let mut environment = BTreeMap::new();
        for name in PASSED_THROUGH {
            if let Some(value) = ambient(name) {
                environment.insert(OsString::from(name), value);
            }
        }
        let mut set = |name: &str, value: &OsStr| {
            environment.insert(OsString::from(name), value.to_owned());
        };
        set("OLLAMA_HOST", OsStr::new(&address.to_string()));
        set("OLLAMA_MODELS", self.locations.models.as_os_str());
        set("OLLAMA_HOME", home.as_os_str());
        set("HOME", home.as_os_str());
        set("USERPROFILE", home.as_os_str());
        set("APPDATA", home.join("AppData").join("Roaming").as_os_str());
        set(
            "LOCALAPPDATA",
            home.join("AppData").join("Local").as_os_str(),
        );
        let temporary = home.join("tmp");
        for name in ["TEMP", "TMP", "TMPDIR"] {
            set(name, temporary.as_os_str());
        }
        if let Some(proxy) = proxy {
            for (name, value) in proxy.child_environment() {
                set(name, OsStr::new(value.as_str()));
            }
        }
        let arguments = self.serve_arguments(&mut environment);
        Ok(ServeCommand {
            executable: active.executable.clone(),
            arguments,
            environment,
            working_directory: home.clone(),
            address,
        })
    }

    #[cfg(not(test))]
    fn serve_arguments(&self, _: &mut BTreeMap<OsString, OsString>) -> Vec<OsString> {
        vec![OsString::from("serve")]
    }

    #[cfg(test)]
    fn serve_arguments(&self, environment: &mut BTreeMap<OsString, OsString>) -> Vec<OsString> {
        match &self.serve_override {
            Some(stand_in) => {
                environment.extend(stand_in.environment.iter().cloned());
                stand_in.arguments.clone()
            }
            None => vec![OsString::from("serve")],
        }
    }

    /// Starts exactly `command` as this engine's server and records it.
    fn start_with(&mut self, command: ServeCommand) -> Result<&Server, LocalAiError> {
        let home = &self.locations.ollama_home;
        for folder in [
            self.locations.models.clone(),
            home.join("AppData").join("Roaming"),
            home.join("AppData").join("Local"),
            home.join("tmp"),
        ] {
            filesystem::refuse_links(&folder)?;
            fs::create_dir_all(&folder)?;
        }
        let record = self.locations.programs.join(SERVER_RECORD);
        let server = Server::spawn(command, &self.version, record.clone())?;
        filesystem::replace_json(
            &record,
            &ServerRecord {
                schema: 1,
                address: server.address().to_string(),
                version: server.version.clone(),
                executable: server.executable.clone(),
                models: self.locations.models.clone(),
                process_id: server.process_id().unwrap_or_default(),
            },
        )?;
        Ok(self.server.insert(server))
    }

    /// Stops the server this engine runs, if any.
    pub fn stop(&mut self) {
        if let Some(mut server) = self.server.take() {
            server.halt();
        }
    }
}

fn remove_record(programs: &Path) -> Result<(), Error> {
    match fs::remove_file(programs.join(SERVER_RECORD)) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
        _ => Ok(()),
    }
}

/// A loopback port free now, for the server to bind. Another process could take it in
/// between; the server then fails to start and reads `program_not_running`.
fn free_loopback_address() -> std::io::Result<SocketAddr> {
    TcpListener::bind((Ipv4Addr::LOCALHOST, 0))?.local_addr()
}

/// Where the publisher's own installers put the program on this platform, and every
/// `PATH` folder, as `lookup` reads the environment.
pub fn system_locations(lookup: &dyn Fn(&str) -> Option<OsString>) -> Vec<PathBuf> {
    let name = if cfg!(windows) {
        "ollama.exe"
    } else {
        "ollama"
    };
    let mut candidates: Vec<PathBuf> = lookup("PATH")
        .map(|path| {
            std::env::split_paths(&path)
                .map(|folder| folder.join(name))
                .collect()
        })
        .unwrap_or_default();
    if cfg!(windows) {
        let local = lookup("LOCALAPPDATA").map(PathBuf::from).or_else(|| {
            lookup("USERPROFILE").map(|home| PathBuf::from(home).join("AppData").join("Local"))
        });
        if let Some(local) = local {
            candidates.push(local.join("Programs").join("Ollama").join(name));
        }
    } else if cfg!(target_os = "macos") {
        candidates.extend(
            [
                "/Applications/Ollama.app/Contents/Resources/ollama",
                "/opt/homebrew/bin/ollama",
                "/usr/local/bin/ollama",
            ]
            .map(PathBuf::from),
        );
    } else {
        candidates.extend(["/usr/local/bin/ollama", "/usr/bin/ollama"].map(PathBuf::from));
    }
    candidates
}

/// The first of `candidates` that is a file outside `own`, the engine's own program
/// folder: a copy installed outside Cadrumo. It is only reported; nothing here runs,
/// changes or removes it.
pub fn system_program(candidates: &[PathBuf], own: &Path) -> Option<PathBuf> {
    candidates
        .iter()
        .filter(|candidate| candidate.is_absolute() && !candidate.starts_with(own))
        .find(|candidate| candidate.is_file())
        .cloned()
}

#[cfg(test)]
mod tests;
