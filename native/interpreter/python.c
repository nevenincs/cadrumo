#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#define BRIDGE_EXPORT __declspec(dllexport)
#define BRIDGE_CALL __cdecl
#define BRIDGE_CHAR wchar_t
#define SET_ARGV PyConfig_SetArgv
#define SET_STRING PyConfig_SetString
#define ENCODING L"utf-8"
#define ISATTY _isatty
#define FILENO _fileno
#else
#include <unistd.h>
#define BRIDGE_EXPORT __attribute__((visibility("default")))
#define BRIDGE_CALL
#define BRIDGE_CHAR char
#define SET_ARGV PyConfig_SetBytesArgv
#define SET_STRING PyConfig_SetBytesString
#define ENCODING "utf-8"
#define ISATTY isatty
#define FILENO fileno
#endif
#include "contract.h"
#include "build_metadata.h"

#if defined(Py_DEBUG) || defined(Py_GIL_DISABLED)
#error "The packaged interpreter requires the release, GIL-enabled CPython ABI"
#endif

BRIDGE_EXPORT int BRIDGE_CALL cadrumo_python_main(int argc, BRIDGE_CHAR **argv, const BRIDGE_CHAR **paths, int development) {
    if (strcmp(PY_VERSION, CADRUMO_PYTHON_VERSION) != 0 ||
        strncmp(Py_GetVersion(), CADRUMO_PYTHON_VERSION " ", sizeof(CADRUMO_PYTHON_VERSION)) != 0) {
        fprintf(stderr, "CADRUMO: incompatible bundled CPython; expected %s, headers %s, runtime %s\n",
            CADRUMO_PYTHON_VERSION, PY_VERSION, Py_GetVersion());
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
    config.site_import = 1;
    config.user_site_directory = 0;
    config.write_bytecode = 0;
    config.safe_path = 1;
    config.module_search_paths_set = 1;
#define CHECK(expr) do { status = (expr); if (PyStatus_Exception(status)) goto fail; } while (0)
    CHECK(SET_ARGV(&config, argc, argv));
    CHECK(PyConfig_Read(&config));
    int banner = !config.quiet && !config.run_command && !config.run_module && !config.run_filename
        && ISATTY(FILENO(stdin));
    if (banner) config.quiet = 1;
    /* Reassert reserved policy after parsing Python invocation options. */
    config.isolated = 1;
    config.use_environment = 0;
    config.user_site_directory = 0;
    config.write_bytecode = 0;
    config.safe_path = 1;
    CHECK(SET_STRING(&config, &config.program_name, paths[2]));
    CHECK(SET_STRING(&config, &config.stdio_encoding, ENCODING));
    CHECK(SET_STRING(&config, &config.executable, paths[2]));
    CHECK(SET_STRING(&config, &config.base_executable, paths[2]));
    CHECK(SET_STRING(&config, &config.home, paths[0]));
    CHECK(SET_STRING(&config, &config.prefix, paths[0]));
    CHECK(SET_STRING(&config, &config.base_prefix, paths[0]));
    CHECK(SET_STRING(&config, &config.exec_prefix, paths[0]));
    CHECK(SET_STRING(&config, &config.base_exec_prefix, paths[0]));
    for (int i = 3; i <= 5; ++i) {
#ifdef _WIN32
        CHECK(PyWideStringList_Append(&config.module_search_paths, paths[i]));
#else
        wchar_t *decoded = Py_DecodeLocale(paths[i], NULL);
        if (!decoded) {
            status = PyStatus_Error("Cannot decode package path");
            goto fail;
        }
        status = PyWideStringList_Append(&config.module_search_paths, decoded);
        PyMem_RawFree(decoded);
        if (PyStatus_Exception(status)) goto fail;
#endif
    }
    CHECK(Py_InitializeFromConfig(&config));
    PyConfig_Clear(&config);
    PyObject *build = Py_BuildValue("{s:s,s:s,s:s,s:i}", "version", CADRUMO_VERSION,
        "build_number", CADRUMO_BUILD_NUMBER, "build_date", CADRUMO_BUILD_DATE, "development", development);
    if (!build || PySys_SetObject("cadrumo_build", build) < 0) {
        Py_XDECREF(build);
        PyErr_Print();
        Py_FinalizeEx();
        return 124;
    }
    Py_DECREF(build);
    if (PyRun_SimpleString("import _cadrumo_bootstrap\n_cadrumo_bootstrap.install()\ndel _cadrumo_bootstrap\n") != 0) {
        Py_FinalizeEx();
        return 122;
    }
    if (banner) fprintf(stderr, "CADRUMO %s build %s (%s), Python %s [%s]\n",
        CADRUMO_VERSION, CADRUMO_BUILD_NUMBER, CADRUMO_BUILD_DATE, CADRUMO_PYTHON_VERSION,
        development ? "development" : "production");
    return Py_RunMain();
fail:
    PyConfig_Clear(&config);
    if (PyStatus_IsExit(status)) return status.exitcode;
    Py_ExitStatusException(status);
}
