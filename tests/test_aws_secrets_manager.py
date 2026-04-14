import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.aws import (
    AWSSecretsManagerSettingsSource,
    import_aws_secrets_manager,
)


class TestImportAwsSecretsManager:
    def test_import_aws_secrets_manager_success(self):
        """Test successful import of AWS Secrets Manager dependencies"""
        # Mock the boto3 and types_boto3_secretsmanager modules
        with patch('pydantic_settings.sources.providers.aws.boto3_client', None):
            with patch('pydantic_settings.sources.providers.aws.SecretsManagerClient', None):
                with patch.dict('sys.modules', {
                    'boto3': Mock(),
                    'types_boto3_secretsmanager': Mock(),
                    'types_boto3_secretsmanager.client': Mock(),
                }):
                    # Import should succeed
                    import_aws_secrets_manager()

                    # Verify that the globals are set
                    from pydantic_settings.sources.providers import aws
                    assert aws.boto3_client is not None
                    assert aws.SecretsManagerClient is not None

    def test_import_aws_secrets_manager_missing_boto3(self):
        """Test ImportError when boto3 is not installed"""
        with patch('pydantic_settings.sources.providers.aws.boto3_client', None):
            with patch('pydantic_settings.sources.providers.aws.SecretsManagerClient', None):
                # Simulate missing boto3 by raising ImportError
                with patch('builtins.__import__', side_effect=ImportError('No module named boto3')):
                    with pytest.raises(ImportError) as exc_info:
                        import_aws_secrets_manager()

                    assert 'AWS Secrets Manager dependencies are not installed' in str(exc_info.value)
                    assert 'pip install pydantic-settings[aws-secrets-manager]' in str(exc_info.value)


class TestAWSSecretsManagerSettingsSource:

    @pytest.fixture
    def mock_boto3_client(self):
        """Fixture that provides a mocked boto3 client"""
        with patch('pydantic_settings.sources.providers.aws.import_aws_secrets_manager'):
            with patch('pydantic_settings.sources.providers.aws.boto3_client') as mock_client_factory:
                mock_client = MagicMock()
                # Set default response for get_secret_value
                mock_client.get_secret_value.return_value = {
                    'SecretString': json.dumps({'test': 'value'})
                }
                mock_client_factory.return_value = mock_client
                yield mock_client_factory, mock_client

    @pytest.fixture
    def settings_cls(self):
        """Fixture that provides a simple settings class"""
        class SimpleSettings(BaseSettings):
            api_key: str = 'default'
            database_url: str = 'default'

        return SimpleSettings

    def test_init_basic(self, mock_boto3_client, settings_cls):
        """Test basic initialization of AWSSecretsManagerSettingsSource"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret'
        )

        # Verify boto3 client was created with correct parameters
        mock_client_factory.assert_called_once_with(
            'secretsmanager',
            region_name=None,
            endpoint_url=None
        )

        # Verify attributes are set correctly
        assert source._secret_id == 'my-secret'
        assert source._secretsmanager_client == mock_client
        assert source._version_id is None

    def test_init_with_region_and_endpoint(self, mock_boto3_client, settings_cls):
        """Test initialization with region_name and endpoint_url"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            region_name='us-west-2',
            endpoint_url='http://localhost:4566'
        )

        # Verify boto3 client was created with correct parameters
        mock_client_factory.assert_called_once_with(
            'secretsmanager',
            region_name='us-west-2',
            endpoint_url='http://localhost:4566'
        )

        assert source._secret_id == 'my-secret'

    def test_init_with_case_sensitive(self, mock_boto3_client, settings_cls):
        """Test initialization with case_sensitive parameter"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            case_sensitive=False
        )

        assert source._secret_id == 'my-secret'
        assert source.case_sensitive is False

    def test_init_with_env_prefix(self, mock_boto3_client, settings_cls):
        """Test initialization with env_prefix parameter"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            env_prefix='APP_'
        )

        assert source._secret_id == 'my-secret'
        assert source.env_prefix == 'APP_'

    def test_init_with_nested_delimiter(self, mock_boto3_client, settings_cls):
        """Test initialization with custom env_nested_delimiter"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            env_nested_delimiter='__'
        )

        assert source._secret_id == 'my-secret'
        assert source.env_nested_delimiter == '__'

    def test_init_with_version_id(self, mock_boto3_client, settings_cls):
        """Test initialization with version_id parameter"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            version_id='version-123'
        )

        assert source._secret_id == 'my-secret'
        assert source._version_id == 'version-123'

    def test_load_env_vars_basic(self, mock_boto3_client, settings_cls):
        """Test _load_env_vars retrieves and parses secrets"""
        mock_client_factory, mock_client = mock_boto3_client

        # Setup mock response
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'api_key': 'secret-key-123',
                'database_url': 'postgresql://localhost/mydb'
            })
        }

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret'
        )

        env_vars = source._load_env_vars()

        # Verify get_secret_value was called correctly
        mock_client.get_secret_value.assert_called_with(SecretId='my-secret')

        # Verify parsed values
        assert env_vars['api_key'] == 'secret-key-123'
        assert env_vars['database_url'] == 'postgresql://localhost/mydb'

    def test_load_env_vars_with_version_id(self, mock_boto3_client, settings_cls):
        """Test _load_env_vars with version_id parameter"""
        mock_client_factory, mock_client = mock_boto3_client

        # Setup mock response
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'api_key': 'versioned-key'
            })
        }

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            version_id='version-456'
        )

        env_vars = source._load_env_vars()

        # Verify get_secret_value was called with VersionId
        mock_client.get_secret_value.assert_called_with(
            SecretId='my-secret',
            VersionId='version-456'
        )

        assert env_vars['api_key'] == 'versioned-key'

    def test_load_env_vars_case_insensitive(self, mock_boto3_client, settings_cls):
        """Test _load_env_vars with case_sensitive=False"""
        mock_client_factory, mock_client = mock_boto3_client

        # Setup mock response with mixed case keys
        mock_client.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'API_KEY': 'secret-key-123',
                'DatabaseURL': 'postgresql://localhost/mydb'
            })
        }

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            case_sensitive=False
        )

        env_vars = source._load_env_vars()

        # Keys should be lowercased
        assert 'api_key' in env_vars
        assert 'databaseurl' in env_vars

    def test_repr(self, mock_boto3_client, settings_cls):
        """Test __repr__ method"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='my-secret',
            env_nested_delimiter='__'
        )

        repr_str = repr(source)

        assert 'AWSSecretsManagerSettingsSource' in repr_str
        assert "secret_id='my-secret'" in repr_str
        assert "env_nested_delimiter='__'" in repr_str

    def test_repr_default_delimiter(self, mock_boto3_client, settings_cls):
        """Test __repr__ with default delimiter"""
        mock_client_factory, mock_client = mock_boto3_client

        source = AWSSecretsManagerSettingsSource(
            settings_cls=settings_cls,
            secret_id='test-secret'
        )

        repr_str = repr(source)

        assert 'AWSSecretsManagerSettingsSource' in repr_str
        assert "secret_id='test-secret'" in repr_str
        assert 'env_nested_delimiter=' in repr_str
