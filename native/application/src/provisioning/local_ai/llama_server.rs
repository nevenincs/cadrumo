//! The llama-server the package carries, run as the local AI server in router mode.
//!
//! The package stages the pinned upstream llama-server into its `llama_server` folder,
//! and the package manifest hashes it with every other file, so nothing here downloads,
//! installs or verifies it: it is set up exactly when the package carries it. A package
//! without it, as a Linux package is until its source build lands, reports it
//! [`LlamaServerUnavailable::NotPackaged`] and never starts it.
//!
//! One supervisor, the runtime manager, runs it on its own fixed loopback address, with
//! its home, settings, cache and temporary files under `components/llama-server/home`.
//! While it runs, `server.json` there names its address, build and process, in the shape
//! the Ollama server's record has. The [`lease`](super::lease) server lock in that folder
//! keeps a second supervisor from starting another.
//!
//! It runs as a router: it holds no model until the agent loads one through
//! `/models/load`, never loads one by itself (`--no-models-autoload`) and holds at most
//! one at a time (`--models-max 1`), so no model is loaded behind the agent's admission.
//! A load the router takes while it holds another model evicts that one, which its list
//! then reads unloaded with no `failed` flag. The models it can load are presented to it
//! in a preset file written from the store's manifests before each start: one section per
//! whole model, with its model layer as `model`, its projector layer as `mmproj`, and the
//! `ctx-size` recorded for the model, so a load never takes the model's full training
//! context. Cadrumo supplies no context of its own: a model with no recorded context has no
//! section and is not presented, so no load of it can start. Each start writes the preset
//! afresh. The model's own name is its `alias`, and the section is named [`router_id`]:
//! the router reads a section name with a colon as a repository and a quantisation and
//! rewrites it, so a section named `qwen3:1.7b` is listed as `qwen3:7B` and no request
//! by the name finds it, while an alias is kept as written and answers every request.
//!
//! The person's [`Placement`] is part of the preset too: `cpu_only` adds `n-gpu-layers = 0`
//! to every section, so no layer goes to a device, and `auto` adds no key, which leaves the
//! offload to the router. A change of the recorded contexts or of the placement changes the
//! preset text, and so is a stale preset like any other: the router drains and starts again
//! with it once it holds no model. The [`PlacementHandle`] is how the manager passes a
//! changed placement to the running server.
//!
//! A running server whose preset no longer matches the store drains: from that look on
//! the `restarting` file in its folder makes every [`load`] refuse with
//! [`LoadRefused::Restarting`], which its caller retries, and the server is started again
//! at the first look that finds it holding no model. A model in use is never unloaded
//! for it, and no load through [`load`] can take the router again before the restart,
//! so a model new in the store, or a changed context or placement, waits at most for the
//! model already held to be let go.
//! A load that a restart overtakes on its way is reported `Restarting` too, never as
//! done, and [`presentation`] tells whether the running router presents a model. The
//! drain's marker is written once, at the first look that finds the preset stale, and
//! left alone until the drain is over.
//!
//! It is ready once `/health` answers `200`, and it is the pinned build once the
//! `build_info` of `/props` is the pinned build tag, alone or followed by its commit.
//!
//! The component engine checks the selected models on it while llama.cpp is the selected
//! engine: the quick check reads from the files alone whether the running router's
//! preset presents a model ([`presented_by_router`]), and the full check
//! ([`check_model`]) finds the model in the router's list, loads it, waits until the list
//! reads it loaded, generates one token with it and unloads it again. A drain that
//! overtakes the full check is waited out for at most the check's own budget, after which
//! the router reads `program_not_running`.
//!
//! The router answers a load `200` at once, whether or not the model then loads: the
//! outcome is only in the model's entry in the list, which reads `loading`, and then
//! `loaded`, or `unloaded` with `failed` set when the model's process exited. The reason
//! is on the router's standard error and in no answer, so the full check reads a failed
//! load as `not_enough_memory`: for a model the store verified and the preset presents, on
//! the pinned build, memory is the expected cause.
//!
//! The router marks the entry `loading` before it answers the load, so an entry that reads
//! `unloaded` with no `failed` flag after the router took the load means another caller's
//! load took the router's one place and evicted this one. That is no failure of the model:
//! the full check looks again, loading it afresh, for as long as its budget lasts.

