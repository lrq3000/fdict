# Unit testing of fdict
from fdict import fdict, sfdict

import ast
import sys

def test_fdict_creation():
    '''fdict: Test creation of just a nested dict, without anything else'''
    a = fdict()
    a['c']['b'] = set([1, 2])
    assert a == {'c/b': set([1, 2])}

def test_fdict_basic():
    '''fdict: Basic tests + copy test'''
    a = fdict()
    a['a'] = {}
    a['c']['b'] = set([1, 2])

    assert list(a.keys()) == ['c/b']
    assert dict(a.items()) == dict([('c/b', set([1, 2]))])

    # Test sharing of the internal dict across nested fdicts
    assert id(a.d) == id(a['c'].d)

    # Test equality
    assert a == {'c/b': set([1, 2])} and a == {'c': {'b': set([1, 2])}}  # equality dict
    assert a['c/b'] == set([1, 2])  # leaf direct access
    assert a['c']['b'] == set([1, 2])  # leaf indirect access
    assert a['c'] == {'b': set([1, 2])}  # node
    assert a['c/d'] == {}  # inexistent node
    assert (a['c/d'] == 1) == False  # inexistent node and wrong type

    # Test getitem
    assert a['c']['b'] == a['c/b'] == set([1, 2])  # leaf
    assert dict(a['c'].items()) == {'b': set([1, 2])}  # node

    # Copy test
    acopy = a.copy()
    assert dict(acopy.items()) == dict(a.items())
    assert acopy is not a

    # Referencing into another variable of a nested item + check update of nested items
    b = acopy['c']
    assert dict(b.items()) == dict([('b', set([1, 2]))])
    acopy['c'].update({'d': 3})
    assert acopy == {'c/b': set([1, 2]), 'c/d': 3}
    assert b == {'b': set([1, 2]), 'd': 3}

    # Test subitem assignment with a nested dict
    d = fdict()
    d['b'] = {'a': 1}
    d['c/b'] = set([2, 3, 5])
    assert d.to_dict() == {'c/b': set([2, 3, 5]), 'b/a': 1}

    # Test simple update
    a.update(d)
    assert a.to_dict() == {'c/b': set([2, 3, 5]), 'b/a': 1}
    assert a['c'].to_dict() == {'b': set([2, 3, 5])}

    # Test initialization with a dict
    a = fdict(d={'a': {'b': set([1, 2])}})
    assert not isinstance(a['a']['b'], fdict) and isinstance(a['a']['b'], set)  # should return the leaf's object, not a nested fdict!
    assert a['a']['b'] == set([1, 2])

def test_fdict_flattening_extract_update():
    '''Test fdict flattening, extract and update'''
    # Flattening test
    m = {}
    m['a'] = 1
    m['b'] = {'c': 3, 'd': {'e': 5}}
    m['f'] = set([1, 2, 5])
    m2 = fdict(m)
    assert dict(m2.items()) == fdict.flatkeys(m)

    # Update and extract test
    n = {}
    n['b'] = {'d': {'f': 6}}
    n['g'] = 7
    m2.update(n)
    assert m2 == {'a': 1, 'g': 7, 'b/c': 3, 'b/d/e': 5, 'b/d/f': 6, 'f': set([1, 2, 5])}

    assert m2['b'].d == m2.d
    assert m2['b'].extract().d == {'b/c': 3, 'b/d/e': 5, 'b/d/f': 6}

    # len() test
    assert len(m2) == 6
    assert len(m2['b']) == 3
    assert len(m2['b']['d']) == len(m2['b/d']) == 2
    assert not hasattr(m2['g'], '__len__') and isinstance(m2['g'], int)

def test_fdict_extract_contains_delitem():
    '''Test fdict extract, contains and delitem'''
    a10 = fdict()
    a10['c/b/d'] = set([1, 2])
    assert a10['c'].extract(fullpath=True).d == {'c/b/d': set([1, 2])}
    assert a10['c'].extract(fullpath=True) == {'b/d': set([1, 2])}
    assert a10['c'].extract(fullpath=False).d == {'b/d': set([1, 2])}

    # Contains test
    p=fdict()
    p['a/b/c'] = set([1, 2])
    p['a/c'] = 3
    p['a/d'] = {'e': {'f': 4}, 'g': 5}
    p['h'] = 6
    assert 'h' in p # check existence of a leaf (O(1))
    assert 'a/b/c' in p # check existence of a nested leaf (O(1))
    assert 'a/b' in p # check existence of a nested dict (O(n))
    assert 'c' in p['a/b']
    assert 'c' in p['a']['b']
    assert 'b' in p['a']
    assert not 'b' in p
    assert not 'x' in p
    assert not 'x' in p['a']

    # Del test
    p=fdict()
    p['a/b/c'] = set([1, 2])
    p['a/c'] = 3
    p['a/d'] = {'e': {'f': 4}, 'g': 5}
    p['h'] = 6
    p2 = p.copy()
    assert 'h' in p # check existence of a leaf (O(1))
    assert 'a/b/c' in p # check existence of a nested leaf (O(1))
    assert 'a/b' in p # check existence of a nested dict (O(n))
    del p['a/b/c']
    del p2['a']['b']['c']  # test both types of access (fullpath or by subselection)
    assert p == p2 == {'h': 6, 'a/d/e/f': 4, 'a/c': 3, 'a/d/g': 5}
    del p['h']
    del p2['h']
    assert p == p2 == {'a/d/e/f': 4, 'a/c': 3, 'a/d/g': 5}
    del p['a/d']
    del p2['a']['d']
    assert p == p2 == {'a/c': 3}
    try:
        # Delete inexistent key
        del p['a']['b']['x']
        assert False
    except KeyError as exc:
        assert True
    else:
        assert False

