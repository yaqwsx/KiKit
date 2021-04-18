import itertools
from io import StringIO

# Simple white-space aware S-Expression parser (parsing and dumping yields the
# same result). Might not support all features of S-expression, but should be
# enough to properly parser KiCAD's S-Expressions

def ParseError(RuntimeError):
    pass

class Atom:
    def __init__(self, value, leadingWhitespace=""):
        self.value = value
        self.leadingWhitespace = leadingWhitespace

    def __str__(self):
        if any([x.isspace() for x in self.value]) or len(self.value) == 0:
            return self.leadingWhitespace + '"' + self.value + '"'
        return self.leadingWhitespace + self.value

    def __repr__(self):
        return f"Atom({self.value}, '{self.leadingWhitespace}')"

    def __eq__(self, o):
        if isinstance(o, str):
            return self.value == o
        return self.value == o.value and self.leadingWhitespace == o.leadingWhitespace

class SExpr:
    def __init__(self, items=None, leadingWhitespace="", trailingWhitespace=""):
        if items is None:
            self.items = []
        else:
            self.items = items
        self.leadingWhitespace = leadingWhitespace
        self.trailingWhitespace = trailingWhitespace

    def __str__(self):
        # TBA: we should validate that two atoms do not get squished together
        # as they have wrongly specified whitespace
        return (self.leadingWhitespace + "("
            + "".join([str(x) for x in self.items])
            + self.trailingWhitespace + ")")

    def __repr__(self):
        val = [x.__repr__() for x in self.items]
        return f"Expr([{', '.join(val)}], '{self.leadingWhitespace}', '{self.trailingWhitespace}')"

    def __eq__(self, o):
        return (self.items == o.items and
                self.leadingWhitespace == o.leadingWhitespace and
                self.trailingWhitespace == o.trailingWhitespace)

    def __iter__(self):
        return self.items.__iter__()

    def __getitem__(self, key):
        return self.items.__getitem__(key)

    def __len__(self):
        return self.items.__len__()

# Python 3 does not support peeking nor relative seeking on text files so we
# implement goBack, shift and peek via seeking. It does not performs the best,
# but it yields simple code.
def goBack(file, n=1):
    file.seek(file.tell() - n)

def shift(stream, what=None):
    c = stream.read(1)
    if len(c) == 0:
        raise ParseError("Unexpected file end")
    if what is not None and c != what:
        raise ParseError(f"Expected '{what}', got '{c}'")
    return c

def peek(stream):
    c = shift(stream)
    goBack(stream)
    return c

def atomEnd(c):
    return c.isspace() or c in set("()")

def readQuotedString(stream):
    shift(stream, '"')
    s = []
    escaped = False
    c = peek(stream)
    while c != '"' or escaped:
        if c == "\\":
            escaped = True
        else:
            escaped = False
            s.append(shift(stream))
        c = peek(stream)
    shift(stream, '"')
    return "".join(s)

def readString(stream):
    s = []
    c = peek(stream)
    while not atomEnd(c):
        s.append(shift(stream))
        c = peek(stream)
    return "".join(s)

def readAtom(stream):
    c = peek(stream)
    if c == '"':
        value = readQuotedString(stream)
    else:
        value = readString(stream)
    return Atom(value)

def readWhitespace(stream):
    w = []
    c = peek(stream)
    while c.isspace():
        w.append(shift(stream))
        c = peek(stream)
    return "".join(w)

def readSexpr(stream):
    shift(stream, "(")

    expr = SExpr()
    c = peek(stream)
    whitespace = ""
    while c != ")":
        if c.isspace():
            whitespace = readWhitespace(stream)
        elif c == "(":
            s = readSexpr(stream)
            s.leadingWhitespace = whitespace
            expr.items.append(s)
            whitespace = ""
        else:
            a = readAtom(stream)
            a.leadingWhitespace = whitespace
            expr.items.append(a)
            whitespace = ""
        c = peek(stream)
    shift(stream, ")")
    expr.trailingWhitespace = whitespace
    return expr

def parseSexprF(stream):
    lw = readWhitespace(stream)
    s = readSexpr(stream)
    s.leadingWhitespace = lw
    return s

def parseSexprS(s):
    return parseSexprF(StringIO(s))