#[cfg(test)]
use super::program::ServeOverride;
use super::{
    LocalAiError, LocalEngine, NotRunningCause, Placement, ServerCall, StartFailureKind,
    huggingface::{MODEL_MEDIA_TYPE, PROJECTOR_MEDIA_TYPE},
    lease::Leases,
    loopback::Loopback,
    models::{MANIFEST_BYTES_LIMIT, ModelName, recorded_context, request_failed},
    program::{
        self, Containment, PASSED_THROUGH, SERVER_RECORD, SERVER_RECORD_SCHEMA, ServeCommand,
        Server, ServerRecord,
    },
    registry::{Blob, RegistryManifest},
    supervision::{SetUpStamp, Supervised},
};
use crate::{
    error::Error,
    filesystem,
    provisioning::{failure::FailureCategory, items::Locations, proxy::ProxySettings},
    value::Sha256Digest,
};
use std::{
    collections::BTreeMap,
    ffi::{OsStr, OsString},
    fmt::Write as _,
    fs,
    net::SocketAddr,
    num::NonZeroU32,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

/// The readiness route: `503` while the server is not ready, `200` once it is.
pub const HEALTH: &str = "/health";
/// The server's properties, whose `build_info` names its build.
pub const PROPERTIES: &str = "/props";
/// The router's models and their statuses.
const MODELS: &str = "/models";
/// The router's load of one model by its id or alias.
const LOAD: &str = "/models/load";
/// The router's unload of one model by its id or alias.
const UNLOAD: &str = "/models/unload";
/// The router's OpenAI-compatible completion, which it hands to the model named.
const COMPLETIONS: &str = "/v1/completions";
/// The file in the server's folder that is there while the running server drains for a
/// restart: no load is started while it is there.
pub const RESTARTING: &str = "restarting";
/// How often a full check looks again while the router drains for a restart or is loading
/// the model.
const DRAIN_LOOK: Duration = Duration::from_millis(250);
/// Bound of the preset file a presentation question reads.
const PRESET_BYTES_LIMIT: u64 = 4 * 1024 * 1024;
/// The server's folder under the components folder.
pub const FOLDER: &str = "llama-server";
/// The preset file in the server's folder.
pub const PRESET: &str = "models.ini";
/// The program's file name in the package's `llama_server` folder.
#[cfg(windows)]
const EXECUTABLE: &str = "llama-server.exe";
#[cfg(not(windows))]
const EXECUTABLE: &str = "llama-server";

/// Why the packaged llama-server cannot be run.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LlamaServerUnavailable {
    /// The package carries no llama-server for this platform. A Linux package carries
    /// none until its source build lands.
    NotPackaged,
    /// The build the package declares is not a llama.cpp build tag, or the storage folders
    /// are not absolute.
    Invalid,
}

/// Whether a model can be loaded from the running router now.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Presentation {
    /// The running router presents the model and takes loads.
    Presented,
    /// The router drains for a restart, or is being started again: ask again shortly.
    Restarting,
    /// The running router does not present the model: it is not whole in the store, or
    /// arrived after the router started and waits for its restart.
    NotPresented,
    /// No router runs.
    NotRunning,
}

/// Why a [`load`] did not leave its model loaded.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LoadRefused {
    /// No router runs.
    NotRunning,
    /// The router drains for a restart, or stopped or was started again while the load
    /// was on its way; nothing of this load stays loaded.
    Restarting,
    /// The running router does not present the model.
    NotPresented,
    /// The router refused the load with this status, or did not answer it. A load the
    /// router takes is answered `200` whether or not the model then loads.
    Failed { status: Option<u16> },
}

impl LoadRefused {
    /// Whether the same load can succeed once the router has moved on, so the caller
    /// asks again rather than reporting a failure.
    pub fn retryable(self) -> bool {
        !matches!(self, Self::Failed { .. })
    }
}

/// Where the router runs a model, shared between the supervised server and whoever holds a
/// clone, so a change of the person's placement reaches the preset of a running server. The
/// server reads it at each look and at each start; a changed value is a stale preset and
/// drains the router like a changed store.
#[derive(Clone, Debug, Default)]
pub struct PlacementHandle(Arc<Mutex<Placement>>);

impl PlacementHandle {
    pub fn new(placement: Placement) -> Self {
        Self(Arc::new(Mutex::new(placement)))
    }

    pub fn get(&self) -> Placement {
        *self.0.lock().unwrap_or_else(|error| error.into_inner())
    }

    pub fn set(&self, placement: Placement) {
        *self.0.lock().unwrap_or_else(|error| error.into_inner()) = placement;
    }
}

/// Whether `program_folder`, the package's `llama_server` folder, carries the llama-server
/// program. A package that does not reads [`LlamaServerUnavailable::NotPackaged`].
pub fn carried(program_folder: &Path) -> bool {
    filesystem::require_executable(&program_folder.join(EXECUTABLE)).is_ok()
}

/// `components/llama-server` under the storage `locations`.
pub fn server_folder(locations: &Locations) -> Option<PathBuf> {
    Some(locations.programs.parent()?.join(FOLDER))
}

/// The packaged llama-server and the server run from it.
pub struct LlamaServer {
    executable: PathBuf,
    build: String,
    /// `components/llama-server`: the record, the preset, the leases and the home.
    folder: PathBuf,
    models: PathBuf,
    placement: PlacementHandle,
    leases: Leases,
    server: Option<Server>,
    /// The preset the running server was started with.
    served_preset: Option<String>,
    /// The arguments and extra environment a test runs its stand-in program with.
    #[cfg(test)]
    pub(crate) serve_override: Option<ServeOverride>,
}

