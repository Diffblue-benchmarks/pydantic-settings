"""Tests for SecretVersion in pydantic_settings.sources.types."""

from pydantic_settings.sources.types import SecretVersion


def test_secret_version_init_stores_version():
    sv = SecretVersion('latest')
    assert sv.version == 'latest'


def test_secret_version_init_empty_string():
    sv = SecretVersion('')
    assert sv.version == ''


def test_secret_version_repr():
    sv = SecretVersion('v1.0')
    assert repr(sv) == "SecretVersion('v1.0')"


def test_secret_version_repr_empty():
    sv = SecretVersion('')
    assert repr(sv) == "SecretVersion('')"
