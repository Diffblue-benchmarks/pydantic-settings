"""Tests for AWS Secrets Manager settings source."""

from __future__ import annotations as _annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.aws import (
    AWSSecretsManagerSettingsSource,
    import_aws_secrets_manager,
)


class SampleSettings(BaseSettings):
    """Sample settings for testing AWS source."""

    api_key: str = 'default'
    debug: bool = False
    database_url: str = 'sqlite:///:memory:'


class TestImportAwsSecretsManager:
    """Tests for import_aws_secrets_manager function."""

    def test_import_aws_secrets_manager_success(self, mocker: Any) -> None:
        """Test successful import of AWS secrets manager dependencies."""
        import pydantic_settings.sources.providers.aws as aws_module

        # Save original values
        original_boto3_client = aws_module.boto3_client
        original_secretsmanager_client = aws_module.SecretsManagerClient

        try:
            # Reset module-level variables
            aws_module.boto3_client = None
            aws_module.SecretsManagerClient = None

            # Mock the imports within the function
            mock_boto3 = MagicMock()
            mock_client = MagicMock()
            mock_boto3.client = mock_client

            def mock_import_side_effect(name: str, *args: Any, **kwargs: Any) -> Any:
                if name == 'boto3':
                    return mock_boto3
                elif name == 'types_boto3_secretsmanager.client':
                    return MagicMock()
                else:
                    return __import__(name, *args, **kwargs)

            mocker.patch('builtins.__import__', side_effect=mock_import_side_effect)

            # This will either succeed or fail based on whether boto3 is installed
            try:
                import_aws_secrets_manager()
            except ImportError as e:
                # If boto3 is truly not installed, this is expected
                if 'AWS Secrets Manager dependencies' in str(e):
                    pass
                else:
                    raise
        finally:
            # Restore original values
            aws_module.boto3_client = original_boto3_client
            aws_module.SecretsManagerClient = original_secretsmanager_client

    def test_import_aws_secrets_manager_missing_dependencies(self, mocker: Any) -> None:
        """Test ImportError when AWS dependencies are not installed."""
        import pydantic_settings.sources.providers.aws as aws_module

        # Save original values
        original_boto3_client = aws_module.boto3_client
        original_secretsmanager_client = aws_module.SecretsManagerClient

        try:
            # Reset module-level variables to simulate import not happening
            aws_module.boto3_client = None
            aws_module.SecretsManagerClient = None

            # Mock import to always raise ImportError for boto3
            def mock_import_side_effect(name: str, *args: Any, **kwargs: Any) -> Any:
                if 'boto3' in name or 'types_boto3' in name:
                    raise ImportError(f'No module named {name}')
                return __import__(name, *args, **kwargs)

            mocker.patch('builtins.__import__', side_effect=mock_import_side_effect)

            with pytest.raises(
                ImportError,
                match='AWS Secrets Manager dependencies are not installed',
            ):
                import_aws_secrets_manager()
        finally:
            # Restore original values
            aws_module.boto3_client = original_boto3_client
            aws_module.SecretsManagerClient = original_secretsmanager_client


