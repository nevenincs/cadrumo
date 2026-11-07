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
//! one at a time (`--models-max 1`), so no model is loaded or evicted behind the agent's
//! admission. The models it can load are presented to it in a preset file written from
//! the store's manifests before each start: one section per whole model, named as the
//! model's own name reads, with its model layer as `model`, its projector layer as
//! `mmproj`, and an explicit `ctx-size`, so a load never takes the model's full
//! training context. Each start writes the preset afresh, and a running server whose
//! preset no longer matches the store is started again once it holds no model.
//!
//! It is ready once `/health` answers `200`, and it is the pinned build once the
//! `build_info` of `/props` is the pinned build tag, alone or followed by its commit.

#[cfg(test)]
use super::program::ServeOverride;
use super::{
    LocalAiError, LocalEngine, NotRunningCause,
    huggingface::{MODEL_MEDIA_TYPE, PROJECTOR_MEDIA_TYPE},
    lease::Leases,
    loopback::Loopback,
    models::{MANIFEST_BYTES_LIMIT, ModelName},
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
};
use std::{
    collections::BTreeMap,
    ffi::{OsStr, OsString},
    fmt::Write as _,
    fs,
    net::SocketAddr,
    path::{Path, PathBuf},
};

/// The readiness route: `503` while the server is not ready, `200` once it is.
pub const HEALTH: &str = "/health";
/// The server's properties, whose `build_info` names its build.
pub const PROPERTIES: &str = "/props";
/// The router's models and their statuses.
const MODELS: &str = "/models";
/// The router's unload of one model by its id.
const UNLOAD: &str = "/models/unload";
/// The server's folder under the components folder.
pub const FOLDER: &str = "llama-server";
/// The preset file in the server's folder.
pub const PRESET: &str = "models.ini";
/// The context every presented model loads with, in tokens. It is the context the
/// local engine measurement ran every model at on both engines.
pub const LOAD_CONTEXT: u32 = 8192;
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
    /// The build the package declares is not a llama.cpp build tag, the load context is
    /// zero, or the storage folders are not absolute.
    Invalid,
}

/// The packaged llama-server and the server run from it.
pub struct LlamaServer {
    executable: PathBuf,
    build: String,
    /// `components/llama-server`: the record, the preset, the leases and the home.
    folder: PathBuf,
    models: PathBuf,
    context: u32,
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
    /// pinned `build`, serving the models under `locations` at `context` tokens.
    pub fn packaged(
        program_folder: &Path,
        build: &str,
        locations: &Locations,
        context: u32,
    ) -> Result<Self, LlamaServerUnavailable> {
        if !build_tag(build) || context == 0 {
            return Err(LlamaServerUnavailable::Invalid);
        }
        let executable = program_folder.join(EXECUTABLE);
        if filesystem::require_executable(&executable).is_err() {
            return Err(LlamaServerUnavailable::NotPackaged);
        }
        let folder = locations
            .programs
            .parent()
            .ok_or(LlamaServerUnavailable::Invalid)?
            .join(FOLDER);
        let leases = Leases::new(folder.clone()).map_err(|_| LlamaServerUnavailable::Invalid)?;
        Ok(Self {
            executable,
            build: build.to_owned(),
            folder,
            models: locations.models.clone(),
            context,
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

    /// The command a start runs: the router on `address`, with the preset, and the
    /// home, cache and temporary folders under the server's folder.
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
        set("LLAMA_ARG_HOST", OsStr::new(&address.ip().to_string()));
        set("LLAMA_ARG_PORT", OsStr::new(&address.port().to_string()));
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
        let arguments = self.serve_arguments(&mut environment);
        Ok(ServeCommand {
            executable: self.executable.clone(),
            arguments,
            environment,
            working_directory: home,
            address,
        })
    }

    #[cfg(not(test))]
    fn serve_arguments(&self, _: &mut BTreeMap<OsString, OsString>) -> Vec<OsString> {
        router_arguments(&self.folder.join(PRESET))
    }

    #[cfg(test)]
    fn serve_arguments(&self, environment: &mut BTreeMap<OsString, OsString>) -> Vec<OsString> {
        match &self.serve_override {
            Some(stand_in) => {
                environment.extend(stand_in.environment.iter().cloned());
                stand_in.arguments.clone()
            }
            None => router_arguments(&self.folder.join(PRESET)),
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
    /// with, and the server holds none: a model in use is never unloaded for it.
    fn restart_due(&mut self) -> bool {
        let Some(server) = &self.server else {
            return false;
        };
        if self.served_preset.as_deref() == Some(preset(&self.models, self.context).as_str()) {
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
        // A new attempt begins: an earlier failure no longer says why no server runs.
        program::clear_start_failure(&self.folder);
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
        let presented = preset(&self.models, self.context);
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
        // Dropping the server unloads its models, ends it and gives the lease up.
        drop(self.server.take());
        self.served_preset = None;
    }
}

/// The router's arguments: the models from `preset`, none loaded until asked for, and
/// at most one held at a time.
fn router_arguments(preset: &Path) -> Vec<OsString> {
    vec![
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

/// The ids of the models the router holds or is loading; `None` when it does not
/// answer with its list.
fn held(loopback: Loopback) -> Option<Vec<String>> {
    let Ok((200, body)) = loopback.get(MODELS) else {
        return None;
    };
    let value: serde_json::Value = serde_json::from_slice(&body).ok()?;
    Some(
        value["data"]
            .as_array()?
            .iter()
            .filter(|model| {
                let status = &model["status"];
                matches!(
                    status["value"].as_str().or_else(|| status.as_str()),
                    Some("loaded" | "loading")
                )
            })
            .filter_map(|model| model["id"].as_str().map(str::to_owned))
            .collect(),
    )
}

/// Unloads every model the router holds; a server that does not answer is left to the
/// termination that follows.
pub(super) fn unload_all(loopback: Loopback) {
    for id in held(loopback).unwrap_or_default() {
        let request = serde_json::json!({ "model": id });
        let _ = loopback.post(UNLOAD, request.to_string().as_bytes());
    }
}

/// One model as the preset presents it: its weights and its projector, as preset values.
struct Presented {
    model: String,
    projector: Option<String>,
}

/// The preset text for the models under `models` at `context` tokens: one section per
/// whole model, in the order of their names.
pub fn preset(models: &Path, context: u32) -> String {
    let mut text = String::new();
    for (id, presented) in presented(models) {
        let _ = writeln!(text, "[{id}]");
        let _ = writeln!(text, "model = {}", presented.model);
        if let Some(projector) = &presented.projector {
            let _ = writeln!(text, "mmproj = {projector}");
        }
        let _ = writeln!(text, "ctx-size = {context}");
        text.push('\n');
    }
    text
}

/// Every whole model the store's manifests name, by the name the model reads as. A
/// manifest that cannot be read, names no model layer or more than one, or names a
/// layer that is not stored at its size presents nothing.
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
                    if let Some(entry) = present(models, &manifest) {
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

/// The model one manifest names, when it is whole in the store.
fn present(models: &Path, manifest: &Path) -> Option<Presented> {
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
mod tests;