impl LlamaServer {
    /// The llama-server in `program_folder`, the package's `llama_server` folder, of the
    /// pinned `build`, serving the models under `locations` that have a recorded context,
    /// placed as `placement` says.
    pub fn packaged(
        program_folder: &Path,
        build: &str,
        locations: &Locations,
        placement: Placement,
    ) -> Result<Self, LlamaServerUnavailable> {
        if !build_tag(build) {
            return Err(LlamaServerUnavailable::Invalid);
        }
        if !carried(program_folder) {
            return Err(LlamaServerUnavailable::NotPackaged);
        }
        let executable = program_folder.join(EXECUTABLE);
        let folder = server_folder(locations).ok_or(LlamaServerUnavailable::Invalid)?;
        let leases = Leases::new(folder.clone()).map_err(|_| LlamaServerUnavailable::Invalid)?;
        Ok(Self {
            executable,
            build: build.to_owned(),
            folder,
            models: locations.models.clone(),
            placement: PlacementHandle::new(placement),
            leases,
            server: None,
            served_preset: None,
            #[cfg(test)]
            serve_override: None,
        })
    }

    pub fn executable(&self) -> &Path {
        &self.executable
    }

    /// The placement the server presents its models with, which the holder of this handle
    /// can change while the server runs.
    pub fn placement_handle(&self) -> PlacementHandle {
        self.placement.clone()
    }

    pub fn build(&self) -> &str {
        &self.build
    }

    /// `components/llama-server`, where the record and the preset are.
    pub fn folder(&self) -> &Path {
        &self.folder
    }

    /// The server this program started, when it is running.
    pub fn server(&self) -> Option<&Server> {
        self.server.as_ref()
    }

    /// The running router answering ready as the pinned build, whoever runs it. The
    /// handle owns nothing.
    pub fn running_server(&self) -> Option<Server> {
        Server::observed_as(LocalEngine::LlamaCpp, &self.folder, &self.build)
    }

    /// The kind of the latest failed start of the router, whoever started it, until a
    /// start succeeds.
    pub fn latest_start_failure(&self) -> Option<StartFailureKind> {
        program::latest_start_failure(&self.folder)
    }

    /// The command a start runs: the router on `address`, with the preset, and the
    /// home, cache and temporary folders under the server's folder. The address is on
    /// the command line, never in the environment, so the model instances the router
    /// starts, which inherit its environment, never read it as their own.
    fn serve_command(
        &self,
        address: SocketAddr,
        ambient: &dyn Fn(&str) -> Option<OsString>,
    ) -> Result<ServeCommand, LocalAiError> {
        Loopback::new(address)?;
        let home = self.folder.join("home");
        let mut environment = BTreeMap::new();
        for name in PASSED_THROUGH {
            if let Some(value) = ambient(name) {
                environment.insert(OsString::from(name), value);
            }
        }
        let mut set = |name: &str, value: &OsStr| {
            environment.insert(OsString::from(name), value.to_owned());
        };
        set("LLAMA_CACHE", home.join("cache").as_os_str());
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
        let arguments = self.serve_arguments(address, &mut environment);
        Ok(ServeCommand {
            executable: self.executable.clone(),
            arguments,
            environment,
            working_directory: home,
            address,
        })
    }

    #[cfg(not(test))]
    fn serve_arguments(
        &self,
        address: SocketAddr,
        _: &mut BTreeMap<OsString, OsString>,
    ) -> Vec<OsString> {
        router_arguments(address, &self.folder.join(PRESET))
    }

    #[cfg(test)]
    fn serve_arguments(
        &self,
        address: SocketAddr,
        environment: &mut BTreeMap<OsString, OsString>,
    ) -> Vec<OsString> {
        let router = router_arguments(address, &self.folder.join(PRESET));
        match &self.serve_override {
            Some(stand_in) => {
                environment.extend(stand_in.environment.iter().cloned());
                // The stand-in is a test binary: after `--` the router's own arguments
                // are test name filters that match nothing, and the stand-in reads them.
                let mut arguments = stand_in.arguments.clone();
                arguments.push(OsString::from("--"));
                arguments.extend(router);
                arguments
            }
            None => router,
        }
    }
}

impl Supervised for LlamaServer {
    fn is_set_up(&self) -> bool {
        filesystem::require_executable(&self.executable).is_ok()
    }

    fn set_up_stamp(&self) -> SetUpStamp {
        let metadata = fs::symlink_metadata(&self.executable).ok()?;
        Some((metadata.modified().ok()?, metadata.len()))
    }

    fn running_mut(&mut self) -> Option<&mut Server> {
        self.server.as_mut()
    }

    fn change_requested(&self) -> bool {
        self.leases.change_requested().unwrap_or(false)
    }

