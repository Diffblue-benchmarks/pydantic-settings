"""Tests for Azure Key Vault settings source."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pydantic_settings.sources.providers.azure import (
    AzureKeyVaultMapping,
    AzureKeyVaultSettingsSource,
    import_azure_key_vault,
)


def _make_secret_property(name: str, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(name=name, enabled=enabled)


def _make_secret(value: str | None) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def _make_mock_client(secrets: dict[str, str | None], disabled: list[str] | None = None) -> MagicMock:
    """Create a mock SecretClient that returns the given secrets."""
    disabled = disabled or []
    client = MagicMock()
    properties = []
    for name in secrets:
        properties.append(_make_secret_property(name, name not in disabled))
    for name in disabled:
        if name not in secrets:
            properties.append(_make_secret_property(name, False))
    client.list_properties_of_secrets.return_value = properties
    client.get_secret.side_effect = lambda name: _make_secret(secrets.get(name))
    return client


class TestImportAzureKeyVault:
    def test_import_raises_when_azure_not_installed(self) -> None:
        import builtins

        real_import = builtins.__import__

        def _block_azure(name: str, *args: object, **kwargs: object) -> object:
            if name.startswith('azure'):
                raise ImportError('No module named azure')
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=_block_azure):
            with pytest.raises(ImportError, match='Azure Key Vault dependencies are not installed'):
                import_azure_key_vault()

    def test_import_sets_globals_when_azure_available(self) -> None:
        mock_token = MagicMock()
        mock_client = MagicMock()
        mock_error = MagicMock()

        modules = {
            'azure': MagicMock(),
            'azure.core': MagicMock(),
            'azure.core.credentials': MagicMock(TokenCredential=mock_token),
            'azure.core.exceptions': MagicMock(ResourceNotFoundError=mock_error),
            'azure.keyvault': MagicMock(),
            'azure.keyvault.secrets': MagicMock(SecretClient=mock_client),
        }
        with patch.dict('sys.modules', modules):
            import_azure_key_vault()

        from pydantic_settings.sources.providers import azure

        assert azure.TokenCredential is mock_token
        assert azure.SecretClient is mock_client
        assert azure.ResourceNotFoundError is mock_error


class TestAzureKeyVaultMapping:
    def test_init_basic(self) -> None:
        client = _make_mock_client({'my-secret': 'val1'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 1
        client.list_properties_of_secrets.assert_called_once()

    def test_load_remote_case_insensitive(self) -> None:
        client = _make_mock_client({'MySecret': 'val1', 'AnotherSecret': 'val2'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert 'mysecret' in mapping
        assert 'anothersecret' in mapping

    def test_load_remote_case_sensitive(self) -> None:
        client = _make_mock_client({'MySecret': 'val1', 'AnotherSecret': 'val2'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert 'MySecret' in mapping
        assert 'AnotherSecret' in mapping
        assert 'mysecret' not in mapping

    def test_load_remote_snake_case_conversion(self) -> None:
        client = _make_mock_client({'MySecretName': 'val1'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )
        assert 'my_secret_name' in mapping

    def test_load_remote_snake_case_with_prefix(self) -> None:
        client = _make_mock_client({'PREFIXMySecretName': 'val1', 'OtherName': 'val2'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix='PREFIX',
        )
        assert 'PREFIXmy_secret_name' in mapping
        assert 'other_name' in mapping

    def test_load_remote_filters_disabled_secrets(self) -> None:
        client = _make_mock_client({'enabled-secret': 'val1'}, disabled=['disabled-secret'])
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 1
        assert 'enabled-secret' in mapping

    def test_load_remote_filters_secrets_with_no_name(self) -> None:
        client = MagicMock()
        client.list_properties_of_secrets.return_value = [
            SimpleNamespace(name='valid', enabled=True),
            SimpleNamespace(name=None, enabled=True),
            SimpleNamespace(name='', enabled=True),
        ]
        client.get_secret.side_effect = lambda name: _make_secret('val')
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 1
        assert 'valid' in mapping

    def test_getitem_case_insensitive(self) -> None:
        client = _make_mock_client({'MySecret': 'hello'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        result = mapping['MySecret']
        assert result == 'hello'
        client.get_secret.assert_called_once_with('MySecret')

    def test_getitem_case_sensitive(self) -> None:
        client = _make_mock_client({'MySecret': 'hello'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        result = mapping['MySecret']
        assert result == 'hello'

    def test_getitem_snake_case_conversion(self) -> None:
        client = _make_mock_client({'MySecretName': 'hello'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )
        result = mapping['MySecretName']
        assert result == 'hello'

    def test_getitem_snake_case_with_prefix(self) -> None:
        client = _make_mock_client({'PREFIXMyName': 'hello'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix='PREFIX',
        )
        result = mapping['PREFIXMyName']
        assert result == 'hello'

    def test_getitem_key_not_found_raises(self) -> None:
        client = _make_mock_client({'existing': 'val'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        with pytest.raises(KeyError, match='nonexistent'):
            mapping['nonexistent']

    def test_getitem_caches_result(self) -> None:
        client = _make_mock_client({'mysecret': 'cached_val'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        result1 = mapping['mysecret']
        result2 = mapping['mysecret']
        assert result1 == result2 == 'cached_val'
        client.get_secret.assert_called_once_with('mysecret')

    def test_getitem_none_value(self) -> None:
        client = _make_mock_client({'mysecret': None})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        result = mapping['mysecret']
        assert result is None

    def test_len(self) -> None:
        client = _make_mock_client({'a': '1', 'b': '2', 'c': '3'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 3

    def test_iter(self) -> None:
        client = _make_mock_client({'alpha': '1', 'beta': '2'})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        keys = list(mapping)
        assert 'alpha' in keys
        assert 'beta' in keys
        assert len(keys) == 2

    def test_empty_mapping(self) -> None:
        client = _make_mock_client({})
        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 0
        assert list(mapping) == []


@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
class TestAzureKeyVaultSettingsSource:
    def _make_source(
        self,
        mock_secret_client_cls: MagicMock,
        secrets: list[SimpleNamespace] | None = None,
        **kwargs: object,
    ) -> AzureKeyVaultSettingsSource:
        from pydantic_settings.main import BaseSettings

        mock_instance = MagicMock()
        mock_instance.list_properties_of_secrets.return_value = secrets or []
        mock_secret_client_cls.return_value = mock_instance

        class MySettings(BaseSettings):
            my_var: str = 'default'

        return AzureKeyVaultSettingsSource(
            MySettings,
            url='https://myvault.vault.azure.net',
            credential=MagicMock(),
            **kwargs,
        )

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_init(self, mock_secret_client_cls: MagicMock, mock_import: MagicMock) -> None:
        from pydantic_settings.main import BaseSettings

        class MySettings(BaseSettings):
            my_var: str = 'default'

        credential = MagicMock()
        mock_instance = MagicMock()
        mock_instance.list_properties_of_secrets.return_value = []
        mock_secret_client_cls.return_value = mock_instance

        source = AzureKeyVaultSettingsSource(
            MySettings,
            url='https://myvault.vault.azure.net',
            credential=credential,
        )
        assert source._url == 'https://myvault.vault.azure.net'
        assert source._credential is credential
        mock_import.assert_called_once()

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_init_snake_case_sets_case_sensitive_true(
        self, mock_secret_client_cls: MagicMock, mock_import: MagicMock
    ) -> None:
        source = self._make_source(mock_secret_client_cls, snake_case_conversion=True)
        assert source.case_sensitive is True
        assert source.env_nested_delimiter == '__'

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_init_default_nested_delimiter(
        self, mock_secret_client_cls: MagicMock, mock_import: MagicMock
    ) -> None:
        source = self._make_source(mock_secret_client_cls)
        assert source.env_nested_delimiter == '--'

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_load_env_vars(self, mock_secret_client_cls: MagicMock, mock_import: MagicMock) -> None:
        mock_instance = MagicMock()
        mock_instance.list_properties_of_secrets.return_value = [
            _make_secret_property('my-var'),
        ]
        mock_instance.get_secret.return_value = _make_secret('test_value')
        mock_secret_client_cls.return_value = mock_instance

        source = self._make_source(mock_secret_client_cls, secrets=[_make_secret_property('my-var')])
        env_vars = source._load_env_vars()
        assert isinstance(env_vars, AzureKeyVaultMapping)

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_extract_field_info_default(
        self, mock_secret_client_cls: MagicMock, mock_import: MagicMock
    ) -> None:
        from pydantic_settings.main import BaseSettings

        mock_instance = MagicMock()
        mock_instance.list_properties_of_secrets.return_value = []
        mock_secret_client_cls.return_value = mock_instance

        class MySettings(BaseSettings):
            my_var: str = 'default'

        source = AzureKeyVaultSettingsSource(
            MySettings,
            url='https://myvault.vault.azure.net',
            credential=MagicMock(),
        )
        fields = MySettings.model_fields
        field_info = source._extract_field_info(fields['my_var'], 'my_var')
        assert isinstance(field_info, list)
        assert len(field_info) > 0

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_extract_field_info_dash_to_underscore(
        self, mock_secret_client_cls: MagicMock, mock_import: MagicMock
    ) -> None:
        from pydantic_settings.main import BaseSettings

        mock_instance = MagicMock()
        mock_instance.list_properties_of_secrets.return_value = []
        mock_secret_client_cls.return_value = mock_instance

        class MySettings(BaseSettings):
            my_var: str = 'default'

        source = AzureKeyVaultSettingsSource(
            MySettings,
            url='https://myvault.vault.azure.net',
            credential=MagicMock(),
            dash_to_underscore=True,
        )
        fields = MySettings.model_fields
        field_info = source._extract_field_info(fields['my_var'], 'my_var')
        assert isinstance(field_info, list)
        for _, env_name, _ in field_info:
            assert '_' not in env_name

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_extract_field_info_snake_case(
        self, mock_secret_client_cls: MagicMock, mock_import: MagicMock
    ) -> None:
        from pydantic_settings.main import BaseSettings

        mock_instance = MagicMock()
        mock_instance.list_properties_of_secrets.return_value = []
        mock_secret_client_cls.return_value = mock_instance

        class MySettings(BaseSettings):
            my_var: str = 'default'

        source = AzureKeyVaultSettingsSource(
            MySettings,
            url='https://myvault.vault.azure.net',
            credential=MagicMock(),
            snake_case_conversion=True,
        )
        fields = MySettings.model_fields
        field_info = source._extract_field_info(fields['my_var'], 'my_var')
        assert isinstance(field_info, list)
        assert len(field_info) > 0

    @patch('pydantic_settings.sources.providers.azure.SecretClient')
    def test_repr(self, mock_secret_client_cls: MagicMock, mock_import: MagicMock) -> None:
        source = self._make_source(mock_secret_client_cls)
        result = repr(source)
        assert 'AzureKeyVaultSettingsSource' in result
        assert 'https://myvault.vault.azure.net' in result
        assert '--' in result
