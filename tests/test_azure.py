"""Tests for Azure Key Vault settings source."""
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Helpers: build a minimal fake azure module tree so the provider can import
# ---------------------------------------------------------------------------


def _make_azure_mocks():
    """Return a dict of fake azure modules to inject into sys.modules."""
    mock_credential = MagicMock()

    mock_secret = MagicMock()
    mock_secret.name = 'my-secret'
    mock_secret.enabled = True

    mock_secret_client_cls = MagicMock()

    mock_token_credential = MagicMock()
    mock_resource_not_found = type('ResourceNotFoundError', (Exception,), {})

    azure_mod = MagicMock()
    azure_core_mod = MagicMock()
    azure_core_credentials_mod = MagicMock()
    azure_core_credentials_mod.TokenCredential = mock_token_credential
    azure_core_exceptions_mod = MagicMock()
    azure_core_exceptions_mod.ResourceNotFoundError = mock_resource_not_found
    azure_keyvault_mod = MagicMock()
    azure_keyvault_secrets_mod = MagicMock()
    azure_keyvault_secrets_mod.SecretClient = mock_secret_client_cls

    modules = {
        'azure': azure_mod,
        'azure.core': azure_core_mod,
        'azure.core.credentials': azure_core_credentials_mod,
        'azure.core.exceptions': azure_core_exceptions_mod,
        'azure.keyvault': azure_keyvault_mod,
        'azure.keyvault.secrets': azure_keyvault_secrets_mod,
    }
    return modules, mock_secret_client_cls, mock_token_credential, mock_resource_not_found


@pytest.fixture(autouse=True)
def inject_azure_mocks():
    """Inject fake azure modules before each test and clean up after."""
    modules, secret_client_cls, token_credential, resource_not_found = _make_azure_mocks()
    original = {k: sys.modules.get(k) for k in modules}
    sys.modules.update(modules)

    # Re-import provider with mocked azure modules
    for mod_name in list(sys.modules):
        if 'pydantic_settings.sources.providers.azure' in mod_name:
            del sys.modules[mod_name]

    yield modules, secret_client_cls, token_credential, resource_not_found

    # Restore
    for k, v in original.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v

    for mod_name in list(sys.modules):
        if 'pydantic_settings.sources.providers.azure' in mod_name:
            del sys.modules[mod_name]


def _get_provider():
    """Import the azure provider fresh (after mocks are in place)."""
    import importlib
    import pydantic_settings.sources.providers.azure as m
    return m


# ---------------------------------------------------------------------------
# Tests for import_azure_key_vault
# ---------------------------------------------------------------------------


def test_import_azure_key_vault_sets_globals(inject_azure_mocks):
    m = _get_provider()
    # Reset globals to None
    m.TokenCredential = None
    m.SecretClient = None
    m.ResourceNotFoundError = None

    m.import_azure_key_vault()

    assert m.TokenCredential is not None
    assert m.SecretClient is not None
    assert m.ResourceNotFoundError is not None


def test_import_azure_key_vault_idempotent(inject_azure_mocks):
    m = _get_provider()
    m.import_azure_key_vault()
    m.import_azure_key_vault()  # calling twice should not raise


# ---------------------------------------------------------------------------
# Helpers to build a mock SecretClient
# ---------------------------------------------------------------------------


def _mock_secret_properties(name: str, enabled: bool = True):
    prop = MagicMock()
    prop.name = name
    prop.enabled = enabled
    return prop


def _make_client(secrets: list):
    client = MagicMock()
    client.list_properties_of_secrets.return_value = secrets
    return client


# ---------------------------------------------------------------------------
# Tests for AzureKeyVaultMapping
# ---------------------------------------------------------------------------


