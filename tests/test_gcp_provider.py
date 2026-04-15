"""Tests for GCP Secret Manager settings provider."""
from __future__ import annotations

import sys
import warnings
from typing import Annotated, Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.sources.types import SecretVersion


def _make_google_mocks():
    """Create mock google modules for patching sys.modules."""
    mock_credentials_cls = MagicMock(name='Credentials')
    mock_secret_manager_client_cls = MagicMock(name='SecretManagerServiceClient')
    mock_google_auth_default = MagicMock(name='google_auth_default')

    mock_google_auth = MagicMock()
    mock_google_auth.default = mock_google_auth_default
    mock_google_auth_credentials = MagicMock()
    mock_google_auth_credentials.Credentials = mock_credentials_cls

    mock_google_cloud_secretmanager = MagicMock()
    mock_google_cloud_secretmanager.SecretManagerServiceClient = mock_secret_manager_client_cls

    google_modules = {
        'google': MagicMock(),
        'google.auth': mock_google_auth,
        'google.auth.credentials': mock_google_auth_credentials,
        'google.cloud': MagicMock(),
        'google.cloud.secretmanager': mock_google_cloud_secretmanager,
    }
    return google_modules, mock_credentials_cls, mock_secret_manager_client_cls, mock_google_auth_default


@pytest.fixture
def google_mocks():
    """Fixture that patches sys.modules with mock google packages."""
    google_modules, mock_credentials_cls, mock_smc_cls, mock_auth_default = _make_google_mocks()

    with patch.dict(sys.modules, google_modules):
        # Reset the gcp module globals so import_gcp_secret_manager can set them
        import pydantic_settings.sources.providers.gcp as gcp_module

        original_creds = gcp_module.Credentials
        original_smc = gcp_module.SecretManagerServiceClient
        original_auth_default = gcp_module.google_auth_default

        gcp_module.Credentials = None
        gcp_module.SecretManagerServiceClient = None
        gcp_module.google_auth_default = None

        yield {
            'gcp_module': gcp_module,
            'Credentials': mock_credentials_cls,
            'SecretManagerServiceClient': mock_smc_cls,
            'google_auth_default': mock_auth_default,
        }

        gcp_module.Credentials = original_creds
        gcp_module.SecretManagerServiceClient = original_smc
        gcp_module.google_auth_default = original_auth_default


@pytest.fixture
def mock_secret_client():
    """Create a mock SecretManagerServiceClient."""
    client = MagicMock(name='secret_client')
    client.common_project_path.return_value = 'projects/test-project'
    client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}
    client.secret_version_path.return_value = 'projects/test-project/secrets/MY_SECRET/versions/latest'
    return client


class SimpleSettings(BaseSettings):
    model_config = {'arbitrary_types_allowed': True}

    my_field: str = 'default'


class SimpleSettingsPopulateByName(BaseSettings):
    model_config = {'arbitrary_types_allowed': True, 'populate_by_name': True}

    my_field: str = 'default'


# ---- Tests for import_gcp_secret_manager ----


def test_import_gcp_secret_manager_sets_globals(google_mocks):
    gcp_module = google_mocks['gcp_module']

    assert gcp_module.Credentials is None
    assert gcp_module.SecretManagerServiceClient is None
    assert gcp_module.google_auth_default is None

    gcp_module.import_gcp_secret_manager()

    assert gcp_module.Credentials is not None
    assert gcp_module.SecretManagerServiceClient is not None
    assert gcp_module.google_auth_default is not None


def test_import_gcp_secret_manager_can_be_called_twice(google_mocks):
    gcp_module = google_mocks['gcp_module']
    gcp_module.import_gcp_secret_manager()
    gcp_module.import_gcp_secret_manager()
    assert gcp_module.SecretManagerServiceClient is not None


# ---- Tests for GoogleSecretManagerMapping ----


