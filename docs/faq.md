---
hide:
  - navigation
---

# Frequently Asked Questions

## KiKit throws away components from my panel, how can I prevent it?

KiKit respects the KiCAD component selection criteria. When you specify an input
rectangle, only the components that **fully fit** inside the input rectangle are
selected. This however take in account **both name and value labels**.

When you do not specify the source are explicitly, KiKit takes the board outline
bounding box as the source area. Therefore, by default, components outside the
board substrate are not copied to panel.

**Since version 1.1 this behavior, however, changes for footprints**. KiKit
decides whether to keep a footprint or not based on whether its origin fits
inside the source area or not. For graphical items, the behavior remains the
same. The reason for this change is that often footprints reach out beyond the
board edge (e.g., connectors) and the users don't want to remove them. On the
other hand, graphical items (e.g., texts or arrows towards the board) are purely
for documentation purposes and thus, they shouldn't be included in the panelized
design.

Note that this is intended behavior; for once it is consistent with KiCAD
behavior of user selection and also it allows to easily ignore surrounding
comments and drawings in the board sheet (it makes no sense to have 12 same
copies of the notes around the board).

How to include the components?
- specify the source area explicitly to include all your components
- specify `tolerance: 20mm` for `source` (i.e., `--source 'tolerance: 20mm'`) to
  enlarge the board outline bounding box. The default value is 1 mm.

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

## I have board with no spacing, but some V-cuts are missing.

The default style of tabs (`spacing`) does not generate in such a case any tabs,
and, therefore, not cuts. Please use tab style `full`.

## I get error `ModuleNotFoundError: No module named 'pcbnew'`

You probably installed KiKit via Windows command prompt, not KiCAD Command
Prompt.

## I would like to make a panel out of different designs, but there is no such option in help

KiKit supports such feature. But it is not available from CLI. You have to write
a simple Python script describing the panel and use KiKit as a library. Also,
please refer to the [panelization documentation](panelization/intro.md).

If you wonder why is it in such way: there are infinitely many ways to panel
your design. A single CLI/UI will not fit them all and also even for the simple
cases, it would be enormous and painful to use. Much better idea is to use a
language to specify the panel. But why reinvent the wheel and design a custom
language when we can use Python? It integrates well with other tools and many
people already know it.

## There are no plugins in KiCAD!

You have to install them via KiCAD PCM. See [the installation
guide](installation/intro.md).

## How do I run KiKit with KiCAD nightly?

See section "Choosing KiCAD version" in [the installation
guide](installation/intro.md). However, at the moment KiKit is incompatible with KiCAD
6.99.
