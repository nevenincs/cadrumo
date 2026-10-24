//! The browser item: the Chromium builds the bundled Playwright driver launches, installed
//! by the engine straight into the layout the driver reads.
//!
//! The driver's `browsers.json` names each build and its revision. The driver looks for a
//! build in `<browsers root>/<name, '-' read as '_'>-<revision>`, finds its executable at
//! a fixed path inside that folder for each platform, and counts the build as installed
//! only while the folder holds an empty `INSTALLATION_COMPLETE` file. Its own installer
//! writes that file last, after extracting the archive and marking the executable
//! runnable. At launch the driver checks only that the executable exists; on Windows it
//! also runs the `winldd` build's `PrintDeps.exe` to check the browser's libraries, unless
//! a `DEPENDENCIES_VALIDATED` file it writes itself after that check is recent.
//!
//! The engine installs each pinned archive the same way. It fetches the bytes the pin
//! names, extracts them with bounded, link-free extraction into a private staging folder
//! beside the builds, marks the executable runnable, writes the marker, and only then
//! moves the finished build into place. A build folder therefore holds a complete build or
//! does not exist, and a build without its marker reads absent and is installed again.
//! The engine never writes `DEPENDENCIES_VALIDATED`, so the driver still runs its own
//! library check, and it writes no `.links` entry, because it removes superseded builds
//! itself rather than leaving that to the vendor installer's collection.
//!
//! [`BrowserLayout::settle`] runs only after the new builds verified: it writes the item's
//! receipt, which says where the builds are and which driver they belong to, and then
//! removes the builds of the same families they supersede.

use super::{
    activity::ItemWriter,
    failure::{FailureCategory, TransferFailure},
    items::ItemId,
    pins::{BrowserArchivePin, BrowserArchivePins, Platform},
    receipts::{
        Receipt, ReceiptFile, ReceiptLocation, ReceiptReading, ReceiptStore, build_manifest,
        check_manifest,
    },
    state::SetupStep,
    transfer::{Pinned, Transfer, TransferEvent, file_failure},
};
use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    value::{HostName, RelativePath},
};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
    time::SystemTime,
};

/// The file the driver reads as "this build is completely installed".
pub const COMPLETION_MARKER: &str = "INSTALLATION_COMPLETE";

/// The bundled driver's package folder, relative to the site-packages folder it ships in.
pub const DRIVER_PACKAGE: &str = "playwright/driver/package";

/// The location setting that relocates the browsers folder, declared in the package's
/// environment definition and honoured by the Python consumer the same way.
pub const BROWSERS_DIR_VARIABLE: &str = "CADRUMO_PLAYWRIGHT_BROWSERS_DIR";

/// The browsers folder under the storage root when no setting relocates it.
pub const BROWSERS_DEFAULT: &str = "components/playwright";

/// The fact a browser receipt's location carries: the driver version its builds belong to.
pub const DRIVER_FACT: &str = "playwright_driver";

/// The folder beside the builds where downloads and extraction happen. Its name is not a
/// build name, so the driver never mistakes it for a browser.
const STAGING: &str = ".cadrumo-staging";

const DRIVER_FILE_BYTES_LIMIT: u64 = 1024 * 1024;
const ARCHIVE_ENTRIES_LIMIT: usize = 100_000;
const BUILD_BYTES_LIMIT: u64 = 8 * 1024 * 1024 * 1024;

/// The build families the engine knows how to place. Their manifest names, folder
/// prefixes and executable paths are the driver's own (`EXECUTABLE_PATHS` in its registry).
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
enum Family {
    Chromium,
    HeadlessShell,
    Ffmpeg,
    Winldd,
}

impl Family {
    const ALL: [Self; 4] = [
        Self::Chromium,
        Self::HeadlessShell,
        Self::Ffmpeg,
        Self::Winldd,
    ];

    fn manifest_name(self) -> &'static str {
        match self {
            Self::Chromium => "chromium",
            Self::HeadlessShell => "chromium-headless-shell",
            Self::Ffmpeg => "ffmpeg",
            Self::Winldd => "winldd",
        }
    }

    fn directory_prefix(self) -> &'static str {
        match self {
            Self::Chromium => "chromium",
            Self::HeadlessShell => "chromium_headless_shell",
            Self::Ffmpeg => "ffmpeg",
            Self::Winldd => "winldd",
        }
    }

    fn executable(self, platform: Platform) -> Option<&'static str> {
        use Platform::*;
        Some(match (self, platform) {
            (Self::Chromium, LinuxX64) => "chrome-linux64/chrome",
            (Self::Chromium, LinuxArm64) => "chrome-linux-arm64/chrome",
            (Self::Chromium, MacX64) => {
                "chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
            }
            (Self::Chromium, MacArm64) => {
                "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
            }
            (Self::Chromium, WinX64) => "chrome-win64/chrome.exe",
            (Self::HeadlessShell, LinuxX64) => {
                "chrome-headless-shell-linux64/chrome-headless-shell"
            }
            (Self::HeadlessShell, LinuxArm64) => {
                "chrome-headless-shell-linux-arm64/chrome-headless-shell"
            }
            (Self::HeadlessShell, MacX64) => "chrome-headless-shell-mac-x64/chrome-headless-shell",
            (Self::HeadlessShell, MacArm64) => {
                "chrome-headless-shell-mac-arm64/chrome-headless-shell"
            }
            (Self::HeadlessShell, WinX64) => {
                "chrome-headless-shell-win64/chrome-headless-shell.exe"
            }
            (Self::Ffmpeg, LinuxX64 | LinuxArm64) => "ffmpeg-linux",
            (Self::Ffmpeg, MacX64 | MacArm64) => "ffmpeg-mac",
            (Self::Ffmpeg, WinX64) => "ffmpeg-win64.exe",
            (Self::Winldd, WinX64) => "PrintDeps.exe",
            (Self::Winldd, _) => return None,
        })
    }

    /// The family and revision a build folder name spells, when it is one of ours.
    fn of_directory(name: &str) -> Option<(Self, &str)> {
        let (prefix, revision) = name.rsplit_once('-')?;
        let family = Self::ALL
            .into_iter()
            .find(|family| family.directory_prefix() == prefix)?;
        (!revision.is_empty() && revision.bytes().all(|c| c.is_ascii_digit()))
            .then_some((family, revision))
    }
}

#[derive(Deserialize)]
struct RawDriverBuild {
    name: String,
    revision: String,
    #[serde(rename = "browserVersion")]
    browser_version: Option<String>,
    #[serde(rename = "revisionOverrides")]
    revision_overrides: Option<BTreeMap<String, String>>,
}

#[derive(Deserialize)]
struct RawBrowsersJson {
    browsers: Vec<RawDriverBuild>,
}

