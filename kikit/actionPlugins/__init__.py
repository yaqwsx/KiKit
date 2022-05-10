from dataclasses import dataclass

@dataclass
class KiKitActionPlugin:
    package: str
    name: str
    description: str

availablePlugins = [
    KiKitActionPlugin("hideReferences", "Show/hide references",
        "Allows you to batch show or hide references based on regular expression"),
    KiKitActionPlugin("panelize", "Panelize design",
        "Allows you to specify panelization process via GUI")
]

def importAllPlugins():
    """
    Bring all plugins that KiKit offers into a the global namespace. This
    function is impure as it modifies the global variable scope. The purpose
    of this function is to allow the PCM proxy to operate.
    """
    import importlib

    for plugin in availablePlugins:
        module = importlib.import_module(f"kikit.actionPlugins.{plugin.package}")
        module.plugin().register()
