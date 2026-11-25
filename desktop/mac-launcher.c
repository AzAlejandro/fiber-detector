#include <mach-o/dyld.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char path[PATH_MAX], resolved[PATH_MAX], python[PATH_MAX], script[PATH_MAX];
    uint32_t length = sizeof path;
    if (_NSGetExecutablePath(path, &length) || !realpath(path, resolved)) return 1;
    char *macos = dirname(resolved);
    snprintf(python, sizeof python, "%s/../Resources/runtime/bin/python3.12", macos);
    snprintf(script, sizeof script, "%s/../Resources/launch.py", macos);
    char **args = calloc(argc + 2, sizeof *args);
    if (!args) return 1;
    args[0] = python;
    args[1] = script;
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);
    for (int i = 1; i < argc; ++i) args[i+1] = argv[i];
    execv(python, args);
    perror("LOCO");
    return 1;
}
