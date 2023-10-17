from typing import Union, Optional, Dict, Any
from pathlib import Path
from string import Template
from functools import cached_property
from pcbnewTransition import pcbnew
import json


class KiCADProject:
    """
    This code represents a KiCAD project and allows easy access to individual
    files without the need to hassle with project names.
    """
    def __init__(self, path: Union[str, Path]) -> None:
        self.projectdir: Path = Path(path).resolve()
        name = None
        if str(path).endswith(".kicad_pro"):
            name = self.projectdir.name[:-len(".kicad_pro")]
            self.projectdir = self.projectdir.parent
        elif str(path).endswith(".kicad_pcb"):
            name = self.projectdir.name[:-len(".kicad_pcb")]
            self.projectdir = self.projectdir.parent
        else:
            if not self.projectdir.is_dir():
                raise RuntimeError(f"The project directory {self.projectdir} is not a directory")
            name = self._resolveProjectName(self.projectdir)
        self._name: str = name

    @staticmethod
    def _resolveProjectName(path: Path) -> str:
        candidate: Optional[str] = None
        for item in path.iterdir():
            if not item.name.endswith(".kicad_pro"):
                continue
            if candidate is not None:
                raise RuntimeError(f"There are multiple projects ({candidate} " +
                                   f"and {item.name}) in directory {path}. Not " +
                                   f"clear which one to choose.")
            candidate = item.name
        if candidate is not None:
            return candidate[:-len(".kicad_pro")]
        raise RuntimeError(f"No project found in {path}")

    @property
    def projectPath(self) -> Path:
        return self.projectdir / f"{self._name}.kicad_pro"

    @property
    def boardPath(self) -> Path:
        return self.projectdir / f"{self._name}.kicad_pcb"

    @property
    def schemaPath(self) -> Path:
        return self.projectdir / f"{self._name}.kicad_sch"

    @property
    def dirPath(self) -> Path:
        return self.projectdir

    def has(self, file: Union[str, Path]):
        return (self.projectdir / file).exists()

    def expandText(self, text: str):
        """
        Given KiCAD text expand
        """
        try:
            return Template(text).substitute(self.textVars)
        except KeyError as e:
            raise RuntimeError(f"Requested text '{text}' expects project variable '{e}' which is missing") from None

    @property
    def board(self) -> pcbnew.BOARD:
        return pcbnew.LoadBoard(str(self.getBoard()))

    @cached_property
    def projectJson(self) -> Dict[str, Any]:
        with open(self.projectPath, "r", encoding="utf-8") as f:
            return json.load(f)

    @cached_property
    def textVars(self) -> Dict[str, str]:
        return self.projectJson.get("text_variables", {})
