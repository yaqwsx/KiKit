# Automatic panelization with KiKit

KiKit panelization module is designed to:

- panelize arbirary shaped boards,
- build panels that need no further inspection, and
- create panels that pass DRC.

There are two ways of specifying a panel:

- there is a [CLI interface](cli.md) that should cover 98 % of use cases. It can
  create panels of a single design with the most common features. It allows you
  to build the panel specification out of predefined preset files. If built-in
  feature is insufficient, you can override it via [plugin](plugins.md). The features of the CLI are covered by [examples](examples.md). If you want, you can use [GUI](gui.md) to rapidly prototype KiKit presets.
- for the rest of the cases there is [Python API](python_api.md) where you use
  KiKit as a library in your panel building script. This is described in [the
  scripting](scripting.md) section. However, at the moment, there are no proper
  examples available.
