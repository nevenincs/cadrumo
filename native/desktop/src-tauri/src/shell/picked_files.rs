//! Files the person picks in a native dialog or drops on the window, and the
//! places they save to. The window learns each one only as an opaque token
//! and its file name; the host keeps the path, and substitutes it when a
//! submission names the token in a field that reads or writes a file. A
//! token belongs to the signed-in session that issued it, to the purpose it
//! was picked for, and to whether the file is read or written.
use super::relay::{Failure, Result, lock};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

const TOKEN_PREFIX: &str = "file-";
/// How many tokens the window may hold; the oldest is forgotten first.
const TOKEN_LIMIT: usize = 4096;
/// How many files one folder or one drop may name.
const FOLDER_LIMIT: usize = 1000;
/// The longest filter name or suggested file name the window may word.
const LABEL_LIMIT: usize = 128;

/// What the person is choosing files for, and so which kinds a dialog offers.
/// The `Modelo` purposes belong to the declarations workspace, whose door
/// names them in its own words: no other door can be asked for one, and a
/// token of one kind never serves a field of another.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Purpose {
    BankStatements,
    InvoiceBooks,
    Documents,
    /// Where a ledger export is written.
    Export,
    /// The electronic certificate the person signs in to AEAT with.
    Certificate,
    /// A Borrador 100 PDF downloaded from AEAT.
    #[serde(skip_deserializing)]
    Borrador,
    /// An AEAT justificante, register or declaration file, or a receipt.
    #[serde(skip_deserializing)]
    ModeloEvidence,
    /// A calculation report whose signature is checked.
    #[serde(skip_deserializing)]
    ModeloReport,
    /// A review package.
    #[serde(skip_deserializing)]
    ModeloPackage,
    /// A review package's signature.
    #[serde(skip_deserializing)]
    ModeloSignature,
    /// A sealed review envelope.
    #[serde(skip_deserializing)]
    ModeloEnvelope,
    /// Where a declaration's export, review package, signature or envelope is
    /// written.
    #[serde(skip_deserializing)]
    ModeloExport,
}
impl Purpose {
    /// The kinds an open dialog offers and a drop takes: none for a purpose
    /// that is only written.
    pub(super) fn extensions(self) -> &'static [&'static str] {
        match self {
            Self::BankStatements => &["csv", "txt", "tsv", "xlsx", "xls", "ofx", "qfx", "pdf"],
            Self::InvoiceBooks => &["csv", "tsv", "xlsx", "xlsm", "xls"],
            Self::Documents => &[
                "pdf", "xml", "png", "jpg", "jpeg", "tif", "tiff", "webp", "heic", "heif",
            ],
            Self::Certificate => &["p12", "pfx"],
            Self::Borrador => &["pdf"],
            Self::ModeloEvidence => &["pdf", "csv", "txt", "xml", "boe"],
            Self::ModeloReport => &["pdf", "csv", "xlsx"],
            Self::ModeloPackage => &["zip"],
            Self::ModeloSignature => &["sig"],
            Self::ModeloEnvelope => &["sealed"],
            Self::Export | Self::ModeloExport => &[],
        }
    }
    fn takes(self, path: &Path) -> bool {
        extension(path).is_some_and(|found| self.extensions().contains(&found.as_str()))
    }
    /// Whether the purpose names where a file is to be written, which only the
    /// save dialog chooses.
    fn written(self) -> bool {
        self.extensions().is_empty()
    }
    /// Whether a folder stands for the files of the purpose's kinds directly in
    /// it. Only the ledger's imports read whole folders; every other purpose
    /// names the one file picked.
    fn reads_folders(self) -> bool {
        matches!(
            self,
            Self::BankStatements | Self::InvoiceBooks | Self::Documents
        )
    }
}

/// How many files an open dialog picks.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Pick {
    File,
    Files,
    /// Every file of the purpose's kinds directly in one folder.
    Folder,
}

