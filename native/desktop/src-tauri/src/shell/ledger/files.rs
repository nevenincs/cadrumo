//! Files the person picks in a native dialog or drops on the window. The
//! window learns each one only as an opaque token and its file name; the
//! host keeps the path, and substitutes it when a submission names the
//! token in a field that reads a file. A token belongs to the signed-in
//! session that issued it and to the purpose it was picked for.
use super::super::relay::{Failure, Result, lock};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

const TOKEN_PREFIX: &str = "file-";
/// How many tokens the window may hold; the oldest is forgotten first.
const TOKEN_LIMIT: usize = 4096;
/// How many files one folder or one drop may name.
const FOLDER_LIMIT: usize = 1000;

/// What the person is choosing files for, and so which kinds a dialog offers.
#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Purpose {
    BankStatements,
    InvoiceBooks,
    Documents,
    Export,
}
impl Purpose {
    pub(super) fn extensions(self) -> &'static [&'static str] {
        match self {
            Self::BankStatements => &["csv", "txt", "tsv", "xlsx", "xls", "ofx", "qfx", "pdf"],
            Self::InvoiceBooks => &["csv", "tsv", "xlsx", "xlsm", "xls"],
            Self::Documents => &[
                "pdf", "xml", "png", "jpg", "jpeg", "tif", "tiff", "webp", "heic", "heif",
            ],
            Self::Export => &["csv", "jsonl", "xlsx"],
        }
    }
    fn takes(self, path: &Path) -> bool {
        extension(path).is_some_and(|found| self.extensions().contains(&found.as_str()))
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

    /// Tokens for every path of the purpose's kinds; the rest are counted.
    /// A folder names its own files, not those of folders within it.
    pub(super) fn issue_all(
        &self,
        identity: &Value,
        purpose: Purpose,
        paths: Vec<PathBuf>,
    ) -> Result<Picks> {
        let mut picks = Picks::default();
        let mut files = Vec::new();
        for path in paths {
            if path.is_dir() {
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
            if purpose.takes(&path) && path.is_absolute() && picks.files.len() < FOLDER_LIMIT {
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
        format: &str,
        path: PathBuf,
    ) -> Result<Picks> {
        if !path.is_absolute() || extension(&path).as_deref() != Some(format) {
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
            "cadrumo-ledger-files-{name}-{}",
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
    fn an_export_is_written_only_where_its_format_was_chosen() {
        let files = Files::default();
        let one = json!({"session_id":"one"});
        let target = std::env::temp_dir().join("ledger.csv");
        let saved = files.issue_save(&one, "csv", target.clone()).unwrap();
        assert_eq!(saved.refused, 0);
        assert_eq!(saved.files[0].bytes, None);
        assert_eq!(
            files
                .path(&one, &saved.files[0].token, Purpose::Export, true)
                .unwrap(),
            target
        );
        for (format, path) in [
            ("xlsx", target.clone()),
            ("csv", std::env::temp_dir().join("ledger")),
            ("csv", PathBuf::from("ledger.csv")),
        ] {
            let refused = files.issue_save(&one, format, path).unwrap();
            assert_eq!((refused.files.len(), refused.refused), (0, 1));
        }
    }
}
