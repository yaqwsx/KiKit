# Fabrication

KiKit offers fully automatic export of all data required for fabrication of your
designs. Since every fabrication house has different requirements on the design
files (e.g., special names of gerber files, different requirements for assembly
files) there is no "universal exporter" in KiKit. Instead, KiKit offers special
command for each supported fabrication house.

## Common Options

All fab subcommands has a common invocation structure:

```
kikit fab <fabhouse> <options> <sourceDir> <outputDir>
```

All commands also support the following options:

- `--drc\--no-drc` (default `--drc`). Check for DRC violations before exporting
  the files. With this options, you won't send a board that fails DRC to your
  manufacturer.
- `--nametemplate <str>`:  If you want to name your files differently, specify
  this option. This option takes a string that should contain `{}`. This string
  will be replaced by `gerber`, `pos` or `bom` in the out file names. The
  extension is appended automatically. [Variables in
  text](../panelization/cli.md#available-variables-in-text) are also supported
  eg: `{boardTitle}_rev{boardRevision}_{date}_{}`. The project variables are
  available with the `user-` prefix; e.g., `MFR: {user-mfr}```

Each of the fab command also take additional, manufacturer specific, options.
See documentation for the individual manufacturer below:

## Currently Supported:

Note: click on the name of the manufacturer to see corresponding documentation:

- [JLC PCB](jlcpcb.md): board manufacturing, SMD assembly. [https://jlcpcb.com/](https://jlcpcb.com/)
- [PCBWay](pcbway.md): board manufacturing, assembly. [https://www.pcbway.com/](https://www.pcbway.com/)
- [OSH Park](oshpark.md): board manufacturing. [https://oshpark.com/](https://oshpark.com/)
- [Neoden YY1](neodenyy1.md): desktop PCB assembly. [https://neodenusa.com/neoden-yy1-pick-place-machine](https://neodenusa.com/neoden-yy1-pick-place-machine)
- [OpenPNP](openpnp.md): Open system for pick'n'place machines. [https://openpnp.org/](https://openpnp.org/)

## Adding New Fabrication Houses

To add a new fabrication command you have to extend KiKit's source code. A
rather basic knowledge of python is required to do so.

Create a new file `kikit/fab/fabhousename.py` and implement a new command with
the same name as the file. Then add the command to `kikit/fab/__init__.py`. The
common functionality for all fabrication houses should be located in
`kikit/fab/common.py`. You can use `kikit/fab/jlcpcb.py` for inspiration.

Once you implement a support for new fabrication house, open a pull request on
KiKit's GitHub page.
