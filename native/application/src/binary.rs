//! Header and digest checks for a caller-selected executable, without executing it.
use crate::{error::Error, filesystem, value::Sha256Digest};
use object::{Object, read::macho::FatArch};
use sha2::{Digest, Sha256};
use std::{fs::File, io::Read, path::Path};

pub use object::{Architecture, BinaryFormat};

/// CPU and container facts supplied by the canonical target declaration.
#[derive(Clone, Copy, Debug)]
pub struct BinaryExpectation {
    pub architecture: Architecture,
    pub format: BinaryFormat,
}

impl BinaryExpectation {
    /// Build-host facts, not a declaration of supported release targets.
    pub fn host() -> Result<Self, Error> {
        let architecture = match std::env::consts::ARCH {
            "x86_64" => Architecture::X86_64,
            "aarch64" => Architecture::Aarch64,
            _ => return Err(Error::Incompatible("unsupported probe host CPU".into())),
        };
        let format = match std::env::consts::OS {
            "windows" => BinaryFormat::Pe,
            "linux" => BinaryFormat::Elf,
            "macos" => BinaryFormat::MachO,
            _ => return Err(Error::Incompatible("unsupported probe host OS".into())),
        };
        Ok(Self {
            architecture,
            format,
        })
    }
}

/// Verify bytes and a matching executable header. This does not prove loader dependencies,
/// OS deployment floors, publisher authenticity, or resistance to a concurrent file writer.
pub fn verify(
    path: &Path,
    digest: &Sha256Digest,
    expected: BinaryExpectation,
) -> Result<(), Error> {
    filesystem::absolute_root(path)?;
    filesystem::require_executable(path)?;
    let file = File::open(path)?;
    if !file.metadata()?.is_file() {
        return Err(Error::Integrity("expected a regular executable".into()));
    }
    let mut bytes = Vec::new();
    const LIMIT: u64 = 128 * 1024 * 1024;
    file.take(LIMIT + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > LIMIT {
        return Err(Error::LimitExceeded);
    }
    if Sha256Digest::new(format!("{:x}", Sha256::digest(&bytes)))? != *digest {
        return Err(Error::Integrity("executable digest differs".into()));
    }
    verify_header(&bytes, expected)
}

fn verify_header(bytes: &[u8], expected: BinaryExpectation) -> Result<(), Error> {
    let invalid = || Error::Incompatible("executable header differs or is malformed".into());
    match object::FileKind::parse(bytes).map_err(|_| invalid())? {
        object::FileKind::MachOFat32 => {
            if expected.format != BinaryFormat::MachO {
                return Err(invalid());
            }
            let fat = object::read::macho::MachOFatFile32::parse(bytes).map_err(|_| invalid())?;
            for arch in fat.arches() {
                if arch.architecture() == expected.architecture {
                    return verify_thin(arch.data(bytes).map_err(|_| invalid())?, expected);
                }
            }
            Err(invalid())
        }
        object::FileKind::MachOFat64 => {
            if expected.format != BinaryFormat::MachO {
                return Err(invalid());
            }
            let fat = object::read::macho::MachOFatFile64::parse(bytes).map_err(|_| invalid())?;
            for arch in fat.arches() {
                if arch.architecture() == expected.architecture {
                    return verify_thin(arch.data(bytes).map_err(|_| invalid())?, expected);
                }
            }
            Err(invalid())
        }
        _ => verify_thin(bytes, expected),
    }
}

fn verify_thin(bytes: &[u8], expected: BinaryExpectation) -> Result<(), Error> {
    let file = object::File::parse(bytes)
        .map_err(|_| Error::Incompatible("malformed executable".into()))?;
    // ELF position-independent executables use ET_DYN but need a nonzero entry point.
    // This is a header admission check, not a substitute for the native loader.
    let executable = file.kind() == object::ObjectKind::Executable
        || (file.format() == BinaryFormat::Elf
            && file.kind() == object::ObjectKind::Dynamic
            && file.entry() != 0);
    if file.architecture() != expected.architecture
        || file.format() != expected.format
        || !executable
    {
        return Err(Error::Incompatible("executable target differs".into()));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mach(kind: u32) -> Vec<u8> {
        [0xfeedfacfu32, 0x0100000c, 0, kind, 0, 0, 0, 0]
            .into_iter()
            .flat_map(u32::to_le_bytes)
            .collect()
    }

    #[test]
    fn macho_executable_and_fat_slice_require_correct_outer_and_inner_target() {
        let expected = BinaryExpectation {
            architecture: Architecture::Aarch64,
            format: BinaryFormat::MachO,
        };
        let thin = mach(2);
        verify_header(&thin, expected).unwrap();
        assert!(verify_header(&mach(6), expected).is_err(), "dylib accepted");
        let mut fat: Vec<u8> = [0xcafebabeu32, 1, 0x0100000c, 0, 4096, 32, 12]
            .into_iter()
            .flat_map(u32::to_be_bytes)
            .collect();
        fat.resize(4096, 0);
        fat.extend(&thin);
        verify_header(&fat, expected).unwrap();
        assert!(
            verify_header(
                &fat,
                BinaryExpectation {
                    format: BinaryFormat::Elf,
                    ..expected
                }
            )
            .is_err()
        );
        assert!(
            verify_header(
                &fat,
                BinaryExpectation {
                    architecture: Architecture::X86_64,
                    ..expected
                }
            )
            .is_err()
        );
        fat.truncate(4100);
        assert!(verify_header(&fat, expected).is_err());
    }
}