    /// Due once the store presents other models than the running server was started
    /// with, and the server holds none: a model in use is never unloaded for it. From
    /// the first look that finds the preset stale the server drains: the `restarting`
    /// file is written before the router is asked what it holds, so a load through
    /// [`load`] either reached the router before that question and keeps the restart
    /// off, or finds the file and reports that it was overtaken.
    fn restart_due(&mut self) -> bool {
        let Some(server) = &self.server else {
            return false;
        };
        let marker = self.folder.join(RESTARTING);
        if self.served_preset.as_deref()
            == Some(preset(&self.models, self.placement.get()).as_str())
        {
            // The store is back to what the server presents: nothing to drain for.
            let _ = fs::remove_file(&marker);
            return false;
        }
        if filesystem::refuse_links(&marker).is_err() {
            return false;
        }
        // The marker is written once per drain; a look that finds it has nothing to add.
        if fs::symlink_metadata(&marker).is_err() && fs::write(&marker, b"").is_err() {
            // Without the file a load could start under the restart: wait for a look
            // that can write it.
            return false;
        }
        held(server.loopback()).is_some_and(|held| held.is_empty())
    }

    /// The server downloads nothing, so no proxy setting applies to it.
    fn uses_proxy(&self) -> bool {
        false
    }

    fn serve(
        &mut self,
        address: SocketAddr,
        containment: &dyn Containment,
        ambient: &dyn Fn(&str) -> Option<OsString>,
        _: Option<&ProxySettings>,
    ) -> Result<(), LocalAiError> {
        if self.server.is_some() {
            return Ok(());
        }
        if !self.is_set_up() {
            return Err(LocalAiError::Failed(FailureCategory::ProgramMissing));
        }
        let Some(lease) = self.leases.try_serve()? else {
            return Err(LocalAiError::Engine(Error::Busy));
        };
        // A new attempt begins: an earlier failure no longer says why no server runs,
        // and a drain an earlier supervisor left unfinished is over.
        program::clear_start_failure(&self.folder);
        let _ = fs::remove_file(self.folder.join(RESTARTING));
        let home = self.folder.join("home");
        for folder in [
            home.join("AppData").join("Roaming"),
            home.join("AppData").join("Local"),
            home.join("tmp"),
            home.join("cache"),
        ] {
            filesystem::refuse_links(&folder)?;
            fs::create_dir_all(&folder)?;
        }
        let presented = preset(&self.models, self.placement.get());
        write_preset(&self.folder.join(PRESET), &presented)?;
        let command = self.serve_command(address, ambient)?;
        let record = self.folder.join(SERVER_RECORD);
        let server = match Server::spawn(
            LocalEngine::LlamaCpp,
            command,
            &self.build,
            record.clone(),
            containment,
            lease,
            None,
        ) {
            Ok(server) => server,
            Err(error) => {
                if let LocalAiError::NotRunning(NotRunningCause::Start(failure)) = &error {
                    program::record_start_failure(&self.folder, failure.kind());
                }
                return Err(error);
            }
        };
        filesystem::replace_json(
            &record,
            &ServerRecord {
                schema: SERVER_RECORD_SCHEMA,
                address: server.address().to_string(),
                version: server.version().to_owned(),
                executable: server.executable().to_path_buf(),
                models: self.models.clone(),
                process_id: server.process_id().unwrap_or_default(),
                proxy: None,
            },
        )?;
        program::clear_start_failure(&self.folder);
        self.served_preset = Some(presented);
        self.server = Some(server);
        Ok(())
    }

    fn halt(&mut self) {
        // Dropping the server unloads its models, ends it and gives the lease up; a
        // load overtaken by it finds the record gone or another process in it.
        drop(self.server.take());
        self.served_preset = None;
        let _ = fs::remove_file(self.folder.join(RESTARTING));
    }
}

/// The router's arguments: listening on `address`, the models from `preset`, none
/// loaded until asked for, and at most one held at a time.
fn router_arguments(address: SocketAddr, preset: &Path) -> Vec<OsString> {
    vec![
        OsString::from("--host"),
        OsString::from(address.ip().to_string()),
        OsString::from("--port"),
        OsString::from(address.port().to_string()),
        OsString::from("--models-preset"),
        preset.as_os_str().to_owned(),
        OsString::from("--models-max"),
        OsString::from("1"),
        OsString::from("--no-models-autoload"),
    ]
}

/// Whether `build` is spelled as a llama.cpp build tag: `b` and the build number.
fn build_tag(build: &str) -> bool {
    build
        .strip_prefix('b')
        .is_some_and(|number| !number.is_empty() && number.bytes().all(|c| c.is_ascii_digit()))
}

/// Whether the `build_info` a server reports is the build tag `expected`, alone or
/// followed by `-` and its commit.
pub(super) fn build_matches(found: &str, expected: &str) -> bool {
    found == expected
        || found
            .strip_prefix(expected)
            .is_some_and(|rest| rest.starts_with('-'))
}

/// The entries of the models the router holds or is loading; `None` when it does not
/// answer with its list.
fn held(loopback: Loopback) -> Option<Vec<serde_json::Value>> {
    let Ok((200, body)) = loopback.get(MODELS) else {
        return None;
    };
    let value: serde_json::Value = serde_json::from_slice(&body).ok()?;
    Some(
        value["data"]
            .as_array()?
            .iter()
            .filter(|entry| holds(entry))
            .cloned()
            .collect(),
    )
}