#[derive(Deserialize)]
struct RawPackageJson {
    version: String,
}

/// One build the driver's `browsers.json` names.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DriverBuild {
    pub name: String,
    pub revision: String,
    pub browser_version: Option<String>,
    /// The driver picks another revision on some hosts; the engine never guesses which.
    pub overridden: bool,
}

/// What the bundled driver launches: its version and the builds it names.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DriverManifest {
    pub version: String,
    pub builds: Vec<DriverBuild>,
}

impl DriverManifest {
    /// Reads `browsers.json` and `package.json` from the driver's package folder. A folder
    /// without them is an I/O `NotFound`: this build carries no browser driver.
    pub fn read(package: &Path) -> Result<Self, Error> {
        filesystem::absolute_root(package)?;
        let browsers: RawBrowsersJson = serde_json::from_slice(&filesystem::bounded_bytes(
            &package.join("browsers.json"),
            DRIVER_FILE_BYTES_LIMIT,
        )?)?;
        let identity: RawPackageJson = serde_json::from_slice(&filesystem::bounded_bytes(
            &package.join("package.json"),
            DRIVER_FILE_BYTES_LIMIT,
        )?)?;
        let text = |value: &str| !value.is_empty() && value.len() <= 128;
        if !text(&identity.version) {
            return Err(Error::Invalid("browser driver version".into()));
        }
        let mut builds = Vec::with_capacity(browsers.browsers.len());
        for build in browsers.browsers {
            if !text(&build.name)
                || build.revision.is_empty()
                || build.revision.len() > 16
                || !build.revision.bytes().all(|c| c.is_ascii_digit())
                || build.browser_version.as_deref().is_some_and(|v| !text(v))
            {
                return Err(Error::Invalid("browser driver build".into()));
            }
            builds.push(DriverBuild {
                overridden: build.revision_overrides.is_some_and(|map| !map.is_empty()),
                name: build.name,
                revision: build.revision,
                browser_version: build.browser_version,
            });
        }
        Ok(Self {
            version: identity.version,
            builds,
        })
    }

    fn build(&self, family: Family) -> Option<&DriverBuild> {
        self.builds
            .iter()
            .find(|build| build.name == family.manifest_name() && !build.overridden)
    }
}

/// One build of the item: its folder under the browsers root, its executable, and the
/// archive pinned for it when this build carries one.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrowserBuild {
    family_name: &'static str,
    pub directory_name: String,
    /// The executable, relative to the browsers root.
    pub executable: RelativePath,
    pub pin: Option<BrowserArchivePin>,
}

impl BrowserBuild {
    /// The driver's name for this build, such as `chromium-headless-shell`.
    pub fn name(&self) -> &'static str {
        self.family_name
    }
}

/// The builds the bundled driver needs on this platform, under one browsers root.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrowserLayout {
    root: PathBuf,
    driver_version: String,
    version: String,
    headless_version: Option<String>,
    builds: Vec<BrowserBuild>,
    pinned: bool,
}

