"""Tests for Google Secret Manager settings source."""

from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.gcp import (
    GoogleSecretManagerMapping,
    GoogleSecretManagerSettingsSource,
    import_gcp_secret_manager,
)
from pydantic_settings.sources.types import SecretVersion


class TestImportGcpSecretManager:
    """Tests for the import_gcp_secret_manager function."""

    def test_import_gcp_secret_manager_success(self) -> None:
        """Test successful import of GCP Secret Manager dependencies."""
        # Mock the google packages
        mock_credentials = MagicMock()
        mock_client = MagicMock()
        mock_default = MagicMock()

        with patch.dict('sys.modules', {
            'google': MagicMock(),
            'google.auth': MagicMock(default=mock_default),
            'google.auth.credentials': MagicMock(Credentials=mock_credentials),
            'google.cloud': MagicMock(),
            'google.cloud.secretmanager': MagicMock(SecretManagerServiceClient=mock_client),
        }):
            import_gcp_secret_manager()

    def test_import_gcp_secret_manager_import_error(self) -> None:
        """Test import error when GCP packages are not installed."""
        with patch.dict('sys.modules', {
            'google': None,
            'google.auth': None,
        }):
            with patch('builtins.__import__', side_effect=ImportError('No module named google')):
                with pytest.raises(ImportError) as exc_info:
                    import_gcp_secret_manager()
                assert 'GCP Secret Manager dependencies are not installed' in str(exc_info.value)