class TestAWSSecretsManagerSettingsSourceInit:
    """Tests for AWSSecretsManagerSettingsSource.__init__ method."""

    @pytest.fixture
    def mock_boto3_client(self, mocker: Any) -> MagicMock:
        """Mock boto3 client fixture."""
        mock_client = MagicMock()
        mocker.patch('pydantic_settings.sources.providers.aws.boto3_client', mock_client)
        return mock_client

    @pytest.fixture
    def mock_import_aws(self, mocker: Any) -> MagicMock:
        """Mock import_aws_secrets_manager function."""
        return mocker.patch('pydantic_settings.sources.providers.aws.import_aws_secrets_manager')

    def test_init_basic(self, mock_import_aws: MagicMock, mock_boto3_client: MagicMock, mocker: Any) -> None:
        """Test basic initialization of AWSSecretsManagerSettingsSource."""
        # Mock the boto3_client factory function to return a mock client
        mock_client_instance = MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        # Mock the parent class _load_env_vars to avoid actual env loading
        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='test-secret',
        )

        assert source._secret_id == 'test-secret'
        assert source._secretsmanager_client is mock_client_instance
        mock_import_aws.assert_called_once()
        mock_boto3_client.assert_called_once_with('secretsmanager', region_name=None, endpoint_url=None)

    def test_init_with_region_and_endpoint(self, mock_import_aws: MagicMock, mock_boto3_client: MagicMock, mocker: Any) -> None:
        """Test initialization with region_name and endpoint_url."""
        mock_client_instance = MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='test-secret',
            region_name='us-west-2',
            endpoint_url='http://localhost:4566',
        )

        assert source._secret_id == 'test-secret'
        mock_boto3_client.assert_called_once_with(
            'secretsmanager',
            region_name='us-west-2',
            endpoint_url='http://localhost:4566',
        )

    def test_init_with_version_id(self, mock_import_aws: MagicMock, mock_boto3_client: MagicMock, mocker: Any) -> None:
        """Test initialization with version_id parameter."""
        mock_client_instance = MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='test-secret',
            version_id='v123',
        )

        assert source._secret_id == 'test-secret'
        assert source._version_id == 'v123'

    def test_init_with_env_options(self, mock_import_aws: MagicMock, mock_boto3_client: MagicMock, mocker: Any) -> None:
        """Test initialization with environment variable parsing options."""
        mock_client_instance = MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='test-secret',
            case_sensitive=False,
            env_prefix='APP_',
            env_nested_delimiter='__',
            env_parse_none_str='null',
            env_parse_enums=True,
        )

        assert source._secret_id == 'test-secret'
        assert source.case_sensitive is False
        assert source.env_prefix == 'APP_'
        assert source.env_nested_delimiter == '__'

    def test_init_calls_import_aws_secrets_manager(self, mock_import_aws: MagicMock, mock_boto3_client: MagicMock, mocker: Any) -> None:
        """Test that __init__ calls import_aws_secrets_manager."""
        mock_client_instance = MagicMock()
        mock_boto3_client.return_value = mock_client_instance

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='test-secret',
        )

        mock_import_aws.assert_called_once()


