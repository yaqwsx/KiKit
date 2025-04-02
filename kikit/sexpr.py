from io import StringIO
from typing import Callable, Dict, Iterable, Optional, Union

# Simple white-space aware S-Expression parser (parsing and dumping yields the
# same result). Might not support all features of S-expression, but should be
# enough to properly parser KiCAD's S-Expressions

class ParseError(RuntimeError):
    pass

# We want the parser to be able to operate on a stream of data, so we define a
# chunked reader that allows us to go back and extract parts of the string.
class Stream:
    def __init__(self, stream, buffer_size=4096):
        self.stream = stream
        self.buffer_size = buffer_size
        self.buffer = ""
        self.position = 0
        self.mark_start = -1
        self._fill_buffer()

    def _fill_buffer(self):
        """Fill the buffer with more data from the stream"""
        # If there's marked content we need to keep, preserve it
        has_grown = True
        if self.mark_start >= 0:
            marked_content = self.buffer[self.mark_start:self.position]
            remaining_content = self.buffer[self.position:]
            new_data = self.stream.read(self.buffer_size)
            if len(new_data) == 0:
                has_grown = False
            self.buffer = marked_content + remaining_content + new_data
            self.position = len(marked_content)
            self.mark_start = 0  # Marked content now starts at beginning of buffer
        else:
            # No marked content, just read more data
            remaining = self.buffer[self.position:]
            new_data = self.stream.read(self.buffer_size)
            if len(new_data) == 0:
                has_grown = False
            self.buffer = remaining + new_data
            self.position = 0
        return has_grown

    def read(self):
        """Read a single character from the stream"""
        try:
            result = self.buffer[self.position]
            self.position += 1
        except:
            if not self._fill_buffer():
                return ''
            result = self.buffer[self.position]
            self.position += 1
        return result

    def readUntilEndOfWhitespace(self):
        whitespace = ""

        while True:
            # Skip to the first non-whitespace character in the current buffer
            pos = self.position
            l = len(self.buffer)
            while pos < l and self.buffer[pos].isspace():
                pos += 1
            whitespace += self.buffer[self.position:pos]
            self.position = pos

            # If we've reached the end of the buffer, try to fill it
            if pos >= l:
                if not self._fill_buffer():
                    return whitespace
            else:
                break
        return whitespace

    def readUntilEndOfString(self):
        result = ""

        while True:
            # Read until we find a space, parenthesis, or end of buffer
            pos = self.position
            l = len(self.buffer)
            while pos < l:
                c = self.buffer[pos]
                if c.isspace() or c == "(" or c == ")":
                    break
                pos += 1

            # Add what we've read to our result
            result += self.buffer[self.position:pos]
            self.position = pos

            # If we've reached the end of the buffer, try to fill it
            if self.position >= l:
                if not self._fill_buffer():
                    return result
            else:
                break
        return result

    def readUntilEndOfQuotedString(self):
        escaped = False
        result = ""

        self.shift('"')  # Consume the opening quote

        while True:
            pos = self.position
            l = len(self.buffer)
            terminated = False
            while pos < l:
                c = self.buffer[pos]

                if c == '"' and not escaped:
                    terminated = True
                    break

                pos += 1
                if c == "\\" and not escaped:
                    escaped = True
                else:
                    escaped = False

            result += self.buffer[self.position:pos]
            self.position = pos
            if terminated:
                self.shift('"') # Consume the closing quote

            # If we've reached the end of the buffer, try to fill it
            if self.position >= len(self.buffer):
                if not self._fill_buffer() and not terminated:
                    raise ParseError("Unexpected end of file in quoted string")
            if terminated:
                break

        return result

    def readAtom(self):
        whitespace = self.readUntilEndOfWhitespace()

        # We know that there is a next whitespace as readUntilEndOfWhitespace
        # ensures it
        c = self.buffer[self.position]
        quoted = c == '"'
        if quoted:
            value = self.readUntilEndOfQuotedString()
        else:
            value = self.readUntilEndOfString()
        return Atom(value, leadingWhitespace=whitespace, quoted=quoted)


    def back(self):
        """Move back one character in the stream"""
        if self.position > 0:
            self.position -= 1
        else:
            raise ParseError("Cannot move back")

    def shift(self, expected):
        """Read the next character and verify it matches the expected value"""
        c = self.read()
        if c != expected:
            raise ParseError(f"Expected '{expected}', got {repr(c)}")
        return c

    def readAll(self):
        """Read all remaining content from the stream"""
        result = self.buffer[self.position:]
        self.position = len(self.buffer)
        self.mark_start = -1  # Reset any mark when reading all
        additional = self.stream.read()
        return result + additional

    def markStart(self):
        """Mark the start position of interesting content"""
        self.mark_start = self.position

    def markEnd(self):
        """Mark the end position of interesting content"""
        # We don't need an explicit end marker since position is our current point
        pass

    def getMarkedContent(self):
        """Get the content between the start and current position"""
        if self.mark_start < 0:
            return ""

        if self.mark_start >= len(self.buffer):
            # This shouldn't happen with proper buffer management
            self.mark_start = -1
            return ""

        result = self.buffer[self.mark_start:self.position]
        self.mark_start = -1  # Reset marker
        return result

    def isEOF(self):
        """Check if we've reached the end of the file"""
        if self.position < len(self.buffer):
            return False
        return not self._fill_buffer()


