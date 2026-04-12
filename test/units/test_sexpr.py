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
    string = stream.readUntilEndOfQuotedString()
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

def test_comment_inside_sexpr():
    """Comments inside s-expressions should be skipped (issue #848)"""
    # Exact reproduction case from the issue: commented line with unbalanced parens
    source = '''(rule "Silkscreen overlap"
  (constraint silk_clearance(min 0.15mm))
  #(condition "((A.Type=='*Text') || (A.Type=='Graphic*')) && (( B.Type=='Via' ) || ( B.Type=='Pad' ))"))
  (condition "((A.Type=='*Text') || (A.Type=='Graphic*')) && ( B.Type=='Pad' )")
)'''
    rules = parseSexprListF(StringIO(source))
    assert len(rules) == 1
    rule = rules[0]
    assert rule[0] == "rule"
    assert rule[1] == "Silkscreen overlap"
    # Round-trip: output must exactly match input
    assert ''.join(str(r) for r in rules) == source

def test_comment_between_items():
    """Comments between items inside an s-expression"""
    source = '(a\n  #comment\n  b)'
    rules = parseSexprListF(StringIO(source))
    assert len(rules) == 1
    assert rules[0][0] == "a"
    assert rules[0][1] == "b"
    assert ''.join(str(r) for r in rules) == source

def test_comment_with_parens():
    """Comments containing parentheses should not confuse the parser"""
    source = '(a\n  # this has ) and ( in it\n  b)'
    rules = parseSexprListF(StringIO(source))
    assert len(rules) == 1
    assert rules[0][0] == "a"
    assert rules[0][1] == "b"
    assert ''.join(str(r) for r in rules) == source

def test_multiple_comments_in_dru():
    """Multiple commented rules in a DRU-like file"""
    source = '''(version 1)
(rule "Active"
  #(constraint clearance(min 0.2mm))
  #(constraint clearance(min 0.1mm))
  (constraint clearance(min 0.3mm))
)'''
    rules = parseSexprListF(StringIO(source))
    assert len(rules) == 2
    assert rules[0][0] == "version"
    assert rules[1][0] == "rule"
    assert ''.join(str(r) for r in rules) == source

def test_comment_at_end_of_sexpr():
    """Comment right before closing paren"""
    source = '(a b\n  #trailing comment\n)'
    rules = parseSexprListF(StringIO(source))
    assert len(rules) == 1
    assert rules[0][0] == "a"
    assert rules[0][1] == "b"
    assert ''.join(str(r) for r in rules) == source

def test_comment_between_top_level_sexprs():
    """Comments between top-level s-expressions are preserved"""
    source = '(a)\n# between\n(b)'
    rules = parseSexprListF(StringIO(source))
    assert len(rules) == 2
    assert ''.join(str(r) for r in rules) == source
