import datetime as dt
from string import Template
from typing import Callable, Optional, Dict, Any
from pcbnewTransition import pcbnew


class Formatter:
    """
    Turns a function into a formatter. Caches the result.
    """
    def __init__(self, fn: Callable[[], str], vars: Dict[str, str]={}) -> None:
        self.fn = fn
        self.value: Optional[str] = None
        self.vars = vars

    def __str__(self) -> str:
        if self.value is None:
            self.value = self.expandVariables(self.fn())
        return self.value

    def expandVariables(self, string: str) -> str:
        try:
            return Template(string).substitute(self.vars)
        except KeyError as e:
            raise RuntimeError(f"Requested text '{string}' expects project variable '{e}' which is missing") from None

def kikitTextVars(board: pcbnew.BOARD, vars: Dict[str, str]={}) -> Dict[str, Any]:
    availableVars: Dict[str, Formatter] = {
        "date": Formatter(lambda: dt.datetime.today().strftime("%Y-%m-%d"), vars),
        "time24": Formatter(lambda: dt.datetime.today().strftime("%-H:%M"), vars),
        "boardTitle": Formatter(lambda: board.GetTitleBlock().GetTitle(), vars),
        "boardDate": Formatter(lambda: board.GetTitleBlock().GetDate(), vars),
        "boardRevision": Formatter(lambda: board.GetTitleBlock().GetRevision(), vars),
        "boardCompany": Formatter(lambda: board.GetTitleBlock().GetCompany(), vars)
    }

    for i in range(10):
        availableVars[f"boardComment{i + 1}"] = Formatter(lambda: board.GetTitleBlock().GetComment(i), vars)

    return availableVars
