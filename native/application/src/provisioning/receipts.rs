//! Receipts: one non-secret record per installed item, written atomically after the item
//! verified, under `components/receipts`.
//!
//! A receipt records what was installed, a digest manifest of the installed files, when
//! the item last verified and the hosts it came from. It is evidence a check compares
//! against, never authority: a receipt whose files are gone describes nothing, so
//! [`observe_install`] only ever reports an item present when its files are.
//!
//! A receipt can also say where the item is: its [`ReceiptLocation`] names the folder the
//! files are relative to, the paths a consumer uses inside it, and the identity facts a
//! consumer compares with its own. The Python consumers locate a component through this
//! record and nothing else, so it is the one place both languages agree on a location.

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
const LOCATION_ENTRIES_LIMIT: usize = 64;
const LOCATION_TEXT_LIMIT: usize = 128;

/// Where a verified item is, for the consumers that use it.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ReceiptLocation {
    /// The absolute folder the receipt's files and these paths are relative to.
    pub root: String,
    /// The paths a consumer uses, by name, each relative to `root`.
    pub paths: BTreeMap<String, RelativePath>,
    /// Locale-neutral identity facts a consumer compares with its own before using the
    /// item, such as the driver version a browser build belongs to.
    pub facts: BTreeMap<String, String>,
}

impl ReceiptLocation {
    pub fn new(
        root: &Path,
        paths: BTreeMap<String, RelativePath>,
        facts: BTreeMap<String, String>,
    ) -> Result<Self, Error> {
        filesystem::absolute_root(root)?;
        let root = root
            .to_str()
            .ok_or_else(|| Error::Invalid("non-UTF8 component location".into()))?
            .to_owned();
        let location = Self { root, paths, facts };
        location.validate()?;
        Ok(location)
    }

    /// The location's folder.
    pub fn root(&self) -> PathBuf {
        PathBuf::from(&self.root)
    }