def test_fdict_update_eq():
    '''Update test and equality test'''
    a1 = {'a': set([1, 2]), 'b': {'c': 3, 'c2': 4}, 'd': 4}
    b1 = {'a': set([1, 2, 3]), 'b': {'c': 4, 'c3': 3}, 'e': 5}
    a2 = fdict(a1)
    b2 = fdict(b1)
    a11 = a1.copy()
    a12 = a1.copy()
    a13 = a1.copy()
    a14 = a1.copy()
    a15 = a1.copy()
    a21 = a2.copy()
    a22 = a2.copy()
    a23 = a2.copy()
    a24 = a2.copy()
    a25 = a2.copy()

    # no rootpath (ie, use whole dicts)
    a11.update(b1)
    a21.update(b2)
    assert a11 == {'a': set([1, 2, 3]), 'b': {'c3': 3, 'c': 4}, 'e': 5, 'd': 4}
    assert a21 == {'a': set([1, 2, 3]), 'b/c': 4, 'b/c2': 4, 'b/c3': 3, 'e': 5, 'd': 4} # by default, fdict supports recursive update (eg, c2 is kept here)

    # update a subdict with a subdict
    a12['b'].update(b1['b'])
    a22['b'].update(b2['b'])
    assert a12 == {'a': set([1, 2]), 'b': {'c3': 3, 'c2': 4, 'c': 4}, 'd': 4}
    assert a22 == {'a': set([1, 2]), 'b/c': 4, 'b/c2': 4, 'b/c3': 3, 'd': 4}
    assert a22 == a12
    assert len(a22) == 5 # len() test

    # update of a subdict with a whole dict (extracted subdict)
    a13['b'].update(b1['b'])
    b2sub = b2['b'].extract()
    a23['b'].update(b2sub)
    b2sub == {'c': 4, 'c3': 3}
    assert b2sub == {'c': 4, 'c3': 3}
    assert a23 == a22
    assert b2['b'].rootpath == b2sub.rootpath # rootpath is kept after extract
    assert b2['b'].d == b2.d # dict of a sub fdict is the same as the root fdict's dict
    assert dict(b2['b'].items()) == dict(b2sub.items())
    assert dict(b2['b'].items(fullpath=True)) == dict(b2sub.items(fullpath=True)) == b2sub.d # but the items (filtered by rootpath) will be different

    # update of a subdict with a whole dict (REALLY extracted subdict, rootpath is lost, so it is just like a new fdict)
    a14['b'].update(b1['b'])
    b2sub_orig = b2['b'].extract(fullpath=False)
    for b2sub in [b2sub_orig.to_dict(), b2sub_orig]:
        # This test should pass with both a dict and a fdict
        a24c = a24.copy()
        a24c['b'].update(b2sub)
        b2sub == {'c': 4, 'c3': 3}
        assert b2sub == {'c': 4, 'c3': 3}
        assert a24c == a22
        assert b2['b'].rootpath == 'b'
        assert not b2sub_orig.rootpath # rootpath is lost after extract(fullpath=False) (so it is like creating a new fdict)
        assert b2['b'].d == b2.d # dict of a sub fdict is the same as the root fdict's dict
        assert dict(b2['b'].items()) == dict(b2sub.items())
        assert dict(b2['b'].items(fullpath=False)) == dict(b2sub_orig.items(fullpath=True)) == b2sub_orig.d # but the items (filtered by rootpath) will be different

    # update of whole dict (extracted subdict) with subdict
    a15sub = a15['b']
    a15sub.update(b1['b'])
    a25sub = a25['b'].extract(fullpath=False)
    a25subc = a25sub.copy()
    a25sub.update(b2['b'])
    a25subc.update(b2['b'].extract(fullpath=False))
    assert a15sub == a25sub == a25subc
    assert dict(a15sub.items()) == dict(a25sub.items()) == dict(a25subc.items())

def test_fdict_setitem_nesteddict():
    '''Test fdict setitem (assignment) of a nested dict'''
    a = fdict()
    a2 = a.copy()
    a3 = a.copy()
    a4 = a.copy()
    a['a']['c'] = {'subelements': {'e': 1, 'f': {'g': 1}}}
    a2['a/c'] = {'subelements': {'e': 1, 'f': {'g': 1}}}
    a3['a']['c'] = fdict({'subelements': {'e': 1, 'f': {'g': 1}}})
    a4['a/c'] = fdict({'subelements': {'e': 1, 'f': {'g': 1}}})
    assert a.d == a2.d == a3.d == a4.d == {'a/c/subelements/f/g': 1, 'a/c/subelements/e': 1}
    a['b'] = {}
    a['b']['d'] = 2
    a['a']['b'] = 3
    assert a == {'a/c/subelements/f/g': 1, 'a/c/subelements/e': 1, 'b/d': 2, 'a/b': 3}

def test_fdict_setitem_replacement():
    '''Test emptying by setitem to empty dict and singleton replacement by a nested dict'''
    a = fdict({'a/b': 1, 'a/c': set([1,2,3]), 'd': [1, 2, 3], 'e': [1, 2, 3]})
    # emptying by setitem with empty dict
    a['d'] = {}
    assert a == {'a/c': set([1, 2, 3]), 'a/b': 1, 'e': [1, 2, 3]}
    # replace singleton with a dict
    a['e'] = {'f': 2, 'g': 3}
    assert a == {'a/c': set([1, 2, 3]), 'a/b': 1, 'e/g': 3, 'e/f': 2}
    # replace dict with a singleton (does not work, both will coexist)
    a['a'] = 2
    assert a == {'a': 2, 'a/c': set([1, 2, 3]), 'a/b': 1, 'e/g': 3, 'e/f': 2}

