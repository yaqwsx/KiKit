# KiKit Plugins

To tweak the KiKit UI process it is possible to use plugins. Plugins are pieces
of Python code that provide some functionality. They can save you from writing a
custom panelization script from scratch when you only need a custom one of the steps during panelization.

## Specifying plugins

Some of the CLI options allow you to specify plugin. In such a case, one of the following formats is expected:

- `<packagename>.<pluginname>`, e.g., `ExternalPackage.CircleLayout`
- `<filename>.<pluginname>`, e.g., `localFile.py.CircleLayout`

All plugins, except text plugins, accept optional user text argument.

The plugins can be implemented and published as Python packages.

## Writing custom plugins

The plugins should be implemented by overriding one of the plugin types
specified in `../kikit/plugin.py`. Currently, the following plugin types are
supported:

- `HookPlugin` - this is a plugin that features a number of callback that are
  invoked during various stages of building the panel. You can tweak the panels in these callbacks.
- `LayoutPlugin` - this plugin implements a new layout of the boards in the
  panel.
- `FramingPlugin` - this plugin implements a new style of framing.
- `TabsPlugin` - this plugin implements a new style of tab placement.
- `CutsPlugin` - this plugin implements a new style of cut rendering.
- `ToolingPlugin` - this plugin implements a new style of tolling decoration.
- `FiducialsPlugin` - this plugin implements a new style of fiducials
  decoration.
- `TextVariablePlugin` - this plugins provides new variables for the text
  placement.

All plugins except `TextVariablePlugin` have attributes `self.preset` containing
the whole preset and `self.userArg` containing the string provided by the user.
