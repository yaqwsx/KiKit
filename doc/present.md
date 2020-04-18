# Present

Present is a collection of functions providing various ways to present KiCAD
boards. The main one is a simple page generator which can be used in continuous
integration to build pages where your users and collagues can download the
automatically generated panels.

## Requirements

In order to include PCB drawings in presentations you will need to install
[PcbDraw](https://github.com/yaqwsx/PcbDraw).

## Template name/path resolution

The template argument is either a name of a built-it template or a path to a
directory with a user-defined template. During the name resolution the first
test is for the user-defined template; i.e., check if the name provided by the
user is a directory path and the directory contains the file `template.json`. If
not, try to resolve the name as the name of the built-in template.

## What is a template?

A template is a directory containing template files. There is a single mandatory
file common to all template types `template.json`. An example of such file follows:

```
{
    "type": "HtmlTemplate",
    "resources": ["css/*.css"]
}
```

The key `type` specifies what kind of template it is. Currently, only
`HtmlTemplate` is supported (see more info about them below). Then there is the
list of `resources` which are glob patterns for resource files which are copied
to the output directory when rendering the template.

### HtmlTemplate

Expects an `index.html` file in the root of the template. This is Handlerbars
template which receives the following dictionary on render:

```
"repo": self.repository,
"gitRev": gitRev,
"gitRevShort": gitRev[:7] if gitRev else None,
"datetime": self.currentDateTime(),
"name": self.name,
"boards": self.boards,
"description": self.description
```

`boards` is a list of a dictionary with following keys:

- `front` path to render of the front side
- `back` path to render of the back side
- `gerbers` path to archive with gerbers
- `file` path to `kicad_pcb` file

See the default template in `kikit/resources/present/templates/default` for a
starting point for custom templates.