/// Whether one entry of the router's model list is the model `name`: listed under it or
/// answering to it as an alias.
fn answers_to(entry: &serde_json::Value, name: &str) -> bool {
    entry["id"].as_str() == Some(name)
        || entry["aliases"]
            .as_array()
            .is_some_and(|aliases| aliases.iter().any(|alias| alias.as_str() == Some(name)))
}

/// The running router in the server's `folder`, unless it drains for a restart.
struct Running {
    loopback: Loopback,
    process_id: u32,
}

fn running(folder: &Path) -> Result<Running, LoadRefused> {
    if draining(folder) {
        return Err(LoadRefused::Restarting);
    }
    let record = ServerRecord::read(folder).ok_or(LoadRefused::NotRunning)?;
    let address = record
        .address
        .parse::<SocketAddr>()
        .map_err(|_| LoadRefused::NotRunning)?;
    let loopback = Loopback::new(address).map_err(|_| LoadRefused::NotRunning)?;
    Ok(Running {
        loopback,
        process_id: record.process_id,
    })
}

fn draining(folder: &Path) -> bool {
    fs::symlink_metadata(folder.join(RESTARTING)).is_ok()
}

/// Whether the preset the running router was started with presents the model `name`.
fn presents(folder: &Path, name: &str) -> bool {
    let Ok(bytes) = filesystem::bounded_bytes(&folder.join(PRESET), PRESET_BYTES_LIMIT) else {
        return false;
    };
    let alias = format!("alias = {name}");
    String::from_utf8_lossy(&bytes)
        .lines()
        .any(|line| line == alias)
}

/// Whether the router running from the server's `folder` presents `model` and takes
/// loads now. The preset in the folder is the running router's own: each start writes
/// it before the process starts and the record after.
pub fn presentation(folder: &Path, model: &ModelName) -> Presentation {
    match running(folder) {
        Err(LoadRefused::Restarting) => Presentation::Restarting,
        Err(_) => Presentation::NotRunning,
        Ok(_) if presents(folder, &model.to_string()) => Presentation::Presented,
        Ok(_) => Presentation::NotPresented,
    }
}

/// Loads `model` into the router running from the server's `folder`.
///
/// `Ok` says the router took the load, or already holds the model. The router answers a
/// load at once, so the model is loaded only once its entry in the router's list reads so;
/// [`check_model`] waits for that.
///
/// A load that a restart overtakes is [`LoadRefused::Restarting`], never success: the
/// record is read again once the router has answered, and a drain begun meanwhile, or
/// another process or none in the record, means the load did not stay. A load the
/// router took during a drain is let go again unless the model was held before it, so
/// the drain is not kept waiting for a model nobody uses; a model another caller holds
/// is never unloaded.
pub fn load(folder: &Path, model: &ModelName) -> Result<(), LoadRefused> {
    load_request(folder, model).map(|_| ())
}

/// How the router took a load.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Accepted {
    /// The router started the load.
    Started,
    /// The router already holds the model, which is another caller's: it answers `400`
    /// that the model is already running.
    AlreadyRunning,
}

/// The load [`load`] makes, saying whether the router started it or already held the model.
fn load_request(folder: &Path, model: &ModelName) -> Result<Accepted, LoadRefused> {
    let before = running(folder)?;
    let id = model.to_string();
    if !presents(folder, &id) {
        return Err(LoadRefused::NotPresented);
    }
    let held_before =
        held(before.loopback).is_some_and(|held| held.iter().any(|entry| answers_to(entry, &id)));
    let request = serde_json::json!({ "model": id }).to_string();
    let answered = before.loopback.post(LOAD, request.as_bytes());
    let same =
        ServerRecord::read(folder).is_some_and(|after| after.process_id == before.process_id);
    if !same || draining(folder) {
        if same && !held_before && matches!(answered, Ok((200, _))) {
            let _ = before.loopback.post(UNLOAD, request.as_bytes());
        }
        return Err(LoadRefused::Restarting);
    }
    match answered {
        Ok((200, _)) => Ok(Accepted::Started),
        Ok((400, body)) if already_running(&body) => Ok(Accepted::AlreadyRunning),
        Ok((status, _)) => Err(LoadRefused::Failed {
            status: Some(status),
        }),
        Err(_) => Err(LoadRefused::Failed { status: None }),
    }
}

/// The lower-cased message of the error a router answered with, empty when it has none.
fn error_text(body: &[u8]) -> String {
    let value: serde_json::Value = serde_json::from_slice(body).unwrap_or_default();
    let error = &value["error"];
    error["message"]
        .as_str()
        .or_else(|| error.as_str())
        .unwrap_or_default()
        .to_lowercase()
}

/// Whether the error a router answered a completion with says in its own words that it ran
/// out of memory, as the Ollama server's error text is read.
fn out_of_memory(body: &[u8]) -> bool {
    error_text(body).contains("memory")
}

/// Whether the error a router answered a load with says the model is already running.
fn already_running(body: &[u8]) -> bool {
    error_text(body).contains("already running")
}