class Atom:
    __slots__ = ['value', 'quoted', 'leadingWhitespace']

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
        if not isinstance(o, Atom):
            return False
        return self.value == o.value and self.leadingWhitespace == o.leadingWhitespace


class SExpr:
    __slots__ = ['items', 'leadingWhitespace', 'trailingWhitespace', 'complete', 'trailingOuterWhitespace']

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
        if not isinstance(o, SExpr):
            return False
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

def readWhitespaceWithComments(stream):
    stream.markStart()

    while True:
        c = stream.read()
        if not c:  # EOF
            break

        if not c.isspace() and c != "#":
            stream.back()  # Put back non-whitespace, non-comment
            break

        if c == "#":
            # Read until end of line
            while True:
                c = stream.read()
                if not c or c == "\n":
                    break

    return stream.getMarkedContent()

def readSexpr(stream, limit=None):
    """
    Reads SExpression from the stream. You can optionally try to parse only the
    first n nodes by specifying limit;
    """
    stream.shift("(")

    expr = SExpr()
    whitespace = ""

    while True:
        c = stream.read()
        if not c:  # EOF
            raise ParseError("Unexpected end of file within expression")

        if c == ")" and (limit is None or limit > 0):
            expr.trailingWhitespace = whitespace
            expr.complete = True
            break

        # Put the character back to be processed by the appropriate reader
        stream.back()

        if limit is not None and limit <= 0:
            # We've read enough nodes, capture the rest
            expr.trailingWhitespace = whitespace + stream.readAll()
            expr.complete = False
            break

        if c.isspace():
            whitespace = stream.readUntilEndOfWhitespace()
        elif c == "(":
            s = readSexpr(stream)
            s.leadingWhitespace = whitespace
            expr.items.append(s)
            if limit is not None:
                limit -= 1
            whitespace = ""
        else:
            a = stream.readAtom()
            a.leadingWhitespace = whitespace
            expr.items.append(a)
            if limit is not None:
                limit -= 1
            whitespace = ""

    return expr

def parseSexprF(sourceStream, limit=None, buffer_size=4096):
    stream = Stream(sourceStream, buffer_size=buffer_size)
    lw = stream.readUntilEndOfWhitespace()
    s = readSexpr(stream, limit=limit)
    s.leadingWhitespace = lw
    s.trailingOuterWhitespace = stream.readUntilEndOfWhitespace()
    return s

def parseSexprS(s, limit=None, buffer_size=4096):
    return parseSexprF(StringIO(s), limit=limit, buffer_size=buffer_size)

def parseSexprListF(sourceStream, limit=None, buffer_size=4096):
    sexprs = []
    stream = Stream(sourceStream, buffer_size=buffer_size)

    while not stream.isEOF():
        lw = readWhitespaceWithComments(stream)

        # Check if we've reached EOF after reading whitespace
        if stream.isEOF():
            break

        s = readSexpr(stream, limit=limit)
        s.leadingWhitespace = lw
        s.trailingOuterWhitespace = readWhitespaceWithComments(stream)
        sexprs.append(s)

    return sexprs

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
