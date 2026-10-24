//! The local AI's models: the pinned model each catalogue role reads with, pulled through
//! the server the engine started and checked against its pin.
//!
//! The program keeps a model as a manifest under `manifests/<registry>/library/<name>/<tag>`
//! in the models folder and its layers as `blobs/sha256-<hex>`. The manifest's SHA-256 is
//! the model's identity, the digest the pins record. So the quick check reads files only:
//! a manifest with the pinned digest whose every layer is stored at its size is present,
//! one with another digest is stale, and a missing manifest or layer is absent. The full
//! check asks the server for the same digest and generates one token with the model.
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
        items::{Destination, FULL_CHECK_BUDGET, MODEL_ROLES},
        pins::{ModelPin, ModelPins},
        plan::{Advisory, PartLicence, PlanPart},
        state::{BlockedReason, Observation, StaleReason},
        transfer::{Pacing, RetryPolicy, TransferEvent},
    },
    value::Sha256Digest,
};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    io,
    path::{Path, PathBuf},
};

/// The registry the pinned models come from, as the program names its folder.
const REGISTRY: &str = "registry.ollama.ai";
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

/// The pinned models and where the program keeps them.
#[derive(Clone, Debug)]
pub struct Models {
    pins: ModelPins,
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
    /// The pinned models, kept by the program under `root`, the installation's models
    /// folder.
    pub fn new(pins: ModelPins, root: PathBuf) -> Self {
        Self { pins, root }
    }

    /// The model `role` reads with, when the pins name one.
    pub fn for_role(&self, role: &str) -> Option<&ModelPin> {
        self.pins
            .roles
            .get(role)
            .and_then(|name| self.pins.model(name))
    }

    /// One plan part per catalogue role, in role order: the role's pinned model, from the
    /// pinned registry, into the models folder, under the licence the pins name. Roles
    /// that share a model share its target, so the plan counts the download once.
    pub fn plan_parts(&self) -> Vec<PlanPart> {
        MODEL_ROLES
            .iter()
            .filter_map(|role| {
                let pin = self.for_role(role)?;
                Some(PlanPart {
                    part_id: (*role).into(),
                    download_bytes: Some(pin.download_bytes),
                    source_hosts: self.pins.hosts.iter().cloned().collect(),
                    destination: Some(Destination::OllamaModels),
                    installs_outside_program: false,
                    target_version: Some(format!("{}@{}", pin.name, pin.manifest_digest)),
                    advisories: if pin.commercial_use_permitted {
                        Vec::new()
                    } else {
                        vec![Advisory::LicenceCommercialUseBarred]
                    },
                    licence: Some(PartLicence {
                        spdx_id: pin.licence.clone(),
                        name: pin.licence_name.clone(),
                    }),
                })
            })
            .collect()
    }

    /// The quick check of `role`'s model: its manifest and layers on disk, no server.
    pub fn observe_quick(&self, role: &str, hardware: &Hardware) -> Observation {
        let Some(pin) = self.for_role(role) else {
            return Observation::Blocked(BlockedReason::NotInThisBuild);
        };
        if hardware.below_floor(pin.memory_bytes) {
            return Observation::Blocked(BlockedReason::Hardware);
        }
        self.installed(pin)
    }

    /// The full check of `role`'s model on `server`: the quick check, the digest the
    /// server reports for it, and one generated token.
    pub fn observe_full(&self, server: &Server, role: &str, hardware: &Hardware) -> Observation {
        let quick = self.observe_quick(role, hardware);
        if quick != (Observation::Present { note: None }) {
            return quick;
        }
        let Some(pin) = self.for_role(role) else {
            return Observation::Blocked(BlockedReason::NotInThisBuild);
        };
        match reported_digest(server, &pin.name) {
            Err(error) => return Observation::Failed(error.category()),
            Ok(None) => return Observation::Absent,
            Ok(Some(digest)) if digest != pin.manifest_digest => {
                return Observation::Differs {
                    stale: StaleReason::DifferentModelVersion,
                    note: None,
                };
            }
            Ok(Some(_)) => {}
        }
        match generate_one_token(server, &pin.name) {
            Ok(true) => Observation::Present { note: None },
            Ok(false) => Observation::Absent,
            Err(error) => Observation::Failed(error.category()),
        }
    }

