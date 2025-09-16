import click
from pathlib import Path
import sys
import os
import json
import glob
import shutil
import subprocess
import tempfile
import markdown2
import pybars
from datetime import datetime
from kikit import export

def resolveTemplatePath(path):
    """
    Return a correct template path:
    - if the path matches a directory relative to working directory and the
      directory contains template.json, return that
    - otherwise treat the path as a name into the default template library.
    If none of those are template directories, raise exception.
    """
    if os.path.exists(os.path.join(path, "template.json")):
        return path
    PKG_BASE = os.path.dirname(__file__)
    TEMPLATES = os.path.join(PKG_BASE, "resources/present/templates")
    if os.path.exists(os.path.join(TEMPLATES, path, "template.json")):
        return os.path.join(TEMPLATES, path)
    raise RuntimeError("'{}' is not a name or a path for existing template. Perhaps you miss template.json in the template?")

def readTemplate(path):
    """
    Resolve template path, read the property file and return a subclass of
    Template which can render the template.
    """
    templateClasses = {
        "HtmlTemplate": HtmlTemplate
    }
    path = resolveTemplatePath(path)
    with open(os.path.join(path, "template.json"), encoding="utf-8") as jsonFile:
        parameters = json.load(jsonFile)
    try:
        tType = parameters["type"]
    except KeyError:
        raise RuntimeError("Invalid template.json - missing 'type'")
    try:
        return templateClasses[tType](path)
    except KeyError:
        raise RuntimeError("Unknown template type '{}'".format(tType))

def copyRelativeTo(sourceTree, sourceFile, outputDir):
    sourceTree = os.path.abspath(sourceTree)
    sourceFile = os.path.abspath(sourceFile)
    relPath = os.path.relpath(sourceFile, sourceTree)
    outputDir = os.path.join(outputDir, os.path.dirname(relPath))
    Path(outputDir).mkdir(parents=True, exist_ok=True)
    shutil.copy(sourceFile, outputDir)

