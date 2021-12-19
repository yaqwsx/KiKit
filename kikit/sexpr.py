from io import StringIO

# Simple white-space aware S-Expression parser (parsing and dumping yields the
# same result). Might not support all features of S-expression, but should be
# enough to properly parser KiCAD's S-Expressions

def ParseError(RuntimeError):
    pass

# Python 3 does not support peeking on text files, so let's implement a stream
# wrapper that supports it.
class Stream:
    def __init__(self, stream):
        self.stream = stream
        self.pending = None

    def read(self):
        if self.pending:
            c = self.pending
            self.pending = None
            return c
        return self.stream.read(1)

    def peek(self):
        if not self.pending:
            self.pending = self.stream.read(1)
        return self.pending

    def shift(self, expected):
        c = self.read()
        if c != expected:
            raise ParseError(f"Expected '{expected}', got {repr(c)}")
        return c


class Atom:
    def __init__(self, value, leadingWhitespace="", quoted=False):
        self.value = value
        self.quoted = quoted
        self.leadingWhitespace = leadingWhitespace

    def __str__(self):
        if self.quoted:
            value = self.value.replace('"', '\\"')
            return self.leadingWhitespace + '"' + value + '"'
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


def atomEnd(c):
    return c.isspace() or c in set("()")

def readQuotedString(stream):
    stream.shift('"')
    s = []
    escaped = False
    c = stream.peek()
    while c != '"' or escaped:
        if c == "\\":
            escaped = True
            stream.read()
        else:
            escaped = False
            s.append(stream.read())
        c = stream.peek()
    stream.shift('"')
    return "".join(s)

def readString(stream):
    s = []
    c = stream.peek()
    while not atomEnd(c):
        s.append(stream.read())
        c = stream.peek()
    return "".join(s)

def readAtom(stream):
    c = stream.peek()
    quoted = c == '"'
    if quoted:
        value = readQuotedString(stream)
    else:
        value = readString(stream)
    return Atom(value, quoted=quoted)

def readWhitespace(stream):
    w = []
    c = stream.peek()
    while c.isspace():
        w.append(stream.read())
        c = stream.peek()
    return "".join(w)

def readSexpr(stream):
    stream.shift("(")

    expr = SExpr()
    c = stream.peek()
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
        c = stream.peek()
    stream.shift(")")
    expr.trailingWhitespace = whitespace
    return expr

def parseSexprF(sourceStream):
    stream = Stream(sourceStream)
    lw = readWhitespace(stream)
    s = readSexpr(stream)
    s.leadingWhitespace = lw
    return s

def parseSexprS(s):
    return parseSexprF(StringIO(s))