impl BrowserLayout {
    /// The layout `driver` needs under `root`. When `pins` cover every build the driver's
    /// Chromium needs on `platform`, the layout is every pinned archive, so setup installs
    /// exactly what the vendor installer would; otherwise it is the two Chromium builds,
    /// which this build can observe but not install.
    pub fn new(
        root: PathBuf,
        driver: &DriverManifest,
        pins: Option<&BrowserArchivePins>,
        platform: Platform,
    ) -> Result<Self, Error> {
        filesystem::absolute_root(&root)?;
        let chromium = driver
            .build(Family::Chromium)
            .ok_or_else(|| Error::Invalid("driver names no Chromium build".into()))?;
        let headless = driver
            .build(Family::HeadlessShell)
            .ok_or_else(|| Error::Invalid("driver names no headless build".into()))?;
        let pinned = pins.and_then(|pins| pinned_builds(pins, driver, platform));
        let builds = match &pinned {
            Some(builds) => builds.clone(),
            None => [Family::Chromium, Family::HeadlessShell]
                .into_iter()
                .map(|family| unpinned_build(family, driver, platform))
                .collect::<Result<_, _>>()?,
        };
        Ok(Self {
            root,
            driver_version: driver.version.clone(),
            version: chromium
                .browser_version
                .clone()
                .unwrap_or_else(|| format!("revision {}", chromium.revision)),
            headless_version: headless.browser_version.clone(),
            builds,
            pinned: pinned.is_some(),
        })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// The version the item reports: the Chromium build's browser version.
    pub fn version(&self) -> &str {
        &self.version
    }

    pub fn driver_version(&self) -> &str {
        &self.driver_version
    }

    pub fn builds(&self) -> &[BrowserBuild] {
        &self.builds
    }

    /// Whether this build pins every archive the layout needs, so setup can install it.
    pub fn pinned(&self) -> bool {
        self.pinned
    }

    fn executable_path(&self, build: &BrowserBuild) -> PathBuf {
        build.executable.under(&self.root)
    }

    /// Whether `build` is installed as the driver reads it: its marker and its executable.
    pub fn complete(&self, build: &BrowserBuild) -> bool {
        let folder = self.root.join(&build.directory_name);
        regular_file(&folder.join(COMPLETION_MARKER)) && regular_file(&self.executable_path(build))
    }

    /// The builds the driver would not read as installed.
    pub fn incomplete(&self) -> Vec<&BrowserBuild> {
        self.builds
            .iter()
            .filter(|build| !self.complete(build))
            .collect()
    }

    /// Whether `reading` is this layout's receipt: for these builds, at this root, of this
    /// driver. Any other receipt describes something else.
    pub fn receipt<'a>(&self, reading: &'a ReceiptReading) -> Option<&'a Receipt> {
        let ReceiptReading::Present(receipt) = reading else {
            return None;
        };
        let location = receipt.location.as_ref()?;
        (receipt.item_id == ItemId::Browser
            && receipt.version.as_deref() == Some(self.version.as_str())
            && location.root() == self.root
            && location.facts.get(DRIVER_FACT) == Some(&self.driver_version)
            && self
                .builds
                .iter()
                .all(|build| location.paths.get(build.name()) == Some(&build.executable)))
        .then_some(receipt)
    }

    /// The builds whose installed files differ from what `reading` recorded, hashing every
    /// recorded file; none when the receipt is not this layout's.
    pub fn damaged(&self, reading: &ReceiptReading) -> BTreeSet<String> {
        let Some(receipt) = self.receipt(reading) else {
            return BTreeSet::new();
        };
        let check = check_manifest(&self.root, receipt, None);
        check
            .missing
            .iter()
            .chain(&check.changed)
            .filter_map(|path| path.as_str().split('/').next().map(str::to_owned))
            .collect()
    }

    /// The bytes setup would download now, or `None` when this build cannot install it.
    pub fn pending_download_bytes(&self, reading: &ReceiptReading) -> Option<u64> {
        self.pinned.then(|| {
            self.pending(reading)
                .iter()
                .filter_map(|build| build.pin.as_ref())
                .map(|pin| pin.download_bytes)
                .sum()
        })
    }

    /// The builds setup installs: every incomplete build and every build the receipt
    /// finds damaged, in table order.
    pub fn pending(&self, reading: &ReceiptReading) -> Vec<&BrowserBuild> {
        let damaged = self.damaged(reading);
        self.builds
            .iter()
            .filter(|build| !self.complete(build) || damaged.contains(&build.directory_name))
            .collect()
    }

    /// Installs every pending build, one at a time, so an interruption keeps each
    /// finished build. `writer` holds the browser's writer lock and records each step;
    /// progress counts the bytes of every pending archive together.
    pub fn install(
        &self,
        transfer: &mut Transfer<'_>,
        writer: &ItemWriter<'_>,
        reading: &ReceiptReading,
    ) -> Result<Installed, Error> {
        if writer.item() != ItemId::Browser {
            return Err(Error::Invalid(
                "browser setup under another item's lock".into(),
            ));
        }
        if !self.pinned {
            return Err(Error::Download(TransferFailure::final_(
                FailureCategory::NotInThisBuild,
            )));
        }
        let pending = self.pending(reading);
        let pins: Vec<(&BrowserBuild, &BrowserArchivePin)> = pending
            .iter()
            .filter_map(|build| build.pin.as_ref().map(|pin| (*build, pin)))
            .collect();
        let total: u64 = pins.iter().map(|(_, pin)| pin.download_bytes).sum();
        let staging = self.staging(pins.iter().map(|(_, pin)| part_name(pin)).collect())?;
        let mut installed = Installed::default();
        let cancellation = transfer.cancellation;
        for (build, pin) in pins {
            cancellation.check()?;
            writer.step(SetupStep::Download)?;
            let partial = staging.join(part_name(pin));
            let done = installed.transferred_bytes;
            let events = &mut *transfer.events;
            let mut overall = |event| {
                events(match event {
                    TransferEvent::Progress { completed, .. } => TransferEvent::Progress {
                        completed: done + completed,
                        total,
                    },
                    other => other,
                })
            };
            Transfer {
                network: transfer.network,
                hosts: transfer.hosts,
                policy: transfer.policy,
                pacing: &mut *transfer.pacing,
                events: &mut overall,
                cancellation,
            }
            .fetch(
                Pinned {
                    sources: &pin.urls,
                    size: pin.download_bytes,
                    sha256: &pin.sha256,
                },
                &partial,
            )?;
            installed.transferred_bytes += pin.download_bytes;
            writer.step(SetupStep::Install)?;
            self.place(build, &partial, &staging, cancellation)?;
            fs::remove_file(&partial)?;
            installed.builds.push(build.directory_name.clone());
        }
        // An empty staging folder is all that is left; one still holding files belongs to
        // a later resume.
        let _ = fs::remove_dir(&staging);
        Ok(installed)
    }

    /// The staging folder, created, holding only the partial downloads named `keep`.
    fn staging(&self, keep: BTreeSet<String>) -> Result<PathBuf, Error> {
        filesystem::refuse_links(&self.root)?;
        fs::create_dir_all(&self.root)?;
        let staging = self.root.join(STAGING);
        filesystem::refuse_links(&staging)?;
        fs::create_dir_all(&staging)?;
        for entry in fs::read_dir(&staging)? {
            let entry = entry?;
            let name = entry.file_name();
            if name.to_str().is_none_or(|name| !keep.contains(name)) {
                remove_tree(&entry.path(), &staging)?;
            }
        }
        Ok(staging)
    }

    /// Extracts the verified archive at `archive` into a candidate beside the builds, marks
    /// it complete, and moves it into place over any incomplete or damaged folder.
    fn place(
        &self,
        build: &BrowserBuild,
        archive: &Path,
        staging: &Path,
        cancellation: &Cancellation,
    ) -> Result<(), Error> {
        let candidate = staging.join(&build.directory_name);
        if fs::symlink_metadata(&candidate).is_ok() {
            remove_tree(&candidate, staging)?;
        }
        fs::create_dir(&candidate)?;
        let files = extract(archive, &candidate, cancellation)?;
        let inside = build
            .executable
            .as_str()
            .strip_prefix(&format!("{}/", build.directory_name))
            .ok_or_else(|| Error::Invalid("executable outside its build".into()))?;
        if !files.contains(inside) {
            return Err(Error::Integrity("browser executable missing".into()));
        }
        make_runnable(&candidate.join(inside))?;
        let marker = File::options()
            .write(true)
            .create_new(true)
            .open(candidate.join(COMPLETION_MARKER))?;
        marker.sync_all()?;
        drop(marker);
        cancellation.check()?;
        let target = self.root.join(&build.directory_name);
        if fs::symlink_metadata(&target).is_ok() {
            remove_tree(&target, &self.root)?;
        }
        fs::rename(&candidate, &target)?;
        Ok(())
    }

    /// Confirms every build is installed as the driver reads it and its executable runs as
    /// a program, before anything is recorded or removed.
    pub fn verify_installation(&self) -> Result<Verified, Error> {
        for build in &self.builds {
            if !self.complete(build) {
                return Err(Error::Integrity("browser build incomplete".into()));
            }
            filesystem::require_executable(&self.executable_path(build))?;
        }
        Ok(Verified(()))
    }

    /// Records the verified builds and then removes the builds of the same families they
    /// supersede. The receipt says where the builds are, which executable each one has
    /// and which driver they belong to, so a consumer locates them without probing.
    pub fn settle(
        &self,
        _verified: Verified,
        receipts: &ReceiptStore,
        hosts: Vec<HostName>,
        verified_at: SystemTime,
    ) -> Result<Settled, Error> {
        let mut files = Vec::new();
        for build in &self.builds {
            let folder = self.root.join(&build.directory_name);
            for file in build_manifest(&folder)? {
                files.push(ReceiptFile {
                    path: RelativePath::new(format!(
                        "{}/{}",
                        build.directory_name,
                        file.path.as_str()
                    ))?,
                    ..file
                });
            }
        }
        files.sort_by(|a, b| a.path.cmp(&b.path));
        let location = ReceiptLocation::new(
            &self.root,
            self.builds
                .iter()
                .map(|build| (build.name().to_owned(), build.executable.clone()))
                .collect(),
            [(DRIVER_FACT.to_owned(), self.driver_version.clone())].into(),
        )?;
        let receipt = Receipt::new(
            ItemId::Browser,
            Some(self.version.clone()),
            files,
            verified_at,
            hosts,
        )?
        .located(location)?;
        receipts.write(&receipt)?;
        Ok(self.remove_superseded())
    }

    /// Removes every other revision of the families this layout installs. A folder that is
    /// a link, or that cannot be removed, stays and is counted.
    fn remove_superseded(&self) -> Settled {
        let mut settled = Settled::default();
        let families: BTreeSet<&str> = self
            .builds
            .iter()
            .filter_map(|build| Family::of_directory(&build.directory_name))
            .map(|(family, _)| family.directory_prefix())
            .collect();
        let current: BTreeSet<&str> = self
            .builds
            .iter()
            .map(|build| build.directory_name.as_str())
            .collect();
        let Ok(entries) = fs::read_dir(&self.root) else {
            settled.left_in_place += 1;
            return settled;
        };
        let mut superseded: Vec<String> = entries
            .filter_map(Result::ok)
            .filter_map(|entry| entry.file_name().into_string().ok())
            .filter(|name| {
                !current.contains(name.as_str())
                    && Family::of_directory(name)
                        .is_some_and(|(family, _)| families.contains(family.directory_prefix()))
            })
            .collect();
        superseded.sort();
        for name in superseded {
            match remove_tree(&self.root.join(&name), &self.root) {
                Ok(()) => settled.removed.push(name),
                Err(_) => settled.left_in_place += 1,
            }
        }
        settled
    }
}

