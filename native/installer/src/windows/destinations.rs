//! Read-only MSI destination and feature inventory validation.
use super::*;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DestinationRefusal {
    Inventory,
    TooLong,
}

const MAX_DESTINATION_ROWS: usize = 100_000;

fn table_rows<const N: usize>(database: &Handle, query: &str) -> Result<Vec<[String; N]>, Refusal> {
    let query = wide(query)?;
    let mut view = 0;
    // SAFETY: owned read-only database, static SQL and writable handle output.
    result(unsafe { MsiDatabaseOpenViewW(database.0, query.as_ptr(), &mut view) })?;
    let view = Handle::new(view)?;
    // SAFETY: queries have no parameters; the view remains owned throughout enumeration.
    result(unsafe { MsiViewExecute(view.0, 0) })?;
    let mut rows = Vec::new();
    loop {
        let mut row = 0;
        // SAFETY: live view, writable record output; each fetched record is closed.
        let code = unsafe { MsiViewFetch(view.0, &mut row) };
        if code == ERROR_NO_MORE_ITEMS {
            return Ok(rows);
        }
        result(code)?;
        let row = Handle::new(row)?;
        if rows.len() == MAX_DESTINATION_ROWS {
            return Err(Refusal::IncompleteInventory);
        }
        let mut fields: [String; N] = std::array::from_fn(|_| String::new());
        for (index, field) in fields.iter_mut().enumerate() {
            // SAFETY: selected field exists and string() owns bounded UTF-16 output.
            *field = string(|buffer, size| unsafe {
                MsiRecordGetStringW(row.0, (index + 1) as u32, buffer, size)
            })?;
            if field.encode_utf16().count() > 255 {
                return Err(Refusal::InvalidRequest);
            }
        }
        rows.push(fields);
    }
}

fn destination_name(value: &str, directory: bool) -> Result<String, DestinationRefusal> {
    let mut sides = value.split(':');
    let target = sides.next().ok_or(DestinationRefusal::Inventory)?;
    let source = sides.next();
    if sides.next().is_some() || (!directory && source.is_some()) {
        return Err(DestinationRefusal::Inventory);
    }
    let parse = |name: &str| -> Result<String, DestinationRefusal> {
        let mut names = name.split('|');
        let short = names.next().ok_or(DestinationRefusal::Inventory)?;
        let long = names.next();
        if names.next().is_some() || short.is_empty() || long.is_some_and(str::is_empty) {
            return Err(DestinationRefusal::Inventory);
        }
        for part in [Some(short), long].into_iter().flatten() {
            let device = part.split('.').next().unwrap_or(part).to_ascii_uppercase();
            if matches!(device.as_str(), "CON" | "PRN" | "AUX" | "NUL")
                || (device.len() == 4
                    && (device.starts_with("COM") || device.starts_with("LPT"))
                    && matches!(device.as_bytes()[3], b'1'..=b'9'))
            {
                return Err(DestinationRefusal::Inventory);
            }
            if (part == "." && directory)
                || (!part.is_empty()
                    && part != ".."
                    && !part.ends_with(['.', ' '])
                    && !part
                        .chars()
                        .any(|value| value.is_control() || "\\/:*?\"<>|".contains(value)))
            {
                continue;
            }
            return Err(DestinationRefusal::Inventory);
        }
        Ok(long.unwrap_or(short).into())
    };
    if let Some(source) = source {
        parse(source)?;
    }
    parse(target)
}

fn destination_identifier(value: &str) -> Result<(), DestinationRefusal> {
    if value.is_empty()
        || value.len() > 72
        || !value
            .bytes()
            .next()
            .is_some_and(|value| value.is_ascii_alphabetic() || value == b'_')
        || !value
            .bytes()
            .all(|value| value.is_ascii_alphanumeric() || matches!(value, b'_' | b'.'))
    {
        return Err(DestinationRefusal::Inventory);
    }
    Ok(())
}

