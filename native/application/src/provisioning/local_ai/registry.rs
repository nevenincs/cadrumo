//! The local AI's registry client: a model fetched from its Ollama registry by the engine
//! itself, with no model server running, and written into the models folder in the
//! layout the program keeps.
//!
//! A model's name resolves to its registry host, namespace, model and tag. Its manifest
//! comes from `https://<host>/v2/<namespace>/<model>/manifests/<tag>`, asked for in the
//! Docker distribution v2 media type, and names the config and every layer by SHA-256
//! digest and size. Each of them comes from `/v2/<namespace>/<model>/blobs/<digest>`
//! through the pinned transfer, with its hop, retry, resume and proxy rules. The registry
//! redirects a blob to its storage host, so a hop is followed only to a host that is both
//! declared here for that registry and in the approved plan.
//!
//! Integrity is the manifest's: a blob is accepted only at the size and digest the
//! manifest states for it. It is fetched into `partial/sha256-<hex>`, beside the store
//! and never inside `blobs`, which the program may clear of files no manifest names. A
//! partial blob that survived an interruption is resumed with a `Range` request, and its
//! whole content is hashed again before it is accepted. A verified blob is renamed into
//! `blobs/sha256-<hex>`; damaged bytes are deleted. A blob already stored at its size and
//! digest is kept and not fetched again. The manifest is written last and atomically,
//! under `manifests/<host>/<namespace>/<model>/<tag>`, so a model the folder names is
//! whole, and the program and the quick check both read it.
//!
//! Progress counts the bytes held of the whole model out of the sum of the sizes the
//! manifest states, each distinct blob counted once, and never goes back.
//!
//! The caller holds the local AI item's writer lock, so no other writer shares the
//! partial files or the store while a pull runs.

use super::{
    LocalAiError,
    models::{DEFAULT_REGISTRY, MANIFEST_BYTES_LIMIT, ModelName},
};
use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    provisioning::{
        connection::Network,
        failure::{FailureCategory, TransferFailure},
        http::{self, Body, Framing},
        transfer::{self, MAX_REDIRECTS, Pinned, Transfer, TransferEvent},
        url::HttpsUrl,
    },
    value::{HostName, Sha256Digest},
};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fmt,
    fs::{self, File},
    io::{self, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

/// The manifest media type a pull asks the registry for.
pub const MANIFEST_MEDIA_TYPE: &str = "application/vnd.docker.distribution.manifest.v2+json";

/// The storage hosts the default registry redirects a blob request to.
const DEFAULT_REGISTRY_BLOB_HOSTS: &[&str] =
    &["dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com"];

/// The folder beside the store that holds blobs still arriving and manifests not yet
/// published.
pub(super) const PARTIAL: &str = "partial";
/// The most layers one manifest may name.
const LAYERS_LIMIT: usize = 256;
const DIGEST_PREFIX: &str = "sha256:";

/// The hosts a pull of `name` may reach: its registry and, for the default registry, the
/// storage hosts that registry redirects blobs to. A plan names these as the model's
/// sources.
pub fn source_hosts(name: &ModelName) -> BTreeSet<HostName> {
    let mut hosts = BTreeSet::from([name.host().clone()]);
    if name.host().as_str() == DEFAULT_REGISTRY {
        hosts.extend(
            DEFAULT_REGISTRY_BLOB_HOSTS
                .iter()
                .filter_map(|host| HostName::new(*host).ok()),
        );
    }
    hosts
}

/// Why a registry pull did not complete, in the closed failure categories.
#[derive(Debug)]
pub enum RegistryError {
    /// The registry has no such model or tag, or no blob its manifest names.
    NotFound,
    /// The registry or its storage host could not be reached, refused a hop, or broke
    /// the exchange; the failure carries its category, status and attempts.
    Network(TransferFailure),
    /// A manifest that is not one, or a blob whose bytes are not the size and digest
    /// the manifest states.
    Damaged,
    /// The models folder could not take the bytes: full, refused, or failing.
    Disk(TransferFailure),
    /// The person stopped the pull.
    Cancelled,
    /// An engine refusal outside those categories, such as a linked path.
    Engine(Error),
}

impl RegistryError {
    /// The closed category a surface words this failure with. A missing model reads as
    /// `unexpected`, as the program's own "manifest unknown" does.
    pub fn category(&self) -> FailureCategory {
        match self {
            Self::NotFound | Self::Engine(_) => FailureCategory::Unexpected,
            Self::Network(failure) | Self::Disk(failure) => failure.category,
            Self::Damaged => FailureCategory::DamagedDownload,
            Self::Cancelled => FailureCategory::Cancelled,
        }
    }
}

impl From<Error> for RegistryError {
    fn from(error: Error) -> Self {
        match error {
            Error::Cancelled => Self::Cancelled,
            Error::Download(failure) => match (failure.category, failure.http_status) {
                (FailureCategory::DamagedDownload, _) => Self::Damaged,
                (FailureCategory::Cancelled, _) => Self::Cancelled,
                (_, Some(404)) => Self::NotFound,
                (FailureCategory::DiskFull | FailureCategory::NoPermission, _) => {
                    Self::Disk(failure)
                }
                _ => Self::Network(failure),
            },
            Error::Io(error) => Self::from(error),
            Error::Integrity(_) | Error::LimitExceeded => Self::Damaged,
            other => Self::Engine(other),
        }
    }
}

impl From<io::Error> for RegistryError {
    fn from(error: io::Error) -> Self {
        Self::Disk(transfer::file_failure(&error))
    }
}

impl From<RegistryError> for LocalAiError {
    fn from(error: RegistryError) -> Self {
        match error {
            RegistryError::Cancelled => Self::Engine(Error::Cancelled),
            RegistryError::Engine(error) => Self::Engine(error),
            other => Self::Failed(other.category()),
        }
    }
}

impl fmt::Display for RegistryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound => f.write_str("model registry: no such model"),
            Self::Engine(error) => write!(f, "model registry: {error}"),
            other => write!(f, "model registry: {}", other.category()),
        }
    }
}

