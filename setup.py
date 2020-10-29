# -*- coding: utf-8 -*-

import setuptools
from setuptools.command.install import install
from setuptools.command.develop import develop
import versioneer
import platform
import os
import shutil
from pathlib import Path

def checkPlatform():
    if platform.system() != "Linux":
        raise RuntimeError(
        """
        KiKit can currently run only on Linux. If you use MacOS or Windows,
        please use WSL or Docker. More information at
        https://github.com/yaqwsx/KiKit/blob/master/doc/installation.md
        """)

class InstallWrapper(install):
    """
    Provides install wrapper which:
    - stops installation if we are not running on Linux
    - register KiCAD action plugin
    """
    def run(self):
        checkPlatform()
        self._registerPlugin()
        install.run(self)

    def _registerPlugin(self):
        if os.geteuid() == 0:
            # Use system-wide location
            location = "/usr/share/kicad/scripting/plugins/"
        else:
            # Use local location
            location = str(Path.home()) + "/.kicad_plugins/"
        Path(location).mkdir(exist_ok=True)
        location += "kikit_plugin.py"
        shutil.copy("scripts/kikit_plugin.py", location)

class DevelopWrapper(develop):
    """
    Provides develop wrapper which:
    - stops installation if we are not running on Linux
    - register KiCAD action plugin
    """
    def run(self):
        if os.geteuid() == 0:
            raise RuntimeError("Develop should be as a non-prvilleged user")
        checkPlatform()
        self._registerPlugin()
        develop.run(self)

    def _registerPlugin(self):
        location = str(Path.home()) + "/.kicad_plugins"
        Path(location).mkdir(exist_ok=True)
        location += "kikit_plugin.py"
        try:
            os.remove(location)
        except OSError:
            pass
        os.symlink("scripts/kikit_plugin.py", location)

with open("README.md", "r") as fh:
    long_description = fh.read()

cmdclass = versioneer.get_cmdclass()
cmdclass.update({
    "install": InstallWrapper,
    "develop": DevelopWrapper
})

setuptools.setup(
    name="KiKit",
    version=versioneer.get_version(),
    cmdclass=cmdclass,
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
        "numpy",
        "shapely",
        "click",
        "markdown2",
        "pybars3",
        "solidpython"
    ],
    setup_requires=[
        "versioneer"
    ],
    zip_safe=False,
    include_package_data=True,
    entry_points = {
        "console_scripts": [
            "kikit=kikit.ui:cli"
        ],
    }
)