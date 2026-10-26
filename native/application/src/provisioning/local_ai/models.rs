//! The local AI's models: the model the person selected for each local role, pulled
//! through the server the engine's manager runs and checked against what that server
//! holds.
//!
//! The engine defines no model. Its caller supplies the selection as role, model name and
//! download size triples, the size as the selected catalogue entry states it, and the
//! engine plans, pulls and checks exactly those. Integrity is the program's: it verifies
//! every layer it pulls against the model's content-addressed manifest, so the engine
//! compares no digest of its own.
//!
//! The program keeps a model as a manifest under
//! `manifests/<host>/<namespace>/<model>/<tag>` in the models folder and its layers as
//! `blobs/sha256-<hex>`. So the quick check reads files only: a manifest whose every layer
//! is stored at its size is present, and a missing manifest or layer is absent. There is
//! no stale model: a manifest other than the one pulled before is the model the program
//! verified under that name. The full check, and the check after a pull, look the model
//! up in the server's own list of installed models; the full check then generates one
//! token with it.
//!
//! A pull streams the program's progress lines into byte progress for the whole model.
//! The program resumes a model's partial layers by itself, so a pull that was cut off is
//! simply pulled again. A pull that fails in a way that may pass is retried under the
//! setup's retry schedule; every other failure is final at once.
//!
//! Role fitness, how well a model answers for its role, is no part of this state: it
//! is the consumer's admission check.

use super::{LocalAiError, hardware::Hardware, program::Server};
use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    provisioning::{
        failure::FailureCategory,
        items::{Destination, FULL_CHECK_BUDGET, PROGRAM_PART},
        plan::PlanPart,
        state::{BlockedReason, Observation},
        transfer::{Pacing, RetryPolicy, TransferEvent},
    },
    value::{HostName, Sha256Digest},
};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fmt, io,
    path::{Path, PathBuf},
};

/// The registry, namespace and tag the program reads a name without them as.
const DEFAULT_REGISTRY: &str = "registry.ollama.ai";
const DEFAULT_NAMESPACE: &str = "library";
const DEFAULT_TAG: &str = "latest";
/// The longest name, and the longest part of one, the engine accepts.
const NAME_LIMIT: usize = 512;
const PART_LIMIT: usize = 128;
const ROLE_LIMIT: usize = 64;
const MANIFEST_BYTES_LIMIT: u64 = 1024 * 1024;
/// What the one-token check asks.
const CHECK_PROMPT: &str = "Reply with one word.";

#[derive(Deserialize)]
struct Layer {
    digest: String,
    size: u64,
}

#[derive(Deserialize)]
struct Manifest {
    config: Layer,
    layers: Vec<Layer>,
}

fn invalid(what: &str) -> Error {
    Error::Invalid(format!("local model selection: {what}"))
}

/// A model's name as the program's registry spells it, `[[host/]namespace/]model[:tag]`,
/// with the registry, namespace and tag the program reads an omitted part as.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ModelName {
    host: HostName,
    namespace: String,
    model: String,
    tag: String,
}

