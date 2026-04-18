"""Unit tests for Google Secret Manager provider."""

import warnings
from typing import Annotated
from unittest.mock import MagicMock, Mock, patch

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
    def test_import_gcp_secret_manager_success(self):
        """Test successful import of GCP Secret Manager dependencies."""
        with patch('pydantic_settings.sources.providers.gcp.Credentials', None):
            with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', None):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', None):
                    with patch('builtins.__import__') as mock_import:
                        import_gcp_secret_manager()
                        assert mock_import.called

    def test_import_gcp_secret_manager_missing_dependencies(self):
        """Test import failure when GCP dependencies are not installed."""
        with patch('builtins.__import__', side_effect=ImportError('No module')):
            with pytest.raises(ImportError) as exc_info:
                import_gcp_secret_manager()
            assert 'GCP Secret Manager dependencies are not installed' in str(exc_info.value)


class TestGoogleSecretManagerMapping:
    def test_init(self):
        """Test GoogleSecretManagerMapping initialization."""
        mock_client = Mock()
        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)

        assert mapping._secret_client == mock_client
        assert mapping._project_id == 'test-project'
        assert mapping._case_sensitive is True
        assert mapping._loaded_secrets == {}

    def test_gcp_project_path(self):
        """Test _gcp_project_path property."""
        mock_client = Mock()
        mock_client.common_project_path.return_value = 'projects/test-project'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        assert mapping._gcp_project_path == 'projects/test-project'
        mock_client.common_project_path.assert_called_once_with('test-project')

    def test_select_case_insensitive_secret_single_candidate(self):
        """Test selecting secret when there's only one candidate."""
        mock_client = Mock()
        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', False)

        result = mapping._select_case_insensitive_secret('secret', ['SECRET'])
        assert result == 'SECRET'

    def test_select_case_insensitive_secret_multiple_candidates(self):
        """Test selecting secret when there are multiple candidates."""
        mock_client = Mock()
        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = mapping._select_case_insensitive_secret('secret', ['SECRET', 'secret', 'Secret'])
            assert len(w) == 1
            assert 'Secret collision' in str(w[0].message)
            assert result == 'secret'  # Last after sorting

    def test_secret_name_map_case_sensitive(self):
        """Test _secret_name_map property with case-sensitive mode."""
        mock_client = Mock()
        mock_secret1 = Mock()
        mock_secret1.name = 'projects/test-project/secrets/SECRET1'
        mock_secret2 = Mock()
        mock_secret2.name = 'projects/test-project/secrets/SECRET2'

        mock_client.list_secrets.return_value = [mock_secret1, mock_secret2]
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'SECRET1'},
            {'secret': 'SECRET2'}
        ]

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        name_map = mapping._secret_name_map

        assert name_map == {'SECRET1': 'SECRET1', 'SECRET2': 'SECRET2'}

    def test_secret_name_map_case_insensitive(self):
        """Test _secret_name_map property with case-insensitive mode."""
        mock_client = Mock()
        mock_secret1 = Mock()
        mock_secret1.name = 'projects/test-project/secrets/SECRET1'
        mock_secret2 = Mock()
        mock_secret2.name = 'projects/test-project/secrets/secret2'

        mock_client.list_secrets.return_value = [mock_secret1, mock_secret2]
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'SECRET1'},
            {'secret': 'secret2'}
        ]

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', False)
        name_map = mapping._secret_name_map

        assert 'SECRET1' in name_map
        assert 'secret2' in name_map
        assert 'secret1' in name_map
        assert 'secret2' in name_map

    def test_secret_names(self):
        """Test _secret_names property."""
        mock_client = Mock()
        mock_secret = Mock()
        mock_secret.name = 'projects/test-project/secrets/SECRET1'

        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.parse_secret_path.return_value = {'secret': 'SECRET1'}

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        names = mapping._secret_names

        assert 'SECRET1' in names

    def test_secret_version_path(self):
        """Test _secret_version_path method."""
        mock_client = Mock()
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/SECRET1/versions/latest'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        path = mapping._secret_version_path('SECRET1')

        assert path == 'projects/test-project/secrets/SECRET1/versions/latest'
        mock_client.secret_version_path.assert_called_once_with('test-project', 'SECRET1', 'latest')

    def test_secret_version_path_with_version(self):
        """Test _secret_version_path method with specific version."""
        mock_client = Mock()
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/SECRET1/versions/5'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        path = mapping._secret_version_path('SECRET1', '5')

        assert path == 'projects/test-project/secrets/SECRET1/versions/5'
        mock_client.secret_version_path.assert_called_once_with('test-project', 'SECRET1', '5')

    def test_get_secret_value_success(self):
        """Test _get_secret_value method with successful retrieval."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.payload.data = b'secret-value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/SECRET1/versions/latest'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        value = mapping._get_secret_value('SECRET1')

        assert value == 'secret-value'

    def test_get_secret_value_failure(self):
        """Test _get_secret_value method when retrieval fails."""
        mock_client = Mock()
        mock_client.access_secret_version.side_effect = Exception('Access denied')
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/SECRET1/versions/latest'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        value = mapping._get_secret_value('SECRET1')

        assert value is None

    def test_getitem_cached(self):
        """Test __getitem__ with cached secret."""
        mock_client = Mock()
        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        mapping._loaded_secrets['SECRET1'] = 'cached-value'

        value = mapping['SECRET1']
        assert value == 'cached-value'

    def test_getitem_case_sensitive(self):
        """Test __getitem__ with case-sensitive lookup."""
        mock_client = Mock()
        mock_secret = Mock()
        mock_secret.name = 'projects/test-project/secrets/SECRET1'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.parse_secret_path.return_value = {'secret': 'SECRET1'}

        mock_response = Mock()
        mock_response.payload.data = b'secret-value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/SECRET1/versions/latest'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        value = mapping['SECRET1']

        assert value == 'secret-value'
        assert mapping._loaded_secrets['SECRET1'] == 'secret-value'

    def test_getitem_case_insensitive(self):
        """Test __getitem__ with case-insensitive lookup."""
        mock_client = Mock()
        mock_secret = Mock()
        mock_secret.name = 'projects/test-project/secrets/SECRET1'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.parse_secret_path.return_value = {'secret': 'SECRET1'}

        mock_response = Mock()
        mock_response.payload.data = b'secret-value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/SECRET1/versions/latest'

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', False)
        value = mapping['secret1']

        assert value == 'secret-value'

    def test_getitem_not_found(self):
        """Test __getitem__ with non-existent secret."""
        mock_client = Mock()
        mock_client.list_secrets.return_value = []

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)

        with pytest.raises(KeyError):
            _ = mapping['NONEXISTENT']

    def test_len(self):
        """Test __len__ method."""
        mock_client = Mock()
        mock_secret1 = Mock()
        mock_secret1.name = 'projects/test-project/secrets/SECRET1'
        mock_secret2 = Mock()
        mock_secret2.name = 'projects/test-project/secrets/SECRET2'

        mock_client.list_secrets.return_value = [mock_secret1, mock_secret2]
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'SECRET1'},
            {'secret': 'SECRET2'}
        ]

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        assert len(mapping) == 2

    def test_iter(self):
        """Test __iter__ method."""
        mock_client = Mock()
        mock_secret1 = Mock()
        mock_secret1.name = 'projects/test-project/secrets/SECRET1'
        mock_secret2 = Mock()
        mock_secret2.name = 'projects/test-project/secrets/SECRET2'

        mock_client.list_secrets.return_value = [mock_secret1, mock_secret2]
        mock_client.parse_secret_path.side_effect = [
            {'secret': 'SECRET1'},
            {'secret': 'SECRET2'}
        ]

        mapping = GoogleSecretManagerMapping(mock_client, 'test-project', True)
        names = list(mapping)

        assert 'SECRET1' in names
        assert 'SECRET2' in names


class TestGoogleSecretManagerSettingsSource:
    def test_init_with_credentials_and_project(self):
        """Test initialization with provided credentials and project_id."""
        mock_credentials = Mock()
        mock_client = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', mock_credentials):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        pass

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project'
                    )

                    assert source._credentials == mock_credentials
                    assert source._project_id == 'test-project'

    def test_init_with_default_credentials(self):
        """Test initialization using default credentials."""
        mock_credentials = Mock()
        mock_client_class = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient') as mock_sm:
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default') as mock_auth:
                    mock_auth.return_value = (mock_credentials, 'default-project')
                    mock_sm.return_value = mock_client_class

                    class TestSettings(BaseSettings):
                        pass

                    source = GoogleSecretManagerSettingsSource(TestSettings)

                    assert source._credentials == mock_credentials
                    assert source._project_id == 'default-project'

    def test_init_without_project_id_raises_error(self):
        """Test initialization fails when project_id cannot be determined."""
        mock_credentials = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', Mock()):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default') as mock_auth:
                    mock_auth.return_value = (mock_credentials, None)

                    class TestSettings(BaseSettings):
                        pass

                    with pytest.raises(AttributeError) as exc_info:
                        GoogleSecretManagerSettingsSource(TestSettings)

                    assert 'project_id is required' in str(exc_info.value)

    def test_init_with_custom_secret_client(self):
        """Test initialization with custom secret client."""
        mock_credentials = Mock()
        mock_client = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', Mock()):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        pass

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project',
                        secret_client=mock_client
                    )

                    assert source._secret_client == mock_client

    def test_init_imports_gcp_when_needed(self):
        """Test that GCP dependencies are imported when not available."""
        import pydantic_settings.sources.providers.gcp as gcp_module

        original_sm = gcp_module.SecretManagerServiceClient
        original_creds = gcp_module.Credentials
        original_auth = gcp_module.google_auth_default

        try:
            gcp_module.SecretManagerServiceClient = None
            gcp_module.Credentials = None
            gcp_module.google_auth_default = None

            with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager') as mock_import:
                mock_credentials = Mock()
                mock_client_class = Mock()

                def import_side_effect():
                    gcp_module.SecretManagerServiceClient = mock_client_class
                    gcp_module.Credentials = mock_credentials
                    gcp_module.google_auth_default = Mock(return_value=(mock_credentials, 'test-project'))

                mock_import.side_effect = import_side_effect

                class TestSettings(BaseSettings):
                    pass

                source = GoogleSecretManagerSettingsSource(TestSettings)
                mock_import.assert_called_once()
        finally:
            gcp_module.SecretManagerServiceClient = original_sm
            gcp_module.Credentials = original_creds
            gcp_module.google_auth_default = original_auth

    def test_get_field_value_without_secret_version(self):
        """Test get_field_value without SecretVersion metadata."""
        mock_credentials = Mock()
        mock_client_class = Mock()
        mock_client = Mock()
        mock_secret = Mock()
        mock_secret.name = 'projects/test-project/secrets/my_secret'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.parse_secret_path.return_value = {'secret': 'my_secret'}

        mock_response = Mock()
        mock_response.payload.data = b'secret-value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/my_secret/versions/latest'
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client_class.return_value = mock_client

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client_class):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        my_secret: str = Field(default='')

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project'
                    )

                    field_info = TestSettings.model_fields['my_secret']
                    value, key, is_complex = source.get_field_value(field_info, 'my_secret')

                    assert value == 'secret-value'
                    assert key == 'my_secret'

    def test_get_field_value_with_secret_version(self):
        """Test get_field_value with SecretVersion metadata."""
        mock_credentials = Mock()
        mock_client_class = Mock()
        mock_client = Mock()
        mock_secret = Mock()
        mock_secret.name = 'projects/test-project/secrets/MY_SECRET'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

        mock_response = Mock()
        mock_response.payload.data = b'secret-value-v2'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/MY_SECRET/versions/2'
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client_class.return_value = mock_client

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client_class):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        my_secret: Annotated[str, Field(default='', alias='MY_SECRET'), SecretVersion('2')]

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project'
                    )

                    field_info = TestSettings.model_fields['my_secret']
                    value, key, is_complex = source.get_field_value(field_info, 'my_secret')

                    assert value == 'secret-value-v2'

    def test_get_field_value_with_secret_version_not_found(self):
        """Test get_field_value with SecretVersion metadata when secret not found."""
        mock_credentials = Mock()
        mock_client_class = Mock()
        mock_client = Mock()
        mock_client.list_secrets.return_value = []
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client_class.return_value = mock_client

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client_class):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        my_secret: Annotated[str, Field(default='', alias='MY_SECRET'), SecretVersion('2')]

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project'
                    )

                    field_info = TestSettings.model_fields['my_secret']
                    value, key, is_complex = source.get_field_value(field_info, 'my_secret')

                    assert value is None
                    assert key == 'my_secret'
                    assert is_complex is False

    def test_get_field_value_with_populate_by_name(self):
        """Test get_field_value with populate_by_name enabled."""
        mock_credentials = Mock()
        mock_client_class = Mock()
        mock_client = Mock()
        mock_secret = Mock()
        mock_secret.name = 'projects/test-project/secrets/my_secret'
        mock_client.list_secrets.return_value = [mock_secret]
        mock_client.parse_secret_path.return_value = {'secret': 'my_secret'}

        mock_response = Mock()
        mock_response.payload.data = b'secret-value'
        mock_client.access_secret_version.return_value = mock_response
        mock_client.secret_version_path.return_value = 'projects/test-project/secrets/my_secret/versions/latest'
        mock_client.common_project_path.return_value = 'projects/test-project'
        mock_client_class.return_value = mock_client

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client_class):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        model_config = {'populate_by_name': True}
                        my_secret: str = Field(default='')

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project'
                    )

                    field_info = TestSettings.model_fields['my_secret']
                    value, key, is_complex = source.get_field_value(field_info, 'my_secret')

                    assert value == 'secret-value'
                    assert key == 'my_secret'

    def test_load_env_vars(self):
        """Test _load_env_vars method."""
        mock_credentials = Mock()
        mock_client = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        pass

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project',
                        secret_client=mock_client
                    )

                    env_vars = source._load_env_vars()

                    assert isinstance(env_vars, GoogleSecretManagerMapping)
                    assert env_vars._secret_client == mock_client
                    assert env_vars._project_id == 'test-project'

    def test_repr(self):
        """Test __repr__ method."""
        mock_credentials = Mock()
        mock_client = Mock()

        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', mock_client):
            with patch('pydantic_settings.sources.providers.gcp.Credentials', Mock()):
                with patch('pydantic_settings.sources.providers.gcp.google_auth_default', Mock()):
                    class TestSettings(BaseSettings):
                        pass

                    source = GoogleSecretManagerSettingsSource(
                        TestSettings,
                        credentials=mock_credentials,
                        project_id='test-project',
                        secret_client=mock_client
                    )

                    repr_str = repr(source)

                    assert 'GoogleSecretManagerSettingsSource' in repr_str
                    assert 'test-project' in repr_str
