from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import pydantic_settings.sources.providers.gcp as gcp_module
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.env import EnvSettingsSource
from pydantic_settings.sources.providers.gcp import (
    GoogleSecretManagerMapping,
    GoogleSecretManagerSettingsSource,
    import_gcp_secret_manager,
)
from pydantic_settings.sources.types import SecretVersion


# ---- Helpers ----


def _make_secret(name: str, project_id: str = 'test-project') -> MagicMock:
    s = MagicMock()
    s.name = f'projects/{project_id}/secrets/{name}'
    return s


def _make_client(*secret_names: str) -> MagicMock:
    client = MagicMock()
    client.common_project_path.return_value = 'projects/test-project'
    client.secret_version_path.side_effect = lambda project, secret, version: (
        f'projects/{project}/secrets/{secret}/versions/{version}'
    )
    client.parse_secret_path.side_effect = lambda name: {'secret': name.split('/')[-1]}
    client.list_secrets.return_value = [_make_secret(n) for n in secret_names]
    return client


# ---- Fixtures ----


@pytest.fixture
def patched_gcp_globals(mocker):
    """Patch gcp module globals to non-None so import_gcp_secret_manager is not called."""
    mock_creds_cls = MagicMock()
    mock_client_cls = MagicMock()
    mock_auth_default = MagicMock()
    mocker.patch.object(gcp_module, 'Credentials', mock_creds_cls)
    mocker.patch.object(gcp_module, 'SecretManagerServiceClient', mock_client_cls)
    mocker.patch.object(gcp_module, 'google_auth_default', mock_auth_default)
    return {
        'Credentials': mock_creds_cls,
        'SecretManagerServiceClient': mock_client_cls,
        'google_auth_default': mock_auth_default,
    }


class SampleSettings(BaseSettings):
    my_secret: str = 'default'
    model_config = {'extra': 'ignore'}


# ---- import_gcp_secret_manager ----


def test_import_gcp_secret_manager_sets_globals(mocker):
    mock_auth_default = MagicMock()
    mock_credentials_cls = MagicMock()
    mock_client_cls = MagicMock()

    mock_google_auth = MagicMock()
    mock_google_auth.default = mock_auth_default
    mock_google_auth_creds = MagicMock()
    mock_google_auth_creds.Credentials = mock_credentials_cls
    mock_sm = MagicMock()
    mock_sm.SecretManagerServiceClient = mock_client_cls

    mocker.patch.dict(
        'sys.modules',
        {
            'google': MagicMock(),
            'google.auth': mock_google_auth,
            'google.auth.credentials': mock_google_auth_creds,
            'google.cloud': MagicMock(),
            'google.cloud.secretmanager': mock_sm,
        },
    )

    orig_creds = gcp_module.Credentials
    orig_client = gcp_module.SecretManagerServiceClient
    orig_auth = gcp_module.google_auth_default
    gcp_module.Credentials = None  # type: ignore[assignment]
    gcp_module.SecretManagerServiceClient = None  # type: ignore[assignment]
    gcp_module.google_auth_default = None  # type: ignore[assignment]
    try:
        import_gcp_secret_manager()
        assert gcp_module.google_auth_default is mock_auth_default
        assert gcp_module.Credentials is mock_credentials_cls
        assert gcp_module.SecretManagerServiceClient is mock_client_cls
    finally:
        gcp_module.Credentials = orig_creds
        gcp_module.SecretManagerServiceClient = orig_client
        gcp_module.google_auth_default = orig_auth


# ---- GoogleSecretManagerMapping ----


def test_mapping_init():
    client = _make_client()
    m = GoogleSecretManagerMapping(client, 'my-project', case_sensitive=True)
    assert m._secret_client is client
    assert m._project_id == 'my-project'
    assert m._case_sensitive is True
    assert m._loaded_secrets == {}


def test_mapping_gcp_project_path():
    client = _make_client()
    client.common_project_path.return_value = 'projects/my-project'
    m = GoogleSecretManagerMapping(client, 'my-project', case_sensitive=True)
    assert m._gcp_project_path == 'projects/my-project'
    client.common_project_path.assert_called_once_with('my-project')


def test_mapping_select_case_insensitive_single_candidate():
    m = GoogleSecretManagerMapping(_make_client(), 'test-project', case_sensitive=False)
    result = m._select_case_insensitive_secret('mysecret', ['MY_SECRET'])
    assert result == 'MY_SECRET'


def test_mapping_select_case_insensitive_multiple_candidates():
    m = GoogleSecretManagerMapping(_make_client(), 'test-project', case_sensitive=False)
    with pytest.warns(UserWarning, match='Secret collision'):
        result = m._select_case_insensitive_secret('my_secret', ['MY_SECRET', 'my_secret'])
    # sorted: ['MY_SECRET', 'my_secret'], last = 'my_secret'
    assert result == 'my_secret'