fn resolved_destinations(
    prefix: &Path,
    directories: Vec<[String; 3]>,
    components: Vec<[String; 2]>,
    files: Vec<[String; 3]>,
) -> Result<Vec<PathBuf>, DestinationRefusal> {
    if !prefix.is_absolute()
        || prefix
            .components()
            .any(|part| matches!(part, Component::ParentDir))
        || !matches!(prefix.components().next(), Some(Component::Prefix(value)) if matches!(value.kind(), Prefix::Disk(_)))
        || directories.is_empty()
        || files.is_empty()
        || [directories.len(), components.len(), files.len()]
            .into_iter()
            .any(|count| count > MAX_DESTINATION_ROWS)
    {
        return Err(DestinationRefusal::Inventory);
    }
    let mut names = BTreeSet::new();
    let mut tree = BTreeMap::new();
    for [id, parent, default] in directories {
        destination_identifier(&id)?;
        if !parent.is_empty() {
            destination_identifier(&parent)?;
        }
        if !names.insert(id.to_ascii_lowercase())
            || tree
                .insert(id, (parent, destination_name(&default, true)?))
                .is_some()
        {
            return Err(DestinationRefusal::Inventory);
        }
    }
    if !tree.contains_key("INSTALL_ROOT")
        || !tree.contains_key("TARGETDIR")
        || !tree["TARGETDIR"].0.is_empty()
        || tree.iter().any(|(id, (parent, _))| {
            (id != "TARGETDIR" && parent.is_empty())
                || (!parent.is_empty() && !tree.contains_key(parent))
        })
    {
        return Err(DestinationRefusal::Inventory);
    }
    let mut resolved = BTreeMap::new();
    let mut directory_paths = BTreeSet::new();
    // Validate all rows, including otherwise unused trees: no unknown parents or cycles.
    for id in tree.keys() {
        let mut chain = Vec::new();
        let mut current = id.as_str();
        let mut seen = BTreeSet::new();
        let mut inside = false;
        loop {
            if !seen.insert(current) || chain.len() > 64 {
                return Err(DestinationRefusal::Inventory);
            }
            if current == "INSTALL_ROOT" {
                inside = true;
            }
            let (parent, name) = &tree[current];
            if !inside {
                chain.push(name.as_str());
            }
            if parent.is_empty() {
                break;
            }
            current = parent;
        }
        if inside {
            let mut destination = prefix.to_owned();
            for name in chain.into_iter().rev().filter(|name| *name != ".") {
                destination.push(name);
            }
            let value = destination
                .to_str()
                .ok_or(DestinationRefusal::Inventory)?
                .to_lowercase();
            if tree[id].1 != "." && !directory_paths.insert(value) {
                return Err(DestinationRefusal::Inventory);
            }
            resolved.insert(id.clone(), destination);
        }
    }
    let mut component_ids = BTreeSet::new();
    let mut component_directories = BTreeMap::new();
    for [id, directory] in components {
        destination_identifier(&id)?;
        if !tree.contains_key(&directory)
            || !component_ids.insert(id.to_ascii_lowercase())
            || component_directories.insert(id, directory).is_some()
        {
            return Err(DestinationRefusal::Inventory);
        }
    }
    let mut file_ids = BTreeSet::new();
    let mut paths = BTreeSet::new();
    let mut destinations = Vec::new();
    for [id, component, name] in files {
        destination_identifier(&id)?;
        if !file_ids.insert(id.to_ascii_lowercase()) {
            return Err(DestinationRefusal::Inventory);
        }
        let directory = component_directories
            .get(&component)
            .ok_or(DestinationRefusal::Inventory)?;
        let directory = resolved
            .get(directory)
            .ok_or(DestinationRefusal::Inventory)?;
        let destination = directory.join(destination_name(&name, false)?);
        let value = destination.to_str().ok_or(DestinationRefusal::Inventory)?;
        if value.encode_utf16().count() > 259 {
            return Err(DestinationRefusal::TooLong);
        }
        if directory_paths.contains(&value.to_lowercase()) || !paths.insert(value.to_lowercase()) {
            return Err(DestinationRefusal::Inventory);
        }
        destinations.push(destination);
    }
    Ok(destinations)
}

