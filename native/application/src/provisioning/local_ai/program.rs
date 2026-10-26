//! The local AI program: the publisher's portable archive for this platform, installed
//! into the component store under `components/ollama`, and the one server run from it.
//!
//! Each pinned version lives in its own folder under `versions`, activated by one pointer
//! as the component store does for every component. One supervisor, the runtime
//! manager, runs the server: it keeps its models in the installation's models folder and
//! its home, settings and temporary files under `components/ollama/home`, and listens on
//! the installation's one fixed loopback address, which its owner supplies from the
//! package's environment declaration. While it runs, `server.json` beside the versions
//! names its address and process. Any other engine only observes that server; it never
//! starts a second one.
//!
//! The [`lease`](super::lease) locks keep the server and a program change apart: the
//! supervisor runs a server only under the server lease, and an engine replaces or
//! removes the program only once the supervisor has stopped its server and given the
//! lease up.
//!
//! The owner contains the server: it supplies a [`Containment`] that places the process
//! in a kill-on-close job on Windows, or in a process group that ends with the owner on
//! Linux and macOS, before any of its code runs, so nothing the server starts outlives
//! its stop. The server gets no console window. On an orderly stop the
//! supervisor unloads any model the server holds, which ends its runner processes, and
//! then ends the server. A copy installed outside Cadrumo is found and reported, never
//! started, changed or removed.
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

