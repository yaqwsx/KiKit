import inspect
import tempfile
import subprocess
import shutil
import os
import sys
import threading
from itertools import chain

def header(func):
    signature = inspect.signature(func)
    args = [str(k) if v.default is inspect.Parameter.empty else str(k) + "=" + str(v.default)
        for k, v in signature.parameters.items()]
    currentLine = func.__name__ + "("
    lines = []
    indent = " " * (len(func.__name__) + 1)
    separator = ""
    for arg in args:
        newLine = currentLine + separator + arg
        if len(newLine) > 80:
            lines.append(currentLine + separator)
            currentLine = indent + arg
        else:
            currentLine = newLine
        separator = ", "
    lines.append(currentLine + ")")
    return("\n".join(lines))

def printHeader(func):
    print(f"\n#### `{func.__name__}`")
    print(f"```\n{header(func)}\n```")

def printHelp(x):
    print(inspect.getdoc(x))

def quote(args):
    """
    Given a list of command line arguments, quote them so they can be can be
    printed
    """
    def q(x):
        if " " in x:
            return "'" + x + "'"
        else:
            return x
    return [q(x) for x in args]


runBoardExampleThreads = []

def runBoardExample(name, args):
    """
    Run kikit CLI command with args - omitting the output file name. Prints a
    markdown with the command and includes a generated board image.

    Generating images runs in parallel, so do not forget to invoke
    runBoardExampleJoin() at the end of your script.
    """
    dirname = tempfile.mkdtemp()
    output = os.path.join(dirname, "x.kicad_pcb")
    realArgs = ["python3", "-m", "kikit.ui"] + list(chain(*args)) + [output]

    # We print first, so in a case of failure we have the command in a nice
    # copy-paste-ready form
    args[0] = ["kikit"] + args[0]
    args[-1] = args[-1] + ["panel.kicad_pcb"]
    print("```")
    for i, c in enumerate(args):
        if i != 0:
            print("    ", end="")
        end = "\n" if i + 1 == len(args) else " \\\n"
        print(" ".join(quote(c)), end=end)
    print("```\n")
    print("![{0}](resources/{0}.png)".format(name))

    def run():
        try:
            outimage = f"doc/resources/{name}.png"
            subprocess.run(realArgs, check=True, capture_output=True)
            subprocess.run(["pcbdraw", "--vcuts", "--silent", output,
                    outimage], check=True, capture_output=True)
            subprocess.run(["convert", outimage, "-define",
                "png:include-chunk=none", outimage], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print("Command: " + " ".join(e.cmd), file=sys.stderr)
            print("Stdout: " + e.stdout.decode("utf8"), file=sys.stderr)
            print("Stderr: " + e.stderr.decode("utf8"), file=sys.stderr)
            sys.exit(1)
        shutil.rmtree(dirname)
    t = threading.Thread(target=run)
    t.start()
    global runBoardExampleThreads
    runBoardExampleThreads.append(t)

def runBoardExampleJoin():
    for t in runBoardExampleThreads:
        t.join()

