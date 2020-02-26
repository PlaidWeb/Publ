""" tests of publ.utils class """

from publ.utils import TagSet


def test_tagset_membership():
    """ Membership tests for TagSet """
    items = ('a', 'S', 'd', 'F')
    others = ('Q', 'w', 'E', 'r')
    tags = TagSet(items)

    assert bool(tags)
    assert not bool(TagSet())
    assert not bool(TagSet([]))
    assert not bool(TagSet({}))

    assert len(tags) == 4

    assert hash(TagSet(('a', 's', 'd'))) == hash(TagSet(('s', 'd', 'a')))
    assert hash(TagSet(('a', 's', 'd'))) == hash(TagSet(('A', 'S', 'D')))
    assert hash(TagSet(items)) != hash(TagSet(others))

    for item in items:
        assert item in tags
        assert item.lower() in tags
        assert item.upper() in tags
        assert item.casefold() in tags

    for item in tags:
        assert item.casefold() in {t.casefold() for t in items}

    for item in others:
        assert item not in tags
        assert item.lower() not in tags
        assert item.upper() not in tags
        assert item.casefold() not in tags


def test_tagset_operators():
    """ Test operators  on TagSet """
    assert TagSet(('a', 's', 'D', 'F')) == TagSet(('A', 'S', 'd', 'f'))
    assert TagSet(('a', 's', 'D', 'F')) == {'A', 'S', 'd', 'f'}
    assert TagSet(('a', 's', 'd', 'f')) != TagSet(('a', 's', 'd'))
    assert TagSet(('a', 's', 'd', 'f')) != {'a', 's', 'd'}

    assert TagSet(('a', 'S', 'd')) | TagSet(('A', 's', 'D', 'F')) == TagSet(('a', 's', 'd', 'f'))
    assert TagSet(('a', 'S', 'd')) | {'A', 's', 'D', 'F'} == TagSet(('a', 's', 'd', 'f'))

    assert TagSet(('a', 'S', 'd')) & TagSet(('a', 'D')) == TagSet(('A', 'd'))
    assert TagSet(('a', 'S', 'd')) & {'a', 'D'} == TagSet(('A', 'd'))

    assert TagSet(('a', 's', 'd', 'f')) ^ TagSet(
        ('A', 'F', 'G', 'h')) == TagSet(('s', 'd', 'g', 'h'))
    assert TagSet(('a', 's', 'd', 'f')) ^ {'A', 'F', 'G', 'h'} == TagSet(('s', 'd', 'g', 'h'))

    assert TagSet(('a', 's', 'd', 'f')) - {'A', 'D', 'g', 'G'} == {'s', 'f'}

    assert TagSet(('1', '2', '3')) < TagSet(('1', '2', '3', '4'))
    assert TagSet(('1', '2', '3')) < {'1', '2', '3', '4'}

    assert TagSet(('1', '2', '3')) <= TagSet(('1', '2', '3', '4'))
    assert TagSet(('1', '2', '3')) <= {'1', '2', '3', '4'}

    # pylint:disable=unneeded-not
    assert not TagSet(('a', 's', 'd')) < TagSet(('a', 's', 'd'))
    assert not TagSet(('a', 's', 'd')) < TagSet(('q', 'w', 'e'))
    assert not TagSet(('a', 's', 'd')) <= TagSet(('q', 'w', 'e'))