def test_fdict_todictnested():
    '''Test to_dict_nested() conversion'''
    a = fdict({'a/b': 1, 'a/c': set([1, 2]), 'd': 3})
    adict = a.to_dict_nested()
    assert adict == {'a': {'b': 1, 'c': set([1, 2])}, 'd': 3}
    assert not isinstance(adict, fdict) and isinstance(adict, dict)

def test_fdict_update_with_empty_dict():
    '''Test update of empty subdict'''
    a = fdict()
    a['a'] = {}
    a['a'].update({'b': 1, 'c': 2})
    assert a == {'a/c': 2, 'a/b': 1}

def test_fdict_update_nesteddict():
    '''Test fdict update of a nested dict'''
    a = fdict()
    a['a'] = {}
    a['a']['b'] = 2
    a2 = a.copy()
    a3 = a.copy()
    a4 = a.copy()
    a['a']['c'].update({'subelements': {'e': 1, 'f': {'g': 1}}})
    a2['a/c'].update({'subelements': {'e': 1, 'f': {'g': 1}}})
    a3['a']['c'].update(fdict({'subelements': {'e': 1, 'f': {'g': 1}}}))
    a4['a/c'].update(fdict({'subelements': {'e': 1, 'f': {'g': 1}}}))
    assert a.d == a2.d == a3.d == a4.d == {'a/c/subelements/f/g': 1, 'a/c/subelements/e': 1, 'a/b': 2}

def test_fdict_fastview_basic():
    '''Test fastview mode basic features'''
    a = fdict(fastview=True)
    a['a/b/c'] = 1
    a['a']['b']['d'] = 2
    a['a']['e']['f'] = 3
    a['a']['e']['g']['h'] = 4
    a['a']['e']['g']['i'] = 5

    assert dict(a.d.items()) == dict([('a/e/g/', set(['a/e/g/i', 'a/e/g/h'])), ('a/e/f', 3), ('a/e/', set(['a/e/g/', 'a/e/f'])), ('a/', set(['a/e/', 'a/b/'])), ('a/b/c', 1), ('a/b/d', 2), ('a/b/', set(['a/b/c', 'a/b/d'])), ('a/e/g/i', 5), ('a/e/g/h', 4)])
    assert dict(a.items()) == dict([('a/e/f', 3), ('a/b/c', 1), ('a/b/d', 2), ('a/e/g/i', 5), ('a/e/g/h', 4)])  # items() on a fastview fdict should hide the nodes (eg, 'a/b/') and only show leafs, so that behavior is comparable to a non-fastview fdict
    assert dict(a['a']['e'].items()) == dict([('g/i', 5), ('g/h', 4), ('f', 3)])
    assert dict(a['a']['e'].items(fullpath=True)) == dict([('a/e/g/i', 5), ('a/e/g/h', 4), ('a/e/f', 3)])  # test recursive fastview items()

    assert dict(a['a']['e'].items(fullpath=True)) == dict([('a/e/g/i', 5), ('a/e/g/h', 4), ('a/e/f', 3)])
    assert set(a['a']['e'].keys(fullpath=True)) == set(['a/e/g/i', 'a/e/g/h', 'a/e/f'])
    assert set(a['a']['e'].values()) == set([5, 4, 3])
    assert set(a['a'].values()) == set([1, 2, 3, 4, 5])  # use set() when we do not case about order in a list
    assert dict(a['j'].items()) == {}  # empty nested dict
    assert list(a['j'].keys()) == []
    assert list(a['j'].values()) == []

    # test fastview contains
    assert 'a' in a
    assert 'a/' in a
    assert 'a/e/g/h' in a
    assert 'g' in a['a']['e']
    assert 'g' in a['a/e']
    assert 'g/h' in a['a/e']
    assert not 'a/e/g/x' in a
    assert not 'x' in a

    # test fastview copy
    from copy import deepcopy
    assert a.d == {'a/e/g/': set(['a/e/g/i', 'a/e/g/h']), 'a/e/f': 3, 'a/e/': set(['a/e/g/', 'a/e/f']), 'a/': set(['a/e/', 'a/b/']), 'a/b/c': 1, 'a/b/d': 2, 'a/b/': set(['a/b/c', 'a/b/d']), 'a/e/g/i': 5, 'a/e/g/h': 4}
    a2 = a.copy()
    for k in a.d.keys():
        if k.endswith(a.delimiter):
            # all nodes should be copied as different objects
            assert id(a.d[k]) != id(a2.d[k])
    # test deepcopy
    if sys.version_info >= (2,7):
        a3 = deepcopy(a)
        for k in a.d.keys():
            # with a deep copy, all items (not just nodes) should be copied as different objects
            if hasattr(a.d[k], '__len__'):  # compare only collections (because for scalars we can't know if Python caches, or at least I did not find how to check that)
                assert id(a.d[k]) != id(a3.d[k])  # could replace by equivalent: a.d[k] is not a3.d[k]
    # check that a is unchanged after copy
    assert a.d == {'a/e/g/': set(['a/e/g/i', 'a/e/g/h']), 'a/e/f': 3, 'a/e/': set(['a/e/g/', 'a/e/f']), 'a/': set(['a/e/', 'a/b/']), 'a/b/c': 1, 'a/b/d': 2, 'a/b/': set(['a/b/c', 'a/b/d']), 'a/e/g/i': 5, 'a/e/g/h': 4}
    # test deepcopy of a nested dict with a different delimiter
    if sys.version_info >= (2,7):
        b = fdict({'a': {'b': 1, 'c': set([1, 2])}, 'd': 3}, delimiter='.', fastview=True)
        bsub = deepcopy(b['a'])
        assert bsub == b['a']