/// One picked file as the window sees it.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Picked {
    pub(super) token: String,
    pub(super) name: String,
    bytes: Option<u64>,
}
/// What a dialog or a drop gave the window: the files it took, and how many
/// it did not because they are not of the purpose's kinds.
#[derive(Debug, Default, PartialEq, Serialize)]
pub struct Picks {
    files: Vec<Picked>,
    refused: usize,
}
impl Picks {
    /// Nothing taken: every one of `refused` files is refused.
    pub(super) fn none(refused: usize) -> Self {
        Self {
            files: vec![],
            refused,
        }
    }

    /// The one file a single pick took: none where the dialog was closed
    /// without a pick, and invalid where the pick was not of the purpose's
    /// kinds.
    pub(super) fn single(self) -> Result<Option<Picked>> {
        match (self.files.into_iter().next(), self.refused) {
            (picked, 0) => Ok(picked),
            _ => Err(Failure::new("invalid")),
        }
    }
}

pub(super) fn extension(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|extension| extension.to_str())
        .map(str::to_ascii_lowercase)
}

/// A path as the JSON text a request carries, or `file_unavailable` where it
/// has none.
pub(super) fn path_text(path: &Path) -> Result<Value> {
    path.to_str()
        .map(|text| json!(text))
        .ok_or_else(|| Failure::new("file_unavailable"))
}

/// Opens the native dialog over `window` for what `pick` names, of the kinds
/// `purpose` reads, and answers the paths chosen. A dialog closed without a
/// pick picks nothing.
pub(super) async fn choose<R: tauri::Runtime>(
    window: tauri::WebviewWindow<R>,
    pick: Pick,
    purpose: Purpose,
    filter_label: String,
) -> Result<Vec<PathBuf>> {
    use tauri_plugin_dialog::DialogExt;
    Ok(super::blocking(move || {
        let dialog = window.dialog().file().set_parent(&window);
        let chosen: Vec<_> = match pick {
            Pick::File => dialog
                .add_filter(filter_label, purpose.extensions())
                .blocking_pick_file()
                .into_iter()
                .collect(),
            Pick::Files => dialog
                .add_filter(filter_label, purpose.extensions())
                .blocking_pick_files()
                .unwrap_or_default(),
            Pick::Folder => dialog.blocking_pick_folder().into_iter().collect(),
        };
        Ok(chosen
            .into_iter()
            .filter_map(|picked| picked.into_path().ok())
            .collect())
    })
    .await?)
}

/// Opens the native save dialog over `window` for a file of `extension` and
/// answers the path chosen. The dialog asks before replacing a file, and a
/// dialog closed without a choice chooses nothing.
pub(super) async fn choose_save<R: tauri::Runtime>(
    window: tauri::WebviewWindow<R>,
    extension: &'static str,
    filter_label: String,
    suggested_name: Option<String>,
) -> Result<Option<PathBuf>> {
    use tauri_plugin_dialog::DialogExt;
    Ok(super::blocking(move || {
        let mut dialog = window
            .dialog()
            .file()
            .set_parent(&window)
            .add_filter(filter_label, &[extension]);
        if let Some(name) = suggested_name {
            dialog = dialog.set_file_name(name);
        }
        Ok(dialog
            .blocking_save_file()
            .and_then(|picked| picked.into_path().ok()))
    })
    .await?)
}

/// Words the window shows in a native dialog: a filter's name or a file name.
pub(super) fn label_admitted(label: &str) -> bool {
    !label.is_empty()
        && label.chars().count() <= LABEL_LIMIT
        && !label.chars().any(char::is_control)
}
pub(super) fn file_name_admitted(name: &str) -> bool {
    label_admitted(name) && !name.contains(['/', '\\', ':']) && !name.starts_with('.')
}

struct Entry {
    token: String,
    path: PathBuf,
    purpose: Purpose,
    saving: bool,
    identity: Value,
}