/// Whether the preset of the router recorded in `folder` presents `model`, while it runs
/// or drains for a restart; `None` when no router is recorded there. It reads files only,
/// for a quick check: a router draining for a restart still presents what it was started
/// with, and presents a model new in the store once it is started again.
pub fn presented_by_router(folder: &Path, model: &ModelName) -> Option<bool> {
    ServerRecord::read(folder)?;
    Some(presents(folder, &model.to_string()))
}

/// The full check of `model` on the router running from `folder`: the router lists it,
/// loads it through [`load`], waits until the list reads it loaded, generates one token of
/// `prompt` with it within `budget`, and unloads it again. `false` when the router does not
/// have the model. A model the router held before the check is another caller's and stays
/// loaded.
///
/// A router that drains for a restart is looked at again until it has restarted, for at
/// most `budget` in all; one that is still draining then, that is not running, or that
/// stopped answering reads `program_not_running`. A load that another caller's load evicted
/// is asked for again in the same way, and reads `program_not_running` when the budget runs
/// out. The same budget bounds the wait for the load: a model still loading then is
/// unloaded again and reads `unexpected`. A model whose entry reads failed reads
/// `not_enough_memory`, since the router gives no reason. A load the router refused, and an
/// answer that holds no generated token, read `unexpected`; a generation that ran out of
/// memory reads `not_enough_memory`.
pub fn check_model(
    folder: &Path,
    model: &ModelName,
    prompt: &str,
    budget: Duration,
) -> Result<bool, LocalAiError> {
    let started = Instant::now();
    let id = model.to_string();
    // A load the router took and has not finished: the next look reads the list for it
    // instead of loading again, which the router would answer as already running.
    let mut waiting: Option<(Loopback, bool, u32)> = None;
    let (loopback, held_before) = loop {
        let taken = match waiting {
            Some((loopback, held_before, process_id)) => {
                settle(folder, model, loopback, process_id, held_before)?
            }
            None => take(folder, model)?,
        };
        match taken {
            Taken::Loaded {
                loopback,
                held_before,
            } => break (loopback, held_before),
            Taken::Absent => return Ok(false),
            Taken::Loading {
                loopback,
                held_before,
                process_id,
            } => {
                if started.elapsed() >= budget {
                    if !held_before {
                        unload(loopback, &id);
                    }
                    return Err(LocalAiError::Failed(FailureCategory::Unexpected));
                }
                waiting = Some((loopback, held_before, process_id));
                std::thread::sleep(DRAIN_LOOK);
            }
            Taken::Draining if started.elapsed() < budget => {
                waiting = None;
                std::thread::sleep(DRAIN_LOOK);
            }
            Taken::Draining => {
                return Err(LocalAiError::Failed(FailureCategory::ProgramNotRunning));
            }
        }
    };
    let generated = generate_one_token(loopback, &id, prompt, budget);
    if !held_before {
        unload(loopback, &id);
    }
    generated
}

/// Asks the router to unload the model `id`; an answer is not waited for.
fn unload(loopback: Loopback, id: &str) {
    let request = serde_json::json!({ "model": id });
    let _ = loopback.post(UNLOAD, request.to_string().as_bytes());
}

/// What one attempt to take a model from the router's list into memory came to.
enum Taken {
    /// The model is loaded, and was or was not held before the attempt.
    Loaded {
        loopback: Loopback,
        held_before: bool,
    },
    /// The router took the load, or already held the model, and the list still reads it
    /// loading. `process_id` is the router's, so a restart is told from a failed load.
    Loading {
        loopback: Loopback,
        held_before: bool,
        process_id: u32,
    },
    /// The router does not have the model.
    Absent,
    /// The router drains for a restart, was started again under the load, or another
    /// caller's load evicted this one: nothing of the attempt stays loaded, and asking
    /// again can succeed.
    Draining,
}

/// Looks `model` up in the list of the router running from `folder` and loads it.
fn take(folder: &Path, model: &ModelName) -> Result<Taken, LocalAiError> {
    let not_running = || LocalAiError::Failed(FailureCategory::ProgramNotRunning);
    let router = match running(folder) {
        Ok(router) => router,
        Err(LoadRefused::Restarting) => return Ok(Taken::Draining),
        Err(_) => return Err(not_running()),
    };
    let loopback = router.loopback;
    let id = model.to_string();
    let (status, body) = loopback
        .get(MODELS)
        .map_err(|error| request_failed(&loopback, ServerCall::ListModels, &error))?;
    if status != 200 {
        return Err(LocalAiError::NotRunning(NotRunningCause::ListStatus {
            status,
        }));
    }
    let listed: serde_json::Value = serde_json::from_slice(&body)
        .map_err(|_| LocalAiError::Failed(FailureCategory::Unexpected))?;
    let Some(entries) = listed["data"].as_array() else {
        return Err(LocalAiError::Failed(FailureCategory::Unexpected));
    };
    let Some(entry) = entries.iter().find(|entry| answers_to(entry, &id)) else {
        return Ok(Taken::Absent);
    };
    let held_before = holds(entry);
    match load_request(folder, model) {
        // A model another caller loaded between the list and the load is theirs too.
        Ok(accepted) => settle(
            folder,
            model,
            loopback,
            router.process_id,
            held_before || accepted == Accepted::AlreadyRunning,
        ),
        Err(LoadRefused::NotPresented) => Ok(Taken::Absent),
        Err(LoadRefused::Restarting) => Ok(Taken::Draining),
        Err(LoadRefused::NotRunning | LoadRefused::Failed { status: None }) => Err(not_running()),
        Err(LoadRefused::Failed { status: Some(_) }) => {
            Err(LocalAiError::Failed(FailureCategory::Unexpected))
        }
    }
}

