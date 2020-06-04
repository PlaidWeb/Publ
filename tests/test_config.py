""" tests of the config manager """
# pylint:disable=missing-docstring

from publ import config

from . import PublMock


def test_config_defaults():
    cfg = config.Config({})
    dfl = config._Defaults  # pylint:disable=protected-access
    for key, val in cfg.__dict__.items():
        if key[0] != '_':
            assert val == getattr(dfl, key)


def test_config_overrides():
    cfg = config.Config({'static_folder': 'kwyjibo', '_not_an_option': 'foo'})
    assert cfg.static_folder == 'kwyjibo'
    assert not hasattr(cfg, '_not_an_option')


def test_config_singleton():
    app = PublMock({'static_folder': 'berry'})
    assert app.publ_config.static_folder == 'berry'
    with app.app_context():
        # pylint:disable=protected-access
        assert config.config._get_current_object() is app.publ_config
