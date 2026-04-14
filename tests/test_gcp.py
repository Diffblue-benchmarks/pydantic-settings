from __future__ import annotations

import warnings
from typing import Annotated, Any
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


@pytest.fixture
def mock_secret_client():
    """Fixture providing a mocked GCP Secret Manager client"""
    client = MagicMock()
    client.common_project_path = Mock(return_value='projects/test-project')
    client.secret_version_path = Mock(
        side_effect=lambda project, secret, version: f'projects/{project}/secrets/{secret}/versions/{version}'
    )
    client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )
    return client


@pytest.fixture
def mock_credentials():
    """Fixture providing mocked GCP credentials"""
    return MagicMock()


def test_import_gcp_secret_manager_success():
    """Test successful import of GCP secret manager dependencies"""
    with patch('pydantic_settings.sources.providers.gcp.Credentials', None):
        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', None):
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default', None):
                with patch('builtins.__import__', return_value=MagicMock()):
                    import_gcp_secret_manager()


def test_import_gcp_secret_manager_missing_dependencies():
    """Test import failure when GCP dependencies are not installed"""
    with patch('pydantic_settings.sources.providers.gcp.Credentials', None):
        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', None):
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default', None):
                with patch('builtins.__import__', side_effect=ImportError('No module named google')):
                    with pytest.raises(ImportError, match='GCP Secret Manager dependencies are not installed'):
                        import_gcp_secret_manager()


def test_google_secret_manager_mapping_init(mock_secret_client):
    """Test initialization of GoogleSecretManagerMapping"""
    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    assert mapping._secret_client == mock_secret_client
    assert mapping._project_id == 'test-project'
    assert mapping._case_sensitive is True
    assert mapping._loaded_secrets == {}


def test_gcp_project_path(mock_secret_client):
    """Test _gcp_project_path property"""
    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    path = mapping._gcp_project_path

    assert path == 'projects/test-project'
    mock_secret_client.common_project_path.assert_called_once_with('test-project')


def test_select_case_insensitive_secret_single_candidate(mock_secret_client):
    """Test selecting secret when only one candidate exists"""
    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    result = mapping._select_case_insensitive_secret('mykey', ['MyKey'])

    assert result == 'MyKey'


def test_select_case_insensitive_secret_multiple_candidates(mock_secret_client):
    """Test selecting secret with multiple candidates triggers warning"""
    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        result = mapping._select_case_insensitive_secret('mykey', ['MyKey', 'MYKEY', 'mykey'])

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert 'Secret collision' in str(w[0].message)
        assert result == 'mykey'  # Last after sort


def test_secret_name_map_case_sensitive(mock_secret_client):
    """Test building secret name map in case-sensitive mode"""
    mock_secret1 = MagicMock()
    mock_secret1.name = 'projects/test-project/secrets/API_KEY'
    mock_secret2 = MagicMock()
    mock_secret2.name = 'projects/test-project/secrets/DB_PASSWORD'

    mock_secret_client.list_secrets = Mock(return_value=[mock_secret1, mock_secret2])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    name_map = mapping._secret_name_map

    assert 'API_KEY' in name_map
    assert 'DB_PASSWORD' in name_map
    assert name_map['API_KEY'] == 'API_KEY'
    assert name_map['DB_PASSWORD'] == 'DB_PASSWORD'


def test_secret_name_map_case_insensitive(mock_secret_client):
    """Test building secret name map in case-insensitive mode"""
    mock_secret1 = MagicMock()
    mock_secret1.name = 'projects/test-project/secrets/API_KEY'
    mock_secret2 = MagicMock()
    mock_secret2.name = 'projects/test-project/secrets/api_key'

    mock_secret_client.list_secrets = Mock(return_value=[mock_secret1, mock_secret2])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        name_map = mapping._secret_name_map

        assert 'API_KEY' in name_map
        assert 'api_key' in name_map
        assert 'api_key' in name_map  # lowercase key should be in map


def test_secret_names(mock_secret_client):
    """Test _secret_names property"""
    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/TEST_SECRET'

    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    names = mapping._secret_names

    assert 'TEST_SECRET' in names


def test_secret_version_path(mock_secret_client):
    """Test _secret_version_path method"""
    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    path = mapping._secret_version_path('MY_SECRET', '123')

    assert path == 'projects/test-project/secrets/MY_SECRET/versions/123'
    mock_secret_client.secret_version_path.assert_called_once_with('test-project', 'MY_SECRET', '123')


def test_get_secret_value_success(mock_secret_client):
    """Test successful retrieval of secret value"""
    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='secret-value')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    value = mapping._get_secret_value('MY_SECRET', 'latest')

    assert value == 'secret-value'
    mock_secret_client.access_secret_version.assert_called_once()


