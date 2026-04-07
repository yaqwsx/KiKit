# Fabrication: JLC PCB

The basic usage of this exporter is:
```
kikit fab jlcpcb [OPTIONS] BOARD OUTPUTDIR
```

When you run this command, you will find file `gerbers.zip` in `OUTPUTDIR`. This
file can be directly uploaded to JLC PCB site. KiKit automatically detects the
number of layers. If you would like to include the project name in the archive
name, you can supply `--autoname`

If you want to name your files differently, you can specify `--nametemplate`.
This option takes a string that should contain `{}`. This string will be
replaced by `gerber`, `pos` or `bom` in the out file names. The extension is
appended automatically.

## Assembly

If you would also like to use the SMD assembly service, you have to specify
`--assembly` option and also provide the board `--schematic <schematics_file>`.
KiKit will generate two extra files: `bom.csv` (bill of materials) and `pos.csv`
(component placement). Use these two files when ordering the PCB assembly.

The files above will include all components on the board. You can override the
default field name with option `--field`. This option accepts a comma separated
list of names. The first found field is used. This can be used, e.g., for
configuration of the board via resistors. You can put field "LCSC" for all
components, then add fields "CFG1_LCSC" and "CFG2_LCSC" for some components.
Then invoke KiKit with option `--field CFG1_LCSC,LCSC` for configuration 1 or
`--field CFG2_LCSC,LCSC` for configuration 2.

You can exclude some of the components by specifying `--ignore <comma separated
list of references>`. You can also specify component field with name
`JLCPCB_IGNORE` (the value of the field does not matter) to exclude the
component from assembly. Also, if a component misses the order code field, KiKit
will show warning. When you pass option `--missingError`, KiKit will fail when
there is a component with missing order code. This might be useful in case when
you run KiKit in CI and you want to fail the build.

Note that when you order SMD assembly for a panel, you should specify panelized
board and the original schematics of a single board.

## Correction of the Footprint Position

It is possible that the orientation of footprints in your design does not match
the orientation expected by the SMD assembly service. There are two solutions:

- correct the orientation in the library or
- apply KiKit's orientation corrections.

The first option is not always feasible - e.g., when you use KiCAD's built-in
libraries or you are preparing a board for multiple fabrication houses and each
of them uses a different orientation.

KiKit allows you to specify the origin and orientation correction of the
position. Add `JLCPCB_CORRECTION` as a custom field on the **symbol in your
schematic**. The value will be read from the BOM data that KiKit extracts via the
`--schematic` option.

The field value is a semicolon separated tuple: `<X>;<Y>;<Rotation>` with values
in millimeters and degrees. **Rotation values are counterclockwise in degrees.**
For example, to rotate a component 90° clockwise, use `270` (or equivalently
`-90`). A value of `90` rotates 90° counterclockwise.

The X and Y correction values are in the **footprint's local coordinate system**
(relative to its current orientation on the board), not the board's global
coordinates. KiKit rotates the correction vector by the footprint's placement
angle before applying it. You can read the XY corrections by hovering cursor
over the intended origin in footprint editor and mark the coordinates. Usually,
you will need only the rotation correction.

**Example:** A component appears rotated 90° clockwise from what it should be
after JLCPCB assembly. To fix this, set `JLCPCB_CORRECTION` to `0;0;90`. This
applies a 90° counterclockwise correction, cancelling out the error. If the
component also needs a 1 mm X offset in its local frame, use `1;0;90`.

## Using Corrections to Configure Jumpers

If your board features solder jumpers you can use the corrections to specify
their default value. The solder jumper should be designed such it can fit a zero
Ohm resistor in suitable size. Then specify an order code of the zero Ohm
resistor for the jumper and adjust correction so it fits the default position.

Note that you can specify multiple correction fields by `--corrections <comma
separated list of correction filed names>`. The first found correction field is
used. This allows you to keep several configuration of the solder jumpers in
your design e.g., in fields `JLCPCB_CORRECTION_CFG_1` and
`JLCPCB_CORRECTION_CFG_2`. Then you can simply change the board configuration by
calling kikit with `--corrections JLCPCB_CORRECTION_CFG_1,JLCPCB_CORRECTION` or
`--corrections JLCPCB_CORRECTION_CFG_2,JLCPCB_CORRECTION`.



