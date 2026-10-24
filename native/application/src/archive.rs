//! Bounded archive extraction, shared by the component store and the browser builds.
//!
//! Every archive is read with the same rules. The member count and the bytes written are
//! bounded. Every member name must be a plain relative path, and two names that spell one
//! path or one folder differently only by case are refused, because they would collide on
//! a case-insensitive volume. Special files are refused. Regular files and folders are
//! written as they arrive; no link exists on disk while they are written.
//!
//! Link members are placed only once every regular file is written. Each one is resolved
//! first against the archive's own members, the way the kernel resolves a path: from the
//! link's folder for a symbolic link and from the archive's root for a hard link, one
//! component at a time, following other links, and with `..` taken from the folder
//! actually reached. A link is refused when its target is absolute, climbs above the
//! archive's root, names nothing, passes through a file, takes more than [`LINK_HOPS`]
//! links to resolve (as a cycle of links does), or names a folder that holds a link to a
//! folder (so that no walk through folder links can loop). A member whose path passes
//! through a link is refused, so nothing is ever written through one.
//!
//! [`LinkRule`] decides how a resolved link is placed. A hard link member is always placed
//! as a hard link of its file. After placement the destination is walked again without
//! following links: every link found must be one this extraction created, with the target
//! it was created with, and must resolve on disk inside the destination.

use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    provisioning::pins::ArchiveFormat,
    value::{RelativePath, Sha256Digest},
};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::{BufRead, BufReader, Read, Write},
    path::Path,
};

/// The most links one resolution follows, as the kernel's own bound on nested links.
pub(crate) const LINK_HOPS: usize = 40;

/// The longest link target admitted, in bytes.
const LINK_TARGET_BYTES: u64 = 4096;

/// How link members that resolve inside the archive are placed.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum LinkRule {
    /// A link that resolves to a regular file is placed as a hard link of that file, whose
    /// bytes count again against the unpacked bound. A link to a folder is refused. No
    /// symbolic link is created.
    FilesAsHardLinks,
    /// On Unix, a symbolic link that resolves to a file or a folder is created as the
    /// symbolic link it is, with its own target. Elsewhere, as [`Self::FilesAsHardLinks`].
    Symbolic,
}

/// The bounds one extraction keeps.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Limits {
    pub(crate) entries: usize,
    pub(crate) unpacked_bytes: u64,
}

/// What an extraction placed.
#[derive(Debug, Default)]
pub(crate) struct Extracted {
    /// Every regular file, hard links included, with its digest.
    pub(crate) files: BTreeMap<RelativePath, Sha256Digest>,
    /// Every symbolic link created, with its target as the archive spells it.
    pub(crate) links: BTreeMap<RelativePath, String>,
    /// The members the archive declares.
    pub(crate) entries: usize,
}

/// Extracts the archive at `archive` into `destination`, an existing empty folder.
pub(crate) fn extract(
    archive: &Path,
    format: ArchiveFormat,
    destination: &Path,
    limits: Limits,
    rule: LinkRule,
    cancellation: &Cancellation,
) -> Result<Extracted, Error> {
    let mut tree = Tree::new(destination, limits, cancellation);
    match format {
        ArchiveFormat::Zip => read_zip(archive, &mut tree)?,
        ArchiveFormat::TarGz => read_tar(
            flate2::bufread::MultiGzDecoder::new(BufReader::new(File::open(archive)?)),
            &mut tree,
        )?,
        ArchiveFormat::TarZst => read_tar(
            ZstdFrames::new(BufReader::new(File::open(archive)?))?,
            &mut tree,
        )?,
    }
    tree.finish(rule)
}

