use crate::{
    error::Error,
    filesystem,
    package::Readiness,
    provisioning::{
        pins::ArchiveFormat,
        transfer::{Pinned, Transfer},
        url::HttpsUrl,
    },
    value::{RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicBool, Ordering},
};

/// Supplied by trusted release metadata. A digest checks integrity, not publisher identity.
#[derive(Clone, Debug, Eq, PartialEq, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Artifact {
    pub id: String,
    pub revision: String,
    pub target: String,
    pub sha256: Sha256Digest,
    pub archive_bytes: u64,
    pub max_unpacked_bytes: u64,
    pub max_entries: usize,
    pub executable: RelativePath,
    pub url: Option<String>,
    /// How the archive is packed; receipts written before formats existed held zips.
    #[serde(default)]
    pub format: ArchiveFormat,
}

impl Artifact {
    fn validate(&self, target: &str) -> Result<(), Error> {
        for value in [&self.id, &self.revision, &self.target] {
            if value.is_empty()
                || value.len() > 128
                || !value
                    .bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"-_.".contains(&c))
                || value == "."
                || value == ".."
            {
                return Err(Error::Invalid("invalid component identity".into()));
            }
            RelativePath::new(value.clone())?;
        }
        if self.target != target {
            return Err(Error::Incompatible("component target differs".into()));
        }
        if self.archive_bytes == 0
            || self.archive_bytes > 8 * 1024 * 1024 * 1024
            || self.max_unpacked_bytes == 0
            || self.max_unpacked_bytes > 32 * 1024 * 1024 * 1024
            || self.max_entries == 0
            || self.max_entries > 100_000
        {
            return Err(Error::LimitExceeded);
        }
        Ok(())
    }
}

#[derive(Default)]
pub struct Cancellation(AtomicBool);
impl Cancellation {
    pub fn cancel(&self) {
        self.0.store(true, Ordering::Release);
    }
    pub(crate) fn check(&self) -> Result<(), Error> {
        if self.0.load(Ordering::Acquire) {
            Err(Error::Cancelled)
        } else {
            Ok(())
        }
    }
}

#[derive(Debug)]
pub struct ActiveComponent {
    pub root: PathBuf,
    pub executable: PathBuf,
    pub revision: String,
}

#[derive(Debug)]
pub struct ComponentInspection {
    pub readiness: Readiness,
    pub active: Option<ActiveComponent>,
}

/// What [`ComponentStore::inspect_quick`] finds.
#[derive(Debug)]
pub enum QuickInspection {
    /// No version is active.
    Missing,
    /// The artifact's version is active and its executable holds its recorded bytes.
    Active(ActiveComponent),
    /// Another revision is active and its executable holds its recorded bytes.
    Other { revision: String },
    /// The active metadata, its receipt or the executable cannot be trusted.
    Damaged,
}