impl ModelName {
    /// Reads `value`; refuses an empty name and any part that is not one plain path
    /// segment, so a name can never point outside the models folder.
    pub fn parse(value: &str) -> Result<Self, Error> {
        if value.is_empty() || value.len() > NAME_LIMIT {
            return Err(invalid("model name"));
        }
        let (path, tag) = match value.rsplit_once(':') {
            Some((path, tag)) if !tag.contains('/') => (path, tag),
            _ => (value, DEFAULT_TAG),
        };
        let parts: Vec<&str> = path.split('/').collect();
        let (host, namespace, model) = match parts.as_slice() {
            [model] => (DEFAULT_REGISTRY, DEFAULT_NAMESPACE, *model),
            [namespace, model] => (DEFAULT_REGISTRY, *namespace, *model),
            [host, namespace, model] => (*host, *namespace, *model),
            _ => return Err(invalid("model name")),
        };
        let segment = |text: &str, first: fn(u8) -> bool| {
            text.len() <= PART_LIMIT
                && text.bytes().next().is_some_and(first)
                && text
                    .bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"_.-".contains(&c))
        };
        if !segment(namespace, |c| c.is_ascii_alphanumeric())
            || !segment(model, |c| c.is_ascii_alphanumeric())
            || !segment(tag, |c| c.is_ascii_alphanumeric() || c == b'_')
        {
            return Err(invalid("model name"));
        }
        Ok(Self {
            host: HostName::new(host).map_err(|_| invalid("model name"))?,
            namespace: namespace.to_owned(),
            model: model.to_owned(),
            tag: tag.to_owned(),
        })
    }

    /// The registry the program pulls this model from.
    pub fn host(&self) -> &HostName {
        &self.host
    }

    /// Whether `other` names the same model; the program compares names regardless of
    /// case.
    pub fn same(&self, other: &Self) -> bool {
        self.host == other.host
            && self.namespace.eq_ignore_ascii_case(&other.namespace)
            && self.model.eq_ignore_ascii_case(&other.model)
            && self.tag.eq_ignore_ascii_case(&other.tag)
    }

    fn manifest_path(&self, root: &Path) -> PathBuf {
        root.join("manifests")
            .join(self.host.as_str())
            .join(&self.namespace)
            .join(&self.model)
            .join(&self.tag)
    }
}

/// The shortest spelling the program reads as this model: the default registry and
/// namespace left out, the tag always written.
impl fmt::Display for ModelName {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.host.as_str() != DEFAULT_REGISTRY {
            write!(f, "{}/{}/", self.host.as_str(), self.namespace)?;
        } else if self.namespace != DEFAULT_NAMESPACE {
            write!(f, "{}/", self.namespace)?;
        }
        write!(f, "{}:{}", self.model, self.tag)
    }
}

/// One local model the person selected: the role it reads for, its name and its download
/// size as the selected catalogue entry states it.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SelectedModel {
    pub role: String,
    pub name: ModelName,
    pub size_bytes: u64,
}

impl SelectedModel {
    /// One selection triple; refuses a role that is not a plain identifier, an empty or
    /// malformed name, and a zero size.
    pub fn new(role: &str, name: &str, size_bytes: u64) -> Result<Self, Error> {
        let mut bytes = role.bytes();
        let identifier = role.len() <= ROLE_LIMIT
            && bytes.next().is_some_and(|c| c.is_ascii_lowercase())
            && bytes.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_');
        if !identifier || role == PROGRAM_PART {
            return Err(invalid("role"));
        }
        if size_bytes == 0 {
            return Err(invalid("model size"));
        }
        Ok(Self {
            role: role.to_owned(),
            name: ModelName::parse(name)?,
            size_bytes,
        })
    }
}

/// The local models the person selected, at most one per role, in role order. Empty
/// when no local role has a selection: then there is nothing to pull, and no fallback.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct LocalModels(Vec<SelectedModel>);

impl LocalModels {
    /// Refuses a role selected twice, and a model selected for two roles under two
    /// different sizes, which no one catalogue entry can state.
    pub fn new(mut models: Vec<SelectedModel>) -> Result<Self, Error> {
        models.sort_by(|a, b| a.role.cmp(&b.role));
        if models.windows(2).any(|pair| pair[0].role == pair[1].role) {
            return Err(invalid("a role is selected once"));
        }
        for (index, model) in models.iter().enumerate() {
            if models[..index]
                .iter()
                .any(|other| other.name.same(&model.name) && other.size_bytes != model.size_bytes)
            {
                return Err(invalid("a model has one size"));
            }
        }
        Ok(Self(models))
    }

    pub fn as_slice(&self) -> &[SelectedModel] {
        &self.0
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// The model selected for `role`, if any.
    pub fn for_role(&self, role: &str) -> Option<&SelectedModel> {
        self.0.iter().find(|model| model.role == role)
    }

    /// The registries the selected models are pulled from.
    pub fn hosts(&self) -> BTreeSet<HostName> {
        self.0
            .iter()
            .map(|model| model.name.host().clone())
            .collect()
    }
}

/// The selected models and where the program keeps them.
#[derive(Clone, Debug)]
pub struct Models {
    selection: LocalModels,
    root: PathBuf,
}

/// The retry schedule, event sink and cancellation one pull runs under.
pub struct Pull<'a> {
    pub policy: RetryPolicy,
    pub pacing: &'a mut dyn Pacing,
    pub events: &'a mut dyn FnMut(TransferEvent),
    pub cancellation: &'a Cancellation,
}

