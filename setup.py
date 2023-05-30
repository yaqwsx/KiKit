# -*- coding: utf-8 -*-

import setuptools
import versioneer
import os
import sys

# Some packages on Linux for v7 change the location of the pcbnew module, let's
# add the new location to path:
import os
if os.name != "nt":
    sys.path.append("/usr/lib/kicad/lib/python3/dist-packages")
    try:
        from ctypes import cdll
        cdll.LoadLibrary("/usr/lib/kicad/lib/x86_64-linux-gnu/libkicad_3dsg.so.2.0.0")
    except Exception:
        pass # Ignore any errors as the library just might not exists here

try:
    import pcbnew
except ImportError:
    if os.name == "nt":
        message = "No Pcbnew Python module found.\n" + \
                  "Please make sure that you use KiCAD command prompt, " + \
                  "not the standard Command Prompt or Power Shell\n" + \
                  "See https://github.com/yaqwsx/KiKit/blob/master/doc/installation.md#installation-on-windows"
    else:
        message = "No Pcbnew Python module found for the current Python interpreter.\n" + \
                  "First, make sure that KiCAD is actually installed\n." + \
                  "Then, make sure that you use the same Python interpreter as KiCAD uses.\n" + \
                  "Usually a good way is to invoke 'python3 -m pip install kikit'."
    delimiter = 100 * "=" + "\n" + 100 * "=" + "\n"
    sys.stderr.write(
        delimiter + f"** Cannot install KiKit**\n{message}\n" + delimiter)
    raise RuntimeError("Cannot install KiKit, see error message above") from None
except AttributeError:
    raise RuntimeError("KiCAD v5 is no longer supported for KiKit. Version v1.0.x is the last one that supports KiCAD 5.")

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="KiKit",
    python_requires='>=3.7',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="Jan Mrázek",
    author_email="email@honzamrazek.cz",
    description="Automation for KiCAD boards",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yaqwsx/KiKit",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "numpy", # Required for MacOS
        "pcbnewTransition >= 0.3.4, <=0.4",
        "shapely>=1.7,<2.0",
        "click>=7.1",
        "markdown2>=2.4",
        "pybars3>=0.9",
        "solidpython>=1.1.2",
        "commentjson>=0.9"
    ],
    setup_requires=[
        "versioneer"
    ],
    extras_require={
        "dev": ["pytest"],
    },
    zip_safe=False,
    include_package_data=True,
    entry_points = {
        "console_scripts": [
            "kikit=kikit.ui:cli",
            "kikit-info=kikit.info:cli"
        ],
    }
)
