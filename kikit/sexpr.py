from io import StringIO
from typing import Callable, Dict, Iterable, Optional, Union

# Simple white-space aware S-Expression parser (parsing and dumping yields the
# same result). Might not support all features of S-expression, but should be
# enough to properly parser KiCAD's S-Expressions

class ParseError(RuntimeError):
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

    def readAll(self):
        x = self.pending
        self.pending = None
        return x + self.stream.read()


class Atom:
    def __init__(self, value, leadingWhitespace="", quoted=False):
        self.value = value
        self.quoted = quoted
        self.leadingWhitespace = leadingWhitespace

    def __str__(self):
        if self.quoted:
            return self.leadingWhitespace + '"' + self.value + '"'
        return self.leadingWhitespace + self.value

    def __repr__(self):
        return f"Atom({self.value}, '{self.leadingWhitespace}')"

    def __eq__(self, o):
        if isinstance(o, str):
            return self.value == o
        return self.value == o.value and self.leadingWhitespace == o.leadingWhitespace

class SExpr:
    def __init__(self, items=None, leadingWhitespace="", trailingWhitespace="", complete=True):
        if items is None:
            self.items = []
        else:
            self.items = items
        self.leadingWhitespace = leadingWhitespace
        self.trailingWhitespace = trailingWhitespace
        self.complete = complete
        self.trailingOuterWhitespace = ""

    def __str__(self):
        # TBA: we should validate that two atoms do not get squished together
        # as they have wrongly specified whitespace
        return (self.leadingWhitespace + "("
            + "".join([str(x) for x in self.items])
            + self.trailingWhitespace
            + (")" if self.complete else "")
            + self.trailingOuterWhitespace)

    def __repr__(self):
        val = [x.__repr__() for x in self.items]
        return f"Expr([{', '.join(val)}], '{self.leadingWhitespace}', '{self.trailingWhitespace}')"

    def __eq__(self, o):
        return (self.items == o.items and
                self.leadingWhitespace == o.leadingWhitespace and
                self.trailingWhitespace == o.trailingWhitespace and
                self.complete == o.complete)

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
        if c == "\\" and not escaped:
            escaped = True
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

def readSexpr(stream, limit=None):
    """
    Reads SExpression from the stream. You can optionally try to parse only the
    first n nodes by specifying limit;
    """
    stream.shift("(")

    expr = SExpr()
    c = stream.peek()
    whitespace = ""
    while c != ")" and (limit is None or limit > 0):
        if c.isspace():
            whitespace = readWhitespace(stream)
        elif c == "(":
            s = readSexpr(stream)
            s.leadingWhitespace = whitespace
            expr.items.append(s)
            if limit is not None:
                limit -= 1
            whitespace = ""
        else:
            a = readAtom(stream)
            a.leadingWhitespace = whitespace
            expr.items.append(a)
            if limit is not None:
                limit -= 1
            whitespace = ""
        c = stream.peek()
    if limit != 0:
        stream.shift(")")
        expr.trailingWhitespace = whitespace
        expr.complete = True
    else:
        expr.trailingWhitespace = whitespace + stream.readAll()
        expr.complete = False
    return expr

def parseSexprF(sourceStream, limit=None):
    stream = Stream(sourceStream)
    lw = readWhitespace(stream)
    s = readSexpr(stream, limit=limit)
    s.leadingWhitespace = lw
    s.trailingOuterWhitespace = readWhitespace(stream)
    return s

def parseSexprS(s, limit=None):
    return parseSexprF(StringIO(s), limit=limit)


AstNode = Union[SExpr, Atom]

def isElement(name: str) -> Callable[[AstNode], bool]:
    def f(node: AstNode) -> bool:
        if isinstance(node, Atom) or len(node) == 0:
            return False
        item = node[0]
        return isinstance(item, Atom) and item.value == name
    return f

def readDict(nodes: Iterable[AstNode]) -> Dict[str, AstNode]:
    d = {}
    for node in nodes:
        if not isinstance(node, SExpr) or len(node.items) != 2:
            raise RuntimeError("Invalid node passed")
        key = node.items[0]
        value = node.items[1]
        if not isinstance(key, Atom):
            raise RuntimeError("Invalid node passed")
        d[key.value] = value
    return d

def readStrDict(nodes: Iterable[AstNode]) -> Dict[str, str]:
    d = {}
    for key, value in readDict(nodes).items():
        if not isinstance(value, Atom):
            raise RuntimeError("Dictionary is not a string dictionary")
        d[key] = value.value
    return d

def findNode(nodes: Iterable[AstNode], name: str) -> Optional[SExpr]:
    """
    Finds a node with given name in a list of nodes
    """
    for node in nodes:
        if isinstance(node, Atom):
            continue
        if len(node.items) == 0:
            continue
        nameNode = node.items[0]
        if isinstance(nameNode, Atom) and nameNode.value == name:
            return node
    return None
