"""Tests for the GCP Secret Manager settings source provider."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.providers.gcp import (
    GoogleSecretManagerMapping,
    GoogleSecretManagerSettingsSource,
    import_gcp_secret_manager,
)
from pydantic_settings.sources.types import SecretVersion


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_secret_obj(name: str) -> MagicMock:
    """Create a mock secret object returned by list_secrets."""
    secret = MagicMock()
    secret.name = name
    return secret


def _mock_secret_client(secrets: dict[str, str | None] | None = None, secret_names: list[str] | None = None):
    """Return a mock SecretManagerServiceClient.

    Args:
        secrets: mapping of secret-name -> value (for access_secret_version).
        secret_names: list of secret names returned by list_secrets.
    """
    if secrets is None:
        secrets = {}
    if secret_names is None:
        secret_names = list(secrets.keys())

    client = MagicMock()

    # common_project_path
    client.common_project_path.return_value = 'projects/my-project'

    # list_secrets
    secret_objs = [_make_secret_obj(f'projects/my-project/secrets/{n}') for n in secret_names]
    client.list_secrets.return_value = iter(secret_objs)

    # parse_secret_path
    def _parse(name: str) -> dict[str, str]:
        parts = name.split('/')
        return {'secret': parts[-1] if parts else ''}

    client.parse_secret_path.side_effect = _parse

    # secret_version_path
    def _version_path(project_id: str, secret_name: str, version: str) -> str:
        return f'projects/{project_id}/secrets/{secret_name}/versions/{version}'

    client.secret_version_path.side_effect = _version_path

    # access_secret_version
    def _access(name: str) -> MagicMock:
        # extract secret name from path like projects/my-project/secrets/MY_SECRET/versions/latest
        parts = name.split('/')
        secret_name = parts[3] if len(parts) > 3 else ''
        if secret_name in secrets and secrets[secret_name] is not None:
            resp = MagicMock()
            resp.payload.data.decode.return_value = secrets[secret_name]
            return resp
        raise Exception(f'Secret {secret_name} not found')

    client.access_secret_version.side_effect = _access

    return client


@pytest.fixture
def mock_client():
    """Fixture providing a simple mock client with two secrets."""
    return _mock_secret_client(
        secrets={'MY_SECRET': 'secret_value', 'ANOTHER_SECRET': 'another_value'},
    )


# ---------------------------------------------------------------------------
# import_gcp_secret_manager
# ---------------------------------------------------------------------------


class TestImportGcpSecretManager:
    def test_import_sets_globals(self, mocker):
        """Test that import_gcp_secret_manager sets module-level globals."""
        mock_creds = MagicMock()
        mock_client_cls = MagicMock()
        mock_default = MagicMock()

        mocker.patch.dict(
            'sys.modules',
            {
                'google': MagicMock(),
                'google.auth': MagicMock(default=mock_default),
                'google.auth.credentials': MagicMock(Credentials=mock_creds),
                'google.cloud': MagicMock(),
                'google.cloud.secretmanager': MagicMock(SecretManagerServiceClient=mock_client_cls),
            },
        )

        import pydantic_settings.sources.providers.gcp as gcp_mod

        # Reset globals to simulate TYPE_CHECKING-only state
        original_smc = gcp_mod.SecretManagerServiceClient
        original_creds = gcp_mod.Credentials
        original_default = gcp_mod.google_auth_default

        gcp_mod.SecretManagerServiceClient = None
        gcp_mod.Credentials = None
        gcp_mod.google_auth_default = None

        try:
            import_gcp_secret_manager()
            # After import, globals should be set
            assert gcp_mod.Credentials is not None
            assert gcp_mod.SecretManagerServiceClient is not None
            assert gcp_mod.google_auth_default is not None
        finally:
            gcp_mod.SecretManagerServiceClient = original_smc
            gcp_mod.Credentials = original_creds
            gcp_mod.google_auth_default = original_default


# ---------------------------------------------------------------------------
# GoogleSecretManagerMapping
# ---------------------------------------------------------------------------


class TestGoogleSecretManagerMapping:
    def test_init(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        assert mapping._loaded_secrets == {}
        assert mapping._secret_client is mock_client
        assert mapping._project_id == 'my-project'
        assert mapping._case_sensitive is True

    def test_gcp_project_path(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        path = mapping._gcp_project_path
        assert path == 'projects/my-project'
        mock_client.common_project_path.assert_called_once_with('my-project')

    def test_secret_name_map_case_sensitive(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        name_map = mapping._secret_name_map
        assert 'MY_SECRET' in name_map
        assert 'ANOTHER_SECRET' in name_map
        assert name_map['MY_SECRET'] == 'MY_SECRET'
        assert name_map['ANOTHER_SECRET'] == 'ANOTHER_SECRET'

    def test_secret_name_map_case_insensitive(self):
        client = _mock_secret_client(
            secrets={'MySecret': 'val1', 'OTHER': 'val2'},
        )
        mapping = GoogleSecretManagerMapping(client, 'my-project', case_sensitive=False)
        name_map = mapping._secret_name_map
        # Original keys preserved
        assert 'MySecret' in name_map
        assert 'OTHER' in name_map
        # Lowercased keys also present
        assert 'mysecret' in name_map
        assert 'other' in name_map

    def test_secret_name_map_case_insensitive_collision(self):
        """When multiple secrets collide in lowercase, a warning is emitted."""
        client = _mock_secret_client(
            secrets={'MySecret': 'val1', 'mysecret': 'val2'},
            secret_names=['MySecret', 'mysecret'],
        )
        mapping = GoogleSecretManagerMapping(client, 'my-project', case_sensitive=False)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            name_map = mapping._secret_name_map
            assert len(w) == 1
            assert 'collision' in str(w[0].message).lower()
        # The winner should be the last after sort (deterministic)
        assert name_map['mysecret'] == 'mysecret'

    def test_select_case_insensitive_secret_single(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=False)
        result = mapping._select_case_insensitive_secret('test', ['TestSecret'])
        assert result == 'TestSecret'

    def test_select_case_insensitive_secret_multiple_warns(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=False)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = mapping._select_case_insensitive_secret('test', ['Test', 'TEST', 'test'])
            assert len(w) == 1
            assert 'collision' in str(w[0].message).lower()
        # sorted: ['TEST', 'Test', 'test'], winner = last = 'test'
        assert result == 'test'

    def test_secret_names(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        names = mapping._secret_names
        assert 'MY_SECRET' in names
        assert 'ANOTHER_SECRET' in names

    def test_secret_version_path(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        path = mapping._secret_version_path('MY_SECRET', 'latest')
        assert path == 'projects/my-project/secrets/MY_SECRET/versions/latest'

    def test_secret_version_path_custom(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        path = mapping._secret_version_path('MY_SECRET', '3')
        assert path == 'projects/my-project/secrets/MY_SECRET/versions/3'

    def test_get_secret_value_success(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        val = mapping._get_secret_value('MY_SECRET')
        assert val == 'secret_value'

    def test_get_secret_value_not_found(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        val = mapping._get_secret_value('NONEXISTENT')
        assert val is None

    def test_getitem_success(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        val = mapping['MY_SECRET']
        assert val == 'secret_value'

    def test_getitem_cached(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        # First access
        val1 = mapping['MY_SECRET']
        # Reset mock call count
        mock_client.access_secret_version.reset_mock()
        # Second access should use cache
        val2 = mapping['MY_SECRET']
        assert val1 == val2
        mock_client.access_secret_version.assert_not_called()

    def test_getitem_key_error(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        with pytest.raises(KeyError):
            mapping['NONEXISTENT']

    def test_getitem_case_insensitive_fallback(self):
        client = _mock_secret_client(secrets={'MySecret': 'the_value'})
        mapping = GoogleSecretManagerMapping(client, 'my-project', case_sensitive=False)
        # Access via lowercase key should find via case-insensitive fallback
        val = mapping['mysecret']
        assert val == 'the_value'

    def test_len(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        assert len(mapping) == 2

    def test_iter(self, mock_client):
        mapping = GoogleSecretManagerMapping(mock_client, 'my-project', case_sensitive=True)
        keys = list(mapping)
        assert 'MY_SECRET' in keys
        assert 'ANOTHER_SECRET' in keys


# ---------------------------------------------------------------------------
# GoogleSecretManagerSettingsSource
# ---------------------------------------------------------------------------


class _MockCredentials:
    """Minimal mock credentials for testing."""
    pass


class TestGoogleSecretManagerSettingsSource:
    @pytest.fixture(autouse=True)
    def patch_gcp_globals(self, mocker):
        """Patch the module-level GCP globals so imports work without google-cloud."""
        import pydantic_settings.sources.providers.gcp as gcp_mod

        self._original_smc = gcp_mod.SecretManagerServiceClient
        self._original_creds = gcp_mod.Credentials
        self._original_default = gcp_mod.google_auth_default

        gcp_mod.SecretManagerServiceClient = MagicMock
        gcp_mod.Credentials = _MockCredentials
        gcp_mod.google_auth_default = MagicMock(return_value=(_MockCredentials(), 'default-project'))

        yield

        gcp_mod.SecretManagerServiceClient = self._original_smc
        gcp_mod.Credentials = self._original_creds
        gcp_mod.google_auth_default = self._original_default

    def _make_settings_cls(self, **config_overrides):
        """Create a simple BaseSettings subclass for testing."""
        config = {'extra': 'ignore'}
        config.update(config_overrides)

        class TestSettings(BaseSettings):
            model_config = config
            my_secret: str = 'default'

        return TestSettings

    def test_init_with_explicit_credentials_and_project(self):
        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='explicit-project',
            secret_client=client,
        )
        assert source._project_id == 'explicit-project'
        assert source._secret_client is client

    def test_init_with_default_credentials(self):
        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            secret_client=client,
        )
        # Should use defaults from google_auth_default
        assert source._project_id == 'default-project'
        assert isinstance(source._credentials, _MockCredentials)

    def test_init_missing_project_id_raises(self):
        import pydantic_settings.sources.providers.gcp as gcp_mod

        gcp_mod.google_auth_default = MagicMock(return_value=(_MockCredentials(), None))
        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        with pytest.raises(AttributeError, match='project_id is required'):
            GoogleSecretManagerSettingsSource(
                settings_cls,
                secret_client=client,
            )

    def test_init_creates_client_when_not_provided(self):
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
        )
        assert source._project_id == 'test-project'
        # A client should have been created (it will be a MagicMock since SecretManagerServiceClient is MagicMock)
        assert source._secret_client is not None

    def test_init_calls_import_when_globals_are_none(self, mocker):
        import pydantic_settings.sources.providers.gcp as gcp_mod

        gcp_mod.SecretManagerServiceClient = None
        mock_import = mocker.patch(
            'pydantic_settings.sources.providers.gcp.import_gcp_secret_manager',
        )
        # After import_gcp_secret_manager is called, globals should be set
        def _set_globals():
            gcp_mod.SecretManagerServiceClient = MagicMock
            gcp_mod.Credentials = _MockCredentials
            gcp_mod.google_auth_default = MagicMock(return_value=(_MockCredentials(), 'proj'))

        mock_import.side_effect = _set_globals

        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
        )
        mock_import.assert_called_once()

    def test_load_env_vars_returns_mapping(self):
        client = _mock_secret_client(secrets={'MY_SECRET': 'val'})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
        )
        assert isinstance(source.env_vars, GoogleSecretManagerMapping)

    def test_repr(self):
        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
        )
        r = repr(source)
        assert 'GoogleSecretManagerSettingsSource' in r
        assert 'test-project' in r

    def test_get_field_value_basic(self):
        client = _mock_secret_client(secrets={'my_secret': 'found_value'})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            case_sensitive=True,
        )
        field_info = settings_cls.model_fields['my_secret']
        val, key, is_complex = source.get_field_value(field_info, 'my_secret')
        assert val == 'found_value'

    def test_get_field_value_with_secret_version(self):
        client = _mock_secret_client(secrets={'my_secret': 'versioned_value'})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            case_sensitive=True,
        )

        # Create a FieldInfo with SecretVersion metadata
        field_info = FieldInfo(annotation=str, metadata=[SecretVersion('5')])
        val, key, is_complex = source.get_field_value(field_info, 'my_secret')
        assert val == 'versioned_value'

    def test_get_field_value_with_secret_version_not_found(self):
        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            case_sensitive=True,
        )

        field_info = FieldInfo(annotation=str, metadata=[SecretVersion('5')])
        val, key, is_complex = source.get_field_value(field_info, 'my_secret')
        assert val is None

    def test_get_field_value_with_populate_by_name(self):
        client = _mock_secret_client(secrets={'my_secret': 'pop_value'})

        class PopSettings(BaseSettings):
            model_config = {'extra': 'ignore', 'populate_by_name': True}
            my_secret: str = 'default'

        source = GoogleSecretManagerSettingsSource(
            PopSettings,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            case_sensitive=True,
        )
        field_info = PopSettings.model_fields['my_secret']
        val, key, is_complex = source.get_field_value(field_info, 'my_secret')
        assert val == 'pop_value'
        assert key == 'my_secret'

    def test_get_field_value_with_secret_version_and_populate_by_name(self):
        client = _mock_secret_client(secrets={'my_secret': 'ver_pop_value'})

        class PopSettings(BaseSettings):
            model_config = {'extra': 'ignore', 'populate_by_name': True}
            my_secret: str = 'default'

        source = GoogleSecretManagerSettingsSource(
            PopSettings,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            case_sensitive=True,
        )
        field_info = FieldInfo(annotation=str, metadata=[SecretVersion('2')])
        val, key, is_complex = source.get_field_value(field_info, 'my_secret')
        assert val == 'ver_pop_value'
        assert key == 'my_secret'

    def test_get_field_value_case_insensitive_with_version(self):
        client = _mock_secret_client(secrets={'MySecret': 'ci_value'})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            case_sensitive=False,
        )
        field_info = FieldInfo(annotation=str, metadata=[SecretVersion('1')])
        val, key, is_complex = source.get_field_value(field_info, 'mysecret')
        assert val == 'ci_value'

    def test_init_with_env_prefix(self):
        client = _mock_secret_client(secrets={})
        settings_cls = self._make_settings_cls()
        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=_MockCredentials(),
            project_id='test-project',
            secret_client=client,
            env_prefix='APP_',
        )
        assert source.env_prefix == 'APP_'
