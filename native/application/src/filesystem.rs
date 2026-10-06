use crate::{error::Error, value::Sha256Digest};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::Path,
};

pub(crate) fn refuse_links(path: &Path) -> Result<(), Error> {
    for ancestor in path.ancestors() {
        match fs::symlink_metadata(ancestor) {
            Ok(meta) => {
                #[cfg(windows)]
                let linked = {
                    use std::os::windows::fs::MetadataExt;
                    meta.file_attributes() & 0x400 != 0
                };
                #[cfg(not(windows))]
                let linked = meta.is_symlink();
                if linked {
                    return Err(Error::Invalid("linked filesystem path".into()));
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
    }
    Ok(())
}

pub(crate) fn absolute_root(path: &Path) -> Result<(), Error> {
    if !path.is_absolute()
        || path
            .components()
            .any(|c| matches!(c, std::path::Component::ParentDir))
    {
        return Err(Error::Invalid(
            "owner must supply an absolute resolved root".into(),
        ));
    }
    refuse_links(path)
}

pub(crate) fn digest(path: &Path) -> Result<Sha256Digest, Error> {
    refuse_links(path)?;
    if !fs::metadata(path)?.is_file() {
        return Err(Error::Integrity("expected a regular file".into()));
    }
    let mut file = File::open(path)?;
    if !file.metadata()?.is_file() {
        return Err(Error::Integrity("expected a regular file".into()));
    }
    let mut hash = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        hash.update(&buffer[..n]);
    }
    Sha256Digest::new(format!("{:x}", hash.finalize()))
}

pub(crate) fn json_file<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T, Error> {
    Ok(serde_json::from_slice(&json_bytes(path)?)?)
}

pub(crate) fn json_bytes(path: &Path) -> Result<Vec<u8>, Error> {
    refuse_links(path)?;
    if !fs::metadata(path)?.is_file() {
        return Err(Error::Integrity("expected a regular JSON file".into()));
    }
    let mut bytes = Vec::new();
    File::open(path)?
        .take(16 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > 16 * 1024 * 1024 {
        return Err(Error::LimitExceeded);
    }
    Ok(bytes)
}

pub(crate) fn write_json<T: serde::Serialize>(path: &Path, value: &T) -> Result<(), Error> {
    let mut file = File::options().write(true).create_new(true).open(path)?;
    file.write_all(&serde_json::to_vec(value)?)?;
    file.sync_all()?;
    Ok(())
}

pub(crate) fn archive_permissions(path: &Path, mode: Option<u32>) -> Result<(), Error> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = if mode.unwrap_or(0) & 0o111 != 0 {
            0o700
        } else {
            0o600
        };
        fs::set_permissions(path, fs::Permissions::from_mode(mode))?;
    }
    #[cfg(not(unix))]
    let _ = (path, mode);
    Ok(())
}

pub(crate) fn require_executable(path: &Path) -> Result<(), Error> {
    refuse_links(path)?;
    if !path.is_file() {
        return Err(Error::Integrity("missing executable".into()));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if fs::metadata(path)?.permissions().mode() & 0o100 == 0 {
            return Err(Error::Integrity(
                "component executable lacks execute permission".into(),
            ));
        }
    }
    Ok(())
}