enum Attempt {
    Done,
    Failed(FailureCategory),
}

impl Models {
    /// The selected models, kept by the program under `root`, the installation's models
    /// folder.
    pub fn new(selection: LocalModels, root: PathBuf) -> Self {
        Self { selection, root }
    }

    pub fn selection(&self) -> &LocalModels {
        &self.selection
    }

    /// One plan part per selected role, in role order: the selected model, from its
    /// registry, into the models folder, at the size the caller stated. Roles that share
    /// a model share its target, so the plan counts the download once.
    pub fn plan_parts(&self) -> Vec<PlanPart> {
        self.selection
            .as_slice()
            .iter()
            .map(|model| PlanPart {
                part_id: model.role.clone(),
                download_bytes: Some(model.size_bytes),
                source_hosts: vec![model.name.host().clone()],
                destination: Some(Destination::OllamaModels),
                installs_outside_program: false,
                target_version: Some(model.name.to_string()),
            })
            .collect()
    }

    /// The quick check of `model`: its manifest and layers on disk, no server. A
    /// computer whose memory cannot hold the model's stated size is held back first.
    pub fn observe_quick(&self, model: &SelectedModel, hardware: &Hardware) -> Observation {
        if hardware.below_floor(model.size_bytes) {
            return Observation::Blocked(BlockedReason::Hardware);
        }
        self.installed(&model.name)
    }

    /// The full check of `model` on `server`: the quick check, the server's own list of
    /// installed models, and one generated token.
    pub fn observe_full(
        &self,
        server: &Server,
        model: &SelectedModel,
        hardware: &Hardware,
    ) -> Observation {
        let quick = self.observe_quick(model, hardware);
        if quick != Observation::Present {
            return quick;
        }
        match listed(server, &model.name) {
            Err(error) => return Observation::Failed(error.category()),
            Ok(false) => return Observation::Absent,
            Ok(true) => {}
        }
        match generate_one_token(server, &model.name) {
            Ok(true) => Observation::Present,
            Ok(false) => Observation::Absent,
            Err(error) => Observation::Failed(error.category()),
        }
    }

    /// Pulls `model` through `server` unless it is already present, then reads it back as
    /// the quick check does and in the server's list of installed models.
    pub fn pull(
        &self,
        server: &Server,
        model: &SelectedModel,
        pull: &mut Pull<'_>,
    ) -> Result<Observation, LocalAiError> {
        if self.installed(&model.name) == Observation::Present {
            (pull.events)(TransferEvent::Progress {
                completed: model.size_bytes,
                total: model.size_bytes,
            });
            return Ok(Observation::Present);
        }
        for attempt in 1..=pull.policy.max_attempts {
            pull.cancellation.check()?;
            match pull_once(server, model, pull)? {
                Attempt::Done => {
                    // The program said it has the model; one it did not store whole, or
                    // does not list, is not the model the plan named.
                    if self.installed(&model.name) != Observation::Present {
                        return Err(LocalAiError::Failed(FailureCategory::DamagedDownload));
                    }
                    if !listed(server, &model.name)? {
                        return Err(LocalAiError::Failed(FailureCategory::DamagedDownload));
                    }
                    return Ok(Observation::Present);
                }
                Attempt::Failed(category) if !retried(category) => {
                    return Err(LocalAiError::Failed(category));
                }
                Attempt::Failed(category) => {
                    let delay = pull.policy.delay(attempt, pull.pacing.jitter());
                    if attempt == pull.policy.max_attempts
                        || pull.pacing.elapsed() + delay > pull.policy.window
                    {
                        return Err(LocalAiError::Failed(category));
                    }
                    (pull.events)(TransferEvent::Retrying {
                        attempt: attempt + 1,
                        delay,
                    });
                    pull.pacing.wait(delay, pull.cancellation)?;
                }
            }
        }
        Err(LocalAiError::Failed(FailureCategory::HostUnreachable))
    }

