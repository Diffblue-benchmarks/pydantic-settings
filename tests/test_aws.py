import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.aws import (
    AWSSecretsManagerSettingsSource,
    import_aws_secrets_manager,
)


def test_import_aws_secrets_manager_success():
    """Test successful import of AWS Secrets Manager dependencies."""
    # Reset globals
    import pydantic_settings.sources.providers.aws as aws_module
    aws_module.boto3_client = None
    aws_module.SecretsManagerClient = None

    # Import should succeed with moto installed
    import_aws_secrets_manager()

    assert aws_module.boto3_client is not None
    assert aws_module.SecretsManagerClient is not None


def test_import_aws_secrets_manager_import_error():
    """Test import error when AWS dependencies are missing."""
    import pydantic_settings.sources.providers.aws as aws_module

    # Reset globals
    aws_module.boto3_client = None
    aws_module.SecretsManagerClient = None

    # Mock the import to raise ImportError
    with patch('builtins.__import__', side_effect=ImportError('boto3 not installed')):
        with pytest.raises(ImportError, match='AWS Secrets Manager dependencies are not installed'):
            import_aws_secrets_manager()


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""
    database_url: str = 'default'
    api_key: str = 'default_key'


def test_aws_secrets_manager_init_basic():
    """Test basic initialization of AWSSecretsManagerSettingsSource."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        # Create the secret first
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_value = {'database_url': 'postgresql://localhost/db'}
        client.create_secret(
            Name='test-secret',
            SecretString=json.dumps(secret_value)
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='test-secret',
            region_name='us-east-1'
        )

        assert source._secret_id == 'test-secret'
        assert source._secretsmanager_client is not None
        assert source.env_nested_delimiter == '--'
        assert source.case_sensitive is True


def test_aws_secrets_manager_init_with_custom_params():
    """Test initialization with custom parameters."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        # Create the secret first
        client = boto3.client('secretsmanager', region_name='eu-west-1')
        secret_value = {'APP_database_url': 'postgresql://localhost/db'}
        client.create_secret(
            Name='my-secret',
            SecretString=json.dumps(secret_value)
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='my-secret',
            region_name='eu-west-1',
            endpoint_url=None,
            case_sensitive=False,
            env_prefix='APP_',
            env_nested_delimiter='__',
            env_parse_none_str='null',
            env_parse_enums=True,
            version_id=None
        )

        assert source._secret_id == 'my-secret'
        assert source.env_nested_delimiter == '__'
        assert source.case_sensitive is False
        assert source.env_prefix == 'APP_'
        assert source.env_parse_none_str == 'null'
        assert source.env_parse_enums is True


def test_load_env_vars_basic():
    """Test loading environment variables from AWS Secrets Manager."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        # Create a mock secret
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_value = {
            'database_url': 'postgresql://localhost/db',
            'api_key': 'secret123'
        }
        client.create_secret(
            Name='test-secret',
            SecretString=json.dumps(secret_value)
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='test-secret',
            region_name='us-east-1'
        )

        env_vars = source._load_env_vars()

        assert 'database_url' in env_vars
        assert env_vars['database_url'] == 'postgresql://localhost/db'
        assert 'api_key' in env_vars
        assert env_vars['api_key'] == 'secret123'


def test_load_env_vars_with_version_id():
    """Test loading environment variables with a specific version ID."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_value = {'key': 'value'}
        response = client.create_secret(
            Name='versioned-secret',
            SecretString=json.dumps(secret_value)
        )
        version_id = response['VersionId']

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='versioned-secret',
            region_name='us-east-1',
            version_id=version_id
        )

        env_vars = source._load_env_vars()

        assert 'key' in env_vars
        assert env_vars['key'] == 'value'


def test_load_env_vars_case_sensitive():
    """Test case sensitivity handling in loaded environment variables."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_value = {
            'API_KEY': 'uppercase',
            'api_key': 'lowercase'
        }
        client.create_secret(
            Name='case-test-secret',
            SecretString=json.dumps(secret_value)
        )

        # Case sensitive
        source_sensitive = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='case-test-secret',
            region_name='us-east-1',
            case_sensitive=True
        )
        env_vars_sensitive = source_sensitive._load_env_vars()
        assert 'API_KEY' in env_vars_sensitive
        assert 'api_key' in env_vars_sensitive

        # Case insensitive
        source_insensitive = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='case-test-secret',
            region_name='us-east-1',
            case_sensitive=False
        )
        env_vars_insensitive = source_insensitive._load_env_vars()
        # Both should be lowercased
        assert 'api_key' in env_vars_insensitive


def test_repr():
    """Test string representation of AWSSecretsManagerSettingsSource."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        # Create the secret first
        client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_value = {'key': 'value'}
        client.create_secret(
            Name='my-test-secret',
            SecretString=json.dumps(secret_value)
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='my-test-secret',
            region_name='us-east-1',
            env_nested_delimiter='__'
        )

        repr_str = repr(source)

        assert 'AWSSecretsManagerSettingsSource' in repr_str
        assert 'my-test-secret' in repr_str
        assert '__' in repr_str


def test_repr_default_delimiter():
    """Test repr with default nested delimiter."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        # Create the secret first
        client = boto3.client('secretsmanager', region_name='us-west-2')
        secret_value = {'key': 'value'}
        client.create_secret(
            Name='another-secret',
            SecretString=json.dumps(secret_value)
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SimpleSettings,
            secret_id='another-secret',
            region_name='us-west-2'
        )

        repr_str = repr(source)

        assert 'AWSSecretsManagerSettingsSource' in repr_str
        assert 'another-secret' in repr_str
        assert '--' in repr_str
