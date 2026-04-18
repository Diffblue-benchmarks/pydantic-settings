from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from pydantic_settings import BaseSettings


# Provide a stub for types_boto3_secretsmanager since it is a type-only package
# that may not be installed in the test environment.
_types_boto3_stub = MagicMock()
sys.modules.setdefault('types_boto3_secretsmanager', _types_boto3_stub)
sys.modules.setdefault('types_boto3_secretsmanager.client', _types_boto3_stub)

from pydantic_settings.sources.providers.aws import (  # noqa: E402
    AWSSecretsManagerSettingsSource,
    import_aws_secrets_manager,
)


class SimpleSettings(BaseSettings):
    foo: str = 'default'
    bar: str = 'default'


# ─── import_aws_secrets_manager ──────────────────────────────────────────────


def test_import_aws_secrets_manager_sets_boto3_client():
    import pydantic_settings.sources.providers.aws as aws_module

    import_aws_secrets_manager()

    assert aws_module.boto3_client is not None


def test_import_aws_secrets_manager_boto3_client_is_callable():
    import pydantic_settings.sources.providers.aws as aws_module

    import_aws_secrets_manager()

    assert callable(aws_module.boto3_client)


def test_import_aws_secrets_manager_sets_secrets_manager_client():
    import pydantic_settings.sources.providers.aws as aws_module

    import_aws_secrets_manager()

    assert aws_module.SecretsManagerClient is not None


# ─── AWSSecretsManagerSettingsSource.__init__ ────────────────────────────────


@mock_aws
def test_init_sets_secret_id():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert source._secret_id == 'my-secret'


@mock_aws
def test_init_version_id_defaults_to_none():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert source._version_id is None


@mock_aws
def test_init_secretsmanager_client_created():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert source._secretsmanager_client is not None


@mock_aws
def test_init_case_sensitive_default_true():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert source.case_sensitive is True


@mock_aws
def test_init_env_nested_delimiter_default():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert source.env_nested_delimiter == '--'


@mock_aws
def test_init_custom_env_nested_delimiter():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        env_nested_delimiter='__',
    )

    assert source.env_nested_delimiter == '__'


@mock_aws
def test_init_with_version_id():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    resp = client.create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )
    version_id = resp['VersionId']

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        version_id=version_id,
    )

    assert source._version_id == version_id


@mock_aws
def test_init_env_ignore_empty_forced_false():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': ''}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert source.env_ignore_empty is False


@mock_aws
def test_init_env_prefix_propagated():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'app_foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        env_prefix='app_',
    )

    assert source.env_prefix == 'app_'


# ─── AWSSecretsManagerSettingsSource._load_env_vars ──────────────────────────


@mock_aws
def test_load_env_vars_returns_secret_key_values():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello', 'bar': 'world'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )
    env_vars = source._load_env_vars()

    assert env_vars['foo'] == 'hello'
    assert env_vars['bar'] == 'world'


@mock_aws
def test_load_env_vars_case_sensitive_preserves_uppercase():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'FOO': 'hello', 'Bar': 'world'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        case_sensitive=True,
    )
    env_vars = source._load_env_vars()

    assert 'FOO' in env_vars
    assert 'Bar' in env_vars


@mock_aws
def test_load_env_vars_case_insensitive_lowercases_keys():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'FOO': 'hello', 'BAR': 'world'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        case_sensitive=False,
    )
    env_vars = source._load_env_vars()

    assert 'foo' in env_vars
    assert 'bar' in env_vars


@mock_aws
def test_load_env_vars_without_version_id_no_request_version_key():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'no-version'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        version_id=None,
    )
    env_vars = source._load_env_vars()

    assert env_vars['foo'] == 'no-version'


@mock_aws
def test_load_env_vars_with_version_id():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    resp = client.create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'v1'}),
    )
    version_id = resp['VersionId']

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        version_id=version_id,
    )
    env_vars = source._load_env_vars()

    assert env_vars['foo'] == 'v1'


# ─── AWSSecretsManagerSettingsSource.__repr__ ────────────────────────────────


@mock_aws
def test_repr_contains_class_name():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert 'AWSSecretsManagerSettingsSource' in repr(source)


@mock_aws
def test_repr_contains_secret_id():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert 'my-secret' in repr(source)


@mock_aws
def test_repr_contains_env_nested_delimiter():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
        env_nested_delimiter='__',
    )

    assert '__' in repr(source)


@mock_aws
def test_repr_exact_format():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='my-secret',
        SecretString=json.dumps({'foo': 'hello'}),
    )

    source = AWSSecretsManagerSettingsSource(
        SimpleSettings,
        secret_id='my-secret',
        region_name='us-east-1',
    )

    assert repr(source) == "AWSSecretsManagerSettingsSource(secret_id='my-secret', env_nested_delimiter='--')"


# ─── Integration: BaseSettings with AWS source ───────────────────────────────


@mock_aws
def test_settings_class_loads_from_secret():
    boto3.client('secretsmanager', region_name='us-east-1').create_secret(
        Name='app-config',
        SecretString=json.dumps({'foo': 'loaded_foo', 'bar': 'loaded_bar'}),
    )

    class AppSettings(BaseSettings):
        foo: str = 'default'
        bar: str = 'default'

        @classmethod
        def settings_customise_sources(cls, settings_cls, **kwargs):
            return (
                AWSSecretsManagerSettingsSource(
                    settings_cls,
                    secret_id='app-config',
                    region_name='us-east-1',
                ),
            )

    settings = AppSettings()

    assert settings.foo == 'loaded_foo'
    assert settings.bar == 'loaded_bar'
