import pytest
from kikit.sexpr import *

def eval(s, truth):
    parsed = parseSexprS(s)
    assert parsed == truth
    assert str(parsed) == s

def test_sexpr():
    eval("(a b)", SExpr([Atom("a"), Atom("b", " ")]))
    eval("(a b )", SExpr([Atom("a"), Atom("b", " ")], "", " "))
    eval("((a)b(c))", SExpr([
        SExpr([Atom("a")]), Atom("b"), SExpr([Atom("c")])
    ]))

    source = """(sym_lib_table
        (lib (name 4xxx)(type Legacy)(uri ${KICAD_SYMBOL_DIR}/4xxx.lib)(options "")(descr "4xxx series symbols"))
        (lib (name 74xGxx)(type Legacy)(uri ${KICAD_SYMBOL_DIR}/74xGxx.lib)(options "")(descr "74xGxx symbols"))
    )"""
    assert str(parseSexprS(source)) == source

def test_readQuotedString():
    SOURCE = r'"ABC\nvDEF\n\"GHI\""'

    stream = Stream(StringIO(SOURCE))
    string = readQuotedString(stream)
    a = Atom(string, quoted=True)
    res = str(a)
    assert res == SOURCE

def test_identiy():
    SOURCE = "../resources/conn.kicad_pcb"
    with open(SOURCE, encoding="utf-8") as f:
        truth = f.read()

    with open(SOURCE, encoding="utf-8") as f:
        ast1 = parseSexprF(f)
    assert str(ast1) == truth

    with open(SOURCE, encoding="utf-8") as f:
        ast2 = parseSexprF(f, limit=3)
    assert str(ast2) == truth

def test_readwhitespace_with_comments():
    stream = Stream(StringIO("  \n\n# Aloha\n("))
    assert readWhitespaceWithComments(stream) == "  \n\n# Aloha\n"

    stream = Stream(StringIO("  \n\n \t# Aloha\n("))
    assert readWhitespaceWithComments(stream) == "  \n\n \t# Aloha\n"