/// Owner-resolved location. Construction and inspection never create directories.
pub struct ComponentStore {
    root: PathBuf,
    target: String,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Receipt {
    schema: u32,
    artifact: Artifact,
    archive_entries: usize,
    files: BTreeMap<RelativePath, Sha256Digest>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ActivePointer {
    schema: u32,
    sha256: Sha256Digest,
    version: RelativePath,
}

pub(crate) struct WriterLock(pub(crate) File);

impl Drop for WriterLock {
    fn drop(&mut self) {
        // Closing alone can leave the lock held by a descriptor inherited during an
        // unrelated thread's fork. Release the shared lock before closing our handle.
        let _ = self.0.unlock();
    }
}

impl ComponentStore {
    pub fn new(root: PathBuf, target: String) -> Result<Self, Error> {
        filesystem::absolute_root(&root)?;
        if target.is_empty() {
            return Err(Error::Invalid("missing projected target".into()));
        }
        Ok(Self { root, target })
    }

    pub fn inspect(&self, artifact: &Artifact) -> Result<ComponentInspection, Error> {
        if let Err(Error::Incompatible(reason)) = artifact.validate(&self.target) {
            return Ok(ComponentInspection {
                readiness: Readiness::Incompatible(reason),
                active: None,
            });
        }
        artifact.validate(&self.target)?;
        filesystem::absolute_root(&self.root)?;
        let directory = self.root.join(&artifact.id);
        let pointer: ActivePointer = match filesystem::json_file(&directory.join("active.json")) {
            Ok(pointer) => pointer,
            Err(Error::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                return Ok(ComponentInspection {
                    readiness: Readiness::Missing(artifact.id.clone()),
                    active: None,
                });
            }
            Err(Error::Json(_)) => {
                return Ok(ComponentInspection {
                    readiness: Readiness::Incompatible("invalid active metadata".into()),
                    active: None,
                });
            }
            Err(e) => return Err(e),
        };
        if pointer.schema != 1 || pointer.sha256 != artifact.sha256 {
            return Ok(ComponentInspection {
                readiness: Readiness::Incompatible("active revision differs".into()),
                active: None,
            });
        }
        if pointer.version.as_str().contains('/') {
            return Err(Error::Invalid("nested component version".into()));
        }
        let version = pointer.version.under(&directory.join("versions"));
        match verify_version(&version, artifact) {
            Ok(()) => Ok(ComponentInspection {
                readiness: Readiness::Ready,
                active: Some(active(&version, artifact)),
            }),
            Err(Error::Integrity(reason)) => Ok(ComponentInspection {
                readiness: Readiness::Incompatible(reason),
                active: None,
            }),
            Err(Error::Json(_)) => Ok(ComponentInspection {
                readiness: Readiness::Incompatible("invalid component receipt".into()),
                active: None,
            }),
            Err(Error::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                Ok(ComponentInspection {
                    readiness: Readiness::Missing("active component files".into()),
                    active: None,
                })
            }
            Err(e) => Err(e),
        }
    }

    /// A look at the active version that hashes only its executable, for a check that
    /// must stay fast: the pointer, the receipt's identity and the executable's recorded
    /// bytes. [`Self::inspect`] remains the check of every installed file.
    pub fn inspect_quick(&self, artifact: &Artifact) -> Result<QuickInspection, Error> {
        artifact.validate(&self.target)?;
        filesystem::absolute_root(&self.root)?;
        let directory = self.root.join(&artifact.id);
        let pointer: ActivePointer = match filesystem::json_file(&directory.join("active.json")) {
            Ok(pointer) => pointer,
            Err(Error::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                return Ok(QuickInspection::Missing);
            }
            Err(Error::Json(_) | Error::Integrity(_) | Error::Invalid(_)) => {
                return Ok(QuickInspection::Damaged);
            }
            Err(e) => return Err(e),
        };
        if pointer.schema != 1 || pointer.version.as_str().contains('/') {
            return Ok(QuickInspection::Damaged);
        }
        let version = pointer.version.under(&directory.join("versions"));
        let receipt: Receipt = match filesystem::json_file(&version.join("receipt.json")) {
            Ok(receipt) => receipt,
            Err(Error::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {
                return Ok(QuickInspection::Missing);
            }
            Err(Error::Json(_) | Error::Integrity(_) | Error::Invalid(_)) => {
                return Ok(QuickInspection::Damaged);
            }
            Err(e) => return Err(e),
        };
        let recorded = &receipt.artifact;
        if receipt.schema != 1
            || recorded.sha256 != pointer.sha256
            || recorded.id != artifact.id
            || recorded.target != artifact.target
        {
            return Ok(QuickInspection::Damaged);
        }
        let executable = recorded.executable.under(&version.join("payload"));
        let intact = receipt
            .files
            .get(&recorded.executable)
            .is_some_and(|expected| {
                filesystem::digest(&executable).is_ok_and(|found| found == *expected)
                    && filesystem::require_executable(&executable).is_ok()
            });
        if !intact {
            return Ok(QuickInspection::Damaged);
        }
        if recorded.sha256 == artifact.sha256 && recorded.executable == artifact.executable {
            Ok(QuickInspection::Active(active(&version, artifact)))
        } else {
            Ok(QuickInspection::Other {
                revision: recorded.revision.clone(),
            })
        }
    }

    /// Removes every stored version but the active one, under the writer lock. The caller
    /// first stops anything running from a superseded version.
    pub fn prune(&self, artifact: &Artifact) -> Result<(), Error> {
        artifact.validate(&self.target)?;
        let (directory, _writer) = self.writer(&artifact.id)?;
        let pointer: ActivePointer = filesystem::json_file(&directory.join("active.json"))?;
        let versions = directory.join("versions");
        filesystem::refuse_links(&versions)?;
        for entry in fs::read_dir(&versions)? {
            let entry = entry?;
            if entry.file_name().to_str() != Some(pointer.version.as_str()) {
                remove_tree(&entry.path(), &versions)?;
            }
        }
        Ok(())
    }

    /// Removes the component's active pointer first, so no reader finds a half-removed
    /// version, then every version, partial download and staging tree, under the writer
    /// lock. Anything else the owner keeps in the component's folder stays. The caller
    /// first stops anything running from it.
    pub fn remove(&self, id: &str) -> Result<(), Error> {
        let (directory, _writer) = self.writer(id)?;
        for pointer in ["active.json", "active.next.json"] {
            let path = directory.join(pointer);
            filesystem::refuse_links(&path)?;
            match fs::remove_file(&path) {
                Err(e) if e.kind() != std::io::ErrorKind::NotFound => return Err(e.into()),
                _ => {}
            }
        }
        for tree in ["versions", "downloads", "staging"] {
            let path = directory.join(tree);
            if path.exists() {
                remove_tree(&path, &directory)?;
            }
        }
        Ok(())
    }

    /// The component's folder, created if needed, with its writer lock held.
    fn writer(&self, id: &str) -> Result<(PathBuf, WriterLock), Error> {
        let identity = RelativePath::new(id)?;
        if identity.as_str().contains('/') {
            return Err(Error::Invalid("nested component identity".into()));
        }
        filesystem::absolute_root(&self.root)?;
        let directory = self.root.join(identity.as_str());
        filesystem::refuse_links(&directory)?;
        fs::create_dir_all(&directory)?;
        filesystem::refuse_links(&directory)?;
        let lock_path = directory.join("writer.lock");
        filesystem::refuse_links(&lock_path)?;
        // Keep the lock inode in place: unlinking it allows two independent writers.
        let lock = File::options()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(lock_path)?;
        lock.try_lock().map_err(|e| match e {
            std::fs::TryLockError::WouldBlock => Error::Busy,
            std::fs::TryLockError::Error(e) => Error::Io(e),
        })?;
        Ok((directory, WriterLock(lock)))
    }

    /// Explicit acquisition. The source is opened only after target admission and writer locking.
    pub fn provision<R: Read>(
        &self,
        artifact: &Artifact,
        source: impl FnOnce() -> Result<R, Error>,
        cancellation: &Cancellation,
    ) -> Result<ActiveComponent, Error> {
        self.acquire(artifact, cancellation, |archive, _| {
            write_archive(artifact, source()?, archive, cancellation)
        })
    }

    /// Admits the target, takes the writer lock and activates `artifact`, calling `fill` to
    /// place its verified archive bytes at the staging path only when no stored version
    /// can be reused.
    fn acquire(
        &self,
        artifact: &Artifact,
        cancellation: &Cancellation,
        fill: impl FnOnce(&Path, &Path) -> Result<(), Error>,
    ) -> Result<ActiveComponent, Error> {
        artifact.validate(&self.target)?;
        cancellation.check()?;
        let (directory, _writer) = self.writer(&artifact.id)?;
        let stage = directory.join("staging");
        remove_staging(&stage, &directory)?;
        let next_pointer = directory.join("active.next.json");
        filesystem::refuse_links(&next_pointer)?;
        if next_pointer.exists() {
            fs::remove_file(&next_pointer)?;
        }
        if let Some(component) = self.inspect(artifact)?.active {
            return Ok(component);
        }

        let versions = directory.join("versions");
        filesystem::refuse_links(&versions)?;
        fs::create_dir_all(&versions)?;
        let version = reusable_or_fresh_version(&versions, artifact)?;
        if !version.exists() {
            fs::create_dir(&stage)?;
            let archive = stage.join("download.archive");
            let result = fill(&archive, &directory)
                .and_then(|()| self.stage(artifact, &archive, cancellation, &stage, &version));
            let cleanup = remove_staging(&stage, &directory);
            result?;
            cleanup?;
        }
        cancellation.check()?;
        filesystem::write_json(
            &next_pointer,
            &ActivePointer {
                schema: 1,
                sha256: artifact.sha256.clone(),
                version: RelativePath::from_native(
                    version
                        .strip_prefix(&versions)
                        .map_err(|_| Error::Invalid("version escaped store".into()))?,
                )?,
            },
        )?;
        cancellation.check()?;
        let pointer = directory.join("active.json");
        filesystem::refuse_links(&pointer)?;
        // Rename replaces one pointer, never a live browser tree; old versions remain available.
        fs::rename(&next_pointer, &pointer)?;
        Ok(active(&version, artifact))
    }

    /// Extracts the verified archive at `archive` into a candidate and moves it to `version`.
    fn stage(
        &self,
        artifact: &Artifact,
        archive: &Path,
        cancellation: &Cancellation,
        stage: &Path,
        version: &Path,
    ) -> Result<(), Error> {
        let candidate = stage.join("candidate");
        fs::create_dir(&candidate)?;
        let payload = candidate.join("payload");
        fs::create_dir(&payload)?;
        let (files, archive_entries) = extract(archive, &payload, artifact, cancellation)?;
        if !files.contains_key(&artifact.executable) {
            return Err(Error::Integrity("component executable missing".into()));
        }
        filesystem::require_executable(&artifact.executable.under(&payload))?;
        filesystem::write_json(
            &candidate.join("receipt.json"),
            &Receipt {
                schema: 1,
                artifact: artifact.clone(),
                archive_entries,
                files,
            },
        )?;
        cancellation.check()?;
        fs::rename(candidate, version)?;
        Ok(())
    }

    /// Downloads the artifact through the pinned transfer and activates it.
    ///
    /// The address must be HTTPS; nothing is created before that is known. The partial
    /// download lives beside the versions, under the writer lock, so an interrupted
    /// download resumes from its bytes; partial downloads of other revisions are removed.
    /// Callers obtain pins independently from trusted release metadata.
    pub fn download_and_activate(
        &self,
        artifact: &Artifact,
        transfer: &mut Transfer<'_>,
    ) -> Result<ActiveComponent, Error> {
        let url = artifact
            .url
            .as_ref()
            .ok_or_else(|| Error::Invalid("no download metadata".into()))?;
        let source = HttpsUrl::parse(url)?;
        let cancellation = transfer.cancellation;
        self.acquire(artifact, cancellation, |archive, directory| {
            let downloads = directory.join("downloads");
            filesystem::refuse_links(&downloads)?;
            fs::create_dir_all(&downloads)?;
            let name = format!("{}.part", artifact.sha256);
            for entry in fs::read_dir(&downloads)? {
                let entry = entry?;
                filesystem::refuse_metadata_links(&entry.metadata()?)?;
                if entry.file_name().to_str() != Some(name.as_str()) {
                    fs::remove_file(entry.path())?;
                }
            }
            let partial = downloads.join(name);
            transfer.fetch(
                Pinned {
                    sources: std::slice::from_ref(&source),
                    size: artifact.archive_bytes,
                    sha256: &artifact.sha256,
                },
                &partial,
            )?;
            fs::rename(&partial, archive)?;
            Ok(())
        })
    }
}

/// Streams `source` into `archive`, refusing bytes beyond or short of the pinned size and
/// any digest but the pinned one.
fn write_archive(
    artifact: &Artifact,
    mut source: impl Read,
    archive: &Path,
    cancellation: &Cancellation,
) -> Result<(), Error> {
    let mut file = File::options().write(true).create_new(true).open(archive)?;
    let mut hash = Sha256::new();
    let mut count = 0u64;
    let mut buffer = [0u8; 65536];
    loop {
        cancellation.check()?;
        let n = source.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        count += n as u64;
        if count > artifact.archive_bytes {
            return Err(Error::LimitExceeded);
        }
        hash.update(&buffer[..n]);
        file.write_all(&buffer[..n])?;
    }
    file.sync_all()?;
    drop(file);
    if count != artifact.archive_bytes
        || Sha256Digest::from_hash(hash.finalize())? != artifact.sha256
    {
        return Err(Error::Integrity("component archive".into()));
    }
    Ok(())
}

fn active(version: &Path, artifact: &Artifact) -> ActiveComponent {
    let root = version.join("payload");
    ActiveComponent {
        executable: artifact.executable.under(&root),
        root,
        revision: artifact.revision.clone(),
    }
}

fn remove_staging(stage: &Path, owner: &Path) -> Result<(), Error> {
    if stage.parent() != Some(owner)
        || stage.file_name().and_then(|s| s.to_str()) != Some("staging")
    {
        return Err(Error::Invalid("cleanup outside staging".into()));
    }
    filesystem::refuse_links(stage)?;
    if stage.exists() {
        remove_tree(stage, owner)?;
    }
    Ok(())
}

/// Removes `tree`, a direct child of `owner`, once no link is found anywhere inside it.
fn remove_tree(tree: &Path, owner: &Path) -> Result<(), Error> {
    if tree.parent() != Some(owner) {
        return Err(Error::Invalid("removal outside the component".into()));
    }
    filesystem::refuse_links(tree)?;
    if !fs::symlink_metadata(tree)?.is_dir() {
        fs::remove_file(tree)?;
        return Ok(());
    }
    // Validate descendants too; the application-owned tree must not contain junctions.
    let mut pending = vec![tree.to_path_buf()];
    while let Some(directory) = pending.pop() {
        for entry in fs::read_dir(directory)? {
            let path = entry?.path();
            filesystem::refuse_links(&path)?;
            if path.is_dir() {
                pending.push(path);
            }
        }
    }
    fs::remove_dir_all(tree)?;
    Ok(())
}

type Extracted = (BTreeMap<RelativePath, Sha256Digest>, usize);

fn extract(
    archive: &Path,
    destination: &Path,
    artifact: &Artifact,
    cancellation: &Cancellation,
) -> Result<Extracted, Error> {
    match artifact.format {
        ArchiveFormat::Zip => extract_zip(archive, destination, artifact, cancellation),
        ArchiveFormat::TarGz => {
            let source = flate2::bufread::MultiGzDecoder::new(BufReader::new(File::open(archive)?));
            extract_tar(source, destination, artifact, cancellation)
        }
        ArchiveFormat::TarZst => {
            let source = ZstdFrames::new(BufReader::new(File::open(archive)?))?;
            extract_tar(source, destination, artifact, cancellation)
        }
    }
}

/// Every member name an archive declares, refused when two spell one path, or one
/// directory, differently only by case: they would collide on a case-insensitive volume.
#[derive(Default)]
struct MemberNames {
    seen: BTreeSet<String>,
    spellings: BTreeMap<String, String>,
}

impl MemberNames {
    fn admit(&mut self, relative: &RelativePath) -> Result<(), Error> {
        if !self.seen.insert(relative.as_str().to_lowercase()) {
            return Err(Error::Invalid("duplicate archive member".into()));
        }
        let mut prefix = String::new();
        for part in relative.as_str().split('/') {
            if !prefix.is_empty() {
                prefix.push('/');
            }
            prefix.push_str(part);
            if let Some(previous) = self.spellings.insert(prefix.to_lowercase(), prefix.clone())
                && previous != prefix
            {
                return Err(Error::Invalid("archive directory casing differs".into()));
            }
        }
        Ok(())
    }
}

/// Streams one member's bytes into a new file at `path`, counting them against the
/// artifact's unpacked bound, and returns their digest.
fn write_member(
    mut member: impl Read,
    path: &Path,
    mode: Option<u32>,
    artifact: &Artifact,
    total: &mut u64,
    cancellation: &Cancellation,
) -> Result<Sha256Digest, Error> {
    fs::create_dir_all(
        path.parent()
            .ok_or_else(|| Error::Invalid("archive path has no parent".into()))?,
    )?;
    let mut out = File::options().write(true).create_new(true).open(path)?;
    let mut hash = Sha256::new();
    let mut buffer = [0u8; 65536];
    loop {
        cancellation.check()?;
        let n = member.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        *total += n as u64;
        if *total > artifact.max_unpacked_bytes {
            return Err(Error::LimitExceeded);
        }
        hash.update(&buffer[..n]);
        out.write_all(&buffer[..n])?;
    }
    out.sync_all()?;
    filesystem::archive_permissions(path, mode)?;
    Sha256Digest::from_hash(hash.finalize())
}

fn extract_zip(
    archive: &Path,
    destination: &Path,
    artifact: &Artifact,
    cancellation: &Cancellation,
) -> Result<Extracted, Error> {
    let mut zip = zip::ZipArchive::new(File::open(archive)?)?;
    if zip.len() > artifact.max_entries {
        return Err(Error::LimitExceeded);
    }
    let mut files = BTreeMap::new();
    let mut names = MemberNames::default();
    let mut total = 0u64;
    for index in 0..zip.len() {
        cancellation.check()?;
        let member = zip.by_index(index)?;
        let name = member.name()?;
        let relative = RelativePath::new(if member.is_dir() {
            name.trim_end_matches('/')
        } else {
            &name
        })?;
        names.admit(&relative)?;
        let kind = member.unix_mode().unwrap_or(0) & 0o170000;
        if member.is_symlink() || !matches!(kind, 0 | 0o040000 | 0o100000) {
            return Err(Error::Invalid(
                "archive links and special files are forbidden".into(),
            ));
        }
        let path = relative.under(destination);
        if member.is_dir() {
            fs::create_dir_all(&path)?;
            continue;
        }
        if member.size() > artifact.max_unpacked_bytes.saturating_sub(total) {
            return Err(Error::LimitExceeded);
        }
        let mode = member.unix_mode();
        let digest = write_member(member, &path, mode, artifact, &mut total, cancellation)?;
        files.insert(relative, digest);
    }
    Ok((files, zip.len()))
}

/// A tar stream extracted with the same bounds as a zip: member count, unpacked bytes,
/// safe relative names and no special files. No link is ever created on disk. A
/// symbolic or hard link member names another member, as the publisher's archives do
/// for versioned shared libraries; it is admitted only when it resolves, inside the
/// archive and through at most a few other links, to a regular file member, and that
/// file is then also placed at the link's path as a hard link of the same bytes, which
/// count again against the unpacked bound. A link to a directory, outside the archive or
/// to nothing is refused.
fn extract_tar(
    source: impl Read,
    destination: &Path,
    artifact: &Artifact,
    cancellation: &Cancellation,
) -> Result<Extracted, Error> {
    let mut archive = tar::Archive::new(source);
    let mut files: BTreeMap<RelativePath, Sha256Digest> = BTreeMap::new();
    let mut sizes: BTreeMap<RelativePath, u64> = BTreeMap::new();
    let mut links: BTreeMap<RelativePath, RelativePath> = BTreeMap::new();
    let mut names = MemberNames::default();
    let mut total = 0u64;
    let mut entries = 0usize;
    for entry in archive.entries()? {
        cancellation.check()?;
        let entry = entry?;
        let kind = entry.header().entry_type();
        if kind.is_pax_global_extensions() {
            continue;
        }
        entries += 1;
        if entries > artifact.max_entries {
            return Err(Error::LimitExceeded);
        }
        let raw = std::str::from_utf8(&entry.path_bytes())
            .map_err(|_| Error::Invalid("non-UTF8 archive member".into()))?
            .to_owned();
        let name = raw.strip_prefix("./").unwrap_or(&raw).trim_end_matches('/');
        if name.is_empty() || name == "." {
            if kind.is_dir() {
                continue;
            }
            return Err(Error::Invalid("unnamed archive member".into()));
        }
        let relative = RelativePath::new(name)?;
        names.admit(&relative)?;
        let path = relative.under(destination);
        if kind.is_dir() {
            fs::create_dir_all(&path)?;
        } else if kind.is_file() || kind.is_contiguous() {
            let size = entry.size();
            if size > artifact.max_unpacked_bytes.saturating_sub(total) {
                return Err(Error::LimitExceeded);
            }
            let mode = entry.header().mode().ok();
            let digest = write_member(entry, &path, mode, artifact, &mut total, cancellation)?;
            files.insert(relative.clone(), digest);
            sizes.insert(relative, size);
        } else if kind.is_symlink() || kind.is_hard_link() {
            let target = entry
                .link_name_bytes()
                .ok_or_else(|| Error::Invalid("archive link without a target".into()))?;
            let target = std::str::from_utf8(&target)
                .map_err(|_| Error::Invalid("non-UTF8 archive link".into()))?;
            // A symbolic link is read from its own folder, a hard link from the root.
            let base = if kind.is_symlink() {
                relative
                    .as_str()
                    .rsplit_once('/')
                    .map_or("", |(base, _)| base)
            } else {
                ""
            };
            let resolved = resolve_member(base, target)?;
            links.insert(relative, resolved);
        } else {
            return Err(Error::Invalid("archive special files are forbidden".into()));
        }
    }
    for (link, target) in &links {
        cancellation.check()?;
        let mut file = target;
        for _ in 0..=links.len() {
            match links.get(file) {
                Some(next) => file = next,
                None => break,
            }
        }
        let (Some(digest), Some(size)) = (files.get(file).cloned(), sizes.get(file)) else {
            return Err(Error::Invalid(
                "archive link does not name a regular file in the archive".into(),
            ));
        };
        total = total.saturating_add(*size);
        if total > artifact.max_unpacked_bytes {
            return Err(Error::LimitExceeded);
        }
        let path = link.under(destination);
        fs::create_dir_all(
            path.parent()
                .ok_or_else(|| Error::Invalid("archive path has no parent".into()))?,
        )?;
        fs::hard_link(file.under(destination), &path)?;
        files.insert(link.clone(), digest);
    }
    Ok((files, entries))
}

/// The archive member `target` names, read lexically from the folder `base`; refused when
/// it is absolute or climbs above the archive's root.
fn resolve_member(base: &str, target: &str) -> Result<RelativePath, Error> {
    if target.starts_with('/') || target.contains('\\') {
        return Err(Error::Invalid("archive link leaves the archive".into()));
    }
    let mut parts: Vec<&str> = base.split('/').filter(|part| !part.is_empty()).collect();
    for part in target.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                parts
                    .pop()
                    .ok_or_else(|| Error::Invalid("archive link leaves the archive".into()))?;
            }
            part => parts.push(part),
        }
    }
    RelativePath::new(parts.join("/"))
}