fn read_zip(archive: &Path, tree: &mut Tree<'_>) -> Result<(), Error> {
    let mut zip = zip::ZipArchive::new(File::open(archive)?)?;
    if zip.len() > tree.limits.entries {
        return Err(Error::LimitExceeded);
    }
    for index in 0..zip.len() {
        tree.cancellation.check()?;
        let member = zip.by_index(index)?;
        tree.count()?;
        let name = member.name()?.into_owned();
        let kind = member.unix_mode().unwrap_or(0) & 0o170000;
        if member.is_symlink() {
            let relative = tree.admit(&name)?;
            if member.size() > LINK_TARGET_BYTES {
                return Err(Error::Invalid("archive link target too long".into()));
            }
            let mut target = Vec::new();
            member
                .take(LINK_TARGET_BYTES + 1)
                .read_to_end(&mut target)?;
            let target = String::from_utf8(target)
                .map_err(|_| Error::Invalid("non-UTF8 archive link".into()))?;
            tree.link(relative, target, LinkKind::Symbolic)?;
        } else if !matches!(kind, 0 | 0o040000 | 0o100000) {
            return Err(Error::Invalid("archive special files are forbidden".into()));
        } else if member.is_dir() {
            let relative = tree.admit(name.trim_end_matches('/'))?;
            tree.folder(&relative)?;
        } else {
            let relative = tree.admit(&name)?;
            let (size, mode) = (member.size(), member.unix_mode());
            tree.file(relative, member, size, mode)?;
        }
    }
    Ok(())
}

