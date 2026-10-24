//! Receipts: one non-secret record per installed item, written atomically after the item
//! verified, under `components/receipts`.
//!
//! A receipt records what was installed, a digest manifest of the installed files, when
//! the item last verified and the hosts it came from. It is evidence a check compares
//! against, never authority: a receipt whose files are gone describes nothing, so
//! [`observe_install`] only ever reports an item present when its files are.

use super::{failure::FailureCategory, items::ItemId, state::Observation};
use crate::{
    error::Error,
    filesystem,
    value::{HostName, RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

pub const RECEIPT_VERSION: u32 = 1;
const RECEIPT_BYTES_LIMIT: u64 = 4 * 1024 * 1024;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ReceiptFile {
    pub path: RelativePath,
    pub size_bytes: u64,
    pub sha256: Sha256Digest,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Receipt {
    pub receipt_version: u32,
    pub item_id: ItemId,
    pub version: Option<String>,
    /// Every installed file, once each, in path order.
    pub files: Vec<ReceiptFile>,
    /// When the item last verified, as UTC `YYYY-MM-DDTHH:MM:SSZ`.
    pub verified_at: String,
    pub hosts: Vec<HostName>,
}

impl Receipt {
    pub fn new(
        item: ItemId,
        version: Option<String>,
        files: Vec<ReceiptFile>,
        verified_at: SystemTime,
        hosts: Vec<HostName>,
    ) -> Result<Self, Error> {
        let receipt = Self {
            receipt_version: RECEIPT_VERSION,
            item_id: item,
            version,
            files,
            verified_at: utc_timestamp(verified_at),
            hosts,
        };
        receipt.validate()?;
        Ok(receipt)
    }

    fn validate(&self) -> Result<(), Error> {
        let ordered = self
            .files
            .windows(2)
            .all(|pair| pair[0].path < pair[1].path);
        if self.receipt_version != RECEIPT_VERSION
            || !ordered
            || self
                .version
                .as_ref()
                .is_some_and(|v| v.is_empty() || v.len() > 128)
            || !timestamp(&self.verified_at)
        {
            return Err(Error::Invalid("receipt shape".into()));
        }
        Ok(())
    }
}

/// A read of one item's receipt: a damaged or foreign file is unreadable, never absent.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ReceiptReading {
    Present(Receipt),
    Absent,
    Unreadable,
}

/// Atomic, per-item receipt files under one folder.
pub struct ReceiptStore {
    root: PathBuf,
}

impl ReceiptStore {
    pub fn new(root: PathBuf) -> Result<Self, Error> {
        filesystem::absolute_root(&root)?;
        Ok(Self { root })
    }

    fn path(&self, item: ItemId) -> PathBuf {
        self.root.join(format!("{item}.json"))
    }

    /// Replaces the item's receipt; written only after the item's own check passed.
    pub fn write(&self, receipt: &Receipt) -> Result<(), Error> {
        receipt.validate()?;
        filesystem::refuse_links(&self.root)?;
        fs::create_dir_all(&self.root)?;
        filesystem::replace_json(&self.path(receipt.item_id), receipt)
    }

    pub fn read(&self, item: ItemId) -> ReceiptReading {
        let bytes = match filesystem::bounded_bytes(&self.path(item), RECEIPT_BYTES_LIMIT) {
            Ok(bytes) => bytes,
            Err(Error::Io(error)) if error.kind() == std::io::ErrorKind::NotFound => {
                return ReceiptReading::Absent;
            }
            Err(_) => return ReceiptReading::Unreadable,
        };
        match serde_json::from_slice::<Receipt>(&bytes) {
            Ok(receipt) if receipt.item_id == item && receipt.validate().is_ok() => {
                ReceiptReading::Present(receipt)
            }
            _ => ReceiptReading::Unreadable,
        }
    }

    /// Removes the item's receipt when its install is removed.
    pub fn remove(&self, item: ItemId) -> Result<(), Error> {
        match fs::remove_file(self.path(item)) {
            Err(error) if error.kind() != std::io::ErrorKind::NotFound => Err(error.into()),
            _ => Ok(()),
        }
    }
}

/// Hashes every regular file under `install_root` into a manifest, in path order. Links
/// and reparse points are refused, so a manifest never describes bytes outside the root.
pub fn build_manifest(install_root: &Path) -> Result<Vec<ReceiptFile>, Error> {
    filesystem::absolute_root(install_root)?;
    let mut files = BTreeMap::new();
    let mut pending = vec![install_root.to_path_buf()];
    while let Some(directory) = pending.pop() {
        for entry in fs::read_dir(&directory)? {
            let entry = entry?;
            let meta = entry.metadata()?;
            filesystem::refuse_metadata_links(&fs::symlink_metadata(entry.path())?)?;
            let path = entry.path();
            if meta.is_dir() {
                pending.push(path);
            } else if meta.is_file() {
                let relative = path
                    .strip_prefix(install_root)
                    .map_err(|_| Error::Invalid("manifest path escaped".into()))?;
                let relative = RelativePath::from_native(relative)?;
                files.insert(
                    relative.clone(),
                    ReceiptFile {
                        path: relative,
                        size_bytes: meta.len(),
                        sha256: filesystem::digest(&path)?,
                    },
                );
            }
        }
    }
    Ok(files.into_values().collect())
}

/// How the files on disk compare with a receipt's manifest.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ManifestCheck {
    pub missing: Vec<RelativePath>,
    pub changed: Vec<RelativePath>,
    pub checked: usize,
}

impl ManifestCheck {
    pub fn intact(&self) -> bool {
        self.missing.is_empty() && self.changed.is_empty()
    }
}

/// Compares installed files with `receipt`; `only` limits the check to named paths, as a
/// quick check does with its executables. A named path the receipt does not record counts
/// as missing.
pub fn check_manifest(
    install_root: &Path,
    receipt: &Receipt,
    only: Option<&[RelativePath]>,
) -> ManifestCheck {
    let recorded: BTreeMap<&RelativePath, &ReceiptFile> = receipt
        .files
        .iter()
        .map(|file| (&file.path, file))
        .collect();
    let names: Vec<&RelativePath> = match only {
        Some(only) => only.iter().collect(),
        None => recorded.keys().copied().collect(),
    };
    let mut check = ManifestCheck {
        checked: names.len(),
        ..ManifestCheck::default()
    };
    for name in names {
        let path = name.under(install_root);
        let Some(entry) = recorded.get(name) else {
            check.missing.push(name.clone());
            continue;
        };
        let present = filesystem::refuse_links(&path).is_ok()
            && fs::symlink_metadata(&path).is_ok_and(|meta| meta.is_file());
        if !present {
            check.missing.push(name.clone());
        } else if fs::metadata(&path).map(|meta| meta.len()).ok() != Some(entry.size_bytes)
            || filesystem::digest(&path).ok().as_ref() != Some(&entry.sha256)
        {
            check.changed.push(name.clone());
        }
    }
    check
}

/// What a check can observe from an install root and its receipt. An item is present only
/// when the receipt lists files and every checked file is there with its recorded bytes;
/// files that are gone read absent, changed bytes are damage, and an unreadable receipt is
/// unreadable.
pub fn observe_install(
    reading: &ReceiptReading,
    install_root: &Path,
    only: Option<&[RelativePath]>,
) -> Observation {
    match reading {
        ReceiptReading::Absent => Observation::Absent,
        ReceiptReading::Unreadable => Observation::Unreadable,
        ReceiptReading::Present(receipt) => {
            if receipt.files.is_empty() {
                return Observation::Absent;
            }
            let check = check_manifest(install_root, receipt, only);
            if !check.missing.is_empty() {
                Observation::Absent
            } else if !check.changed.is_empty() {
                Observation::Failed(FailureCategory::DamagedDownload)
            } else {
                Observation::Present { note: None }
            }
        }
    }
}

/// `time` as UTC `YYYY-MM-DDTHH:MM:SSZ`.
pub fn utc_timestamp(time: SystemTime) -> String {
    let seconds = time
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_secs())
        .unwrap_or_default();
    let days = (seconds / 86_400) as i64;
    let rest = seconds % 86_400;
    // Civil date from days since 1970-01-01 (Howard Hinnant's algorithm).
    let shifted = days + 719_468;
    let era = shifted.div_euclid(146_097);
    let day_of_era = shifted.rem_euclid(146_097);
    let year_of_era =
        (day_of_era - day_of_era / 1460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_index = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_index + 2) / 5 + 1;
    let month = if month_index < 10 {
        month_index + 3
    } else {
        month_index - 9
    };
    let year = year_of_era + era * 400 + i64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        rest / 3600,
        rest % 3600 / 60,
        rest % 60
    )
}

