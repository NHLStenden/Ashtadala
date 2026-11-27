#include <stdio.h>
#include <string.h>
#include <unistd.h>
int cogl_color_from_string(void *, const char *);

int main(int argc, char **argv)
{
    if (argc != 2 && argc != 3) return 2;
    char out[64] = {0};
    if (!cogl_color_from_string(out, argv[1])) return 3;
    puts(out);
    if (argc == 3 && strcmp(argv[2], "exec-child") == 0) {
        if (fflush(stdout) != 0) return 4;
        execl(argv[0], argv[0], argv[1], (char *)NULL);
        return 5;
    }
    return 0;
}
