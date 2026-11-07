//! The local AI's Hugging Face source: a GGUF model file and its optional multimodal
//! projector, fetched from a Hugging Face repository at a pinned commit and written into
//! the same content-addressed store as a registry model.
//!
//! The engine defines no model. The agent's catalogue declares each file by repository,
//! commit, file name, SHA-256 digest and size, and the engine fetches exactly those. A
//! file comes from `https://huggingface.co/<owner>/<repo>/resolve/<commit>/<file>`
//! through the pinned transfer, with its hop, retry, resume and proxy rules, and a hop is
//! followed only to a host declared here and in the approved plan. A file is accepted
//! only at its declared size and digest, as a registry blob is, and is stored as
//! `blobs/sha256-<hex>`.
//!
//! The model is then published as a manifest in the registry's own shape, under
//! `manifests/huggingface.co/<owner>/<repo>/<tag>`, the tag being the model file's name
//! without `.gguf`. The model file is its `application/vnd.ollama.image.model` layer and
//! the projector its `application/vnd.ollama.image.projector` layer; the config is a small
//! document the engine writes itself from the layers' digests. So the quick check, the
//! removal of a model with its unshared layers, and the server's model presets read both
//! sources alike. The manifest is written last and atomically, so a model the folder
//! names is whole.
//!
//! Progress counts the bytes held of the declared files out of the sum of their declared
//! sizes, and never goes back.

use super::{
    models::ModelName,
    registry::{Blob, MANIFEST_MEDIA_TYPE, Registry, RegistryError, RegistryManifest},
};
use crate::{
    error::Error,
    provisioning::{transfer::Transfer, url::HttpsUrl},
    value::{HostName, Sha256Digest},
};
use serde::Serialize;
use std::collections::BTreeSet;

/// The host a Hugging Face repository is addressed at.
pub const HUGGING_FACE: &str = "huggingface.co";

/// The storage hosts Hugging Face redirects a file request to. On 2026-11-07 a `resolve`
/// request for a GGUF file at a pinned commit answered `302 Found` to
/// `us.aws.cdn.hf.co`, in one hop, for repositories old and new; that host answered a
/// `Range` request with `206` and an exact `Content-Range`. A small non-GGUF file
/// redirected within `huggingface.co` itself. No other host was seen, so no other is
/// declared: a file moved elsewhere is refused as blocked until its host is added here.
const HUGGING_FACE_FILE_HOSTS: &[&str] = &["us.aws.cdn.hf.co"];

/// The media types the store's manifests name a GGUF model, its projector and the
/// engine's config document by.
pub const MODEL_MEDIA_TYPE: &str = "application/vnd.ollama.image.model";
pub const PROJECTOR_MEDIA_TYPE: &str = "application/vnd.ollama.image.projector";
const CONFIG_MEDIA_TYPE: &str = "application/vnd.docker.container.image.v1+json";

const GGUF_SUFFIX: &str = ".gguf";
/// The longest file name the engine accepts; its tag stays within a name's part limit.
const FILE_LIMIT: usize = 128 + GGUF_SUFFIX.len();
const COMMIT_LENGTH: usize = 40;

fn invalid(what: &str) -> Error {
    Error::Invalid(format!("hugging face model: {what}"))
}

/// The hosts a Hugging Face fetch may reach: the hub and the storage it redirects to. A
/// plan names these as the model's sources.
pub fn source_hosts() -> BTreeSet<HostName> {
    std::iter::once(HUGGING_FACE)
        .chain(HUGGING_FACE_FILE_HOSTS.iter().copied())
        .filter_map(|host| HostName::new(host).ok())
        .collect()
}

/// One declared file of a Hugging Face repository: its name at the repository's root,
/// its SHA-256 digest and its size in bytes.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HuggingFaceFile {
    file: String,
    sha256: Sha256Digest,
    size: u64,
}