def test_fdict_fastview_del():
    '''Test fastview del'''
    a = fdict({'a/e/g/': set(['a/e/g/i', 'a/e/g/h']), 'a/e/f': 3, 'a/e/': set(['a/e/g/', 'a/e/f']), 'a/': set(['a/e/', 'a/b/']), 'a/b/c': 1, 'a/b/d': 2, 'a/b/': set(['a/b/c', 'a/b/d']), 'a/e/g/i': 5, 'a/e/g/h': 4}, fastview=True)
    a2 = a.copy()
    # leaf deletion
    assert set(a['a'].keys(fullpath=True, nodes=True)) == set(['a/e/', 'a/e/g/', 'a/b/', 'a/b/c', 'a/b/d', 'a/e/f', 'a/e/g/i', 'a/e/g/h'])
    del a['a/e/g/h']
    del a2['a']['e']['g']['h']
    assert a.d == a2.d == {'a/e/g/': set(['a/e/g/i']), 'a/e/f': 3, 'a/e/': set(['a/e/g/', 'a/e/f']), 'a/': set(['a/e/', 'a/b/']), 'a/b/c': 1, 'a/b/d': 2, 'a/b/': set(['a/b/c', 'a/b/d']), 'a/e/g/i': 5}
    assert 'a/e/g/h' not in list(a['a'].keys(fullpath=True, nodes=True))
    # node deletion
    assert set(a['a/e'].keys()) == set(a2['a']['e'].keys()) == set(['g/i', 'f'])
    assert set(a['a/e'].keys(nodes=True)) == set(a['a']['e'].keys(nodes=True)) == set(['g/', 'g/i', 'f'])
    del a['a/e']
    del a2['a']['e']
    assert a.d == a2.d == {'a/': set(['a/b/']), 'a/b/c': 1, 'a/b/d': 2, 'a/b/': set(['a/b/c', 'a/b/d'])}
    assert a == a2 == {'a/b/c': 1, 'a/b/d': 2}
    assert not set(a['a/e'].keys()) and not dict(a2['a']['e'])
    assert set(a['a'].keys(fullpath=True, nodes=True)) == set(['a/b/', 'a/b/d', 'a/b/c'])

def test_fdict_fastview_metadata_nested_dict():
    '''Test fastview nodes metadata creation with nested dicts and at creation'''
    a = fdict({'a/b': 1, 'a/c': set([1,2,3]), 'd': [1, 2, 3]}, fastview=True)
    # add nested dict
    a['g'] = {'h': {'i': {'j': 6}, 'k': 7}, 'l': 8}
    assert a.d == {'g/l': 8, 'g/h/i/j': 6, 'g/h/i/': set(['g/h/i/j']), 'a/': set(['a/b', 'a/c']), 'a/c': set([1, 2, 3]), 'a/b': 1, 'g/h/': set(['g/h/k', 'g/h/i/']), 'g/': set(['g/l', 'g/h/']), 'g/h/k': 7, 'd': [1, 2, 3]}

def test_fdict_fastview_setitem_noconflict_delitem():
    '''Test fdict fastview setitem replacement of singleton by nested dict and inversely + delitem'''
    a = fdict({'a/b': 1, 'a/c': set([1,2,3]), 'd': [1, 2, 3]}, fastview=True)
    # singleton to nested dict
    a['d/e'] = 4
    a['d/f'] = 5
    assert ('d', [1, 2, 3]) not in a.viewitems(nodes=True)
    # nested dict to singleton
    a['a'] = 2
    # add nested dict (and check metadata creation for each parent of nested leaves in the nested dict)
    a['g'] = {'h': {'i': {'j': 6}, 'k': 7}, 'l': 8}
    assert a['a'] == 2
    # delitem singleton
    del a['g/h/i/j']
    assert a.d == {'a': 2, 'd/': set(['d/f', 'd/e']), 'g/l': 8, 'd/f': 5, 'd/e': 4, 'g/h/': set(['g/h/k']), 'g/': set(['g/l', 'g/h/']), 'g/h/k': 7}
    # delitem nested dict
    del a['d']
    assert a.d == {'a': 2, 'g/l': 8, 'g/h/': set(['g/h/k']), 'g/': set(['g/l', 'g/h/']), 'g/h/k': 7}

def test_fdict_fastview_delitem():
    '''Test fdict fastview delitem'''
    # Test leaf deletion
    a = fdict({'a': {'b': 1, 'c': set([1, 2]), 'd': {'e': 3}}, 'f': 4}, fastview=True)

    assert a.d == {'a/c': set([1, 2]), 'a/b': 1, 'f': 4, 'a/d/': set(['a/d/e']), 'a/d/e': 3, 'a/': set(['a/d/', 'a/c', 'a/b'])}
    del a['a']['d']['e']
    assert a.d == {'a/c': set([1, 2]), 'a/b': 1, 'f': 4, 'a/': set(['a/c', 'a/b'])}
    del a['a/c']
    assert a.d == {'a/b': 1, 'f': 4, 'a/': set(['a/b'])}
    del a['a/b']
    assert a.d == {'f': 4}
    del a['f']
    assert a.d == a == {}

    # Test node deletion
    a = fdict({'a': {'b': {'c': set([1, 2])}}, 'd': 3}, fastview=True)
    a2 = a.copy()
    assert a.d == a2.d == {'a/b/c': set([1, 2]), 'd': 3, 'a/': set(['a/b/']), 'a/b/': set(['a/b/c'])}
    del a['a']['b']
    del a2['a/b']
    assert a.d == a2.d == {'d': 3}