impl std::error::Error for RegistryError {}

/// One blob a manifest names: the config or a layer.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Blob {
    pub media_type: String,
    pub digest: Sha256Digest,
    pub size: u64,
}

impl Blob {
    /// The blob's file name in the store and in the partial folder.
    pub(super) fn file_name(&self) -> String {
        format!("sha256-{}", self.digest)
    }

    /// The blob's digest as the registry addresses it and a manifest names it.
    pub(super) fn reference(&self) -> String {
        format!("{DIGEST_PREFIX}{}", self.digest)
    }
}

#[derive(Deserialize)]
struct Descriptor {
    #[serde(rename = "mediaType")]
    media_type: String,
    digest: String,
    size: u64,
}

#[derive(Deserialize)]
struct Document {
    #[serde(rename = "schemaVersion")]
    schema_version: u32,
    config: Descriptor,
    layers: Vec<Descriptor>,
}

/// A model's registry manifest: the exact bytes the registry served, and the config and
/// layers they name.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RegistryManifest {
    bytes: Vec<u8>,
    config: Blob,
    layers: Vec<Blob>,
}

impl RegistryManifest {
    /// Reads a served manifest; refuses one that is too long, is not schema version 2,
    /// names no layer or too many, names a blob by anything but a lowercase SHA-256
    /// digest, gives one digest two sizes, or whose sizes cannot be summed.
    pub fn parse(bytes: Vec<u8>) -> Result<Self, RegistryError> {
        if bytes.len() as u64 > MANIFEST_BYTES_LIMIT {
            return Err(RegistryError::Damaged);
        }
        let document: Document =
            serde_json::from_slice(&bytes).map_err(|_| RegistryError::Damaged)?;
        if document.schema_version != 2
            || document.layers.is_empty()
            || document.layers.len() > LAYERS_LIMIT
        {
            return Err(RegistryError::Damaged);
        }
        let config = blob(document.config)?;
        let layers = document
            .layers
            .into_iter()
            .map(blob)
            .collect::<Result<Vec<_>, _>>()?;
        let manifest = Self {
            bytes,
            config,
            layers,
        };
        let mut sizes: BTreeMap<String, u64> = BTreeMap::new();
        for blob in manifest.all() {
            if *sizes
                .entry(blob.digest.as_str().to_owned())
                .or_insert(blob.size)
                != blob.size
            {
                return Err(RegistryError::Damaged);
            }
        }
        if sizes
            .values()
            .try_fold(0u64, |sum, size| sum.checked_add(*size))
            .is_none()
        {
            return Err(RegistryError::Damaged);
        }
        Ok(manifest)
    }

