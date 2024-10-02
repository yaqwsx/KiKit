# Fabrication: JLC PCB

The basic usage of this exporter is:
```
kikit fab jlcpcb [OPTIONS] BOARD OUTPUTDIR
```

When you run this command, you will find file `gerbers.zip` in `OUTPUTDIR`. This
file can be directly uploaded to JLC PCB site. KiKit automatically detects the
number of layers.

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

It is possible that orientation footprints in your SMD does not match the
orientation of the components in the SMD assembly service. There are two
solutions:

- correct the orientation in the library or
- apply KiKit's orientation corrections.

The first option is not always feasible - e.g., when you use KiCAD's built-in
libraries or you are preparing a board for multiple fabrication houses and each
of them uses a different orientation.

KiKit allows you to specify the origin and orientation correction of the
position. The correction is specified by `JLCPCB_CORRECTION` field. The field
value is a semicolon separated tuple: `<X>; <Y>; <Rotation>` with values in
millimeters and degrees. You can read the XY corrections by hovering cursor over
the intended origin in footprint editor and mark the coordinates. Note that
first the rotation correction is applied, then the translation. Usually, you
will need only the rotation correction.

## Correction Pattern Files

Specifying corrections for individual components can quickly become tedious.
It is also possible to specify correction patterns using CSV files. The
correction pattern files have the following format:

```
"Pattern","X correction","Y correction","Rotation"
"^U101$",0,0,180
"^COS1333TR$",0,0,-90
":PinHeader_2x06_P2.54mm_",1.27,6.35,90
":SOIC-8_3.9x4.9mm_P1.27mm",0,0,-90
":VQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm",0,0,-90
":SS5U100_TO-277",0.8,0,0
":SOT-23",0,0,180
```

The X and Y correction values are in millimeters and refer to the
component footprint original orientation. The rotation correction is in degrees,
with positive values meaning counter-clockwise rotation.

The Pattern field is a regular expression that is matched against the
reference, value and footprint fields of the component (in this order). For
all footprints, the first matching pattern and field values are used. The
pattern is matched against the whole string, so you should use `^` and `$`
characters to match the beginning and the end of the string if you want to
match the whole string.

In the example above, the first row matches a specific component with
reference `U101`. The second row matches all components with value
`COS1333TR`. The following rows match all components with a given footprint.
For footprints, the pattern is matched against the whole footprint name,
including the library - for example, `Package_TO_SOT_SMD:SOT-23-5`. To only
match the name part, all footprint patterns in the example start with `:`.

## Using Corrections to Configure Jumpers

If your board features solder jumpers you can use the corrections to specify
their default value. The solder jumper should be designed such it can fit a zero
Ohm resistor in suitable size. Then specify an order code of the zero Ohm
resistor for the jumper and adjust correction so it fits the default position.

Note that you can specify multiple correction fields by `--corrections <comma
separated list of correction field names>`. The first found correction field is
used. This allows you to keep several configuration of the solder jumpers in
your design e.g., in fields `JLCPCB_CORRECTION_CFG_1` and
`JLCPCB_CORRECTION_CFG_2`. Then you can simply change the board configuration by
calling kikit with `--corrections JLCPCB_CORRECTION_CFG_1,JLCPCB_CORRECTION` or
`--corrections JLCPCB_CORRECTION_CFG_2,JLCPCB_CORRECTION`.