    /// Removes every selected model the models folder holds: its manifest, then each
    /// layer that no manifest left there uses. A model kept beside them keeps its layers,
    /// and when any kept manifest cannot be read, every layer stays.
    pub fn remove(&self) -> Result<(), Error> {
        self.remove_manifests(
            &self
                .selection
                .as_slice()
                .iter()
                .map(|model| model.name.manifest_path(&self.root))
                .collect(),
        )
    }

    /// Removes the model `name` alone, selected or not, under the same rule as
    /// [`Self::remove`]: every other model and the layers it uses stay.
    pub fn remove_named(&self, name: &ModelName) -> Result<(), Error> {
        self.remove_manifests(&BTreeSet::from([name.manifest_path(&self.root)]))
    }

    fn remove_manifests(&self, selected: &BTreeSet<PathBuf>) -> Result<(), Error> {
        let manifests = self.root.join("manifests");
        filesystem::refuse_links(&manifests)?;
        if std::fs::symlink_metadata(&manifests).is_err() {
            return Ok(());
        }
        let mut released = BTreeSet::new();
        let mut kept = BTreeSet::new();
        let mut unreadable = false;
        let mut pending = vec![manifests];
        while let Some(folder) = pending.pop() {
            for entry in std::fs::read_dir(&folder)? {
                let path = entry?.path();
                let meta = std::fs::symlink_metadata(&path)?;
                filesystem::refuse_metadata_links(&meta)?;
                if meta.is_dir() {
                    pending.push(path);
                    continue;
                }
                let layers = filesystem::bounded_bytes(&path, MANIFEST_BYTES_LIMIT)
                    .ok()
                    .and_then(|bytes| serde_json::from_slice::<Manifest>(&bytes).ok())
                    .map(|manifest| {
                        std::iter::once(manifest.config)
                            .chain(manifest.layers)
                            .map(|layer| layer.digest)
                            .collect::<Vec<_>>()
                    });
                if selected.contains(&path) {
                    released.extend(layers.into_iter().flatten());
                    std::fs::remove_file(&path)?;
                } else {
                    unreadable |= layers.is_none();
                    kept.extend(layers.into_iter().flatten());
                }
            }
        }
        if unreadable {
            return Ok(());
        }
        for digest in released.difference(&kept) {
            let Some(hex) = digest.strip_prefix("sha256:") else {
                continue;
            };
            if Sha256Digest::new(hex).is_err() {
                continue;
            }
            let blob = self.root.join("blobs").join(format!("sha256-{hex}"));
            filesystem::refuse_links(&blob)?;
            match std::fs::remove_file(&blob) {
                Err(error) if error.kind() != io::ErrorKind::NotFound => return Err(error.into()),
                _ => {}
            }
        }
        Ok(())
    }

    /// What the models folder holds for `name`.
    fn installed(&self, name: &ModelName) -> Observation {
        let path = name.manifest_path(&self.root);
        let bytes = match filesystem::bounded_bytes(&path, MANIFEST_BYTES_LIMIT) {
            Ok(bytes) => bytes,
            Err(Error::Io(error)) if error.kind() == io::ErrorKind::NotFound => {
                return Observation::Absent;
            }
            Err(_) => return Observation::Unreadable,
        };
        let Ok(manifest) = serde_json::from_slice::<Manifest>(&bytes) else {
            return Observation::Failed(FailureCategory::DamagedDownload);
        };
        let stored = std::iter::once(&manifest.config)
            .chain(&manifest.layers)
            .all(|layer| blob_stored(&self.root, layer));
        if stored {
            Observation::Present
        } else {
            Observation::Absent
        }
    }
}