def test_fdict_init_fdict():
    '''Test fdict initialization with another fdict'''
    a = fdict({'a': {'b': 1, 'c': set([1, 2])}})
    b = fdict(a)
    assert b == a
    assert id(b.d) != id(a.d)

def test_fdict_init_tuples():
    '''Test fdict init with a non-dict object (eg, list of tuples)'''
    a = fdict([('a', {'b': 1, 'c': set([1, 2])})])
    assert a == {'a/c': set([1, 2]), 'a/b': 1}
    a = fdict([('a', {'b': 1, 'c': set([1, 2])})], fastview=True)  # fastview mode
    assert a == {'a/c': set([1, 2]), 'a/b': 1}
    assert a.d == {'a/c': set([1, 2]), 'a/b': 1, 'a/': set(['a/c', 'a/b'])}

def test_fdict_str_repr():
    '''Test fdict str and repr'''
    def convert_sets_to_lists(d):
        for k, v in d.items():
            if isinstance(v, set):
                d[k] = list(v)
        return d

    # No fastview
    a = fdict({'a': {'b': 1, 'c': [1, 2]}})
    assert ast.literal_eval(str(a)) == ast.literal_eval(repr(a)) == a.to_dict()
    assert ast.literal_eval(str(a['a'])) == ast.literal_eval(repr(a['a'])) == a['a'].to_dict()

    a = fdict({'a': {'b': 1, 'c': [1, 2], 'd': {'e': 1}}}, fastview=True)  # fastview mode
    asub = a['a']
    # Need to convert all sets to lists, else literal_eval will fail
    a.d = convert_sets_to_lists(a.d)
    # cannot use ast for asub with fastview because of nodes, they will always be shown as sets (unless we extract but then there is no rootpath and we cannot test this branch)
    assert ast.literal_eval(str(a)) == ast.literal_eval(repr(a)) == a.d
    assert "'d/'" not in str(asub) and  "'c': [1, 2]" in str(asub) and "'b': 1" in str(asub) and "'d/e': 1" in str(asub)
    assert "'d/'" in repr(asub) and "'c': [1, 2]" in repr(asub) and "'b': 1" in repr(asub) and "'d/e': 1" in repr(asub)  # nodes are present in repr but not in str

def test_fdict_str_nodict():
    '''Test fdict string representation and repr if provided an internal dict-like object that has no str method'''
    class nostrdict(object):
        def __init__(self, d=None):
            if d is None:
                d = {}
            self.d = d
            self.viewkeys, self.viewvalues, self.viewitems = fdict._getitermethods(self.d)
            self.keys, self.values, self.items = fdict._getitermethods(self.d)
            return
        def __getitem__(self, key):
            return self.d.__getitem__(key)
        def __setitem__(self, key, d):
            return self.d.__setitem__(key, d)
        __str__ = None
        __repr__ = None

    anodict = nostrdict({'a': 1})
    assert dict(anodict.viewitems()) == {'a': 1}

    a = fdict(anodict, rootpath='lala')
    a.rootpath = ''  # cheat to bypass object conversion to dict at init, and then remove rootpath
    assert dict(a.items()) == {'a': 1}
    assert str(a) == repr(a) == "{'a': 1}"

def test_fdict_extract_fastview():
    '''Test fdict extract with fastview'''
    a = fdict({'a': {'b': 1, 'c': [1, 2], 'd': {'e': 1}}}, fastview=True)  # fastview mode
    asub = a['a'].extract(fullpath=True)
    assert asub == fdict({'c': [1, 2], 'b': 1, 'd/e': 1})
    assert asub.d == {'a/d/': set(['a/d/e']), 'a/c': [1, 2], 'a/b': 1, 'a/': set(['a/d/', 'a/c', 'a/b']), 'a/d/e': 1}

    asub2 = a['a'].extract(fullpath=False)
    assert asub2 == {'c': [1, 2], 'b': 1, 'd/e': 1}
    assert asub2.d == {'d/': set(['d/e']), 'c': [1, 2], 'b': 1, 'd/e': 1}

def test_fdict_setitem_update_fdict():
    '''Test fdict setitem+update with another fdict or dict'''
    a = fdict({'a': {'b': 1, 'c': set([1, 2])}})
    a1 = a.copy()
    a2 = a.copy()
    a3 = a.copy()
    a4 = a.copy()
    a5 = a.copy()
    a6 = a.copy()

    b1 = fdict({'b': 2, 'd': 3})
    b2 = {'b': 2, 'd': 3}
    b3 = fdict({'e': {'f': 4}})

    a1['a'] = b1
    a2['a'] = b2
    a3['a'] = b3['e']
    # Node replacement fails with non-fastview fdict for now (else it would imply calling viewitems and being super slow! Then it would be no better than fastview mode)
    #assert a1 == a2 == {'a/d': 3, 'a/b': 2}
    #assert ('a/c', set([1, 2])) not in a1.items()
    #assert ('a/c', set([1, 2])) not in a2.items()
    #assert a3 == {'a/f': 4}
    a4['a'].update(b1)
    a5['a'].update(b2)
    a6['a'].update(b3['e'])
    assert a4 == a5 == {'a/d': 3, 'a/c': set([1, 2]), 'a/b': 2}
    assert ('a/c', set([1, 2])) in a4.items()
    assert ('a/c', set([1, 2])) in a5.items()
    assert a6 == {'a/f': 4, 'a/c': set([1, 2]), 'a/b': 1}