class TestGoogleSecretManagerMapping:
    """Tests for GoogleSecretManagerMapping class."""

    def test_init(self) -> None:
        """Test GoogleSecretManagerMapping initialization."""
        mock_client = MagicMock()
        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )
        assert mapping._project_id == 'test-project'
        assert mapping._case_sensitive is True
        assert mapping._loaded_secrets == {}
        assert mapping._secret_client is mock_client

    def test_gcp_project_path(self) -> None:
        """Test _gcp_project_path property."""
        mock_client = MagicMock()
        mock_client.common_project_path.return_value = 'projects/test-project'
        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )
        assert mapping._gcp_project_path == 'projects/test-project'
        mock_client.common_project_path.assert_called_once_with('test-project')

    def test_select_case_insensitive_secret_single_candidate(self) -> None:
        """Test _select_case_insensitive_secret with a single candidate."""
        mock_client = MagicMock()
        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=False
        )
        result = mapping._select_case_insensitive_secret('api_key', ['API_KEY'])
        assert result == 'API_KEY'

    def test_select_case_insensitive_secret_multiple_candidates(self) -> None:
        """Test _select_case_insensitive_secret with multiple candidates warns."""
        mock_client = MagicMock()
        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=False
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = mapping._select_case_insensitive_secret('api_key', ['API_KEY', 'Api_Key', 'api_key'])
            assert len(w) == 1
            assert 'Secret collision' in str(w[0].message)
            assert result == 'api_key'  # Last after sorting

    def test_secret_name_map_case_sensitive(self) -> None:
        """Test _secret_name_map property with case sensitive mode."""
        mock_client = MagicMock()
        mock_secret_1 = MagicMock()
        mock_secret_1.name = 'projects/test-project/secrets/API_KEY'
        mock_secret_2 = MagicMock()
        mock_secret_2.name = 'projects/test-project/secrets/DB_PASSWORD'
        mock_client.list_secrets.return_value = [mock_secret_1, mock_secret_2]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'API_KEY'},
            {'secret': 'DB_PASSWORD'}
        ]

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        result = mapping._secret_name_map
        assert 'API_KEY' in result
        assert 'DB_PASSWORD' in result
        assert result['API_KEY'] == 'API_KEY'
        assert result['DB_PASSWORD'] == 'DB_PASSWORD'

    def test_secret_name_map_case_insensitive(self) -> None:
        """Test _secret_name_map property with case insensitive mode."""
        mock_client = MagicMock()
        mock_secret_1 = MagicMock()
        mock_secret_1.name = 'projects/test-project/secrets/API_KEY'
        mock_client.list_secrets.return_value = [mock_secret_1]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'API_KEY'}

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=False
        )

        result = mapping._secret_name_map
        assert 'API_KEY' in result
        assert 'api_key' in result
        assert result['api_key'] == 'API_KEY'

    def test_secret_names(self) -> None:
        """Test _secret_names property."""
        mock_client = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/MY_SECRET'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        result = mapping._secret_names
        assert 'MY_SECRET' in result

    def test_secret_version_path(self) -> None:
        """Test _secret_version_path method."""
        mock_client = MagicMock()
        mock_client.secret_version_path.return_value = 'projects/test/secrets/key/versions/latest'
        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        result = mapping._secret_version_path('key', 'v1')
        mock_client.secret_version_path.assert_called_once_with('test-project', 'key', 'v1')
        assert result == 'projects/test/secrets/key/versions/latest'

    def test_get_secret_value_success(self) -> None:
        """Test _get_secret_value method with successful retrieval."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'secret-value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test/secrets/key/versions/latest'

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        result = mapping._get_secret_value('key')
        assert result == 'secret-value'

    def test_get_secret_value_failure(self) -> None:
        """Test _get_secret_value method when access fails."""
        mock_client = MagicMock()
        mock_client.access_secret_version.side_effect = Exception('Access denied')
        mock_client.secret_version_path.return_value = 'projects/test/secrets/key/versions/latest'

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        result = mapping._get_secret_value('key')
        assert result is None

    def test_getitem_cached(self) -> None:
        """Test __getitem__ returns cached value."""
        mock_client = MagicMock()
        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )
        mapping._loaded_secrets['my_key'] = 'cached_value'

        result = mapping['my_key']
        assert result == 'cached_value'

    def test_getitem_fetch_success(self) -> None:
        """Test __getitem__ fetches and caches value."""
        mock_client = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/MY_KEY'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'MY_KEY'}
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'secret_value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'path'

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        result = mapping['MY_KEY']
        assert result == 'secret_value'
        assert mapping._loaded_secrets['MY_KEY'] == 'secret_value'

    def test_getitem_case_insensitive(self) -> None:
        """Test __getitem__ with case insensitive lookup."""
        mock_client = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/MY_KEY'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'MY_KEY'}
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'secret_value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'path'

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=False
        )

        result = mapping['my_key']
        assert result == 'secret_value'

    def test_getitem_key_not_found(self) -> None:
        """Test __getitem__ raises KeyError for missing key."""
        mock_client = MagicMock()
        mock_client.list_secrets.return_value = []
        mock_client.common_project_path.return_value = 'projects/test-project'

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        with pytest.raises(KeyError):
            _ = mapping['missing_key']

    def test_len(self) -> None:
        """Test __len__ method."""
        mock_client = MagicMock()
        mock_secret_1 = MagicMock()
        mock_secret_1.name = 'projects/test-project/secrets/KEY1'
        mock_secret_2 = MagicMock()
        mock_secret_2.name = 'projects/test-project/secrets/KEY2'
        mock_client.list_secrets.return_value = [mock_secret_1, mock_secret_2]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'KEY1'},
            {'secret': 'KEY2'}
        ]

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        assert len(mapping) == 2

    def test_iter(self) -> None:
        """Test __iter__ method."""
        mock_client = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/MY_SECRET'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

        mapping = GoogleSecretManagerMapping(
            secret_client=mock_client,
            project_id='test-project',
            case_sensitive=True
        )

        keys = list(mapping)
        assert 'MY_SECRET' in keys


class TestGoogleSecretManagerSettingsSource:
    """Tests for GoogleSecretManagerSettingsSource class."""

    def _create_mock_settings_cls(self, **config_overrides: Any) -> type[BaseSettings]:
        """Helper to create a mock settings class."""
        config = {
            'case_sensitive': True,
            'env_prefix': '',
            'env_ignore_empty': False,
            'env_parse_none_str': None,
            'env_parse_enums': None,
            'env_nested_delimiter': None,
            'env_nested_max_split': None,
            **config_overrides
        }

        class TestSettings(BaseSettings):
            api_key: str = ''
            model_config = config  # type: ignore[assignment]

        return TestSettings

    def test_init_with_credentials_and_project(self) -> None:
        """Test initialization with explicit credentials and project_id."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        settings_cls = self._create_mock_settings_cls()

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client):
                source = GoogleSecretManagerSettingsSource(
                    settings_cls,
                    credentials=mock_credentials,
                    project_id='test-project',
                    secret_client=mock_client,
                )

        assert source._credentials is mock_credentials
        assert source._project_id == 'test-project'

    def test_init_uses_default_credentials(self) -> None:
        """Test initialization uses google.auth.default() when no credentials provided."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_default = MagicMock(return_value=(mock_credentials, 'default-project'))
        settings_cls = self._create_mock_settings_cls()

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default', mock_default):
                with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', MagicMock(return_value=mock_client)):
                    source = GoogleSecretManagerSettingsSource(
                        settings_cls,
                        secret_client=mock_client,
                    )

        assert source._credentials is mock_credentials
        assert source._project_id == 'default-project'

    def test_init_raises_without_project_id(self) -> None:
        """Test initialization raises when project_id cannot be determined."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_default = MagicMock(return_value=(mock_credentials, None))
        settings_cls = self._create_mock_settings_cls()

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default', mock_default):
                with pytest.raises(AttributeError) as exc_info:
                    GoogleSecretManagerSettingsSource(
                        settings_cls,
                        secret_client=mock_client,
                    )
                assert 'project_id is required' in str(exc_info.value)

    def test_init_creates_client_when_not_provided(self) -> None:
        """Test initialization creates SecretManagerServiceClient when not provided."""
        mock_credentials = MagicMock()
        mock_client_cls = MagicMock()
        mock_default = MagicMock(return_value=(mock_credentials, 'test-project'))
        settings_cls = self._create_mock_settings_cls()

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default', mock_default):
                with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client_cls):
                    GoogleSecretManagerSettingsSource(settings_cls)

        mock_client_cls.assert_called_once_with(credentials=mock_credentials)

    def test_load_env_vars_returns_mapping(self) -> None:
        """Test _load_env_vars returns GoogleSecretManagerMapping."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_client.list_secrets.return_value = []
        mock_client.common_project_path.return_value = 'projects/test-project'
        settings_cls = self._create_mock_settings_cls()

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                settings_cls,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
            )

        assert isinstance(source.env_vars, GoogleSecretManagerMapping)

    def test_repr(self) -> None:
        """Test __repr__ method."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_client.list_secrets.return_value = []
        mock_client.common_project_path.return_value = 'projects/test-project'
        settings_cls = self._create_mock_settings_cls()

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                settings_cls,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
            )

        result = repr(source)
        assert 'GoogleSecretManagerSettingsSource' in result
        assert 'test-project' in result

    def test_get_field_value_basic(self) -> None:
        """Test get_field_value for a basic field."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/api_key'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'api_key'}
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'secret_api_key'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'path'
        settings_cls = self._create_mock_settings_cls(case_sensitive=False)

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                settings_cls,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
                case_sensitive=False,
            )

        field_info = FieldInfo(annotation=str, default='')
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value == 'secret_api_key'

    def test_get_field_value_with_secret_version(self) -> None:
        """Test get_field_value with SecretVersion metadata."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/api_key'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'api_key'}
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'versioned_secret'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'path'

        class TestSettings(BaseSettings):
            api_key: str = Field(default='', json_schema_extra={'metadata': [SecretVersion('v2')]})

            model_config = {'case_sensitive': False}  # type: ignore[assignment]

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                TestSettings,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
                case_sensitive=False,
            )

        # Create field info with SecretVersion metadata
        field_info = FieldInfo(annotation=str, default='', metadata=[SecretVersion('v2')])
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value == 'versioned_secret'

    def test_get_field_value_secret_version_not_found(self) -> None:
        """Test get_field_value with SecretVersion when secret is not found."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_client.list_secrets.return_value = []
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.secret_version_path.return_value = 'path'

        class TestSettings(BaseSettings):
            api_key: str = ''

            model_config = {'case_sensitive': False}  # type: ignore[assignment]

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                TestSettings,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
                case_sensitive=False,
            )

        field_info = FieldInfo(annotation=str, default='', metadata=[SecretVersion('v2')])
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value is None

    def test_get_field_value_with_populate_by_name(self) -> None:
        """Test get_field_value respects populate_by_name config."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = 'projects/test-project/secrets/api_key'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.return_value = {'secret': 'api_key'}
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'versioned_secret'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'path'

        class TestSettings(BaseSettings):
            api_key: str = ''

            model_config = {'case_sensitive': False, 'populate_by_name': True}  # type: ignore[assignment]

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                TestSettings,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
                case_sensitive=False,
            )

        field_info = FieldInfo(annotation=str, default='', metadata=[SecretVersion('v2')])
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value == 'versioned_secret'
        assert key == 'api_key'