impl HuggingFaceFile {
    /// One declaration; refuses a name that is not one plain `.gguf` file name at the
    /// repository's root, a digest that is not SHA-256 hex, and an empty file.
    pub fn new(file: &str, sha256: &str, size: u64) -> Result<Self, Error> {
        let stem = file.strip_suffix(GGUF_SUFFIX).unwrap_or_default();
        let plain = file.len() <= FILE_LIMIT
            && stem
                .bytes()
                .next()
                .is_some_and(|c| c.is_ascii_alphanumeric())
            && stem
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"_.-".contains(&c));
        if !plain {
            return Err(invalid("file name"));
        }
        if size == 0 {
            return Err(invalid("file size"));
        }
        Ok(Self {
            file: file.to_owned(),
            sha256: Sha256Digest::new(sha256).map_err(|_| invalid("file digest"))?,
            size,
        })
    }

    pub fn file(&self) -> &str {
        &self.file
    }

    pub fn sha256(&self) -> &Sha256Digest {
        &self.sha256
    }

    pub fn size(&self) -> u64 {
        self.size
    }

    fn blob(&self, media_type: &str) -> Blob {
        Blob {
            media_type: media_type.to_owned(),
            digest: self.sha256.clone(),
            size: self.size,
        }
    }
}

/// A model declared on Hugging Face: its repository at a pinned commit, its GGUF model
/// file and, for a vision model, the projector file it loads with.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HuggingFaceModel {
    name: ModelName,
    revision: String,
    model: HuggingFaceFile,
    projector: Option<HuggingFaceFile>,
}

impl HuggingFaceModel {
    /// One declaration; refuses a repository that is not `<owner>/<repo>` in plain name
    /// segments, a revision that is not a full lowercase commit id, and a projector that
    /// is the model file itself.
    pub fn new(
        repository: &str,
        revision: &str,
        model: HuggingFaceFile,
        projector: Option<HuggingFaceFile>,
    ) -> Result<Self, Error> {
        let (owner, repo) = repository
            .split_once('/')
            .ok_or_else(|| invalid("repository"))?;
        let tag = model
            .file
            .strip_suffix(GGUF_SUFFIX)
            .ok_or_else(|| invalid("file name"))?;
        let name = ModelName::parse(&format!("{HUGGING_FACE}/{owner}/{repo}:{tag}"))
            .map_err(|_| invalid("repository"))?;
        if name.namespace() != owner || name.model() != repo || name.tag() != tag {
            return Err(invalid("repository"));
        }
        let commit = revision.len() == COMMIT_LENGTH
            && revision
                .bytes()
                .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c));
        if !commit {
            return Err(invalid("revision"));
        }
        if projector.as_ref().is_some_and(|projector| {
            projector.sha256 == model.sha256 || projector.file == model.file
        }) {
            return Err(invalid("projector"));
        }
        Ok(Self {
            name,
            revision: revision.to_owned(),
            model,
            projector,
        })
    }

    /// The name the store keeps the model under, `huggingface.co/<owner>/<repo>:<tag>`.
    pub fn name(&self) -> &ModelName {
        &self.name
    }

    /// The commit the files are fetched at.
    pub fn revision(&self) -> &str {
        &self.revision
    }

    pub fn model(&self) -> &HuggingFaceFile {
        &self.model
    }

    pub fn projector(&self) -> Option<&HuggingFaceFile> {
        self.projector.as_ref()
    }

    /// The bytes a fetch downloads: the declared sizes of the model and its projector.
    pub fn download_bytes(&self) -> u64 {
        self.files()
            .fold(0u64, |sum, file| sum.saturating_add(file.size))
    }

    fn files(&self) -> impl Iterator<Item = &HuggingFaceFile> {
        std::iter::once(&self.model).chain(&self.projector)
    }

    /// The manifest layers: the model, then its projector if it has one.
    fn layers(&self) -> Vec<Blob> {
        std::iter::once(self.model.blob(MODEL_MEDIA_TYPE))
            .chain(
                self.projector
                    .iter()
                    .map(|projector| projector.blob(PROJECTOR_MEDIA_TYPE)),
            )
            .collect()
    }

    /// Where `file` is fetched from.
    fn url(&self, file: &HuggingFaceFile) -> Result<HttpsUrl, RegistryError> {
        HttpsUrl::parse(&format!(
            "https://{HUGGING_FACE}/{}/{}/resolve/{}/{}",
            self.name.namespace(),
            self.name.model(),
            self.revision,
            file.file
        ))
        .map_err(RegistryError::from)
    }

    /// The config document the engine writes for the model, and the manifest naming it
    /// and the layers. Both follow from the declaration alone, so the same declaration
    /// always publishes the same bytes.
    pub fn documents(&self) -> Result<(Vec<u8>, RegistryManifest), RegistryError> {
        let layers = self.layers();
        let config = serde_json::to_vec(&ConfigDocument {
            model_format: "gguf",
            rootfs: RootFs {
                kind: "layers",
                diff_ids: layers.iter().map(Blob::reference).collect(),
            },
        })
        .map_err(Error::from)?;
        let descriptor = |blob: &Blob| Descriptor {
            media_type: blob.media_type.clone(),
            digest: blob.reference(),
            size: blob.size,
        };
        let manifest = serde_json::to_vec(&ManifestDocument {
            schema_version: 2,
            media_type: MANIFEST_MEDIA_TYPE,
            config: Descriptor {
                media_type: CONFIG_MEDIA_TYPE.to_owned(),
                digest: format!("sha256:{}", Sha256Digest::of(&config)),
                size: config.len() as u64,
            },
            layers: layers.iter().map(descriptor).collect(),
        })
        .map_err(Error::from)?;
        Ok((config, RegistryManifest::parse(manifest)?))
    }
}

