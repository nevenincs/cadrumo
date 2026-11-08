//! The local AI's models: the models its caller admits, fetched by the engine itself into
//! the one store both engines read, and checked against what the store and the selected
//! engine's server hold.
//!
//! The engine defines no model. Its caller supplies the admitted models as part, artefact
//! and download size triples, the size as a catalogue entry states it or unknown when
//! none does, and the engine plans, fetches and checks exactly those. An artefact is a
//! name its registry serves, or files the catalogue declares on Hugging Face with their
//! digests and sizes; a plain name is the registry form. A model of unknown size is
//! planned with an unknown download, passes no hardware floor check before it is
//! fetched, and reports progress against the sizes its fetched manifest declares.
//!
//! No local model server runs to acquire a model. The [`registry`] client fetches a
//! registry model's manifest and every layer it names, and the [`huggingface`] source a
//! declared model's files, each verified by Rust against its content digest, the
//! manifest's or the catalogue's, before it enters the store. A fetch that fails in a way
//! that may pass is retried under the setup's retry schedule, and resumes the partial
//! bytes an earlier one left.
//!
//! The store keeps a model as a manifest under
//! `manifests/<host>/<namespace>/<model>/<tag>` in the models folder and its layers as
//! `blobs/sha256-<hex>`. So the quick check reads files only: a manifest whose every layer
//! is stored at its size is present, and a missing manifest or layer is absent. There is
//! no stale model: a manifest other than the one fetched before is the model verified
//! under that name. The full check looks the model up in the server's own list of
//! installed models and then generates one token with it.
//!
//! Each check asks the selected engine's server only. With Ollama selected the quick
//! check is the store alone, and the full check asks the Ollama server. With llama.cpp
//! selected the quick check also needs the running llama-server router's preset to
//! present the model, and the full check has the router list it, load it, generate one
//! token with it and unload it ([`llama_server::check_model`]); no Ollama server is asked.
//!
//! Beside the store the engine keeps one record of its own for each model that states a
//! llama.cpp context: the context the llama-server router loads it with. It lies outside
//! `manifests/` and `blobs/`, the only folders Ollama reads, so Ollama never sees it. A pull
//! records the context of the model it was given, also when the model is already stored
//! whole and nothing is fetched, a new value replaces the old one, and removing a model
//! removes its record. A model with no recorded context is stored and checked as the store
//! reads it, and is not presented to the router, so no context is ever supplied for it.
//!
//! Role fitness, how well a model answers for its role, is no part of this state: it
//! is the consumer's admission check.

