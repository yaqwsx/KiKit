# This has nothing to do with KiKit plugins, instead, it is the registration
# routine for Action plugins. However, the original implementation used the name
# 'plugin'. In order not to break the existing PCM installations we import this
# and leave it here for at least a couple of months to ensure that everybody
# upgrades to a new PCM package.
from kikit.actionPlugins import importAllPlugins