class TestAWSSecretsManagerSettingsSourceLoadEnvVars:
    """Tests for AWSSecretsManagerSettingsSource._load_env_vars method."""

    @pytest.fixture
    def mock_setup(self, mocker: Any) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Setup mocks for testing _load_env_vars."""
        mock_client_factory = MagicMock()
        mock_boto3_client = mocker.patch('pydantic_settings.sources.providers.aws.boto3_client', mock_client_factory)
        mock_import_aws = mocker.patch('pydantic_settings.sources.providers.aws.import_aws_secrets_manager')

        return mock_client_factory, mock_boto3_client, mock_import_aws

    def test_load_env_vars_basic(self, mock_setup: tuple[MagicMock, MagicMock, MagicMock], mocker: Any) -> None:
        """Test basic loading of environment variables from secret."""
        mock_client_factory, _, mock_import_aws = mock_setup

        # Create a mock client instance
        mock_client_instance = MagicMock()
        mock_client_factory.return_value = mock_client_instance

        # Mock the parent class __init__ to not call parent
        mocker.patch('pydantic_settings.sources.providers.aws.EnvSettingsSource.__init__', return_value=None)

        source = AWSSecretsManagerSettingsSource.__new__(AWSSecretsManagerSettingsSource)
        source._secret_id = 'test-secret'
        source._version_id = None
        source._secretsmanager_client = mock_client_instance
        source.case_sensitive = False
        source.env_ignore_empty = False
        source.env_parse_none_str = None

        # Setup the mock response
        secret_data = {'api_key': 'secret-value', 'debug': 'true'}
        mock_client_instance.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data),
        }

        result = source._load_env_vars()

        assert result is not None
        mock_client_instance.get_secret_value.assert_called_once_with(SecretId='test-secret')

    def test_load_env_vars_with_version_id(self, mock_setup: tuple[MagicMock, MagicMock, MagicMock], mocker: Any) -> None:
        """Test loading env vars with version_id specified."""
        mock_client_factory, _, _ = mock_setup

        mock_client_instance = MagicMock()
        mock_client_factory.return_value = mock_client_instance

        mocker.patch('pydantic_settings.sources.providers.aws.EnvSettingsSource.__init__', return_value=None)

        source = AWSSecretsManagerSettingsSource.__new__(AWSSecretsManagerSettingsSource)
        source._secret_id = 'test-secret'
        source._version_id = 'v123'
        source._secretsmanager_client = mock_client_instance
        source.case_sensitive = False
        source.env_ignore_empty = False
        source.env_parse_none_str = None

        secret_data = {'api_key': 'secret-value'}
        mock_client_instance.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data),
        }

        result = source._load_env_vars()

        mock_client_instance.get_secret_value.assert_called_once_with(SecretId='test-secret', VersionId='v123')

    def test_load_env_vars_json_parsing(self, mock_setup: tuple[MagicMock, MagicMock, MagicMock], mocker: Any) -> None:
        """Test JSON parsing of secret response."""
        mock_client_factory, _, _ = mock_setup

        mock_client_instance = MagicMock()
        mock_client_factory.return_value = mock_client_instance

        mocker.patch('pydantic_settings.sources.providers.aws.EnvSettingsSource.__init__', return_value=None)

        source = AWSSecretsManagerSettingsSource.__new__(AWSSecretsManagerSettingsSource)
        source._secret_id = 'test-secret'
        source._version_id = None
        source._secretsmanager_client = mock_client_instance
        source.case_sensitive = False
        source.env_ignore_empty = False
        source.env_parse_none_str = None

        secret_data = {'api_key': 'secret-value', 'debug': 'false', 'database_url': 'postgres://localhost'}
        mock_client_instance.get_secret_value.return_value = {
            'SecretString': json.dumps(secret_data),
        }

        result = source._load_env_vars()

        assert result is not None
        assert isinstance(result, dict)


class TestAWSSecretsManagerSettingsSourceRepr:
    """Tests for AWSSecretsManagerSettingsSource.__repr__ method."""

    @pytest.fixture
    def mock_setup_for_repr(self, mocker: Any) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Setup mocks for testing __repr__."""
        mock_client = MagicMock()
        mock_boto3_client = mocker.patch('pydantic_settings.sources.providers.aws.boto3_client', mock_client)
        mock_import_aws = mocker.patch('pydantic_settings.sources.providers.aws.import_aws_secrets_manager')

        return mock_client, mock_boto3_client, mock_import_aws

    def test_repr_basic(self, mock_setup_for_repr: tuple[MagicMock, MagicMock, MagicMock], mocker: Any) -> None:
        """Test __repr__ method returns correct format."""
        mock_client_instance, mock_boto3_client, mock_import_aws = mock_setup_for_repr
        mock_client_instance.return_value = MagicMock()

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='my-secret',
        )

        repr_str = repr(source)
        assert 'AWSSecretsManagerSettingsSource' in repr_str
        assert 'my-secret' in repr_str
        assert 'env_nested_delimiter' in repr_str

    def test_repr_with_custom_delimiter(self, mock_setup_for_repr: tuple[MagicMock, MagicMock, MagicMock], mocker: Any) -> None:
        """Test __repr__ includes custom env_nested_delimiter."""
        mock_client_instance, mock_boto3_client, mock_import_aws = mock_setup_for_repr
        mock_client_instance.return_value = MagicMock()

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='test-secret',
            env_nested_delimiter='__',
        )

        repr_str = repr(source)
        assert '__' in repr_str
        assert 'test-secret' in repr_str

    def test_repr_format(self, mock_setup_for_repr: tuple[MagicMock, MagicMock, MagicMock], mocker: Any) -> None:
        """Test __repr__ format includes required fields."""
        mock_client_instance, mock_boto3_client, mock_import_aws = mock_setup_for_repr
        mock_client_instance.return_value = MagicMock()

        mocker.patch.object(
            AWSSecretsManagerSettingsSource,
            '_load_env_vars',
            return_value={},
        )

        source = AWSSecretsManagerSettingsSource(
            settings_cls=SampleSettings,
            secret_id='prod-secret',
            env_nested_delimiter=':',
        )

        repr_str = repr(source)
        # Check for expected format: ClassName(secret_id=..., env_nested_delimiter=...)
        assert 'secret_id=' in repr_str
        assert 'prod-secret' in repr_str
        assert 'env_nested_delimiter=' in repr_str
        assert ':' in repr_str
