//! Structured native diagnostic files; payloads, arguments and environment never enter them.
use crate::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    filesystem,
};
use serde::Serialize;
use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogPaths {
    pub current: PathBuf,
    pub lock: PathBuf,
}
impl LogPaths {
    pub fn new(directory: &Path) -> Result<Self> {
        filesystem::absolute_root(directory).map_err(|e| failure().caused_by(e))?;
        Ok(Self {
            current: directory.join("cadrumo-native.jsonl"),
            lock: directory.join("cadrumo-native.lock"),
        })
    }
    pub fn for_file(current: &Path) -> Result<Self> {
        filesystem::absolute_root(current).map_err(|e| failure().caused_by(e))?;
        if current.file_name().is_none() {
            return Err(failure());
        }
        Ok(Self {
            current: current.to_owned(),
            lock: suffixed(current, ".lock"),
        })
    }
    fn backup(&self, index: u32) -> PathBuf {
        suffixed(&self.current, &format!(".{index}"))
    }
}
fn suffixed(path: &Path, suffix: &str) -> PathBuf {
    let mut name = path.as_os_str().to_owned();
    name.push(suffix);
    name.into()
}
fn failure() -> ApplicationError {
    ApplicationError::new(ErrorCode::LogUnavailable, Operation::Logging)
}

pub struct LogFile {
    pub paths: LogPaths,
    max_bytes: u64,
    backups: u32,
}
impl LogFile {
    pub fn new(directory: &Path, max_bytes: u64, backups: u32) -> Result<Self> {
        Self::with_paths(LogPaths::new(directory)?, max_bytes, backups)
    }
    pub fn for_file(current: &Path, max_bytes: u64, backups: u32) -> Result<Self> {
        Self::with_paths(LogPaths::for_file(current)?, max_bytes, backups)
    }
    fn with_paths(paths: LogPaths, max_bytes: u64, backups: u32) -> Result<Self> {
        if max_bytes == 0 {
            return Err(failure());
        }
        Ok(Self {
            paths,
            max_bytes,
            backups,
        })
    }
    pub fn append(&self, record: &crate::diagnostics::Event) -> Result<()> {
        let directory = self.paths.current.parent().ok_or_else(failure)?;
        filesystem::absolute_root(directory).map_err(|e| failure().caused_by(e))?;
        fs::create_dir_all(directory).map_err(|e| failure().caused_by(e))?;
        let lock = open(&self.paths.lock)?;
        lock.try_lock().map_err(|e| failure().caused_by(e))?;
        let mut bytes = serde_json::to_vec(record).map_err(|e| failure().caused_by(e))?;
        bytes.push(b'\n');
        if bytes.len() as u64 > self.max_bytes {
            return Err(failure());
        }
        let existing = open(&self.paths.current)?;
        let size = existing
            .metadata()
            .map_err(|e| failure().caused_by(e))?
            .len();
        drop(existing);
        if size + bytes.len() as u64 > self.max_bytes {
            if self.backups == 0 {
                fs::remove_file(&self.paths.current).map_err(|e| failure().caused_by(e))?;
            } else {
                for index in (1..=self.backups).rev() {
                    let destination = self.paths.backup(index);
                    filesystem::absolute_root(&destination).map_err(|e| failure().caused_by(e))?;
                    if destination.exists() {
                        fs::remove_file(&destination).map_err(|e| failure().caused_by(e))?;
                    }
                    let source = if index == 1 {
                        self.paths.current.clone()
                    } else {
                        self.paths.backup(index - 1)
                    };
                    filesystem::absolute_root(&source).map_err(|e| failure().caused_by(e))?;
                    if source.exists() {
                        fs::rename(source, destination).map_err(|e| failure().caused_by(e))?;
                    }
                }
            }
        }
        let mut file = open(&self.paths.current)?;
        file.write_all(&bytes)
            .and_then(|()| file.flush())
            .map_err(|e| failure().caused_by(e))
    }
}
fn open(path: &Path) -> Result<File> {
    filesystem::absolute_root(path).map_err(|e| failure().caused_by(e))?;
    let mut options = OpenOptions::new();
    options.create(true).read(true).append(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    options.open(path).map_err(|e| failure().caused_by(e))
}