#[derive(Serialize)]
struct RootFs {
    #[serde(rename = "type")]
    kind: &'static str,
    diff_ids: Vec<String>,
}

#[derive(Serialize)]
struct ConfigDocument {
    model_format: &'static str,
    rootfs: RootFs,
}

#[derive(Serialize)]
struct Descriptor {
    #[serde(rename = "mediaType")]
    media_type: String,
    digest: String,
    size: u64,
}

#[derive(Serialize)]
struct ManifestDocument {
    #[serde(rename = "schemaVersion")]
    schema_version: u32,
    #[serde(rename = "mediaType")]
    media_type: &'static str,
    config: Descriptor,
    layers: Vec<Descriptor>,
}

impl Registry {
    /// Fetches `model`'s declared files into the models folder, each not already stored
    /// whole, then writes its config and, last, its manifest. Returns the manifest the
    /// store now holds. A failure leaves resumable partial bytes, never damaged ones, and
    /// publishes no manifest.
    pub fn pull_hugging_face(
        &self,
        model: &HuggingFaceModel,
        transfer: &mut Transfer<'_>,
    ) -> Result<RegistryManifest, RegistryError> {
        let hosts: BTreeSet<HostName> = source_hosts()
            .intersection(transfer.hosts)
            .cloned()
            .collect();
        let (config, manifest) = model.documents()?;
        let sources = |blob: &Blob| -> Result<Vec<HttpsUrl>, RegistryError> {
            let file = model
                .files()
                .find(|file| file.sha256 == blob.digest)
                .ok_or(RegistryError::Damaged)?;
            Ok(vec![model.url(file)?])
        };
        self.store(
            &manifest.layers().iter().collect::<Vec<_>>(),
            &hosts,
            transfer,
            &sources,
        )?;
        self.store_local(manifest.config(), &config, transfer.cancellation)?;
        self.publish(model.name(), &manifest)?;
        Ok(manifest)
    }
}

#[cfg(test)]
mod tests;
