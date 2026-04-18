"""Tests for SecretVersion in pydantic_settings.sources.types."""

from pydantic_settings.sources.types import SecretVersion


def test_secret_version_init():
    sv = SecretVersion('v1')
    assert sv.version == 'v1'


def test_secret_version_init_empty_string():
    sv = SecretVersion('')
    assert sv.version == ''


def test_secret_version_repr():
    sv = SecretVersion('v1')
    assert repr(sv) == "SecretVersion('v1')"


def test_secret_version_repr_empty():
    sv = SecretVersion('')
    assert repr(sv) == "SecretVersion('')"