def test_get_secret_value_failure(mock_secret_client):
    """Test secret retrieval returns None on failure"""
    mock_secret_client.access_secret_version = Mock(side_effect=Exception('Secret not found'))

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    value = mapping._get_secret_value('NON_EXISTENT', 'latest')

    assert value is None


def test_getitem_cached_secret(mock_secret_client):
    """Test __getitem__ returns cached secret"""
    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    mapping._loaded_secrets['CACHED_KEY'] = 'cached-value'

    value = mapping['CACHED_KEY']

    assert value == 'cached-value'


def test_getitem_case_sensitive_lookup(mock_secret_client):
    """Test __getitem__ with case-sensitive lookup"""
    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/API_KEY'
    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='my-api-key')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    value = mapping['API_KEY']

    assert value == 'my-api-key'


def test_getitem_case_insensitive_lookup(mock_secret_client):
    """Test __getitem__ with case-insensitive lookup"""
    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/API_KEY'
    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='my-api-key')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    value = mapping['api_key']

    assert value == 'my-api-key'


def test_getitem_key_not_found(mock_secret_client):
    """Test __getitem__ raises KeyError for missing key"""
    mock_secret_client.list_secrets = Mock(return_value=[])

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    with pytest.raises(KeyError):
        _ = mapping['NON_EXISTENT']


def test_len(mock_secret_client):
    """Test __len__ returns correct count"""
    mock_secret1 = MagicMock()
    mock_secret1.name = 'projects/test-project/secrets/SECRET1'
    mock_secret2 = MagicMock()
    mock_secret2.name = 'projects/test-project/secrets/SECRET2'

    mock_secret_client.list_secrets = Mock(return_value=[mock_secret1, mock_secret2])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    assert len(mapping) == 2


