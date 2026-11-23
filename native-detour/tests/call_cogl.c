#include <stdio.h>
int cogl_color_from_string(void *, const char *);

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    char out[64] = {0};
    if (!cogl_color_from_string(out, argv[1])) return 3;
    puts(out);
    return 0;
}
