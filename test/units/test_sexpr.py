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