/// A zstd stream of one or more frames, decoded one frame after another with the
/// decoder's default window bound.
struct ZstdFrames<R: BufRead> {
    decoder: Option<ruzstd::decoding::StreamingDecoder<R, ruzstd::decoding::FrameDecoder>>,
}

impl<R: BufRead> ZstdFrames<R> {
    fn new(source: R) -> Result<Self, Error> {
        Ok(Self {
            decoder: Some(Self::frame(source).map_err(Error::Io)?),
        })
    }

    fn frame(
        source: R,
    ) -> std::io::Result<ruzstd::decoding::StreamingDecoder<R, ruzstd::decoding::FrameDecoder>>
    {
        ruzstd::decoding::StreamingDecoder::new(source)
            .map_err(|_| std::io::Error::new(std::io::ErrorKind::InvalidData, "invalid zstd frame"))
    }
}

impl<R: BufRead> Read for ZstdFrames<R> {
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        loop {
            let Some(decoder) = self.decoder.as_mut() else {
                return Ok(0);
            };
            let read = decoder.read(buffer)?;
            if read > 0 || buffer.is_empty() {
                return Ok(read);
            }
            let Some(decoder) = self.decoder.take() else {
                return Ok(0);
            };
            let mut source = decoder.into_inner();
            if source.fill_buf()?.is_empty() {
                return Ok(0);
            }
            self.decoder = Some(Self::frame(source)?);
        }
    }
}

