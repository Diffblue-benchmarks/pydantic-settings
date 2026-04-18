"""Tests for AWSSecretsManagerSettingsSource."""
from __future__ import annotations

import json
import sys
from typing import Optional
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from pydantic_settings import BaseSettings


@pytest.fixture
def aws_credentials(monkeypatch):
    """Mocked AWS credentials."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')


@pytest.fixture
def mock_boto3(mocker):
    """Mock boto3 and types_boto3_secretsmanager modules."""
    mock_client_instance = MagicMock()

    mock_boto3_module = MagicMock()
    mock_boto3_module.client = MagicMock(return_value=mock_client_instance)

    mock_types_boto3 = MagicMock()
    mock_types_boto3_client = MagicMock()

    mocker.patch.dict(sys.modules, {
        'boto3': mock_boto3_module,
        'types_boto3_secretsmanager': mock_types_boto3,
        'types_boto3_secretsmanager.client': mock_types_boto3_client,
    })

    # Reset the global variables in the aws module
    import pydantic_settings.sources.providers.aws as aws_module
    aws_module.boto3_client = None
    aws_module.SecretsManagerClient = None

    return mock_client_instance, mock_boto3_module


class TestImportAWSSecretsManager:
    """Tests for import_aws_secrets_manager function."""

    def test_import_aws_secrets_manager_success(self, mock_boto3):
        """Test that import_aws_secrets_manager succeeds when boto3 is installed."""
        from pydantic_settings.sources.providers.aws import import_aws_secrets_manager

        import_aws_secrets_manager()

        import pydantic_settings.sources.providers.aws as aws_module
        assert aws_module.boto3_client is not None

    def test_import_aws_secrets_manager_sets_globals(self, mock_boto3):
        """Test that import_aws_secrets_manager sets the global variables."""
        import pydantic_settings.sources.providers.aws as aws_module

        # Initially reset
        aws_module.boto3_client = None
        aws_module.SecretsManagerClient = None

        from pydantic_settings.sources.providers.aws import import_aws_secrets_manager
        import_aws_secrets_manager()

        assert aws_module.boto3_client is not None
        assert aws_module.SecretsManagerClient is not None


class TestAWSSecretsManagerSettingsSourceInit:
    """Tests for AWSSecretsManagerSettingsSource.__init__."""

    def test_init_basic(self, mock_boto3, aws_credentials):
        """Test basic initialization of AWSSecretsManagerSettingsSource."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'api_key': 'secret123', 'database_url': 'postgres://localhost/db'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            api_key: str
            database_url: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='my-secret',
            region_name='us-east-1',
        )

        assert source._secret_id == 'my-secret'
        assert source._version_id is None
        assert source.env_nested_delimiter == '--'

    def test_init_with_version_id(self, mock_boto3, aws_credentials):
        """Test initialization with version_id parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='versioned-secret',
            region_name='us-east-1',
            version_id='version-123',
        )

        assert source._version_id == 'version-123'

    def test_init_with_endpoint_url(self, mock_boto3, aws_credentials):
        """Test initialization with endpoint_url parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='endpoint-secret',
            region_name='us-east-1',
            endpoint_url='http://localhost:4566',
        )

        mock_boto3_module.client.assert_called_with(
            'secretsmanager',
            region_name='us-east-1',
            endpoint_url='http://localhost:4566',
        )
        assert source._secret_id == 'endpoint-secret'

    def test_init_with_case_sensitive_true(self, mock_boto3, aws_credentials):
        """Test initialization with case_sensitive=True parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'Key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str = 'default'

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='case-secret',
            region_name='us-east-1',
            case_sensitive=True,
        )

        assert source.case_sensitive is True

    def test_init_with_case_sensitive_false(self, mock_boto3, aws_credentials):
        """Test initialization with case_sensitive=False parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'KEY': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str = 'default'

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='case-secret',
            region_name='us-east-1',
            case_sensitive=False,
        )

        assert source.case_sensitive is False

    def test_init_with_env_prefix(self, mock_boto3, aws_credentials):
        """Test initialization with env_prefix parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'APP_key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str = 'default'

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='prefix-secret',
            region_name='us-east-1',
            env_prefix='APP_',
        )

        assert source.env_prefix == 'APP_'

    def test_init_with_env_nested_delimiter(self, mock_boto3, aws_credentials):
        """Test initialization with env_nested_delimiter parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='nested-secret',
            region_name='us-east-1',
            env_nested_delimiter='__',
        )

        assert source.env_nested_delimiter == '__'

    def test_init_with_env_parse_none_str(self, mock_boto3, aws_credentials):
        """Test initialization with env_parse_none_str parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'null'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: Optional[str] = None

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='none-secret',
            region_name='us-east-1',
            env_parse_none_str='null',
        )

        assert source.env_parse_none_str == 'null'

    def test_init_with_env_parse_enums(self, mock_boto3, aws_credentials):
        """Test initialization with env_parse_enums parameter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='enum-secret',
            region_name='us-east-1',
            env_parse_enums=True,
        )

        assert source.env_parse_enums is True

    def test_init_region_name_none(self, mock_boto3, aws_credentials):
        """Test initialization with region_name=None (default region)."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='region-default-secret',
        )

        mock_boto3_module.client.assert_called_with(
            'secretsmanager',
            region_name=None,
            endpoint_url=None,
        )
        assert source._secret_id == 'region-default-secret'


class TestAWSSecretsManagerSettingsSourceLoadEnvVars:
    """Tests for AWSSecretsManagerSettingsSource._load_env_vars."""

    def test_load_env_vars_basic(self, mock_boto3, aws_credentials):
        """Test loading environment variables from secrets manager."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'api_key': 'secret123', 'debug': 'true'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            api_key: str
            debug: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='load-secret',
            region_name='us-east-1',
        )

        env_vars = source.env_vars
        assert env_vars.get('api_key') == 'secret123'
        assert env_vars.get('debug') == 'true'

    def test_load_env_vars_with_version_id(self, mock_boto3, aws_credentials):
        """Test loading environment variables with version_id."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'version1'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='versioned-load-secret',
            region_name='us-east-1',
            version_id='v123',
        )

        mock_client_instance.get_secret_value.assert_called_once_with(
            SecretId='versioned-load-secret',
            VersionId='v123',
        )

        env_vars = source.env_vars
        assert env_vars.get('key') == 'version1'

    def test_load_env_vars_without_version_id(self, mock_boto3, aws_credentials):
        """Test loading environment variables without version_id."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'latest'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='no-version-secret',
            region_name='us-east-1',
        )

        mock_client_instance.get_secret_value.assert_called_once_with(
            SecretId='no-version-secret',
        )

        env_vars = source.env_vars
        assert env_vars.get('key') == 'latest'

    def test_load_env_vars_case_insensitive(self, mock_boto3, aws_credentials):
        """Test loading environment variables case insensitively."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'API_KEY': 'secret123'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            api_key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='case-load-secret',
            region_name='us-east-1',
            case_sensitive=False,
        )

        env_vars = source.env_vars
        assert env_vars.get('api_key') == 'secret123'


class TestAWSSecretsManagerSettingsSourceRepr:
    """Tests for AWSSecretsManagerSettingsSource.__repr__."""

    def test_repr(self, mock_boto3, aws_credentials):
        """Test string representation of AWSSecretsManagerSettingsSource."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='repr-secret',
            region_name='us-east-1',
        )

        result = repr(source)
        assert 'AWSSecretsManagerSettingsSource' in result
        assert "secret_id='repr-secret'" in result
        assert "env_nested_delimiter='--'" in result

    def test_repr_with_custom_delimiter(self, mock_boto3, aws_credentials):
        """Test repr with custom env_nested_delimiter."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'key': 'value'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class Settings(BaseSettings):
            key: str

        source = AWSSecretsManagerSettingsSource(
            Settings,
            secret_id='repr-delim-secret',
            region_name='us-east-1',
            env_nested_delimiter='__',
        )

        result = repr(source)
        assert "env_nested_delimiter='__'" in result


class TestAWSSecretsManagerSettingsSourceIntegration:
    """Integration tests for AWSSecretsManagerSettingsSource with BaseSettings."""

    def test_integration_with_base_settings(self, mock_boto3, aws_credentials):
        """Test AWSSecretsManagerSettingsSource integration with BaseSettings."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {'app_name': 'MyApp', 'port': '8080'}
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class MySettings(BaseSettings):
            app_name: str
            port: int

            @classmethod
            def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
                return (
                    AWSSecretsManagerSettingsSource(
                        settings_cls,
                        secret_id='integration-secret',
                        region_name='us-east-1',
                    ),
                )

        settings = MySettings()
        assert settings.app_name == 'MyApp'
        assert settings.port == 8080

    def test_nested_model_settings(self, mock_boto3, aws_credentials):
        """Test AWSSecretsManagerSettingsSource with nested models."""
        mock_client_instance, mock_boto3_module = mock_boto3
        secret_data = {
            'database--host': 'localhost',
            'database--port': '5432',
        }
        mock_client_instance.get_secret_value.return_value = {'SecretString': json.dumps(secret_data)}

        from pydantic_settings.sources.providers.aws import AWSSecretsManagerSettingsSource

        class DatabaseSettings(BaseModel):
            host: str
            port: int

        class MySettings(BaseSettings):
            database: DatabaseSettings

            @classmethod
            def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
                return (
                    AWSSecretsManagerSettingsSource(
                        settings_cls,
                        secret_id='nested-model-secret',
                        region_name='us-east-1',
                        env_nested_delimiter='--',
                    ),
                )

        settings = MySettings()
        assert settings.database.host == 'localhost'
        assert settings.database.port == 5432
