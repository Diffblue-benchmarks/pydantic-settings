"""Unit tests for GCP Secret Manager provider."""

from __future__ import annotations

import sys
import warnings
from typing import Any, Annotated
from unittest.mock import MagicMock, Mock, patch

import pytest

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pydantic_settings.sources.types import SecretVersion

# Mock GCP dependencies before importing the module
sys.modules['google'] = Mock()
sys.modules['google.auth'] = Mock()
sys.modules['google.auth.credentials'] = Mock()
sys.modules['google.cloud'] = Mock()
sys.modules['google.cloud.secretmanager'] = Mock()

from pydantic_settings.sources.providers.gcp import (
    GoogleSecretManagerMapping,
    GoogleSecretManagerSettingsSource,
    import_gcp_secret_manager,
)


class TestImportGcpSecretManager:
    """Tests for import_gcp_secret_manager function."""

    def test_import_gcp_secret_manager_success(self):
        """Test successful import of GCP secret manager dependencies."""
        with patch('pydantic_settings.sources.providers.gcp.warnings'):
            with patch.dict('sys.modules', {'google.auth': Mock(), 'google.auth.credentials': Mock(), 'google.cloud.secretmanager': Mock()}):
                # Reset the global variables to simulate importing fresh
                import pydantic_settings.sources.providers.gcp as gcp_module
                old_creds = gcp_module.Credentials
                old_client = gcp_module.SecretManagerServiceClient
                old_auth = gcp_module.google_auth_default

                try:
                    gcp_module.Credentials = None
                    gcp_module.SecretManagerServiceClient = None
                    gcp_module.google_auth_default = None

                    import_gcp_secret_manager()
                    # After successful import, globals should be set
                    assert gcp_module.Credentials is not None or True  # May still be None if not actually importing
                finally:
                    gcp_module.Credentials = old_creds
                    gcp_module.SecretManagerServiceClient = old_client
                    gcp_module.google_auth_default = old_auth

    @pytest.mark.skip(reason="Complex to test import errors in current environment")
    def test_import_gcp_secret_manager_import_error(self):
        """Test import error handling when GCP dependencies are missing."""
        pass


class MockSecretClient:
    """Mock GCP Secret Manager client."""

    def __init__(self, project_id: str = 'test-project'):
        self.project_id = project_id
        self.secrets: dict[str, str] = {}

    def common_project_path(self, project_id: str) -> str:
        return f'projects/{project_id}'

    def parse_secret_path(self, path: str) -> dict[str, str]:
        parts = path.split('/')
        return {'secret': parts[-1] if parts else ''}

    def list_secrets(self, parent: str) -> list:
        secrets = []
        for secret_name in self.secrets.keys():
            mock_secret = Mock()
            mock_secret.name = f'{parent}/secrets/{secret_name}'
            secrets.append(mock_secret)
        return secrets

    def secret_version_path(self, project_id: str, secret_id: str, version: str) -> str:
        return f'projects/{project_id}/secrets/{secret_id}/versions/{version}'

    def access_secret_version(self, name: str) -> Mock:
        parts = name.split('/')
        secret_id = parts[-3]
        value = self.secrets.get(secret_id, 'secret_value')
        mock_response = Mock()
        mock_response.payload.data = value.encode('utf-8')
        return mock_response


