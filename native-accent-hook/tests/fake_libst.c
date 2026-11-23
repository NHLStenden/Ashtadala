/* Minimal fake St shared object with both expected original literal and PLT call. */
extern int cogl_color_from_string(void *, const char *);
int fake_st_theme_init(void *out)
{
    return cogl_color_from_string(out, "#6f8396");
}
