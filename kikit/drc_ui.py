import click
from enum import Enum

class ReportLevel(Enum):
    warning = "warning"
    error = "error"

    def __str__(self):
        return self.value

class EnumType(click.Choice):
    def __init__(self, enum: Enum, case_sensitive=False):
        self.__enum = enum
        super().__init__(choices=[item.value for item in enum], case_sensitive=case_sensitive)

    def convert(self, value, param, ctx):
        if value is None or isinstance(value, Enum):
            return value

        converted_str = super().convert(value, param, ctx)
        return self.__enum(converted_str)

@click.group()
def drc():
    """
    Validate design rules of the board
    """
    pass

@click.command()
@click.argument("boardfile", type=click.Path(dir_okay=False))
@click.option("--useMm/--useInch", default=True)
@click.option("--strict/--weak", default=False,
    help="Check all track errors")
@click.option("--level", type=EnumType(ReportLevel), default=ReportLevel.error,
    help="Minimum severity to report")
def run(boardfile, usemm, strict, level):
    """
    Check DRC rules. If no rules are validated, the process exists with code 0.

    If any errors are detected, the process exists with non-zero return code and
    prints DRC report on the standard output.
    """
    from kikit.drc import runImpl
    import sys
    from pcbnewTransition import pcbnew, isV6

    try:
        if not isV6():
            raise RuntimeError("This feature is available only with KiCAD 6.")
        board = pcbnew.LoadBoard(boardfile)
        failed = runImpl(board, usemm, strict, level, lambda x: print(x))
        if not failed:
            print("No DRC errors found.")
        else:
            print("Found some DRC violations. See the report above.")
        sys.exit(failed)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.exit(1)

drc.add_command(run)
