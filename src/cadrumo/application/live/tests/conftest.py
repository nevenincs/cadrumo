from ....adapters.persistence.tests.runtime_profile_fixture import default_bucket_runtime_profile_fixture

#: Explicitly requested, never autouse: only three of this directory's test
#: modules want a runtime, and a conftest fixture made autouse would install one
#: for every test beside them. The body is shared; the reach stays declared here.
secure_engine = default_bucket_runtime_profile_fixture(autouse=False, name="secure_engine")
