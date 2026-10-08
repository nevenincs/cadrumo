//! Installed registration observations never resolve shortcuts or repair resources.
#![allow(unsafe_code)]
use crate::{
    admission::{Refusal, Scope},
    custody::{self, FileCustody},
};
use cadrumo_application::{
    installation::maintenance::{NativeContext, NativeOwner},
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Description {
    pub schema: u32,
    pub application_id: String,
    pub version: String,
    pub scope: Scope,
    pub files: BTreeMap<String, Sha256Digest>,
    pub components: Vec<String>,
    pub registry: Vec<Registry>,
    pub shortcuts: Vec<Shortcut>,
    pub absent_registry: Vec<AbsentRegistry>,
    pub absent_shortcuts: Vec<String>,
}
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AbsentRegistry {
    key: String,
    name: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Registry {
    component: String,
    key: String,
    name: String,
    #[serde(rename = "type")]
    kind: String,
    value: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Shortcut {
    component: String,
    path: String,
    target: String,
    arguments: String,
    working_directory: String,
    app_id: String,
}
impl Description {
    pub fn parse(value: &str) -> Result<Self, Refusal> {
        if value.len() > 32 * 1024 {
            return Err(Refusal::InvalidRequest);
        }
        let description: Self = serde_json::from_str(value).map_err(|_| Refusal::InvalidRequest)?;
        if description.schema != 1
            || description.files.len() != 4
            || description.components.len() > 16
            || description.components.is_empty()
            || description.registry.len() > 16
            || description.registry.is_empty()
            || description.shortcuts.len() > 1
            || description.absent_registry.len() > 2
            || description.absent_shortcuts.len() > 1
        {
            return Err(Refusal::InvalidRequest);
        }
        for path in description
            .files
            .keys()
            .chain(description.shortcuts.iter().map(|s| &s.path))
            .chain(description.absent_shortcuts.iter())
        {
            RelativePath::new(path).map_err(|_| Refusal::InvalidRequest)?;
        }
        let mut components = std::collections::BTreeSet::new();
        for component in &description.components {
            if !components.insert(crate::admission::canonical_guid(component)?) {
                return Err(Refusal::InvalidRequest);
            }
        }
        for resource in &description.registry {
            if !description.components.contains(&resource.component)
                || !matches!(resource.kind.as_str(), "string" | "integer")
                || !valid_registry_address(&resource.key, &resource.name)
            {
                return Err(Refusal::InvalidRequest);
            }
        }
        for resource in &description.absent_registry {
            if !valid_registry_address(&resource.key, &resource.name) {
                return Err(Refusal::InvalidRequest);
            }
        }
        for shortcut in &description.shortcuts {
            if !description.components.contains(&shortcut.component)
                || shortcut.app_id != description.application_id
            {
                return Err(Refusal::InvalidRequest);
            }
        }
        Ok(description)
    }

    /// Retain all file/shortcut handles until the caller has rechecked publication.
    pub fn verify(&self, owner: &NativeOwner) -> Result<Vec<FileCustody>, Refusal> {
        if !matches!(
            (self.scope, owner.context()),
            (Scope::Machine, NativeContext::Machine) | (Scope::User, NativeContext::User { .. })
        ) {
            return Err(Refusal::InvalidRequest);
        }
        let mut observation = Native::new(owner)?;
        for component in &self.components {
            observation.component(component)?;
        }
        let mut held = self.verify_files(owner)?;
        for expected in &self.registry {
            observation.registry(expected)?;
        }
        for expected in &self.shortcuts {
            held.push(observation.shortcut(expected)?);
        }
        for expected in &self.absent_registry {
            observation.absent_registry(expected)?;
        }
        for expected in &self.absent_shortcuts {
            let path = RelativePath::new(expected)
                .map_err(|_| Refusal::InvalidRequest)?
                .under(&observation.programs()?);
            match std::fs::symlink_metadata(path) {
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                _ => return Err(Refusal::IncompleteInventory),
            }
        }
        Ok(held)
    }

    pub(crate) fn verify_files(&self, owner: &NativeOwner) -> Result<Vec<FileCustody>, Refusal> {
        let mut held = Vec::new();
        for (member, expected) in &self.files {
            let path = RelativePath::new(member)
                .map_err(|_| Refusal::InvalidRequest)?
                .under(owner.prefix());
            let mut file = custody::file(&path)?;
            if &file_digest(&mut file.file)? != expected {
                return Err(Refusal::IncompleteInventory);
            }
            held.push(file);
        }
        Ok(held)
    }
}

fn valid_registry_address(key: &str, name: &str) -> bool {
    key.starts_with("Software\\")
        && !key.contains(['\0', '\r', '\n'])
        && !name.contains(['\0', '\r', '\n'])
        && !name.is_empty()
        && key.len() <= 2048
        && name.len() <= 256
}

pub(crate) fn file_digest(file: &mut std::fs::File) -> Result<Sha256Digest, Refusal> {
    let mut hash = Sha256::new();
    let mut bytes = [0u8; 65536];
    loop {
        let count = file
            .read(&mut bytes)
            .map_err(|_| Refusal::IncompleteInventory)?;
        if count == 0 {
            break;
        }
        hash.update(&bytes[..count]);
    }
    Sha256Digest::new(format!("{:x}", hash.finalize())).map_err(|_| Refusal::InvalidRequest)
}

fn wide(value: &str) -> Result<Vec<u16>, Refusal> {
    if value.contains('\0') || value.len() > 32767 {
        return Err(Refusal::InvalidRequest);
    }
    Ok(value.encode_utf16().chain([0]).collect())
}
fn expand(value: &str, prefix: &Path) -> Result<String, Refusal> {
    let prefix = prefix.to_str().ok_or(Refusal::InvalidRequest)?;
    let result = value.replace(
        "[INSTALL_ROOT]",
        &format!("{}\\", prefix.trim_end_matches('\\')),
    );
    if result.contains(['[', ']', '\0']) {
        return Err(Refusal::InvalidRequest);
    }
    Ok(result)
}

struct Native<'a> {
    owner: &'a NativeOwner,
    com: bool,
}
impl<'a> Native<'a> {
    fn new(owner: &'a NativeOwner) -> Result<Self, Refusal> {
        use windows::Win32::System::Com::{COINIT_APARTMENTTHREADED, CoInitializeEx};
        // SAFETY: This synchronous verifier owns its apartment initialization balance.
        unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) }
            .ok()
            .map_err(|_| Refusal::NativeFailure)?;
        Ok(Self { owner, com: true })
    }
    fn component(&self, component: &str) -> Result<(), Refusal> {
        #[link(name = "msi")]
        unsafe extern "system" {
            fn MsiQueryComponentStateW(
                product: *const u16,
                user: *const u16,
                context: u32,
                component: *const u16,
                state: *mut i32,
            ) -> u32;
        }
        let product = wide(&format!("{{{}}}", self.owner.product_code()))?;
        let component = wide(&format!(
            "{{{}}}",
            crate::admission::canonical_guid(component)?
        ))?;
        let sid = match self.owner.context() {
            NativeContext::Machine => None,
            NativeContext::User { sid } => Some(wide(sid)?),
        };
        let contexts: &[u32] = if sid.is_none() { &[4] } else { &[1, 2] };
        let mut found = 0;
        for context in contexts {
            let mut state = 0;
            // SAFETY: All strings and the bounded state output remain live.
            let status = unsafe {
                MsiQueryComponentStateW(
                    product.as_ptr(),
                    sid.as_ref().map_or(std::ptr::null(), |s| s.as_ptr()),
                    *context,
                    component.as_ptr(),
                    &mut state,
                )
            };
            if status == 1605 {
                continue;
            }
            if status != 0 || state != 3 {
                return Err(Refusal::IncompleteInventory);
            }
            found += 1;
        }
        if found != 1 {
            return Err(Refusal::IncompleteInventory);
        }
        Ok(())
    }
    fn registry(&self, expected: &Registry) -> Result<(), Refusal> {
        use windows::Win32::System::Registry::{
            HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, RRF_RT_REG_DWORD, RRF_RT_REG_SZ,
            RRF_SUBKEY_WOW6464KEY, RegGetValueW,
        };
        use windows::core::PCWSTR;
        let hive = match self.owner.context() {
            NativeContext::Machine => HKEY_LOCAL_MACHINE,
            NativeContext::User { .. } => HKEY_CURRENT_USER,
        };
        let key = wide(&expected.key)?;
        let name = wide(&expected.name)?;
        let text = expand(&expected.value, self.owner.prefix())?;
        let desired = if expected.kind == "integer" {
            text.parse::<u32>()
                .map_err(|_| Refusal::InvalidRequest)?
                .to_le_bytes()
                .to_vec()
        } else {
            wide(&text)?
                .into_iter()
                .flat_map(u16::to_le_bytes)
                .collect()
        };
        let mut bytes = vec![0u8; 65536];
        let mut size = bytes.len() as u32;
        let flags = if expected.kind == "integer" {
            RRF_RT_REG_DWORD
        } else {
            RRF_RT_REG_SZ
        } | RRF_SUBKEY_WOW6464KEY;
        // SAFETY: Native function receives bounded writable storage and terminated names.
        unsafe {
            RegGetValueW(
                hive,
                PCWSTR(key.as_ptr()),
                PCWSTR(name.as_ptr()),
                flags,
                None,
                Some(bytes.as_mut_ptr().cast()),
                Some(&mut size),
            )
        }
        .ok()
        .map_err(|_| Refusal::IncompleteInventory)?;
        if size as usize > bytes.len() || bytes[..size as usize] != desired {
            return Err(Refusal::IncompleteInventory);
        }
        Ok(())
    }
    fn shortcut(&mut self, expected: &Shortcut) -> Result<FileCustody, Refusal> {
        let root = self.programs()?;
        let path = RelativePath::new(&expected.path)
            .map_err(|_| Refusal::InvalidRequest)?
            .under(&root);
        self.shortcut_at(expected, &path)
    }
    fn shortcut_at(&mut self, expected: &Shortcut, path: &Path) -> Result<FileCustody, Refusal> {
        use windows::Win32::{
            System::Com::{
                CLSCTX_INPROC_SERVER, CoCreateInstance, IPersistFile, STGM_READ,
                StructuredStorage::PropVariantToString,
            },
            UI::Shell::{
                IShellLinkW,
                PropertiesSystem::{IPropertyStore, PSGetPropertyKeyFromName},
                SLGP_RAWPATH, ShellLink,
            },
        };
        use windows::core::{Interface, PCWSTR};
        let held = custody::file(path)?;
        let path = wide(path.to_str().ok_or(Refusal::InvalidRequest)?)?;
        // SAFETY: Instantiate the OS ShellLink reader. Load read-only; never Resolve or Save.
        let link: IShellLinkW = unsafe { CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER) }
            .map_err(|_| Refusal::NativeFailure)?;
        let persistence: IPersistFile = link.cast().map_err(|_| Refusal::NativeFailure)?;
        unsafe { persistence.Load(PCWSTR(path.as_ptr()), STGM_READ) }
            .map_err(|_| Refusal::IncompleteInventory)?;
        let mut target = vec![0u16; 32768];
        let mut arguments = vec![0u16; 32768];
        let mut directory = vec![0u16; 32768];
        unsafe {
            link.GetPath(&mut target, std::ptr::null_mut(), SLGP_RAWPATH.0 as u32)
                .map_err(|_| Refusal::IncompleteInventory)?;
            link.GetArguments(&mut arguments)
                .map_err(|_| Refusal::IncompleteInventory)?;
            link.GetWorkingDirectory(&mut directory)
                .map_err(|_| Refusal::IncompleteInventory)?;
        }
        let decode = |text: &[u16]| -> Result<String, Refusal> {
            let end = text
                .iter()
                .position(|c| *c == 0)
                .ok_or(Refusal::IncompleteInventory)?;
            if end + 1 == text.len() {
                return Err(Refusal::IncompleteInventory);
            }
            String::from_utf16(&text[..end]).map_err(|_| Refusal::IncompleteInventory)
        };
        if decode(&target)? != expand(&expected.target, self.owner.prefix())?
            || decode(&arguments)? != expected.arguments
            || decode(&directory)?.trim_end_matches('\\')
                != expand(&expected.working_directory, self.owner.prefix())?.trim_end_matches('\\')
        {
            return Err(Refusal::IncompleteInventory);
        }
        let properties: IPropertyStore = link.cast().map_err(|_| Refusal::IncompleteInventory)?;
        let key = wide("System.AppUserModel.ID")?;
        let mut property_key = windows::Win32::Foundation::PROPERTYKEY::default();
        unsafe { PSGetPropertyKeyFromName(PCWSTR(key.as_ptr()), &mut property_key) }
            .map_err(|_| Refusal::NativeFailure)?;
        let key = property_key;
        let value =
            unsafe { properties.GetValue(&key) }.map_err(|_| Refusal::IncompleteInventory)?;
        let kind = unsafe { value.Anonymous.Anonymous.vt };
        if !matches!(
            kind,
            windows::Win32::System::Variant::VT_BSTR | windows::Win32::System::Variant::VT_LPWSTR
        ) {
            return Err(Refusal::IncompleteInventory);
        }
        let mut app_id = [0u16; 4096];
        unsafe { PropVariantToString(&value, &mut app_id) }
            .map_err(|_| Refusal::IncompleteInventory)?;
        if decode(&app_id)? != expected.app_id {
            return Err(Refusal::IncompleteInventory);
        }
        Ok(held)
    }
    fn programs(&self) -> Result<PathBuf, Refusal> {
        use windows::Win32::{
            System::Com::CoTaskMemFree,
            UI::Shell::{
                FOLDERID_CommonPrograms, FOLDERID_Programs, KF_FLAG_DONT_VERIFY,
                SHGetKnownFolderPath,
            },
        };
        let folder = match self.owner.context() {
            NativeContext::Machine => &FOLDERID_CommonPrograms,
            NativeContext::User { .. } => &FOLDERID_Programs,
        };
        // SAFETY: Query only; no creation flag. Release the returned COM allocation.
        let folder = unsafe { SHGetKnownFolderPath(folder, KF_FLAG_DONT_VERIFY, None) }
            .map_err(|_| Refusal::IncompleteInventory)?;
        let text = unsafe { folder.to_string() };
        unsafe { CoTaskMemFree(Some(folder.0.cast())) };
        Ok(PathBuf::from(
            text.map_err(|_| Refusal::IncompleteInventory)?,
        ))
    }
    fn absent_registry(&self, expected: &AbsentRegistry) -> Result<(), Refusal> {
        use windows::{
            Win32::System::Registry::{
                HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, RRF_RT_ANY, RRF_SUBKEY_WOW6464KEY,
                RegGetValueW,
            },
            core::PCWSTR,
        };
        let hive = match self.owner.context() {
            NativeContext::Machine => HKEY_LOCAL_MACHINE,
            NativeContext::User { .. } => HKEY_CURRENT_USER,
        };
        let key = wide(&expected.key)?;
        let name = wide(&expected.name)?;
        // SAFETY: Read-only existence query. Only positive not-found proves absence.
        let result = unsafe {
            RegGetValueW(
                hive,
                PCWSTR(key.as_ptr()),
                PCWSTR(name.as_ptr()),
                RRF_RT_ANY | RRF_SUBKEY_WOW6464KEY,
                None,
                None,
                None,
            )
        };
        if result.0 != 2 {
            return Err(Refusal::IncompleteInventory);
        }
        Ok(())
    }
}
impl Drop for Native<'_> {
    fn drop(&mut self) {
        if self.com {
            unsafe { windows::Win32::System::Com::CoUninitialize() };
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use windows::{
        Win32::{
            Foundation::PROPERTYKEY,
            System::Com::{
                CLSCTX_INPROC_SERVER, CoCreateInstance, IPersistFile,
                StructuredStorage::PROPVARIANT,
            },
            UI::Shell::{
                IShellLinkW,
                PropertiesSystem::{IPropertyStore, PSGetPropertyKeyFromName},
                ShellLink,
            },
        },
        core::{Interface, PCWSTR},
    };

    #[test]
    fn real_private_shortcut_refuses_changed_semantics_and_retains_custody() {
        let root = tempfile::tempdir().unwrap();
        let owner = NativeOwner::new(
            "12345678-1234-1234-1234-123456789ABC".into(),
            NativeContext::Machine,
            root.path().to_owned(),
        )
        .unwrap();
        let mut observer = Native::new(&owner).unwrap();
        let expected = Shortcut {
            component: owner.product_code().into(),
            path: "fixture.lnk".into(),
            target: "[INSTALL_ROOT]desktop.exe".into(),
            arguments: String::new(),
            working_directory: "[INSTALL_ROOT]".into(),
            app_id: "test.registration".into(),
        };
        let target = root.path().join("desktop.exe");
        std::fs::write(&target, b"fixture, never executed").unwrap();
        let path = root.path().join("fixture.lnk");
        // SAFETY: All writes are to the caller-owned isolated temporary fixture.
        unsafe {
            let link: IShellLinkW =
                CoCreateInstance(&ShellLink, None, CLSCTX_INPROC_SERVER).unwrap();
            link.SetPath(PCWSTR(wide(target.to_str().unwrap()).unwrap().as_ptr()))
                .unwrap();
            link.SetWorkingDirectory(PCWSTR(
                wide(root.path().to_str().unwrap()).unwrap().as_ptr(),
            ))
            .unwrap();
            let properties: IPropertyStore = link.cast().unwrap();
            let mut key = PROPERTYKEY::default();
            PSGetPropertyKeyFromName(
                PCWSTR(wide("System.AppUserModel.ID").unwrap().as_ptr()),
                &mut key,
            )
            .unwrap();
            properties
                .SetValue(&key, &PROPVARIANT::from(expected.app_id.as_str()))
                .unwrap();
            properties.Commit().unwrap();
            let persist: IPersistFile = link.cast().unwrap();
            persist
                .Save(PCWSTR(wide(path.to_str().unwrap()).unwrap().as_ptr()), true)
                .unwrap();
        }
        let held = observer.shortcut_at(&expected, &path).unwrap();
        assert!(std::fs::remove_file(&path).is_err());
        drop(held);
        for field in 0..4 {
            let mut altered = expected.clone();
            match field {
                0 => altered.target = "[INSTALL_ROOT]other.exe".into(),
                1 => altered.arguments = "--unexpected".into(),
                2 => altered.working_directory = "[INSTALL_ROOT]other".into(),
                _ => altered.app_id = "foreign.application".into(),
            }
            assert!(observer.shortcut_at(&altered, &path).is_err());
        }
        std::fs::remove_file(&path).unwrap();
        assert!(observer.shortcut_at(&expected, &path).is_err());
    }

    #[test]
    fn registration_description_rejects_legacy_unbounded_and_escaping_inputs() {
        assert!(Description::parse("{}").is_err());
        assert!(Description::parse(&" ".repeat(32769)).is_err());
        assert!(expand("[OTHER]", Path::new("C:\\fixture")).is_err());
        assert!(wide("unexpected\0suffix").is_err());
        let mut value = serde_json::json!({"schema":1,"application_id":"test","version":"1.0.0","scope":"machine", "files":{"../escape":"a".repeat(64),"a":"a".repeat(64),"b":"a".repeat(64),"c":"a".repeat(64)}, "components":["12345678-1234-1234-1234-123456789ABC"], "registry":[{"component":"12345678-1234-1234-1234-123456789ABC","key":"Software\\test","name":"Installed","type":"integer","value":"1"}],"shortcuts":[],"absent_registry":[],"absent_shortcuts":[]});
        assert!(Description::parse(&value.to_string()).is_err());
        value["files"].as_object_mut().unwrap().remove("../escape");
        value["files"]["safe"] = serde_json::json!("a".repeat(64));
        assert!(Description::parse(&value.to_string()).is_ok());
        for path in ["../escape.lnk", "C:/escape.lnk", "bad\\leaf.lnk"] {
            let mut changed = value.clone();
            changed["absent_shortcuts"] = serde_json::json!([path]);
            assert!(Description::parse(&changed.to_string()).is_err());
        }
        for (key, name) in [
            ("System\\test", "Name"),
            ("Software\\test\0", "Name"),
            ("Software\\test", "Name\n"),
        ] {
            let mut changed = value.clone();
            changed["absent_registry"] = serde_json::json!([{ "key":key, "name":name }]);
            assert!(Description::parse(&changed.to_string()).is_err());
        }
        let root = tempfile::tempdir().unwrap();
        let owner = NativeOwner::new(
            "12345678-1234-1234-1234-123456789ABC".into(),
            NativeContext::User {
                sid: "S-1-5-21-1000".into(),
            },
            root.path().to_owned(),
        )
        .unwrap();
        assert!(matches!(
            Description::parse(&value.to_string())
                .unwrap()
                .verify(&owner),
            Err(Refusal::InvalidRequest)
        ));
    }
}
