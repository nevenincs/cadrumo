//! Files the person attaches to a conversation: picked in the host's own
//! dialog, checked against what the agent's storage takes, and streamed into
//! the conversation's own storage with the digest it is checked against.
//!
//! The page learns each file's name, size and where its upload is; never its
//! path, never its bytes. Nothing about a file is logged.

use super::{
    Refused,
    gateway::Client,
    session::{document_record, plain_name},
    supervisor::Gateway,
};
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs::File,
    io::{self, Read},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};
use tauri::ipc::Channel;

/// How far an upload goes between two reports of its progress, at most.
const REPORT_EVERY: u64 = 512 * 1024;
/// The most files one pick stages.
const PICK_LIMIT: usize = 200;

/// What a conversation's storage takes: `GET /v1/attachments/policy`.
#[derive(Debug, PartialEq, Eq)]
pub struct Policy {
    pub max_file_bytes: u64,
    /// The extensions it takes, lowercase and without their dot.
    pub extensions: Vec<String>,
}

/// The policy as the agent serves it, or unreadable.
pub fn policy_of(value: &Value) -> Result<Policy, Refused> {
    let unreadable = || Refused::new("agent_gateway_unreadable".to_owned());
    let max_file_bytes = value
        .get("max_file_bytes")
        .and_then(Value::as_u64)
        .filter(|bytes| *bytes > 0)
        .ok_or_else(unreadable)?;
    let mut extensions = Vec::new();
    for format in value
        .get("formats")
        .and_then(Value::as_array)
        .ok_or_else(unreadable)?
    {
        for extension in format
            .get("extensions")
            .and_then(Value::as_array)
            .ok_or_else(unreadable)?
        {
            let extension = extension
                .as_str()
                .map(|e| e.trim_start_matches('.').to_ascii_lowercase())
                .filter(|e| {
                    !e.is_empty() && e.len() <= 16 && e.bytes().all(|b| b.is_ascii_alphanumeric())
                })
                .ok_or_else(unreadable)?;
            if !extensions.contains(&extension) {
                extensions.push(extension);
            }
        }
    }
    if extensions.is_empty() {
        return Err(unreadable());
    }
    Ok(Policy {
        max_file_bytes,
        extensions,
    })
}

/// A file a pick staged, as the page is told of it: refused already, or
/// queued for upload.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Picked {
    pub id: String,
    pub name: String,
    pub size_bytes: u64,
    pub state: &'static str,
    pub code: Option<String>,
}

/// Where an upload is, as the page follows it.
#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum UploadEvent {
    Progress {
        id: String,
        sent: u64,
    },
    /// Stored: the record the agent keeps of it, which a message can name.
    Stored {
        id: String,
        document: Value,
    },
    Refused {
        id: String,
        code: String,
    },
}

/// One file the policy admits, still to be sent.
pub struct Queued {
    id: String,
    name: String,
    size: u64,
    path: PathBuf,
}

/// A file's name and size where the policy takes it, else why not.
pub fn admit(path: &Path, policy: &Policy) -> Result<(String, u64), &'static str> {
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        // The storage takes no name that starts with a dot.
        .filter(|name| plain_name(name) && !name.starts_with('.'))
        .ok_or("agent_attachment_name_refused")?;
    let extension = Path::new(name)
        .extension()
        .and_then(|e| e.to_str())
        .map(str::to_ascii_lowercase)
        .unwrap_or_default();
    if !policy.extensions.contains(&extension) {
        return Err("agent_attachment_format_refused");
    }
    let metadata = std::fs::metadata(path).map_err(|_| "agent_attachment_unreadable")?;
    if !metadata.is_file() {
        return Err("agent_attachment_unreadable");
    }
    if metadata.len() > policy.max_file_bytes {
        return Err("agent_attachment_too_large");
    }
    Ok((name.to_owned(), metadata.len()))
}

fn next_id() -> String {
    static NEXT: AtomicU64 = AtomicU64::new(1);
    format!("upload-{}", NEXT.fetch_add(1, Ordering::Relaxed))
}

