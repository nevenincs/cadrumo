#ifndef CADRUMO_INTERPRETER_LAUNCH_GUARD_H
#define CADRUMO_INTERPRETER_LAUNCH_GUARD_H
#include "cadrumo_launch_guard.h"
#include "cadrumo_platform.h"

/* The platform context supplies the exact package of this image. No environment
 * flag or interpreter argument can turn installed maintenance into portable use. */
static int acquire_launch_guard(cadrumo_context *context, cadrumo_launch_guard **guard) {
    cadrumo_buffer package = {0};
    if (cadrumo_platform_path(context, 0, &package)) return 0;
    uint32_t status = cadrumo_launch_guard_acquire(package.data, (size_t)package.len, guard);
    cadrumo_platform_release(&package);
    return status == 0;
}
#endif
