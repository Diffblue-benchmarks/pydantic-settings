from __future__ import annotations

import json
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.aws import (
    AWSSecretsManagerSettingsSource,
    import_aws_secrets_manager,
)


@pytest.fixture
def aws_region():
    return 'us-east-1'


@pytest.fixture
def secret_name():
    return 'test/my-secret'


@pytest.fixture
def secret_value():
    return {'MY_VAR': 'my_value', 'OTHER_VAR': 'other_value'}


@pytest.fixture
def aws_secret(aws_region, secret_name, secret_value):
    with mock_aws():
        client = boto3.client('secretsmanager', region_name=aws_region)
        client.create_secret(
            Name=secret_name,
            SecretString=json.dumps(secret_value),
        )
        yield


def test_import_aws_secrets_manager():
    import_aws_secrets_manager()
    from pydantic_settings.sources.providers import aws

    assert aws.boto3_client is not None
    assert aws.SecretsManagerClient is not None


@mock_aws
def test_init_default_params(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps({'VAR': 'val'}))

    class MySettings(BaseSettings):
        VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
    )
    assert source._secret_id == secret_name
    assert source._version_id is None
    assert source.case_sensitive is True
    assert source.env_nested_delimiter == '--'


@mock_aws
def test_init_custom_params(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    create_resp = client.create_secret(Name=secret_name, SecretString=json.dumps({'VAR': 'val'}))
    version_id = create_resp['VersionId']

    class MySettings(BaseSettings):
        VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
        case_sensitive=False,
        env_prefix='APP_',
        env_nested_delimiter='__',
        env_parse_none_str='None',
        version_id=version_id,
    )
    assert source._secret_id == secret_name
    assert source._version_id == version_id
    assert source.case_sensitive is False
    assert source.env_nested_delimiter == '__'
    assert source.env_prefix == 'APP_'
    assert source.env_parse_none_str == 'None'


@mock_aws
def test_load_env_vars_basic(aws_region, secret_name, secret_value):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps(secret_value))

    class MySettings(BaseSettings):
        MY_VAR: str = 'default'
        OTHER_VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
    )
    env_vars = source.env_vars
    assert env_vars['MY_VAR'] == 'my_value'
    assert env_vars['OTHER_VAR'] == 'other_value'


@mock_aws
def test_load_env_vars_case_insensitive(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps({'MY_VAR': 'value'}))

    class MySettings(BaseSettings):
        my_var: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
        case_sensitive=False,
    )
    env_vars = source.env_vars
    assert 'my_var' in env_vars
    assert env_vars['my_var'] == 'value'


@mock_aws
def test_load_env_vars_with_version_id(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    create_resp = client.create_secret(Name=secret_name, SecretString=json.dumps({'VAR': 'v1'}))
    version_id = create_resp['VersionId']

    class MySettings(BaseSettings):
        VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
        version_id=version_id,
    )
    env_vars = source.env_vars
    assert env_vars['VAR'] == 'v1'


@mock_aws
def test_repr(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps({'VAR': 'val'}))

    class MySettings(BaseSettings):
        VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
    )
    result = repr(source)
    assert 'AWSSecretsManagerSettingsSource' in result
    assert secret_name in result
    assert '--' in result


@mock_aws
def test_repr_custom_delimiter(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps({'VAR': 'val'}))

    class MySettings(BaseSettings):
        VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
        env_nested_delimiter='__',
    )
    result = repr(source)
    assert "env_nested_delimiter='__'" in result
    assert f"secret_id='{secret_name}'" in result


@mock_aws
def test_settings_integration(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps({'MY_VAR': 'from_aws', 'NUM': '42'}))

    class MySettings(BaseSettings):
        MY_VAR: str = 'default'
        NUM: str = '0'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
    )
    assert source.env_vars['MY_VAR'] == 'from_aws'
    assert source.env_vars['NUM'] == '42'


@mock_aws
def test_load_env_vars_with_nested_json(aws_region, secret_name):
    nested_data = {'DB--HOST': 'localhost', 'DB--PORT': '5432'}
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps(nested_data))

    class DbConfig(BaseModel):
        HOST: str = 'default'
        PORT: str = '0'

    class MySettings(BaseSettings):
        DB: DbConfig = DbConfig()

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
    )
    env_vars = source.env_vars
    assert env_vars['DB--HOST'] == 'localhost'
    assert env_vars['DB--PORT'] == '5432'


@mock_aws
def test_init_with_endpoint_url(aws_region, secret_name):
    client = boto3.client('secretsmanager', region_name=aws_region)
    client.create_secret(Name=secret_name, SecretString=json.dumps({'VAR': 'val'}))

    class MySettings(BaseSettings):
        VAR: str = 'default'

    source = AWSSecretsManagerSettingsSource(
        MySettings,
        secret_id=secret_name,
        region_name=aws_region,
        endpoint_url=None,
    )
    assert source._secret_id == secret_name