fn blob_stored(root: &Path, layer: &Layer) -> bool {
    let Some(hex) = layer.digest.strip_prefix("sha256:") else {
        return false;
    };
    if Sha256Digest::new(hex).is_err() {
        return false;
    }
    let path = root.join("blobs").join(format!("sha256-{hex}"));
    filesystem::refuse_links(&path).is_ok()
        && std::fs::metadata(&path).is_ok_and(|meta| meta.is_file() && meta.len() == layer.size)
}

/// Failures another pull may cure; every other one is final at once.
fn retried(category: FailureCategory) -> bool {
    matches!(
        category,
        FailureCategory::HostUnreachable | FailureCategory::Offline
    )
}

/// One `POST /api/pull` through `server`, its progress lines folded into byte progress
/// for the whole model and its error line into a closed category.
fn pull_once(
    server: &Server,
    model: &SelectedModel,
    pull: &mut Pull<'_>,
) -> Result<Attempt, LocalAiError> {
    let request = serde_json::json!({ "model": model.name.to_string(), "stream": true });
    let mut layers: BTreeMap<String, u64> = BTreeMap::new();
    let mut succeeded = false;
    let mut failed = None;
    let cancellation = pull.cancellation;
    let stop = || cancellation.check().is_err();
    let events = &mut *pull.events;
    let answer = server
        .loopback()
        .with_io_timeout(FULL_CHECK_BUDGET)
        .post_lines(
            "/api/pull",
            request.to_string().as_bytes(),
            &stop,
            &mut |line| {
                let Ok(value) = serde_json::from_slice::<serde_json::Value>(line) else {
                    return Ok(());
                };
                if let Some(error) = value["error"].as_str() {
                    failed = Some(pull_error_category(error));
                    return Ok(());
                }
                if value["status"] == "success" {
                    succeeded = true;
                }
                if let (Some(digest), Some(completed)) =
                    (value["digest"].as_str(), value["completed"].as_u64())
                {
                    let held = layers.entry(digest.to_owned()).or_default();
                    *held = (*held).max(completed);
                    let completed = layers
                        .values()
                        .fold(0u64, |sum, bytes| sum.saturating_add(*bytes))
                        .min(model.size_bytes);
                    events(TransferEvent::Progress {
                        completed,
                        total: model.size_bytes,
                    });
                }
                Ok(())
            },
        );
    cancellation.check()?;
    let (status, body) = match answer {
        Ok(answer) => answer,
        // The engine's own connection to the program broke: the program, not the
        // registry, is the problem.
        Err(_) => return Ok(Attempt::Failed(FailureCategory::ProgramNotRunning)),
    };
    if !(200..300).contains(&status) {
        let error = serde_json::from_slice::<serde_json::Value>(&body)
            .ok()
            .and_then(|value| value["error"].as_str().map(pull_error_category));
        return Ok(Attempt::Failed(
            error.unwrap_or(FailureCategory::Unexpected),
        ));
    }
    Ok(match (succeeded, failed) {
        (_, Some(category)) => Attempt::Failed(category),
        (true, None) => {
            events(TransferEvent::Progress {
                completed: model.size_bytes,
                total: model.size_bytes,
            });
            Attempt::Done
        }
        // The answer ended before the program said it had the model: a pull cut off.
        (false, None) => Attempt::Failed(FailureCategory::HostUnreachable),
    })
}