class TestGoogleSecretManagerIntegration:
    """Integration-style tests for GoogleSecretManagerSettingsSource."""

    def test_full_settings_loading(self) -> None:
        """Test loading settings from Google Secret Manager."""
        mock_client = MagicMock()
        mock_credentials = MagicMock()

        # Setup secrets
        mock_secret_1 = MagicMock()
        mock_secret_1.name = 'projects/test-project/secrets/DATABASE_URL'
        mock_secret_2 = MagicMock()
        mock_secret_2.name = 'projects/test-project/secrets/API_KEY'
        mock_client.list_secrets.return_value = [mock_secret_1, mock_secret_2]
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'DATABASE_URL'},
            {'secret': 'API_KEY'},
        ]

        def access_secret_version(name: str) -> MagicMock:
            mock_response = MagicMock()
            if 'DATABASE_URL' in name:
                mock_response.payload.data.decode.return_value = 'postgres://localhost/db'
            else:
                mock_response.payload.data.decode.return_value = 'my-api-key'
            return mock_response

        mock_client.access_secret_version.side_effect = access_secret_version
        mock_client.secret_version_path.side_effect = lambda proj, name, ver: f'projects/{proj}/secrets/{name}/versions/{ver}'

        class AppSettings(BaseSettings):
            database_url: str = ''
            api_key: str = ''

            model_config = {'case_sensitive': False}  # type: ignore[assignment]

        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                AppSettings,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_client,
                case_sensitive=False,
            )

        # Verify the env_vars mapping works
        assert isinstance(source.env_vars, GoogleSecretManagerMapping)