fn timestamp(value: &str) -> bool {
    let bytes = value.as_bytes();
    bytes.len() == 20
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes[10] == b'T'
        && bytes[13] == b':'
        && bytes[16] == b':'
        && bytes[19] == b'Z'
        && [0..4, 5..7, 8..10, 11..13, 14..16, 17..19]
            .into_iter()
            .all(|range| bytes[range].iter().all(u8::is_ascii_digit))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    fn install(root: &Path) {
        fs::create_dir_all(root.join("bin")).unwrap();
        fs::write(root.join("bin/tool"), b"tool bytes").unwrap();
        fs::write(root.join("data.txt"), b"data").unwrap();
    }

    fn receipt(root: &Path) -> Receipt {
        Receipt::new(
            ItemId::LocalAi,
            Some("0.40.10".into()),
            build_manifest(root).unwrap(),
            UNIX_EPOCH + Duration::from_secs(1_792_846_800),
            vec![HostName::new("github.com").unwrap()],
        )
        .unwrap()
    }

    #[test]
    fn receipts_round_trip_atomically_and_damage_reads_unreadable_not_absent() {
        let directory = tempfile::tempdir().unwrap();
        let install_root = directory.path().join("install");
        install(&install_root);
        let store = ReceiptStore::new(directory.path().join("receipts")).unwrap();
        assert_eq!(store.read(ItemId::LocalAi), ReceiptReading::Absent);
        let written = receipt(&install_root);
        assert_eq!(written.verified_at, "2026-10-24T13:00:00Z");
        assert_eq!(
            written
                .files
                .iter()
                .map(|file| file.path.as_str())
                .collect::<Vec<_>>(),
            ["bin/tool", "data.txt"]
        );
        store.write(&written).unwrap();
        store.write(&written).unwrap();
        assert_eq!(
            store.read(ItemId::LocalAi),
            ReceiptReading::Present(written.clone())
        );
        assert_eq!(
            fs::read_dir(directory.path().join("receipts"))
                .unwrap()
                .count(),
            1,
            "no pending file is left behind"
        );
        assert_eq!(store.read(ItemId::Browser), ReceiptReading::Absent);
        fs::write(directory.path().join("receipts/browser.json"), b"{not json").unwrap();
        assert_eq!(store.read(ItemId::Browser), ReceiptReading::Unreadable);
        fs::copy(
            directory.path().join("receipts/local_ai.json"),
            directory.path().join("receipts/browser.json"),
        )
        .unwrap();
        assert_eq!(
            store.read(ItemId::Browser),
            ReceiptReading::Unreadable,
            "a foreign item's receipt"
        );
        store.remove(ItemId::LocalAi).unwrap();
        store.remove(ItemId::LocalAi).unwrap();
        assert_eq!(store.read(ItemId::LocalAi), ReceiptReading::Absent);
    }

    #[test]
    fn a_receipt_alone_never_makes_an_item_present() {
        let directory = tempfile::tempdir().unwrap();
        let install_root = directory.path().join("install");
        install(&install_root);
        let present = ReceiptReading::Present(receipt(&install_root));
        assert_eq!(
            observe_install(&present, &install_root, None),
            Observation::Present { note: None }
        );
        let quick = [RelativePath::new("bin/tool").unwrap()];
        assert_eq!(
            observe_install(&present, &install_root, Some(&quick)),
            Observation::Present { note: None }
        );
        fs::write(install_root.join("data.txt"), b"DATA").unwrap();
        assert_eq!(
            observe_install(&present, &install_root, None),
            Observation::Failed(FailureCategory::DamagedDownload)
        );
        assert_eq!(
            observe_install(&present, &install_root, Some(&quick)),
            Observation::Present { note: None },
            "a quick check reads only what it names"
        );
        fs::remove_dir_all(&install_root).unwrap();
        assert_eq!(
            observe_install(&present, &install_root, None),
            Observation::Absent
        );
        let unlisted = [RelativePath::new("bin/other").unwrap()];
        install(&install_root);
        assert_eq!(
            observe_install(&present, &install_root, Some(&unlisted)),
            Observation::Absent
        );
        let mut empty = receipt(&install_root);
        empty.files.clear();
        assert_eq!(
            observe_install(&ReceiptReading::Present(empty), &install_root, None),
            Observation::Absent
        );
        assert_eq!(
            observe_install(&ReceiptReading::Unreadable, &install_root, None),
            Observation::Unreadable
        );
    }

    #[test]
    fn timestamps_spell_utc_civil_time() {
        for (seconds, expected) in [
            (0, "1970-01-01T00:00:00Z"),
            (951_782_400, "2000-02-29T00:00:00Z"),
            (4_107_542_399, "2100-02-28T23:59:59Z"),
        ] {
            let spelled = utc_timestamp(UNIX_EPOCH + Duration::from_secs(seconds));
            assert_eq!(spelled, expected);
            assert!(timestamp(&spelled));
        }
        assert!(!timestamp("2026-10-24 13:00:00Z"));
    }
}