fn verify_version(version: &Path, artifact: &Artifact) -> Result<(), Error> {
    let receipt: Receipt = filesystem::json_file(&version.join("receipt.json"))?;
    if receipt.schema != 1
        || receipt.artifact.id != artifact.id
        || receipt.artifact.revision != artifact.revision
        || receipt.artifact.target != artifact.target
        || receipt.artifact.sha256 != artifact.sha256
        || receipt.artifact.archive_bytes != artifact.archive_bytes
        || receipt.artifact.executable != artifact.executable
        || !receipt.files.contains_key(&artifact.executable)
    {
        return Err(Error::Integrity("component receipt differs".into()));
    }
    let payload = version.join("payload");
    if receipt.archive_entries > artifact.max_entries
        || receipt.archive_entries < receipt.files.len()
    {
        return Err(Error::Integrity(
            "stored archive entry count exceeds current policy".into(),
        ));
    }
    let mut total = 0u64;
    for (relative, expected) in &receipt.files {
        let path = relative.under(&payload);
        filesystem::refuse_links(&path)?;
        total = total
            .checked_add(fs::metadata(&path)?.len())
            .ok_or_else(|| Error::Integrity("stored component size overflow".into()))?;
        if total > artifact.max_unpacked_bytes {
            return Err(Error::Integrity(
                "stored component exceeds current size policy".into(),
            ));
        }
        if filesystem::digest(&relative.under(&payload))? != *expected {
            return Err(Error::Integrity("component payload changed".into()));
        }
    }
    let mut pending = vec![payload.clone()];
    while let Some(directory) = pending.pop() {
        filesystem::refuse_links(&directory)?;
        for entry in fs::read_dir(directory)? {
            let path = entry?.path();
            filesystem::refuse_links(&path)?;
            if path.is_dir() {
                pending.push(path);
                continue;
            }
            let relative = path
                .strip_prefix(&payload)
                .map_err(|_| Error::Invalid("payload path escaped".into()))?;
            let relative = RelativePath::from_native(relative)?;
            if !receipt.files.contains_key(&relative) {
                return Err(Error::Integrity("unexpected component file".into()));
            }
        }
    }
    filesystem::require_executable(&artifact.executable.under(&payload))
}

