//! The files a view moves: a download the person saves where the native save
//! dialog chose, and the files the person picks in the native open dialog for
//! a page's file chooser. Their bytes pass through this host to or from the
//! path the person chose and nowhere else: not into custody, a log, a
//! diagnostic or the window.
use cadrumo_application::view_stream::{lane::UploadFile, transfer::TransferChunk};
use std::{
    ffi::OsString,
    fs::{File, OpenOptions, remove_file, rename},
    io::{self, Write},
    path::{Path, PathBuf},
};
use tauri::Runtime;

/// The longest extension the save dialog's kind filter is built from.
const EXTENSION_LIMIT: usize = 16;
/// What ends the name of a download's file until it is whole.
const PARTIAL_SUFFIX: &str = ".cadrumo-part";

/// What the native dialogs answer. The real ones are the system's; a test
/// scripts them.
pub(crate) trait Dialogs: Send + Sync {
    /// The path the person chose to save `suggested` at, or `None` if the
    /// dialog was closed without a choice. The dialog asks before replacing a
    /// file.
    fn save(&self, suggested: &str) -> Option<PathBuf>;
    /// The files the person chose to open, none if the dialog was closed
    /// without a choice, and at most one unless `multiple`.
    fn open(&self, multiple: bool) -> Vec<PathBuf>;
}

/// The system dialogs over the window that asked.
pub(super) struct NativeDialogs<R: Runtime>(pub(super) tauri::WebviewWindow<R>);

impl<R: Runtime> Dialogs for NativeDialogs<R> {
    fn save(&self, suggested: &str) -> Option<PathBuf> {
        use tauri_plugin_dialog::DialogExt;
        let mut dialog = self
            .0
            .dialog()
            .file()
            .set_parent(&self.0)
            .set_file_name(suggested);
        if let Some(extension) = extension(suggested) {
            dialog = dialog.add_filter(extension.to_ascii_uppercase(), &[extension]);
        }
        dialog
            .blocking_save_file()
            .and_then(|chosen| chosen.into_path().ok())
    }

    fn open(&self, multiple: bool) -> Vec<PathBuf> {
        use tauri_plugin_dialog::DialogExt;
        let dialog = self.0.dialog().file().set_parent(&self.0);
        let chosen: Vec<_> = if multiple {
            dialog.blocking_pick_files().unwrap_or_default()
        } else {
            dialog.blocking_pick_file().into_iter().collect()
        };
        chosen
            .into_iter()
            .filter_map(|picked| picked.into_path().ok())
            .collect()
    }
}

/// The suffix after the last dot of a name the page suggested, when it can
/// stand as a dialog filter: short and plain.
fn extension(name: &str) -> Option<&str> {
    let (_, extension) = name.rsplit_once('.')?;
    ((1..=EXTENSION_LIMIT).contains(&extension.len())
        && extension.bytes().all(|byte| byte.is_ascii_alphanumeric()))
    .then_some(extension)
}

/// A download being written.
///
/// Its bytes go to a file of its own beside the chosen path until the transfer
/// is whole, and replace the chosen file only then, so a download that fails or
/// is stopped leaves a file the person agreed to replace as it was. The file's
/// name carries a random tag, so it never takes the place of a file the person
/// has. Dropping an unfinished download removes the partial file.
pub(super) struct Download {
    target: PathBuf,
    partial: PathBuf,
    file: Option<File>,
    written: u64,
}

impl Download {
    /// Begins a download to `target`, a path the save dialog returned.
    pub(super) fn create(target: PathBuf) -> io::Result<Self> {
        if !target.is_absolute() {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let mut name = OsString::from(target.file_name().ok_or(io::ErrorKind::InvalidInput)?);
        let mut tag = [0u8; 6];
        getrandom::fill(&mut tag).map_err(|error| io::Error::other(error.to_string()))?;
        let tag: String = tag.iter().map(|byte| format!("{byte:02x}")).collect();
        name.push(format!(".{tag}{PARTIAL_SUFFIX}"));
        let partial = target.with_file_name(name);
        let file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&partial)?;
        Ok(Self {
            target,
            partial,
            file: Some(file),
            written: 0,
        })
    }

    /// Writes the next chunk, which the receiver already checked for order.
    pub(super) fn write(&mut self, chunk: &TransferChunk) -> io::Result<()> {
        if chunk.offset != self.written {
            return Err(io::ErrorKind::InvalidData.into());
        }
        let file = self.file.as_mut().ok_or(io::ErrorKind::BrokenPipe)?;
        file.write_all(&chunk.data)?;
        self.written += chunk.data.len() as u64;
        Ok(())
    }

    /// Ends the download: `size` is the byte count the sender completed with.
    /// The chosen path then holds the bytes.
    pub(super) fn finish(mut self, size: u64) -> io::Result<()> {
        if self.written != size {
            // Dropping removes the partial file.
            return Err(io::ErrorKind::InvalidData.into());
        }
        let mut file = self.file.take().ok_or(io::ErrorKind::BrokenPipe)?;
        let flushed = file.flush().and_then(|()| file.sync_all());
        drop(file);
        flushed
            .and_then(|()| rename(&self.partial, &self.target))
            .inspect_err(|_| {
                let _ = remove_file(&self.partial);
            })
    }
}

impl Drop for Download {
    fn drop(&mut self) {
        if self.file.take().is_some() {
            // The partial file is this download's own; nothing else names it.
            let _ = remove_file(&self.partial);
        }
    }
}