    /// The bytes as the registry served them, which the store keeps unchanged.
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    pub fn config(&self) -> &Blob {
        &self.config
    }

    pub fn layers(&self) -> &[Blob] {
        &self.layers
    }

    /// Every distinct blob the manifest names, config first, each once.
    pub fn blobs(&self) -> Vec<&Blob> {
        let mut blobs: Vec<&Blob> = Vec::new();
        for blob in self.all() {
            if !blobs.iter().any(|held| held.digest == blob.digest) {
                blobs.push(blob);
            }
        }
        blobs
    }

    /// The bytes a pull holds once the model is whole: the sizes of its distinct blobs.
    pub fn total_bytes(&self) -> u64 {
        self.blobs()
            .iter()
            .fold(0u64, |sum, blob| sum.saturating_add(blob.size))
    }

    fn all(&self) -> impl Iterator<Item = &Blob> {
        std::iter::once(&self.config).chain(&self.layers)
    }
}

fn blob(descriptor: Descriptor) -> Result<Blob, RegistryError> {
    let hex = descriptor
        .digest
        .strip_prefix(DIGEST_PREFIX)
        .ok_or(RegistryError::Damaged)?;
    let digest = Sha256Digest::new(hex).map_err(|_| RegistryError::Damaged)?;
    if digest.as_str() != hex || descriptor.media_type.is_empty() {
        return Err(RegistryError::Damaged);
    }
    Ok(Blob {
        media_type: descriptor.media_type,
        digest,
        size: descriptor.size,
    })
}

/// The bytes a pull has reported, so progress across blobs only grows.
struct Tally {
    /// Bytes of the blobs already held.
    done: u64,
    total: u64,
    reported: u64,
}

impl Tally {
    /// Reports `completed` bytes of the whole model, never fewer than before.
    fn report(&mut self, events: &mut dyn FnMut(TransferEvent), completed: u64) {
        self.reported = completed.min(self.total).max(self.reported);
        events(TransferEvent::Progress {
            completed: self.reported,
            total: self.total,
        });
    }
}

/// The models folder a registry pull writes into.
#[derive(Clone, Debug)]
pub struct Registry {
    root: PathBuf,
}

