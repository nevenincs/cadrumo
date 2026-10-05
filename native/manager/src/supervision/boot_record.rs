//! Reading a supervised runtime's non-private boot record.
//!
//! The record is an identity claim used for adoption, never authority. The runtime owns its
//! grammar and location; the conformance vectors in `tests/protocol_vectors.json` hold this
//! reader to the Python owner's verdicts, and to the location the storage taxonomy registers.

use super::json::{FlatObject, canonical_uuid, text, unsigned};
use super::protocol::Admission;
use serde_json::Value;
use std::fs::{self, File};
use std::io::{self, Read};
use std::path::{Path, PathBuf};

/// Location of the record below the storage root, one component per element.
pub const BOOT_RECORD_LOCATION: [&str; 2] = [".runtime", "boot.json"];

/// Upper bound of the encoded record.
pub const MAXIMUM_BOOT_RECORD_BYTES: u64 = 8192;

const SCHEMA_VERSION: u64 = 1;
const MAXIMUM_VERSION_CHARACTERS: usize = 64;
const MAXIMUM_PACKAGE_DIRECTORY_CHARACTERS: usize = 1024;

/// One supervised runtime boot's identity claim.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BootRecord {
    pub boot_id: String,
    pub pid: u32,
    /// The platform-native creation stamp of `pid`: FILETIME ticks on Windows.
    pub process_created: u64,
    pub version: String,
    /// The absolute versioned package root, absent outside a native package.
    pub package_directory: Option<PathBuf>,
    pub admission: Admission,
}

/// Why no boot record could be read.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BootRecordUnavailable {
    /// Neither the `.runtime` directory nor the record exists.
    Absent,
    /// The record exists but is not a regular file within its bound, or is malformed.
    Unreadable,
}

/// The record location under an absolute storage root.
pub fn boot_record_path(storage_root: &Path) -> PathBuf {
    BOOT_RECORD_LOCATION
        .iter()
        .fold(storage_root.to_path_buf(), |path, part| path.join(part))
}

/// Parse record bytes strictly: one flat object, no repeated or unknown member.
pub fn decode_boot_record(raw: &[u8]) -> Option<BootRecord> {
    if u64::try_from(raw.len()).ok()? > MAXIMUM_BOOT_RECORD_BYTES {
        return None;
    }
    let mut object = FlatObject::parse(raw)?;
    unsigned(
        &object.take("schema_version")?,
        SCHEMA_VERSION,
        SCHEMA_VERSION,
    )?;
    let boot_id = canonical_uuid(&object.take("boot_id")?)?.to_owned();
    let pid = unsigned(&object.take("pid")?, 1, u64::from(u32::MAX))?;
    let process_created = unsigned(&object.take("process_created")?, 1, u64::MAX)?;
    let version = text(&object.take("version")?, MAXIMUM_VERSION_CHARACTERS)?.to_owned();
    let package_directory = match object.take("package_directory")? {
        Value::Null => None,
        value => {
            let directory = PathBuf::from(text(&value, MAXIMUM_PACKAGE_DIRECTORY_CHARACTERS)?);
            if !directory.is_absolute() {
                return None;
            }
            Some(directory)
        }
    };
    let admission = Admission::parse(&object.take("admission")?)?;
    if !object.is_exhausted() {
        return None;
    }
    Some(BootRecord {
        boot_id,
        pid: u32::try_from(pid).ok()?,
        process_created,
        version,
        package_directory,
        admission,
    })
}

/// Read the published record without creating anything.
pub fn read_boot_record(storage_root: &Path) -> Result<BootRecord, BootRecordUnavailable> {
    let path = boot_record_path(storage_root);
    let raw = match read_bounded_regular_file(&path) {
        Ok(raw) => raw,
        Err(error) if error.kind() == io::ErrorKind::NotFound => {
            return Err(BootRecordUnavailable::Absent);
        }
        Err(_) => return Err(BootRecordUnavailable::Unreadable),
    };
    decode_boot_record(&raw).ok_or(BootRecordUnavailable::Unreadable)
}

/// Read a regular file that is no link or reparse point, refusing one above the bound.
fn read_bounded_regular_file(path: &Path) -> io::Result<Vec<u8>> {
    let refused = || io::Error::new(io::ErrorKind::InvalidData, "not a bounded regular file");
    if !is_plain_file(&fs::symlink_metadata(path)?) {
        return Err(refused());
    }
    let mut file = File::open(path)?;
    let metadata = file.metadata()?;
    if !is_plain_file(&metadata) || metadata.len() > MAXIMUM_BOOT_RECORD_BYTES {
        return Err(refused());
    }
    let mut raw = Vec::new();
    file.by_ref()
        .take(MAXIMUM_BOOT_RECORD_BYTES + 1)
        .read_to_end(&mut raw)?;
    if u64::try_from(raw.len()).map_err(|_| refused())? > MAXIMUM_BOOT_RECORD_BYTES {
        return Err(refused());
    }
    Ok(raw)
}

#[cfg(windows)]
fn is_plain_file(metadata: &fs::Metadata) -> bool {
    use std::os::windows::fs::MetadataExt;
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
    metadata.file_type().is_file() && metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT == 0
}

#[cfg(not(windows))]
fn is_plain_file(metadata: &fs::Metadata) -> bool {
    metadata.file_type().is_file()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn absolute_directory() -> &'static str {
        if cfg!(windows) {
            "C:\\cadrumo\\1.2.3"
        } else {
            "/opt/cadrumo/1.2.3"
        }
    }

    fn record(package_directory: Value) -> Vec<u8> {
        serde_json::json!({
            "admission": "native",
            "boot_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
            "package_directory": package_directory,
            "pid": 4321,
            "process_created": 133_000_000_000_000_000_u64,
            "schema_version": 1,
            "version": "1.2.3",
        })
        .to_string()
        .into_bytes()
    }

    #[test]
    fn an_absolute_package_directory_is_kept() {
        let decoded =
            decode_boot_record(&record(Value::from(absolute_directory()))).expect("valid record");
        assert_eq!(
            decoded.package_directory.as_deref(),
            Some(Path::new(absolute_directory()))
        );
        assert_eq!(decoded.process_created, 133_000_000_000_000_000);
    }

    #[test]
    fn a_relative_package_directory_is_refused() {
        assert!(decode_boot_record(&record(Value::from("relative\\dir"))).is_none());
        assert!(decode_boot_record(&record(Value::Null)).is_some());
    }

    #[test]
    fn a_record_above_the_bound_is_refused() {
        let mut raw = record(Value::Null);
        raw.extend(std::iter::repeat_n(b' ', 8192));
        assert!(decode_boot_record(&raw).is_none());
    }

    #[test]
    fn the_location_sits_beside_the_installation_record() {
        let root = Path::new(absolute_directory());
        assert_eq!(
            boot_record_path(root),
            root.join(".runtime").join("boot.json")
        );
    }
}
