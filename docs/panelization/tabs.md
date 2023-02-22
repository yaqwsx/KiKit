# How are tabs in KiKit created?

When you place multiple PCB into the panel, KiKit expects you to generate a
so-called partition line for each individual PCB. Partition line is an oriented
(poly)line that partitions the free space between the PCBs. It gives you the
information "this part of the free space belongs to this PCB substrate and this
PCB is responsible for placing tabs in that space". So for a regular input
the partition line can look like this:

![partition1](../resources/partition1.svg)

For more complicated input, it can look like this:

![partition2](../resources/partition2.svg)

Note several facts:
- partition line is used for backbone generator
- partition line is not generated automatically, it is up to the user to
  generate it. KiKit offers `Panel.buildPartitionLineFromBB` that builds the
  partition line based on bounding boxes. If you need possibly a more
  complicated lines, you have to implement them by yourself.
- partition line is used for deciding if an annotation yields a tab or not - if
  the tab does not hit the partition line, it is not created.
- when we create partition line from bounding boxes, we include "ghost
  substrates" representing the framing, that will be added in the future.

When KiKit generates a tab, it generates it based on tab origin, direction and
optionally the partition line. When a tab is successfully generated, it consists
out of two components - a piece of a substrate (which will be later appended to
the panel) and a cut-line.

So assume we have the following PCB outline (the PCB is below the line, there is
a free space above the line):

![tabdrawing1](../resources/tabdrawing1.svg)

Then you specify your tab origin and its direction:

![tabdrawing2](../resources/tabdrawing2.svg)

This is your input (e.g., via an annotation). Now KiKit does its job; it shoots
two rays `tabWidth` apart and looks for the intersection with existing
substrates. Note that if the ray starts within the PCB, no intersection will be
found.

![tabdrawing3](../resources/tabdrawing3.svg)

Once we have the intersections, we can easily generate the tab substrate and the
cut:

![tabdrawing4](../resources/tabdrawing4.svg)

Note that if we specify a partition line, than we shoot new rays in the opposite
direction and try to hit the line. If we manage to do so, we get a tab.
Otherwise, no tab is generated.

![tabdrawing5](../resources/tabdrawing5.svg)

This is the basic algorithm for generating tabs. Well, we might also call them
"half tabs". KiKit usually generates the half tabs around the board bounding box
and then expects that two half tabs in the middle of the panel will merge into a
single one. Also, KiKit first generates all the tabs and then merges them in one
step to the board substrate. The cut is just a polyline which is in later steps
either rendered as a V-cut or via mousebites.
