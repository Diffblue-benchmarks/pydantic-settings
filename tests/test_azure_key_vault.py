"""Tests for Azure Key Vault settings source."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pydantic_settings.sources.providers import azure as azure_mod
from pydantic_settings.sources.providers.azure import AzureKeyVaultMapping


def _make_secret_properties(name, enabled=True):
    """Helper to create a mock secret properties object."""
    props = SimpleNamespace()
    props.name = name
    props.enabled = enabled
    return props


def _make_secret(value):
    """Helper to create a mock secret object."""
    secret = SimpleNamespace()
    secret.value = value
    return secret


def _make_mock_client(secrets_map, disabled_names=None):
    """Create a mock SecretClient.

    Args:
        secrets_map: dict mapping secret names to their values.
        disabled_names: set of names that should be disabled.
    """
    disabled_names = disabled_names or set()
    client = MagicMock()
    props_list = []
    for name in secrets_map:
        enabled = name not in disabled_names
        props_list.append(_make_secret_properties(name, enabled=enabled))
    client.list_properties_of_secrets.return_value = props_list
    client.get_secret.side_effect = lambda name: _make_secret(secrets_map[name])
    return client


def _patch_azure_modules():
    """Return a patch.dict context that fakes the azure.* modules."""
    mock_token_cred = type('TokenCredential', (), {})
    mock_resource_not_found = type('ResourceNotFoundError', (Exception,), {})
    # SecretClient needs to be a MagicMock class so it can be called with kwargs
    mock_secret_client_cls = MagicMock()

    fake_azure_core_creds = SimpleNamespace(TokenCredential=mock_token_cred)
    fake_azure_core_exc = SimpleNamespace(ResourceNotFoundError=mock_resource_not_found)
    fake_azure_kv_secrets = SimpleNamespace(SecretClient=mock_secret_client_cls)

    return (
        patch.dict(
            sys.modules,
            {
                'azure': MagicMock(),
                'azure.core': MagicMock(),
                'azure.core.credentials': fake_azure_core_creds,
                'azure.core.exceptions': fake_azure_core_exc,
                'azure.keyvault': MagicMock(),
                'azure.keyvault.secrets': fake_azure_kv_secrets,
            },
        ),
        mock_token_cred,
        mock_secret_client_cls,
        mock_resource_not_found,
    )


class _AzureGlobalRestore:
    """Context manager to save/restore azure module globals."""

    def __enter__(self):
        self._original_tc = azure_mod.TokenCredential
        self._original_sc = azure_mod.SecretClient
        self._original_rnf = azure_mod.ResourceNotFoundError
        return self

    def __exit__(self, *args):
        azure_mod.TokenCredential = self._original_tc
        azure_mod.SecretClient = self._original_sc
        azure_mod.ResourceNotFoundError = self._original_rnf


class TestImportAzureKeyVault:
    def test_import_sets_globals(self):
        """Test that import_azure_key_vault sets the global variables when azure packages are available."""
        ctx, mock_tc, mock_sc, mock_rnf = _patch_azure_modules()

        with _AzureGlobalRestore(), ctx:
            azure_mod.import_azure_key_vault()
            assert azure_mod.TokenCredential is mock_tc
            assert azure_mod.ResourceNotFoundError is mock_rnf


class TestAzureKeyVaultMappingCaseInsensitive:
    def test_init_loads_secrets_case_insensitive(self):
        """Test that secrets are loaded with lowered keys when case_sensitive=False."""
        secrets = {'MySecret': 'value1', 'AnotherSecret': 'value2'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 2
        assert 'mysecret' in mapping
        assert 'anothersecret' in mapping

    def test_getitem_case_insensitive(self):
        """Test __getitem__ lowercases the key when case_sensitive=False."""
        secrets = {'MySecret': 'hello'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        result = mapping['MySecret']
        assert result == 'hello'
        client.get_secret.assert_called_once_with('MySecret')

    def test_getitem_raises_key_error(self):
        """Test __getitem__ raises KeyError for missing secrets."""
        secrets = {'MySecret': 'hello'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        with pytest.raises(KeyError, match='nonexistent'):
            mapping['nonexistent']

    def test_getitem_caches_result(self):
        """Test that __getitem__ caches the result after first access."""
        secrets = {'MySecret': 'cached-value'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        result1 = mapping['MySecret']
        result2 = mapping['MySecret']
        assert result1 == result2 == 'cached-value'
        assert client.get_secret.call_count == 1


class TestAzureKeyVaultMappingCaseSensitive:
    def test_init_loads_secrets_case_sensitive(self):
        """Test that secrets are loaded with original keys when case_sensitive=True."""
        secrets = {'MySecret': 'value1', 'AnotherSecret': 'value2'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 2
        assert 'MySecret' in mapping
        assert 'AnotherSecret' in mapping

    def test_getitem_case_sensitive(self):
        """Test __getitem__ preserves key case when case_sensitive=True."""
        secrets = {'MySecret': 'world'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        result = mapping['MySecret']
        assert result == 'world'

        with pytest.raises(KeyError):
            mapping['mysecret']


class TestAzureKeyVaultMappingSnakeCaseConversion:
    def test_snake_case_conversion_without_prefix(self):
        """Test that secret names are converted to snake_case."""
        secrets = {'MySecretName': 'val1', 'AnotherValue': 'val2'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )

        keys = list(mapping)
        assert 'my_secret_name' in keys
        assert 'another_value' in keys

    def test_snake_case_conversion_with_prefix(self):
        """Test snake_case conversion with env_prefix."""
        secrets = {'APP_MySecretName': 'val1', 'OtherName': 'val2'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix='APP_',
        )

        keys = list(mapping)
        assert 'APP_my_secret_name' in keys
        assert 'other_name' in keys

    def test_getitem_snake_case_with_prefix(self):
        """Test __getitem__ with snake_case conversion and prefix."""
        secrets = {'APP_DatabaseUrl': 'postgres://localhost'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix='APP_',
        )

        result = mapping['APP_DatabaseUrl']
        assert result == 'postgres://localhost'

    def test_getitem_snake_case_without_prefix(self):
        """Test __getitem__ with snake_case conversion without prefix."""
        secrets = {'DatabaseUrl': 'postgres://localhost'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )

        result = mapping['DatabaseUrl']
        assert result == 'postgres://localhost'


class TestAzureKeyVaultMappingIterAndLen:
    def test_len(self):
        """Test __len__ returns the number of secrets."""
        secrets = {'secret1': 'a', 'secret2': 'b', 'secret3': 'c'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 3

    def test_iter(self):
        """Test __iter__ returns keys of the secret map."""
        secrets = {'alpha': 'a', 'beta': 'b'}
        client = _make_mock_client(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        keys = list(mapping)
        assert sorted(keys) == ['alpha', 'beta']

    def test_disabled_secrets_excluded(self):
        """Test that disabled secrets are excluded from the mapping."""
        secrets = {'enabled-secret': 'val1', 'disabled-secret': 'val2'}
        client = _make_mock_client(secrets, disabled_names={'disabled-secret'})

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 1
        assert 'enabled-secret' in mapping

    def test_none_name_secrets_excluded(self):
        """Test that secrets with None name are excluded."""
        client = MagicMock()
        client.list_properties_of_secrets.return_value = [
            _make_secret_properties('valid-secret', enabled=True),
            SimpleNamespace(name=None, enabled=True),
        ]
        client.get_secret.side_effect = lambda name: _make_secret('value')

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 1
        assert 'valid-secret' in mapping


class TestAzureKeyVaultSettingsSource:
    def _create_source(self, **kwargs):
        """Helper to create an AzureKeyVaultSettingsSource with mocked Azure deps."""
        from pydantic_settings.sources.providers.azure import AzureKeyVaultSettingsSource

        from pydantic_settings import BaseSettings

        class MySettings(BaseSettings):
            my_field: str = 'default'

        defaults = {
            'settings_cls': MySettings,
            'url': 'https://my-vault.vault.azure.net',
            'credential': MagicMock(),
        }
        defaults.update(kwargs)
        return AzureKeyVaultSettingsSource(**defaults), MySettings

    def test_init_and_repr(self):
        """Test AzureKeyVaultSettingsSource initialization and __repr__."""
        ctx, mock_tc, mock_sc_cls, mock_rnf = _patch_azure_modules()
        # Make the mock secret client instance usable
        mock_client_instance = _make_mock_client({})
        mock_sc_cls.return_value = mock_client_instance

        with _AzureGlobalRestore(), ctx:
            source, _ = self._create_source()

            assert source._url == 'https://my-vault.vault.azure.net'
            assert source._dash_to_underscore is False
            assert source._snake_case_conversion is False
            assert source.env_nested_delimiter == '--'

            repr_str = repr(source)
            assert 'AzureKeyVaultSettingsSource' in repr_str
            assert 'https://my-vault.vault.azure.net' in repr_str
            assert '--' in repr_str

    def test_init_snake_case_conversion(self):
        """Test that snake_case_conversion sets case_sensitive=True and env_nested_delimiter='__'."""
        ctx, mock_tc, mock_sc_cls, mock_rnf = _patch_azure_modules()
        mock_client_instance = _make_mock_client({})
        mock_sc_cls.return_value = mock_client_instance

        with _AzureGlobalRestore(), ctx:
            source, _ = self._create_source(
                snake_case_conversion=True,
                env_prefix='APP_',
            )

            assert source._snake_case_conversion is True
            assert source.case_sensitive is True
            assert source.env_nested_delimiter == '__'

    def test_load_env_vars(self):
        """Test _load_env_vars creates a SecretClient and returns AzureKeyVaultMapping."""
        ctx, mock_tc, mock_sc_cls, mock_rnf = _patch_azure_modules()
        mock_client_instance = _make_mock_client({'my-secret': 'value'})
        mock_sc_cls.return_value = mock_client_instance

        with _AzureGlobalRestore(), ctx:
            credential = MagicMock()
            source, _ = self._create_source(credential=credential)

            # The _load_env_vars was already called during __init__ via super().__init__
            # Verify the result is an AzureKeyVaultMapping
            assert isinstance(source.env_vars, AzureKeyVaultMapping)

    def test_extract_field_info_default(self):
        """Test _extract_field_info without dash_to_underscore or snake_case_conversion."""
        ctx, mock_tc, mock_sc_cls, mock_rnf = _patch_azure_modules()
        mock_client_instance = _make_mock_client({})
        mock_sc_cls.return_value = mock_client_instance

        with _AzureGlobalRestore(), ctx:
            source, settings_cls = self._create_source()

            field_info = settings_cls.model_fields['my_field']
            result = source._extract_field_info(field_info, 'my_field')
            assert isinstance(result, list)
            assert len(result) > 0

    def test_extract_field_info_dash_to_underscore(self):
        """Test _extract_field_info with dash_to_underscore=True replaces underscores with dashes."""
        ctx, mock_tc, mock_sc_cls, mock_rnf = _patch_azure_modules()
        mock_client_instance = _make_mock_client({})
        mock_sc_cls.return_value = mock_client_instance

        with _AzureGlobalRestore(), ctx:
            source, settings_cls = self._create_source(dash_to_underscore=True)

            field_info = settings_cls.model_fields['my_field']
            result = source._extract_field_info(field_info, 'my_field')
            assert isinstance(result, list)
            # The field name my_field should have underscores replaced with dashes
            field_keys = [item[1] for item in result]
            for key in field_keys:
                assert '_' not in key

    def test_extract_field_info_snake_case_conversion(self):
        """Test _extract_field_info with snake_case_conversion=True."""
        ctx, mock_tc, mock_sc_cls, mock_rnf = _patch_azure_modules()
        mock_client_instance = _make_mock_client({})
        mock_sc_cls.return_value = mock_client_instance

        with _AzureGlobalRestore(), ctx:
            source, settings_cls = self._create_source(snake_case_conversion=True)

            field_info = settings_cls.model_fields['my_field']
            result = source._extract_field_info(field_info, 'my_field')
            assert isinstance(result, list)
            assert len(result) > 0
