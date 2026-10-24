//! Files the person picks in a native dialog, for a declaration's imports,
//! review packages and exports. The window learns each one only as an opaque
//! token and its file name; the host keeps the path, and substitutes it when
//! a submission names the token in a field that reads or writes a file. A
//! token belongs to the signed-in session that issued it, to the purpose it
//! was picked for, and to whether the file is read or written.
use super::super::relay::{Failure, Result, lock};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

const TOKEN_PREFIX: &str = "file-";
/// How many tokens the window may hold; the oldest is forgotten first.
const TOKEN_LIMIT: usize = 4096;
/// How many files one dialog may name.
const PICK_LIMIT: usize = 100;

/// What the person is choosing a file for, and so which kinds a dialog offers.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Purpose {
    /// An AEAT justificante, register or declaration file, or a receipt.
    Evidence,
    /// A calculation report whose signature is checked.
    Report,
    /// A review package.
    Package,
    /// A review package's signature.
    Signature,
    /// A sealed review envelope.
    Envelope,
    /// Where an export is written.
    Export,
}
impl Purpose {
    pub(super) fn extensions(self) -> &'static [&'static str] {
        match self {
            Self::Evidence => &["pdf", "csv", "txt", "xml", "boe"],
            Self::Report => &["pdf", "csv", "xlsx"],
            Self::Package => &["zip"],
            Self::Signature => &["sig"],
            Self::Envelope => &["sealed"],
            Self::Export => Format::EXTENSIONS,
        }
    }
    fn takes(self, path: &Path) -> bool {
        extension(path).is_some_and(|found| self.extensions().contains(&found.as_str()))
    }
}

/// The kind of file an export is written as, which the save dialog offers.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Format {
    /// The fichero BOE: a filing laid out by its fixed-width design.
    Boe,
    Xml,
    Csv,
    Pdf,
    Xlsx,
    Zip,
    Sig,
    Sealed,
}
impl Format {
    const EXTENSIONS: &'static [&'static str] =
        &["boe", "xml", "csv", "pdf", "xlsx", "zip", "sig", "sealed"];
    pub(super) fn extension(self) -> &'static str {
        match self {
            Self::Boe => "boe",
            Self::Xml => "xml",
            Self::Csv => "csv",
            Self::Pdf => "pdf",
            Self::Xlsx => "xlsx",
            Self::Zip => "zip",
            Self::Sig => "sig",
            Self::Sealed => "sealed",
        }
    }
}

/// One picked file as the window sees it.
#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Picked {
    token: String,
    name: String,
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
}

pub(super) fn extension(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|extension| extension.to_str())
        .map(str::to_ascii_lowercase)
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
    pub(super) fn issue_all(
        &self,
        identity: &Value,
        purpose: Purpose,
        paths: Vec<PathBuf>,
    ) -> Result<Picks> {
        let mut picks = Picks::default();
        for path in paths {
            if purpose != Purpose::Export
                && purpose.takes(&path)
                && path.is_absolute()
                && path.is_file()
                && picks.files.len() < PICK_LIMIT
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

    /// A token for where an export is to be written. The person chose the
    /// name in the save dialog, which asked before replacing a file; a name
    /// whose kind is not `format` is refused rather than renamed.
    pub(super) fn issue_save(
        &self,
        identity: &Value,
        format: Format,
        path: PathBuf,
    ) -> Result<Picks> {
        if !path.is_absolute() || extension(&path).as_deref() != Some(format.extension()) {
            return Ok(Picks::none(1));
        }
        Ok(Picks {
            files: vec![self.issue(identity, Purpose::Export, path, true)?],
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
    use serde_json::json;

    fn scratch(name: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "cadrumo-modelo-files-{name}-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("inner")).unwrap();
        for file in ["justificante.PDF", "review.zip", "notes.docx"] {
            std::fs::write(root.join(file), b"x").unwrap();
        }
        root
    }

    #[test]
    fn a_pick_names_files_of_the_purposes_kinds_and_never_a_folder() {
        let root = scratch("pick");
        let files = Files::default();
        let session = json!({"session_id":"one"});
        let picks = files
            .issue_all(
                &session,
                Purpose::Evidence,
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
        assert_eq!(picks.refused, 3);
        let shown = serde_json::to_value(&picks).unwrap().to_string();
        assert!(
            !shown.contains(&*root.to_string_lossy()),
            "no path reaches the window"
        );
        assert_eq!(
            files
                .path(&session, &picks.files[0].token, Purpose::Evidence, false)
                .unwrap(),
            root.join("justificante.PDF")
        );
        let package = files
            .issue_all(&session, Purpose::Package, vec![root.join("review.zip")])
            .unwrap();
        assert_eq!(package.files.len(), 1);
        assert_eq!(
            files
                .issue_all(&session, Purpose::Export, vec![root.join("review.zip")])
                .unwrap()
                .refused,
            1,
            "a file to write is chosen in the save dialog only"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn a_token_serves_only_its_session_purpose_and_use() {
        let root = scratch("token");
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let token = files
            .issue_all(&one, Purpose::Package, vec![root.join("review.zip")])
            .unwrap()
            .files[0]
            .token
            .clone();
        assert!(files.path(&one, &token, Purpose::Package, false).is_ok());
        for (purpose, saving) in [(Purpose::Evidence, false), (Purpose::Package, true)] {
            assert_eq!(
                files.path(&one, &token, purpose, saving).unwrap_err().code,
                "invalid"
            );
        }
        assert_eq!(
            files
                .path(&one, r"C:\review.zip", Purpose::Package, false)
                .unwrap_err()
                .code,
            "invalid",
            "a path is never a token"
        );
        let two = json!({"session_id":"two"});
        assert_eq!(
            files
                .path(&two, &token, Purpose::Package, false)
                .unwrap_err()
                .code,
            "file_unavailable"
        );
        assert_eq!(
            files
                .path(&one, &token, Purpose::Package, false)
                .unwrap_err()
                .code,
            "file_unavailable",
            "a later session's use forgets the earlier session's tokens"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn an_export_is_written_only_where_its_format_was_chosen() {
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let target = std::env::temp_dir().join("modelo-303-2026-3T.boe");
        let saved = files.issue_save(&one, Format::Boe, target.clone()).unwrap();
        assert_eq!((saved.files.len(), saved.refused), (1, 0));
        assert_eq!(saved.files[0].bytes, None);
        assert_eq!(
            files
                .path(&one, &saved.files[0].token, Purpose::Export, true)
                .unwrap(),
            target
        );
        for (format, path) in [
            (Format::Xml, target.clone()),
            (Format::Boe, std::env::temp_dir().join("modelo")),
            (Format::Boe, std::env::temp_dir().join("modelo-303.txt")),
            (Format::Boe, PathBuf::from("modelo.boe")),
        ] {
            let refused = files.issue_save(&one, format, path).unwrap();
            assert_eq!((refused.files.len(), refused.refused), (0, 1));
        }
        files.forget(&[saved.files[0].token.clone()]);
        assert!(
            files
                .path(&one, &saved.files[0].token, Purpose::Export, true)
                .is_err()
        );
    }
}