use super::{
    LocalAiError, NotRunningCause, ServerCall,
    hardware::Hardware,
    huggingface::{self, HuggingFaceFile, HuggingFaceModel},
    llama_server,
    loopback::Loopback,
    program::Server,
    registry::{self, Registry, RegistryManifest},
};
use crate::{
    error::Error,
    filesystem,
    provisioning::{
        failure::FailureCategory,
        items::{Destination, FULL_CHECK_BUDGET, PROGRAM_PART},
        plan::PlanPart,
        state::{BlockedReason, Observation},
        transfer::{Transfer, TransferEvent},
    },
    value::{HostName, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeSet,
    fmt, io,
    num::NonZeroU32,
    path::{Path, PathBuf},
};

/// The registry, namespace and tag the program reads a name without them as.
pub(super) const DEFAULT_REGISTRY: &str = "registry.ollama.ai";
const DEFAULT_NAMESPACE: &str = "library";
const DEFAULT_TAG: &str = "latest";
/// The longest name, and the longest part of one, the engine accepts.
const NAME_LIMIT: usize = 512;
const PART_LIMIT: usize = 128;
const ROLE_LIMIT: usize = 64;
/// The longest manifest the models folder holds.
pub(super) const MANIFEST_BYTES_LIMIT: u64 = 1024 * 1024;
/// What the one-token check asks.
const CHECK_PROMPT: &str = "Reply with one word.";
/// The folder in the models folder that holds the engine's own records about stored models.
/// Ollama reads only `manifests` and `blobs`, so nothing here reaches it.
pub(super) const CADRUMO_FOLDER: &str = "cadrumo";
/// The folder in [`CADRUMO_FOLDER`] that holds one record of the llama.cpp context of each
/// model that states one, at the model's own `<host>/<namespace>/<model>/<tag>.json`.
pub(super) const CONTEXT_FOLDER: &str = "llamacpp-context";
/// The schema of a context record.
const CONTEXT_SCHEMA: u32 = 1;
/// The longest context record the engine reads.
const CONTEXT_BYTES_LIMIT: u64 = 4096;

/// What the context record of one model holds. Zero cannot be recorded or read.
#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ContextRecord {
    schema: u32,
    llamacpp_context: NonZeroU32,
}

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

    /// The namespace the model is published under in its registry.
    pub fn namespace(&self) -> &str {
        &self.namespace
    }

    /// The model's own name within its namespace.
    pub fn model(&self) -> &str {
        &self.model
    }

    /// The tag naming one edition of the model.
    pub fn tag(&self) -> &str {
        &self.tag
    }

    /// The model's place in the store, `<host>/<namespace>/<model>/<tag>`: where its
    /// manifest lies under `manifests`.
    fn stored_place(&self) -> PathBuf {
        Path::new(self.host.as_str())
            .join(&self.namespace)
            .join(&self.model)
            .join(&self.tag)
    }

    /// Where the models folder under `root` keeps this model's manifest.
    pub(super) fn manifest_path(&self, root: &Path) -> PathBuf {
        root.join("manifests").join(self.stored_place())
    }

    /// Where the models folder under `root` keeps the llama.cpp context recorded for this
    /// model.
    fn context_path(&self, root: &Path) -> PathBuf {
        context_record_path(root, &self.stored_place())
    }
}

/// Where the models folder `root` keeps the llama.cpp context of the model whose manifest
/// lies at `place` under `manifests`: the same place under the context folder, with
/// `.json` added to the tag. The tag is added to, never replaced, since a tag may hold a
/// dot.
fn context_record_path(root: &Path, place: &Path) -> PathBuf {
    let mut record = root
        .join(CADRUMO_FOLDER)
        .join(CONTEXT_FOLDER)
        .join(place)
        .into_os_string();
    record.push(".json");
    PathBuf::from(record)
}

/// Records `context` as the llama.cpp context of the model `name` in the models folder
/// `root`, replacing any earlier value atomically. A link in the way is refused.
pub(crate) fn record_context(
    root: &Path,
    name: &ModelName,
    context: NonZeroU32,
) -> Result<(), Error> {
    let path = name.context_path(root);
    let folder = path
        .parent()
        .ok_or_else(|| invalid("context record location"))?;
    filesystem::refuse_links(folder)?;
    std::fs::create_dir_all(folder)?;
    filesystem::replace_json(
        &path,
        &ContextRecord {
            schema: CONTEXT_SCHEMA,
            llamacpp_context: context,
        },
    )
}

/// The llama.cpp context recorded for the model `name` in the models folder `root`; `None`
/// when there is none, or the record is a link, too long, of another schema, holds more than
/// it should or is zero.
pub(crate) fn recorded_context(root: &Path, name: &ModelName) -> Option<NonZeroU32> {
    let bytes = filesystem::bounded_bytes(&name.context_path(root), CONTEXT_BYTES_LIMIT).ok()?;
    let record: ContextRecord = serde_json::from_slice(&bytes).ok()?;
    (record.schema == CONTEXT_SCHEMA).then_some(record.llamacpp_context)
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

/// One admitted local model: the plan part it is fetched as, its artefact and its download
/// size as its catalogue entry states it, or `None` when no entry states one, and the
/// context llama.cpp loads it with, which the caller states or leaves out.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SelectedModel {
    pub role: String,
    pub artefact: ModelArtefact,
    pub size_bytes: Option<u64>,
    /// The context, in tokens, the llama.cpp router loads the model with. Zero cannot be
    /// stated. A model without one is stored but not presented to the router.
    pub llamacpp_context: Option<NonZeroU32>,
}

