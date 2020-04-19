import inspect
import tempfile
import subprocess
import shutil
import os

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
    print("```\n" + header(func) + "\n```")

def printHelp(x):
    print(inspect.getdoc(x))

def runBoardExample(name, args):
    """
    Run kikit CLI command with args - omitting the output file name. Prints a
    markdown with the command and includes a generated board image
    """
    dirname = tempfile.mkdtemp()
    output = os.path.join(dirname, "x.kicad_pcb")
    realArgs = ["python3", "-m", "kikit.ui"] + args + [output]
    fakeArgs = ["kikit"] + args + ["panel.kicad_pcb"]
    subprocess.run(realArgs, check=True)
    subprocess.run(["pcbdraw", "--vcuts", "--silent", output,
            "doc/resources/{}.png".format(name)], check=True)
    print("```\n{}\n```".format(" ".join(fakeArgs)))
    print("![{0}](resources/{0}.png)".format(name))
    shutil.rmtree(dirname)