def test_mapping_secret_name_map_case_sensitive():
    client = _make_client('SECRET_A', 'secret_b')
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    name_map = m._secret_name_map
    assert name_map == {'SECRET_A': 'SECRET_A', 'secret_b': 'secret_b'}


def test_mapping_secret_name_map_case_insensitive_no_collision():
    client = _make_client('SECRET_A', 'SECRET_B')
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)
    name_map = m._secret_name_map
    assert name_map['SECRET_A'] == 'SECRET_A'
    assert name_map['SECRET_B'] == 'SECRET_B'
    assert name_map['secret_a'] == 'SECRET_A'
    assert name_map['secret_b'] == 'SECRET_B'


def test_mapping_secret_name_map_case_insensitive_with_collision():
    client = _make_client('MY_SECRET', 'my_secret')
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)
    with pytest.warns(UserWarning, match='Secret collision'):
        name_map = m._secret_name_map
    assert 'MY_SECRET' in name_map
    assert 'my_secret' in name_map


def test_mapping_secret_names():
    client = _make_client('A', 'B', 'C')
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    assert set(m._secret_names) == {'A', 'B', 'C'}


def test_mapping_secret_version_path():
    client = _make_client()
    client.secret_version_path.return_value = 'projects/test-project/secrets/MY_SECRET/versions/v1'
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    path = m._secret_version_path('MY_SECRET', 'v1')
    client.secret_version_path.assert_called_once_with('test-project', 'MY_SECRET', 'v1')
    assert path == 'projects/test-project/secrets/MY_SECRET/versions/v1'


def test_mapping_get_secret_value_success():
    client = _make_client()
    client.secret_version_path.return_value = 'some/path'
    response = MagicMock()
    response.payload.data.decode.return_value = 'super-secret'
    client.access_secret_version.return_value = response
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    assert m._get_secret_value('MY_SECRET', 'latest') == 'super-secret'
    response.payload.data.decode.assert_called_once_with('UTF-8')


def test_mapping_get_secret_value_exception_returns_none():
    client = _make_client()
    client.secret_version_path.return_value = 'some/path'
    client.access_secret_version.side_effect = Exception('not found')
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    assert m._get_secret_value('MISSING', 'latest') is None


def test_mapping_getitem_cache_hit():
    client = _make_client()
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    m._loaded_secrets['MY_SECRET'] = 'cached'
    assert m['MY_SECRET'] == 'cached'
    client.access_secret_version.assert_not_called()


def test_mapping_getitem_cache_miss_case_sensitive():
    client = _make_client('MY_SECRET')
    client.secret_version_path.return_value = 'some/path'
    response = MagicMock()
    response.payload.data.decode.return_value = 'fetched'
    client.access_secret_version.return_value = response
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    assert m['MY_SECRET'] == 'fetched'
    assert m._loaded_secrets['MY_SECRET'] == 'fetched'


def test_mapping_getitem_case_insensitive_lowercase_key():
    client = _make_client('MY_SECRET')
    client.secret_version_path.return_value = 'some/path'
    response = MagicMock()
    response.payload.data.decode.return_value = 'insensitive-value'
    client.access_secret_version.return_value = response
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=False)
    assert m['my_secret'] == 'insensitive-value'


def test_mapping_getitem_key_error():
    client = _make_client()
    m = GoogleSecretManagerMapping(client, 'test-project', case_sensitive=True)
    with pytest.raises(KeyError):
        _ = m['NONEXISTENT']


def test_mapping_len():
    m = GoogleSecretManagerMapping(_make_client('A', 'B', 'C'), 'test-project', case_sensitive=True)
    assert len(m) == 3


def test_mapping_iter():
    m = GoogleSecretManagerMapping(_make_client('A', 'B'), 'test-project', case_sensitive=True)
    assert set(m) == {'A', 'B'}


# ---- GoogleSecretManagerSettingsSource ----


def test_settings_source_init_with_credentials_and_project(patched_gcp_globals):
    mock_creds = MagicMock()
    mock_client = _make_client()
    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=mock_creds,
        project_id='my-project',
        secret_client=mock_client,
    )
    assert source._credentials is mock_creds
    assert source._project_id == 'my-project'
    assert source._secret_client is mock_client


def test_settings_source_init_uses_google_auth_default(patched_gcp_globals):
    mock_creds = MagicMock()
    mock_client = _make_client()
    patched_gcp_globals['google_auth_default'].return_value = (mock_creds, 'auto-project')

    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        secret_client=mock_client,
    )
    assert source._credentials is mock_creds
    assert source._project_id == 'auto-project'


def test_settings_source_init_only_missing_project_id(patched_gcp_globals):
    mock_creds_arg = MagicMock()
    mock_client = _make_client()
    patched_gcp_globals['google_auth_default'].return_value = (MagicMock(), 'inferred-project')

    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=mock_creds_arg,
        secret_client=mock_client,
    )
    assert source._project_id == 'inferred-project'
    assert source._credentials is mock_creds_arg