fn verified_component_budget(
    components: Vec<[String; 3]>,
    registry: Vec<[String; 3]>,
) -> Result<(), DestinationRefusal> {
    let mut keys = BTreeMap::new();
    for [id, root, component] in registry {
        if keys.insert(id, (root, component)).is_some() {
            return Err(DestinationRefusal::Inventory);
        }
    }
    let mut costed = components.len();
    let mut seen = BTreeSet::new();
    for [component, attributes, keypath] in components {
        if !seen.insert(component.clone()) {
            return Err(DestinationRefusal::Inventory);
        }
        let attributes = attributes
            .parse::<u16>()
            .map_err(|_| DestinationRefusal::Inventory)?;
        if attributes & 4 != 0 {
            if !keys.get(&keypath).is_some_and(|(root, owner)| {
                owner == &component && matches!(root.as_str(), "-1" | "0" | "1" | "2" | "3")
            }) {
                return Err(DestinationRefusal::Inventory);
            }
            costed += 1;
        }
    }
    if costed > 65535 {
        return Err(DestinationRefusal::Inventory);
    }
    Ok(())
}

fn verified_features(
    features: Vec<[String; 5]>,
    components: &[[String; 2]],
    links: Vec<[String; 2]>,
) -> Result<(), DestinationRefusal> {
    let mut tree = BTreeMap::new();
    for [name, parent, display, level, attributes] in features {
        if tree
            .insert(name, (parent, display, level, attributes))
            .is_some()
        {
            return Err(DestinationRefusal::Inventory);
        }
    }
    let owned: BTreeSet<_> = components.iter().map(|row| row[0].as_str()).collect();
    if tree.is_empty() || owned.is_empty() || owned.len() != components.len() {
        return Err(DestinationRefusal::Inventory);
    }
    let mut enrolled = BTreeSet::new();
    let mut counts = BTreeMap::<String, usize>::new();
    for [feature, component] in links {
        if !tree.contains_key(&feature)
            || !owned.contains(component.as_str())
            || !enrolled.insert(component)
        {
            return Err(DestinationRefusal::Inventory);
        }
        let count = counts.entry(feature).or_default();
        *count += 1;
        if *count > 1600 {
            return Err(DestinationRefusal::Inventory);
        }
    }
    if enrolled.len() != owned.len() {
        return Err(DestinationRefusal::Inventory);
    }
    let combined = tree.contains_key("VersionFiles")
        && tree.contains_key("SharedRegistration")
        && !tree.contains_key("ProductFeature");
    for (name, (parent, display, level, attributes)) in &tree {
        if !matches!(display.as_str(), "" | "0")
            || level != "1"
            || attributes
                != if combined {
                    if parent.is_empty() { "8" } else { "10" }
                } else if parent.is_empty() {
                    "24"
                } else {
                    "26"
                }
        {
            return Err(DestinationRefusal::Inventory);
        }
        let mut visited = BTreeSet::from([name.as_str()]);
        let mut current = parent.as_str();
        while !current.is_empty() {
            if visited.len() >= 16 || !visited.insert(current) {
                return Err(DestinationRefusal::Inventory);
            }
            current = &tree.get(current).ok_or(DestinationRefusal::Inventory)?.0;
        }
        if if combined {
            !["VersionFiles", "SharedRegistration"].iter().any(|root| {
                visited.contains(root) && tree.get(*root).is_some_and(|row| row.0.is_empty())
            })
        } else {
            !visited.contains("ProductFeature")
                || !tree
                    .get("ProductFeature")
                    .is_some_and(|row| row.0.is_empty())
        } {
            return Err(DestinationRefusal::Inventory);
        }
    }
    Ok(())
}