use super::{
    LocalAiError,
    lease::{Leases, PROGRAM_CHANGE_BUDGET, ProgramChange, ServerLease},
    loopback::Loopback,
};
use crate::{
    component::{ActiveComponent, Artifact, ComponentStore, QuickInspection},
    error::Error,
    filesystem,
    package::Readiness,
    provisioning::{
        failure::FailureCategory,
        items::{Destination, ItemId, Locations, PROGRAM_PART},
        pins::{Platform, ProgramPins},
        plan::PlanPart,
        proxy::ProxySettings,
        receipts::{Receipt, ReceiptFile, ReceiptLocation, ReceiptStore, build_manifest},
        state::{Observation, StaleReason},
        transfer::Transfer,
    },
    value::{HostName, RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    ffi::{OsStr, OsString},
    fs,
    io::{BufRead, BufReader, Read},
    net::SocketAddr,
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::mpsc,
    time::{Duration, SystemTime},
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
/// The receipt location's path naming the program's executable.
pub const PROGRAM_PATH: &str = "program";
/// The receipt location's path naming the models folder.
pub const MODELS_PATH: &str = "models";
/// The receipt location's fact naming the fixed `host:port` the server answers on.
pub const ADDRESS_FACT: &str = "address";
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

/// How the owner contains each server process: the creation flags the process is created
/// with, the process group it is created in, and the step that places it before any of
/// its code runs. The guards `open_group` and `contain` return live as long as the server
/// and are dropped once it has ended, which is where a kill-on-close job or a group's
/// guardian ends anything the server left behind.
pub trait Containment {
    /// Windows process creation flags added to the server's own.
    fn creation_flags(&self) -> u32 {
        0
    }

    /// Opens the process group the server is created in on Linux and macOS, before the
    /// process exists; `None` leaves it in its owner's group. On an error nothing starts.
    #[cfg(unix)]
    fn open_group(&self) -> std::io::Result<Option<ProcessGroup>> {
        Ok(None)
    }

    /// Contains `child`, created with [`Self::creation_flags`], and lets it run. On an
    /// error the child is ended without having run.
    fn contain(&self, child: &Child) -> std::io::Result<Box<dyn Send>>;
}

/// The process group a server is created in, and what keeps the group until the server
/// has ended.
pub struct ProcessGroup {
    /// The group id; 0 makes a new group of the server's own.
    pub id: i32,
    pub guard: Box<dyn Send>,
}

/// No containment of its own, for an owner already contained as a whole.
#[derive(Clone, Copy, Debug, Default)]
pub struct Uncontained;

impl Containment for Uncontained {
    fn contain(&self, _: &Child) -> std::io::Result<Box<dyn Send>> {
        Ok(Box::new(()))
    }
}

/// The record of the running server, read by the programs that use it.
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
    /// The digest of the route of the proxy setting this server was started under,
    /// absent when it was started without one. Never the address itself, which is a
    /// credential, and never its password, which the digest leaves out.
    pub proxy: Option<String>,
}

/// The record shape this build writes and reads.
pub const SERVER_RECORD_SCHEMA: u32 = 2;

impl ServerRecord {
    /// The record under `programs`, when one is there and readable.
    pub fn read(programs: &Path) -> Option<Self> {
        let bytes =
            filesystem::bounded_bytes(&programs.join(SERVER_RECORD), SERVER_RECORD_LIMIT).ok()?;
        serde_json::from_slice::<Self>(&bytes)
            .ok()
            .filter(|record| record.schema == SERVER_RECORD_SCHEMA)
    }

    /// The proxy setting the server was started under, when the record names a digest
    /// this build can read.
    pub fn proxy_fingerprint(&self) -> Option<Sha256Digest> {
        Sha256Digest::new(self.proxy.clone()?).ok()
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

/// A running server. The one the supervisor started stops when dropped; one only
/// observed through its record is left running.
pub struct Server {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    loopback: Loopback,
    version: String,
    executable: PathBuf,
    record: PathBuf,
    /// Dropped after the process has ended.
    containment: Option<Box<dyn Send>>,
    /// Released last, once the process has ended and its record is gone.
    lease: Option<ServerLease>,
    /// The digest of the proxy setting this server was started under, absent when it
    /// was started without one.
    proxy: Option<Sha256Digest>,
}

impl std::fmt::Debug for Server {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Server")
            .field("address", &self.loopback.address())
            .field("version", &self.version)
            .field("process_id", &self.process_id())
            .finish_non_exhaustive()
    }
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

    /// The proxy setting this server was started under; `None` when it was started
    /// without one, or when its record names no digest this build reads.
    pub fn proxy_fingerprint(&self) -> Option<Sha256Digest> {
        self.proxy.clone()
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
            containment: None,
            lease: None,
            proxy: None,
        }
    }

    /// The server `programs`' record names, when it answers there with `version`. The
    /// handle owns nothing: dropping it leaves the server running.
    pub fn observed(programs: &Path, version: &str) -> Option<Self> {
        let record = ServerRecord::read(programs)?;
        let server = Self {
            child: None,
            stdin: None,
            loopback: record.loopback()?,
            version: record.version.clone(),
            executable: record.executable.clone(),
            record: programs.join(SERVER_RECORD),
            containment: None,
            lease: None,
            proxy: record.proxy_fingerprint(),
        };
        (record.version == version
            && server
                .answers_version()
                .is_some_and(|found| found == version))
        .then_some(server)
    }

    /// Whether the process this handle started has ended. An observed server is never
    /// seen to end here.
    pub fn exited(&mut self) -> bool {
        self.child
            .as_mut()
            .is_some_and(|child| !matches!(child.try_wait(), Ok(None)))
    }

    /// Waits until the process this handle started has ended.
    #[cfg(test)]
    pub(crate) fn wait_exit(&mut self) {
        if let Some(child) = self.child.as_mut() {
            let _ = child.wait();
        }
    }

    /// Starts `command` contained and waits for the program to announce that it listens,
    /// then for it to answer with `version`. A program that exits, stays silent past
    /// [`START_BUDGET`] or answers otherwise is ended and reads `program_not_running`.
    fn spawn(
        command: ServeCommand,
        version: &str,
        record: PathBuf,
        containment: &dyn Containment,
        lease: ServerLease,
        proxy: Option<Sha256Digest>,
    ) -> Result<Self, LocalAiError> {
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
            process.creation_flags(CREATE_NO_WINDOW | containment.creation_flags());
        }
        #[cfg(unix)]
        let group = {
            let group = containment
                .open_group()
                .map_err(|_| LocalAiError::Failed(FailureCategory::ProgramNotRunning))?;
            if let Some(group) = &group {
                use std::os::unix::process::CommandExt;
                process.process_group(group.id);
            }
            group.map(|group| group.guard)
        };
        let loopback = Loopback::new(command.address)?;
        let mut child = crate::process::creation::run(|| process.spawn())
            .map_err(|_| LocalAiError::Failed(FailureCategory::ProgramNotRunning))?;
        let guard = match containment.contain(&child) {
            Ok(guard) => guard,
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(LocalAiError::Failed(FailureCategory::ProgramNotRunning));
            }
        };
        // The group's guard is dropped after the job's, once the server has ended.
        #[cfg(unix)]
        let guard: Box<dyn Send> = Box::new((guard, group));
        let stdin = child.stdin.take();
        let mut server = Self {
            child: Some(child),
            stdin,
            loopback,
            version: version.to_owned(),
            executable: command.executable,
            record,
            containment: Some(guard),
            lease: Some(lease),
            proxy,
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

    /// Asks the server to unload every model it holds, which ends its runners, then ends
    /// the server and whatever it left in its containment, removes its record and gives
    /// the lease up. Safe to call more than once.
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
        drop(self.containment.take());
        if ServerRecord::read(self.record.parent().unwrap_or(Path::new("")))
            .is_some_and(|record| record.process_id == child.id())
        {
            let _ = fs::remove_file(&self.record);
        }
        drop(self.lease.take());
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
/// run from it.
pub struct Program {
    store: ComponentStore,
    artifact: Artifact,
    version: String,
    hosts: Vec<HostName>,
    locations: Locations,
    leases: Leases,
    server: Option<Server>,
    /// Runs when a program change has asked the supervisor to stop and is waiting.
    change_requested: Option<Box<dyn FnMut() + Send>>,
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
        let leases = Leases::new(locations.activity.clone())?;
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
            leases,
            server: None,
            change_requested: None,
            #[cfg(test)]
            serve_override: None,
        }))
    }

    /// Runs `hook` whenever a change of the program has asked the running server's
    /// supervisor to stop and waits for it, so a surface can say what it is waiting for.
    pub fn on_change_requested(&mut self, hook: Box<dyn FnMut() + Send>) {
        self.change_requested = Some(hook);
    }

    pub fn leases(&self) -> &Leases {
        &self.leases
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
        }
    }

    /// The quick check: the active version, its receipt and its executable's bytes, with
    /// no network and no start.
    pub fn observe_quick(&self) -> Observation {
        match self.store.inspect_quick(&self.artifact) {
            Ok(QuickInspection::Active(_)) => Observation::Present,
            Ok(QuickInspection::Other { .. }) => Observation::Differs {
                stale: StaleReason::ProgramTooOld,
            },
            Ok(QuickInspection::Missing) => Observation::Absent,
            Ok(QuickInspection::Damaged) => Observation::Failed(FailureCategory::DamagedDownload),
            Err(_) => Observation::Unreadable,
        }
    }

    /// The full check: every installed file against its receipt, then the running server
    /// answering at its recorded address with the pinned version. Nothing is started:
    /// with no server running the program reads `program_not_running`.
    pub fn observe_full(&self) -> Observation {
        let quick = self.observe_quick();
        if quick != Observation::Present {
            return quick;
        }
        match self.store.inspect(&self.artifact) {
            Ok(inspection) if matches!(inspection.readiness, Readiness::Ready) => {}
            Ok(_) => return Observation::Failed(FailureCategory::DamagedDownload),
            Err(_) => return Observation::Unreadable,
        }
        match self.running_server() {
            Some(_) => Observation::Present,
            None => Observation::Failed(FailureCategory::ProgramNotRunning),
        }
    }

    /// The running server answering with the pinned version, whoever runs it.
    pub fn running_server(&self) -> Option<Server> {
        Server::observed(&self.locations.programs, &self.version)
    }

    /// Records the verified program in the local AI's receipt: the active version's
    /// files, and where a consumer finds the program, the models folder and the fixed
    /// `address` the supervisor's server answers on. The location's folder is the nearest
    /// one holding both the program and the models.
    pub fn settle(
        &self,
        receipts: &ReceiptStore,
        address: SocketAddr,
        verified_at: SystemTime,
    ) -> Result<(), LocalAiError> {
        Loopback::new(address)?;
        let QuickInspection::Active(active) = self.store.inspect_quick(&self.artifact)? else {
            return Err(LocalAiError::Failed(FailureCategory::ProgramMissing));
        };
        let root = common_folder(&self.locations.programs, &self.locations.models)
            .ok_or_else(|| Error::Invalid("local AI program and models share no folder".into()))?;
        let relative = |path: &Path| -> Result<RelativePath, Error> {
            RelativePath::from_native(
                path.strip_prefix(&root)
                    .map_err(|_| Error::Invalid("local AI location escaped".into()))?,
            )
        };
        let payload = relative(&active.root)?;
        let mut files = Vec::new();
        for file in build_manifest(&active.root)? {
            files.push(ReceiptFile {
                path: RelativePath::new(format!("{}/{}", payload.as_str(), file.path.as_str()))?,
                ..file
            });
        }
        files.sort_by(|a, b| a.path.cmp(&b.path));
        let location = ReceiptLocation::new(
            &root,
            [
                (PROGRAM_PATH.to_owned(), relative(&active.executable)?),
                (MODELS_PATH.to_owned(), relative(&self.locations.models)?),
            ]
            .into(),
            [(ADDRESS_FACT.to_owned(), address.to_string())].into(),
        )?;
        let receipt = Receipt::new(
            ItemId::LocalAi,
            Some(self.version.clone()),
            files,
            verified_at,
            self.hosts.clone(),
        )?
        .located(location)?;
        Ok(receipts.write(&receipt)?)
    }

    /// Downloads and activates the pinned version unless it is already active. The
    /// running server is stopped first, so no version is replaced under it.
    pub fn install(
        &mut self,
        transfer: &mut Transfer<'_>,
    ) -> Result<ActiveComponent, LocalAiError> {
        if let QuickInspection::Active(active) = self.store.inspect_quick(&self.artifact)? {
            return Ok(active);
        }
        let _change = self.change()?;
        Ok(self.store.download_and_activate(&self.artifact, transfer)?)
    }

    /// Removes every version but the active one, once the pinned version verified, with
    /// the running server stopped first.
    pub fn prune(&mut self) -> Result<(), LocalAiError> {
        let QuickInspection::Active(_) = self.store.inspect_quick(&self.artifact)? else {
            return Err(LocalAiError::Failed(FailureCategory::ProgramMissing));
        };
        let _change = self.change()?;
        Ok(self.store.prune(&self.artifact)?)
    }

    /// Removes every installed version, with the running server stopped first.
    pub fn remove(&mut self) -> Result<(), LocalAiError> {
        let _change = self.change()?;
        Ok(self.store.remove(&self.artifact.id)?)
    }

    /// The right to change the program: a server this program runs is stopped here, and
    /// the supervisor of any other is asked to stop it and waited for. A server still
    /// answering at the recorded address once the lease is held runs outside the lease
    /// and leaves the program busy; a record no server answers for is removed.
    fn change(&mut self) -> Result<ProgramChange, LocalAiError> {
        self.stop();
        let hook = &mut self.change_requested;
        let mut requested = || {
            if let Some(hook) = hook.as_mut() {
                hook();
            }
        };
        let change = self
            .leases
            .change_program(PROGRAM_CHANGE_BUDGET, &mut requested)?;
        if let Some(record) = ServerRecord::read(&self.locations.programs) {
            let answering = record
                .loopback()
                .is_some_and(|loopback| loopback.get("/api/version").is_ok());
            if answering {
                return Err(LocalAiError::Engine(Error::Busy));
            }
            remove_record(&self.locations.programs)?;
        }
        Ok(change)
    }

    /// The server this program started, when it is running.
    pub fn server(&self) -> Option<&Server> {
        self.server.as_ref()
    }

    /// The server this program started, to learn whether it has ended.
    pub fn server_mut(&mut self) -> Option<&mut Server> {
        self.server.as_mut()
    }

    /// Starts the server from the active pinned version on `address`, contained by
    /// `containment`, unless this program already runs it. Only the supervisor calls
    /// this. `Busy` while an engine changes the program or asks to, or another server
    /// holds the lease. `ambient` reads the supervisor's own environment for the
    /// operating system settings the server is given; `proxy` is the operator's proxy for
    /// the models it downloads.
    pub fn start(
        &mut self,
        address: SocketAddr,
        containment: &dyn Containment,
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
        let Some(lease) = self.leases.try_serve()? else {
            return Err(LocalAiError::Engine(Error::Busy));
        };
        let fingerprint = proxy.map(ProxySettings::fingerprint);
        let command = self.serve_command(&active, address, ambient, proxy)?;
        self.start_with(command, containment, lease, fingerprint)
    }

    /// The command a start of `active` runs: `serve` on `address`, with the models, home
    /// and temporary folders under the installation's storage root.
    fn serve_command(
        &self,
        active: &ActiveComponent,
        address: SocketAddr,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        proxy: Option<&ProxySettings>,
    ) -> Result<ServeCommand, LocalAiError> {
        Loopback::new(address)?;
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

    /// Starts exactly `command` as this program's server under `lease` and records it.
    fn start_with(
        &mut self,
        command: ServeCommand,
        containment: &dyn Containment,
        lease: ServerLease,
        proxy: Option<Sha256Digest>,
    ) -> Result<&Server, LocalAiError> {
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
        let server = Server::spawn(
            command,
            &self.version,
            record.clone(),
            containment,
            lease,
            proxy.clone(),
        )?;
        filesystem::replace_json(
            &record,
            &ServerRecord {
                schema: SERVER_RECORD_SCHEMA,
                address: server.address().to_string(),
                version: server.version.clone(),
                executable: server.executable.clone(),
                models: self.locations.models.clone(),
                process_id: server.process_id().unwrap_or_default(),
                proxy: proxy.map(|digest| digest.as_str().to_owned()),
            },
        )?;
        Ok(self.server.insert(server))
    }

    /// Stops the server this program started, if any.
    pub fn stop(&mut self) {
        if let Some(mut server) = self.server.take() {
            server.halt();
        }
    }
}

/// The deepest folder holding both `left` and `right`.
fn common_folder(left: &Path, right: &Path) -> Option<PathBuf> {
    let mut common = PathBuf::new();
    for (a, b) in left.components().zip(right.components()) {
        if a != b {
            break;
        }
        common.push(a);
    }
    common.is_absolute().then_some(common)
}

fn remove_record(programs: &Path) -> Result<(), Error> {
    match fs::remove_file(programs.join(SERVER_RECORD)) {
        Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
        _ => Ok(()),
    }
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
pub(crate) mod tests;