def test_mapping_init(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    assert mapping._project_id == 'test-project'
    assert mapping._case_sensitive is True
    assert mapping._loaded_secrets == {}
    assert mapping._secret_client is mock_secret_client


def test_mapping_gcp_project_path(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    path = mapping._gcp_project_path

    mock_secret_client.common_project_path.assert_called_once_with('test-project')
    assert path == 'projects/test-project'


def test_select_case_insensitive_secret_single_candidate(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)
    result = mapping._select_case_insensitive_secret('my_secret', ['MY_SECRET'])

    assert result == 'MY_SECRET'


def test_select_case_insensitive_secret_multiple_candidates_warns(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    with pytest.warns(UserWarning, match='Secret collision'):
        result = mapping._select_case_insensitive_secret('my_secret', ['MY_SECRET', 'my_secret', 'My_Secret'])

    assert isinstance(result, str)
    assert result in ['MY_SECRET', 'my_secret', 'My_Secret']


def test_select_case_insensitive_secret_multiple_candidates_uses_last_sorted(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    candidates = ['abc', 'xyz', 'mno']
    with pytest.warns(UserWarning):
        result = mapping._select_case_insensitive_secret('abc', candidates)

    # sorted descending: ['xyz', 'mno', 'abc'], last is 'xyz'
    assert result == 'xyz'


def test_secret_name_map_case_sensitive(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/MY_SECRET'
    secret2 = MagicMock()
    secret2.name = 'projects/test-project/secrets/OTHER_SECRET'

    mock_secret_client.list_secrets.return_value = [secret1, secret2]
    mock_secret_client.parse_secret_path.side_effect = [
        {'secret': 'MY_SECRET'},
        {'secret': 'OTHER_SECRET'},
    ]

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    name_map = mapping._secret_name_map

    assert 'MY_SECRET' in name_map
    assert 'OTHER_SECRET' in name_map
    assert name_map['MY_SECRET'] == 'MY_SECRET'


def test_secret_name_map_case_insensitive_no_collision(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/MY_SECRET'

    mock_secret_client.list_secrets.return_value = [secret1]
    mock_secret_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)
    name_map = mapping._secret_name_map

    assert 'MY_SECRET' in name_map
    assert 'my_secret' in name_map
    assert name_map['my_secret'] == 'MY_SECRET'


def test_secret_name_map_case_insensitive_with_collision(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/MY_SECRET'
    secret2 = MagicMock()
    secret2.name = 'projects/test-project/secrets/my_secret'

    mock_secret_client.list_secrets.return_value = [secret1, secret2]
    mock_secret_client.parse_secret_path.side_effect = [
        {'secret': 'MY_SECRET'},
        {'secret': 'my_secret'},
    ]

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)

    with pytest.warns(UserWarning, match='Secret collision'):
        name_map = mapping._secret_name_map

    assert 'my_secret' in name_map


def test_secret_names(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/MY_SECRET'

    mock_secret_client.list_secrets.return_value = [secret1]
    mock_secret_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    names = mapping._secret_names

    assert isinstance(names, list)
    assert 'MY_SECRET' in names


def test_secret_version_path(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mock_secret_client.secret_version_path.return_value = (
        'projects/test-project/secrets/MY_SECRET/versions/latest'
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    path = mapping._secret_version_path('MY_SECRET', 'latest')

    mock_secret_client.secret_version_path.assert_called_once_with('test-project', 'MY_SECRET', 'latest')
    assert path == 'projects/test-project/secrets/MY_SECRET/versions/latest'


def test_get_secret_value_success(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'secret-value'
    mock_secret_client.access_secret_version.return_value = mock_response
    mock_secret_client.secret_version_path.return_value = (
        'projects/test-project/secrets/MY_SECRET/versions/latest'
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    value = mapping._get_secret_value('MY_SECRET')

    assert value == 'secret-value'


def test_get_secret_value_exception_returns_none(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mock_secret_client.access_secret_version.side_effect = Exception('Not found')
    mock_secret_client.secret_version_path.return_value = (
        'projects/test-project/secrets/MY_SECRET/versions/latest'
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    value = mapping._get_secret_value('MY_SECRET')

    assert value is None


def test_getitem_from_loaded_secrets(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    mapping._loaded_secrets['MY_SECRET'] = 'cached-value'

    result = mapping['MY_SECRET']
    assert result == 'cached-value'


def test_getitem_loads_secret_from_gcp(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/MY_SECRET'
    mock_secret_client.list_secrets.return_value = [secret1]
    mock_secret_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'fetched-value'
    mock_secret_client.access_secret_version.return_value = mock_response
    mock_secret_client.secret_version_path.return_value = (
        'projects/test-project/secrets/MY_SECRET/versions/latest'
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)
    result = mapping['MY_SECRET']

    assert result == 'fetched-value'
    assert mapping._loaded_secrets['MY_SECRET'] == 'fetched-value'


def test_getitem_case_insensitive_lookup(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/MY_SECRET'
    mock_secret_client.list_secrets.return_value = [secret1]
    mock_secret_client.parse_secret_path.return_value = {'secret': 'MY_SECRET'}

    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'fetched-value'
    mock_secret_client.access_secret_version.return_value = mock_response
    mock_secret_client.secret_version_path.return_value = (
        'projects/test-project/secrets/MY_SECRET/versions/latest'
    )

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=False)
    # Use lowercase key to trigger case-insensitive lookup path
    result = mapping['my_secret']

    assert result == 'fetched-value'


def test_getitem_key_not_found_raises(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    mock_secret_client.list_secrets.return_value = []

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    with pytest.raises(KeyError):
        mapping['NONEXISTENT']


def test_len(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/SECRET_A'
    secret2 = MagicMock()
    secret2.name = 'projects/test-project/secrets/SECRET_B'

    mock_secret_client.list_secrets.return_value = [secret1, secret2]
    mock_secret_client.parse_secret_path.side_effect = [
        {'secret': 'SECRET_A'},
        {'secret': 'SECRET_B'},
    ]

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    assert len(mapping) == 2


def test_iter(mock_secret_client):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerMapping

    secret1 = MagicMock()
    secret1.name = 'projects/test-project/secrets/SECRET_A'

    mock_secret_client.list_secrets.return_value = [secret1]
    mock_secret_client.parse_secret_path.return_value = {'secret': 'SECRET_A'}

    mapping = GoogleSecretManagerMapping(mock_secret_client, 'test-project', case_sensitive=True)

    names = list(mapping)
    assert 'SECRET_A' in names


# ---- Tests for GoogleSecretManagerSettingsSource ----


@pytest.fixture
def patched_gcp_module():
    """Patch the gcp module's globals directly for testing GoogleSecretManagerSettingsSource."""
    import pydantic_settings.sources.providers.gcp as gcp_module

    mock_credentials_cls = MagicMock(name='Credentials')
    mock_smc_cls = MagicMock(name='SecretManagerServiceClient')
    mock_auth_default = MagicMock(name='google_auth_default')

    with (
        patch.object(gcp_module, 'Credentials', mock_credentials_cls),
        patch.object(gcp_module, 'SecretManagerServiceClient', mock_smc_cls),
        patch.object(gcp_module, 'google_auth_default', mock_auth_default),
    ):
        yield {
            'gcp_module': gcp_module,
            'Credentials': mock_credentials_cls,
            'SecretManagerServiceClient': mock_smc_cls,
            'google_auth_default': mock_auth_default,
        }


def _make_mock_secret_client_for_settings():
    """Create a mock SecretManagerServiceClient suitable for settings tests."""
    client = MagicMock(name='secret_client_for_settings')
    client.common_project_path.return_value = 'projects/test-project'
    client.list_secrets.return_value = []
    return client


def test_settings_source_init_with_explicit_credentials_and_project(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    assert source._project_id == 'my-project'
    assert source._credentials is mock_creds
    assert source._secret_client is mock_client


def test_settings_source_init_uses_google_auth_default_when_no_creds(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_auth_default = patched_gcp_module['google_auth_default']
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, 'auto-project')

    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        secret_client=mock_client,
    )

    assert source._project_id == 'auto-project'
    assert source._credentials is mock_creds


def test_settings_source_init_raises_if_project_id_not_string(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_auth_default = patched_gcp_module['google_auth_default']
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, None)  # project_id is None

    mock_client = _make_mock_secret_client_for_settings()

    with pytest.raises(AttributeError, match='project_id is required'):
        GoogleSecretManagerSettingsSource(
            SimpleSettings,
            secret_client=mock_client,
        )


def test_settings_source_init_creates_client_if_not_provided(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_auth_default = patched_gcp_module['google_auth_default']
    mock_smc_cls = patched_gcp_module['SecretManagerServiceClient']
    mock_creds = MagicMock()
    mock_auth_default.return_value = (mock_creds, 'auto-project')

    mock_instance = _make_mock_secret_client_for_settings()
    mock_smc_cls.return_value = mock_instance

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
    )

    mock_smc_cls.assert_called_once_with(credentials=mock_creds)
    assert source._secret_client is mock_instance


def test_settings_source_init_only_credentials_provided(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_auth_default = patched_gcp_module['google_auth_default']
    mock_creds_from_arg = MagicMock()
    mock_creds_from_default = MagicMock()
    mock_auth_default.return_value = (mock_creds_from_default, 'auto-project')

    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds_from_arg,
        secret_client=mock_client,
    )

    # project_id should come from default, credentials from arg
    assert source._project_id == 'auto-project'
    assert source._credentials is mock_creds_from_arg


def test_settings_source_repr(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    repr_str = repr(source)
    assert 'GoogleSecretManagerSettingsSource' in repr_str
    assert 'my-project' in repr_str


def test_load_env_vars_returns_mapping(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import (
        GoogleSecretManagerMapping,
        GoogleSecretManagerSettingsSource,
    )

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    assert isinstance(source.env_vars, GoogleSecretManagerMapping)


def test_get_field_value_no_secret_version_falls_back_to_super(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    secret1 = MagicMock()
    secret1.name = 'projects/my-project/secrets/my_field'
    mock_client.list_secrets.return_value = [secret1]
    mock_client.parse_secret_path.return_value = {'secret': 'my_field'}
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'secret-val'
    mock_client.access_secret_version.return_value = mock_response
    mock_client.secret_version_path.return_value = (
        'projects/my-project/secrets/my_field/versions/latest'
    )

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    field_info = SimpleSettings.model_fields['my_field']
    val, key, is_complex = source.get_field_value(field_info, 'my_field')

    assert val == 'secret-val'


def test_get_field_value_with_secret_version_found(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    class VersionedSettings(BaseSettings):
        my_field: Annotated[str, SecretVersion('2')] = 'default'

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    secret1 = MagicMock()
    secret1.name = 'projects/my-project/secrets/my_field'
    mock_client.list_secrets.return_value = [secret1]
    mock_client.parse_secret_path.return_value = {'secret': 'my_field'}
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'versioned-value'
    mock_client.access_secret_version.return_value = mock_response
    mock_client.secret_version_path.return_value = (
        'projects/my-project/secrets/my_field/versions/2'
    )

    source = GoogleSecretManagerSettingsSource(
        VersionedSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    field_info = VersionedSettings.model_fields['my_field']
    val, key, is_complex = source.get_field_value(field_info, 'my_field')

    assert val == 'versioned-value'


def test_get_field_value_with_secret_version_not_found_returns_none(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    class VersionedSettings(BaseSettings):
        my_field: Annotated[str, SecretVersion('99')] = 'default'

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    mock_client.list_secrets.return_value = []

    source = GoogleSecretManagerSettingsSource(
        VersionedSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    field_info = VersionedSettings.model_fields['my_field']
    val, key, is_complex = source.get_field_value(field_info, 'my_field')

    assert val is None
    assert key == 'my_field'
    assert is_complex is False


def test_get_field_value_with_secret_version_populate_by_name(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    class VersionedSettingsByName(BaseSettings):
        model_config = {'populate_by_name': True}
        my_field: Annotated[str, Field(alias='my_alias'), SecretVersion('1')] = 'default'

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    secret1 = MagicMock()
    secret1.name = 'projects/my-project/secrets/my_alias'
    mock_client.list_secrets.return_value = [secret1]
    mock_client.parse_secret_path.return_value = {'secret': 'my_alias'}
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'alias-value'
    mock_client.access_secret_version.return_value = mock_response
    mock_client.secret_version_path.return_value = (
        'projects/my-project/secrets/my_alias/versions/1'
    )

    source = GoogleSecretManagerSettingsSource(
        VersionedSettingsByName,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    field_info = VersionedSettingsByName.model_fields['my_field']
    val, key, is_complex = source.get_field_value(field_info, 'my_field')

    assert val == 'alias-value'
    assert key == 'my_field'


def test_get_field_value_populate_by_name_no_version(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    class PopulateByNameSettings(BaseSettings):
        model_config = {'populate_by_name': True}
        my_field: str = Field(default='default', alias='my_alias')

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    secret1 = MagicMock()
    secret1.name = 'projects/my-project/secrets/my_alias'
    mock_client.list_secrets.return_value = [secret1]
    mock_client.parse_secret_path.return_value = {'secret': 'my_alias'}
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = 'alias-value'
    mock_client.access_secret_version.return_value = mock_response
    mock_client.secret_version_path.return_value = (
        'projects/my-project/secrets/my_alias/versions/latest'
    )

    source = GoogleSecretManagerSettingsSource(
        PopulateByNameSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )

    field_info = PopulateByNameSettings.model_fields['my_field']
    val, key, is_complex = source.get_field_value(field_info, 'my_field')

    assert val == 'alias-value'
    assert key == 'my_field'


def test_settings_source_init_with_env_prefix(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds,
        project_id='my-project',
        env_prefix='APP_',
        secret_client=mock_client,
    )

    assert source.env_prefix == 'APP_'


def test_settings_source_case_insensitive(patched_gcp_module):
    from pydantic_settings.sources.providers.gcp import GoogleSecretManagerSettingsSource

    mock_creds = MagicMock()
    mock_client = _make_mock_secret_client_for_settings()

    source = GoogleSecretManagerSettingsSource(
        SimpleSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
        case_sensitive=False,
    )

    assert source.case_sensitive is False