/// Read exact admitted MSI tables while the caller retains its hash-verified file custody.
pub fn verify_installation_destinations(
    package: &Path,
    prefix: &Path,
    _custody: &crate::custody::FileCustody,
) -> Result<(), DestinationRefusal> {
    verify_installation_destinations_for_scope(package, prefix, _custody, Scope::User)
}
pub fn verify_installation_destinations_for_scope(
    package: &Path,
    prefix: &Path,
    _custody: &crate::custody::FileCustody,
    scope: Scope,
) -> Result<(), DestinationRefusal> {
    let inspect = || -> Result<_, Refusal> {
        let database = database(package)?;
        let tables = table_rows::<1>(&database, "SELECT `Name` FROM `_Tables`")?;
        verified_component_budget(
            table_rows(
                &database,
                "SELECT `Component`, `Attributes`, `KeyPath` FROM `Component`",
            )?,
            if tables.iter().any(|row| row[0] == "Registry") {
                table_rows(
                    &database,
                    "SELECT `Registry`, `Root`, `Component_` FROM `Registry`",
                )?
            } else {
                Vec::new()
            },
        )
        .map_err(|_| Refusal::InvalidRequest)?;
        let mut components = table_rows(
            &database,
            "SELECT `Component`, `Directory_` FROM `Component`",
        )?;
        verified_features(
            table_rows(&database, "SELECT `Feature`, `Feature_Parent`, `Display`, `Level`, `Attributes` FROM `Feature`")?,
            &components,
            table_rows(&database, "SELECT `Feature_`, `Component_` FROM `FeatureComponents`")?,
        ).map_err(|_| Refusal::InvalidRequest)?;
        if tables.iter().any(|row| row[0] == "Condition")
            && !table_rows::<1>(&database, "SELECT `Feature_` FROM `Condition`")?.is_empty()
        {
            return Err(Refusal::InvalidRequest);
        }
        if property(&database, "INSTALLLEVEL")?
            .is_some_and(|level| level.parse::<u32>().map_or(true, |level| level == 0))
        {
            return Err(Refusal::InvalidRequest);
        }
        let combined = property(&database, "CadrumoAdmissionUser")?.is_some();
        let mut files = table_rows::<3>(
            &database,
            "SELECT `File`, `Component_`, `FileName` FROM `File`",
        )?;
        if combined {
            let conditions = table_rows::<2>(
                &database,
                "SELECT `Component`, `Condition` FROM `Component`",
            )?;
            let mut excluded = BTreeSet::new();
            for [component, condition] in conditions {
                let active = match condition.as_str() {
                    "" => true,
                    "NOT ALLUSERS" => scope == Scope::User,
                    "ALLUSERS = \"1\"" => scope == Scope::Machine,
                    _ => return Err(Refusal::InvalidRequest),
                };
                if !active {
                    excluded.insert(component);
                }
            }
            components.retain(|row: &[String; 2]| !excluded.contains(&row[0]));
            files.retain(|row| !excluded.contains(&row[1]));
        }
        Ok((
            table_rows(
                &database,
                "SELECT `Directory`, `Directory_Parent`, `DefaultDir` FROM `Directory`",
            )?,
            components,
            files,
        ))
    };
    let (directories, components, files) = inspect().map_err(|_| DestinationRefusal::Inventory)?;
    resolved_destinations(prefix, directories, components, files).map(|_| ())
}
#[cfg(test)]
mod tests {
    use super::*;

    type DestinationFixture = (Vec<[String; 3]>, Vec<[String; 2]>, Vec<[String; 3]>);

    fn destination_fixture() -> DestinationFixture {
        (
            vec![
                ["TARGETDIR".into(), "".into(), "SourceDir".into()],
                ["LocalAppDataFolder".into(), "TARGETDIR".into(), ".".into()],
                [
                    "INSTALL_ROOT".into(),
                    "LocalAppDataFolder".into(),
                    "CADRUMO".into(),
                ],
                [
                    "Versions".into(),
                    "INSTALL_ROOT".into(),
                    "versio~1|versions:source".into(),
                ],
                ["Release".into(), "Versions".into(), "0.6.0".into()],
                ["Alias".into(), "Release".into(), ".".into()],
            ],
            vec![
                ["C_Version".into(), "Alias".into()],
                ["C_Manager".into(), "INSTALL_ROOT".into()],
            ],
            vec![
                [
                    "F_Version".into(),
                    "C_Version".into(),
                    "payloa~1.bin|payload.bin".into(),
                ],
                ["F_Manager".into(), "C_Manager".into(), "manager.exe".into()],
            ],
        )
    }

