//! The component pins: declarative package data that names the only bytes the engine accepts.
//!
//! Three tables sit together in the product package's `cadrumo/_data/dependencies`
//! folder, which the package layout names `component_pins`. Python reads the same files:
//! the model table supplies the catalogue's role defaults, weights and memory floors.
//!
//! - `browser_archives.toml`: every archive the bundled Playwright driver's Chromium builds
//!   need, per platform, with its build directory, sources, size and SHA-256.
//! - `local_ai_program.toml`: the local AI program's official standalone archive per
//!   platform, with its format, executable, size and SHA-256.
//! - `local_ai_models.toml`: the model each role reads with, and every pinned model's
//!   manifest digest, size, memory floor and licence.
//!
//! A table this build does not carry reads as `None`: the item it pins is not in this
//! build. A table that is present but malformed is refused rather than read partly.

use super::url::HttpsUrl;
use crate::{
    error::Error,
    filesystem,
    value::{HostName, RelativePath, Sha256Digest},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
};

pub const BROWSER_ARCHIVES: &str = "browser_archives.toml";
pub const LOCAL_AI_PROGRAM: &str = "local_ai_program.toml";
pub const LOCAL_AI_MODELS: &str = "local_ai_models.toml";

const TABLE_BYTES_LIMIT: u64 = 1024 * 1024;

/// The platform keys pins are written for; each names one archive family.
#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub enum Platform {
    #[serde(rename = "win-x64")]
    WinX64,
    #[serde(rename = "linux-x64")]
    LinuxX64,
    #[serde(rename = "linux-arm64")]
    LinuxArm64,
    #[serde(rename = "mac-x64")]
    MacX64,
    #[serde(rename = "mac-arm64")]
    MacArm64,
}

impl Platform {
    /// The platform this build runs on, or `None` where no pins can apply.
    pub fn current() -> Option<Self> {
        match (std::env::consts::OS, std::env::consts::ARCH) {
            ("windows", "x86_64") => Some(Self::WinX64),
            ("linux", "x86_64") => Some(Self::LinuxX64),
            ("linux", "aarch64") => Some(Self::LinuxArm64),
            ("macos", "x86_64") => Some(Self::MacX64),
            ("macos", "aarch64") => Some(Self::MacArm64),
            _ => None,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::WinX64 => "win-x64",
            Self::LinuxX64 => "linux-x64",
            Self::LinuxArm64 => "linux-arm64",
            Self::MacX64 => "mac-x64",
            Self::MacArm64 => "mac-arm64",
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq)]
#[serde(deny_unknown_fields)]
struct RawBrowserArchive {
    platform: Platform,
    directory_name: String,
    path: String,
    urls: Vec<String>,
    download_bytes: u64,
    sha256: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawBrowserTable {
    playwright_driver: String,
    hosts: Vec<HostName>,
    archives: Vec<RawBrowserArchive>,
}

/// One browser archive on one platform and the exact bytes it must be.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrowserArchivePin {
    pub platform: Platform,
    /// The build directory under the browsers root this archive extracts into.
    pub directory_name: String,
    /// The archive's path under the vendor's download host.
    pub path: String,
    /// The vendor's sources, in the order they are tried.
    pub urls: Vec<HttpsUrl>,
    pub download_bytes: u64,
    pub sha256: Sha256Digest,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrowserArchivePins {
    pub playwright_driver: String,
    /// The declared browser hosts, the only ones a download may pass through.
    pub hosts: BTreeSet<HostName>,
    pub archives: Vec<BrowserArchivePin>,
}

impl BrowserArchivePins {
    pub fn parse(text: &str) -> Result<Self, Error> {
        let raw: RawBrowserTable = parse_table(text)?;
        let hosts = unique_hosts(raw.hosts)?;
        if raw.playwright_driver.is_empty() || raw.playwright_driver.len() > 128 {
            return Err(invalid("browser driver version"));
        }
        let mut builds = BTreeSet::new();
        let mut paths = BTreeSet::new();
        let mut archives = Vec::with_capacity(raw.archives.len());
        for archive in raw.archives {
            if !build_directory(&archive.directory_name)
                || !archive_path(&archive.path)
                || archive.urls.is_empty()
                || archive.download_bytes == 0
                || !builds.insert((archive.platform, archive.directory_name.clone()))
                || !paths.insert((archive.platform, archive.path.clone()))
            {
                return Err(invalid("browser archive"));
            }
            let mut urls = Vec::with_capacity(archive.urls.len());
            for url in &archive.urls {
                let parsed = HttpsUrl::parse(url)?;
                if !url.starts_with("https://")
                    || !url.ends_with(&format!("/{}", archive.path))
                    || !hosts.contains(parsed.host())
                    || urls.contains(&parsed)
                {
                    return Err(invalid("browser archive source"));
                }
                urls.push(parsed);
            }
            archives.push(BrowserArchivePin {
                platform: archive.platform,
                directory_name: archive.directory_name,
                path: archive.path,
                urls,
                download_bytes: archive.download_bytes,
                sha256: lowercase_digest(&archive.sha256)?,
            });
        }
        if archives.is_empty() {
            return Err(invalid("browser table pins no archive"));
        }
        Ok(Self {
            playwright_driver: raw.playwright_driver,
            hosts,
            archives,
        })
    }