impl SelectedModel {
    /// One admitted model its registry serves under `name`; refuses a part that is not a
    /// plain identifier, an empty or malformed name, and a stated zero size.
    pub fn new(
        role: &str,
        name: &str,
        size_bytes: Option<u64>,
        llamacpp_context: Option<NonZeroU32>,
    ) -> Result<Self, Error> {
        Self::of_artefact(
            role,
            ModelArtefact::Registry(ModelName::parse(name)?),
            size_bytes,
            llamacpp_context,
        )
    }

    /// One admitted model of any artefact, under the same refusals as [`Self::new`].
    pub fn of_artefact(
        role: &str,
        artefact: ModelArtefact,
        size_bytes: Option<u64>,
        llamacpp_context: Option<NonZeroU32>,
    ) -> Result<Self, Error> {
        let mut bytes = role.bytes();
        let identifier = role.len() <= ROLE_LIMIT
            && bytes.next().is_some_and(|c| c.is_ascii_lowercase())
            && bytes.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_');
        if !identifier || role == PROGRAM_PART {
            return Err(invalid("role"));
        }
        if size_bytes == Some(0) {
            return Err(invalid("model size"));
        }
        Ok(Self {
            role: role.to_owned(),
            artefact,
            size_bytes,
            llamacpp_context,
        })
    }

    /// The name the store keeps the model under.
    pub fn name(&self) -> &ModelName {
        self.artefact.name()
    }

    /// The bytes the model downloads as far as is known before it is fetched: the size its
    /// catalogue entry states, else the sizes a Hugging Face declaration pins; `None` for
    /// a registry model no entry sizes.
    pub fn stated_bytes(&self) -> Option<u64> {
        self.size_bytes.or_else(|| self.artefact.declared_bytes())
    }
}

/// What a catalogue model is fetched as: a name its registry serves, whose manifest
/// states the layers and their digests, or files declared on Hugging Face with the
/// digests and sizes the catalogue pins.
///
/// The catalogue states it in one of two JSON forms:
/// `{"source": "registry", "name": "<name>"}`, or `{"source": "huggingface",
/// "repository": "<owner>/<repo>", "revision": "<commit>", "model": <file>,
/// "projector": <file>}`, each `<file>` being `{"file": "<name>.gguf", "sha256": "<hex>",
/// "size_bytes": <bytes>}` and the projector left out for a model without one.
#[derive(Clone, Debug, Eq, PartialEq, Deserialize)]
#[serde(try_from = "ArtefactDocument")]
pub enum ModelArtefact {
    Registry(ModelName),
    HuggingFace(HuggingFaceModel),
}

impl ModelArtefact {
    /// The name the models folder keeps the model under.
    pub fn name(&self) -> &ModelName {
        match self {
            Self::Registry(name) => name,
            Self::HuggingFace(model) => model.name(),
        }
    }

    /// The hosts fetching the model may reach, which a plan names as its sources.
    pub fn source_hosts(&self) -> BTreeSet<HostName> {
        match self {
            Self::Registry(name) => registry::source_hosts(name),
            Self::HuggingFace(_) => huggingface::source_hosts(),
        }
    }

    /// The source hosts as a plan lists them: the host the model is addressed at first,
    /// then the hosts it may be redirected to.
    pub fn plan_hosts(&self) -> Vec<HostName> {
        let addressed = self.name().host().clone();
        let mut hosts: Vec<HostName> = self
            .source_hosts()
            .into_iter()
            .filter(|host| *host != addressed)
            .collect();
        hosts.insert(0, addressed);
        hosts
    }

    /// The bytes the artefact's own declaration pins: a Hugging Face model's files. A
    /// registry model's sizes are known only once its manifest is fetched.
    pub fn declared_bytes(&self) -> Option<u64> {
        match self {
            Self::Registry(_) => None,
            Self::HuggingFace(model) => Some(model.download_bytes()),
        }
    }