/// The program words a registry failure as its HTTP and TLS libraries do; each phrase
/// names the closed category it means, most specific first. Anything else is
/// unexpected and never retried.
const PULL_ERRORS: &[(&str, FailureCategory)] = &[
    ("no space left on device", FailureCategory::DiskFull),
    ("not enough space", FailureCategory::DiskFull),
    ("disk full", FailureCategory::DiskFull),
    ("permission denied", FailureCategory::NoPermission),
    ("access is denied", FailureCategory::NoPermission),
    ("digest mismatch", FailureCategory::DamagedDownload),
    ("tls handshake timeout", FailureCategory::HostUnreachable),
    ("x509", FailureCategory::SecureConnectionFailed),
    ("certificate", FailureCategory::SecureConnectionFailed),
    ("tls:", FailureCategory::SecureConnectionFailed),
    (
        "proxy authentication required",
        FailureCategory::BlockedByNetwork,
    ),
    ("forbidden", FailureCategory::BlockedByNetwork),
    ("407", FailureCategory::BlockedByNetwork),
    ("403", FailureCategory::BlockedByNetwork),
    ("file does not exist", FailureCategory::Unexpected),
    ("manifest unknown", FailureCategory::Unexpected),
    ("no such host", FailureCategory::Offline),
    (
        "temporary failure in name resolution",
        FailureCategory::Offline,
    ),
    ("server misbehaving", FailureCategory::Offline),
    ("connection reset", FailureCategory::HostUnreachable),
    ("connection refused", FailureCategory::HostUnreachable),
    ("i/o timeout", FailureCategory::HostUnreachable),
    ("timeout", FailureCategory::HostUnreachable),
    ("unexpected eof", FailureCategory::HostUnreachable),
    ("max retries exceeded", FailureCategory::HostUnreachable),
    ("too many requests", FailureCategory::HostUnreachable),
    ("service unavailable", FailureCategory::HostUnreachable),
    ("bad gateway", FailureCategory::HostUnreachable),
    ("gateway timeout", FailureCategory::HostUnreachable),
    ("internal server error", FailureCategory::HostUnreachable),
    ("429", FailureCategory::HostUnreachable),
    ("500", FailureCategory::HostUnreachable),
    ("502", FailureCategory::HostUnreachable),
    ("503", FailureCategory::HostUnreachable),
    ("504", FailureCategory::HostUnreachable),
];

/// The closed category of the program's own error text for a pull.
pub fn pull_error_category(message: &str) -> FailureCategory {
    let text = message.to_lowercase();
    PULL_ERRORS
        .iter()
        .find(|(phrase, _)| text.contains(phrase))
        .map_or(FailureCategory::Unexpected, |(_, category)| *category)
}

/// Whether the server's own list of installed models holds `name`.
fn listed(server: &Server, name: &ModelName) -> Result<bool, LocalAiError> {
    let (status, body) = server
        .loopback()
        .get("/api/tags")
        .map_err(|_| LocalAiError::Failed(FailureCategory::ProgramNotRunning))?;
    if status != 200 {
        return Err(LocalAiError::Failed(FailureCategory::ProgramNotRunning));
    }
    let value: serde_json::Value = serde_json::from_slice(&body)
        .map_err(|_| LocalAiError::Failed(FailureCategory::Unexpected))?;
    let Some(models) = value["models"].as_array() else {
        return Err(LocalAiError::Failed(FailureCategory::Unexpected));
    };
    Ok(models.iter().any(|model| {
        [&model["name"], &model["model"]].into_iter().any(|listed| {
            listed
                .as_str()
                .and_then(|text| ModelName::parse(text).ok())
                .is_some_and(|listed| listed.same(name))
        })
    }))
}

/// Generates one token with `name` and unloads it again: `false` when the server does not
/// have the model. One that does not fit in memory fails as `not_enough_memory`.
fn generate_one_token(server: &Server, name: &ModelName) -> Result<bool, LocalAiError> {
    let request = serde_json::json!({
        "model": name.to_string(),
        "prompt": CHECK_PROMPT,
        "stream": false,
        "keep_alive": 0,
        "options": { "num_predict": 1 },
    });
    let (status, body) = server
        .loopback()
        .with_io_timeout(FULL_CHECK_BUDGET)
        .post("/api/generate", request.to_string().as_bytes())
        .map_err(|_| LocalAiError::Failed(FailureCategory::ProgramNotRunning))?;
    let value: serde_json::Value = serde_json::from_slice(&body).unwrap_or_default();
    if status == 200 && value["done"] == true {
        return Ok(true);
    }
    if status == 404 {
        return Ok(false);
    }
    let error = value["error"].as_str().unwrap_or_default().to_lowercase();
    Err(LocalAiError::Failed(if error.contains("memory") {
        FailureCategory::NotEnoughMemory
    } else {
        FailureCategory::Unexpected
    }))
}

#[cfg(test)]
mod tests;
