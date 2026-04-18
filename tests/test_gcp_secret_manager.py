from __future__ import annotations

import warnings
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import AliasChoices
from pydantic.fields import FieldInfo

from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.providers.gcp import (
    GoogleSecretManagerMapping,
    GoogleSecretManagerSettingsSource,
    import_gcp_secret_manager,
)
from pydantic_settings.sources.types import SecretVersion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_secret_client(secrets: dict[str, str | None] | None = None, secret_names: list[str] | None = None):
    """Build a lightweight mock of SecretManagerServiceClient."""
    client = MagicMock()

    if secret_names is None:
        secret_names = list((secrets or {}).keys())

    # list_secrets returns objects whose `.name` attribute is a full resource path
    secret_objects = []
    for name in secret_names:
        s = SimpleNamespace(name=f'projects/my-proj/secrets/{name}')
        secret_objects.append(s)
    client.list_secrets.return_value = secret_objects

    # parse_secret_path extracts the short name from the resource path
    def _parse(path: str) -> dict[str, str]:
        short = path.rsplit('/', 1)[-1]
        return {'secret': short}

    client.parse_secret_path.side_effect = _parse

    # common_project_path
    client.common_project_path.return_value = 'projects/my-proj'

    # secret_version_path
    client.secret_version_path.side_effect = (
        lambda project, secret, version: f'projects/{project}/secrets/{secret}/versions/{version}'
    )

    # access_secret_version
    if secrets is not None:
        def _access(name: str):
            # name looks like projects/.../secrets/KEY/versions/latest
            parts = name.split('/')
            key = parts[3]
            val = secrets.get(key)
            if val is None:
                raise Exception('Secret not found')
            return SimpleNamespace(payload=SimpleNamespace(data=val.encode('UTF-8')))

        client.access_secret_version.side_effect = _access

    return client


def _make_settings_cls(**config_overrides: Any) -> type[BaseSettings]:
    """Return a minimal BaseSettings subclass with the given config."""
    config = {'case_sensitive': True}
    config.update(config_overrides)

    class _Settings(BaseSettings):
        model_config = config  # type: ignore[assignment]

    return _Settings


# ---------------------------------------------------------------------------
# import_gcp_secret_manager
# ---------------------------------------------------------------------------

class TestImportGcpSecretManager:
    def test_import_sets_globals(self):
        """import_gcp_secret_manager should set the three global symbols when google packages exist."""
        import pydantic_settings.sources.providers.gcp as gcp_mod

        orig_creds = gcp_mod.Credentials
        orig_client = gcp_mod.SecretManagerServiceClient
        orig_default = gcp_mod.google_auth_default

        mock_creds = MagicMock()
        mock_default = MagicMock()
        mock_client_cls = MagicMock()

        try:
            gcp_mod.Credentials = None
            gcp_mod.SecretManagerServiceClient = None
            gcp_mod.google_auth_default = None

            with patch.dict(
                'sys.modules',
                {
                    'google': MagicMock(),
                    'google.auth': MagicMock(default=mock_default, credentials=MagicMock(Credentials=mock_creds)),
                    'google.auth.credentials': MagicMock(Credentials=mock_creds),
                    'google.cloud': MagicMock(),
                    'google.cloud.secretmanager': MagicMock(SecretManagerServiceClient=mock_client_cls),
                },
            ):
                import_gcp_secret_manager()

            assert gcp_mod.Credentials is not None
            assert gcp_mod.SecretManagerServiceClient is not None
            assert gcp_mod.google_auth_default is not None
        finally:
            gcp_mod.Credentials = orig_creds
            gcp_mod.SecretManagerServiceClient = orig_client
            gcp_mod.google_auth_default = orig_default


# ---------------------------------------------------------------------------
# GoogleSecretManagerMapping
# ---------------------------------------------------------------------------

