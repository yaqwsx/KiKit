# Frequently Asked Questions

## KiKit throws away components from my panel, how can I prevent it?

KiKit respects the KiCAD component selection criteria. When you specify an input
rectangle, only the components that **fully fit** inside the input rectangle are
selected. This however take in account **both name and value labels** (even when
they are hidden).

When you do not specify the source are explicitly, KiKit takes the board outline
bounding box as the source area. Therefore, by default, components outside the
board substrate are not copied to panel.

Note that this is intended behavior; for once it is consistent with KiCAD
behavior of user selection and also it allows to easily ignore surrounding
comments and drawings in the board sheet (it makes no sense to have 12 same
copies of the notes around the board).

How to include the components?
- specify the source area explicitly to include all your components
- specify `--tolerance 10` to enlarge the board outline bounding box by e.g. 10
  mm. The default value is 5 mm.

## My milled slots are gone! How can I preserve them?

KiKit's `--radius` parameter simulates the board outline milling by a tool with
given radius. That means that it will round all inner corners. It is not a
command to round just your tabs. That means if you specify a tool which diameter
is larger than your slot, KiKit will remove the slot as such slot cannot be
created with the tool.

This is an intended behavior. The options is designed for you to check if your
board can be manufactured with all the features you have in your board outline.
There aren't many fabrication houses that support sharp inner corners as they
cannot be milled but have to be e.g., broached, which is much more complicated
and expensive setup.

If you want to preserve your narrow internal slots:
- don't specify `--radius` at all
- specify smaller `--radius` but make sure that your fabrication house supports
  such small tools.