    fn validate(&self) -> Result<(), Error> {
        let named = |name: &String| {
            !name.is_empty()
                && name.len() <= LOCATION_TEXT_LIMIT
                && name
                    .bytes()
                    .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || b"_-".contains(&c))
        };
        let root = Path::new(&self.root);
        if !root.is_absolute()
            || root
                .components()
                .any(|part| matches!(part, std::path::Component::ParentDir))
            || self.paths.is_empty()
            || self.paths.len() + self.facts.len() > LOCATION_ENTRIES_LIMIT
            || !self.paths.keys().all(named)
            || !self.facts.keys().all(named)
            || self
                .facts
                .values()
                .any(|value| value.is_empty() || value.len() > LOCATION_TEXT_LIMIT)
        {
            return Err(Error::Invalid("receipt location".into()));
        }
        Ok(())
    }
}

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
    /// When the item last verified, as UTC `YYYY-MM-DDTHH:MM:SSZ`. A receipt read with
    /// fractional seconds, as the earlier setup wrote them, holds them truncated.
    pub verified_at: String,
    pub hosts: Vec<HostName>,
    /// Where the item is; absent from receipts that only describe files.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub location: Option<ReceiptLocation>,
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
            location: None,
        };
        receipt.validate()?;
        Ok(receipt)
    }

    /// The same receipt, saying where the item is.
    pub fn located(mut self, location: ReceiptLocation) -> Result<Self, Error> {
        self.location = Some(location);
        self.validate()?;
        Ok(self)
    }

    fn validate(&self) -> Result<(), Error> {
        if let Some(location) = &self.location {
            location.validate()?;
        }
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
            || canonical_timestamp(&self.verified_at).as_deref() != Some(&self.verified_at)
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
        let Ok(mut receipt) = serde_json::from_slice::<Receipt>(&bytes) else {
            return ReceiptReading::Unreadable;
        };
        let Some(verified_at) = canonical_timestamp(&receipt.verified_at) else {
            return ReceiptReading::Unreadable;
        };
        receipt.verified_at = verified_at;
        if receipt.item_id == item && receipt.validate().is_ok() {
            ReceiptReading::Present(receipt)
        } else {
            ReceiptReading::Unreadable
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

/// The canonical `YYYY-MM-DDTHH:MM:SSZ` form of an RFC 3339 UTC timestamp with optional
/// fractional seconds (one to nine digits), or `None` for any other text.
fn canonical_timestamp(value: &str) -> Option<String> {
    let bytes = value.as_bytes();
    let seconds = bytes.get(..19)?;
    let shaped = seconds[4] == b'-'
        && seconds[7] == b'-'
        && seconds[10] == b'T'
        && seconds[13] == b':'
        && seconds[16] == b':'
        && [0..4, 5..7, 8..10, 11..13, 14..16, 17..19]
            .into_iter()
            .all(|range| seconds[range].iter().all(u8::is_ascii_digit));
    let fraction = match &bytes[19..] {
        [b'Z'] => true,
        [b'.', digits @ .., b'Z'] => {
            (1..=9).contains(&digits.len()) && digits.iter().all(u8::is_ascii_digit)
        }
        _ => false,
    };
    (shaped && fraction).then(|| format!("{}Z", &value[..19]))
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
            assert_eq!(canonical_timestamp(&spelled).as_deref(), Some(expected));
        }
        for (value, canonical) in [
            ("2026-10-18T13:00:00.123456Z", Some("2026-10-18T13:00:00Z")),
            ("2026-10-18T13:00:00.1Z", Some("2026-10-18T13:00:00Z")),
            (
                "2026-10-18T13:00:00.123456789Z",
                Some("2026-10-18T13:00:00Z"),
            ),
            ("2026-10-18T13:00:00.1234567890Z", None),
            ("2026-10-18T13:00:00.Z", None),
            ("2026-10-18T13:00:00.12a4Z", None),
            ("2026-10-18T13:00:00+00:00", None),
            ("2026-10-18T13:00:00", None),
            ("2026-10-24 13:00:00Z", None),
            ("", None),
        ] {
            assert_eq!(canonical_timestamp(value).as_deref(), canonical, "{value}");
        }
    }

    /// Written by the earlier Python setup's own receipt model and serialiser for a
    /// browser verified at 13:00:00.123456 UTC.
    const PYTHON_RECEIPT: &str = r#"{"files":[{"path":"chrome-win/chrome.exe","sha256":"b0335dc5c19f374fb20d56c5e3764727a1dc64df38c0a2f4239d35a6ef4a3e82","size_bytes":10}],"hosts":["cdn.playwright.dev"],"item_id":"browser","receipt_version":1,"verified_at":"2026-10-18T13:00:00.123456Z","version":"1194"}"#;

    #[test]
    fn a_receipt_the_earlier_setup_wrote_reads_and_is_rewritten_canonically() {
        let directory = tempfile::tempdir().unwrap();
        let receipts = directory.path().join("receipts");
        fs::create_dir_all(&receipts).unwrap();
        fs::write(receipts.join("browser.json"), PYTHON_RECEIPT).unwrap();
        let store = ReceiptStore::new(receipts.clone()).unwrap();
        let ReceiptReading::Present(read) = store.read(ItemId::Browser) else {
            panic!("a Python-written receipt must read present");
        };
        assert_eq!(read.verified_at, "2026-10-18T13:00:00Z");
        assert_eq!(read.version.as_deref(), Some("1194"));
        assert_eq!(read.files[0].sha256, Sha256Digest::of(b"tool bytes"));
        store.write(&read).unwrap();
        let rewritten = fs::read_to_string(receipts.join("browser.json")).unwrap();
        assert!(rewritten.contains("\"verified_at\":\"2026-10-18T13:00:00Z\""));
        assert_eq!(store.read(ItemId::Browser), ReceiptReading::Present(read));

        let install_root = directory.path().join("install");
        fs::create_dir_all(install_root.join("chrome-win")).unwrap();
        fs::write(install_root.join("chrome-win/chrome.exe"), b"tool bytes").unwrap();
        assert_eq!(
            observe_install(&store.read(ItemId::Browser), &install_root, None),
            Observation::Present { note: None },
            "its files decide, not its age"
        );

        let mut odd = read_value(PYTHON_RECEIPT);
        odd["verified_at"] = "2026-10-18T13:00:00+01:00".into();
        fs::write(receipts.join("browser.json"), odd.to_string()).unwrap();
        assert_eq!(store.read(ItemId::Browser), ReceiptReading::Unreadable);
        let mut invalid = read_value(PYTHON_RECEIPT);
        invalid["verified_at"] = "2026-10-18T13:00:00.123456Z".into();
        let invalid: Receipt = serde_json::from_value(invalid).unwrap();
        assert!(
            store.write(&invalid).is_err(),
            "a receipt is only ever written in the canonical form"
        );
    }

    #[test]
    fn a_located_receipt_round_trips_and_a_location_that_could_mislead_is_refused() {
        let directory = tempfile::tempdir().unwrap();
        let install_root = directory.path().join("install");
        install(&install_root);
        let location = ReceiptLocation::new(
            &install_root,
            [("tool".to_owned(), RelativePath::new("bin/tool").unwrap())].into(),
            [("driver".to_owned(), "1.2.3".to_owned())].into(),
        )
        .unwrap();
        assert_eq!(location.root(), install_root);
        let located = receipt(&install_root).located(location.clone()).unwrap();
        let store = ReceiptStore::new(directory.path().join("receipts")).unwrap();
        store.write(&located).unwrap();
        assert_eq!(
            store.read(ItemId::LocalAi),
            ReceiptReading::Present(located.clone())
        );
        let unlocated = serde_json::to_value(receipt(&install_root)).unwrap();
        assert!(
            unlocated.get("location").is_none(),
            "a receipt without a location keeps the earlier shape"
        );

        assert!(
            ReceiptLocation::new(Path::new("relative"), location.paths.clone(), [].into()).is_err()
        );
        assert!(ReceiptLocation::new(&install_root, [].into(), [].into()).is_err());
        for (name, value) in [("Driver", "1"), ("driver", ""), ("", "1")] {
            assert!(
                ReceiptLocation::new(
                    &install_root,
                    location.paths.clone(),
                    [(name.to_owned(), value.to_owned())].into()
                )
                .is_err(),
                "{name}={value}"
            );
        }
        let mut stored = serde_json::to_value(&located).unwrap();
        stored["location"]["root"] = "relative/root".into();
        fs::write(
            directory.path().join("receipts/local_ai.json"),
            stored.to_string(),
        )
        .unwrap();
        assert_eq!(store.read(ItemId::LocalAi), ReceiptReading::Unreadable);
    }

    fn read_value(text: &str) -> serde_json::Value {
        serde_json::from_str(text).unwrap()
    }
}