    #[test]
    fn msi_destinations_resolve_all_files_long_target_names_and_dot_directories() {
        let (directories, components, files) = destination_fixture();
        assert_eq!(
            resolved_destinations(Path::new(r"C:\Install"), directories, components, files)
                .unwrap(),
            vec![
                PathBuf::from(r"C:\Install\versions\0.6.0\payload.bin"),
                PathBuf::from(r"C:\Install\manager.exe"),
            ]
        );
    }

    #[test]
    fn msi_destination_budget_uses_absolute_utf16_units_including_astral_names() {
        for astral in [false, true] {
            let (directories, components, mut files) = destination_fixture();
            let base = r"C:\Install\versions\0.6.0\";
            let available = 259 - base.encode_utf16().count();
            let mut name = if astral {
                "😀".repeat(available / 2)
            } else {
                "a".repeat(available)
            };
            if name.encode_utf16().count() < available {
                name.push('a');
            }
            files[0][2] = name;
            assert!(
                resolved_destinations(
                    Path::new(r"C:\Install"),
                    directories.clone(),
                    components.clone(),
                    files.clone()
                )
                .is_ok()
            );
            files[0][2].push('a');
            assert_eq!(
                resolved_destinations(Path::new(r"C:\Install"), directories, components, files),
                Err(DestinationRefusal::TooLong)
            );
        }
    }

    #[test]
    fn msi_destination_inventory_refuses_incomplete_escaping_cyclic_and_ambiguous_trees() {
        for defect in 0..14 {
            let (mut directories, mut components, mut files) = destination_fixture();
            match defect {
                0 => directories.retain(|row| row[0] != "INSTALL_ROOT"),
                1 => directories[3][1] = "Unknown".into(),
                2 => directories[3][1] = "Release".into(),
                3 => directories[3][2] = "..".into(),
                4 => directories[3][2] = r"a\b".into(),
                5 => directories[3][2] = "short|long|extra".into(),
                6 => directories[0][1] = "Release".into(),
                7 => components[0][1] = "Unknown".into(),
                8 => files[0][1] = "Unknown".into(),
                9 => files[0][2] = "../outside".into(),
                10 => files.clear(),
                11 => {
                    files.push([
                        "F_Duplicate".into(),
                        "C_Manager".into(),
                        "MANAGER.EXE".into(),
                    ]);
                }
                12 => {
                    directories.push([
                        "OtherVersions".into(),
                        "INSTALL_ROOT".into(),
                        "VERSIONS".into(),
                    ]);
                }
                13 => files[0][2] = "CON.bin".into(),
                _ => unreachable!(),
            }
            assert_eq!(
                resolved_destinations(Path::new(r"C:\Install"), directories, components, files),
                Err(DestinationRefusal::Inventory),
                "defect {defect}"
            );
        }
        let (directories, components, files) = destination_fixture();
        assert_eq!(
            resolved_destinations(Path::new(r"\\?\C:\Install"), directories, components, files),
            Err(DestinationRefusal::Inventory)
        );
    }

    #[test]
    fn component_costing_budget_reserves_registry_keypath_expansion() {
        let components: Vec<[String; 3]> = (0..32767)
            .map(|index| [format!("C_{index}"), "260".into(), format!("R_{index}")])
            .collect();
        let registry: Vec<[String; 3]> = (0..32767)
            .map(|index| [format!("R_{index}"), "1".into(), format!("C_{index}")])
            .collect();
        let mut boundary = components.clone();
        boundary.push(["C_File".into(), "256".into(), "F_File".into()]);
        assert_eq!(
            verified_component_budget(boundary, registry.clone()),
            Ok(())
        );
        let mut oversized = components.clone();
        oversized.push(["C_Extra".into(), "260".into(), "R_Extra".into()]);
        let mut extra_registry = registry.clone();
        extra_registry.push(["R_Extra".into(), "1".into(), "C_Extra".into()]);
        assert_eq!(
            verified_component_budget(oversized, extra_registry),
            Err(DestinationRefusal::Inventory)
        );
        let mut invalid = registry;
        invalid[0][2] = "C_Foreign".into();
        assert_eq!(
            verified_component_budget(components, invalid),
            Err(DestinationRefusal::Inventory)
        );
    }

