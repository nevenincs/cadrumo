#include <assert.h>
#include "../invocation.h"

int main(void) {
    char *argv[] = {"python", "-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker",
        "--request-fd", "3", "--result-fd", "4", "--descriptor-bound", "1024"};
    assert(supervised_kdf_invocation(9, argv));
    assert(!supervised_kdf_invocation(8, argv));
    argv[6] = "3";
    assert(!supervised_kdf_invocation(9, argv));
    argv[6] = "999999999999999999999999999";
    assert(!supervised_kdf_invocation(9, argv));
    argv[6] = "4";
    argv[8] = "4";
    assert(!supervised_kdf_invocation(9, argv));
    argv[8] = "1024";
    argv[4] = "0";
    assert(!supervised_kdf_invocation(9, argv));
    argv[4] = "03";
    assert(!supervised_kdf_invocation(9, argv));
    argv[4] = "3";
    argv[2] = "other.module";
    assert(!supervised_kdf_invocation(9, argv));
    return 0;
}
