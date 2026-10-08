#define _POSIX_C_SOURCE 200809L
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cadrumo_platform.h"
#include "contract.h"
#include "build_metadata.h"
#include "launch_guard.h"

#ifndef CADRUMO_DEVELOPMENT
#define CADRUMO_DEVELOPMENT 0
#endif
#ifndef CADRUMO_ENTRYPOINT
#include "invocation.h"
#endif

typedef int (*bridge_main)(int, char **, const char **, int);
extern char **environ;

static char *path(cadrumo_context *ctx, uint32_t key) {
    cadrumo_buffer value = {0};
    if (cadrumo_platform_path(ctx, key, &value)) return NULL;
    char *result = value.len < SIZE_MAX ? malloc((size_t)value.len + 1) : NULL;
    if (result) {
        memcpy(result, value.data, (size_t)value.len);
        result[value.len] = '\0';
    }
    cadrumo_platform_release(&value);
    return result;
}

static char *join(const char *directory, const char *name) {
    size_t a = strlen(directory), b = strlen(name);
    if (a > SIZE_MAX - b - 2) return NULL;
    char *value = malloc(a + b + 2);
    if (value) snprintf(value, a + b + 2, "%s/%s", directory, name);
    return value;
}

static void *load(const char *directory, const char *name, int flags) {
    char *filename = join(directory, name);
    if (!filename) return NULL;
    void *handle = dlopen(filename, RTLD_NOW | flags);
    if (!handle) fprintf(stderr, "CADRUMO: cannot load bundled %s: %s\n", name, dlerror());
    free(filename);
    return handle;
}

int main(int argc, char **argv) {
    /* Refusal cannot undo loader injection that happened before main. */
    for (char **item = environ; *item; ++item) {
        if (!strncmp(*item, "LD_", 3) || !strncmp(*item, "DYLD_", 5)) {
            fprintf(stderr, "CADRUMO: inherited dynamic-loader controls are not permitted\n");
            return 120;
        }
    }
    cadrumo_context *ctx = NULL;
    cadrumo_launch_guard *version_guard = NULL;
    cadrumo_buffer error = {0};
    char *paths[CADRUMO_PATH_KEYS] = {0};
    int result = 120;
    if (cadrumo_platform_abi() != CADRUMO_PLATFORM_ABI ||
        cadrumo_platform_create(CADRUMO_PLATFORM_ABI, &ctx, &error)) goto failure;
    for (uint32_t i = 0; i < CADRUMO_PATH_KEYS; ++i) {
        paths[i] = path(ctx, i);
        if (!paths[i]) goto failure;
    }
    if (!acquire_launch_guard(ctx, &version_guard)) {
        fprintf(stderr, "CADRUMO: installed package is unavailable for launch\n");
        goto done;
    }
#ifndef CADRUMO_ENTRYPOINT
    if (argc == 2 && (!strcmp(argv[1], "--version") || !strcmp(argv[1], "-V"))) {
        printf("CADRUMO %s build %s (%s), Python %s [%s]\n", CADRUMO_VERSION,
            CADRUMO_BUILD_NUMBER, CADRUMO_BUILD_DATE, CADRUMO_PYTHON_VERSION,
            CADRUMO_DEVELOPMENT ? "development" : "production");
        result = 0;
        goto done;
    }
#endif
    /* libpython must export symbols to subsequently loaded extension modules. */
    if (!load(paths[5], CADRUMO_RUNTIME, RTLD_GLOBAL)) goto done;
    void *bridge = load(paths[5], CADRUMO_BRIDGE, RTLD_LOCAL);
    if (!bridge) goto done;
    bridge_main run = (bridge_main)dlsym(bridge, "cadrumo_python_main");
    if (!run) goto failure;
#ifdef CADRUMO_ENTRYPOINT
    if (cadrumo_platform_prepare(ctx, &error)) goto failure;
    char *interpreter = join(paths[0], CADRUMO_EXECUTABLE);
    char **forwarded = calloc((size_t)argc + 3, sizeof(char *));
    if (!interpreter || !forwarded) {
        free(interpreter);
        free(forwarded);
        goto failure;
    }
    free(paths[2]);
    paths[2] = interpreter;
    forwarded[0] = interpreter;
    forwarded[1] = "-c";
    forwarded[2] = "import _cadrumo_bootstrap; _cadrumo_bootstrap.run_entrypoint('" CADRUMO_ENTRYPOINT "')";
    for (int i = 1; i < argc; ++i) forwarded[i + 2] = argv[i];
    result = run(argc + 2, forwarded, (const char **)paths, CADRUMO_DEVELOPMENT);
    free(forwarded);
#else
    /* The KDF worker attests its parent's neutral environment before reading requests. */
    if (!supervised_kdf_invocation(argc, argv) && cadrumo_platform_prepare(ctx, &error)) goto failure;
    if (argc == 2 && !strcmp(argv[1], "--check-package")) {
        char *check[] = {argv[0], "-c", "import _cadrumo_bootstrap; _cadrumo_bootstrap.verify(full=True); print('CADRUMO package verified')", NULL};
        result = run(3, check, (const char **)paths, CADRUMO_DEVELOPMENT);
    } else {
        result = run(argc, argv, (const char **)paths, CADRUMO_DEVELOPMENT);
    }
#endif
    goto done;
failure:
    if (error.data) fprintf(stderr, "CADRUMO: %.*s\n", (int)error.len, error.data);
    else fprintf(stderr, "CADRUMO: native bootstrap failed\n");
done:
    /* Keep the single version guard alive through loader destructors and exit.
     * The kernel closes its lease descriptor when this process finishes. */
    cadrumo_platform_release(&error);
    cadrumo_platform_destroy(ctx);
    for (int i = 0; i < CADRUMO_PATH_KEYS; ++i) free(paths[i]);
    return result;
}