/// Reads where the router's list has `model` once the router took its load, which it
/// answers before the model has loaded. The router process is `process_id`; another one in
/// the record, or none, means a restart overtook the load. A drain begun meanwhile lets
/// the model go again unless it was held before, as [`load`] does.
///
/// The router lists the entry `loading` before it answers a load. An entry listed
/// `unloaded` that has not failed was therefore evicted by another caller's load, and reads
/// [`Taken::Draining`]: nothing of the attempt stays loaded and asking again can succeed. An
/// entry that failed is a model whose process ended, which for a stored model is memory.
fn settle(
    folder: &Path,
    model: &ModelName,
    loopback: Loopback,
    process_id: u32,
    held_before: bool,
) -> Result<Taken, LocalAiError> {
    let id = model.to_string();
    let same = ServerRecord::read(folder).is_some_and(|record| record.process_id == process_id);
    if !same {
        return Ok(Taken::Draining);
    }
    if draining(folder) {
        if !held_before {
            unload(loopback, &id);
        }
        return Ok(Taken::Draining);
    }
    let (status, body) = loopback
        .get(MODELS)
        .map_err(|error| request_failed(&loopback, ServerCall::ListModels, &error))?;
    if status != 200 {
        return Err(LocalAiError::NotRunning(NotRunningCause::ListStatus {
            status,
        }));
    }
    let listed: serde_json::Value = serde_json::from_slice(&body)
        .map_err(|_| LocalAiError::Failed(FailureCategory::Unexpected))?;
    let entry = listed["data"]
        .as_array()
        .and_then(|entries| entries.iter().find(|entry| answers_to(entry, &id)))
        .ok_or(LocalAiError::Failed(FailureCategory::Unexpected))?;
    let status = &entry["status"];
    let value = status["value"].as_str().or_else(|| status.as_str());
    match value {
        // The router's own process for the model ended and says why only on its standard
        // error: for a preset model of the pinned build that is memory.
        _ if status["failed"].as_bool() == Some(true) => {
            Err(LocalAiError::Failed(FailureCategory::NotEnoughMemory))
        }
        Some("loaded") => Ok(Taken::Loaded {
            loopback,
            held_before,
        }),
        Some("loading") => Ok(Taken::Loading {
            loopback,
            held_before,
            process_id,
        }),
        Some("unloaded") => Ok(Taken::Draining),
        _ => Err(LocalAiError::Failed(FailureCategory::Unexpected)),
    }
}

/// Whether one entry of the router's model list is loaded or loading.
fn holds(entry: &serde_json::Value) -> bool {
    let status = &entry["status"];
    matches!(
        status["value"].as_str().or_else(|| status.as_str()),
        Some("loaded" | "loading")
    )
}

/// Generates one token of `prompt` with the loaded model `id`, by the name the router
/// answers to: `false` when the router does not have the model.
fn generate_one_token(
    loopback: Loopback,
    id: &str,
    prompt: &str,
    budget: Duration,
) -> Result<bool, LocalAiError> {
    let request = serde_json::json!({
        "model": id,
        "prompt": prompt,
        "max_tokens": 1,
        "stream": false,
    });
    let loopback = loopback.with_io_timeout(budget);
    let (status, body) = loopback
        .post(COMPLETIONS, request.to_string().as_bytes())
        .map_err(|error| request_failed(&loopback, ServerCall::Generate, &error))?;
    let value: serde_json::Value = serde_json::from_slice(&body).unwrap_or_default();
    match status {
        200 if value["usage"]["completion_tokens"]
            .as_u64()
            .is_some_and(|tokens| tokens >= 1) =>
        {
            Ok(true)
        }
        // An answer without a generated token is no proof the model generates.
        200 => Err(LocalAiError::Failed(FailureCategory::Unexpected)),
        404 => Ok(false),
        _ => Err(LocalAiError::Failed(if out_of_memory(&body) {
            FailureCategory::NotEnoughMemory
        } else {
            FailureCategory::Unexpected
        })),
    }
}

/// Unloads every model the router holds; a server that does not answer is left to the
/// termination that follows.
pub(super) fn unload_all(loopback: Loopback) {
    for entry in held(loopback).unwrap_or_default() {
        let request = serde_json::json!({ "model": entry["id"] });
        let _ = loopback.post(UNLOAD, request.to_string().as_bytes());
    }
}

