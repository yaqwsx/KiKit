# Upgrading KiKit and installing special versions

## Upgrading KiKit

If you want to upgrade KiKit, you have to perform two steps:

- you upgrade the backend by running `pip install -U kikit` in the command line
  (depending on the platform, see the installation instructions for individual
  platform).
- then you can upgrade the PCM packages within KiCAD. Note that this step is
  often not needed. If it will be needed, the release notes will say so.

## Installing a special version of KiKit

If you would like to install a specific version of KiKit (e.g., the upstream
version), you can install it directly from git. The command for that is:

```.bash
# The master branch (also called the upstream version) - the most up-to-date KiKit there is (but might me unstable)
pip install https://github.com/yaqwsx/KiKit/archive/master.zip
# A concrete branch, e.g., from a pull request
pip3 install https://github.com/yaqwsx/KiKit/archive/someBranchName.zip
```