    #[test]
    fn mandatory_feature_inventory_enforces_component_limit_and_complete_selection() {
        let components: Vec<[String; 2]> = (0..1601)
            .map(|index| [format!("C_{index}"), "INSTALL_ROOT".into()])
            .collect();
        let features = vec![
            [
                "ProductFeature".into(),
                "".into(),
                "0".into(),
                "1".into(),
                "24".into(),
            ],
            [
                "PayloadFeature0001".into(),
                "ProductFeature".into(),
                "0".into(),
                "1".into(),
                "26".into(),
            ],
        ];
        let links: Vec<[String; 2]> = components
            .iter()
            .enumerate()
            .map(|(index, row)| {
                [
                    if index < 1600 {
                        "ProductFeature"
                    } else {
                        "PayloadFeature0001"
                    }
                    .into(),
                    row[0].clone(),
                ]
            })
            .collect();
        assert_eq!(
            verified_features(features.clone(), &components, links.clone()),
            Ok(())
        );
        for fault in 0..7 {
            let mut features = features.clone();
            let mut links = links.clone();
            match fault {
                0 => links[1600][0] = "ProductFeature".into(),
                1 => {
                    links.pop();
                }
                2 => links[1600][0] = "Unknown".into(),
                3 => links[1600][1] = "C_0".into(),
                4 => features[1][1] = "PayloadFeature0001".into(),
                5 => features[1][3] = "0".into(),
                _ => features[1][4] = "22".into(),
            }
            assert_eq!(
                verified_features(features, &components, links),
                Err(DestinationRefusal::Inventory)
            );
        }
    }

