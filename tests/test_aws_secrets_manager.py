from __future__ import annotations

import json
from typing import Optional

import boto3
import pytest
from moto import mock_aws
from pydantic import Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource


@pytest.fixture
def aws_credentials(monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')


@pytest.fixture
def secret_id():
    return 'my/test/secret'


@pytest.fixture
def aws_secret(aws_credentials, secret_id):
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        client.create_secret(
            Name=secret_id,
            SecretString=json.dumps({'app_name': 'TestApp', 'app_version': '1.0'}),
        )
        yield client, secret_id


class MySettings(BaseSettings):
    app_name: str = 'default'
    app_version: str = '0.0'


def test_import_aws_secrets_manager():
    from pydantic_settings.sources.providers import aws as aws_module
    aws_module.boto3_client = None
    aws_module.SecretsManagerClient = None

    from pydantic_settings.sources.providers.aws import import_aws_secrets_manager
    import_aws_secrets_manager()

    assert aws_module.boto3_client is not None
    assert aws_module.SecretsManagerClient is not None


def test_init_basic(aws_secret):
    client, secret_id = aws_secret
    with mock_aws():
        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )
        assert source._secret_id == secret_id
        assert source._version_id is None


def test_init_with_version_id(aws_credentials, secret_id):
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        resp = client.create_secret(
            Name=secret_id,
            SecretString=json.dumps({'app_name': 'VersionedApp'}),
        )
        version_id = resp['VersionId']

        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
            version_id=version_id,
        )
        assert source._version_id == version_id


def test_init_with_env_prefix(aws_secret):
    client, secret_id = aws_secret
    with mock_aws():
        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
            env_prefix='APP_',
        )
        assert source.env_prefix == 'APP_'


def test_init_with_nested_delimiter(aws_secret):
    client, secret_id = aws_secret
    with mock_aws():
        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
            env_nested_delimiter='__',
        )
        assert source.env_nested_delimiter == '__'


def test_load_env_vars(aws_secret):
    client, secret_id = aws_secret
    with mock_aws():
        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )
        env_vars = source._load_env_vars()
        assert 'app_name' in env_vars
        assert env_vars['app_name'] == 'TestApp'


def test_load_env_vars_with_version_id(aws_credentials, secret_id):
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        resp = client.create_secret(
            Name=secret_id,
            SecretString=json.dumps({'app_name': 'VersionedApp'}),
        )
        version_id = resp['VersionId']

        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
            version_id=version_id,
        )
        env_vars = source._load_env_vars()
        assert env_vars['app_name'] == 'VersionedApp'


def test_repr(aws_secret):
    client, secret_id = aws_secret
    with mock_aws():
        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
        )
        result = repr(source)
        assert 'AWSSecretsManagerSettingsSource' in result
        assert secret_id in result
        assert 'env_nested_delimiter' in result


def test_repr_with_custom_delimiter(aws_secret):
    client, secret_id = aws_secret
    with mock_aws():
        source = AWSSecretsManagerSettingsSource(
            MySettings,
            secret_id=secret_id,
            region_name='us-east-1',
            env_nested_delimiter='__',
        )
        result = repr(source)
        assert "'__'" in result


def test_settings_loaded_from_aws(aws_credentials, secret_id):
    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        client.create_secret(
            Name=secret_id,
            SecretString=json.dumps({'app_name': 'AWSApp', 'app_version': '2.0'}),
        )

        class SettingsFromAWS(BaseSettings):
            app_name: str = 'default'
            app_version: str = '0.0'

            @classmethod
            def settings_customise_sources(cls, settings_cls, **kwargs):
                return (
                    AWSSecretsManagerSettingsSource(
                        settings_cls,
                        secret_id=secret_id,
                        region_name='us-east-1',
                    ),
                )

        settings = SettingsFromAWS()
        assert settings.app_name == 'AWSApp'
        assert settings.app_version == '2.0'