fn reusable_or_fresh_version(versions: &Path, artifact: &Artifact) -> Result<PathBuf, Error> {
    for generation in 0..1024 {
        let version = versions.join(format!("{}-{generation}", artifact.sha256));
        filesystem::refuse_links(&version)?;
        if !version.exists() {
            return Ok(version);
        }
        match verify_version(&version, artifact) {
            Ok(()) => return Ok(version),
            Err(Error::Integrity(_) | Error::Json(_)) => {}
            Err(Error::Io(e)) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e),
        }
    }
    Err(Error::LimitExceeded)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn writer_scope_releases_lock_even_with_a_duplicated_descriptor() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("writer.lock");
        let file = File::options()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&path)
            .unwrap();
        file.try_lock().unwrap();
        let duplicate = file.try_clone().unwrap();
        let guard = WriterLock(file);
        let next = File::options().read(true).write(true).open(&path).unwrap();
        assert!(matches!(
            next.try_lock(),
            Err(std::fs::TryLockError::WouldBlock)
        ));
        drop(guard);
        next.try_lock()
            .expect("completed writer left its lock held through a duplicate descriptor");
        drop(duplicate);
    }

    #[test]
    fn a_pinned_download_resumes_its_partial_bytes_and_activates_once() {
        use crate::provisioning::{
            test_servers::{Reply, Request, TestCertificate, TlsServer, network_to, response},
            transfer::{RetryPolicy, SystemPacing, Transfer},
        };
        use crate::value::HostName;
        use std::io::Cursor;

        let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
        zip.start_file(
            "bin/tool",
            zip::write::SimpleFileOptions::default().unix_permissions(0o755),
        )
        .unwrap();
        zip.write_all(&vec![7u8; 100_000]).unwrap();
        let bytes = zip.finish().unwrap().into_inner();
        let served = bytes.clone();
        let certificate = TestCertificate::new(&["cdn.example.com"]);
        let server = TlsServer::start(&certificate, move |request: &Request| {
            let start = request
                .header("range")
                .and_then(|range| range.strip_prefix("bytes="))
                .and_then(|range| range.strip_suffix("-"))
                .and_then(|start| start.parse::<usize>().ok())
                .unwrap_or(0);
            let status = if start > 0 { "206 Partial" } else { "200 OK" };
            let range = format!("bytes {start}-{}/{}", served.len() - 1, served.len());
            Reply::Bytes(response(
                status,
                &[
                    ("Content-Length", (served.len() - start).to_string()),
                    ("Content-Range", range),
                ],
                &served[start..],
            ))
        });
        let network = network_to(certificate.roots(), server.address(), None);
        let directory = tempfile::tempdir().unwrap();
        let store = ComponentStore::new(directory.path().into(), "fixture-target".into()).unwrap();
        let artifact = Artifact {
            id: "tool".into(),
            revision: "1".into(),
            target: "fixture-target".into(),
            sha256: Sha256Digest::of(&bytes),
            archive_bytes: bytes.len() as u64,
            max_unpacked_bytes: 1_000_000,
            max_entries: 10,
            executable: RelativePath::new("bin/tool").unwrap(),
            url: Some("https://cdn.example.com/tool.zip".into()),
            format: ArchiveFormat::Zip,
        };
        let downloads = directory.path().join("tool/downloads");
        fs::create_dir_all(&downloads).unwrap();
        fs::write(downloads.join("stale-revision.part"), b"old").unwrap();
        fs::write(
            downloads.join(format!("{}.part", artifact.sha256)),
            &bytes[..100],
        )
        .unwrap();
        let hosts = [HostName::new("cdn.example.com").unwrap()].into();
        let mut pacing = SystemPacing::default();
        let cancellation = Cancellation::default();
        let progress = std::cell::Cell::new(0);
        let mut events = |_| progress.set(progress.get() + 1);
        let mut transfer = Transfer {
            network: &network,
            hosts: &hosts,
            policy: RetryPolicy::default(),
            pacing: &mut pacing,
            events: &mut events,
            cancellation: &cancellation,
        };
        let active = store
            .download_and_activate(&artifact, &mut transfer)
            .unwrap();
        assert_eq!(fs::read(&active.executable).unwrap(), vec![7u8; 100_000]);
        assert_eq!(fs::read_dir(&downloads).unwrap().count(), 0);
        assert_eq!(
            server.requests.lock().unwrap()[0].header("range"),
            Some("bytes=100-")
        );
        store
            .download_and_activate(&artifact, &mut transfer)
            .unwrap();
        assert_eq!(server.targets().len(), 1, "an active version is reused");
        assert!(matches!(
            store.inspect(&artifact).unwrap().readiness,
            Readiness::Ready
        ));
        assert!(progress.get() > 0);
    }

    /// One tar member written field by field, so a test can spell names and link targets
    /// a well-behaved archiver would refuse to write.
    #[derive(Clone, Copy)]
    struct Member<'a> {
        name: &'a str,
        kind: tar::EntryType,
        link: &'a str,
        data: &'a [u8],
        mode: u32,
    }

    fn file<'a>(name: &'a str, data: &'a [u8], mode: u32) -> Member<'a> {
        Member {
            name,
            kind: tar::EntryType::Regular,
            link: "",
            data,
            mode,
        }
    }

    fn link<'a>(name: &'a str, kind: tar::EntryType, target: &'a str) -> Member<'a> {
        Member {
            name,
            kind,
            link: target,
            data: b"",
            mode: 0o777,
        }
    }

    fn folder(name: &str) -> Member<'_> {
        Member {
            name,
            kind: tar::EntryType::Directory,
            link: "",
            data: b"",
            mode: 0o755,
        }
    }

    fn tar_of(members: &[Member<'_>]) -> Vec<u8> {
        let mut builder = tar::Builder::new(Vec::new());
        for member in members {
            let mut header = tar::Header::new_gnu();
            let old = header.as_old_mut();
            old.name[..member.name.len()].copy_from_slice(member.name.as_bytes());
            old.linkname[..member.link.len()].copy_from_slice(member.link.as_bytes());
            header.set_entry_type(member.kind);
            header.set_size(member.data.len() as u64);
            header.set_mode(member.mode);
            header.set_cksum();
            builder.append(&header, member.data).unwrap();
        }
        builder.into_inner().unwrap()
    }

    fn packed(format: ArchiveFormat, tar: &[u8]) -> Vec<u8> {
        match format {
            ArchiveFormat::TarGz => {
                let mut encoder =
                    flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
                encoder.write_all(tar).unwrap();
                encoder.finish().unwrap()
            }
            ArchiveFormat::TarZst => ruzstd::encoding::compress_to_vec(
                std::io::Cursor::new(tar.to_vec()),
                ruzstd::encoding::CompressionLevel::Fastest,
            ),
            ArchiveFormat::Zip => unreachable!("a tar test"),
        }
    }

    fn tar_artifact(bytes: &[u8], format: ArchiveFormat) -> Artifact {
        Artifact {
            id: "ollama".into(),
            revision: "1".into(),
            target: "fixture-target".into(),
            sha256: Sha256Digest::of(bytes),
            archive_bytes: bytes.len() as u64,
            max_unpacked_bytes: 1_000_000,
            max_entries: 20,
            executable: RelativePath::new("bin/ollama").unwrap(),
            url: None,
            format,
        }
    }

    fn provision_tar(
        format: ArchiveFormat,
        members: &[Member<'_>],
        adjust: impl FnOnce(&mut Artifact),
    ) -> (tempfile::TempDir, Result<ActiveComponent, Error>) {
        let bytes = packed(format, &tar_of(members));
        let mut artifact = tar_artifact(&bytes, format);
        adjust(&mut artifact);
        let directory = tempfile::tempdir().unwrap();
        let store = ComponentStore::new(directory.path().into(), "fixture-target".into()).unwrap();
        let result = store.provision(
            &artifact,
            || Ok(std::io::Cursor::new(bytes.clone())),
            &Cancellation::default(),
        );
        if result.is_ok() {
            assert!(matches!(
                store.inspect(&artifact).unwrap().readiness,
                Readiness::Ready
            ));
        }
        (directory, result)
    }

    const LIBRARY: &[u8] = b"shared library bytes";

    /// The publisher's Linux layout in miniature: versioned libraries reached through a
    /// chain of links, one of them listed before what it names.
    fn publisher_layout() -> Vec<Member<'static>> {
        vec![
            folder("./"),
            folder("./bin/"),
            file("./bin/ollama", b"program", 0o755),
            folder("lib/ollama/"),
            link(
                "lib/ollama/libggml.so",
                tar::EntryType::Symlink,
                "libggml.so.0",
            ),
            link(
                "lib/ollama/libggml.so.0",
                tar::EntryType::Symlink,
                "./libggml.so.0.27.0",
            ),
            file("lib/ollama/libggml.so.0.27.0", LIBRARY, 0o644),
            link(
                "lib/ollama/cuda/libggml.so",
                tar::EntryType::Symlink,
                "../libggml.so.0.27.0",
            ),
            link(
                "lib/ollama/copy.so",
                tar::EntryType::Link,
                "lib/ollama/libggml.so.0.27.0",
            ),
        ]
    }

    #[test]
    fn tar_archives_extract_their_links_as_files_of_the_same_bytes_and_no_link() {
        for format in [ArchiveFormat::TarGz, ArchiveFormat::TarZst] {
            let (_directory, result) = provision_tar(format, &publisher_layout(), |_| {});
            let active = result.unwrap();
            assert_eq!(fs::read(&active.executable).unwrap(), b"program");
            filesystem::require_executable(&active.executable).unwrap();
            for name in [
                "lib/ollama/libggml.so",
                "lib/ollama/libggml.so.0",
                "lib/ollama/libggml.so.0.27.0",
                "lib/ollama/cuda/libggml.so",
                "lib/ollama/copy.so",
            ] {
                let path = active.root.join(name);
                assert!(
                    !fs::symlink_metadata(&path).unwrap().is_symlink(),
                    "{format:?} {name}"
                );
                filesystem::refuse_links(&path).unwrap();
                assert_eq!(fs::read(&path).unwrap(), LIBRARY, "{format:?} {name}");
            }
        }
    }

    #[test]
    fn tar_links_out_of_the_archive_or_to_no_file_and_special_members_are_refused() {
        let refused: Vec<Vec<Member<'static>>> = vec![
            // Each escape names a member that exists, so only the escape is refused.
            vec![
                file("outside", b"x", 0o644),
                link("bin/escape", tar::EntryType::Symlink, "../../outside"),
            ],
            vec![
                file("etc/passwd", b"x", 0o644),
                link("bin/absolute", tar::EntryType::Symlink, "/etc/passwd"),
            ],
            vec![link("bin/nothing", tar::EntryType::Symlink, "missing")],
            vec![
                folder("lib/"),
                link("bin/folder", tar::EntryType::Symlink, "../lib"),
            ],
            vec![
                link("bin/a", tar::EntryType::Symlink, "b"),
                link("bin/b", tar::EntryType::Symlink, "a"),
            ],
            vec![
                file("outside", b"x", 0o644),
                link("bin/hard", tar::EntryType::Link, "../outside"),
            ],
            vec![Member {
                name: "bin/pipe",
                kind: tar::EntryType::Fifo,
                link: "",
                data: b"",
                mode: 0o644,
            }],
            vec![file("../outside", b"x", 0o644)],
            vec![file("/absolute", b"x", 0o644)],
            vec![file("bin/OLLAMA", b"x", 0o755)],
        ];
        for format in [ArchiveFormat::TarGz, ArchiveFormat::TarZst] {
            for extra in &refused {
                let mut members = vec![file("bin/ollama", b"program", 0o755)];
                members.extend(extra.iter().copied());
                let (directory, result) = provision_tar(format, &members, |_| {});
                assert!(
                    matches!(result, Err(Error::Invalid(_))),
                    "{format:?} {}: {result:?}",
                    extra[extra.len() - 1].name
                );
                assert!(!directory.path().join("outside").exists());
                assert!(!directory.path().join("ollama/active.json").exists());
            }
        }
    }

    #[test]
    fn tar_archives_keep_the_member_and_unpacked_bounds_links_included() {
        for format in [ArchiveFormat::TarGz, ArchiveFormat::TarZst] {
            let layout = publisher_layout();
            let (_directory, result) =
                provision_tar(format, &layout, |artifact| artifact.max_entries = 8);
            assert!(matches!(result, Err(Error::LimitExceeded)), "{format:?}");
            // Four links place the library's bytes four more times.
            let files = b"program".len() + LIBRARY.len();
            let placed = (files + 4 * LIBRARY.len()) as u64;
            let (_directory, result) = provision_tar(format, &layout, |artifact| {
                artifact.max_unpacked_bytes = placed - 1;
            });
            assert!(matches!(result, Err(Error::LimitExceeded)), "{format:?}");
            let (_directory, result) = provision_tar(format, &layout, |artifact| {
                artifact.max_unpacked_bytes = placed;
            });
            result.unwrap();
        }
    }

    #[test]
    fn quick_inspection_hashes_the_executable_and_tells_another_revision_apart() {
        let bytes = packed(
            ArchiveFormat::TarGz,
            &tar_of(&[
                file("bin/ollama", b"program", 0o755),
                file("data", b"d", 0o644),
            ]),
        );
        let artifact = tar_artifact(&bytes, ArchiveFormat::TarGz);
        let directory = tempfile::tempdir().unwrap();
        let store = ComponentStore::new(directory.path().into(), "fixture-target".into()).unwrap();
        assert!(matches!(
            store.inspect_quick(&artifact).unwrap(),
            QuickInspection::Missing
        ));
        let active = store
            .provision(
                &artifact,
                || Ok(std::io::Cursor::new(bytes.clone())),
                &Cancellation::default(),
            )
            .unwrap();
        assert!(matches!(
            store.inspect_quick(&artifact).unwrap(),
            QuickInspection::Active(_)
        ));
        let mut newer = artifact.clone();
        newer.revision = "2".into();
        newer.sha256 = Sha256Digest::of(b"other bytes");
        assert!(matches!(
            store.inspect_quick(&newer).unwrap(),
            QuickInspection::Other { revision } if revision == "1"
        ));
        // A changed data file is the full inspection's to find; a changed executable is
        // found quickly.
        fs::write(active.root.join("data"), b"e").unwrap();
        assert!(matches!(
            store.inspect_quick(&artifact).unwrap(),
            QuickInspection::Active(_)
        ));
        assert!(!matches!(
            store.inspect(&artifact).unwrap().readiness,
            Readiness::Ready
        ));
        fs::write(&active.executable, b"changed").unwrap();
        assert!(matches!(
            store.inspect_quick(&artifact).unwrap(),
            QuickInspection::Damaged
        ));
        store.remove(&artifact.id).unwrap();
        assert!(matches!(
            store.inspect_quick(&artifact).unwrap(),
            QuickInspection::Missing
        ));
        assert!(!directory.path().join("ollama/versions").exists());
    }
}
