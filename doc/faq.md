# Frequently Asked Questions

## KiKit throws away components from my panel, how can I prevent it?

KiKit respects the KiCAD component selection criteria. When you specify an input
rectangle, only the components that **fully fit** inside the input rectangle are
selected. This however take in account **both name and value labels**.

When you do not specify the source are explicitly, KiKit takes the board outline
bounding box as the source area. Therefore, by default, components outside the
board substrate are not copied to panel.

Note that this is intended behavior; for once it is consistent with KiCAD
behavior of user selection and also it allows to easily ignore surrounding
comments and drawings in the board sheet (it makes no sense to have 12 same
copies of the notes around the board).

How to include the components?
- specify the source area explicitly to include all your components
- specify `tolerance: 20mm` for `source` (i.e., `--source 'tolerance: 20mm'`) to
  enlarge the board outline bounding box. The default value is 5 mm.

## I rotated my board in a panel and the component references did not rotate.

KiCAD, more precisely Pcbnew, has a feature for component references "Keep
upright". When this option is on, the label will turn so it is always upright
ignoring the component orientation. If you wish to preserve your references
orientation even when you rotate the board, uncheck this option in reference
properties.

## My milled slots are gone! How can I preserve them?

KiKit's `millradius` parameter from the `postprocess` section simulates the
board outline milling by a tool with given radius. That means that it will round
all inner corners. It is not a command to round just your tabs. That means if
you specify a tool which diameter is larger than your slot, KiKit will remove
the slot as such slot cannot be created with the tool.

This is an intended behavior. The options is designed for you to check if your
board can be manufactured with all the features you have in your board outline.
There aren't many fabrication houses that support sharp inner corners as they
cannot be milled but have to be e.g., broached, which is much more complicated
and expensive setup.

If you want to preserve your narrow internal slots:
- don't specify `millradius` at all in the `postprocess`
- specify smaller `millradius` but make sure that your fabrication house
  supports such small tools.

## My mouse bites are inside the board, what should I do about it?

KiKit's mouse bites offset specifies how much should be the mouse bites put
**inside** the board. The recommended value is 0.25 mm (read about it [in this
blog
post](https://web.archive.org/web/20150415040424/http://blogs.mentor.com/tom-hausherr/blog/tag/mouse-bite/)).
Why is it so? When you break the tab, there will be rough edges. By putting the
mouse bites inside the board, these rough edges won't be sticking outside the
designed board outline. When you want to fit your board in a tight enclosure,
you don't have to perform manual deburing. Since it is considered a good
practice, KiKit makes this the positive direction so you don't have to put minus
everywhere.

If you don't want to put mouse bites inside your board, just specify zero or
negative offset.

## I get error `ModuleNotFoundError: No module named 'pcbnew'`

See the following question

## I want to use KiKit on Windows and I get various errors

Unfortunately, KiCAD includes it's own version of Python interpreter on Windows.
That means that the `pcbnew` module is not installed for your system Python
installation. The KiCAD's Python does not allow to install libraries with binary
dependencies, therefore you cannot install KiKit in it.

I have plans for solving this issue, unfortunately, I cannot implement them
until KiCAD on Windows migrate to Python 3 which should come with 6.0 release.

Until then you have two options to use KiKit on Windows:
- use the pre-built [Docker image](https://hub.docker.com/r/yaqwsx/kikit) with KiKit
- install KiCAD and KiKit inside [WSL](https://docs.microsoft.com/en-us/windows/wsl/about)

Both of these procedures are described in the [installation
document](installation.md).

## I would like to make a panel out of different designs, but there is no such option in help

KiKit supports such feature. But it is not available from CLI. You have to write
a simple Python script describing the panel and use KiKit as a library. An
example of such a script can be found
[here](https://github.com/RoboticsBrno/RB0002-BatteryPack/blob/baa010a6cda7d175eb96d8e656043b8ac2444515/scripts/panelizeBattery.py).
Also, please refer to the [panelization
documentation](https://github.com/yaqwsx/KiKit/blob/master/doc/panelization.md).

If you wonder why is it in such way: there are infinitely many ways to panel
your design. A single CLI/UI will not fit them all and also even for the simple
cases, it would be enormous and painful to use. Much better idea is to use a
language to specify the panel. But why reinvent the wheel and design a custom
language when we can use Python? It integrates well with other tools and many
people already know it.

## There are no plugins in KiCAD!

You have to enable them. See [the installation guide](installation.md).

## How do I run KiKit with KiCAD nightly?

See section "Choosing KiCAD version" in [the installation
guide](installation.md).