    /// Whether `other` is the same artefact: the same registry name regardless of case,
    /// or the same Hugging Face declaration.
    pub fn same(&self, other: &Self) -> bool {
        match (self, other) {
            (Self::Registry(name), Self::Registry(other)) => name.same(other),
            (Self::HuggingFace(model), Self::HuggingFace(other)) => model == other,
            _ => false,
        }
    }
}

#[derive(Deserialize)]
#[serde(tag = "source", deny_unknown_fields)]
enum ArtefactDocument {
    #[serde(rename = "registry")]
    Registry { name: String },
    #[serde(rename = "huggingface")]
    HuggingFace {
        repository: String,
        revision: String,
        model: FileDocument,
        #[serde(default)]
        projector: Option<FileDocument>,
    },
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct FileDocument {
    file: String,
    sha256: String,
    size_bytes: u64,
}

impl TryFrom<FileDocument> for HuggingFaceFile {
    type Error = Error;

    fn try_from(document: FileDocument) -> Result<Self, Error> {
        Self::new(&document.file, &document.sha256, document.size_bytes)
    }
}

impl TryFrom<ArtefactDocument> for ModelArtefact {
    type Error = Error;

    fn try_from(document: ArtefactDocument) -> Result<Self, Error> {
        Ok(match document {
            ArtefactDocument::Registry { name } => Self::Registry(ModelName::parse(&name)?),
            ArtefactDocument::HuggingFace {
                repository,
                revision,
                model,
                projector,
            } => Self::HuggingFace(HuggingFaceModel::new(
                &repository,
                &revision,
                model.try_into()?,
                projector.map(HuggingFaceFile::try_from).transpose()?,
            )?),
        })
    }
}

/// The local models the person selected, at most one per role, in role order. Empty
/// when no local role has a selection: then there is nothing to fetch, and no fallback.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct LocalModels(Vec<SelectedModel>);

impl LocalModels {
    /// Refuses a role selected twice, and a model selected for two roles under two
    /// different sizes, artefacts or llama.cpp contexts, which no one catalogue entry can
    /// state: the store keeps one context for one model.
    pub fn new(mut models: Vec<SelectedModel>) -> Result<Self, Error> {
        models.sort_by(|a, b| a.role.cmp(&b.role));
        if models.windows(2).any(|pair| pair[0].role == pair[1].role) {
            return Err(invalid("a role is selected once"));
        }
        for (index, model) in models.iter().enumerate() {
            if models[..index].iter().any(|other| {
                other.name().same(model.name())
                    && (other.size_bytes != model.size_bytes
                        || other.llamacpp_context != model.llamacpp_context
                        || !other.artefact.same(&model.artefact))
            }) {
                return Err(invalid("a model has one size, one source and one context"));
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

    /// Every host fetching the selected models may reach.
    pub fn hosts(&self) -> BTreeSet<HostName> {
        self.0
            .iter()
            .flat_map(|model| model.artefact.source_hosts())
            .collect()
    }
}

/// A model the store holds whole after a pull, and the bytes its progress was reported
/// against: the sizes its fetched manifest or declaration states, each distinct blob once.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Pulled {
    pub observation: Observation,
    pub bytes: u64,
}

/// The selected models and where the program keeps them.
#[derive(Clone, Debug)]
pub struct Models {
    selection: LocalModels,
    root: PathBuf,
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

    /// One plan part per selected role, in role order: the selected model, from every host
    /// its fetch may reach, into the models folder, at the size stated before it is
    /// fetched. Roles that share a model share its target, so the plan counts the
    /// download once.
    pub fn plan_parts(&self) -> Vec<PlanPart> {
        self.selection
            .as_slice()
            .iter()
            .map(|model| PlanPart {
                part_id: model.role.clone(),
                download_bytes: model.stated_bytes(),
                source_hosts: model.artefact.plan_hosts(),
                destination: Some(Destination::OllamaModels),
                installs_outside_program: false,
                target_version: Some(model.name().to_string()),
            })
            .collect()
    }

    /// The quick check of `model`: its manifest and layers on disk, no server. A
    /// computer whose memory cannot hold the model's stated size is held back first;
    /// a model of unknown size has nothing to hold it back by.
    pub fn observe_quick(&self, model: &SelectedModel, hardware: &Hardware) -> Observation {
        if model
            .size_bytes
            .is_some_and(|size| hardware.below_floor(size))
        {
            return Observation::Blocked(BlockedReason::Hardware);
        }
        self.installed(model.name())
    }

    /// The full check of `model` on `server`: the quick check, the server's own list of
    /// installed models, and one generated token.
    pub fn observe_full(
        &self,
        server: &Server,
        model: &SelectedModel,
        hardware: &Hardware,
    ) -> Observation {
        self.check_full(server, model, hardware)
            .unwrap_or_else(|error| Observation::Failed(error.category()))
    }

    /// The full check as [`Models::observe_full`] reads it, with a failed request kept as
    /// the error that says what failed, for a setup that records why it stopped.
    pub fn check_full(
        &self,
        server: &Server,
        model: &SelectedModel,
        hardware: &Hardware,
    ) -> Result<Observation, LocalAiError> {
        let quick = self.observe_quick(model, hardware);
        if quick != Observation::Present {
            return Ok(quick);
        }
        if !listed(server, model.name())? {
            return Ok(Observation::Absent);
        }
        Ok(if generate_one_token(server, model.name())? {
            Observation::Present
        } else {
            Observation::Absent
        })
    }

    /// The quick check of `model` while llama.cpp is the selected engine: the quick check
    /// of the store, then whether the router recorded in `router`, the llama-server's
    /// folder, presents the model. A model stored whole that the router does not present
    /// yet is absent, and with no router recorded there it reads `program_not_running`.
    /// Files only: no server is asked.
    pub fn observe_presented(
        &self,
        model: &SelectedModel,
        hardware: &Hardware,
        router: &Path,
    ) -> Observation {
        let stored = self.observe_quick(model, hardware);
        if stored != Observation::Present {
            return stored;
        }
        match llama_server::presented_by_router(router, model.name()) {
            Some(true) => Observation::Present,
            Some(false) => Observation::Absent,
            None => Observation::Failed(FailureCategory::ProgramNotRunning),
        }
    }

    /// The full check of `model` on the llama-server router recorded in `router`: the
    /// quick check as [`Models::observe_presented`] reads it, then the router's own list,
    /// a load, one generated token and the unload.
    pub fn observe_full_on_router(
        &self,
        router: &Path,
        model: &SelectedModel,
        hardware: &Hardware,
    ) -> Observation {
        self.check_full_on_router(router, model, hardware)
            .unwrap_or_else(|error| Observation::Failed(error.category()))
    }

    /// The full check as [`Models::observe_full_on_router`] reads it, with a failed
    /// request kept as the error that says what failed, for a setup that records why it
    /// stopped.
    pub fn check_full_on_router(
        &self,
        router: &Path,
        model: &SelectedModel,
        hardware: &Hardware,
    ) -> Result<Observation, LocalAiError> {
        let quick = self.observe_presented(model, hardware, router);
        if quick != Observation::Present {
            return Ok(quick);
        }
        let generated =
            llama_server::check_model(router, model.name(), CHECK_PROMPT, FULL_CHECK_BUDGET)?;
        Ok(if generated {
            Observation::Present
        } else {
            Observation::Absent
        })
    }

    /// Fetches `model` into the models folder unless its manifest is already there whole,
    /// through `transfer`, whose hosts are the plan's approved ones; then reads it back
    /// as the quick check does. No server is asked: the registry client or the Hugging
    /// Face source fetches and verifies every byte. Progress counts against the sizes the
    /// fetched manifest or the declaration states, and [`Pulled::bytes`] is that total, so
    /// a setup that fetches several models advances its running offset by what each
    /// reported rather than by the size a catalogue stated.
    ///
    /// The llama.cpp context the model states is recorded whether or not anything was
    /// fetched, so a model stored before it had one needs no new download to be presented. A
    /// pull of a model that states none leaves any earlier record as it was.
    pub fn pull(
        &self,
        model: &SelectedModel,
        transfer: &mut Transfer<'_>,
    ) -> Result<Pulled, LocalAiError> {
        if self.installed(model.name()) == Observation::Present {
            self.record_stated_context(model)?;
            let bytes = self.download_bytes(model);
            if let Some(size) = bytes {
                (transfer.events)(TransferEvent::Progress {
                    completed: size,
                    total: size,
                });
            }
            return Ok(Pulled {
                observation: Observation::Present,
                bytes: bytes.unwrap_or(0),
            });
        }
        transfer.cancellation.check()?;
        let registry = Registry::new(self.root.clone());
        let bytes = match &model.artefact {
            ModelArtefact::Registry(name) => registry.pull(name, transfer)?.total_bytes(),
            ModelArtefact::HuggingFace(declared) => {
                registry.pull_hugging_face(declared, transfer)?;
                declared.download_bytes()
            }
        };
        // A manifest the store does not hold whole is not the model the plan named.
        if self.installed(model.name()) != Observation::Present {
            return Err(LocalAiError::Failed(FailureCategory::DamagedDownload));
        }
        self.record_stated_context(model)?;
        Ok(Pulled {
            observation: Observation::Present,
            bytes,
        })
    }

    /// Records the llama.cpp context `model` states, if it states one.
    fn record_stated_context(&self, model: &SelectedModel) -> Result<(), LocalAiError> {
        match model.llamacpp_context {
            Some(context) => {
                record_context(&self.root, model.name(), context).map_err(LocalAiError::Engine)
            }
            None => Ok(()),
        }
    }

    /// Removes every selected model the models folder holds: its manifest and its recorded
    /// llama.cpp context, then the partial bytes of any fetch that never finished and every
    /// layer that no manifest left there uses, which includes layers an earlier removal or
    /// fetch left unused. A model kept beside them keeps its layers and its context, and when
    /// any kept manifest cannot be read, every layer stays. The caller holds the local AI
    /// item's writer lock, so no fetch is writing to the store.
    pub fn remove(&self) -> Result<(), Error> {
        self.remove_manifests(
            &self
                .selection
                .as_slice()
                .iter()
                .map(|model| model.name().manifest_path(&self.root))
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
        let mut kept = BTreeSet::new();
        let mut unreadable = false;
        let mut pending = Vec::new();
        if std::fs::symlink_metadata(&manifests).is_ok() {
            pending.push(manifests);
        }
        while let Some(folder) = pending.pop() {
            for entry in std::fs::read_dir(&folder)? {
                let path = entry?.path();
                let meta = std::fs::symlink_metadata(&path)?;
                filesystem::refuse_metadata_links(&meta)?;
                if meta.is_dir() {
                    pending.push(path);
                    continue;
                }
                if selected.contains(&path) {
                    std::fs::remove_file(&path)?;
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
                unreadable |= layers.is_none();
                kept.extend(
                    layers
                        .into_iter()
                        .flatten()
                        .filter_map(|digest| layer_hex(&digest)),
                );
            }
        }
        // A removed model keeps no context record, whether or not its manifest was there.
        for manifest in selected {
            self.remove_context_of(manifest)?;
        }
        // Bytes of a fetch that never finished belong to no manifest, kept or not.
        self.clear_partial()?;
        if unreadable {
            return Ok(());
        }
        self.remove_unreferenced_blobs(&kept)
    }

    /// Deletes the recorded llama.cpp context of the model whose manifest was at `manifest`,
    /// when it has one.
    fn remove_context_of(&self, manifest: &Path) -> Result<(), Error> {
        let Ok(place) = manifest.strip_prefix(self.root.join("manifests")) else {
            return Ok(());
        };
        let record = context_record_path(&self.root, place);
        filesystem::refuse_links(&record)?;
        remove_if_present(&record)
    }

    /// Deletes the files the partial folder holds: blobs still arriving and manifests not
    /// yet published.
    fn clear_partial(&self) -> Result<(), Error> {
        let folder = self.root.join(registry::PARTIAL);
        filesystem::refuse_links(&folder)?;
        let entries = match std::fs::read_dir(&folder) {
            Ok(entries) => entries,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
            Err(error) => return Err(error.into()),
        };
        for entry in entries {
            let path = entry?.path();
            let meta = std::fs::symlink_metadata(&path)?;
            filesystem::refuse_metadata_links(&meta)?;
            if meta.is_file() {
                remove_if_present(&path)?;
            }
        }
        Ok(())
    }

    /// Deletes each stored blob whose digest no manifest in `kept` names.
    fn remove_unreferenced_blobs(&self, kept: &BTreeSet<String>) -> Result<(), Error> {
        let folder = self.root.join("blobs");
        filesystem::refuse_links(&folder)?;
        let entries = match std::fs::read_dir(&folder) {
            Ok(entries) => entries,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(()),
            Err(error) => return Err(error.into()),
        };
        for entry in entries {
            let path = entry?.path();
            let hex = path
                .file_name()
                .and_then(|name| name.to_str())
                .and_then(|name| name.strip_prefix("sha256-"))
                .and_then(|hex| Sha256Digest::new(hex).ok());
            let Some(hex) = hex else {
                continue;
            };
            if kept.contains(hex.as_str()) {
                continue;
            }
            filesystem::refuse_links(&path)?;
            remove_if_present(&path)?;
        }
        Ok(())
    }

    /// The bytes `model` downloads: the size stated before it is fetched, else the
    /// distinct blobs the manifest the models folder holds for it names; `None` when
    /// neither says.
    pub fn download_bytes(&self, model: &SelectedModel) -> Option<u64> {
        model.stated_bytes().or_else(|| {
            let path = model.name().manifest_path(&self.root);
            let bytes = filesystem::bounded_bytes(&path, MANIFEST_BYTES_LIMIT).ok()?;
            Some(RegistryManifest::parse(bytes).ok()?.total_bytes())
        })
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

/// The lowercase hex of a manifest's layer `digest`, `None` when it is not a SHA-256 one.
fn layer_hex(digest: &str) -> Option<String> {
    let hex = digest.strip_prefix("sha256:")?;
    Some(Sha256Digest::new(hex).ok()?.as_str().to_owned())
}

fn remove_if_present(path: &Path) -> Result<(), Error> {
    match std::fs::remove_file(path) {
        Err(error) if error.kind() != io::ErrorKind::NotFound => Err(error.into()),
        _ => Ok(()),
    }
}

fn blob_stored(root: &Path, layer: &Layer) -> bool {
    let Some(hex) = layer_hex(&layer.digest) else {
        return false;
    };
    let path = root.join("blobs").join(format!("sha256-{hex}"));
    filesystem::refuse_links(&path).is_ok()
        && std::fs::metadata(&path).is_ok_and(|meta| meta.is_file() && meta.len() == layer.size)
}

/// The program is not running as far as `call` could tell: the exchange over `loopback`
/// failed with `error`, under the bound that client enforced.
pub(super) fn request_failed(
    loopback: &Loopback,
    call: ServerCall,
    error: &std::io::Error,
) -> LocalAiError {
    LocalAiError::NotRunning(NotRunningCause::Request {
        call,
        failure: loopback.failure(error),
    })
}

/// Whether the server's own list of installed models holds `name`.
fn listed(server: &Server, name: &ModelName) -> Result<bool, LocalAiError> {
    let loopback = server.loopback();
    let (status, body) = loopback
        .get("/api/tags")
        .map_err(|error| request_failed(&loopback, ServerCall::ListModels, &error))?;
    if status != 200 {
        return Err(LocalAiError::NotRunning(NotRunningCause::ListStatus {
            status,
        }));
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
    let loopback = server.loopback().with_io_timeout(FULL_CHECK_BUDGET);
    let (status, body) = loopback
        .post("/api/generate", request.to_string().as_bytes())
        .map_err(|error| request_failed(&loopback, ServerCall::Generate, &error))?;
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
