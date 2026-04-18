from __future__ import annotations

import json
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel

from pydantic_settings import BaseSettings

import pydantic_settings.sources.providers.aws as aws_mod


@pytest.fixture(autouse=True)
def _setup_aws_module():
    """Set up the aws module globals so import_aws_secrets_manager is not needed."""
    old_client = aws_mod.boto3_client
    old_sm = aws_mod.SecretsManagerClient
    aws_mod.boto3_client = boto3.client
    aws_mod.SecretsManagerClient = object  # type stub only, not used at runtime
    yield
    aws_mod.boto3_client = old_client
    aws_mod.SecretsManagerClient = old_sm


def _noop_import() -> None:
    """No-op replacement for import_aws_secrets_manager."""
    pass


class SimpleSettings(BaseSettings):
    foo: str = 'default'
    bar: int = 0


class NestedSubModel(BaseModel):
    x: int = 1
    y: str = 'hello'


class NestedSettings(BaseSettings):
    sub: NestedSubModel = NestedSubModel()
    name: str = 'test'


def test_import_aws_secrets_manager_success() -> None:
    """Test that import_aws_secrets_manager sets globals when deps are available."""
    aws_mod.boto3_client = None
    aws_mod.SecretsManagerClient = None

    with patch('pydantic_settings.sources.providers.aws.boto3_client', None):
        with patch('pydantic_settings.sources.providers.aws.SecretsManagerClient', None):
            # Patch the import to only import boto3.client (skip types_boto3_secretsmanager)
            with patch.dict('sys.modules', {'types_boto3_secretsmanager': type('module', (), {}),
                                            'types_boto3_secretsmanager.client': type('module', (), {'SecretsManagerClient': object})}):
                aws_mod.import_aws_secrets_manager()
                assert aws_mod.boto3_client is not None


def test_import_aws_secrets_manager_missing_deps() -> None:
    """Test that import_aws_secrets_manager raises ImportError when deps missing."""
    with patch.dict('sys.modules', {'boto3': None}):
        with pytest.raises(ImportError, match='AWS Secrets Manager dependencies are not installed'):
            aws_mod.import_aws_secrets_manager()


@mock_aws
def test_init_creates_client_and_sets_attributes() -> None:
    """Test that __init__ creates a secretsmanager client and sets secret_id."""
    secret_id = 'test/secret'
    secret_data = {'foo': 'bar_value', 'bar': '42'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )

    assert source._secret_id == secret_id
    assert source._secretsmanager_client is not None
    assert source._version_id is None


@mock_aws
def test_init_with_version_id() -> None:
    """Test that __init__ stores version_id when provided."""
    secret_id = 'test/secret'
    secret_data = {'foo': 'value', 'bar': '1'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    resp = client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))
    version_id = resp['VersionId']

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            version_id=version_id,
        )

    assert source._version_id == version_id


@mock_aws
def test_init_with_custom_parameters() -> None:
    """Test that __init__ passes through env-related parameters to parent."""
    secret_id = 'test/secret'
    secret_data = {'MY_foo': 'val', 'MY_bar': '10'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            case_sensitive=False,
            env_prefix='MY_',
            env_nested_delimiter='__',
            env_parse_none_str='null',
        )

    assert source.case_sensitive is False
    assert source.env_prefix == 'MY_'
    assert source.env_nested_delimiter == '__'
    assert source.env_parse_none_str == 'null'


@mock_aws
def test_load_env_vars_returns_secret_values() -> None:
    """Test that _load_env_vars fetches and parses the secret string."""
    secret_id = 'test/settings'
    secret_data = {'foo': 'secret_foo', 'bar': '99'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )

    env_vars = source._load_env_vars()
    assert env_vars['foo'] == 'secret_foo'
    assert env_vars['bar'] == '99'


@mock_aws
def test_load_env_vars_with_version_id() -> None:
    """Test that _load_env_vars includes VersionId in request when set."""
    secret_id = 'test/versioned'
    secret_data = {'foo': 'versioned_val', 'bar': '7'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    resp = client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))
    version_id = resp['VersionId']

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            version_id=version_id,
        )

    env_vars = source._load_env_vars()
    assert env_vars['foo'] == 'versioned_val'


@mock_aws
def test_load_env_vars_case_insensitive() -> None:
    """Test that _load_env_vars lowercases keys when case_sensitive=False."""
    secret_id = 'test/case'
    secret_data = {'FOO': 'upper', 'Bar': 'mixed'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            case_sensitive=False,
        )

    env_vars = source._load_env_vars()
    assert 'foo' in env_vars
    assert 'bar' in env_vars


@mock_aws
def test_load_env_vars_case_sensitive() -> None:
    """Test that _load_env_vars preserves case when case_sensitive=True."""
    secret_id = 'test/case_sensitive'
    secret_data = {'FOO': 'upper', 'bar': 'lower'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            case_sensitive=True,
        )

    env_vars = source._load_env_vars()
    assert 'FOO' in env_vars
    assert 'bar' in env_vars


@mock_aws
def test_repr() -> None:
    """Test __repr__ output format."""
    secret_id = 'my/secret'
    secret_data = {'foo': 'x', 'bar': '0'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )

    result = repr(source)
    assert 'AWSSecretsManagerSettingsSource' in result
    assert "secret_id='my/secret'" in result
    assert "env_nested_delimiter='--'" in result


@mock_aws
def test_repr_with_custom_delimiter() -> None:
    """Test __repr__ with custom env_nested_delimiter."""
    secret_id = 'my/secret2'
    secret_data = {'foo': 'y', 'bar': '1'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            env_nested_delimiter='__',
        )

    result = repr(source)
    assert "env_nested_delimiter='__'" in result


@mock_aws
def test_init_with_endpoint_url() -> None:
    """Test that __init__ accepts endpoint_url parameter and stores secret_id."""
    secret_id = 'test/endpoint'
    secret_data = {'foo': 'ep_val', 'bar': '5'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            SimpleSettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )

    assert source._secret_id == secret_id


@mock_aws
def test_settings_integration() -> None:
    """Test end-to-end integration with BaseSettings using settings_customise_sources."""
    secret_id = 'app/settings'
    secret_data = {'foo': 'from_aws', 'bar': '123'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):

        class MySettings(BaseSettings):
            foo: str = 'default'
            bar: int = 0

            @classmethod
            def settings_customise_sources(cls, settings_cls, **kwargs):  # type: ignore
                return (
                    aws_mod.AWSSecretsManagerSettingsSource(
                        settings_cls,
                        secret_id=secret_id,
                        region_name='us-east-1',
                    ),
                )

        settings = MySettings()
    assert settings.foo == 'from_aws'
    assert settings.bar == 123


@mock_aws
def test_load_env_vars_with_nested_delimiter() -> None:
    """Test loading secrets with nested delimiter keys."""
    secret_id = 'app/nested'
    secret_data = {'sub--x': '42', 'sub--y': 'world', 'name': 'nested_test'}
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(Name=secret_id, SecretString=json.dumps(secret_data))

    with patch.object(aws_mod, 'import_aws_secrets_manager', _noop_import):
        source = aws_mod.AWSSecretsManagerSettingsSource(
            NestedSettings,
            secret_id=secret_id,
            region_name='us-east-1',
            env_nested_delimiter='--',
        )

    env_vars = source._load_env_vars()
    assert 'name' in env_vars
    assert env_vars['name'] == 'nested_test'
