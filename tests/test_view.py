""" Test of view functionality """
# pylint:disable=missing-function-docstring

from publ import view

from . import PublMock


def test_view_refinement():
    app = PublMock()
    with app.app_context():
        test_view = view.View.load({})
        assert test_view.spec == {}

        test_view = test_view(category='foo')
        assert test_view.spec['category'] == 'foo'

        test_view = test_view(count=10)
        assert test_view.spec['category'] == 'foo'
        assert test_view.spec['count'] == 10

        test_view = test_view(recurse=True)
        assert test_view.spec['category'] == 'foo'
        assert test_view.spec['count'] == 10
        assert test_view.spec['recurse'] is True

        test_view = test_view(count=25)
        assert test_view.spec['category'] == 'foo'
        assert test_view.spec['count'] == 25
        assert test_view.spec['recurse'] is True

        test_view = test_view(date='2024')
        assert test_view.spec['category'] == 'foo'
        assert test_view.spec['date'] == '2024'
        assert test_view.spec['recurse'] is True
        assert 'count' not in test_view.spec

        test_view = test_view(count=25)
        assert test_view.spec['category'] == 'foo'
        assert test_view.spec['date'] == '2024'
        assert test_view.spec['recurse'] is True
        assert 'count' not in test_view.spec