    /// The archives pinned for `platform`, in table order; empty when none are.
    pub fn for_platform(&self, platform: Platform) -> Vec<&BrowserArchivePin> {
        self.archives
            .iter()
            .filter(|pin| pin.platform == platform)
            .collect()
    }

    /// `platform`'s archives when they belong to `driver` and cover every named build;
    /// `None` when this build cannot authenticate what the installed driver needs.
    pub fn covering(
        &self,
        platform: Platform,
        driver: &str,
        directories: &[&str],
    ) -> Option<Vec<&BrowserArchivePin>> {
        if driver != self.playwright_driver {
            return None;
        }
        let pins = self.for_platform(platform);
        let pinned: BTreeSet<&str> = pins.iter().map(|pin| pin.directory_name.as_str()).collect();
        (!pins.is_empty() && directories.iter().all(|name| pinned.contains(name))).then_some(pins)
    }
}

/// How a program archive is packed.
#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub enum ArchiveFormat {
    #[default]
    #[serde(rename = "zip")]
    Zip,
    #[serde(rename = "tar.gz")]
    TarGz,
    #[serde(rename = "tar.zst")]
    TarZst,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawProgramArchive {
    platform: Platform,
    url: String,
    format: ArchiveFormat,
    executable: RelativePath,
    download_bytes: u64,
    sha256: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawProgramTable {
    program: String,
    version: String,
    hosts: Vec<HostName>,
    archives: Vec<RawProgramArchive>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProgramArchivePin {
    pub platform: Platform,
    pub url: HttpsUrl,
    pub format: ArchiveFormat,
    pub executable: RelativePath,
    pub download_bytes: u64,
    pub sha256: Sha256Digest,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ProgramPins {
    pub program: String,
    pub version: String,
    pub hosts: BTreeSet<HostName>,
    pub archives: Vec<ProgramArchivePin>,
}

impl ProgramPins {
    pub fn parse(text: &str) -> Result<Self, Error> {
        let raw: RawProgramTable = parse_table(text)?;
        let hosts = unique_hosts(raw.hosts)?;
        let numeric = raw.version.split('.').collect::<Vec<_>>();
        if raw.program != "ollama"
            || numeric.len() != 3
            || numeric
                .iter()
                .any(|part| part.is_empty() || !part.bytes().all(|c| c.is_ascii_digit()))
        {
            return Err(invalid("program identity"));
        }
        let mut platforms = BTreeSet::new();
        let mut archives = Vec::with_capacity(raw.archives.len());
        for archive in raw.archives {
            let url = HttpsUrl::parse(&archive.url)?;
            if !platforms.insert(archive.platform)
                || archive.download_bytes == 0
                || !hosts.contains(url.host())
                || !url.default_port()
            {
                return Err(invalid("program archive"));
            }
            archives.push(ProgramArchivePin {
                platform: archive.platform,
                url,
                format: archive.format,
                executable: archive.executable,
                download_bytes: archive.download_bytes,
                sha256: lowercase_digest(&archive.sha256)?,
            });
        }
        if archives.is_empty() {
            return Err(invalid("program table pins no archive"));
        }
        Ok(Self {
            program: raw.program,
            version: raw.version,
            hosts,
            archives,
        })
    }

    pub fn for_platform(&self, platform: Platform) -> Option<&ProgramArchivePin> {
        self.archives.iter().find(|pin| pin.platform == platform)
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawModel {
    name: String,
    manifest_digest: String,
    download_bytes: u64,
    memory_bytes: u64,
    licence: String,
    commercial_use_permitted: bool,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct RawModelTable {
    hosts: Vec<HostName>,
    roles: BTreeMap<String, String>,
    models: Vec<RawModel>,
}

/// One model's tested manifest digest, download size, memory floor and licence.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ModelPin {
    pub name: String,
    pub manifest_digest: Sha256Digest,
    pub download_bytes: u64,
    /// The publisher's stated weight size: the requirement before any safety margin.
    pub memory_bytes: u64,
    pub licence: String,
    pub commercial_use_permitted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ModelPins {
    pub hosts: BTreeSet<HostName>,
    /// Role name to model name, in role order.
    pub roles: BTreeMap<String, String>,
    pub models: Vec<ModelPin>,
}

impl ModelPins {
    pub fn parse(text: &str) -> Result<Self, Error> {
        let raw: RawModelTable = parse_table(text)?;
        let hosts = unique_hosts(raw.hosts)?;
        let mut names = BTreeSet::new();
        let mut models = Vec::with_capacity(raw.models.len());
        for model in raw.models {
            if !model_name(&model.name)
                || model.download_bytes == 0
                || model.memory_bytes == 0
                || model.licence.is_empty()
                || model.licence.len() > 128
                || !names.insert(model.name.clone())
            {
                return Err(invalid("model pin"));
            }
            models.push(ModelPin {
                name: model.name,
                manifest_digest: lowercase_digest(&model.manifest_digest)?,
                download_bytes: model.download_bytes,
                memory_bytes: model.memory_bytes,
                licence: model.licence,
                commercial_use_permitted: model.commercial_use_permitted,
            });
        }
        if models.is_empty()
            || raw.roles.is_empty()
            || raw
                .roles
                .iter()
                .any(|(role, model)| !identifier(role) || role.len() > 64 || !names.contains(model))
        {
            return Err(invalid("model roles"));
        }
        Ok(Self {
            hosts,
            roles: raw.roles,
            models,
        })
    }

    pub fn model(&self, name: &str) -> Option<&ModelPin> {
        self.models.iter().find(|pin| pin.name == name)
    }
}

/// Every table this build carries, read from the package's pin folder.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ComponentPins {
    pub browser: Option<BrowserArchivePins>,
    pub program: Option<ProgramPins>,
    pub models: Option<ModelPins>,
}

impl ComponentPins {
    /// Reads the tables under `directory`, an owner-resolved absolute path. A missing table
    /// reads as `None`; a present table that cannot be read or validated is an error.
    pub fn load(directory: &Path) -> Result<Self, Error> {
        filesystem::absolute_root(directory)?;
        Ok(Self {
            browser: read_optional(&directory.join(BROWSER_ARCHIVES), BrowserArchivePins::parse)?,
            program: read_optional(&directory.join(LOCAL_AI_PROGRAM), ProgramPins::parse)?,
            models: read_optional(&directory.join(LOCAL_AI_MODELS), ModelPins::parse)?,
        })
    }
}

fn read_optional<T>(path: &Path, parse: fn(&str) -> Result<T, Error>) -> Result<Option<T>, Error> {
    let bytes = match filesystem::bounded_bytes(path, TABLE_BYTES_LIMIT) {
        Ok(bytes) => bytes,
        Err(Error::Io(error)) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let text = std::str::from_utf8(&bytes).map_err(|_| invalid("pin table encoding"))?;
    parse(text).map(Some)
}

fn parse_table<T: serde::de::DeserializeOwned>(text: &str) -> Result<T, Error> {
    toml::from_str(text).map_err(|_| invalid("pin table"))
}

fn invalid(what: &str) -> Error {
    Error::Invalid(format!("component pins: {what}"))
}

fn unique_hosts(hosts: Vec<HostName>) -> Result<BTreeSet<HostName>, Error> {
    let count = hosts.len();
    let set: BTreeSet<HostName> = hosts.into_iter().collect();
    if set.is_empty() || set.len() != count {
        return Err(invalid("hosts"));
    }
    Ok(set)
}

fn lowercase_digest(value: &str) -> Result<Sha256Digest, Error> {
    if value.bytes().any(|c| c.is_ascii_uppercase()) {
        return Err(invalid("digest"));
    }
    Sha256Digest::new(value)
}

fn identifier(value: &str) -> bool {
    let mut bytes = value.bytes();
    bytes.next().is_some_and(|c| c.is_ascii_lowercase())
        && bytes.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'_')
}

fn build_directory(value: &str) -> bool {
    match value.rsplit_once('-') {
        Some((name, revision)) => {
            value.len() <= 96
                && identifier(name)
                && !revision.is_empty()
                && revision.bytes().all(|c| c.is_ascii_digit())
        }
        None => false,
    }
}

fn archive_path(value: &str) -> bool {
    value.len() <= 512
        && value.ends_with(".zip")
        && value.starts_with("builds/")
        && value.split('/').skip(1).all(|part| {
            part.bytes()
                .next()
                .is_some_and(|c| c.is_ascii_alphanumeric())
                && part
                    .bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"._-".contains(&c))
        })
        && value.split('/').count() > 1
}

fn model_name(value: &str) -> bool {
    let part = |text: &str| {
        text.bytes()
            .next()
            .is_some_and(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
            && text
                .bytes()
                .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || b"._-".contains(&c))
    };
    value.len() <= 128
        && value
            .split_once(':')
            .is_some_and(|(name, tag)| part(name) && part(tag))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn committed() -> PathBuf {
        let checkout = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(Path::parent)
            .unwrap();
        checkout.join("src/cadrumo/_data/dependencies")
    }

    fn committed_text(name: &str) -> String {
        std::fs::read_to_string(committed().join(name)).unwrap()
    }

    #[test]
    fn the_committed_tables_load_and_pin_every_supported_platform() {
        let pins = ComponentPins::load(&committed()).unwrap();
        let browser = pins.browser.unwrap();
        let program = pins.program.unwrap();
        let models = pins.models.unwrap();
        for platform in [
            Platform::WinX64,
            Platform::LinuxX64,
            Platform::LinuxArm64,
            Platform::MacX64,
            Platform::MacArm64,
        ] {
            assert!(!browser.for_platform(platform).is_empty(), "{platform:?}");
            let archive = program.for_platform(platform).unwrap();
            assert!(program.hosts.contains(archive.url.host()));
        }
        assert!(
            browser
                .hosts
                .contains(&HostName::new("cdn.playwright.dev").unwrap())
        );
        assert_eq!(
            models.roles.keys().map(String::as_str).collect::<Vec<_>>(),
            [
                "column_role_mapping",
                "supply_nature_proposal",
                "text_extraction",
                "vision_transcription"
            ]
        );
        for model in models.roles.values() {
            assert!(models.model(model).unwrap().commercial_use_permitted);
        }
    }

    #[test]
    fn a_missing_table_reads_as_not_in_this_build() {
        let directory = tempfile::tempdir().unwrap();
        let pins = ComponentPins::load(directory.path()).unwrap();
        assert_eq!(
            pins,
            ComponentPins {
                browser: None,
                program: None,
                models: None
            }
        );
        assert!(ComponentPins::load(Path::new("relative")).is_err());
    }

    #[test]
    fn a_present_but_damaged_table_is_refused_rather_than_read_partly() {
        let directory = tempfile::tempdir().unwrap();
        std::fs::write(directory.path().join(LOCAL_AI_MODELS), "hosts = [").unwrap();
        assert!(ComponentPins::load(directory.path()).is_err());
    }

    #[test]
    fn browser_pins_cover_an_install_only_for_their_driver_and_every_build() {
        let browser = BrowserArchivePins::parse(&committed_text(BROWSER_ARCHIVES)).unwrap();
        let builds: Vec<&str> = browser
            .for_platform(Platform::WinX64)
            .iter()
            .map(|pin| pin.directory_name.as_str())
            .collect();
        let driver = browser.playwright_driver.clone();
        assert!(
            browser
                .covering(Platform::WinX64, &driver, &builds)
                .is_some()
        );
        assert!(
            browser
                .covering(Platform::WinX64, "0.0.0", &builds)
                .is_none()
        );
        assert!(
            browser
                .covering(Platform::WinX64, &driver, &["chromium-1"])
                .is_none()
        );
    }

    fn mutated(name: &str, old: &str, new: &str) -> String {
        let text = committed_text(name);
        assert!(text.contains(old), "{old}");
        text.replacen(old, new, 1)
    }

    #[test]
    fn a_table_that_could_admit_other_bytes_or_sources_is_refused() {
        let browser = [
            ("sha256 = \"", "sha256 = \"AB"),
            ("download_bytes = 199750508", "download_bytes = 0"),
            (
                "\"https://cdn.playwright.dev/",
                "\"http://cdn.playwright.dev/",
            ),
            ("path = \"builds/", "path = \"builds/../"),
            ("platform = \"linux-arm64\"", "platform = \"win-arm64\""),
            ("hosts = [\n", "hosts = [\n  \"cdn.playwright.dev\",\n"),
            (
                "\"https://cdn.playwright.dev/",
                "\"https://mirror.example.com/",
            ),
            (
                "playwright_driver = ",
                "unexpected = 1\nplaywright_driver = ",
            ),
        ];
        for (old, new) in browser {
            assert!(
                BrowserArchivePins::parse(&mutated(BROWSER_ARCHIVES, old, new)).is_err(),
                "{new}"
            );
        }
        let program = [
            ("sha256 = \"", "sha256 = \"0"),
            ("format = \"zip\"", "format = \"rar\""),
            (
                "executable = \"ollama.exe\"",
                "executable = \"../ollama.exe\"",
            ),
            ("\"https://github.com/", "\"https://mirror.example.com/"),
            (
                "https://github.com/ollama",
                "https://github.com:8443/ollama",
            ),
            ("program = \"ollama\"", "program = \"other\""),
            ("platform = \"mac-x64\"", "platform = \"mac-arm64\""),
        ];
        for (old, new) in program {
            assert!(
                ProgramPins::parse(&mutated(LOCAL_AI_PROGRAM, old, new)).is_err(),
                "{new}"
            );
        }
        let models = [
            ("manifest_digest = \"", "manifest_digest = \"AB"),
            (
                "vision_transcription = \"qwen3-vl:2b\"",
                "vision_transcription = \"llama3:8b\"",
            ),
            ("name = \"moondream:1.8b\"", "name = \"qwen3:1.7b\""),
            ("memory_bytes = 1700000000", "memory_bytes = 0"),
            ("name = \"moondream:1.8b\"", "name = \"Moondream\""),
        ];
        for (old, new) in models {
            assert!(
                ModelPins::parse(&mutated(LOCAL_AI_MODELS, old, new)).is_err(),
                "{new}"
            );
        }
    }
}