/// What the page is told of the files picked, and the ones to send.
pub fn stage(paths: Vec<PathBuf>, policy: &Policy) -> (Vec<Picked>, Vec<Queued>) {
    let mut picked = Vec::new();
    let mut queued = Vec::new();
    for path in paths.into_iter().take(PICK_LIMIT) {
        let id = next_id();
        match admit(&path, policy) {
            Ok((name, size)) => {
                picked.push(Picked {
                    id: id.clone(),
                    name: name.clone(),
                    size_bytes: size,
                    state: "queued",
                    code: None,
                });
                queued.push(Queued {
                    id,
                    name,
                    size,
                    path,
                });
            }
            Err(code) => picked.push(Picked {
                id,
                // A name the storage cannot take is still shown as the file
                // is named, never as its path.
                name: path
                    .file_name()
                    .map(|name| name.to_string_lossy().into_owned())
                    .unwrap_or_default(),
                size_bytes: std::fs::metadata(&path).map_or(0, |m| m.len()),
                state: "refused",
                code: Some(code.to_owned()),
            }),
        }
    }
    (picked, queued)
}

/// The directory the live lane gives the packaged test host's picker. Read
/// only by that host; no other build knows the name.
#[cfg(feature = "webview2-remote-debugging")]
pub const LANE_ATTACH_DIRECTORY: &str = "CADRUMO_DEV_DESKTOP_LIVE_ATTACH_DIR";

/// Where the live lane put the files the packaged test host picks, if it
/// says.
#[cfg(feature = "webview2-remote-debugging")]
pub fn lane_directory() -> Option<std::ffi::OsString> {
    std::env::var_os(LANE_ATTACH_DIRECTORY).filter(|value| !value.is_empty())
}

/// No other build reads where the lane put any files.
#[cfg(not(feature = "webview2-remote-debugging"))]
pub fn lane_directory() -> Option<std::ffi::OsString> {
    None
}

/// The files the packaged test host picks in place of the dialog: every
/// entry of the lane's directory, by name, which are then staged and sent
/// as a person's picks are.
#[cfg(feature = "webview2-remote-debugging")]
pub fn lane_picks(directory: Option<std::ffi::OsString>) -> Option<Vec<PathBuf>> {
    let mut paths: Vec<PathBuf> = std::fs::read_dir(directory?)
        .ok()?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .collect();
    paths.sort();
    Some(paths)
}

/// Every other build picks nothing here, whatever it is given, and opens the
/// dialog.
#[cfg(not(feature = "webview2-remote-debugging"))]
pub fn lane_picks(_directory: Option<std::ffi::OsString>) -> Option<Vec<PathBuf>> {
    None
}

/// The SHA-256 of what `reader` holds, as 64 lowercase hex digits.
pub fn sha256_of(reader: &mut dyn Read) -> io::Result<String> {
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 64 * 1024];
    loop {
        let read = reader.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect())
}

/// A reader that says how far it has been read, now and then.
struct Reporting<'a, R> {
    inner: R,
    sent: u64,
    reported: u64,
    report: &'a dyn Fn(u64),
}

impl<R: Read> Read for Reporting<'_, R> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let read = self.inner.read(buffer)?;
        self.sent += read as u64;
        if self.sent - self.reported >= REPORT_EVERY {
            self.reported = self.sent;
            (self.report)(self.sent);
        }
        Ok(read)
    }
}

/// Sends one file: its digest first, then its bytes, as they are now.
fn send_one(
    client: &Client,
    conversation: &str,
    file: &Queued,
    channel: &Channel<UploadEvent>,
) -> Result<Value, Refused> {
    let unreadable = || Refused::new("agent_attachment_unreadable".to_owned());
    let sha256 = sha256_of(&mut File::open(&file.path).map_err(|_| unreadable())?)
        .map_err(|_| unreadable())?;
    let report = |sent: u64| {
        let _ = channel.send(UploadEvent::Progress {
            id: file.id.clone(),
            sent,
        });
    };
    // Exactly the length announced is sent: a file that grew since is cut
    // there, and one that shrank fails, so the digest decides.
    let mut body = Reporting {
        inner: File::open(&file.path)
            .map_err(|_| unreadable())?
            .take(file.size),
        sent: 0,
        reported: 0,
        report: &report,
    };
    let stored = client.upload(conversation, &file.name, &mut body, file.size, &sha256)?;
    document_record(&stored)
}