/// The media type browsers give files of well-known kinds, for a page that
/// reads it; any other file goes without one and the page sees the generic type.
fn media_type(path: &Path) -> Option<&'static str> {
    let extension = path.extension()?.to_str()?.to_ascii_lowercase();
    Some(match extension.as_str() {
        "pdf" => "application/pdf",
        "xml" => "application/xml",
        "txt" => "text/plain",
        "csv" => "text/csv",
        "json" => "application/json",
        "zip" => "application/zip",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "p12" | "pfx" => "application/x-pkcs12",
        _ => return None,
    })
}

/// A file the person chose, opened for the lane's upload thread to read as it
/// goes. Nothing is copied: the file is read where it is.
pub(super) fn upload_file(path: &Path) -> io::Result<UploadFile> {
    let file = File::open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_file() {
        return Err(io::ErrorKind::InvalidInput.into());
    }
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or(io::ErrorKind::InvalidInput)?
        .to_owned();
    Ok(UploadFile {
        name,
        mime: media_type(path).map(str::to_owned),
        size: metadata.len(),
        source: Box::new(file),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use zeroize::Zeroizing;

    fn scratch(name: &str) -> PathBuf {
        let root =
            std::env::temp_dir().join(format!("cadrumo-sede-view-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        root
    }

    /// The names in `root` other than `except`.
    fn others(root: &Path, except: &str) -> Vec<String> {
        let mut names: Vec<String> = std::fs::read_dir(root)
            .unwrap()
            .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
            .filter(|name| name != except)
            .collect();
        names.sort();
        names
    }

    fn chunk(offset: u64, bytes: &[u8], last: bool) -> TransferChunk {
        TransferChunk {
            transfer_id: 1,
            offset,
            data: Zeroizing::new(bytes.to_vec()),
            last,
        }
    }

    #[test]
    fn a_whole_download_replaces_the_chosen_file_only_when_it_ends() {
        let root = scratch("whole");
        let target = root.join("report.pdf");
        std::fs::write(&target, b"the file the person agreed to replace").unwrap();
        let mut download = Download::create(target.clone()).unwrap();
        download.write(&chunk(0, b"abc", false)).unwrap();
        download.write(&chunk(3, b"de", true)).unwrap();
        assert_eq!(
            std::fs::read(&target).unwrap(),
            b"the file the person agreed to replace",
            "the chosen path is untouched until the transfer is whole"
        );
        assert_eq!(others(&root, "report.pdf").len(), 1, "the partial file");
        download.finish(5).unwrap();
        assert_eq!(std::fs::read(&target).unwrap(), b"abcde");
        assert!(others(&root, "report.pdf").is_empty());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_download_that_stops_leaves_the_chosen_file_and_no_partial_one() {
        let root = scratch("stopped");
        let target = root.join("report.pdf");
        std::fs::write(&target, b"original").unwrap();
        let mut download = Download::create(target.clone()).unwrap();
        download.write(&chunk(0, b"abc", false)).unwrap();
        let partial = others(&root, "report.pdf");
        assert_eq!(partial.len(), 1);
        assert!(partial[0].starts_with("report.pdf.") && partial[0].ends_with(PARTIAL_SUFFIX));
        drop(download);
        assert_eq!(std::fs::read(&target).unwrap(), b"original");
        assert!(others(&root, "report.pdf").is_empty());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_download_refuses_a_gap_a_short_end_and_a_path_that_is_not_absolute() {
        let root = scratch("refused");
        let target = root.join("report.pdf");
        let mut download = Download::create(target.clone()).unwrap();
        assert!(download.write(&chunk(1, b"x", false)).is_err());
        download.write(&chunk(0, b"abc", true)).unwrap();
        assert!(download.finish(4).is_err());
        assert!(!target.exists(), "a short download is not saved");
        assert!(others(&root, "report.pdf").is_empty());
        assert!(Download::create(PathBuf::from("report.pdf")).is_err());
        assert!(Download::create(root.join("missing").join("report.pdf")).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn two_downloads_to_one_path_never_share_a_partial_file_nor_take_a_persons_file() {
        let root = scratch("tagged");
        let target = root.join("report.pdf");
        let theirs = root.join("report.pdf.part");
        std::fs::write(&theirs, b"the person's own file").unwrap();
        let first = Download::create(target.clone()).unwrap();
        let second = Download::create(target.clone()).unwrap();
        assert_ne!(first.partial, second.partial);
        assert_eq!(std::fs::read(&theirs).unwrap(), b"the person's own file");
        drop((first, second));
        assert_eq!(std::fs::read(&theirs).unwrap(), b"the person's own file");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn an_upload_reads_the_chosen_file_where_it_is_and_names_its_kind() {
        let root = scratch("upload");
        let pdf = root.join("Declaración.PDF");
        std::fs::write(&pdf, b"%PDF").unwrap();
        let upload = upload_file(&pdf).unwrap();
        assert_eq!(upload.name, "Declaración.PDF");
        assert_eq!(upload.size, 4);
        assert_eq!(upload.mime.as_deref(), Some("application/pdf"));
        let other = root.join("notes.docx");
        std::fs::write(&other, b"x").unwrap();
        assert_eq!(upload_file(&other).unwrap().mime, None);
        assert!(upload_file(&root).is_err(), "a folder is not a file");
        assert!(upload_file(&root.join("missing.pdf")).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn the_save_dialog_filters_by_a_plain_short_extension_only() {
        assert_eq!(extension("report.pdf"), Some("pdf"));
        assert_eq!(extension("archive.tar.gz"), Some("gz"));
        for name in [
            "report",
            "report.",
            "a.b c",
            "a.pd/f",
            "a.0123456789abcdefg",
        ] {
            assert_eq!(extension(name), None, "{name}");
        }
    }
}
