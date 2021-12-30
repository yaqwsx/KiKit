# -*- coding: utf-8 -*-

import setuptools
import versioneer



with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="KiKit",
    python_requires='>3.7',
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
        "pcbnewTransition==0.2.0",
        "numpy>=1.21",
        "shapely>=1.7",
        "click>=7.1",
        "markdown2>=2.4",
        "pybars3>=0.9",
        "solidpython>=1.1",
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
            "kikit-plugin=kikit.plugin:cli",
            "kikit-info=kikit.info:cli"
        ],
    }
)