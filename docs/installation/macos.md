# KiKit Installation on MacOS

Installation on MacOS is a little more involved as MacOS enforces that all
external programs are signed. KiCAD installed via homebrew is signed, however,
once plugins with binary dependencies are installed, the signature gets
invalidated. This prevents KiKit from running.

The current solution is to re-sign KiCAD after KiKit installation. Therefore,
KiKit's installation on MacOS is twofold:
- create a self-signed certificate
- install KiKit and sign KiCAD

## Create a codesigning certificate

Open Keychain a select "Create a Certificate":

![](../resources/key-1.png)

Then, enter name "kikit", select "Self-Signed Root" and type "Code Signing":

![](../resources/key-2.png)

Confirm and the certificate is ready.

## Install KiKit & related wrappers

We provide a script for KiKit installation's, KiCAD signing and creating a
wrapper script for KiKit. You can find [the script
here](https://raw.githubusercontent.com/yaqwsx/KiKit/master/scripts/installMacOS.bash).
You can download and run it. Open a terminal and enter:

```.bash
$ curl -O https://raw.githubusercontent.com/yaqwsx/KiKit/master/scripts/installMacOS.bash
$ sudo bash installMacOS.bash
```

The script will ask you for a password several times. Once it finishes, you can
test it:

```.bash
$ kikit --help
Usage: python3 -m kikit.ui [OPTIONS] COMMAND [ARGS]...

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

Once you install the PCM plugin, KiKit will be available via GUI in Pcbnew.