/// Proof that the layout's builds verified; only a check mints it, and settling needs it.
#[derive(Debug)]
pub struct Verified(());

/// What an install did.
#[derive(Debug, Default, Eq, PartialEq)]
pub struct Installed {
    /// The build folders installed, in order.
    pub builds: Vec<String>,
    pub transferred_bytes: u64,
}

/// What settling removed, and how many superseded builds it had to leave.
#[derive(Debug, Default, Eq, PartialEq)]
pub struct Settled {
    pub removed: Vec<String>,
    pub left_in_place: usize,
}

/// The closed category a failed browser setup reports.
pub fn failure_category(error: &Error) -> FailureCategory {
    match error {
        Error::Download(failure) => failure.category,
        Error::Cancelled => FailureCategory::Cancelled,
        Error::Io(error) => file_failure(error).category,
        Error::Archive(_) | Error::Integrity(_) | Error::LimitExceeded => {
            FailureCategory::DamagedDownload
        }
        _ => FailureCategory::Unexpected,
    }
}

/// The browsers folder under `storage_root`, relocated by [`BROWSERS_DIR_VARIABLE`] in
/// `lookup` by the package's member rule: absolute, home-relative or root-relative.
#[cfg(feature = "platform")]
pub fn browsers_root(
    storage_root: &Path,
    lookup: &dyn Fn(&str) -> Option<std::ffi::OsString>,
) -> Result<PathBuf, Error> {
    cadrumo_platform::storage::member_path(
        storage_root,
        BROWSERS_DIR_VARIABLE,
        BROWSERS_DEFAULT,
        lookup,
    )
    .map_err(|refusal| Error::Invalid(format!("browsers location refused: {}", refusal.code)))
}

fn pinned_builds(
    pins: &BrowserArchivePins,
    driver: &DriverManifest,
    platform: Platform,
) -> Option<Vec<BrowserBuild>> {
    let needed = [Family::Chromium, Family::HeadlessShell].map(|family| {
        driver
            .build(family)
            .map(|build| format!("{}-{}", family.directory_prefix(), build.revision))
    });
    let [Some(chromium), Some(headless)] = needed else {
        return None;
    };
    let covering = pins.covering(platform, &driver.version, &[&chromium, &headless])?;
    covering
        .into_iter()
        .map(|pin| {
            let (family, revision) = Family::of_directory(&pin.directory_name)?;
            let named = driver.build(family)?;
            if named.revision != revision {
                return None;
            }
            Some(BrowserBuild {
                family_name: family.manifest_name(),
                directory_name: pin.directory_name.clone(),
                executable: executable_in(&pin.directory_name, family, platform)?,
                pin: Some(pin.clone()),
            })
        })
        .collect()
}

fn unpinned_build(
    family: Family,
    driver: &DriverManifest,
    platform: Platform,
) -> Result<BrowserBuild, Error> {
    let named = driver
        .build(family)
        .ok_or_else(|| Error::Invalid("driver build missing".into()))?;
    let directory_name = format!("{}-{}", family.directory_prefix(), named.revision);
    Ok(BrowserBuild {
        family_name: family.manifest_name(),
        executable: executable_in(&directory_name, family, platform)
            .ok_or_else(|| Error::Invalid("no browser build for this platform".into()))?,
        directory_name,
        pin: None,
    })
}

fn executable_in(directory: &str, family: Family, platform: Platform) -> Option<RelativePath> {
    RelativePath::new(format!("{directory}/{}", family.executable(platform)?)).ok()
}

fn part_name(pin: &BrowserArchivePin) -> String {
    format!("{}.part", pin.sha256)
}

fn regular_file(path: &Path) -> bool {
    filesystem::refuse_links(path).is_ok()
        && fs::symlink_metadata(path).is_ok_and(|meta| meta.is_file())
}

fn make_runnable(path: &Path) -> Result<(), Error> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
    }
    filesystem::require_executable(path)
}

/// Removes `tree`, a direct child of `owner`, once no link is found anywhere inside it;
/// a link is refused rather than followed or removed.
fn remove_tree(tree: &Path, owner: &Path) -> Result<(), Error> {
    if tree.parent() != Some(owner) {
        return Err(Error::Invalid("removal outside the browsers folder".into()));
    }
    filesystem::refuse_links(tree)?;
    if !fs::symlink_metadata(tree)?.is_dir() {
        fs::remove_file(tree)?;
        return Ok(());
    }
    let mut pending = vec![tree.to_path_buf()];
    while let Some(directory) = pending.pop() {
        for entry in fs::read_dir(directory)? {
            let entry = entry?;
            filesystem::refuse_metadata_links(&fs::symlink_metadata(entry.path())?)?;
            if entry.file_type()?.is_dir() {
                pending.push(entry.path());
            }
        }
    }
    fs::remove_dir_all(tree)?;
    Ok(())
}