impl Registry {
    /// Pulls into `root`, the installation's models folder.
    pub fn new(root: PathBuf) -> Self {
        Self { root }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Fetches and reads `name`'s manifest, writing nothing.
    pub fn manifest(
        &self,
        name: &ModelName,
        transfer: &mut Transfer<'_>,
    ) -> Result<RegistryManifest, RegistryError> {
        let hosts = admitted_hosts(name, transfer.hosts);
        fetch_manifest(name, &hosts, transfer)
    }

    /// Pulls `name` into the models folder: its manifest, each blob not already stored
    /// whole, and then the manifest itself. Returns the manifest the store now holds.
    /// A failure leaves resumable partial bytes, never damaged ones, and publishes no
    /// manifest.
    pub fn pull(
        &self,
        name: &ModelName,
        transfer: &mut Transfer<'_>,
    ) -> Result<RegistryManifest, RegistryError> {
        let hosts = admitted_hosts(name, transfer.hosts);
        let manifest = fetch_manifest(name, &hosts, transfer)?;
        let sources = |blob: &Blob| -> Result<Vec<HttpsUrl>, RegistryError> {
            Ok(vec![repository_url(
                name,
                &format!("blobs/{}", blob.reference()),
            )?])
        };
        self.store(&manifest.blobs(), &hosts, transfer, &sources)?;
        self.publish(name, &manifest)?;
        Ok(manifest)
    }

    /// Stores each of `blobs` the store does not already hold whole, fetched from the
    /// addresses `sources` names for it and only through `hosts`. Progress counts the
    /// bytes held out of the sum of their sizes. A failure leaves resumable partial
    /// bytes, never damaged ones.
    pub(super) fn store(
        &self,
        blobs: &[&Blob],
        hosts: &BTreeSet<HostName>,
        transfer: &mut Transfer<'_>,
        sources: &dyn Fn(&Blob) -> Result<Vec<HttpsUrl>, RegistryError>,
    ) -> Result<(), RegistryError> {
        let (stored_blobs, partials) = self.folders()?;
        let mut tally = Tally {
            done: 0,
            total: blobs
                .iter()
                .fold(0u64, |sum, blob| sum.saturating_add(blob.size)),
            reported: 0,
        };
        tally.report(&mut *transfer.events, 0);
        for &blob in blobs {
            transfer.cancellation.check()?;
            let stored = stored_blobs.join(blob.file_name());
            if !verified(&stored, blob, transfer.cancellation)? {
                let partial = partials.join(blob.file_name());
                fetch_blob(&sources(blob)?, blob, hosts, transfer, &partial, &mut tally)?;
                filesystem::refuse_links(&stored)?;
                fs::rename(&partial, &stored)?;
                sync_folder(&stored_blobs)?;
            }
            tally.done = tally.done.saturating_add(blob.size);
            let done = tally.done;
            tally.report(&mut *transfer.events, done);
        }
        Ok(())
    }

    /// Stores `bytes`, which the engine wrote itself, as `blob`, unless the store already
    /// holds it whole. Bytes that are not the blob's size and digest are refused.
    pub(super) fn store_local(
        &self,
        blob: &Blob,
        bytes: &[u8],
        cancellation: &Cancellation,
    ) -> Result<(), RegistryError> {
        if bytes.len() as u64 != blob.size || Sha256Digest::of(bytes) != blob.digest {
            return Err(RegistryError::Damaged);
        }
        let (stored_blobs, partials) = self.folders()?;
        let stored = stored_blobs.join(blob.file_name());
        if verified(&stored, blob, cancellation)? {
            return Ok(());
        }
        let partial = partials.join(blob.file_name());
        filesystem::refuse_links(&partial)?;
        filesystem::refuse_links(&stored)?;
        let written = write_synced(&partial, bytes).and_then(|()| fs::rename(&partial, &stored));
        if written.is_err() {
            let _ = fs::remove_file(&partial);
        }
        written?;
        sync_folder(&stored_blobs)?;
        Ok(())
    }

    /// The store's blob folder and the partial folder beside it, both created.
    fn folders(&self) -> Result<(PathBuf, PathBuf), RegistryError> {
        let blobs = self.root.join("blobs");
        let partials = self.root.join(PARTIAL);
        for folder in [&blobs, &partials] {
            filesystem::refuse_links(folder)?;
            fs::create_dir_all(folder)?;
        }
        Ok((blobs, partials))
    }

    /// Writes `manifest` as `name`'s, atomically: it is staged in the partial folder and
    /// renamed into place, so the manifests folder never holds a partial document.
    pub(super) fn publish(
        &self,
        name: &ModelName,
        manifest: &RegistryManifest,
    ) -> Result<(), RegistryError> {
        static WRITES: AtomicU64 = AtomicU64::new(0);
        let path = name.manifest_path(&self.root);
        let folder = path
            .parent()
            .ok_or_else(|| Error::Invalid("model manifest folder".into()))?;
        let partials = self.root.join(PARTIAL);
        let pending = partials.join(format!(
            "manifest-{}-{}",
            std::process::id(),
            WRITES.fetch_add(1, Ordering::Relaxed)
        ));
        filesystem::refuse_links(&path)?;
        filesystem::refuse_links(&pending)?;
        fs::create_dir_all(folder)?;
        fs::create_dir_all(&partials)?;
        let written =
            write_synced(&pending, manifest.bytes()).and_then(|()| fs::rename(&pending, &path));
        if written.is_err() {
            let _ = fs::remove_file(&pending);
        }
        written?;
        sync_folder(folder)?;
        Ok(())
    }
}

/// The hosts a pull of `name` may reach under this plan: declared for its registry and
/// approved.
fn admitted_hosts(name: &ModelName, approved: &BTreeSet<HostName>) -> BTreeSet<HostName> {
    source_hosts(name).intersection(approved).cloned().collect()
}

fn repository_url(name: &ModelName, rest: &str) -> Result<HttpsUrl, RegistryError> {
    HttpsUrl::parse(&format!(
        "https://{}/v2/{}/{}/{rest}",
        name.host(),
        name.namespace(),
        name.model()
    ))
    .map_err(RegistryError::from)
}

/// The manifest, retried under the transfer's schedule while the failure is transient.
fn fetch_manifest(
    name: &ModelName,
    hosts: &BTreeSet<HostName>,
    transfer: &mut Transfer<'_>,
) -> Result<RegistryManifest, RegistryError> {
    let url = repository_url(name, &format!("manifests/{}", name.tag()))?;
    let mut attempt = 1;
    loop {
        transfer.cancellation.check()?;
        let failure = match get_manifest(transfer.network, hosts, &url, transfer.cancellation) {
            Ok(bytes) => return RegistryManifest::parse(bytes),
            Err(RegistryError::Network(failure)) => failure,
            Err(other) => return Err(other),
        };
        let last = TransferFailure {
            transient: false,
            attempts: attempt,
            ..failure
        };
        if !failure.transient || attempt >= transfer.policy.max_attempts {
            return Err(RegistryError::Network(last));
        }
        let delay = transfer.policy.delay(attempt, transfer.pacing.jitter());
        if transfer.pacing.elapsed() + delay > transfer.policy.window {
            return Err(RegistryError::Network(last));
        }
        attempt += 1;
        (transfer.events)(TransferEvent::Retrying { attempt, delay });
        transfer.pacing.wait(delay, transfer.cancellation)?;
    }
}

/// One request chain for the manifest at `source`, under the transfer's hop policy.
fn get_manifest(
    network: &Network,
    hosts: &BTreeSet<HostName>,
    source: &HttpsUrl,
    cancellation: &Cancellation,
) -> Result<Vec<u8>, RegistryError> {
    let stop = move || cancellation.is_cancelled();
    let network_failure =
        |error: &io::Error| RegistryError::Network(transfer::network_failure(error));
    let mut url = source.clone();
    let mut redirects = 0;
    loop {
        cancellation.check()?;
        if !(url.default_port() && hosts.contains(url.host())) {
            return Err(RegistryError::Network(TransferFailure::final_(
                FailureCategory::BlockedByNetwork,
            )));
        }
        let mut stream = match network.open_unless_cancelled(&url, None, Some(cancellation)) {
            Ok(stream) => stream,
            Err(failure) => {
                cancellation.check()?;
                return Err(RegistryError::Network(transfer::connect_failure(&failure)));
            }
        };
        http::write_request(
            &mut stream,
            "GET",
            url.target(),
            &url.authority(),
            &[("Accept", MANIFEST_MEDIA_TYPE)],
        )
        .map_err(|error| network_failure(&error))?;
        let mut reader = BufReader::new(stream);
        let head = http::read_head(&mut reader, &stop);
        cancellation.check()?;
        let head = head.map_err(|error| network_failure(&error))?;
        if head.redirect() {
            redirects += 1;
            let next = head
                .header("location")
                .map(|location| url.redirect(location));
            match next {
                Some(Ok(next)) if redirects <= MAX_REDIRECTS => {
                    url = next;
                    continue;
                }
                _ => {
                    return Err(RegistryError::Network(
                        TransferFailure::final_(FailureCategory::BlockedByNetwork)
                            .with_status(head.status),
                    ));
                }
            }
        }
        if head.status == 404 {
            return Err(RegistryError::NotFound);
        }
        if let Some(failure) = TransferFailure::of_status(head.status) {
            return Err(RegistryError::Network(failure));
        }
        if head.status != 200 {
            return Err(RegistryError::Network(
                TransferFailure::final_(FailureCategory::Unexpected).with_status(head.status),
            ));
        }
        let framing = Framing::of(&head).map_err(|error| network_failure(&error))?;
        if matches!(framing, Framing::Length(length) if length > MANIFEST_BYTES_LIMIT) {
            return Err(RegistryError::Damaged);
        }
        let mut bytes = Vec::new();
        let read = Body::new(reader, framing, &stop)
            .take(MANIFEST_BYTES_LIMIT + 1)
            .read_to_end(&mut bytes);
        cancellation.check()?;
        read.map_err(|error| network_failure(&error))?;
        if bytes.len() as u64 > MANIFEST_BYTES_LIMIT {
            return Err(RegistryError::Damaged);
        }
        return Ok(bytes);
    }
}

/// Fetches `blob` from `sources` into `partial`, which holds exactly its bytes on
/// success. Damaged bytes are deleted; any other failure leaves resumable bytes in place.
fn fetch_blob(
    sources: &[HttpsUrl],
    blob: &Blob,
    hosts: &BTreeSet<HostName>,
    transfer: &mut Transfer<'_>,
    partial: &Path,
    tally: &mut Tally,
) -> Result<(), RegistryError> {
    filesystem::refuse_links(partial)?;
    if blob.size == 0 {
        // The pinned transfer fetches no empty file; empty content has one digest.
        if blob.digest != Sha256Digest::of(b"") {
            return Err(RegistryError::Damaged);
        }
        File::create(partial)?.sync_all()?;
        return Ok(());
    }
    let before = tally.done;
    let outer = &mut *transfer.events;
    let mut sink = |event: TransferEvent| match event {
        TransferEvent::Progress { completed, .. } => {
            tally.report(&mut *outer, before.saturating_add(completed));
        }
        other => outer(other),
    };
    let fetched = Transfer {
        network: transfer.network,
        hosts,
        policy: transfer.policy,
        pacing: &mut *transfer.pacing,
        events: &mut sink,
        cancellation: transfer.cancellation,
    }
    .fetch(
        Pinned {
            sources,
            size: blob.size,
            sha256: &blob.digest,
        },
        partial,
    )
    .map_err(RegistryError::from);
    if matches!(fetched, Err(RegistryError::Damaged)) {
        match fs::remove_file(partial) {
            Err(error) if error.kind() != io::ErrorKind::NotFound => return Err(error.into()),
            _ => {}
        }
    }
    fetched
}

/// Whether the store already holds `blob` whole at `path`: a regular file of its size and
/// digest.
fn verified(path: &Path, blob: &Blob, cancellation: &Cancellation) -> Result<bool, RegistryError> {
    filesystem::refuse_links(path)?;
    let meta = match fs::metadata(path) {
        Ok(meta) => meta,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(error.into()),
    };
    if !meta.is_file() || meta.len() != blob.size {
        return Ok(false);
    }
    let mut file = File::open(path)?;
    Ok(filesystem::digest_reader(&mut file, cancellation)? == blob.digest)
}

fn write_synced(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let mut file = File::create(path)?;
    file.write_all(bytes)?;
    file.sync_all()
}

/// Makes a rename into `folder` durable where the platform needs the folder synced.
fn sync_folder(folder: &Path) -> io::Result<()> {
    #[cfg(unix)]
    File::open(folder)?.sync_all()?;
    #[cfg(not(unix))]
    let _ = folder;
    Ok(())
}

#[cfg(test)]
mod tests;
