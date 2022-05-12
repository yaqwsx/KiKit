import datetime as dt
from typing import Callable, Optional, Dict, Any
from pcbnewTransition import pcbnew


class Formatter:
    """
    Turns a function into a formatter. Caches the result.
    """
    def __init__(self, fn: Callable[[], str]) -> None:
        self.fn = fn
        self.value: Optional[str] = None

    def __str__(self) -> str:
        if self.value is None:
            self.value = self.fn()
        return self.value

def kikitTextVars(board: pcbnew.BOARD) -> Dict[str, Any]:
    return {
        "date": Formatter(lambda: dt.datetime.today().strftime("%Y-%m-%d")),
        "time24": Formatter(lambda: dt.datetime.today().strftime("%-H:%M")),
    }
