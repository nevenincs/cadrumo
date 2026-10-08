//! Real publication, byte inventory and custody with only native MSI reads substituted.
use super::*;
use cadrumo_application::installation::maintenance::NativeContext;
use serde_json::json;
use std::fs;

struct Fixture {
    _root: tempfile::TempDir,
    plan: Plan,
    store: Store,
    owner: NativeOwner,
    registration: NativeOwner,
    admission: Request,
    description: crate::registration::Description,
}

impl Fixture {
    fn new() -> Self {
        let root = tempfile::tempdir().unwrap();
        let prefix = root.path().to_owned();
        let contract: DiscoveryContract = serde_json::from_value(json!({
            "installation_identity":{"application_id":"test.discovery","channel":"stable"},
            "layout":{"abi":1,"platform":"windows-x64",
                "installation":{"schema":1,"marker":"data/installation.json","versions":"versions","maximum_versions":128,"publication":"data/installation-state"},
                "files":{"package_manifest":"data/package-manifest.json"},
                "application_images":[{"name":"manager","placement":".","target":"rust_manager"}],"entrypoint_suffix":".exe"}
        })).unwrap();
        let package = prefix.join("versions/1.0.0");
        fs::create_dir_all(package.join("data")).unwrap();
        fs::create_dir_all(prefix.join("data")).unwrap();
        let manager = contract.manager_member().unwrap();
        let image =
            PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32/where.exe");
        fs::copy(image, manager.under(&package)).unwrap();
        fs::write(package.join("payload.bin"), b"owned version payload").unwrap();
        let digest = |path: &Path| format!("{:x}", Sha256::digest(fs::read(path).unwrap()));
        let manifest_path = package.join("data/package-manifest.json");
        fs::write(&manifest_path, serde_json::to_vec(&json!({
            "build":{"application_id":"test.discovery","channel":"stable","version":"1.0.0","target":"windows-x86-64"},
            "layout":{"abi":1,"platform":"windows-x64"},"python":"fixture","distributions":{},
            "files":{(manager.as_str()):digest(&manager.under(&package)),"payload.bin":digest(&package.join("payload.bin"))},
            "user_docs":{"directory":"docs/user","bundled":false}
        })).unwrap()).unwrap();
        fs::write(prefix.join("data/installation.json"), serde_json::to_vec(&json!({
            "schema":1,"application_id":"test.discovery","channel":"stable","platform":"windows-x64","abi":1,
            "publication":"data/installation-state","launch_policy":"native"
        })).unwrap()).unwrap();
        for member in ["shared-manager.exe", "maintenance.exe", "receipt.json"] {
            fs::write(prefix.join(member), b"shared resource bytes").unwrap();
        }
        let files: std::collections::BTreeMap<_, _> = [
            "shared-manager.exe",
            "maintenance.exe",
            "receipt.json",
            "data/installation.json",
        ]
        .into_iter()
        .map(|member| (member, digest(&prefix.join(member))))
        .collect();
        let description = crate::registration::Description::parse(&json!({
            "schema":1,"application_id":"test.discovery","version":"1.0.0","scope":"machine","files":files,
            "components":["12345678-1234-1234-1234-123456789ABC"],
            "registry":[{"component":"12345678-1234-1234-1234-123456789ABC","key":"Software\\test.discovery","name":"Installed","type":"integer","value":"1"}],
            "shortcuts":[],"absent_registry":[],"absent_shortcuts":[]
        }).to_string()).unwrap();
        let owner = NativeOwner::new(
            "10000000-0000-0000-0000-000000000001".into(),
            NativeContext::Machine,
            prefix.clone(),
        )
        .unwrap();
        let registration = NativeOwner::new(
            "20000000-0000-0000-0000-000000000001".into(),
            NativeContext::Machine,
            prefix.clone(),
        )
        .unwrap();
        let manifest_sha256 = Sha256Digest::new(digest(&manifest_path)).unwrap();
        let store = Store::new(
            prefix.join("data/installation-state"),
            Identity {
                application_id: "test.discovery".into(),
                channel: "stable".into(),
                platform: "windows-x64".into(),
            },
            128,
        )
        .unwrap();
        store.initialize().unwrap();
        drop(store.exclusive_maintenance().unwrap());
        let lease = store
            .prepare("1.0.0", owner.clone(), manifest_sha256.clone())
            .unwrap();
        store
            .publish_registered("1.0.0", &package, &contract, false, registration.clone())
            .unwrap();
        drop(lease);
        let artifact = |code: &str| Artifact {
            path: prefix.join("unused-native.msi"),
            sha256: manifest_sha256.clone(),
            product_code: code.into(),
        };
        let plan = Plan {
            schema: 1,
            scope: Scope::Machine,
            prefix: prefix.clone(),
            version: "1.0.0".into(),
            desktop_present: false,
            version_product: artifact(owner.product_code()),
            registration_product: artifact(registration.product_code()),
            manifest_sha256,
            contract,
        };
        let admission = Request {
            schema: 1,
            scope: Scope::Machine,
            permitted_families: ["version".into(), "registration".into()],
            conflicting_families: ["other-v".into(), "other-r".into(), "legacy".into()],
        };
        Self {
            _root: root,
            plan,
            store,
            owner,
            registration,
            admission,
            description,
        }
    }
    fn verify(&self, observation: &mut Observed) -> Result<Option<Held<()>>, Error> {
        verify_held(
            &self.plan,
            &self.admission,
            &self.owner,
            &self.registration,
            &self.store,
            observation,
        )
    }
    fn observation(&self, fault: &'static str) -> Observed {
        Observed {
            description: self.description.clone(),
            fault,
            calls: Vec::new(),
        }
    }
}