def test_fdict_setitem_update_fdict_fastview():
    '''Test fdict fastview setitem+update with another fdict or dict'''
    a = fdict({'a': {'b': 1, 'c': set([1, 2])}}, fastview=True)
    a1 = a.copy()
    a2 = a.copy()
    a3 = a.copy()
    a4 = a.copy()
    a5 = a.copy()
    a6 = a.copy()

    b1 = fdict({'b': 2, 'd': 3})
    b2 = {'b': 2, 'd': 3}
    b3 = fdict({'e': {'f': 4}}, fastview=True)

    a1['a'] = b1
    a2['a'] = b2
    a3['a'] = b3['e']
    assert a1.d == a2.d == {'a/d': 3, 'a/b': 2, 'a/': set(['a/d', 'a/b'])}
    assert ('a/c', set([1, 2])) not in a1.items()
    assert ('a/c', set([1, 2])) not in a2.items()
    assert a3.d == {'a/f': 4, 'a/': set(['a/f'])}
    a4['a'].update(b1)
    a5['a'].update(b2)
    a6['a'].update(b3['e'])
    assert a4.d == a5.d == {'a/d': 3, 'a/c': set([1, 2]), 'a/b': 2, 'a/': set(['a/c', 'a/b', 'a/d'])}
    assert ('a/c', set([1, 2])) in a4.items() and 'a/d' in a4.d['a/']
    assert ('a/c', set([1, 2])) in a5.items() and 'a/d' in a5.d['a/']
    assert a6.d == {'a/f': 4, 'a/c': set([1, 2]), 'a/b': 1, 'a/': set(['a/f', 'a/c', 'a/b'])}

def test_fdict_update_exception():
    '''Test fdict update exception if supplied non-dict object'''
    a = fdict()
    try:
        a.update([1, 2])
        assert False
    except ValueError:
        assert True
    else:
        assert False

def test_fdict_viewvalues():
    '''Test fdict viewvalues()'''
    # No fastview
    a = fdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    assert set(a.values()) == set([1, 2, 3])
    assert set(a['a'].values()) == set([1, 2])
    # Fastview mode
    a = fdict({'a': {'b': 1, 'c': 2, 'e': {'f': 4}}, 'd': 3}, fastview=True)
    assert set(a.values()) == set([1, 2, 3, 4])
    assert set(a['a'].values()) == set([1, 2, 4])
    # test with fastview mode and nodes=True
    v1 = list(a.values(nodes=True))
    assert set(['a/e/f']) in v1 and set(['a/b', 'a/c', 'a/e/']) in v1
    v2 = list(a['a'].values(nodes=True))
    assert set(['e/f']) in v2
    # test with fullpath
    v3 = list(a['a'].values(nodes=True, fullpath=True))
    assert set(['a/e/f']) in v3

def test_fdict_viewkeys():
    '''Test fdict viewkeys()'''
    # No fastview
    a = fdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    assert set(a.keys()) == set(['a/c', 'd', 'a/b'])
    assert set(a['a'].keys()) == set(['c', 'b'])
    # Fastview mode
    a = fdict({'a': {'b': 1, 'c': 2, 'e': {'f': 4}}, 'd': 3}, fastview=True)
    assert set(a.keys()) == set(['a/c', 'd', 'a/e/f', 'a/b'])
    assert set(a['a'].keys()) == set(['c', 'b', 'e/f'])
    # test with fastview mode and nodes=True
    v1 = set(a.keys(nodes=True))
    assert v1 == set(['a/c', 'd', 'a/e/f', 'a/e/', 'a/', 'a/b'])
    v2 = set(a['a'].keys(nodes=True))
    assert v2 == set(['e/', 'c', 'b', 'e/f'])
    # test with fullpath
    v3 = set(a['a'].keys(nodes=True, fullpath=True))
    assert v3 == set(['a/e/', 'a/c', 'a/b', 'a/e/f'])

def test_fdict_viewitems():
    '''Test fdict viewitems()'''
    # No fastview
    a = fdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    assert dict(a.items()) == fdict.flatkeys({'a': {'b': 1, 'c': 2}, 'd': 3})
    assert dict(a['a'].items()) == {'c': 2, 'b': 1}
    # Fastview mode
    a = fdict({'a': {'b': 1, 'c': 2, 'e': {'f': 4}}, 'd': 3}, fastview=True)
    assert dict(a.items()) == fdict.flatkeys({'a': {'b': 1, 'c': 2, 'e': {'f': 4}}, 'd': 3})
    assert dict(a['a'].items()) == {'c': 2, 'b': 1, 'e/f': 4}
    # test with fastview mode and nodes=True
    v1 = dict(a.items(nodes=True))
    assert v1 == {'a/c': 2, 'a/b': 1, 'a/e/f': 4, 'a/e/': set(['a/e/f']), 'a/': set(['a/e/', 'a/c', 'a/b']), 'd': 3}
    v2 = dict(a['a'].items(nodes=True))
    assert v2 == {'e/': set(['e/f']), 'b': 1, 'c': 2, 'e/f': 4}
    # test with fullpath
    v3 = dict(a['a'].items(nodes=True, fullpath=True))
    assert v3 == {'a/e/': set(['a/e/f']), 'a/c': 2, 'a/b': 1, 'a/e/f': 4}

