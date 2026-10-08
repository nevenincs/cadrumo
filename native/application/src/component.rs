use crate::{
    error::Error,
    filesystem,
    package::Readiness,
    value::{RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicBool, Ordering},
    time::Duration,
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

struct WriterLock(File);

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

    /// Explicit acquisition. The source is opened only after target admission and writer locking.
    pub fn provision<R: Read>(
        &self,
        artifact: &Artifact,
        source: impl FnOnce() -> Result<R, Error>,
        cancellation: &Cancellation,
    ) -> Result<ActiveComponent, Error> {
        artifact.validate(&self.target)?;
        cancellation.check()?;
        filesystem::absolute_root(&self.root)?;
        let directory = self.root.join(&artifact.id);
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
        let _writer = WriterLock(lock);
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
            let result = self.stage(artifact, source, cancellation, &stage, &version);
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

    fn stage<R: Read>(
        &self,
        artifact: &Artifact,
        source: impl FnOnce() -> Result<R, Error>,
        cancellation: &Cancellation,
        stage: &Path,
        version: &Path,
    ) -> Result<(), Error> {
        let archive = stage.join("download.zip");
        let mut source = source()?;
        let mut file = File::options()
            .write(true)
            .create_new(true)
            .open(&archive)?;
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
            || format!("{:x}", hash.finalize()) != artifact.sha256.as_str()
        {
            return Err(Error::Integrity("component archive".into()));
        }
        let candidate = stage.join("candidate");
        fs::create_dir(&candidate)?;
        let payload = candidate.join("payload");
        fs::create_dir(&payload)?;
        let (files, archive_entries) = extract(&archive, &payload, artifact, cancellation)?;
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

    /// HTTPS-only transport; callers must obtain pins independently from trusted release metadata.
    pub fn download_and_activate(
        &self,
        artifact: &Artifact,
        cancellation: &Cancellation,
    ) -> Result<ActiveComponent, Error> {
        let url = artifact
            .url
            .as_ref()
            .ok_or_else(|| Error::Invalid("no download metadata".into()))?;
        if !url.starts_with("https://") {
            return Err(Error::Invalid("download requires HTTPS".into()));
        }
        self.provision(
            artifact,
            || {
                let agent: ureq::Agent = ureq::Agent::config_builder()
                    .https_only(true)
                    .timeout_global(Some(Duration::from_secs(300)))
                    .build()
                    .into();
                let response = agent.get(url).call().map_err(|_| Error::Download)?;
                Ok(response.into_body().into_reader())
            },
            cancellation,
        )
    }
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
        // Validate descendants too; the application-owned tree must not contain junctions.
        let mut pending = vec![stage.to_path_buf()];
        while let Some(directory) = pending.pop() {
            for entry in fs::read_dir(directory)? {
                let path = entry?.path();
                filesystem::refuse_links(&path)?;
                if path.is_dir() {
                    pending.push(path);
                }
            }
        }
        fs::remove_dir_all(stage)?;
    }
    Ok(())
}

fn extract(
    archive: &Path,
    destination: &Path,
    artifact: &Artifact,
    cancellation: &Cancellation,
) -> Result<(BTreeMap<RelativePath, Sha256Digest>, usize), Error> {
    let mut zip = zip::ZipArchive::new(File::open(archive)?)?;
    if zip.len() > artifact.max_entries {
        return Err(Error::LimitExceeded);
    }
    let mut files = BTreeMap::new();
    let mut seen = BTreeSet::new();
    let mut spellings = BTreeMap::new();
    let mut total = 0u64;
    for index in 0..zip.len() {
        cancellation.check()?;
        let mut member = zip.by_index(index)?;
        let name = member.name();
        let relative = RelativePath::new(if member.is_dir() {
            name.trim_end_matches('/')
        } else {
            name
        })?;
        if !seen.insert(relative.as_str().to_lowercase()) {
            return Err(Error::Invalid("duplicate archive member".into()));
        }
        let mut prefix = String::new();
        for part in relative.as_str().split('/') {
            if !prefix.is_empty() {
                prefix.push('/');
            }
            prefix.push_str(part);
            if let Some(previous) = spellings.insert(prefix.to_lowercase(), prefix.clone())
                && previous != prefix
            {
                return Err(Error::Invalid("archive directory casing differs".into()));
            }
        }
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
        fs::create_dir_all(
            path.parent()
                .ok_or_else(|| Error::Invalid("archive path has no parent".into()))?,
        )?;
        let mut out = File::options().write(true).create_new(true).open(&path)?;
        let mut hash = Sha256::new();
        let mut buffer = [0u8; 65536];
        loop {
            cancellation.check()?;
            let n = member.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            total += n as u64;
            if total > artifact.max_unpacked_bytes {
                return Err(Error::LimitExceeded);
            }
            hash.update(&buffer[..n]);
            out.write_all(&buffer[..n])?;
        }
        out.sync_all()?;
        filesystem::archive_permissions(&path, member.unix_mode())?;
        files.insert(
            relative,
            Sha256Digest::new(format!("{:x}", hash.finalize()))?,
        );
    }
    Ok((files, zip.len()))
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
}