struct Observed {
    description: crate::registration::Description,
    fault: &'static str,
    calls: Vec<&'static str>,
}
impl Observation for Observed {
    type Custody = ();
    fn bind(
        &mut self,
        plan: &Plan,
        _: &Request,
        _: &NativeOwner,
        _: &NativeOwner,
    ) -> Result<(crate::registration::Description, ()), Error> {
        self.calls.push("bind");
        let mut cached = self.description.clone();
        if self.fault == "cached-different" {
            cached.files.insert(
                "receipt.json".into(),
                Sha256Digest::new("b".repeat(64)).unwrap(),
            );
        }
        let cached = (self.fault != "cached-missing").then_some(&cached);
        let incoming = (self.fault != "incoming-missing").then_some(&self.description);
        Ok((bound_description(plan, incoming, cached)?.clone(), ()))
    }
    fn resources(
        &mut self,
        description: &crate::registration::Description,
        owner: &NativeOwner,
    ) -> Result<Vec<crate::custody::FileCustody>, Error> {
        self.calls.push("resources");
        if self.fault == "native-resources" {
            return Err(Error::Integrity("fixture actual registry differs".into()));
        }
        description.verify_files(owner).map_err(native_error)
    }
    fn recheck(
        &mut self,
        plan: &Plan,
        _: &Request,
        _: &NativeOwner,
        _: &NativeOwner,
    ) -> Result<(), Error> {
        self.calls.push("recheck");
        if self.fault == "native-owner" {
            return Err(Error::Integrity("fixture native owner changed".into()));
        }
        if self.fault == "publication" {
            let path = plan.prefix.join("data/installation-state/state.json");
            let mut value: serde_json::Value = serde_json::from_slice(&fs::read(&path)?).unwrap();
            value["versions"]["1.0.0"]["phase"] = json!("pending");
            fs::write(path, serde_json::to_vec(&value).unwrap())?;
        }
        Ok(())
    }
}

#[test]
fn exact_noop_retains_real_exclusion_and_every_verified_file_until_return_guard_drops() {
    let fixture = Fixture::new();
    let mut observation = fixture.observation("");
    let held = fixture.verify(&mut observation).unwrap().unwrap();
    assert_eq!(
        observation.calls,
        ["bind", "resources", "recheck", "resources", "recheck"]
    );
    assert!(fixture.store.exclusive_maintenance().is_err());
    assert!(
        fs::write(
            fixture.plan.prefix.join("versions/1.0.0/payload.bin"),
            b"changed"
        )
        .is_err()
    );
    assert!(fs::write(fixture.plan.prefix.join("shared-manager.exe"), b"changed").is_err());
    drop(held);
    assert!(fixture.store.exclusive_maintenance().is_ok());
    fs::write(
        fixture.plan.prefix.join("versions/1.0.0/payload.bin"),
        b"changed",
    )
    .unwrap();
}

#[test]
fn no_op_refuses_missing_or_changed_contract_resources_owner_and_publication() {
    for fault in [
        "incoming-missing",
        "cached-missing",
        "cached-different",
        "native-resources",
        "native-owner",
        "publication",
    ] {
        let fixture = Fixture::new();
        let mut observation = fixture.observation(fault);
        assert!(fixture.verify(&mut observation).is_err(), "{fault}");
        assert_eq!(observation.calls.first(), Some(&"bind"));
        assert!(fixture.store.exclusive_maintenance().is_ok());
    }
    for member in ["versions/1.0.0/payload.bin", "shared-manager.exe"] {
        let fixture = Fixture::new();
        fs::write(fixture.plan.prefix.join(member), b"damaged").unwrap();
        assert!(
            fixture.verify(&mut fixture.observation("")).is_err(),
            "{member}"
        );
    }
}

#[test]
fn no_op_requires_exact_ready_anchors_before_native_observation() {
    for defect in [
        "pending",
        "removing",
        "desktop",
        "registration",
        "manifest",
        "owner",
    ] {
        let mut fixture = Fixture::new();
        match defect {
            "desktop" => fixture.plan.desktop_present = true,
            "manifest" => fixture.plan.manifest_sha256 = Sha256Digest::new("b".repeat(64)).unwrap(),
            "owner" => fixture.owner = fixture.registration.clone(),
            _ => {
                let path = fixture
                    .plan
                    .prefix
                    .join("data/installation-state/state.json");
                let mut value: serde_json::Value =
                    serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
                if defect == "registration" {
                    value["registration"]["phase"] = json!("removing");
                } else {
                    value["versions"]["1.0.0"]["phase"] = json!(defect);
                }
                fs::write(path, serde_json::to_vec(&value).unwrap()).unwrap();
            }
        }
        let mut observation = fixture.observation("");
        assert!(fixture.verify(&mut observation).is_err(), "{defect}");
        assert!(observation.calls.is_empty(), "{defect}");
    }
}
