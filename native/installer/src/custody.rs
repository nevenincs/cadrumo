//! Stable local artifact custody across hash verification and native consumption.
use crate::admission::Refusal;
use std::{
    fs::File,
    os::windows::fs::{MetadataExt, OpenOptionsExt},
    path::{Component, Path, Prefix},
};

const REPARSE_POINT: u32 = 0x400;
const BACKUP_SEMANTICS: u32 = 0x0200_0000;
const OPEN_REPARSE_POINT: u32 = 0x0020_0000;

pub struct FileCustody {
    pub file: File,
    _parents: Vec<File>,
}

/// Hold every parent without delete sharing before opening the child. The final
/// file denies both writes and replacement until the complete operation settles.
/// No pathname verification result is reused without these live kernel handles.
pub fn file(path: &Path) -> Result<FileCustody, Refusal> {
    if !path.is_absolute()
        || !matches!(path.components().next(), Some(Component::Prefix(prefix)) if matches!(prefix.kind(), Prefix::Disk(_) | Prefix::VerbatimDisk(_)))
        || path
            .components()
            .any(|component| matches!(component, Component::ParentDir))
    {
        return Err(Refusal::InvalidRequest);
    }
    let mut parents = path.ancestors().skip(1).collect::<Vec<_>>();
    parents.reverse();
    let mut guards = Vec::with_capacity(parents.len());
    for parent in parents {
        let directory = File::options()
            .access_mode(0)
            .share_mode(3)
            .custom_flags(BACKUP_SEMANTICS | OPEN_REPARSE_POINT)
            .open(parent)
            .map_err(|_| Refusal::IncompleteInventory)?;
        let metadata = directory
            .metadata()
            .map_err(|_| Refusal::IncompleteInventory)?;
        if !metadata.is_dir() || metadata.file_attributes() & REPARSE_POINT != 0 {
            return Err(Refusal::InvalidRequest);
        }
        guards.push(directory);
    }
    let file = File::options()
        .read(true)
        .share_mode(1)
        .custom_flags(OPEN_REPARSE_POINT)
        .open(path)
        .map_err(|_| Refusal::IncompleteInventory)?;
    let metadata = file.metadata().map_err(|_| Refusal::IncompleteInventory)?;
    if !metadata.is_file() || metadata.file_attributes() & REPARSE_POINT != 0 {
        return Err(Refusal::InvalidRequest);
    }
    Ok(FileCustody {
        file,
        _parents: guards,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn admitted_artifact_and_ancestors_cannot_be_replaced_until_settlement() {
        let root = tempfile::tempdir().unwrap();
        let directory = root.path().join("source");
        std::fs::create_dir(&directory).unwrap();
        let source = directory.join("package.msi");
        std::fs::write(&source, b"admitted").unwrap();
        let guard = file(&source).unwrap();
        assert!(std::fs::write(&source, b"changed").is_err());
        assert!(std::fs::remove_file(&source).is_err());
        assert!(std::fs::rename(&directory, root.path().join("moved")).is_err());
        assert_eq!(std::fs::read(&source).unwrap(), b"admitted");
        drop(guard);
        std::fs::write(&source, b"released").unwrap();
        assert!(file(Path::new("relative.msi")).is_err());
        assert!(file(&directory).is_err());
    }
}
