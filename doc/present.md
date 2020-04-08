# Present

Present is a collection of functions providing various ways to present KiCAD
boards. The main one is a simple page generator which can be used in continuous
integration to build pages where your users and colleges can download the
automatically generated panels.

## Template name/path resolution

The template argument is either a name of built-it template or a path to a
directory with user-defined template. During name resolution the first test is
for user-defined template; i.e., check if name provided by user is a directory
path and the directory contains file `template.json`. If not, try to resolve the
name as a name of built-in template.

## What is a template?

Template is a directory containing template files. There is a single mandatory
file common to all template type `template.json`. Example of such file follows:

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

Expects an `index.html` file in the root of template. This is Handlerbars
template which on render receives the following dictionary:

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

See the default template in `kikit/resources/present/templates/default` for an
starting point for custom templates.
