import pcbnew
print("Plugin should be registered")
from kikit.plugin.hideReferences import HideReferencesPlugin

HideReferencesPlugin().register()