fn read_tar(source: impl Read, tree: &mut Tree<'_>) -> Result<(), Error> {
    let mut archive = tar::Archive::new(source);
    for entry in archive.entries()? {
        tree.cancellation.check()?;
        let entry = entry?;
        let kind = entry.header().entry_type();
        if kind.is_pax_global_extensions() {
            continue;
        }
        tree.count()?;
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
        let relative = tree.admit(name)?;
        if kind.is_dir() {
            tree.folder(&relative)?;
        } else if kind.is_file() || kind.is_contiguous() {
            let (size, mode) = (entry.size(), entry.header().mode().ok());
            tree.file(relative, entry, size, mode)?;
        } else if kind.is_symlink() || kind.is_hard_link() {
            let target = entry
                .link_name_bytes()
                .ok_or_else(|| Error::Invalid("archive link without a target".into()))?;
            let target = String::from_utf8(target.into_owned())
                .map_err(|_| Error::Invalid("non-UTF8 archive link".into()))?;
            let kind = if kind.is_symlink() {
                LinkKind::Symbolic
            } else {
                LinkKind::Hard
            };
            tree.link(relative, target, kind)?;
        } else {
            return Err(Error::Invalid("archive special files are forbidden".into()));
        }
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum LinkKind {
    /// Read from the link's own folder.
    Symbolic,
    /// Read from the archive's root.
    Hard,
}

struct Link {
    path: RelativePath,
    target: String,
    kind: LinkKind,
}

/// What a link resolves to among the archive's members; the empty key is the root.
#[derive(Clone, Debug, Eq, PartialEq)]
enum Node {
    File(String),
    Folder(String),
}

/// The members read so far, with the bounds they count against.
struct Tree<'a> {
    destination: &'a Path,
    limits: Limits,
    cancellation: &'a Cancellation,
    names: MemberNames,
    files: BTreeMap<String, (Sha256Digest, u64)>,
    folders: BTreeSet<String>,
    links: BTreeMap<String, Link>,
    total: u64,
    entries: usize,
}

impl<'a> Tree<'a> {
    fn new(destination: &'a Path, limits: Limits, cancellation: &'a Cancellation) -> Self {
        Self {
            destination,
            limits,
            cancellation,
            names: MemberNames::default(),
            files: BTreeMap::new(),
            folders: BTreeSet::new(),
            links: BTreeMap::new(),
            total: 0,
            entries: 0,
        }
    }

    fn count(&mut self) -> Result<(), Error> {
        self.entries += 1;
        if self.entries > self.limits.entries {
            return Err(Error::LimitExceeded);
        }
        Ok(())
    }

    fn admit(&mut self, name: &str) -> Result<RelativePath, Error> {
        let relative = RelativePath::new(name)?;
        self.names.admit(&relative)?;
        Ok(relative)
    }

    fn folder(&mut self, relative: &RelativePath) -> Result<(), Error> {
        fs::create_dir_all(relative.under(self.destination))?;
        self.folders.insert(relative.as_str().to_owned());
        Ok(())
    }

    fn file(
        &mut self,
        relative: RelativePath,
        member: impl Read,
        size: u64,
        mode: Option<u32>,
    ) -> Result<(), Error> {
        if size > self.limits.unpacked_bytes.saturating_sub(self.total) {
            return Err(Error::LimitExceeded);
        }
        let before = self.total;
        let digest = write_member(
            member,
            &relative.under(self.destination),
            mode,
            self.limits.unpacked_bytes,
            &mut self.total,
            self.cancellation,
        )?;
        let written = self.total - before;
        self.files
            .insert(relative.as_str().to_owned(), (digest, written));
        Ok(())
    }

    fn link(&mut self, path: RelativePath, target: String, kind: LinkKind) -> Result<(), Error> {
        if target.is_empty()
            || target.len() as u64 > LINK_TARGET_BYTES
            || target.starts_with('/')
            || target.contains(['\\', '\0'])
        {
            return Err(Error::Invalid("archive link leaves the archive".into()));
        }
        self.links
            .insert(path.as_str().to_owned(), Link { path, target, kind });
        Ok(())
    }

    /// Resolves and places every link, then checks what is on disk.
    fn finish(mut self, rule: LinkRule) -> Result<Extracted, Error> {
        self.imply_folders()?;
        let mut resolved = Vec::with_capacity(self.links.len());
        for (key, link) in &self.links {
            self.cancellation.check()?;
            resolved.push((key.clone(), self.resolve(link)?));
        }
        self.refuse_looping_folders(&resolved)?;
        let mut extracted = Extracted {
            entries: self.entries,
            ..Extracted::default()
        };
        for (key, node) in resolved {
            self.cancellation.check()?;
            let link = &self.links[&key];
            let path = link.path.under(self.destination);
            let symbolic = rule == LinkRule::Symbolic && link.kind == LinkKind::Symbolic;
            match node {
                Node::File(file) if !(symbolic && cfg!(unix)) => {
                    let (digest, size) = self.files[&file].clone();
                    self.total = self.total.saturating_add(size);
                    if self.total > self.limits.unpacked_bytes {
                        return Err(Error::LimitExceeded);
                    }
                    create_parent(&path)?;
                    fs::hard_link(self.destination.join(&file), &path)?;
                    extracted.files.insert(link.path.clone(), digest);
                }
                Node::Folder(_) if !(symbolic && cfg!(unix)) => {
                    return Err(Error::Invalid("archive link to a folder".into()));
                }
                _ => {
                    create_parent(&path)?;
                    symbolic_link(&link.target, &path)?;
                    extracted
                        .links
                        .insert(link.path.clone(), link.target.clone());
                }
            }
        }
        for (file, (digest, _)) in self.files {
            extracted.files.insert(RelativePath::new(file)?, digest);
        }
        verify_links(self.destination, &extracted.links)?;
        Ok(extracted)
    }

    /// Adds every folder a member path implies, refusing a member whose path passes
    /// through a link.
    fn imply_folders(&mut self) -> Result<(), Error> {
        let members: Vec<String> = self
            .files
            .keys()
            .chain(&self.folders)
            .chain(self.links.keys())
            .cloned()
            .collect();
        for member in members {
            let mut end = 0;
            while let Some(found) = member[end..].find('/') {
                let prefix = &member[..end + found];
                if self.links.contains_key(prefix) {
                    return Err(Error::Invalid("archive member inside a link".into()));
                }
                self.folders.insert(prefix.to_owned());
                end += found + 1;
            }
        }
        Ok(())
    }

    /// What `link` names among the members, resolved the way the kernel resolves it.
    fn resolve(&self, link: &Link) -> Result<Node, Error> {
        let mut reached: Vec<&str> = match link.kind {
            LinkKind::Symbolic => {
                let mut folder: Vec<&str> = link.path.as_str().split('/').collect();
                folder.pop();
                folder
            }
            LinkKind::Hard => Vec::new(),
        };
        let mut pending: Vec<&str> = link.target.split('/').rev().collect();
        let mut hops = 1;
        while let Some(part) = pending.pop() {
            match part {
                "" | "." => {}
                ".." => {
                    reached
                        .pop()
                        .ok_or_else(|| Error::Invalid("archive link leaves the archive".into()))?;
                }
                name => {
                    reached.push(name);
                    let key = reached.join("/");
                    if let Some(next) = self.links.get(&key) {
                        hops += 1;
                        if hops > LINK_HOPS {
                            return Err(Error::Invalid("archive links form a cycle".into()));
                        }
                        reached.pop();
                        if next.kind == LinkKind::Hard {
                            reached.clear();
                        }
                        pending.extend(next.target.split('/').rev());
                    } else if !pending.is_empty() && !self.folders.contains(&key) {
                        return Err(Error::Invalid(
                            "archive link passes through no folder".into(),
                        ));
                    }
                }
            }
        }
        let key = reached.join("/");
        if key.is_empty() || self.folders.contains(&key) {
            Ok(Node::Folder(key))
        } else if self.files.contains_key(&key) {
            Ok(Node::File(key))
        } else {
            Err(Error::Invalid(
                "archive link names nothing in the archive".into(),
            ))
        }
    }

    /// Refuses a link to a folder that holds a link to a folder, the link itself included,
    /// so that following folder links from anywhere always ends.
    fn refuse_looping_folders(&self, resolved: &[(String, Node)]) -> Result<(), Error> {
        let folder_links: BTreeSet<&str> = resolved
            .iter()
            .filter(|(_, node)| matches!(node, Node::Folder(_)))
            .map(|(key, _)| key.as_str())
            .collect();
        for (_, node) in resolved {
            let Node::Folder(folder) = node else {
                continue;
            };
            let inside = if folder.is_empty() {
                !folder_links.is_empty()
            } else {
                let prefix = format!("{folder}/");
                folder_links
                    .range(prefix.as_str()..)
                    .next()
                    .is_some_and(|key| key.starts_with(&prefix))
            };
            if inside {
                return Err(Error::Invalid("archive links form a cycle".into()));
            }
        }
        Ok(())
    }
}

fn create_parent(path: &Path) -> Result<(), Error> {
    fs::create_dir_all(
        path.parent()
            .ok_or_else(|| Error::Invalid("archive path has no parent".into()))?,
    )?;
    Ok(())
}

#[cfg(unix)]
fn symbolic_link(target: &str, path: &Path) -> Result<(), Error> {
    std::os::unix::fs::symlink(target, path)?;
    Ok(())
}

#[cfg(not(unix))]
fn symbolic_link(_target: &str, _path: &Path) -> Result<(), Error> {
    Err(Error::Invalid(
        "archive links are placed as files here".into(),
    ))
}

/// Walks `destination` without following links: every link found must be one of
/// `created`, with the same target, and must resolve on disk inside `destination`.
fn verify_links(destination: &Path, created: &BTreeMap<RelativePath, String>) -> Result<(), Error> {
    let root = fs::canonicalize(destination)?;
    let mut found = 0usize;
    let mut pending = vec![destination.to_path_buf()];
    while let Some(folder) = pending.pop() {
        for entry in fs::read_dir(&folder)? {
            let path = entry?.path();
            let meta = fs::symlink_metadata(&path)?;
            if meta.is_symlink() {
                let relative = RelativePath::from_native(
                    path.strip_prefix(destination)
                        .map_err(|_| Error::Invalid("archive path escaped".into()))?,
                )?;
                let target = fs::read_link(&path)?;
                let resolved = fs::canonicalize(&path)
                    .map_err(|_| Error::Integrity("archive link names nothing".into()))?;
                if created.get(&relative).map(Path::new) != Some(target.as_path())
                    || !resolved.starts_with(&root)
                {
                    return Err(Error::Integrity("archive link resolves outside".into()));
                }
                found += 1;
                continue;
            }
            filesystem::refuse_metadata_links(&meta)?;
            if meta.is_dir() {
                pending.push(path);
            }
        }
    }
    if found != created.len() {
        return Err(Error::Integrity("archive link missing".into()));
    }
    Ok(())
}

/// Every member name an archive declares, refused when two spell one path, or one
/// folder, differently only by case: they would collide on a case-insensitive volume.
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
                return Err(Error::Invalid("archive folder spelled two ways".into()));
            }
        }
        Ok(())
    }
}

/// Streams one member's bytes into a new file at `path`, counting them against `limit`,
/// and returns their digest.
fn write_member(
    mut member: impl Read,
    path: &Path,
    mode: Option<u32>,
    limit: u64,
    total: &mut u64,
    cancellation: &Cancellation,
) -> Result<Sha256Digest, Error> {
    create_parent(path)?;
    let mut out = File::options().write(true).create_new(true).open(path)?;
    let mut hash = Sha256::new();
    let mut buffer = vec![0u8; 64 * 1024];
    loop {
        cancellation.check()?;
        let n = member.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        *total += n as u64;
        if *total > limit {
            return Err(Error::LimitExceeded);
        }
        hash.update(&buffer[..n]);
        out.write_all(&buffer[..n])?;
    }
    out.sync_all()?;
    filesystem::archive_permissions(path, mode)?;
    Sha256Digest::from_hash(hash.finalize())
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

#[cfg(test)]
mod tests;