/// The paths behind the window's tokens, for one signed-in session.
#[derive(Default)]
pub(super) struct Files(Mutex<Vec<Entry>>);
impl Files {
    fn issue(
        &self,
        identity: &Value,
        purpose: Purpose,
        path: PathBuf,
        saving: bool,
    ) -> Result<Picked> {
        let mut bytes = [0u8; 16];
        getrandom::fill(&mut bytes).map_err(|_| Failure::new("unavailable"))?;
        let token =
            TOKEN_PREFIX.to_owned() + &bytes.iter().map(|b| format!("{b:02x}")).collect::<String>();
        let name = path
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_default();
        let size = if saving {
            None
        } else {
            std::fs::metadata(&path).ok().map(|meta| meta.len())
        };
        let mut entries = lock(&self.0);
        entries.retain(|entry| entry.identity == *identity);
        if entries.len() >= TOKEN_LIMIT {
            entries.remove(0);
        }
        entries.push(Entry {
            token: token.clone(),
            path,
            purpose,
            saving,
            identity: identity.clone(),
        });
        Ok(Picked {
            token,
            name,
            bytes: size,
        })
    }

    /// Tokens for every file of the purpose's kinds; the rest are counted.
    /// Where the purpose reads folders, a folder names its own files, not
    /// those of folders within it; elsewhere it is not a file and is refused.
    /// A purpose that is only written takes nothing: its file is chosen in the
    /// save dialog.
    pub(super) fn issue_all(
        &self,
        identity: &Value,
        purpose: Purpose,
        paths: Vec<PathBuf>,
    ) -> Result<Picks> {
        let mut picks = Picks::default();
        let mut files = Vec::new();
        for path in paths {
            if purpose.reads_folders() && path.is_dir() {
                let mut inside: Vec<PathBuf> = std::fs::read_dir(&path)
                    .map(|entries| {
                        entries
                            .filter_map(|entry| entry.ok().map(|entry| entry.path()))
                            .filter(|path| path.is_file())
                            .collect()
                    })
                    .unwrap_or_default();
                inside.sort();
                files.extend(inside);
            } else {
                files.push(path);
            }
        }
        for path in files {
            if purpose.takes(&path)
                && path.is_absolute()
                && path.is_file()
                && picks.files.len() < FOLDER_LIMIT
            {
                picks
                    .files
                    .push(self.issue(identity, purpose, path, false)?);
            } else {
                picks.refused += 1;
            }
        }
        Ok(picks)
    }

    /// A token for where an export of `purpose` is to be written. The person
    /// chose the name in the save dialog, which asked before replacing a file;
    /// a name whose kind is not `format` is refused rather than renamed, and
    /// so is a purpose that is read.
    pub(super) fn issue_save(
        &self,
        identity: &Value,
        purpose: Purpose,
        format: &str,
        path: PathBuf,
    ) -> Result<Picks> {
        if !purpose.written() || !path.is_absolute() || extension(&path).as_deref() != Some(format)
        {
            return Ok(Picks::none(1));
        }
        Ok(Picks {
            files: vec![self.issue(identity, purpose, path, true)?],
            refused: 0,
        })
    }

    /// The path behind `token`, for this session, purpose and use only.
    pub(super) fn path(
        &self,
        identity: &Value,
        token: &str,
        purpose: Purpose,
        saving: bool,
    ) -> Result<PathBuf> {
        if !token.starts_with(TOKEN_PREFIX) {
            return Err(Failure::new("invalid"));
        }
        let mut entries = lock(&self.0);
        // A token from an earlier session names nothing in this one.
        entries.retain(|entry| entry.identity == *identity);
        let entry = entries
            .iter()
            .find(|entry| entry.token == token)
            .ok_or_else(|| Failure::new("file_unavailable"))?;
        if entry.purpose != purpose || entry.saving != saving {
            return Err(Failure::new("invalid"));
        }
        Ok(entry.path.clone())
    }

