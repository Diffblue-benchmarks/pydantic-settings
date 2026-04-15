from pydantic_settings.sources.types import SecretVersion


def test_secret_version_init():
    sv = SecretVersion('v1')
    assert sv.version == 'v1'


def test_secret_version_repr():
    sv = SecretVersion('v2')
    assert repr(sv) == "SecretVersion('v2')"