def test_settings_source_init_project_id_not_string_raises(patched_gcp_globals):
    patched_gcp_globals['google_auth_default'].return_value = (MagicMock(), 42)

    with pytest.raises(AttributeError, match='project_id is required'):
        GoogleSecretManagerSettingsSource(
            SampleSettings,
        )


def test_settings_source_init_creates_client_if_not_given(patched_gcp_globals):
    mock_creds = MagicMock()
    mock_client_instance = _make_client()
    patched_gcp_globals['SecretManagerServiceClient'].return_value = mock_client_instance

    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=mock_creds,
        project_id='test-project',
    )
    patched_gcp_globals['SecretManagerServiceClient'].assert_called_once_with(credentials=mock_creds)
    assert source._secret_client is mock_client_instance


def test_settings_source_repr(patched_gcp_globals):
    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=MagicMock(),
        project_id='my-project',
        secret_client=_make_client(),
    )
    r = repr(source)
    assert 'GoogleSecretManagerSettingsSource' in r
    assert 'my-project' in r


def test_settings_source_load_env_vars(patched_gcp_globals):
    mock_client = _make_client()
    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=MagicMock(),
        project_id='my-project',
        secret_client=mock_client,
    )
    env_vars = source._load_env_vars()
    assert isinstance(env_vars, GoogleSecretManagerMapping)
    assert env_vars._project_id == 'my-project'
    assert env_vars._secret_client is mock_client


def test_settings_source_get_field_value_with_version_found(patched_gcp_globals, mocker):
    client = _make_client('my_secret')
    response = MagicMock()
    response.payload.data.decode.return_value = 'versioned-value'
    client.access_secret_version.return_value = response

    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=MagicMock(),
        project_id='test-project',
        secret_client=client,
    )
    mocker.patch.object(source, '_extract_field_info', return_value=[('my_secret', 'my_secret', False)])

    field = MagicMock()
    field.metadata = [SecretVersion('42')]

    val, key, is_complex = source.get_field_value(field, 'my_secret')
    assert val == 'versioned-value'
    assert is_complex is False


def test_settings_source_get_field_value_with_version_not_found(patched_gcp_globals, mocker):
    client = _make_client()  # no secrets
    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=MagicMock(),
        project_id='test-project',
        secret_client=client,
    )
    mocker.patch.object(source, '_extract_field_info', return_value=[('my_secret', 'my_secret', False)])

    field = MagicMock()
    field.metadata = [SecretVersion('42')]

    val, key, is_complex = source.get_field_value(field, 'my_secret')
    assert val is None
    assert key == 'my_secret'
    assert is_complex is False


def test_settings_source_get_field_value_no_version_fallback_to_super(patched_gcp_globals, mocker):
    client = _make_client()
    source = GoogleSecretManagerSettingsSource(
        SampleSettings,
        credentials=MagicMock(),
        project_id='test-project',
        secret_client=client,
    )
    mocker.patch.object(
        EnvSettingsSource,
        'get_field_value',
        return_value=('super-val', 'my_secret', False),
    )

    field = MagicMock()
    field.metadata = []

    val, key, is_complex = source.get_field_value(field, 'my_secret')
    assert val == 'super-val'
    assert key == 'my_secret'


def test_settings_source_get_field_value_populate_by_name_with_version(patched_gcp_globals, mocker):
    client = _make_client('my_secret')
    response = MagicMock()
    response.payload.data.decode.return_value = 'value'
    client.access_secret_version.return_value = response

    class NamedSettings(BaseSettings):
        my_secret: str = 'default'
        model_config = {'extra': 'ignore', 'populate_by_name': True}

    source = GoogleSecretManagerSettingsSource(
        NamedSettings,
        credentials=MagicMock(),
        project_id='test-project',
        secret_client=client,
    )
    mocker.patch.object(source, '_extract_field_info', return_value=[('alias_key', 'my_secret', False)])

    field = MagicMock()
    field.metadata = [SecretVersion('1')]

    val, key, is_complex = source.get_field_value(field, 'my_secret')
    assert key == 'my_secret'  # field_name, not alias_key
    assert val == 'value'


def test_settings_source_get_field_value_populate_by_name_no_version(patched_gcp_globals, mocker):
    client = _make_client()

    class NamedSettings(BaseSettings):
        my_secret: str = 'default'
        model_config = {'extra': 'ignore', 'populate_by_name': True}

    source = GoogleSecretManagerSettingsSource(
        NamedSettings,
        credentials=MagicMock(),
        project_id='test-project',
        secret_client=client,
    )
    mocker.patch.object(
        EnvSettingsSource,
        'get_field_value',
        return_value=('some-val', 'alias_key', False),
    )

    field = MagicMock()
    field.metadata = []

    val, key, is_complex = source.get_field_value(field, 'my_secret')
    assert val == 'some-val'
    assert key == 'my_secret'  # populate_by_name forces field_name
