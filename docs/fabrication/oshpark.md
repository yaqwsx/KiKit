# Fabrication: OSH Park

The basic usage of this exporter is:
```
kikit fab oshpark [OPTIONS] BOARD OUTPUTDIR
```

When you run this command, you will find `gerbers.zip` in `OUTPUTDIR`. This file
can be directly uploaded to the OSH Park site. KiKit automatically detects the
number of layers.

If you want to name your files differently, you can specify `--nametemplate`.
The extension is appended automatically.
