""" tests of publ.utils class """

import pytest

from publ.utils import TagSet

def test_TagSet_membership():
    """ Membership tests for TagSet """
    items = ('a','S','d','F')
    others = ('Q','w','E','r')
    ts = TagSet(items)

    assert len(ts) == 4

    for item in items:
        assert item in ts
        assert item.lower() in ts
        assert item.upper() in ts
        assert item.casefold() in ts

    for item in ts:
        assert item.casefold() in {t.casefold() for t in items}

    for item in others:
        assert item not in ts
        assert item.lower() not in ts
        assert item.upper() not in ts
        assert item.casefold() not in ts

def test_TagSet_operators():
    """ Test operators  on TagSet """
    assert TagSet(('a','s','D','F')) == TagSet(('A','S','d','f'))
    assert TagSet(('a','s','D','F')) == {'A','S','d','f'}
    assert TagSet(('a','s','d','f')) != TagSet(('a','s','d'))
    assert TagSet(('a','s','d','f')) != {'a','s','d'}

    assert TagSet(('a','S','d')) | TagSet(('A','s','D','F')) == TagSet(('a','s','d','f'))
    assert TagSet(('a','S','d')) | {'A','s','D','F'} == TagSet(('a','s','d','f'))

    assert TagSet(('a','S','d')) & TagSet(('a','D')) == TagSet(('A','d'))
    assert TagSet(('a','S','d')) & {'a','D'} == TagSet(('A','d'))

    assert TagSet(('a','s','d','f')) ^ TagSet(('A','F','G','h')) == TagSet(('s','d','g','h'))
    assert TagSet(('a','s','d','f')) ^ {'A','F','G','h'} == TagSet(('s','d','g','h'))

    assert TagSet(('a','s','d','f')) - {'A','D','g','G'} == {'s','f'}

    assert TagSet(('1','2','3')) < TagSet(('1','2','3','4'))
    assert TagSet(('1','2','3')) < {'1','2','3','4'}

    assert TagSet(('1','2','3')) <= TagSet(('1','2','3','4'))
    assert TagSet(('1','2','3')) <= {'1','2','3','4'}