def test_iter(mock_secret_client):
    """Test __iter__ returns iterator over secret names"""
    mock_secret1 = MagicMock()
    mock_secret1.name = 'projects/test-project/secrets/SECRET1'
    mock_secret2 = MagicMock()
    mock_secret2.name = 'projects/test-project/secrets/SECRET2'

    mock_secret_client.list_secrets = Mock(return_value=[mock_secret1, mock_secret2])
    mock_secret_client.parse_secret_path = Mock(
        side_effect=lambda path: {'secret': path.split('/')[-1]}
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    names = list(mapping)

    assert 'SECRET1' in names
    assert 'SECRET2' in names


def test_settings_source_init_with_credentials_and_project(mock_secret_client, mock_credentials):
    """Test GoogleSecretManagerSettingsSource initialization with provided credentials and project"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient') as mock_client_class:
        mock_client_class.return_value = mock_secret_client
        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                TestSettings,
                credentials=mock_credentials,
                project_id='test-project',
                secret_client=mock_secret_client,
            )

    assert source._credentials == mock_credentials
    assert source._project_id == 'test-project'
    assert source._secret_client == mock_secret_client


def test_settings_source_init_imports_packages():
    """Test GoogleSecretManagerSettingsSource imports GCP packages when needed"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', None):
        with patch('pydantic_settings.sources.providers.gcp.Credentials', None):
            with patch('pydantic_settings.sources.providers.gcp.google_auth_default', None):
                with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager') as mock_import:
                    mock_creds = MagicMock()
                    mock_client = MagicMock()
                    mock_client.common_project_path = Mock(return_value='projects/test')

                    with patch('pydantic_settings.sources.providers.gcp.google_auth_default', return_value=(mock_creds, 'test-project')):
                        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', return_value=mock_client):
                            source = GoogleSecretManagerSettingsSource(TestSettings)

                            mock_import.assert_called_once()


def test_settings_source_init_uses_default_credentials(mock_secret_client):
    """Test GoogleSecretManagerSettingsSource uses default credentials when not provided"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    mock_creds = MagicMock()

    with patch('pydantic_settings.sources.providers.gcp.google_auth_default', return_value=(mock_creds, 'default-project')):
        with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', return_value=mock_secret_client):
            with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
                source = GoogleSecretManagerSettingsSource(TestSettings)

    assert source._credentials == mock_creds
    assert source._project_id == 'default-project'


def test_settings_source_init_raises_when_no_project_id():
    """Test GoogleSecretManagerSettingsSource raises when project_id cannot be determined"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    mock_creds = MagicMock()

    with patch('pydantic_settings.sources.providers.gcp.google_auth_default', return_value=(mock_creds, None)):
        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            with pytest.raises(AttributeError, match='project_id is required'):
                GoogleSecretManagerSettingsSource(TestSettings)


def test_settings_source_init_creates_client_when_not_provided(mock_credentials):
    """Test GoogleSecretManagerSettingsSource creates client when not provided"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    mock_client = MagicMock()

    with patch('pydantic_settings.sources.providers.gcp.SecretManagerServiceClient', return_value=mock_client) as mock_client_class:
        with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
            source = GoogleSecretManagerSettingsSource(
                TestSettings,
                credentials=mock_credentials,
                project_id='test-project'
            )

    mock_client_class.assert_called_once_with(credentials=mock_credentials)
    assert source._secret_client == mock_client


def test_get_field_value_with_secret_version(mock_secret_client):
    """Test get_field_value with SecretVersion metadata"""

    class TestSettings(BaseSettings):
        model_config = {'populate_by_name': False}
        api_key: Annotated[str, SecretVersion('42')] = ''

    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/api_key'
    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(side_effect=lambda path: {'secret': path.split('/')[-1]})

    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='versioned-secret')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='test-project',
            secret_client=mock_secret_client,
        )

    field_info = TestSettings.model_fields['api_key']
    value, key, is_complex = source.get_field_value(field_info, 'api_key')

    assert value == 'versioned-secret'
    assert is_complex is False


def test_get_field_value_with_secret_version_not_found(mock_secret_client):
    """Test get_field_value returns None when versioned secret not found"""

    class TestSettings(BaseSettings):
        model_config = {'populate_by_name': False}
        api_key: Annotated[str, SecretVersion('999')] = ''

    mock_secret_client.list_secrets = Mock(return_value=[])

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='test-project',
            secret_client=mock_secret_client,
        )

    field_info = TestSettings.model_fields['api_key']
    value, key, is_complex = source.get_field_value(field_info, 'api_key')

    assert value is None
    assert is_complex is False


def test_get_field_value_with_populate_by_name(mock_secret_client):
    """Test get_field_value with populate_by_name enabled"""

    class TestSettings(BaseSettings):
        model_config = {'populate_by_name': True}
        api_key: Annotated[str, SecretVersion('1')] = ''

    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/api_key'
    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(side_effect=lambda path: {'secret': path.split('/')[-1]})

    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='versioned-secret')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='test-project',
            secret_client=mock_secret_client,
        )

    field_info = TestSettings.model_fields['api_key']
    value, key, is_complex = source.get_field_value(field_info, 'api_key')

    assert value == 'versioned-secret'
    assert key == 'api_key'


def test_get_field_value_without_secret_version(mock_secret_client):
    """Test get_field_value without SecretVersion metadata falls back to parent"""

    class TestSettings(BaseSettings):
        model_config = {'populate_by_name': False}
        api_key: str = ''

    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/api_key'
    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(side_effect=lambda path: {'secret': path.split('/')[-1]})

    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='latest-secret')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='test-project',
            secret_client=mock_secret_client,
        )

    field_info = TestSettings.model_fields['api_key']
    value, key, is_complex = source.get_field_value(field_info, 'api_key')

    assert value == 'latest-secret'


def test_get_field_value_populate_by_name_without_version(mock_secret_client):
    """Test get_field_value with populate_by_name but no version"""

    class TestSettings(BaseSettings):
        model_config = {'populate_by_name': True}
        api_key: str = ''

    mock_secret = MagicMock()
    mock_secret.name = 'projects/test-project/secrets/api_key'
    mock_secret_client.list_secrets = Mock(return_value=[mock_secret])
    mock_secret_client.parse_secret_path = Mock(side_effect=lambda path: {'secret': path.split('/')[-1]})

    mock_response = MagicMock()
    mock_response.payload.data.decode = Mock(return_value='latest-secret')
    mock_secret_client.access_secret_version = Mock(return_value=mock_response)

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='test-project',
            secret_client=mock_secret_client,
        )

    field_info = TestSettings.model_fields['api_key']
    value, key, is_complex = source.get_field_value(field_info, 'api_key')

    assert value == 'latest-secret'
    assert key == 'api_key'


def test_load_env_vars(mock_secret_client):
    """Test _load_env_vars creates GoogleSecretManagerMapping"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='test-project',
            secret_client=mock_secret_client,
        )

    env_vars = source._load_env_vars()

    assert isinstance(env_vars, GoogleSecretManagerMapping)
    assert env_vars._project_id == 'test-project'
    assert env_vars._secret_client == mock_secret_client


def test_settings_source_repr(mock_secret_client):
    """Test __repr__ of GoogleSecretManagerSettingsSource"""

    class TestSettings(BaseSettings):
        api_key: str = ''

    with patch('pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'):
        source = GoogleSecretManagerSettingsSource(
            TestSettings,
            credentials=MagicMock(),
            project_id='my-project',
            secret_client=mock_secret_client,
        )

    repr_str = repr(source)

    assert 'GoogleSecretManagerSettingsSource' in repr_str
    assert 'my-project' in repr_str
