import inspect

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