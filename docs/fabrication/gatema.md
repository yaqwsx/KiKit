# Fabrication: Gatema PCB

The basic usage of this exporter is:
```
kikit fab gatema [OPTIONS] BOARD OUTPUTDIR
```

When you run this command, you will find file `gerbers.zip` in `OUTPUTDIR`. This
file can be directly uploaded to Gatema PCB site. KiKit automatically detects the
number of layers. If you would like to include the project name in the archive
name, you can supply `--autoname`

If you want to name your files differently, you can specify `--nametemplate`.
This option takes a string that should contain `{}`. This string will be
replaced by `gerber`, `pos` or `bom` in the out file names. The extension is
appended automatically.