def test_fdict_view_override_rootpath():
    '''Test fdict view* override rootpath'''
    a = fdict({'a': {'b': 1, 'c': 2, 'e': {'f': 4}}, 'd': 3}, fastview=True)
    assert list(a.values(rootpath='a/e')) == [4]
    assert list(a.keys(rootpath='a/e')) == ['f']
    assert list(a.items(rootpath='a/e')) == [('f', 4)]

def test_fdict_eq_extended():
    '''Test fdict equality/inequality'''
    a = fdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    # Unequal by size
    assert a != {'a': 1}
    assert a != fdict({'a': 1})
    assert a['a'] != fdict({'b': 1, 'c': 2, 'e': 4})
    # Unequal by value
    assert a != {'a': {'b': 1, 'c': 2}, 'd': -1}
    assert a != {'a': {'b': 1, 'c': -1}, 'd': 3}
    # Equal
    assert a == {'a': {'b': 1, 'c': 2}, 'd': 3}
    assert a == fdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    assert a['a'] == {'b': 1, 'c': 2}
    assert a['a'] == fdict({'b': 1, 'c': 2})
    # Equality with subclasses or variants
    assert a == fdict({'a': {'b': 1, 'c': 2}, 'd': 3}, fastview=True)
    assert a['a'] == fdict({'b': 1, 'c': 2}, fastview=True)
    assert a == sfdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    assert a['a'] == sfdict({'b': 1, 'c': 2})

def test_fdict_not():
    '''Test fdict truth value (not d)'''
    a = fdict({'a': 1})
    b = fdict({})
    assert (not a) == False
    assert (not b) == True

def test_fdict_empty_list():
    '''Test fdict assigning an empty list'''
    a = fdict({})
    a['a'] = {}
    assert a == {}
    a['b'] = []
    a['b'].append(1)
    assert a == {'b': [1]}

def test_fdict_pop_popitem():
    '''Test fdict pop and popitem'''
    a = fdict({'a': {'b': 1, 'c': 2}, 'd': 3})
    a2 = a.copy()

    leaf = a.pop('a/b')
    assert leaf == 1
    assert a == {'a/c': 2, 'd': 3}
    node = a.pop('a')
    assert node.d == {'a/c': 2}
    assert a == {'d': 3}
    inexistent = a.pop('e', 'inexistent!')
    assert inexistent == 'inexistent!'


    a2.popitem()
    a2.popitem()
    a2.popitem()
    try:
        a2.popitem()
        assert False
    except KeyError:
        assert True
    else:
        assert False

def test_fdict_fastview_pop_popitem():
    '''Test fdict with fastview pop and popitem'''
    # fastview mode
    a = fdict({'a': {'b': 1, 'c': 2}, 'd': 3}, fastview=True)
    a2 = a.copy()

    leaf = a.pop('a/b')
    assert leaf == 1
    assert a.d == {'a/': set(['a/c']), 'a/c': 2, 'd': 3}
    node = a.pop('a')
    assert node.d == {'a/c': 2, 'a/': set(['a/c'])}
    assert a == {'d': 3}
    inexistent = a.pop('e', 'inexistent!')
    assert inexistent == 'inexistent!'


    a2.popitem()
    a2.popitem()
    a2.popitem()
    try:
        a2.popitem()
        assert False
    except KeyError:
        assert True
    else:
        assert False

def test_fdict_nodel_mode():
    '''Test fdict nodel mode'''
    # Test view* methods in nodel mode
    a = fdict({'a': {'b': 1, 'c': 2, 'd': {'e': 3}}, 'f': 4}, nodel=True)
    assert set(a.keys()) == set(['a/c', 'a/b', 'a/d/e', 'f'])
    assert set(a.keys(nodes=True)) == set(['a/d/', 'a/c', 'a/b', 'a/', 'a/d/e', 'f'])
    assert set(a['a'].keys()) == set(['c', 'b', 'd/e'])
    assert set(a['a'].keys(nodes=True)) == set(['d/', 'c', 'b', 'd/e'])

    assert set(a.values()) == set([2, 1, 4, 3])
    assert set(a.values(nodes=True)) == set([2, 1, 4, None, 3, None])
    assert set(a['a'].values()) == set([2, 1, 3])
    assert set(a['a'].values(nodes=True)) == set([2, 1, None, 3])

    assert dict(a.items()) == {'a/d/e': 3, 'a/c': 2, 'a/b': 1, 'f': 4}
    assert dict(a.items(nodes=True)) == {'a/c': 2, 'a/b': 1, 'f': 4, 'a/d/': None, 'a/d/e': 3, 'a/': None}
    assert dict(a['a'].items()) == {'c': 2, 'b': 1, 'd/e': 3}
    assert dict(a['a'].items(nodes=True)) == {'d/': None, 'c': 2, 'b': 1, 'd/e': 3}

    # Test normal fdict stripped of viewkeys(), should not detect nodes anymore
    a = fdict({'a': {'b': 1, 'c': 2}}, nodel=False)
    a.viewkeys = lambda *args, **kwargs: []
    assert not ('a' in a)

    # Test nodel fdict, stripped of viewkeys() it will still find nodes (because nodes are signalled by creating an empty key)
    a = fdict({'a': {'b': 1, 'c': 2}}, nodel=True)
    b = fdict(nodel=True)
    c = fdict(nodel=True)
    b['a'] = {'b': 1, 'c': 2}
    c.update({'a': {'b': 1, 'c': 2}})
    a.viewkeys = lambda *args, **kwargs: []
    a.viewkeys()
    assert ('a' in a) and ('a/' in a)
    assert ('a' in b) and ('a/' in b)
    assert ('a' in c) and ('a/' in c)
    assert not ('x' in a) and not ('x' in b) and not ('x' in c)  # just to check it does not just return True for any inexistent node...
    assert ('a/b') in a and ('a/b') in b and ('a/c') in a

    # delitem cannot work in nodel mode
    del a['a']
    assert a.d == {'a/c': 2, 'a/b': 1, 'a/': None}

    # check metadata building
    a = fdict(nodel=True)
    a._build_metadata_nodel(fullkeys=['x/y', 'x/w/', 'z/'])  # should not create parents for nodes such as x/w/
    assert a.d == {'x/': None}

    # check metadata building by assignment + is not created twice for same parent
    a = fdict(nodel=True)
    a['a/b'] = 1
    a['a']['c'] = 2
    assert a == {'a/b': 1, 'a/c': 2}
    assert a.d == {'a/': None, 'a/c': 2, 'a/b': 1}
    # Test equality
    a = fdict({'a': {'b': 1, 'c': 2}}, nodel=True)
    b = fdict({'a': {'b': 1, 'c': 2}}, nodel=True)
    c = fdict({'a': {'b': 1, 'c': 2}}, nodel=False)
    d = fdict({'a': {'b': 1, 'c': 2, 'd': 3}}, nodel=True)
    assert a == {'a': {'b': 1, 'c': 2}}  # with no nodes, should accept this representation
    assert a.d == {'a/': None, 'a/c': 2, 'a/b': 1}
    assert a == b
    assert a == c
    assert not (a == d) and a != d  # test inequality

