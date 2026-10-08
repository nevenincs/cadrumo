use crate::{component::Cancellation, error::Error, value::Sha256Digest};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::Path,
};

pub(crate) fn refuse_links(path: &Path) -> Result<(), Error> {
    for ancestor in path.ancestors() {
        match fs::symlink_metadata(ancestor) {
            Ok(meta) => refuse_metadata_links(&meta)?,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
    }
    Ok(())
}

/// Validate metadata obtained without following this entry's link/reparse point.
pub(crate) fn refuse_metadata_links(meta: &fs::Metadata) -> Result<(), Error> {
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
    digest_opened(&mut file)
}

/// The caller has admitted the path and checked that the opened descriptor is regular.
pub(crate) fn digest_opened(file: &mut File) -> Result<Sha256Digest, Error> {
    digest_reader(file, &Cancellation::default())
}

/// The descriptor admission remains with the caller. Cancellation cannot interrupt
/// a blocked operating-system read, but is observed before and after each chunk.
pub(crate) fn digest_reader(
    reader: &mut impl Read,
    cancellation: &Cancellation,
) -> Result<Sha256Digest, Error> {
    let mut hash = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        cancellation.check()?;
        let read = reader.read(&mut buffer);
        cancellation.check()?;
        let n = read?;
        if n == 0 {
            break;
        }
        hash.update(&buffer[..n]);
    }
    Sha256Digest::new(format!("{:x}", hash.finalize()))
}

pub(crate) const JSON_BYTES_LIMIT: u64 = 16 * 1024 * 1024;

pub(crate) fn json_file<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T, Error> {
    Ok(serde_json::from_slice(&json_bytes(path)?)?)
}

pub(crate) fn json_file_cancellable<T: serde::de::DeserializeOwned>(
    path: &Path,
    cancellation: &Cancellation,
) -> Result<T, Error> {
    cancellation.check()?;
    let bytes = json_bytes(path);
    cancellation.check()?;
    let parsed = serde_json::from_slice(&bytes?);
    cancellation.check()?;
    Ok(parsed?)
}

pub(crate) fn json_bytes(path: &Path) -> Result<Vec<u8>, Error> {
    refuse_links(path)?;
    if !fs::metadata(path)?.is_file() {
        return Err(Error::Integrity("expected a regular JSON file".into()));
    }
    let mut bytes = Vec::new();
    File::open(path)?
        .take(JSON_BYTES_LIMIT + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > JSON_BYTES_LIMIT {
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

#[cfg(test)]
mod cancellation_tests {
    use super::*;
    use std::io::{self, Cursor};

    struct CancellingReader<'a> {
        cancellation: &'a Cancellation,
        reads: usize,
        fail: bool,
    }

    impl Read for CancellingReader<'_> {
        fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
            self.reads += 1;
            assert!(
                self.reads <= 2,
                "must not read another chunk after cancellation"
            );
            assert_eq!(bytes.len(), 65536);
            bytes.fill(7);
            if self.reads == 2 {
                self.cancellation.cancel();
                if self.fail {
                    return Err(io::Error::other("isolated reader failure"));
                }
            }
            Ok(bytes.len())
        }
    }

    #[test]
    fn stream_checks_cancellation_after_a_real_read_boundary_and_preserves_it_over_io_error() {
        for fail in [false, true] {
            let cancellation = Cancellation::default();
            let mut reader = CancellingReader {
                cancellation: &cancellation,
                reads: 0,
                fail,
            };
            assert!(matches!(
                digest_reader(&mut reader, &cancellation),
                Err(Error::Cancelled)
            ));
            assert_eq!(reader.reads, 2);
        }
    }

    #[test]
    fn cancelled_stream_does_not_read_and_uncancelled_stream_hashes_all_chunks() {
        let cancellation = Cancellation::default();
        cancellation.cancel();
        let mut reader = CancellingReader {
            cancellation: &cancellation,
            reads: 0,
            fail: false,
        };
        assert!(matches!(
            digest_reader(&mut reader, &cancellation),
            Err(Error::Cancelled)
        ));
        assert_eq!(reader.reads, 0);
        let bytes = vec![11u8; 131_073];
        assert_eq!(
            digest_reader(&mut Cursor::new(&bytes), &Cancellation::default()).unwrap(),
            Sha256Digest::new(format!("{:x}", Sha256::digest(&bytes))).unwrap()
        );
    }
}