    /// The file an export's save token names, once the host has written it:
    /// for this session and `purpose` only, never a file the person picked to
    /// read, and only while it is still there.
    pub(super) fn saved(&self, identity: &Value, token: &str, purpose: Purpose) -> Result<PathBuf> {
        let path = self.path(identity, token, purpose, true)?;
        if !path.is_file() {
            return Err(Failure::new("file_unavailable"));
        }
        Ok(path)
    }

    pub(super) fn forget(&self, tokens: &[String]) {
        lock(&self.0).retain(|entry| !tokens.contains(&entry.token));
    }

    pub(super) fn clear(&self) {
        lock(&self.0).clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "cadrumo-picked-files-{name}-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("inner")).unwrap();
        for file in ["b.csv", "a.OFX", "notes.docx", "inner/c.csv"] {
            std::fs::write(root.join(file), b"x").unwrap();
        }
        root
    }

    #[test]
    fn a_folder_names_its_own_files_of_the_purposes_kinds_only() {
        let root = scratch("folder");
        let files = Files::default();
        let session = json!({"session_id":"one"});
        let picks = files
            .issue_all(&session, Purpose::BankStatements, vec![root.clone()])
            .unwrap();
        let names: Vec<&str> = picks.files.iter().map(|p| p.name.as_str()).collect();
        assert_eq!(names, ["a.OFX", "b.csv"]);
        assert_eq!(picks.refused, 1, "the document is not a statement");
        assert!(picks.files.iter().all(|p| p.bytes == Some(1)));
        let shown = serde_json::to_value(&picks).unwrap().to_string();
        assert!(
            !shown.contains(&*root.to_string_lossy()),
            "no path reaches the window"
        );
        let token = &picks.files[1].token;
        assert_eq!(
            files
                .path(&session, token, Purpose::BankStatements, false)
                .unwrap(),
            root.join("b.csv")
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_token_serves_only_its_session_purpose_and_use() {
        let root = scratch("token");
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let picked = files
            .issue_all(&one, Purpose::Documents, vec![root.join("b.csv")])
            .unwrap();
        assert_eq!(picked.files.len(), 0, "a statement is not a document");
        let picked = files
            .issue_all(&one, Purpose::InvoiceBooks, vec![root.join("b.csv")])
            .unwrap();
        let token = picked.files[0].token.clone();
        assert!(
            files
                .path(&one, &token, Purpose::InvoiceBooks, false)
                .is_ok()
        );
        assert_eq!(
            files
                .path(&one, &token, Purpose::BankStatements, false)
                .unwrap_err()
                .code,
            "invalid"
        );
        assert_eq!(
            files
                .path(&one, &token, Purpose::InvoiceBooks, true)
                .unwrap_err()
                .code,
            "invalid"
        );
        assert_eq!(
            files
                .path(&one, "C:\\statement.csv", Purpose::InvoiceBooks, false)
                .unwrap_err()
                .code,
            "invalid",
            "a path is never a token"
        );
        let two = json!({"session_id":"two"});
        assert_eq!(
            files
                .path(&two, &token, Purpose::InvoiceBooks, false)
                .unwrap_err()
                .code,
            "file_unavailable"
        );
        assert_eq!(
            files
                .path(&one, &token, Purpose::InvoiceBooks, false)
                .unwrap_err()
                .code,
            "file_unavailable",
            "a later session's use forgets the earlier session's tokens"
        );
        let again = files
            .issue_all(&one, Purpose::InvoiceBooks, vec![root.join("b.csv")])
            .unwrap();
        files.forget(&[again.files[0].token.clone()]);
        assert!(
            files
                .path(&one, &again.files[0].token, Purpose::InvoiceBooks, false)
                .is_err()
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_certificate_token_and_a_ledger_token_never_serve_each_other() {
        let root = scratch("certificate");
        for file in ["identity.PFX", "receipt.pdf"] {
            std::fs::write(root.join(file), b"x").unwrap();
        }
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let issue = |purpose: Purpose, file: &str| {
            files
                .issue_all(&one, purpose, vec![root.join(file)])
                .unwrap()
                .single()
                .unwrap()
                .unwrap()
        };
        let certificate = issue(Purpose::Certificate, "identity.PFX");
        assert_eq!(certificate.name, "identity.PFX");
        assert_eq!(
            files
                .path(&one, &certificate.token, Purpose::Certificate, false)
                .unwrap(),
            root.join("identity.PFX")
        );
        for (purpose, file) in [
            (Purpose::BankStatements, "b.csv"),
            (Purpose::InvoiceBooks, "b.csv"),
            (Purpose::Documents, "receipt.pdf"),
        ] {
            let ledger = issue(purpose, file);
            assert_eq!(
                files
                    .path(&one, &ledger.token, Purpose::Certificate, false)
                    .unwrap_err()
                    .code,
                "invalid",
                "a {purpose:?} token is not a certificate"
            );
            assert_eq!(
                files
                    .path(&one, &certificate.token, purpose, false)
                    .unwrap_err()
                    .code,
                "invalid",
                "a certificate token is not a {purpose:?} file"
            );
        }
        for refused in ["b.csv", "receipt.pdf", "notes.docx"] {
            let picks = files
                .issue_all(&one, Purpose::Certificate, vec![root.join(refused)])
                .unwrap();
            assert_eq!(picks.refused, 1, "{refused}");
            assert_eq!(picks.single().unwrap_err().code, "invalid", "{refused}");
        }
        let closed = files.issue_all(&one, Purpose::Certificate, vec![]).unwrap();
        assert!(
            closed.single().unwrap().is_none(),
            "a dialog closed without a pick picks nothing"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_declarations_pick_names_files_of_the_purposes_kinds_and_never_a_folder() {
        let root = scratch("declaration");
        for file in ["justificante.PDF", "review.zip"] {
            std::fs::write(root.join(file), b"x").unwrap();
        }
        std::fs::create_dir_all(root.join("bundle.zip")).unwrap();
        let files = Files::default();
        let session = json!({"session_id":"one"});
        let picks = files
            .issue_all(
                &session,
                Purpose::ModeloEvidence,
                vec![
                    root.join("justificante.PDF"),
                    root.join("review.zip"),
                    root.join("notes.docx"),
                    root.join("inner"),
                ],
            )
            .unwrap();
        let names: Vec<&str> = picks.files.iter().map(|p| p.name.as_str()).collect();
        assert_eq!(names, ["justificante.PDF"]);
        assert_eq!(picks.refused, 3, "a folder does not name the files in it");
        let shown = serde_json::to_value(&picks).unwrap().to_string();
        assert!(
            !shown.contains(&*root.to_string_lossy()),
            "no path reaches the window"
        );
        assert_eq!(
            files
                .path(
                    &session,
                    &picks.files[0].token,
                    Purpose::ModeloEvidence,
                    false
                )
                .unwrap(),
            root.join("justificante.PDF")
        );
        let package = files
            .issue_all(
                &session,
                Purpose::ModeloPackage,
                vec![root.join("review.zip")],
            )
            .unwrap();
        assert_eq!(package.files.len(), 1);
        let folder = files
            .issue_all(
                &session,
                Purpose::ModeloPackage,
                vec![root.join("bundle.zip")],
            )
            .unwrap();
        assert_eq!(
            (folder.files.len(), folder.refused),
            (0, 1),
            "a folder is not a file for its name's kind"
        );
        for (purpose, file) in [
            (Purpose::ModeloExport, "review.zip"),
            (Purpose::Export, "b.csv"),
        ] {
            let picks = files
                .issue_all(&session, purpose, vec![root.join(file)])
                .unwrap();
            assert_eq!(
                (picks.files.len(), picks.refused),
                (0, 1),
                "a file to write is chosen in the save dialog only"
            );
        }
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_token_serves_only_the_purpose_and_use_it_was_issued_for() {
        let root = scratch("purposes");
        let reads = [
            (Purpose::BankStatements, "b.csv"),
            (Purpose::InvoiceBooks, "b.csv"),
            (Purpose::Documents, "receipt.pdf"),
            (Purpose::Certificate, "identity.pfx"),
            (Purpose::ModeloEvidence, "receipt.pdf"),
            (Purpose::ModeloReport, "report.xlsx"),
            (Purpose::ModeloPackage, "review.zip"),
            (Purpose::ModeloSignature, "review.sig"),
            (Purpose::ModeloEnvelope, "review.sealed"),
        ];
        let writes = [
            (Purpose::Export, "csv", "ledger.csv"),
            (Purpose::ModeloExport, "boe", "modelo-303-2026-3T.boe"),
        ];
        for (_, file) in reads {
            std::fs::write(root.join(file), b"x").unwrap();
        }
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let mut held = Vec::new();
        for (purpose, file) in reads {
            let picked = files
                .issue_all(&one, purpose, vec![root.join(file)])
                .unwrap()
                .single()
                .unwrap()
                .unwrap();
            held.push((purpose, false, picked.token));
        }
        for (purpose, format, name) in writes {
            let picked = files
                .issue_save(&one, purpose, format, root.join(name))
                .unwrap()
                .single()
                .unwrap()
                .unwrap();
            held.push((purpose, true, picked.token));
        }
        for (issued, writing, token) in &held {
            for (asked, using, _) in &held {
                let found = files.path(&one, token, *asked, *using);
                if (issued, writing) == (asked, using) {
                    assert!(found.is_ok(), "a {issued:?} token serves its own purpose");
                } else {
                    assert_eq!(
                        found.unwrap_err().code,
                        "invalid",
                        "a {issued:?} token is not a {asked:?} one"
                    );
                }
            }
            for (asked, ..) in held.iter().filter(|(_, writing, _)| *writing) {
                if (issued, writing) != (asked, &true) {
                    assert_eq!(
                        files.saved(&one, token, *asked).unwrap_err().code,
                        "invalid",
                        "a {issued:?} token is not a saved {asked:?} file"
                    );
                }
            }
        }
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn no_door_can_be_asked_for_a_declarations_purpose() {
        for ledger in [
            "bank_statements",
            "invoice_books",
            "documents",
            "export",
            "certificate",
        ] {
            assert!(
                serde_json::from_value::<Purpose>(json!(ledger)).is_ok(),
                "{ledger}"
            );
        }
        for declaration in [
            Purpose::ModeloEvidence,
            Purpose::ModeloReport,
            Purpose::ModeloPackage,
            Purpose::ModeloSignature,
            Purpose::ModeloEnvelope,
            Purpose::ModeloExport,
        ] {
            let named = serde_json::to_value(declaration).unwrap();
            assert!(
                serde_json::from_value::<Purpose>(named.clone()).is_err(),
                "{named}"
            );
        }
    }

    #[test]
    fn an_export_is_written_only_where_its_format_was_chosen() {
        let files = Files::default();
        let one = json!({"session_id":"one"});
        for (purpose, format, other, name) in [
            (Purpose::Export, "csv", "xlsx", "ledger.csv"),
            (
                Purpose::ModeloExport,
                "boe",
                "xml",
                "modelo-303-2026-3T.boe",
            ),
        ] {
            let target = std::env::temp_dir().join(name);
            let saved = files
                .issue_save(&one, purpose, format, target.clone())
                .unwrap();
            assert_eq!((saved.files.len(), saved.refused), (1, 0));
            assert_eq!(saved.files[0].bytes, None);
            assert_eq!(
                files
                    .path(&one, &saved.files[0].token, purpose, true)
                    .unwrap(),
                target
            );
            for (kind, path) in [
                (other, target.clone()),
                (format, std::env::temp_dir().join("export")),
                (format, std::env::temp_dir().join("export.txt")),
                (format, PathBuf::from(name)),
            ] {
                let refused = files.issue_save(&one, purpose, kind, path).unwrap();
                assert_eq!(
                    (refused.files.len(), refused.refused),
                    (0, 1),
                    "{purpose:?}"
                );
            }
            files.forget(&[saved.files[0].token.clone()]);
            assert!(
                files
                    .path(&one, &saved.files[0].token, purpose, true)
                    .is_err()
            );
        }
        let read = files
            .issue_save(
                &one,
                Purpose::BankStatements,
                "csv",
                std::env::temp_dir().join("b.csv"),
            )
            .unwrap();
        assert_eq!(
            (read.files.len(), read.refused),
            (0, 1),
            "a purpose that is read is never written"
        );
    }

    #[test]
    fn only_a_saved_file_that_is_still_there_is_shown() {
        let root = scratch("saved");
        std::fs::write(root.join("receipt.pdf"), b"x").unwrap();
        let files = Files::default();
        let one = json!({"session_id":"one"});
        for (purpose, format, other, name) in [
            (Purpose::Export, "csv", Purpose::ModeloExport, "ledger.csv"),
            (
                Purpose::ModeloExport,
                "boe",
                Purpose::Export,
                "modelo-303-2026-3T.boe",
            ),
        ] {
            let target = root.join(name);
            let token = files
                .issue_save(&one, purpose, format, target.clone())
                .unwrap()
                .files[0]
                .token
                .clone();
            assert_eq!(
                files.saved(&one, &token, purpose).unwrap_err().code,
                "file_unavailable",
                "nothing was written there yet"
            );
            std::fs::write(&target, b"x").unwrap();
            assert_eq!(files.saved(&one, &token, purpose).unwrap(), target);
            assert_eq!(
                files.saved(&one, &token, other).unwrap_err().code,
                "invalid",
                "another workspace's export is not shown through this one"
            );
            let picked = files
                .issue_all(&one, Purpose::Documents, vec![root.join("receipt.pdf")])
                .unwrap()
                .files[0]
                .token
                .clone();
            assert_eq!(
                files.saved(&one, &picked, purpose).unwrap_err().code,
                "invalid",
                "a file picked to read is not one the host saved"
            );
            assert_eq!(
                files
                    .saved(&one, &target.to_string_lossy(), purpose)
                    .unwrap_err()
                    .code,
                "invalid",
                "a path is never a token"
            );
            assert_eq!(
                files
                    .saved(&one, "file-00000000000000000000000000000000", purpose)
                    .unwrap_err()
                    .code,
                "file_unavailable"
            );
            std::fs::remove_file(&target).unwrap();
            assert_eq!(
                files.saved(&one, &token, purpose).unwrap_err().code,
                "file_unavailable",
                "a file removed since it was saved"
            );
            std::fs::write(&target, b"x").unwrap();
            files.forget(std::slice::from_ref(&token));
            assert_eq!(
                files.saved(&one, &token, purpose).unwrap_err().code,
                "file_unavailable"
            );
            let token = files
                .issue_save(&one, purpose, format, target.clone())
                .unwrap()
                .files[0]
                .token
                .clone();
            assert_eq!(
                files
                    .saved(&json!({"session_id":"two"}), &token, purpose)
                    .unwrap_err()
                    .code,
                "file_unavailable",
                "another session's save names nothing"
            );
        }
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn dialog_words_are_bounded_and_a_suggested_name_names_no_folder() {
        let longest = "a".repeat(LABEL_LIMIT);
        let too_long = "a".repeat(LABEL_LIMIT + 1);
        for label in ["Extractos bancarios", "Fichero BOE", longest.as_str()] {
            assert!(label_admitted(label), "{label}");
        }
        for label in ["", "line\nbreak", too_long.as_str()] {
            assert!(!label_admitted(label), "{label:?}");
        }
        for name in ["libro-2026.csv", "modelo-303-2026-3T.txt"] {
            assert!(file_name_admitted(name), "{name}");
        }
        for refused in ["..\\up.csv", "C:\\x.csv", "C:x.txt", "a/b.csv", ".hidden"] {
            assert!(!file_name_admitted(refused), "{refused}");
        }
    }
}