class TestAzureKeyVaultMappingInit:
    def test_basic_init(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([_mock_secret_properties('mysecret')])
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert mapping._loaded_secrets == {}
        assert mapping._secret_client is client
        assert mapping._case_sensitive is True
        assert mapping._snake_case_conversion is False
        assert mapping._env_prefix == ''

    def test_env_prefix_stored(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([])
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix='MY_',
        )

        assert mapping._env_prefix == 'MY_'


class TestAzureKeyVaultMappingLoadRemote:
    def test_load_remote_case_sensitive(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [_mock_secret_properties('MySecret'), _mock_secret_properties('other')]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert mapping._secret_map == {'MySecret': 'MySecret', 'other': 'other'}

    def test_load_remote_case_insensitive(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [_mock_secret_properties('MySecret')]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert 'mysecret' in mapping._secret_map
        assert mapping._secret_map['mysecret'] == 'MySecret'

    def test_load_remote_snake_case_with_prefix(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [_mock_secret_properties('my-prefix-my-secret')]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix='my-prefix-',
        )

        assert 'my-prefix-my_secret' in mapping._secret_map

    def test_load_remote_snake_case_no_prefix(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [_mock_secret_properties('my-secret-name')]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )

        assert 'my_secret_name' in mapping._secret_map

    def test_load_remote_skips_disabled(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [
            _mock_secret_properties('enabled-secret', enabled=True),
            _mock_secret_properties('disabled-secret', enabled=False),
        ]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert 'enabled-secret' in mapping._secret_map
        assert 'disabled-secret' not in mapping._secret_map

    def test_load_remote_skips_none_name(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        prop = MagicMock()
        prop.name = None
        prop.enabled = True
        client = _make_client([prop])
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert mapping._secret_map == {}


class TestAzureKeyVaultMappingGetItem:
    def _make_mapping(self, m, client, *, case_sensitive=True, snake_case=False, prefix=''):
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=case_sensitive,
            snake_case_conversion=snake_case,
            env_prefix=prefix if prefix else None,
        )
        return mapping

    def test_getitem_returns_secret_value(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([_mock_secret_properties('my-secret')])
        secret_val = MagicMock()
        secret_val.value = 'supersecret'
        client.get_secret.return_value = secret_val

        mapping = self._make_mapping(m, client, case_sensitive=True)
        result = mapping['my-secret']

        assert result == 'supersecret'

    def test_getitem_caches_secret(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([_mock_secret_properties('my-secret')])
        secret_val = MagicMock()
        secret_val.value = 'val'
        client.get_secret.return_value = secret_val

        mapping = self._make_mapping(m, client, case_sensitive=True)
        _ = mapping['my-secret']
        _ = mapping['my-secret']

        assert client.get_secret.call_count == 1

    def test_getitem_key_not_found_raises(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([])
        mapping = self._make_mapping(m, client, case_sensitive=True)

        with pytest.raises(KeyError):
            _ = mapping['nonexistent']

    def test_getitem_case_insensitive(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([_mock_secret_properties('MySecret')])
        secret_val = MagicMock()
        secret_val.value = 'val'
        client.get_secret.return_value = secret_val

        mapping = self._make_mapping(m, client, case_sensitive=False)
        result = mapping['MYSECRET']

        assert result == 'val'

    def test_getitem_snake_case_with_prefix(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([_mock_secret_properties('pfx-my-key')])
        secret_val = MagicMock()
        secret_val.value = 'v'
        client.get_secret.return_value = secret_val

        mapping = self._make_mapping(m, client, snake_case=True, prefix='pfx-')
        result = mapping['pfx-my-key']

        assert result == 'v'

    def test_getitem_snake_case_without_prefix(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        client = _make_client([_mock_secret_properties('my-key')])
        secret_val = MagicMock()
        secret_val.value = 'v2'
        client.get_secret.return_value = secret_val

        mapping = self._make_mapping(m, client, snake_case=True)
        result = mapping['my-key']

        assert result == 'v2'


class TestAzureKeyVaultMappingLenIter:
    def test_len(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [_mock_secret_properties('a'), _mock_secret_properties('b')]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 2

    def test_iter(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        secrets = [_mock_secret_properties('alpha'), _mock_secret_properties('beta')]
        client = _make_client(secrets)
        mapping = m.AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        keys = list(mapping)
        assert sorted(keys) == ['alpha', 'beta']


# ---------------------------------------------------------------------------
# Tests for AzureKeyVaultSettingsSource
# ---------------------------------------------------------------------------


class MySettings(BaseSettings):
    model_config = {'extra': 'ignore'}

    my_key: str = 'default'
    other_field: str = 'other_default'


class TestAzureKeyVaultSettingsSourceInit:
    def test_init_basic(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        assert src._url == 'https://myvault.vault.azure.net/'
        assert src._credential is credential
        assert src._dash_to_underscore is False
        assert src._snake_case_conversion is False

    def test_init_with_snake_case(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            snake_case_conversion=True,
        )

        assert src._snake_case_conversion is True
        assert src.case_sensitive is True
        assert src.env_nested_delimiter == '__'

    def test_init_without_snake_case(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            snake_case_conversion=False,
        )

        assert src.env_nested_delimiter == '--'

    def test_init_with_dash_to_underscore(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            dash_to_underscore=True,
        )

        assert src._dash_to_underscore is True

    def test_init_with_env_prefix(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            env_prefix='app-',
        )

        assert src.env_prefix == 'app-'


class TestAzureKeyVaultSettingsSourceLoadEnvVars:
    def test_load_env_vars_returns_mapping(self, inject_azure_mocks):
        modules, secret_client_cls, _, _ = inject_azure_mocks
        m = _get_provider()
        m.import_azure_key_vault()

        mock_instance = _make_client([])
        secret_client_cls.return_value = mock_instance

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        result = src._load_env_vars()

        assert isinstance(result, m.AzureKeyVaultMapping)
        # SecretClient is called during __init__ (via super().__init__ -> _load_env_vars)
        # and again when we explicitly call _load_env_vars(), so just verify it was called
        secret_client_cls.assert_called_with(
            vault_url='https://myvault.vault.azure.net/', credential=credential
        )


class TestAzureKeyVaultSettingsSourceExtractFieldInfo:
    def test_extract_field_info_default(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        field_info = FieldInfo(annotation=str)
        result = src._extract_field_info(field_info, 'my_key')

        assert isinstance(result, list)
        assert len(result) > 0

    def test_extract_field_info_dash_to_underscore(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            dash_to_underscore=True,
        )

        field_info = FieldInfo(annotation=str)
        result = src._extract_field_info(field_info, 'my_key')

        assert isinstance(result, list)
        for item in result:
            assert '_' not in item[1], f"Expected no underscores in field name, got: {item[1]}"

    def test_extract_field_info_snake_case_conversion(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            snake_case_conversion=True,
        )

        field_info = FieldInfo(annotation=str)
        result = src._extract_field_info(field_info, 'my_key')

        assert isinstance(result, list)
        assert len(result) > 0


class TestAzureKeyVaultSettingsSourceRepr:
    def test_repr(self, inject_azure_mocks):
        m = _get_provider()
        m.import_azure_key_vault()

        credential = MagicMock()
        src = m.AzureKeyVaultSettingsSource(
            settings_cls=MySettings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        r = repr(src)

        assert 'AzureKeyVaultSettingsSource' in r
        assert 'https://myvault.vault.azure.net/' in r
        assert 'env_nested_delimiter' in r
