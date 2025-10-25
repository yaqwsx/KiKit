# -*- coding: utf-8 -*-

import setuptools
import versioneer

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="KiKit",
    python_requires='>=3.8', # if you bump this, be sure to also adjust the matrix in .github/workflows/test-kikit.yml
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
        "pcbnewTransition >= 0.5.2, <=0.6",
        "shapely>=2.0.3",
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
        "dev": [
            "pytest",
            "wheel",
        ],
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