    /// Pulls `role`'s model through `server` unless it is already present, then reads it
    /// back as the quick check does: present, or stale when the registry served another
    /// manifest than the pinned one.
    pub fn pull(
        &self,
        server: &Server,
        role: &str,
        pull: &mut Pull<'_>,
    ) -> Result<Observation, LocalAiError> {
        let Some(pin) = self.for_role(role) else {
            return Err(LocalAiError::Failed(FailureCategory::NotInThisBuild));
        };
        if self.installed(pin) == (Observation::Present { note: None }) {
            (pull.events)(TransferEvent::Progress {
                completed: pin.download_bytes,
                total: pin.download_bytes,
            });
            return Ok(Observation::Present { note: None });
        }
        for attempt in 1..=pull.policy.max_attempts {
            pull.cancellation.check()?;
            match pull_once(server, pin, pull)? {
                Attempt::Done => {
                    return match self.installed(pin) {
                        observation @ (Observation::Present { .. }
                        | Observation::Differs { .. }) => Ok(observation),
                        _ => Err(LocalAiError::Failed(FailureCategory::DamagedDownload)),
                    };
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

    /// Removes every pinned model the models folder holds: its manifest, then each layer
    /// that no manifest left there uses. A model kept beside them keeps its layers, and
    /// when any kept manifest cannot be read, every layer stays.
    pub fn remove(&self) -> Result<(), Error> {
        let manifests = self.root.join("manifests");
        filesystem::refuse_links(&manifests)?;
        if std::fs::symlink_metadata(&manifests).is_err() {
            return Ok(());
        }
        let pinned: BTreeSet<PathBuf> = self
            .pins
            .models
            .iter()
            .filter_map(|pin| self.manifest_path(&pin.name))
            .collect();
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
                if pinned.contains(&path) {
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

    fn manifest_path(&self, name: &str) -> Option<PathBuf> {
        let (model, tag) = name.split_once(':')?;
        Some(
            self.root
                .join("manifests")
                .join(REGISTRY)
                .join("library")
                .join(model)
                .join(tag),
        )
    }

    /// What the models folder holds for `pin`.
    fn installed(&self, pin: &ModelPin) -> Observation {
        let Some(path) = self.manifest_path(&pin.name) else {
            return Observation::Unreadable;
        };
        let bytes = match filesystem::bounded_bytes(&path, MANIFEST_BYTES_LIMIT) {
            Ok(bytes) => bytes,
            Err(Error::Io(error)) if error.kind() == io::ErrorKind::NotFound => {
                return Observation::Absent;
            }
            Err(_) => return Observation::Unreadable,
        };
        if Sha256Digest::of(&bytes) != pin.manifest_digest {
            return Observation::Differs {
                stale: StaleReason::DifferentModelVersion,
                note: None,
            };
        }
        let Ok(manifest) = serde_json::from_slice::<Manifest>(&bytes) else {
            return Observation::Failed(FailureCategory::DamagedDownload);
        };
        let stored = std::iter::once(&manifest.config)
            .chain(&manifest.layers)
            .all(|layer| blob_stored(&self.root, layer));
        if stored {
            Observation::Present { note: None }
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
    pin: &ModelPin,
    pull: &mut Pull<'_>,
) -> Result<Attempt, LocalAiError> {
    let request = serde_json::json!({ "model": pin.name, "stream": true });
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
                        .min(pin.download_bytes);
                    events(TransferEvent::Progress {
                        completed,
                        total: pin.download_bytes,
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
                completed: pin.download_bytes,
                total: pin.download_bytes,
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

/// The manifest digest the server reports for `name`, or `None` when it has no such
/// model.
fn reported_digest(server: &Server, name: &str) -> Result<Option<Sha256Digest>, LocalAiError> {
    let (status, body) = server
        .loopback()
        .get("/api/tags")
        .map_err(|_| LocalAiError::Failed(FailureCategory::ProgramNotRunning))?;
    if status != 200 {
        return Err(LocalAiError::Failed(FailureCategory::ProgramNotRunning));
    }
    let value: serde_json::Value = serde_json::from_slice(&body)
        .map_err(|_| LocalAiError::Failed(FailureCategory::Unexpected))?;
    let entry = value["models"].as_array().and_then(|models| {
        models
            .iter()
            .find(|model| model["name"] == name || model["model"] == name)
    });
    match entry.and_then(|entry| entry["digest"].as_str()) {
        None => Ok(None),
        Some(digest) => Sha256Digest::new(digest.trim_start_matches("sha256:"))
            .map(Some)
            .map_err(|_| LocalAiError::Failed(FailureCategory::Unexpected)),
    }
}

/// Generates one token with `name` and unloads it again: `false` when the server does not
/// have the model. One that does not fit in memory fails as `not_enough_memory`.
fn generate_one_token(server: &Server, name: &str) -> Result<bool, LocalAiError> {
    let request = serde_json::json!({
        "model": name,
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
