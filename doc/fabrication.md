# Fabrication

KiKit offers fully automatic export of all data required for fabrication of your
designs. Since every fabrication house has different requirements on the design
files (e.g., special names of gerber files, different requirements for assembly
files) there is no "universal exporter" in KiKit. Instead, KiKit offers special
command for each supported fabrication house.

## Currently Supported:

Note: click on the name of the manufacturer to see corresponding documentation:

- [JLC PCB](fabrication/jlcpcb.md): board manufacturing, SMD assembly. [https://jlcpcb.com/](https://jlcpcb.com/)
- [PCBWay](fabrication/pcbway.md): board manufacturing, assembly. [https://www.pcbway.com/](https://www.pcbway.com/)

## Adding New Fabrication Houses

To add a new fabrication command you have to extend KiKit's source code. A
rather basic knowledge of python is required to do so.

Create a new file `kikit/fab/fabhousename.py` and implement a new command with
the same name as the file. Then add the command to `kikit/fab/__init__.py`. The
common functionality for all fabrication houses should be located in
`kikit/fab/common.py`. You can use `kikit/fab/jlcpcb.py` for inspiration.

Once you implement a support for new fabrication house, open a pull request on
KiKit's GitHub page.
