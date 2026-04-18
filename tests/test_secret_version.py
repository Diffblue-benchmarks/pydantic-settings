"""Tests for SecretVersion in pydantic_settings.sources.types."""

from pydantic_settings.sources.types import SecretVersion


def test_secret_version_init():
    sv = SecretVersion('v1')
    assert sv.version == 'v1'


def test_secret_version_repr():
    sv = SecretVersion('latest')
    assert repr(sv) == "SecretVersion('latest')"
