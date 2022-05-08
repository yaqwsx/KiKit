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

def quotePosix(args):
    """
    Given a list of command line arguments, quote them so they can be can be
    printed on POSIX
    """
    def q(x):
        if " " in x:
            return "'" + x + "'"
        else:
            return x
    return [q(x) for x in args]

def quoteWindows(args):
    """
    Given a list of command line arguments, quote them so they can be can be
    printed in Windows CLI
    """
    def q(x):
        if " " in x:
            return '"' + x + '"'
        else:
            return x
    return [q(x) for x in args]

def panelizeAndDraw(name, command):
    dirname = tempfile.mkdtemp()
    output = os.path.join(dirname, "x.kicad_pcb")
    try:
        outimage = f"doc/resources/{name}.png"
        subprocess.run(command + [output], check=True, capture_output=True)

        r = subprocess.run(["pcbdraw", "plot", "--help"], capture_output=True)
        if r.returncode == 0:
            # We have a new PcbDraw
            r = subprocess.run(["pcbdraw", "plot", "--vcuts", "Cmts.User", "--silent", output,
                    outimage], check=True, capture_output=True)
        else:
            # We have an old PcbDraw
            r = subprocess.run(["pcbdraw", "--vcuts", "--silent", output,
                    outimage], check=True, capture_output=True)
        subprocess.run(["convert", outimage, "-define",
            "png:include-chunk=none", outimage], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print("Command: " + " ".join(e.cmd), file=sys.stderr)
        print("Stdout: " + e.stdout.decode("utf8"), file=sys.stderr)
        print("Stderr: " + e.stderr.decode("utf8"), file=sys.stderr)
        sys.exit(1)
    shutil.rmtree(dirname)


runExampleThreads = []

def runBoardExample(name, args):
    """
    Run kikit CLI command with args - omitting the output file name. Prints a
    markdown with the command and includes a generated board image.

    Generating images runs in parallel, so do not forget to invoke
    runBoardExampleJoin() at the end of your script.
    """
    realArgs = ["python3", "-m", "kikit.ui"] + list(chain(*args))

    # We print first, so in a case of failure we have the command in a nice
    # copy-paste-ready form
    args[0] = ["kikit"] + args[0]
    args[-1] = args[-1] + ["panel.kicad_pcb"]
    print("```")
    print("# Linux")
    for i, c in enumerate(args):
        if i != 0:
            print("    ", end="")
        end = "\n" if i + 1 == len(args) else " \\\n"
        print(" ".join(quotePosix(c)), end=end)
    print("\n# Windows")
    for i, c in enumerate(args):
        if i != 0:
            print("    ", end="")
        end = "\n" if i + 1 == len(args) else " ^\n"
        print(" ".join(quoteWindows(c)), end=end)
    print("```\n")
    print("![{0}](resources/{0}.png)".format(name))

    t = threading.Thread(target=lambda: panelizeAndDraw(name, realArgs))
    t.start()
    global runExampleThreads
    runExampleThreads.append(t)

def runScriptingExample(name, args):
    """
    Run a Python panelization script that takes the name of the output as a last
    argument and create a drawing of it.
    """

    realArgs = ["python3"] + list(chain(*args))
    print("```")
    for i, c in enumerate(args):
        if i != 0:
            print("    ", end="")
        end = "\n" if i + 1 == len(args) else " \\\n"
        print(" ".join(quote(c)), end=end)
    print("```\n")
    print("![{0}](resources/{0}.png)".format(name))

    t = threading.Thread(target=lambda: panelizeAndDraw(name, realArgs))
    t.start()
    global runExampleThreads
    runExampleThreads.append(t)


def runExampleJoin():
    for t in runExampleThreads:
        t.join()