/// Extracts a zip into `destination`, which must be empty, and returns the files written.
/// Every member must be a plain relative path; links, special files, duplicate names,
/// names that differ only in case and folders spelled two ways are refused, and the member
/// count and the bytes written are bounded.
fn extract(
    archive: &Path,
    destination: &Path,
    cancellation: &Cancellation,
) -> Result<BTreeSet<String>, Error> {
    let mut zip = zip::ZipArchive::new(File::open(archive)?)?;
    if zip.len() > ARCHIVE_ENTRIES_LIMIT {
        return Err(Error::LimitExceeded);
    }
    let mut files = BTreeSet::new();
    let mut seen = BTreeSet::new();
    let mut spellings = BTreeMap::new();
    let mut total = 0u64;
    let mut buffer = vec![0u8; 64 * 1024];
    for index in 0..zip.len() {
        cancellation.check()?;
        let mut member = zip.by_index(index)?;
        let name = member.name()?.into_owned();
        let relative = RelativePath::new(if member.is_dir() {
            name.trim_end_matches('/')
        } else {
            &name
        })?;
        if !seen.insert(relative.as_str().to_lowercase()) {
            return Err(Error::Invalid("duplicate archive member".into()));
        }
        let mut prefix = String::new();
        for part in relative.as_str().split('/') {
            if !prefix.is_empty() {
                prefix.push('/');
            }
            prefix.push_str(part);
            if let Some(previous) = spellings.insert(prefix.to_lowercase(), prefix.clone())
                && previous != prefix
            {
                return Err(Error::Invalid("archive folder spelled two ways".into()));
            }
        }
        let kind = member.unix_mode().unwrap_or(0) & 0o170000;
        if member.is_symlink() || !matches!(kind, 0 | 0o040000 | 0o100000) {
            return Err(Error::Invalid(
                "archive links and special files are refused".into(),
            ));
        }
        let path = relative.under(destination);
        if member.is_dir() {
            fs::create_dir_all(&path)?;
            continue;
        }
        if member.size() > BUILD_BYTES_LIMIT.saturating_sub(total) {
            return Err(Error::LimitExceeded);
        }
        fs::create_dir_all(
            path.parent()
                .ok_or_else(|| Error::Invalid("archive member has no folder".into()))?,
        )?;
        let mut out = File::options().write(true).create_new(true).open(&path)?;
        loop {
            cancellation.check()?;
            let n = member.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            total += n as u64;
            if total > BUILD_BYTES_LIMIT {
                return Err(Error::LimitExceeded);
            }
            out.write_all(&buffer[..n])?;
        }
        out.sync_all()?;
        filesystem::archive_permissions(&path, member.unix_mode())?;
        files.insert(relative.as_str().to_owned());
    }
    Ok(files)
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::{
        provisioning::{
            activity::ActivityStore,
            state::Activity,
            test_servers::{Reply, Request, TestCertificate, TlsServer, network_to, response},
            transfer::{RetryPolicy, SystemPacing},
        },
        value::Sha256Digest,
    };
    use std::{
        io::Cursor,
        sync::Mutex,
        time::{Duration, UNIX_EPOCH},
    };
    use zip::write::SimpleFileOptions;

    pub(crate) const DRIVER: &str = "1.64.0-beta-1791568591000";
    pub(crate) const BROWSER_VERSION: &str = "156.0.8078.4";
    const HOST: &str = "cdn.example.com";

    pub(crate) fn platform() -> Platform {
        Platform::current().expect("tests run on a supported platform")
    }

    /// A driver package as the bundled one lays it out, with its revisions.
    pub(crate) fn driver_package(folder: &Path) -> DriverManifest {
        fs::create_dir_all(folder).unwrap();
        let browsers = serde_json::json!({
            "comment": "Do not edit this file, use utils/roll_browser.js",
            "browsers": [
                {"name": "chromium", "revision": "1248", "installByDefault": true,
                 "browserVersion": BROWSER_VERSION, "title": "Chrome for Testing"},
                {"name": "chromium-headless-shell", "revision": "1248", "installByDefault": true,
                 "browserVersion": BROWSER_VERSION, "title": "Chrome Headless Shell"},
                {"name": "webkit", "revision": "2370", "installByDefault": true,
                 "revisionOverrides": {"mac14": "2251"}, "browserVersion": "27.2"},
                {"name": "ffmpeg", "revision": "1013", "installByDefault": true},
                {"name": "winldd", "revision": "1007", "installByDefault": false}
            ]
        });
        fs::write(folder.join("browsers.json"), browsers.to_string()).unwrap();
        fs::write(
            folder.join("package.json"),
            serde_json::json!({"name": "playwright-core", "version": DRIVER}).to_string(),
        )
        .unwrap();
        DriverManifest::read(folder).unwrap()
    }

    /// The builds this platform's pins name, as the vendor's installer lists them.
    fn families() -> Vec<(Family, &'static str)> {
        let mut families = vec![
            (Family::Chromium, "chromium-1248"),
            (Family::HeadlessShell, "chromium_headless_shell-1248"),
            (Family::Ffmpeg, "ffmpeg-1013"),
        ];
        if platform() == Platform::WinX64 {
            families.push((Family::Winldd, "winldd-1007"));
        }
        families
    }

    /// A small archive laid out like the vendor's: the executable at its platform path
    /// with the runnable mode, and a data file beside it.
    fn archive(executable: &str, tag: &str) -> Vec<u8> {
        let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
        let top = executable.split('/').next().unwrap();
        if executable.contains('/') {
            zip.add_directory(format!("{top}/"), SimpleFileOptions::default())
                .unwrap();
        }
        zip.start_file(
            executable,
            SimpleFileOptions::default().unix_permissions(0o755),
        )
        .unwrap();
        zip.write_all(format!("{tag} executable").as_bytes())
            .unwrap();
        let data = if executable.contains('/') {
            format!("{top}/resources.pak")
        } else {
            "LICENSE".to_owned()
        };
        zip.start_file(data, SimpleFileOptions::default().unix_permissions(0o644))
            .unwrap();
        zip.write_all(&[b'r'; 70_000]).unwrap();
        zip.finish().unwrap().into_inner()
    }

    /// A pin table for one archive per build of this platform, and the bytes served.
    pub(crate) struct Archives {
        pub table: String,
        pub served: BTreeMap<String, Vec<u8>>,
    }

    pub(crate) fn archives(tag: &str) -> Archives {
        let platform = platform();
        let mut table = format!("playwright_driver = \"{DRIVER}\"\nhosts = [\"{HOST}\"]\n");
        let mut served = BTreeMap::new();
        for (family, directory) in families() {
            let bytes = archive(family.executable(platform).unwrap(), tag);
            let path = format!("builds/{directory}/{}.zip", family.directory_prefix());
            table.push_str(&pin_entry(platform, directory, &path, &bytes));
            served.insert(format!("/{path}"), bytes);
        }
        Archives { table, served }
    }

    fn pin_entry(platform: Platform, directory: &str, path: &str, bytes: &[u8]) -> String {
        format!(
            "\n[[archives]]\nplatform = \"{}\"\ndirectory_name = \"{directory}\"\npath = \"{path}\"\nurls = [\"https://{HOST}/{path}\"]\ndownload_bytes = {}\nsha256 = \"{}\"\n",
            platform.as_str(),
            bytes.len(),
            Sha256Digest::of(bytes),
        )
    }

    /// Serves `served` by path, answering a `Range` request from its start byte.
    pub(crate) fn serve(served: BTreeMap<String, Vec<u8>>) -> (TestCertificate, TlsServer) {
        let certificate = TestCertificate::new(&[HOST]);
        let server = TlsServer::start(&certificate, move |request: &Request| {
            let Some(bytes) = served.get(request.target()) else {
                return Reply::Bytes(response(
                    "404 Not Found",
                    &[("Content-Length", "0".into())],
                    b"",
                ));
            };
            let start = request
                .header("range")
                .and_then(|range| range.strip_prefix("bytes="))
                .and_then(|range| range.strip_suffix('-'))
                .and_then(|start| start.parse::<usize>().ok())
                .unwrap_or(0);
            let status = if start > 0 { "206 Partial" } else { "200 OK" };
            Reply::Bytes(response(
                status,
                &[
                    ("Content-Length", (bytes.len() - start).to_string()),
                    (
                        "Content-Range",
                        format!("bytes {start}-{}/{}", bytes.len() - 1, bytes.len()),
                    ),
                ],
                &bytes[start..],
            ))
        });
        (certificate, server)
    }

    struct Fixture {
        directory: tempfile::TempDir,
        layout: BrowserLayout,
        activity: ActivityStore,
        receipts: ReceiptStore,
        certificate: TestCertificate,
        server: TlsServer,
        served: BTreeMap<String, Vec<u8>>,
    }

    fn fixture() -> Fixture {
        let directory = tempfile::tempdir().unwrap();
        let driver = driver_package(&directory.path().join("driver"));
        let Archives { table, served } = archives("pinned");
        let pins = BrowserArchivePins::parse(&table).unwrap();
        let layout = BrowserLayout::new(
            directory.path().join("components/playwright"),
            &driver,
            Some(&pins),
            platform(),
        )
        .unwrap();
        let (certificate, server) = serve(served.clone());
        Fixture {
            activity: ActivityStore::new(directory.path().join("components/activity")).unwrap(),
            receipts: ReceiptStore::new(directory.path().join("components/receipts")).unwrap(),
            directory,
            layout,
            certificate,
            server,
            served,
        }
    }

    /// Runs `act` with a transfer to `fixture`'s server, recording progress.
    fn with_transfer<T>(
        certificate: &TestCertificate,
        server: &TlsServer,
        progress: &Mutex<Vec<(u64, u64)>>,
        act: impl FnOnce(&mut Transfer<'_>) -> T,
    ) -> T {
        let network = network_to(certificate.roots(), server.address(), None);
        let hosts = [HostName::new(HOST).unwrap()].into();
        let mut pacing = SystemPacing::default();
        let cancellation = Cancellation::default();
        let mut events = |event| {
            if let TransferEvent::Progress { completed, total } = event {
                progress.lock().unwrap().push((completed, total));
            }
        };
        act(&mut Transfer {
            network: &network,
            hosts: &hosts,
            policy: RetryPolicy::default(),
            pacing: &mut pacing,
            events: &mut events,
            cancellation: &cancellation,
        })
    }

    impl Fixture {
        fn install(&self, progress: &Mutex<Vec<(u64, u64)>>) -> Result<Installed, Error> {
            with_transfer(&self.certificate, &self.server, progress, |transfer| {
                let writer = self.activity.begin(ItemId::Browser, SetupStep::Plan)?;
                let reading = self.receipts.read(ItemId::Browser);
                let installed = self.layout.install(transfer, &writer, &reading)?;
                writer.finished()?;
                Ok(installed)
            })
        }

        fn root(&self) -> &Path {
            self.layout.root()
        }

        fn settle(&self) -> Settled {
            let verified = self.layout.verify_installation().unwrap();
            self.layout
                .settle(
                    verified,
                    &self.receipts,
                    vec![HostName::new(HOST).unwrap()],
                    UNIX_EPOCH + Duration::from_secs(1_792_846_800),
                )
                .unwrap()
        }
    }

    fn mark_complete(folder: &Path) {
        fs::create_dir_all(folder).unwrap();
        fs::write(folder.join(COMPLETION_MARKER), b"").unwrap();
    }

    #[test]
    fn the_bundled_driver_reads_and_pins_cover_its_builds_only_for_its_version() {
        let directory = tempfile::tempdir().unwrap();
        let driver = driver_package(&directory.path().join("driver"));
        assert_eq!(driver.version, DRIVER);
        assert!(
            driver
                .builds
                .iter()
                .any(|build| build.name == "webkit" && build.overridden),
            "a per-host revision is kept as overridden, never guessed"
        );
        let pins = BrowserArchivePins::parse(&archives("pinned").table).unwrap();
        let root = directory.path().join("browsers");
        let layout = BrowserLayout::new(root.clone(), &driver, Some(&pins), platform()).unwrap();
        assert!(layout.pinned());
        assert_eq!(layout.version(), BROWSER_VERSION);
        assert_eq!(layout.driver_version(), DRIVER);
        assert_eq!(
            layout
                .builds()
                .iter()
                .map(|build| build.directory_name.as_str())
                .collect::<Vec<_>>(),
            families()
                .iter()
                .map(|(_, directory)| *directory)
                .collect::<Vec<_>>()
        );
        let chromium = &layout.builds()[0];
        assert_eq!(chromium.name(), "chromium");
        assert!(
            chromium
                .executable
                .as_str()
                .starts_with("chromium-1248/chrome-")
        );

        let mut other = driver.clone();
        other.version = "1.65.0".into();
        let unpinned = BrowserLayout::new(root.clone(), &other, Some(&pins), platform()).unwrap();
        assert!(!unpinned.pinned());
        assert_eq!(
            unpinned.builds().len(),
            2,
            "the two Chromium builds are still observed"
        );
        assert_eq!(
            unpinned.pending_download_bytes(&ReceiptReading::Absent),
            None
        );
        let mut rolled = driver.clone();
        rolled.builds[1].revision = "1249".into();
        assert!(
            !BrowserLayout::new(root.clone(), &rolled, Some(&pins), platform())
                .unwrap()
                .pinned(),
            "pins for another headless revision cover nothing"
        );
        assert!(
            !BrowserLayout::new(root, &driver, None, platform())
                .unwrap()
                .pinned()
        );
        assert!(matches!(
            DriverManifest::read(&directory.path().join("absent")),
            Err(Error::Io(error)) if error.kind() == std::io::ErrorKind::NotFound
        ));
        fs::write(
            directory.path().join("driver/browsers.json"),
            br#"{"browsers": [{"name": "chromium", "revision": "12a"}]}"#,
        )
        .unwrap();
        assert!(DriverManifest::read(&directory.path().join("driver")).is_err());
    }

    #[test]
    fn the_committed_pins_cover_the_bundled_drivers_builds_on_this_platform() {
        let checkout = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(Path::parent)
            .unwrap();
        let pins = crate::provisioning::pins::ComponentPins::load(
            &checkout.join("src/cadrumo/_data/dependencies"),
        )
        .unwrap()
        .browser
        .unwrap();
        let directory = tempfile::tempdir().unwrap();
        let mut driver = driver_package(&directory.path().join("driver"));
        driver.version = pins.playwright_driver.clone();
        let layout = BrowserLayout::new(
            directory.path().join("browsers"),
            &driver,
            Some(&pins),
            platform(),
        )
        .unwrap();
        assert!(layout.pinned());
        assert_eq!(
            layout.builds().len(),
            pins.for_platform(platform()).len(),
            "every archive the vendor installer fetches is installed"
        );
    }

    #[test]
    fn pending_archives_install_into_the_driver_layout_with_their_marker_and_resume() {
        let fixture = fixture();
        let root = fixture.root().to_path_buf();
        let builds = fixture.layout.builds().to_vec();
        let total: u64 = fixture
            .served
            .values()
            .map(|bytes| bytes.len() as u64)
            .sum();
        assert_eq!(fixture.layout.incomplete().len(), builds.len());
        assert_eq!(
            fixture
                .layout
                .pending_download_bytes(&ReceiptReading::Absent),
            Some(total)
        );
        // A half-extracted build without its marker, a partial download to resume, and a
        // partial of an archive no longer pending.
        fs::create_dir_all(root.join("chromium-1248/chrome-leftover")).unwrap();
        fs::write(root.join("chromium-1248/chrome-leftover/stale"), b"x").unwrap();
        let first = builds[0].pin.clone().unwrap();
        let first_bytes = &fixture.served[&format!("/{}", first.path)];
        let staging = root.join(STAGING);
        fs::create_dir_all(&staging).unwrap();
        fs::write(staging.join(part_name(&first)), &first_bytes[..100]).unwrap();
        fs::write(staging.join("0000.part"), b"old").unwrap();

        let progress = Mutex::new(Vec::new());
        let installed = fixture.install(&progress).unwrap();
        assert_eq!(
            installed.builds,
            builds
                .iter()
                .map(|build| build.directory_name.clone())
                .collect::<Vec<_>>()
        );
        assert_eq!(installed.transferred_bytes, total);
        let progress = progress.into_inner().unwrap();
        assert!(progress.iter().all(|&(_, of)| of == total));
        assert_eq!(progress.last(), Some(&(total, total)));
        assert!(progress.windows(2).all(|pair| pair[0].0 <= pair[1].0));
        assert_eq!(
            fixture.server.requests.lock().unwrap()[0].header("range"),
            Some("bytes=100-"),
            "the partial bytes are resumed"
        );
        for build in &builds {
            let folder = root.join(&build.directory_name);
            assert_eq!(fs::read(folder.join(COMPLETION_MARKER)).unwrap(), b"");
            assert_eq!(
                fs::read(build.executable.under(&root)).unwrap(),
                b"pinned executable"
            );
            filesystem::require_executable(&build.executable.under(&root)).unwrap();
        }
        assert!(!root.join("chromium-1248/chrome-leftover").exists());
        assert!(!staging.exists(), "nothing is left in staging");
        assert!(fixture.layout.incomplete().is_empty());
        assert_eq!(
            fixture.activity.activity(ItemId::Browser).unwrap(),
            Activity::Idle
        );
    }

    #[test]
    fn settling_records_the_location_and_only_then_removes_superseded_builds() {
        let fixture = fixture();
        let root = fixture.root().to_path_buf();
        for old in [
            "chromium-1200",
            "chromium_headless_shell-1200",
            "ffmpeg-1011",
        ] {
            mark_complete(&root.join(old));
        }
        mark_complete(&root.join("firefox-1555"));
        fixture.install(&Mutex::new(Vec::new())).unwrap();
        assert!(
            root.join("chromium-1200").exists(),
            "a superseded build stays until the new ones verified"
        );
        let settled = fixture.settle();
        assert_eq!(
            settled.removed,
            [
                "chromium-1200",
                "chromium_headless_shell-1200",
                "ffmpeg-1011"
            ]
        );
        assert_eq!(settled.left_in_place, 0);
        assert!(
            root.join("firefox-1555").exists(),
            "another family is not this item's to remove"
        );

        let reading = fixture.receipts.read(ItemId::Browser);
        let receipt = fixture
            .layout
            .receipt(&reading)
            .expect("this layout's receipt");
        assert_eq!(receipt.version.as_deref(), Some(BROWSER_VERSION));
        assert_eq!(receipt.verified_at, "2026-10-24T13:00:00Z");
        assert_eq!(receipt.hosts, [HostName::new(HOST).unwrap()]);
        let location = receipt.location.as_ref().unwrap();
        assert_eq!(location.root(), root);
        assert_eq!(location.facts[DRIVER_FACT], DRIVER);
        for build in fixture.layout.builds() {
            assert_eq!(location.paths[build.name()], build.executable);
            assert!(
                receipt
                    .files
                    .iter()
                    .any(|file| file.path == build.executable)
            );
        }
        assert!(fixture.layout.damaged(&reading).is_empty());
        assert_eq!(fixture.layout.pending_download_bytes(&reading), Some(0));

        // A changed file makes its build pending again, and only that build downloads.
        let chromium = fixture.layout.builds()[0].clone();
        fs::write(chromium.executable.under(&root), b"tampered").unwrap();
        assert_eq!(
            fixture.layout.damaged(&reading),
            BTreeSet::from([chromium.directory_name.clone()])
        );
        let requests = fixture.server.targets().len();
        let installed = fixture.install(&Mutex::new(Vec::new())).unwrap();
        assert_eq!(
            installed.builds,
            std::slice::from_ref(&chromium.directory_name)
        );
        assert_eq!(fixture.server.targets().len(), requests + 1);
        assert_eq!(
            fs::read(chromium.executable.under(&root)).unwrap(),
            b"pinned executable"
        );

        // A build whose marker is gone is incomplete to the driver, and so to the engine.
        fs::remove_file(root.join(&chromium.directory_name).join(COMPLETION_MARKER)).unwrap();
        assert_eq!(fixture.layout.incomplete().len(), 1);
        assert!(fixture.layout.verify_installation().is_err());
        let moved = BrowserLayout::new(
            fixture.directory.path().join("elsewhere"),
            &driver_package(&fixture.directory.path().join("driver")),
            None,
            platform(),
        )
        .unwrap();
        assert!(
            moved.receipt(&reading).is_none(),
            "a receipt for another root describes other builds"
        );
    }

    fn zip_of(build: impl FnOnce(&mut zip::ZipWriter<Cursor<Vec<u8>>>)) -> Vec<u8> {
        let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
        build(&mut zip);
        zip.finish().unwrap().into_inner()
    }

    #[test]
    fn archives_with_links_escapes_or_no_executable_never_become_builds() {
        let platform = platform();
        let executable = Family::Chromium.executable(platform).unwrap();
        let plain = SimpleFileOptions::default;
        let cases = [
            (
                "link",
                zip_of(|zip| {
                    zip.add_symlink("chrome-link", "../../outside", plain())
                        .unwrap();
                    zip.start_file(executable, plain().unix_permissions(0o755))
                        .unwrap();
                    zip.write_all(b"x").unwrap();
                }),
            ),
            (
                "escape",
                zip_of(|zip| {
                    zip.start_file("../escaped", plain()).unwrap();
                    zip.write_all(b"x").unwrap();
                }),
            ),
            (
                "casing",
                zip_of(|zip| {
                    zip.start_file("Data/a", plain()).unwrap();
                    zip.start_file("data/b", plain()).unwrap();
                }),
            ),
            (
                "no executable",
                zip_of(|zip| {
                    zip.start_file("README", plain()).unwrap();
                }),
            ),
        ];
        for (case, bytes) in cases {
            let directory = tempfile::tempdir().unwrap();
            let driver = driver_package(&directory.path().join("driver"));
            let path = "builds/chromium-1248/chromium.zip";
            let headless = b"headless".to_vec();
            let table = format!(
                "playwright_driver = \"{DRIVER}\"\nhosts = [\"{HOST}\"]\n{}{}",
                pin_entry(platform, "chromium-1248", path, &bytes),
                pin_entry(
                    platform,
                    "chromium_headless_shell-1248",
                    "builds/headless/headless.zip",
                    &headless
                ),
            );
            let pins = BrowserArchivePins::parse(&table).unwrap();
            let layout = BrowserLayout::new(
                directory.path().join("components/playwright"),
                &driver,
                Some(&pins),
                platform,
            )
            .unwrap();
            let (certificate, server) = serve(
                [
                    (format!("/{path}"), bytes),
                    ("/builds/headless/headless.zip".into(), headless),
                ]
                .into(),
            );
            let activity = ActivityStore::new(directory.path().join("activity")).unwrap();
            let writer = activity.begin(ItemId::Browser, SetupStep::Plan).unwrap();
            let failure = with_transfer(&certificate, &server, &Mutex::default(), |transfer| {
                layout
                    .install(transfer, &writer, &ReceiptReading::Absent)
                    .unwrap_err()
            });
            let expected = if case == "no executable" {
                FailureCategory::DamagedDownload
            } else {
                FailureCategory::Unexpected
            };
            assert_eq!(failure_category(&failure), expected, "{case}: {failure}");
            assert!(
                !layout.root().join("chromium-1248").exists(),
                "{case}: a refused archive leaves no build folder"
            );
            assert!(!directory.path().join("outside").exists(), "{case}");
            assert!(
                !directory.path().join("components/escaped").exists(),
                "{case}"
            );
        }
    }

    #[test]
    fn a_build_this_copy_cannot_authenticate_is_never_downloaded() {
        let fixture = fixture();
        let unpinned = BrowserLayout::new(
            fixture.root().to_path_buf(),
            &driver_package(&fixture.directory.path().join("driver")),
            None,
            platform(),
        )
        .unwrap();
        let progress = Mutex::default();
        with_transfer(
            &fixture.certificate,
            &fixture.server,
            &progress,
            |transfer| {
                let writer = fixture
                    .activity
                    .begin(ItemId::Browser, SetupStep::Plan)
                    .unwrap();
                let refused = unpinned
                    .install(transfer, &writer, &ReceiptReading::Absent)
                    .unwrap_err();
                assert_eq!(failure_category(&refused), FailureCategory::NotInThisBuild);
                drop(writer);
                let other = fixture
                    .activity
                    .begin(ItemId::LocalAi, SetupStep::Plan)
                    .unwrap();
                assert!(matches!(
                    fixture
                        .layout
                        .install(transfer, &other, &ReceiptReading::Absent),
                    Err(Error::Invalid(_))
                ));
            },
        );
        assert!(fixture.server.targets().is_empty());
    }

    #[test]
    fn setup_failures_map_to_their_closed_categories() {
        for (error, category) in [
            (Error::Cancelled, FailureCategory::Cancelled),
            (
                Error::Integrity("changed".into()),
                FailureCategory::DamagedDownload,
            ),
            (Error::LimitExceeded, FailureCategory::DamagedDownload),
            (
                Error::Io(std::io::Error::from(std::io::ErrorKind::PermissionDenied)),
                FailureCategory::NoPermission,
            ),
            (
                Error::Io(std::io::Error::from(std::io::ErrorKind::StorageFull)),
                FailureCategory::DiskFull,
            ),
            (
                Error::Download(TransferFailure::final_(FailureCategory::BlockedByNetwork)),
                FailureCategory::BlockedByNetwork,
            ),
            (Error::Busy, FailureCategory::Unexpected),
        ] {
            assert_eq!(failure_category(&error), category, "{error}");
        }
    }

    #[test]
    fn the_browsers_folder_setting_is_a_declared_location_with_the_default_layout() {
        let native = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let declared: toml::Table = toml::from_str(
            &fs::read_to_string(native.join("application-environment.toml")).unwrap(),
        )
        .unwrap();
        assert_eq!(
            declared["names"][BROWSERS_DIR_VARIABLE]["role"].as_str(),
            Some("location")
        );
        let root = std::env::temp_dir();
        assert_eq!(
            crate::provisioning::items::Locations::under(&root).browsers,
            root.join("components").join("playwright")
        );
        assert_eq!(BROWSERS_DEFAULT, "components/playwright");
    }

    #[cfg(feature = "platform")]
    #[test]
    fn the_browsers_folder_follows_the_package_member_rule() {
        let root = std::env::temp_dir().join("cadrumo-browsers-root");
        let none = |_: &str| None;
        assert_eq!(
            browsers_root(&root, &none).unwrap(),
            crate::provisioning::items::Locations::under(&root).browsers
        );
        let absolute = std::env::temp_dir().join("elsewhere");
        let moved = absolute.clone();
        let set = move |name: &str| {
            (name == BROWSERS_DIR_VARIABLE).then(|| moved.clone().into_os_string())
        };
        assert_eq!(browsers_root(&root, &set).unwrap(), absolute);
        let relative =
            |name: &str| (name == BROWSERS_DIR_VARIABLE).then(|| "shared/browsers".into());
        assert_eq!(
            browsers_root(&root, &relative).unwrap(),
            root.join("shared").join("browsers")
        );
    }
}
