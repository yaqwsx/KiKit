# How are tabs in KiKit created?

When KiKit generates a tab, it generates it based on tab origin and direction.
When a tab is successfully generated, it consists out of two components - a
piece of a substrate (which will be later appended to the panel) and a cut-line.

So assume we have the following PCB outline (the PCB is below the line, there is
a free space above the line):

![tabdrawing1](https://user-images.githubusercontent.com/1590880/106768839-a22f1e80-663c-11eb-8d03-06df811943cc.png)

Then you specify your tab origin and its direction:

![tabdrawing2](https://user-images.githubusercontent.com/1590880/106768894-b1ae6780-663c-11eb-89a9-62227161a0db.png)

This is your input. Now KiKit does its job; it shoots two rays `tabWidth` apart
and looks for the intersection with existing substrates. Note that if the ray
starts within the PCB, no intersection will be found.

![tabdrawing3](https://user-images.githubusercontent.com/1590880/106768902-b541ee80-663c-11eb-825c-7a498cf6da84.png)

Once we have the intersections, we can easily generate the tab substrate and the
cut:

![tabdrawing4](https://user-images.githubusercontent.com/1590880/106768934-bd9a2980-663c-11eb-916c-4b6bf5623822.png)

This is the basic algorithm for generating tabs. Well, we might also call them
"half tabs". KiKit usually generates the half tabs around the board bounding box
and then expects that two half tabs in the middle of the panel will merge into a
single one. Also, KiKit first generates all the tabs and then merges them in one
step to the board substrate. The cut is just a polyline which is in later steps
either rendered as a V-cut or via mousebites.