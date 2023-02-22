## Installation on Windows

To install KiKit on Windows, you have to open "KiCAD Command Prompt". You can
find it in the start menu:

![KiCAD Command Prompt in Start menu](../resources/windowsCommandPrompt1.jpg)

Once you have it open like this:

![KiCAD Command Prompt in Start menu](../resources/windowsCommandPrompt2.jpg)

you can put command in there and confirm them by pressing
enter. This is also the prompt from which you will invoke all KiKit's CLI
commands. They, unfortunately, does not work in an ordinary Command prompt due
to the way KiCAD is packaged on Windows.

Then you have to enter the following command to install it:

```.bash
pip install kikit
```

Now you can test that it works:

```.bash
kikit --help
```

You should get something like this:

```
Usage: kikit [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  drc       Validate design rules of the board
  export    Export KiCAD boards
  fab       Export complete manufacturing data for given fabrication houses
  modify    Modify board items
  panelize  Panelize boards
  present   Prepare board presentation
  separate  Separate a single board out of a multi-board design.
  stencil   Create solder paste stencils
```

Now you are done with the basic installation. Don't forget to get the GUI
frontend and libraries via PCM.
