#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <string.h>
#include "contract.h"

__declspec(dllexport) int __cdecl cadrumo_python_main(int argc, wchar_t **argv, const wchar_t **paths) {
    if (strncmp(Py_GetVersion(), CADRUMO_PYTHON_VERSION " ", sizeof(CADRUMO_PYTHON_VERSION)) != 0) {
        fprintf(stderr, "CADRUMO: incompatible bundled CPython; expected %s, got %s\n",
            CADRUMO_PYTHON_VERSION, Py_GetVersion());
        return 121;
    }
    PyConfig config;
    PyStatus status;
    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) Py_ExitStatusException(status);
    PyConfig_InitIsolatedConfig(&config);
    config.parse_argv = 1;
    config.install_signal_handlers = 1;
    config.site_import = 0;
    config.user_site_directory = 0;
    config.write_bytecode = 0;
    config.safe_path = 1;
    config.module_search_paths_set = 1;
#define CHECK(expr) do { status = (expr); if (PyStatus_Exception(status)) goto fail; } while (0)
    CHECK(PyConfig_SetArgv(&config, argc, argv));
    CHECK(PyConfig_Read(&config));
    /* Reassert reserved policy after parsing Python invocation options. */
    config.isolated = 1;
    config.use_environment = 0;
    config.site_import = 0;
    config.user_site_directory = 0;
    config.write_bytecode = 0;
    config.safe_path = 1;
    CHECK(PyConfig_SetString(&config, &config.program_name, paths[2]));
    CHECK(PyConfig_SetString(&config, &config.stdio_encoding, L"utf-8"));
    CHECK(PyConfig_SetString(&config, &config.executable, paths[2]));
    CHECK(PyConfig_SetString(&config, &config.base_executable, paths[2]));
    CHECK(PyConfig_SetString(&config, &config.home, paths[0]));
    CHECK(PyConfig_SetString(&config, &config.prefix, paths[0]));
    CHECK(PyConfig_SetString(&config, &config.base_prefix, paths[0]));
    CHECK(PyConfig_SetString(&config, &config.exec_prefix, paths[0]));
    CHECK(PyConfig_SetString(&config, &config.base_exec_prefix, paths[0]));
    CHECK(PyWideStringList_Append(&config.module_search_paths, paths[3]));
    CHECK(PyWideStringList_Append(&config.module_search_paths, paths[4]));
    CHECK(PyWideStringList_Append(&config.module_search_paths, paths[5]));
    CHECK(Py_InitializeFromConfig(&config));
    PyConfig_Clear(&config);
    if (PyRun_SimpleString("import _cadrumo_bootstrap\n_cadrumo_bootstrap.install()\ndel _cadrumo_bootstrap\n") != 0) {
        Py_FinalizeEx();
        return 122;
    }
    return Py_RunMain();
fail:
    PyConfig_Clear(&config);
    if (PyStatus_IsExit(status)) return status.exitcode;
    Py_ExitStatusException(status);
    return 123;
}