class Template:
    def __init__(self, directory):
        self.directory = directory
        with open(os.path.join(directory, "template.json"), encoding="utf-8") as jsonFile:
            self.parameters = json.load(jsonFile)
        self.extraResources = []
        self.boards = []
        self.name = None
        self.repository = None

    def _copyResources(self, outputDirectory):
        """
        Copy all resource files specified by template.json and further specified
        by addResource to the output directory.
        """
        for pattern in self.parameters["resources"]:
            for path in glob.glob(os.path.join(self.directory, pattern), recursive=True):
                copyRelativeTo(self.directory, path, outputDirectory)
        for pattern in self.extraResources:
            for path in glob.glob(pattern, recursive=True):
                copyRelativeTo(".", path, outputDirectory)

    def addResource(self, resource):
        """
        Add a resources. Resource can be specified by a glob pattern. The files
        are treated relative to current working directory.
        """
        self.extraResources.append(resource)

    def addBoard(self, name, comment, boardfile):
        """
        Add board
        """
        self.boards.append({
            "name": name,
            "comment": comment,
            "source": boardfile
        })

    @staticmethod
    def _renderBoardImagesPcbDraw(outputDirectory, boardDesc):
        """Render front and back board images for a board using PcbDraw."""

        pcbdraw = shutil.which("pcbdraw")
        if not pcbdraw:
            raise RuntimeError("PcbDraw needs to be installed in order to render boards")

        frontPath = os.path.join(outputDirectory, boardDesc["front"])
        backPath = os.path.join(outputDirectory, boardDesc["back"])
        subprocess.check_call([pcbdraw, "plot", "--vcuts=Cmts.User", "--silent", "--side=front", boardDesc["source"], frontPath])
        subprocess.check_call([pcbdraw, "plot", "--vcuts=Cmts.User", "--silent", "--side=back", boardDesc["source"], backPath])

    @staticmethod
    def _renderBoardImagesKicadCli(outputDirectory, boardDesc):
        """Render front and back board images for a board using kicad-cli."""

        kicadCli = shutil.which("kicad-cli")
        if not kicadCli:
            raise RuntimeError("kicad-cli needs to be installed in order to render boards")

        convert = shutil.which("convert")
        if not convert:
            raise RuntimeError("ImageMagick needs to be installed in order to render boards")

        frontPath = os.path.join(outputDirectory, boardDesc["front"])
        backPath = os.path.join(outputDirectory, boardDesc["back"])


        # render an image with transparent background using the KiCad cli
        subprocess.check_call([kicadCli, "pcb", "render", "--side", "top", "--width", "2048", "--height", "2048", boardDesc["source"], "--output", frontPath])
        subprocess.check_call([kicadCli, "pcb", "render", "--side", "bottom", "--width", "2048", "--height", "2048", boardDesc["source"], "--output", backPath])

        # crop rendered images to the actual rendered board size
        resizeArgs = ["-trim", "-bordercolor", "transparent", "-border", "25", "+repage"]
        subprocess.check_call([convert, frontPath, *resizeArgs, frontPath])
        subprocess.check_call([convert, backPath, *resizeArgs, backPath])

    def _renderBoards(self, outputDirectory, renderer):
        """
        Convert all boards to images and gerber exports. Enrich self.boards
        with paths of generated files
        """

        dirPrefix = "boards"
        boardDir = os.path.join(outputDirectory, dirPrefix)
        Path(boardDir).mkdir(parents=True, exist_ok=True)
        for boardDesc in self.boards:
            boardName = os.path.basename(boardDesc["source"]).replace(".kicad_pcb", "")
            boardDesc["front"] = os.path.join(dirPrefix, boardName + "-front.png")
            boardDesc["back"] = os.path.join(dirPrefix, boardName + "-back.png")
            boardDesc["gerbers"] = os.path.join(dirPrefix, boardName + "-gerbers.zip")
            boardDesc["file"] = os.path.join(dirPrefix, boardName + ".kicad_pcb")

            if renderer.lower() == 'pcbdraw':
                self._renderBoardImagesPcbDraw(outputDirectory, boardDesc)
            elif renderer.lower() == "kicad-cli":
                self._renderBoardImagesKicadCli(outputDirectory, boardDesc)
            else:
                raise RuntimeError(f"Unknown renderer '{renderer}'.")

            tmp = tempfile.mkdtemp()
            export.gerberImpl(boardDesc["source"], tmp)
            shutil.make_archive(os.path.join(outputDirectory, boardDesc["gerbers"])[:-4], "zip", tmp)
            shutil.rmtree(tmp)

            shutil.copy(boardDesc["source"], os.path.join(outputDirectory, boardDesc["file"]))

    def render(self, outputDirectory, renderer):
        self._copyResources(outputDirectory)
        self._renderBoards(outputDirectory, renderer)
        self._renderPage(outputDirectory)

    def gitRevision(self):
        """
        Return a git revision string if in git repo, None otherwise
        """
        proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True)
        if proc.returncode:
            return None
        return proc.stdout.decode("utf-8")

    def currentDateTime(self):
        return datetime.now().strftime("%d. %m. %Y %H:%M")

    def setName(self, name):
        self.name = name

    def setRepository(self, rep):
        self.repository = rep


class HtmlTemplate(Template):
    def __init__(self, path):
        super().__init__(path)

    def addDescriptionFile(self, description):
        if not description.endswith(".md"):
            raise RuntimeError("Only markdown descriptions are supported for now")
        self.description = markdown2.markdown_path(description, extras=["fenced-code-blocks", "tables"])

    def _renderPage(self, outputDirectory):
        with open(os.path.join(self.directory, "index.html"), encoding="utf-8") as templateFile:
            template = pybars.Compiler().compile(templateFile.read())
        gitRev = self.gitRevision()
        content = template({
            "repo": self.repository,
            "gitRev": gitRev,
            "gitRevShort": gitRev[:7] if gitRev else None,
            "datetime": self.currentDateTime(),
            "name": self.name,
            "boards": self.boards,
            "description": self.description
        })
        with open(os.path.join(outputDirectory, "index.html"),"w", encoding="utf-8") as outFile:
            outFile.write(content)

def boardpage(outdir, description, board, resource, template, repository, name, renderer):
    try:
        Path(outdir).mkdir(parents=True, exist_ok=True)
        template = readTemplate(template)
        template.addDescriptionFile(description)
        template.setRepository(repository)
        template.setName(name)
        for r in resource:
            template.addResource(r)
        for name, comment, file in board:
            template.addBoard(name, comment, file)
        template.render(outdir, renderer)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.exit(1)





