# Fabrication: OpenPNP

The basic usage of this exporter is:
```
kikit fab openpn [OPTIONS] BOARD OUTPUTDIR
```

This exporter creates a single file `components.pos` that mimics KiCAD native
`.pos` output. However, unlike KiCAD, it adds a unique identifier to component
references to ensure they are unique (in the case of panels).