/// Sends each queued file in turn and tells the page how each went.
pub fn send_all(
    gateway: &Gateway,
    conversation: &str,
    queued: Vec<Queued>,
    channel: &Channel<UploadEvent>,
) {
    let client = Client::new(gateway);
    for file in queued {
        let event = match send_one(&client, conversation, &file, channel) {
            Ok(document) => UploadEvent::Stored {
                id: file.id,
                document,
            },
            Err(refused) => UploadEvent::Refused {
                id: file.id,
                code: refused.code,
            },
        };
        let _ = channel.send(event);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn policy() -> Policy {
        policy_of(
            &json!({"max_file_bytes": 10, "max_files_per_conversation": 200,
            "max_total_bytes_per_conversation": 1_000,
            "formats": [{"media_type": "application/pdf", "extensions": [".pdf", "PDF"]},
                        {"media_type": "text/plain", "extensions": ["txt"]}]}),
        )
        .unwrap()
    }

    #[test]
    fn the_policy_reads_its_bound_and_extensions_once_each() {
        assert_eq!(
            policy(),
            Policy {
                max_file_bytes: 10,
                extensions: vec!["pdf".to_owned(), "txt".to_owned()]
            }
        );
        for bad in [
            json!({}),
            json!({"max_file_bytes": 0, "formats": [{"extensions": ["pdf"]}]}),
            json!({"max_file_bytes": 1, "formats": []}),
            json!({"max_file_bytes": 1, "formats": [{"extensions": ["p/f"]}]}),
            json!({"max_file_bytes": 1, "formats": [{"extensions": [3]}]}),
        ] {
            assert_eq!(
                policy_of(&bad).unwrap_err().code,
                "agent_gateway_unreadable",
                "{bad}"
            );
        }
    }

    #[test]
    fn a_pick_is_staged_against_the_policy_before_anything_is_sent() {
        let root = std::env::temp_dir().join(format!("cadrumo-upload-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let write = |name: &str, bytes: &[u8]| {
            let path = root.join(name);
            std::fs::write(&path, bytes).unwrap();
            path
        };
        let fits = write("factura.PDF", b"%PDF-1");
        let large = write("grande.pdf", &[0u8; 11]);
        let zipped = write("archivo.zip", b"PK");
        let missing = root.join("ausente.pdf");
        let hidden = write(".oculto.pdf", b"%PDF-1");
        let (picked, queued) = stage(
            vec![fits, large, zipped, missing, root.clone(), hidden],
            &policy(),
        );
        let states: Vec<(&str, &str, Option<&str>)> = picked
            .iter()
            .map(|p| (p.name.as_str(), p.state, p.code.as_deref()))
            .collect();
        assert_eq!(
            states[..4],
            [
                ("factura.PDF", "queued", None),
                ("grande.pdf", "refused", Some("agent_attachment_too_large")),
                (
                    "archivo.zip",
                    "refused",
                    Some("agent_attachment_format_refused")
                ),
                (
                    "ausente.pdf",
                    "refused",
                    Some("agent_attachment_unreadable")
                ),
            ]
        );
        assert_eq!(picked[4].state, "refused");
        assert_eq!(
            picked[5].code.as_deref(),
            Some("agent_attachment_name_refused")
        );
        assert_eq!(queued.len(), 1);
        assert_eq!(queued[0].size, 6);
        assert!(
            picked
                .iter()
                .all(|p| !p.name.contains(std::path::MAIN_SEPARATOR))
        );
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn only_the_packaged_test_host_takes_the_lanes_files() {
        let root = std::env::temp_dir().join(format!("cadrumo-lane-picks-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(root.join("b.txt"), b"b").unwrap();
        std::fs::write(root.join("a.csv"), b"a").unwrap();
        let picks = lane_picks(Some(root.clone().into_os_string()));
        #[cfg(feature = "webview2-remote-debugging")]
        assert_eq!(picks, Some(vec![root.join("a.csv"), root.join("b.txt")]));
        // A shipped build opens the dialog whatever directory it is given,
        // and reads no variable naming one.
        #[cfg(not(feature = "webview2-remote-debugging"))]
        {
            assert_eq!(picks, None);
            assert_eq!(lane_directory(), None);
        }
        assert_eq!(lane_picks(None), None);
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn a_digest_is_the_sha256_of_every_byte() {
        assert_eq!(
            sha256_of(&mut &b"abc"[..]).unwrap(),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }
}