    #[test]
    fn read_only_native_msi_tables_supply_complete_admitted_destination_inventory() {
        let root = tempfile::tempdir().unwrap();
        let package = root.path().join("destination.msi");
        let name = wide(package.to_str().unwrap()).unwrap();
        let mut database = 0;
        // SAFETY: creates only this test's isolated MSI database, with owned output.
        result(unsafe { MsiOpenDatabaseW(name.as_ptr(), 3_usize as *const u16, &mut database) })
            .unwrap();
        let database = Handle::new(database).unwrap();
        for statement in [
            "CREATE TABLE `Directory` (`Directory` CHAR(72) NOT NULL, `Directory_Parent` CHAR(72), `DefaultDir` CHAR(255) NOT NULL PRIMARY KEY `Directory`)",
            "CREATE TABLE `Component` (`Component` CHAR(72) NOT NULL, `Directory_` CHAR(72) NOT NULL, `Attributes` SHORT NOT NULL, `KeyPath` CHAR(72) PRIMARY KEY `Component`)",
            "CREATE TABLE `File` (`File` CHAR(72) NOT NULL, `Component_` CHAR(72) NOT NULL, `FileName` CHAR(255) NOT NULL PRIMARY KEY `File`)",
            "CREATE TABLE `Feature` (`Feature` CHAR(38) NOT NULL, `Feature_Parent` CHAR(38), `Display` SHORT, `Level` SHORT NOT NULL, `Attributes` SHORT NOT NULL PRIMARY KEY `Feature`)",
            "CREATE TABLE `FeatureComponents` (`Feature_` CHAR(38) NOT NULL, `Component_` CHAR(72) NOT NULL PRIMARY KEY `Feature_`, `Component_`)",
            "CREATE TABLE `Property` (`Property` CHAR(72) NOT NULL, `Value` CHAR(0) NOT NULL PRIMARY KEY `Property`)",
            "INSERT INTO `Feature` (`Feature`, `Display`, `Level`, `Attributes`) VALUES ('ProductFeature', 0, 1, 24)",
            "INSERT INTO `FeatureComponents` (`Feature_`, `Component_`) VALUES ('ProductFeature', 'C_File')",
            "INSERT INTO `Directory` (`Directory`, `DefaultDir`) VALUES ('TARGETDIR', 'SourceDir')",
            "INSERT INTO `Directory` (`Directory`, `Directory_Parent`, `DefaultDir`) VALUES ('LocalAppDataFolder', 'TARGETDIR', '.')",
            "INSERT INTO `Directory` (`Directory`, `Directory_Parent`, `DefaultDir`) VALUES ('INSTALL_ROOT', 'LocalAppDataFolder', 'CADRUMO')",
            "INSERT INTO `Directory` (`Directory`, `Directory_Parent`, `DefaultDir`) VALUES ('Versions', 'INSTALL_ROOT', 'versio~1|versions:source')",
            "INSERT INTO `Component` (`Component`, `Directory_`, `Attributes`, `KeyPath`) VALUES ('C_File', 'Versions', 256, 'F_One')",
            "INSERT INTO `File` (`File`, `Component_`, `FileName`) VALUES ('F_One', 'C_File', 'one.bin')",
            "INSERT INTO `File` (`File`, `Component_`, `FileName`) VALUES ('F_Two', 'C_File', 'two.bin')",
        ] {
            let statement = wide(statement).unwrap();
            let mut view = 0;
            // SAFETY: live isolated database and terminated fixed SQL, writable view output.
            result(unsafe { MsiDatabaseOpenViewW(database.0, statement.as_ptr(), &mut view) })
                .unwrap();
            let view = Handle::new(view).unwrap();
            // SAFETY: fixed statements have no parameter records.
            result(unsafe { MsiViewExecute(view.0, 0) }).unwrap();
        }
        let statement = wide(&format!(
            "UPDATE `File` SET `FileName` = '{}' WHERE `File` = 'F_Two'",
            "a".repeat(220)
        ))
        .unwrap();
        let mut view = 0;
        // SAFETY: exact isolated database, fixed test-only update and writable view output.
        result(unsafe { MsiDatabaseOpenViewW(database.0, statement.as_ptr(), &mut view) }).unwrap();
        let view = Handle::new(view).unwrap();
        // SAFETY: this statement has no parameter record and touches only this fixture.
        result(unsafe { MsiViewExecute(view.0, 0) }).unwrap();
        drop(view);
        // SAFETY: persist this owned fixture before closing and reopening read-only.
        result(unsafe { MsiDatabaseCommit(database.0) }).unwrap();
        drop(database);
        let custody = crate::custody::file(&package).unwrap();
        assert_eq!(
            verify_installation_destinations(&package, Path::new(r"C:\Install"), &custody),
            Ok(())
        );
        // The first seven-character file still fits; only the second row exceeds
        // the budget, proving complete native enumeration rather than first-row sampling.
        let oversized = PathBuf::from(format!("C:\\{}", "a".repeat(27)));
        assert_eq!(
            verify_installation_destinations(&package, &oversized, &custody),
            Err(DestinationRefusal::TooLong)
        );
        assert!(!oversized.exists());
        drop(custody);
        let mut raw_database = 0;
        // SAFETY: reopen only this fixture in transacted mode, with owned output.
        result(unsafe {
            MsiOpenDatabaseW(
                name.as_ptr(),
                ptr::without_provenance::<u16>(1),
                &mut raw_database,
            )
        })
        .unwrap();
        let database = Handle::new(raw_database).unwrap();
        for index in 0..1600 {
            for statement in [
                format!(
                    "INSERT INTO `Component` (`Component`, `Directory_`, `Attributes`) VALUES ('C_Extra{index}', 'Versions', 256)"
                ),
                format!(
                    "INSERT INTO `FeatureComponents` (`Feature_`, `Component_`) VALUES ('ProductFeature', 'C_Extra{index}')"
                ),
            ] {
                let statement = wide(&statement).unwrap();
                let mut view = 0;
                // SAFETY: fixed generated SQL touches only the isolated fixture.
                result(unsafe { MsiDatabaseOpenViewW(database.0, statement.as_ptr(), &mut view) })
                    .unwrap();
                let view = Handle::new(view).unwrap();
                // SAFETY: the insert has no parameter records.
                result(unsafe { MsiViewExecute(view.0, 0) }).unwrap();
            }
        }
        // SAFETY: commit this owned fixture before reacquiring read-only custody.
        result(unsafe { MsiDatabaseCommit(database.0) }).unwrap();
        drop(database);
        let custody = crate::custody::file(&package).unwrap();
        assert_eq!(
            verify_installation_destinations(&package, Path::new(r"C:\Install"), &custody),
            Err(DestinationRefusal::Inventory)
        );
    }
}