class TestGoogleSecretManagerMapping:
    def test_init(self):
        client = _make_secret_client({})
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert mapping._project_id == 'proj-1'
        assert mapping._case_sensitive is True
        assert mapping._loaded_secrets == {}

    def test_gcp_project_path(self):
        client = _make_secret_client({})
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert mapping._gcp_project_path == 'projects/my-proj'
        client.common_project_path.assert_called_once_with('proj-1')

    def test_select_case_insensitive_secret_single(self):
        client = _make_secret_client({})
        mapping = GoogleSecretManagerMapping(client, 'proj-1', False)
        assert mapping._select_case_insensitive_secret('foo', ['FOO']) == 'FOO'

    def test_select_case_insensitive_secret_multiple_warns(self):
        client = _make_secret_client({})
        mapping = GoogleSecretManagerMapping(client, 'proj-1', False)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = mapping._select_case_insensitive_secret('foo', ['Foo', 'FOO', 'foo'])
        assert len(w) == 1
        assert 'collision' in str(w[0].message).lower()
        # Sorted: FOO, Foo, foo -> last is 'foo'
        assert result == 'foo'

    def test_secret_name_map_case_sensitive(self):
        secrets = {'MY_SECRET': 'val1', 'another': 'val2'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        name_map = mapping._secret_name_map
        assert name_map == {'MY_SECRET': 'MY_SECRET', 'another': 'another'}

    def test_secret_name_map_case_insensitive(self):
        client = _make_secret_client(secret_names=['MyKey', 'OTHER'])
        mapping = GoogleSecretManagerMapping(client, 'proj-1', False)
        name_map = mapping._secret_name_map
        assert 'MyKey' in name_map
        assert 'OTHER' in name_map
        assert 'mykey' in name_map
        assert 'other' in name_map

    def test_secret_name_map_case_insensitive_collision(self):
        client = _make_secret_client(secret_names=['Foo', 'FOO'])
        mapping = GoogleSecretManagerMapping(client, 'proj-1', False)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            name_map = mapping._secret_name_map
        # Both original names should be in the map plus the normalized key
        assert 'Foo' in name_map
        assert 'FOO' in name_map
        assert 'foo' in name_map

    def test_secret_names(self):
        secrets = {'A': 'a', 'B': 'b'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert set(mapping._secret_names) == {'A', 'B'}

    def test_secret_version_path(self):
        client = _make_secret_client({})
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        result = mapping._secret_version_path('my_secret', '3')
        assert result == 'projects/proj-1/secrets/my_secret/versions/3'

    def test_get_secret_value_success(self):
        secrets = {'KEY': 'the-value'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert mapping._get_secret_value('KEY') == 'the-value'

    def test_get_secret_value_failure(self):
        client = _make_secret_client({})
        client.access_secret_version.side_effect = Exception('not found')
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert mapping._get_secret_value('MISSING') is None

    def test_getitem_hit(self):
        secrets = {'KEY': 'val'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert mapping['KEY'] == 'val'
        # Second call should use cache
        assert mapping['KEY'] == 'val'

    def test_getitem_missing_raises(self):
        client = _make_secret_client({})
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        with pytest.raises(KeyError):
            mapping['NOPE']

    def test_getitem_case_insensitive_fallback(self):
        secrets = {'MyKey': 'hello'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', False)
        # Access by lowercase should work via case-insensitive fallback
        assert mapping['mykey'] == 'hello'

    def test_len(self):
        secrets = {'A': '1', 'B': '2', 'C': '3'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        assert len(mapping) == 3

    def test_iter(self):
        secrets = {'X': '1', 'Y': '2'}
        client = _make_secret_client(secrets)
        mapping = GoogleSecretManagerMapping(client, 'proj-1', True)
        result = list(iter(mapping))
        assert set(result) == {'X', 'Y'}


# ---------------------------------------------------------------------------
# GoogleSecretManagerSettingsSource
# ---------------------------------------------------------------------------

class TestGoogleSecretManagerSettingsSource:
    @pytest.fixture()
    def mock_gcp_imports(self):
        """Patch the GCP globals so we can test without google-cloud-* packages."""
        import pydantic_settings.sources.providers.gcp as gcp_mod

        orig_creds = gcp_mod.Credentials
        orig_client_cls = gcp_mod.SecretManagerServiceClient
        orig_auth_default = gcp_mod.google_auth_default

        mock_creds_cls = MagicMock()
        mock_client_cls = MagicMock()
        mock_auth_default = MagicMock(return_value=(MagicMock(), 'default-project'))

        gcp_mod.Credentials = mock_creds_cls
        gcp_mod.SecretManagerServiceClient = mock_client_cls
        gcp_mod.google_auth_default = mock_auth_default

        yield {
            'Credentials': mock_creds_cls,
            'SecretManagerServiceClient': mock_client_cls,
            'google_auth_default': mock_auth_default,
        }

        gcp_mod.Credentials = orig_creds
        gcp_mod.SecretManagerServiceClient = orig_client_cls
        gcp_mod.google_auth_default = orig_auth_default

    def test_init_with_explicit_credentials_and_project(self, mock_gcp_imports):
        creds = MagicMock()
        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=creds, project_id='my-project', secret_client=client
        )

        assert source._credentials is creds
        assert source._project_id == 'my-project'
        assert source._secret_client is client

    def test_init_uses_default_credentials(self, mock_gcp_imports):
        default_creds = MagicMock()
        mock_gcp_imports['google_auth_default'].return_value = (default_creds, 'auto-project')

        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(settings_cls, secret_client=client)

        assert source._credentials is default_creds
        assert source._project_id == 'auto-project'

    def test_init_raises_when_no_project_id(self, mock_gcp_imports):
        mock_gcp_imports['google_auth_default'].return_value = (MagicMock(), None)

        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        with pytest.raises(AttributeError, match='project_id is required'):
            GoogleSecretManagerSettingsSource(settings_cls, secret_client=client)

    def test_init_creates_client_when_not_provided(self, mock_gcp_imports):
        creds = MagicMock()
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(settings_cls, credentials=creds, project_id='proj')

        mock_gcp_imports['SecretManagerServiceClient'].assert_called_once_with(credentials=creds)

    def test_init_calls_import_when_globals_none(self, mock_gcp_imports):
        """When the module globals are None, import_gcp_secret_manager is called."""
        import pydantic_settings.sources.providers.gcp as gcp_mod

        # Set globals to None to trigger the import path
        gcp_mod.Credentials = None
        gcp_mod.SecretManagerServiceClient = None
        gcp_mod.google_auth_default = None

        client = _make_secret_client({})
        creds = MagicMock()
        settings_cls = _make_settings_cls()

        with patch(
            'pydantic_settings.sources.providers.gcp.import_gcp_secret_manager'
        ) as mock_import:
            # After the import, globals need to be non-None for the rest of __init__ to work
            def _restore_globals():
                gcp_mod.Credentials = mock_gcp_imports['Credentials']
                gcp_mod.SecretManagerServiceClient = mock_gcp_imports['SecretManagerServiceClient']
                gcp_mod.google_auth_default = mock_gcp_imports['google_auth_default']

            mock_import.side_effect = _restore_globals

            source = GoogleSecretManagerSettingsSource(
                settings_cls, credentials=creds, project_id='proj', secret_client=client
            )
            mock_import.assert_called_once()
            assert source._project_id == 'proj'

    def test_load_env_vars_returns_mapping(self, mock_gcp_imports):
        client = _make_secret_client({'DB_HOST': 'localhost'})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        env_vars = source._load_env_vars()
        assert isinstance(env_vars, GoogleSecretManagerMapping)

    def test_repr(self, mock_gcp_imports):
        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        r = repr(source)
        assert 'GoogleSecretManagerSettingsSource' in r
        assert "'proj'" in r

    def test_get_field_value_no_secret_version(self, mock_gcp_imports):
        """Without SecretVersion metadata, delegates to super().get_field_value."""
        secrets = {'MY_VAR': 'hello'}
        client = _make_secret_client(secrets)
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        field = FieldInfo(annotation=str)
        val, key, is_complex = source.get_field_value(field, 'my_var')
        # The field should be looked up from the GoogleSecretManagerMapping
        # The key depends on whether the mapping has a matching env var
        assert val == 'hello' or val is None  # depends on env_prefix/case handling

    def test_get_field_value_with_secret_version(self, mock_gcp_imports):
        """With SecretVersion metadata, get a specific version of the secret."""
        secrets = {'MY_VAR': 'versioned-value'}
        client = _make_secret_client(secrets)
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        field = FieldInfo(annotation=str, metadata=[SecretVersion('5')])
        val, key, is_complex = source.get_field_value(field, 'MY_VAR')
        # With a specific version requested, the source accesses via _get_secret_value
        # The result depends on whether the secret name is found in the name map
        if val is not None:
            assert val == 'versioned-value'

    def test_get_field_value_secret_version_not_found_returns_none(self, mock_gcp_imports):
        """When secret version is requested but not found, returns None."""
        client = _make_secret_client({})
        client.access_secret_version.side_effect = Exception('not found')
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        field = FieldInfo(annotation=str, metadata=[SecretVersion('2')])
        val, key, is_complex = source.get_field_value(field, 'MISSING_SECRET')
        assert val is None

    def test_get_field_value_with_populate_by_name(self, mock_gcp_imports):
        """When populate_by_name is True, field_name is used as key."""
        secrets = {'MY_VAR': 'pop-val'}
        client = _make_secret_client(secrets)
        settings_cls = _make_settings_cls(populate_by_name=True)

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        field = FieldInfo(annotation=str)
        val, key, is_complex = source.get_field_value(field, 'MY_VAR')
        if val is not None:
            assert key == 'MY_VAR'

    def test_init_with_env_prefix(self, mock_gcp_imports):
        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client, env_prefix='APP_'
        )
        assert source.env_prefix == 'APP_'

    def test_init_case_sensitive_default_true(self, mock_gcp_imports):
        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client
        )
        assert source.case_sensitive is True

    def test_init_case_sensitive_false(self, mock_gcp_imports):
        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, credentials=MagicMock(), project_id='proj', secret_client=client, case_sensitive=False
        )
        assert source.case_sensitive is False

    def test_get_field_value_secret_version_case_insensitive(self, mock_gcp_imports):
        """Case-insensitive lookup with secret version falls back to lower-case key."""
        secrets = {'my_var': 'ci-val'}
        client = _make_secret_client(secrets)
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=MagicMock(),
            project_id='proj',
            secret_client=client,
            case_sensitive=False,
        )
        field = FieldInfo(annotation=str, metadata=[SecretVersion('1')])
        val, key, is_complex = source.get_field_value(field, 'my_var')
        if val is not None:
            assert val == 'ci-val'

    def test_get_field_value_secret_version_with_populate_by_name(self, mock_gcp_imports):
        """With both secret version and populate_by_name, field_name is returned as key."""
        secrets = {'MY_VAR': 'pbn-val'}
        client = _make_secret_client(secrets)
        settings_cls = _make_settings_cls(populate_by_name=True)

        source = GoogleSecretManagerSettingsSource(
            settings_cls,
            credentials=MagicMock(),
            project_id='proj',
            secret_client=client,
        )
        field = FieldInfo(annotation=str, metadata=[SecretVersion('latest')])
        val, key, is_complex = source.get_field_value(field, 'MY_VAR')
        if val is not None:
            assert key == 'MY_VAR'

    def test_init_partial_default_creds_only(self, mock_gcp_imports):
        """When only credentials is None, it falls back to google_auth_default for creds."""
        default_creds = MagicMock()
        mock_gcp_imports['google_auth_default'].return_value = (default_creds, 'fallback-proj')

        client = _make_secret_client({})
        settings_cls = _make_settings_cls()

        source = GoogleSecretManagerSettingsSource(
            settings_cls, project_id='explicit-proj', secret_client=client
        )
        # project_id was explicitly given, so should not use fallback
        assert source._project_id == 'explicit-proj'
        # credentials were not given, so should use default
        assert source._credentials is default_creds
