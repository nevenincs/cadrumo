#include <assert.h>
#include <stdio.h>
#include "cadrumo_platform.h"
int main(void) {
    cadrumo_context *ctx = NULL;
    cadrumo_buffer error = {0}, path = {0};
    assert(cadrumo_platform_abi() == 1);
    assert(cadrumo_platform_create(2, &ctx, &error) == 1);
    assert(ctx == NULL && error.len > 0);
    cadrumo_platform_release(&error);
    assert(cadrumo_platform_create(1, &ctx, &error) == 0);
    assert(cadrumo_platform_path(ctx, 1, &path) == 0);
    printf("C consumer ABI 1: %.*s\n", (int)path.len, path.data);
    cadrumo_platform_release(&path);
    cadrumo_platform_release(&path);
    assert(cadrumo_platform_path(ctx, 99, &path) == 2);
    cadrumo_platform_destroy(ctx);
    return 0;
}