/// One model as the preset presents it: its weights and its projector, as preset values,
/// and the context recorded for it.
struct Presented {
    model: String,
    projector: Option<String>,
    context: NonZeroU32,
}

/// The id the router lists the model `name` under: the preset section's name, which has
/// no colon for the router to rewrite and is the same for one name every time.
pub fn router_id(name: &str) -> String {
    let digest = Sha256Digest::of(name.as_bytes());
    format!("m-{}", &digest.as_str()[..16])
}

/// The preset text for the models under `models`: one section per whole model that has a
/// recorded context, in the order of their names, each model's name as its alias and its
/// recorded context as its `ctx-size`. A model with no recorded context has no section.
/// `cpu_only` places no layer on a device, with `n-gpu-layers = 0` in every section; `auto`
/// adds no key.
pub fn preset(models: &Path, placement: Placement) -> String {
    let mut text = String::new();
    for (name, presented) in presented(models) {
        let _ = writeln!(text, "[{}]", router_id(&name));
        let _ = writeln!(text, "alias = {name}");
        let _ = writeln!(text, "model = {}", presented.model);
        if let Some(projector) = &presented.projector {
            let _ = writeln!(text, "mmproj = {projector}");
        }
        let _ = writeln!(text, "ctx-size = {}", presented.context);
        if placement == Placement::CpuOnly {
            let _ = writeln!(text, "n-gpu-layers = 0");
        }
        text.push('\n');
    }
    text
}

/// Every whole model the store's manifests name that has a recorded context, by the name
/// the model reads as. A manifest that cannot be read, names no model layer or more than
/// one, or names a layer that is not stored at its size presents nothing, and neither does
/// a model with no recorded context.
fn presented(models: &Path) -> BTreeMap<String, Presented> {
    let mut found = BTreeMap::new();
    for (host, host_folder) in children(&models.join("manifests"), true) {
        for (namespace, namespace_folder) in children(&host_folder, true) {
            for (model, model_folder) in children(&namespace_folder, true) {
                for (tag, manifest) in children(&model_folder, false) {
                    let Ok(name) = ModelName::parse(&format!("{host}/{namespace}/{model}:{tag}"))
                    else {
                        continue;
                    };
                    let Some(context) = recorded_context(models, &name) else {
                        continue;
                    };
                    if let Some(entry) = present(models, &manifest, context) {
                        found.insert(name.to_string(), entry);
                    }
                }
            }
        }
    }
    found
}

/// The folders, or the files, directly in `folder` whose names are text, never a link.
fn children(folder: &Path, folders: bool) -> Vec<(String, PathBuf)> {
    let Ok(entries) = fs::read_dir(folder) else {
        return Vec::new();
    };
    entries
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let kind = entry.file_type().ok()?;
            let wanted = if folders {
                kind.is_dir()
            } else {
                kind.is_file()
            };
            if !wanted || kind.is_symlink() {
                return None;
            }
            Some((entry.file_name().into_string().ok()?, entry.path()))
        })
        .collect()
}

/// The model one manifest names, when it is whole in the store, with its recorded `context`.
fn present(models: &Path, manifest: &Path, context: NonZeroU32) -> Option<Presented> {
    let bytes = filesystem::bounded_bytes(manifest, MANIFEST_BYTES_LIMIT).ok()?;
    let manifest = RegistryManifest::parse(bytes).ok()?;
    let mut weights = manifest
        .layers()
        .iter()
        .filter(|blob| blob.media_type == MODEL_MEDIA_TYPE);
    let model = weights.next()?;
    if weights.next().is_some() {
        return None;
    }
    let projector = match manifest
        .layers()
        .iter()
        .find(|blob| blob.media_type == PROJECTOR_MEDIA_TYPE)
    {
        Some(projector) => Some(stored(models, projector)?),
        None => None,
    };
    Some(Presented {
        model: stored(models, model)?,
        projector,
        context,
    })
}

/// Where `blob` is stored, as a preset value, when it is stored at its size.
fn stored(models: &Path, blob: &Blob) -> Option<String> {
    let path = models.join("blobs").join(blob.file_name());
    filesystem::refuse_links(&path).ok()?;
    let metadata = fs::metadata(&path).ok()?;
    if !metadata.is_file() || metadata.len() != blob.size {
        return None;
    }
    let text = path.to_str()?;
    // A preset value runs to the end of its line.
    if text.contains(['\n', '\r']) {
        return None;
    }
    Some(if cfg!(windows) {
        text.replace('\\', "/")
    } else {
        text.to_owned()
    })
}

/// Replaces the preset at `path` with `text` whole: the server reads either the earlier
/// preset or this one.
fn write_preset(path: &Path, text: &str) -> Result<(), Error> {
    let pending = path.with_extension("ini.pending");
    filesystem::refuse_links(path)?;
    filesystem::refuse_links(&pending)?;
    let written = fs::write(&pending, text).and_then(|()| fs::rename(&pending, path));
    if written.is_err() {
        let _ = fs::remove_file(&pending);
    }
    Ok(written?)
}

#[cfg(test)]
pub(crate) mod tests;