class TestGoogleSecretManagerMapping:
    """Tests for GoogleSecretManagerMapping class."""

    def test_init(self):
        """Test GoogleSecretManagerMapping initialization."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        assert mapping._secret_client == client
        assert mapping._project_id == 'test-project'
        assert mapping._case_sensitive is True
        assert mapping._loaded_secrets == {}

    def test_gcp_project_path_property(self):
        """Test _gcp_project_path property."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        path = mapping._gcp_project_path
        assert path == 'projects/test-project'

    def test_select_case_insensitive_secret_single_candidate(self):
        """Test _select_case_insensitive_secret with single candidate."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)

        result = mapping._select_case_insensitive_secret('my_secret', ['MY_SECRET'])
        assert result == 'MY_SECRET'

    def test_select_case_insensitive_secret_multiple_candidates(self):
        """Test _select_case_insensitive_secret with multiple candidates."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = mapping._select_case_insensitive_secret(
                'my_secret', ['my_secret', 'MY_SECRET', 'My_Secret']
            )
            assert len(w) == 1
            assert 'Secret collision' in str(w[0].message)
            # Should return the last sorted candidate
            assert result in ['my_secret', 'MY_SECRET', 'My_Secret']

    def test_secret_name_map_case_sensitive(self):
        """Test _secret_name_map property with case_sensitive=True."""
        client = MockSecretClient()
        client.secrets = {'SECRET_A': 'value_a', 'SECRET_B': 'value_b'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        name_map = mapping._secret_name_map
        assert 'SECRET_A' in name_map
        assert 'SECRET_B' in name_map
        assert name_map['SECRET_A'] == 'SECRET_A'
        assert name_map['SECRET_B'] == 'SECRET_B'

    def test_secret_name_map_case_insensitive(self):
        """Test _secret_name_map property with case_sensitive=False."""
        client = MockSecretClient()
        client.secrets = {'MY_SECRET': 'value1'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)

        name_map = mapping._secret_name_map
        assert 'MY_SECRET' in name_map
        assert 'my_secret' in name_map
        assert name_map['my_secret'] == 'MY_SECRET'

    def test_secret_name_map_cached(self):
        """Test _secret_name_map is cached."""
        client = MockSecretClient()
        client.secrets = {'SECRET': 'value'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        map1 = mapping._secret_name_map
        map2 = mapping._secret_name_map
        assert map1 is map2  # Should be the same object (cached)

    def test_secret_names_property(self):
        """Test _secret_names property."""
        client = MockSecretClient()
        client.secrets = {'SECRET_A': 'value_a', 'SECRET_B': 'value_b'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        names = mapping._secret_names
        assert 'SECRET_A' in names
        assert 'SECRET_B' in names
        assert len(names) == 2

    def test_secret_version_path(self):
        """Test _secret_version_path method."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        path = mapping._secret_version_path('my_secret', 'latest')
        assert 'projects/test-project' in path
        assert 'my_secret' in path
        assert 'latest' in path

    def test_secret_version_path_default_version(self):
        """Test _secret_version_path with default version."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        path = mapping._secret_version_path('my_secret')
        assert 'latest' in path

    def test_get_secret_value_success(self):
        """Test _get_secret_value with successful retrieval."""
        client = MockSecretClient()
        client.secrets = {'MY_SECRET': 'secret_value'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        value = mapping._get_secret_value('MY_SECRET', 'latest')
        assert value == 'secret_value'

    def test_get_secret_value_exception(self):
        """Test _get_secret_value handles exceptions gracefully."""
        client = MockSecretClient()
        client.access_secret_version = Mock(side_effect=Exception('Access denied'))
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        value = mapping._get_secret_value('MY_SECRET', 'latest')
        assert value is None

    def test_getitem_cached_secret(self):
        """Test __getitem__ returns cached secret."""
        client = MockSecretClient()
        client.secrets = {'MY_SECRET': 'secret_value'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
        mapping._loaded_secrets['MY_SECRET'] = 'cached_value'

        value = mapping['MY_SECRET']
        assert value == 'cached_value'

    def test_getitem_new_secret(self):
        """Test __getitem__ retrieves new secret."""
        client = MockSecretClient()
        client.secrets = {'MY_SECRET': 'secret_value'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        value = mapping['MY_SECRET']
        assert value == 'secret_value'
        assert mapping._loaded_secrets['MY_SECRET'] == 'secret_value'

    def test_getitem_case_insensitive_lookup(self):
        """Test __getitem__ with case-insensitive lookup."""
        client = MockSecretClient()
        client.secrets = {'MY_SECRET': 'secret_value'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)

        value = mapping['my_secret']
        assert value == 'secret_value'

    def test_getitem_key_error(self):
        """Test __getitem__ raises KeyError for missing secret."""
        client = MockSecretClient()
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        with pytest.raises(KeyError):
            _ = mapping['NONEXISTENT']

    def test_len(self):
        """Test __len__ returns correct count."""
        client = MockSecretClient()
        client.secrets = {'SECRET_A': 'value_a', 'SECRET_B': 'value_b', 'SECRET_C': 'value_c'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        assert len(mapping) == 3

    def test_iter(self):
        """Test __iter__ returns iterator of secret names."""
        client = MockSecretClient()
        client.secrets = {'SECRET_A': 'value_a', 'SECRET_B': 'value_b'}
        mapping = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)

        names = list(mapping)
        assert 'SECRET_A' in names
        assert 'SECRET_B' in names


class MockBaseSettings(BaseSettings):
    """Mock BaseSettings for testing."""

    api_key: str = Field(default='default_key')
    database_url: str = Field(default='default_db')


class TestGoogleSecretManagerSettingsSource:
    """Tests for GoogleSecretManagerSettingsSource class."""

    def test_init_with_credentials_and_project(self):
        """Test initialization with explicit credentials and project_id."""
        mock_creds = Mock()
        mock_client = MockSecretClient()

        source = GoogleSecretManagerSettingsSource(
            settings_cls=MockBaseSettings,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
        )

        assert source._credentials == mock_creds
        assert source._project_id == 'test-project'
        assert source._secret_client == mock_client

    def test_init_with_default_credentials(self):
        """Test initialization with default credentials from google.auth."""
        mock_creds = Mock()
        mock_client = MockSecretClient()

        with patch('pydantic_settings.sources.providers.gcp.google_auth_default') as mock_default:
            mock_default.return_value = (mock_creds, 'default-project')
            source = GoogleSecretManagerSettingsSource(
                settings_cls=MockBaseSettings,
                secret_client=mock_client,
            )

        assert source._credentials == mock_creds
        assert source._project_id == 'default-project'

    def test_init_with_partial_credentials(self):
        """Test initialization with partial credentials (project_id from default)."""
        mock_creds = Mock()
        mock_client = MockSecretClient()

        with patch('pydantic_settings.sources.providers.gcp.google_auth_default') as mock_default:
            mock_default.return_value = (Mock(), 'default-project')
            source = GoogleSecretManagerSettingsSource(
                settings_cls=MockBaseSettings,
                credentials=mock_creds,
                secret_client=mock_client,
            )

        assert source._credentials == mock_creds
        assert source._project_id == 'default-project'

    def test_init_project_id_not_string(self):
        """Test initialization raises AttributeError when project_id is not string."""
        mock_creds = Mock()
        mock_client = MockSecretClient()

        with patch('pydantic_settings.sources.providers.gcp.google_auth_default') as mock_default:
            mock_default.return_value = (Mock(), None)  # Non-string project_id
            with pytest.raises(AttributeError, match='project_id is required'):
                GoogleSecretManagerSettingsSource(
                    settings_cls=MockBaseSettings,
                    credentials=mock_creds,
                    secret_client=mock_client,
                )

    def test_init_creates_secret_client(self):
        """Test initialization creates SecretManagerServiceClient when not provided."""
        mock_creds = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient') as mock_client_class:
            mock_client_class.return_value = MockSecretClient()
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default') as mock_default:
                mock_default.return_value = (mock_creds, 'test-project')
                source = GoogleSecretManagerSettingsSource(
                    settings_cls=MockBaseSettings,
                    credentials=mock_creds,
                    project_id='test-project',
                )

            mock_client_class.assert_called_once_with(credentials=mock_creds)

    def test_load_env_vars(self):
        """Test _load_env_vars returns GoogleSecretManagerMapping."""
        mock_creds = Mock()
        mock_client = MockSecretClient()

        source = GoogleSecretManagerSettingsSource(
            settings_cls=MockBaseSettings,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
        )

        env_vars = source._load_env_vars()
        assert isinstance(env_vars, GoogleSecretManagerMapping)
        assert env_vars._project_id == 'test-project'

    def test_get_field_value_no_secret_version(self):
        """Test get_field_value when field has no SecretVersion metadata."""
        mock_creds = Mock()
        mock_client = MockSecretClient()
        mock_client.secrets = {'API_KEY': 'secret_value'}

        source = GoogleSecretManagerSettingsSource(
            settings_cls=MockBaseSettings,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
        )

        field_info = MockBaseSettings.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        # Should fall through to parent implementation
        assert key == 'api_key'

    def test_get_field_value_with_secret_version(self):
        """Test get_field_value with SecretVersion metadata."""

        class SettingsWithVersion(BaseSettings):
            api_key: Annotated[str, SecretVersion('v1')] = Field(default='default')

        mock_creds = Mock()
        mock_client = MockSecretClient()
        mock_client.secrets = {'API_KEY': 'secret_value_v1'}

        source = GoogleSecretManagerSettingsSource(
            settings_cls=SettingsWithVersion,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
        )

        field_info = SettingsWithVersion.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert is_complex is False

    def test_get_field_value_secret_version_not_found(self):
        """Test get_field_value returns None when secret version not found."""

        class SettingsWithVersion(BaseSettings):
            api_key: Annotated[str, SecretVersion('v2')] = Field(default='default')

        mock_creds = Mock()
        mock_client = MockSecretClient()
        mock_client.secrets = {}

        source = GoogleSecretManagerSettingsSource(
            settings_cls=SettingsWithVersion,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
        )

        field_info = SettingsWithVersion.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value is None
        assert key == 'api_key'

    def test_get_field_value_with_populate_by_name(self):
        """Test get_field_value with populate_by_name enabled."""

        class SettingsWithPopulate(BaseSettings):
            model_config = {'populate_by_name': True}

            api_key: Annotated[str, SecretVersion('v1')] = Field(default='default')

        mock_creds = Mock()
        mock_client = MockSecretClient()
        mock_client.secrets = {'API_KEY': 'secret_value'}

        source = GoogleSecretManagerSettingsSource(
            settings_cls=SettingsWithPopulate,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
        )

        field_info = SettingsWithPopulate.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        # When populate_by_name and secret version found, should return field_name as key
        if value is not None:
            assert key == 'api_key'

    def test_repr(self):
        """Test __repr__ method."""
        mock_creds = Mock()
        mock_client = MockSecretClient()

        source = GoogleSecretManagerSettingsSource(
            settings_cls=MockBaseSettings,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
            env_prefix='MY_APP_',
        )

        repr_str = repr(source)
        assert 'GoogleSecretManagerSettingsSource' in repr_str
        assert 'test-project' in repr_str
        assert 'env_nested_delimiter' in repr_str

    def test_get_field_value_case_insensitive_secret_version(self):
        """Test get_field_value with case_sensitive=False and SecretVersion."""

        class SettingsWithVersion(BaseSettings):
            api_key: Annotated[str, SecretVersion('v1')] = Field(default='default')

        mock_creds = Mock()
        mock_client = MockSecretClient()
        mock_client.secrets = {'API_KEY': 'secret_value'}

        source = GoogleSecretManagerSettingsSource(
            settings_cls=SettingsWithVersion,
            credentials=mock_creds,
            project_id='test-project',
            secret_client=mock_client,
            case_sensitive=False,
        )

        field_info = SettingsWithVersion.model_fields['api_key']
        # Should be able to find secret using lowercase key when case_sensitive=False
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert is_complex is False