def test_sfdict_basic():
    '''sfdict: basic tests'''
    # Sfdict test
    g = sfdict(filename='testshelf')
    g['a'] = 3
    g['b/c'] = set([1, 3, 4])
    g['d'] = {}
    assert g == {'a': 3, 'b/c': set([1, 3, 4])}
    assert g == {'a': 3, 'b/c': set([1, 3, 4]), 'd': {}} # empty dicts are stripped out before comparison
    assert g['b'].filename == g.filename # check that subdicts also share the same filename (parameters propagation)
    g.sync()  # commit the changes

    # Sfdict reloading test
    h = sfdict(filename='testshelf')
    assert h == g
    g.close()
    h.close(delete=True)

def test_sfdict_dictinit():
    '''Test sfdict initialization with a dict'''
    g = sfdict(d={'a': {'b': set([1, 2])}})
    assert g == {'a/b': set([1, 2])}
    assert id(g.d) == id(g['a'].d)  # ensure the same dict is shared with nested sfdict
    g.close(delete=True)

def test_sfdict_forcedbm_filename():
    '''Test sfdict forcedbm=True and get_filename()'''
    g = sfdict(filename='testshelf2')
    assert g.get_filename() == 'testshelf2'
    g.close(delete=True)
    i = sfdict()
    assert len(i.get_filename()) > 0
    i.close(delete=True)
    # Test forcedbm
    j = sfdict(forcedumbdbm=True)
    assert len(j.get_filename()) > 0
    j.close(delete=True)

def test_sfdict_autosync():
    '''Test sfdict autosync'''
    # With autosync, updating a nested object is saved to disk
    g = sfdict(d={'a': {'b': set([1, 2])}}, autosync=True)
    assert 'shelve' in str(type(g.d)) or 'instance' in str(type(g.d))  # check the internal dict is a db shelve
    g['a']['b'].add(3)
    assert g['a/b'] == set([1, 2, 3])
    g['d'] = 4  # trigger the autosync on setitem
    assert g == {'a/b': set([1, 2, 3]), 'd': 4}
    filename = g.get_filename()
    # try to access the same shelve before closing/syncing it
    h = sfdict(filename=filename)
    assert h['a/b'] == set([1, 2, 3])
    assert (h['a/b/c'] == 3) == False
    g.close()
    h.close(delete=True)
    # Without autosync, the change is lost
    g = sfdict(d={'a': {'b': set([1, 2])}}, autosync=False)
    g['a']['b'].add(3)
    assert g['a/b'] == set([1, 2, 3])
    g['d'] = 4
    filename = g.get_filename()
    h = sfdict(filename=filename)
    if not '__pypy__' in sys.builtin_module_names:
        # pypy seems to always commit the changes, even without sync!
        # also happens on Travis, I don't know why, maybe on some linuxes the commits are instantaneous?
        try:
            assert h['a/b'] == {}  # not synced, h has nothing
        except AssertionError:
            pass
    h.close()
    g.sync()
    h = sfdict(filename=filename)  # reopen after syncing g
    assert h == {'a/b': set([1, 2, 3]), 'd': 4}
    g.close()
    h.close(delete=True)

def test_sfdict_writeback():
    '''Test sfdict writeback'''
    # Writeback=True
    g = sfdict(d={'a': {'b': set([1, 2])}, 'd': {'e': set([1, 2])}}, writeback=True)
    g['a/b'].add(3)
    g['d']['e'].add(3)
    assert g['a/b'] == set([1, 2, 3])
    assert g['d']['e'] == set([1, 2, 3])
    g.close(delete=True)
    # Writeback=False
    g = sfdict(d={'a': {'b': set([1, 2])}, 'd': {'e': set([1, 2])}}, writeback=False)
    g['a/b'].add(3)
    g['d']['e'].add(3)
    assert g['a/b'] == set([1, 2])
    assert g['d']['e'] == set([1, 2])
    temp = g['a']['b']
    temp.add(3)
    g['a/b'] = temp
    g['d']['e'] = temp
    assert id(g.d) == id(g['d'].d)
    assert g['a/b'] == set([1, 2, 3])
    assert g['d']['e'] == set([1, 2, 3])
    g.close(delete=True)
