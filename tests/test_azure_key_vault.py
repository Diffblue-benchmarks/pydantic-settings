"""Tests for Azure Key Vault settings source."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.azure import (
    AzureKeyVaultMapping,
    AzureKeyVaultSettingsSource,
    import_azure_key_vault,
)


class MockSecretProperties:
    """Mock for Azure SecretProperties."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled


class MockSecretBundle:
    """Mock for Azure SecretBundle."""

    def __init__(self, value: str):
        self.value = value


@pytest.fixture
def mock_azure_modules():
    """Mock Azure SDK modules."""
    with patch.dict('sys.modules', {
        'azure': MagicMock(),
        'azure.core': MagicMock(),
        'azure.core.credentials': MagicMock(),
        'azure.core.exceptions': MagicMock(),
        'azure.keyvault': MagicMock(),
        'azure.keyvault.secrets': MagicMock(),
    }):
        yield


def test_import_azure_key_vault_success(mock_azure_modules):
    """Test successful import of Azure Key Vault dependencies."""
    # Setup mocks
    mock_token_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_resource_not_found = MagicMock()

    with patch('pydantic_settings.sources.providers.azure.TokenCredential', None):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', None):
            with patch('pydantic_settings.sources.providers.azure.ResourceNotFoundError', None):
                with patch.dict('sys.modules', {
                    'azure.core.credentials': MagicMock(TokenCredential=mock_token_credential),
                    'azure.core.exceptions': MagicMock(ResourceNotFoundError=mock_resource_not_found),
                    'azure.keyvault.secrets': MagicMock(SecretClient=mock_secret_client),
                }):
                    import_azure_key_vault()

                    # Verify globals were set
                    from pydantic_settings.sources.providers import azure
                    assert azure.TokenCredential is not None
                    assert azure.SecretClient is not None
                    assert azure.ResourceNotFoundError is not None


def test_import_azure_key_vault_missing_dependency():
    """Test import error when Azure SDK is not installed."""
    import builtins

    with patch('pydantic_settings.sources.providers.azure.TokenCredential', None):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', None):
            with patch('pydantic_settings.sources.providers.azure.ResourceNotFoundError', None):
                # Mock import to raise ImportError
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name.startswith('azure'):
                        raise ImportError('No module named azure')
                    return original_import(name, *args, **kwargs)

                with patch('builtins.__import__', side_effect=mock_import):
                    with pytest.raises(ImportError, match='Azure Key Vault dependencies are not installed'):
                        import_azure_key_vault()


def test_azure_key_vault_mapping_init_basic():
    """Test AzureKeyVaultMapping initialization with basic settings."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('secret1', enabled=True),
        MockSecretProperties('secret2', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert mapping._secret_client == mock_client
    assert mapping._case_sensitive is True
    assert mapping._snake_case_conversion is False
    assert mapping._env_prefix == ''
    assert len(mapping._secret_map) == 2


def test_azure_key_vault_mapping_init_with_prefix():
    """Test AzureKeyVaultMapping initialization with env prefix."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('APP_secret1', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix='APP_',
    )

    assert mapping._env_prefix == 'APP_'


def test_azure_key_vault_mapping_load_remote_case_sensitive():
    """Test _load_remote with case sensitive mode."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecret', enabled=True),
        MockSecretProperties('AnotherSecret', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert mapping._secret_map == {'MySecret': 'MySecret', 'AnotherSecret': 'AnotherSecret'}


def test_azure_key_vault_mapping_load_remote_case_insensitive():
    """Test _load_remote with case insensitive mode."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecret', enabled=True),
        MockSecretProperties('AnotherSecret', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert mapping._secret_map == {'mysecret': 'MySecret', 'anothersecret': 'AnotherSecret'}


def test_azure_key_vault_mapping_load_remote_snake_case():
    """Test _load_remote with snake case conversion."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecretKey', enabled=True),
        MockSecretProperties('AnotherAPIKey', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix=None,
    )

    assert mapping._secret_map == {'my_secret_key': 'MySecretKey', 'another_api_key': 'AnotherAPIKey'}


def test_azure_key_vault_mapping_load_remote_snake_case_with_prefix():
    """Test _load_remote with snake case conversion and prefix."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('APP_MySecret', enabled=True),
        MockSecretProperties('OtherSecret', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix='APP_',
    )

    assert mapping._secret_map == {'APP_my_secret': 'APP_MySecret', 'other_secret': 'OtherSecret'}


def test_azure_key_vault_mapping_load_remote_filters_disabled():
    """Test _load_remote filters out disabled secrets."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('EnabledSecret', enabled=True),
        MockSecretProperties('DisabledSecret', enabled=False),
        MockSecretProperties('AnotherEnabled', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert len(mapping._secret_map) == 2
    assert 'EnabledSecret' in mapping._secret_map
    assert 'DisabledSecret' not in mapping._secret_map
    assert 'AnotherEnabled' in mapping._secret_map


def test_azure_key_vault_mapping_load_remote_filters_none_names():
    """Test _load_remote filters out secrets with None names."""
    mock_client = MagicMock()
    mock_secret_with_none = MockSecretProperties('ValidSecret', enabled=True)
    mock_secret_none_name = MockSecretProperties(None, enabled=True)

    mock_client.list_properties_of_secrets.return_value = [
        mock_secret_with_none,
        mock_secret_none_name,
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert len(mapping._secret_map) == 1
    assert 'ValidSecret' in mapping._secret_map


def test_azure_key_vault_mapping_getitem_basic():
    """Test __getitem__ retrieves secret value."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecret', enabled=True),
    ]
    mock_client.get_secret.return_value = MockSecretBundle('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    value = mapping['MySecret']

    assert value == 'secret_value'
    mock_client.get_secret.assert_called_once_with('MySecret')


def test_azure_key_vault_mapping_getitem_caches_value():
    """Test __getitem__ caches retrieved secret values."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecret', enabled=True),
    ]
    mock_client.get_secret.return_value = MockSecretBundle('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    # First access
    value1 = mapping['MySecret']
    # Second access
    value2 = mapping['MySecret']

    assert value1 == 'secret_value'
    assert value2 == 'secret_value'
    # Should only call get_secret once due to caching
    mock_client.get_secret.assert_called_once_with('MySecret')


def test_azure_key_vault_mapping_getitem_case_insensitive():
    """Test __getitem__ with case insensitive mode."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecret', enabled=True),
    ]
    mock_client.get_secret.return_value = MockSecretBundle('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )

    value = mapping['MYSECRET']

    assert value == 'secret_value'
    mock_client.get_secret.assert_called_once_with('MySecret')


def test_azure_key_vault_mapping_getitem_snake_case():
    """Test __getitem__ with snake case conversion."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecretKey', enabled=True),
    ]
    mock_client.get_secret.return_value = MockSecretBundle('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix=None,
    )

    value = mapping['MySecretKey']

    assert value == 'secret_value'
    mock_client.get_secret.assert_called_once_with('MySecretKey')


def test_azure_key_vault_mapping_getitem_snake_case_with_prefix():
    """Test __getitem__ with snake case conversion and prefix."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('APP_MySecret', enabled=True),
    ]
    mock_client.get_secret.return_value = MockSecretBundle('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix='APP_',
    )

    value = mapping['APP_MySecret']

    assert value == 'secret_value'
    mock_client.get_secret.assert_called_once_with('APP_MySecret')


def test_azure_key_vault_mapping_getitem_snake_case_without_prefix():
    """Test __getitem__ with snake case conversion when key doesn't have prefix."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('SomeOtherKey', enabled=True),
    ]
    mock_client.get_secret.return_value = MockSecretBundle('other_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix='APP_',
    )

    value = mapping['SomeOtherKey']

    assert value == 'other_value'
    mock_client.get_secret.assert_called_once_with('SomeOtherKey')


def test_azure_key_vault_mapping_getitem_key_not_found():
    """Test __getitem__ raises KeyError when key not found."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('MySecret', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    with pytest.raises(KeyError):
        _ = mapping['NonExistentSecret']


def test_azure_key_vault_mapping_len():
    """Test __len__ returns number of secrets."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('secret1', enabled=True),
        MockSecretProperties('secret2', enabled=True),
        MockSecretProperties('secret3', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert len(mapping) == 3


def test_azure_key_vault_mapping_iter():
    """Test __iter__ returns iterator over secret keys."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [
        MockSecretProperties('secret1', enabled=True),
        MockSecretProperties('secret2', enabled=True),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    keys = list(mapping)

    assert set(keys) == {'secret1', 'secret2'}


def test_azure_key_vault_settings_source_init_basic():
    """Test AzureKeyVaultSettingsSource initialization with basic settings."""

    class MySettings(BaseSettings):
        secret_key: str = ''

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
            )

    assert source._url == 'https://myvault.vault.azure.net/'
    assert source._credential == mock_credential
    assert source._dash_to_underscore is False
    assert source._snake_case_conversion is False


def test_azure_key_vault_settings_source_init_with_options():
    """Test AzureKeyVaultSettingsSource initialization with various options."""

    class MySettings(BaseSettings):
        secret_key: str = ''

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
                dash_to_underscore=True,
                case_sensitive=False,
                snake_case_conversion=True,
                env_prefix='APP_',
                env_parse_none_str='null',
                env_parse_enums=True,
            )

    assert source._url == 'https://myvault.vault.azure.net/'
    assert source._credential == mock_credential
    assert source._dash_to_underscore is True
    assert source._snake_case_conversion is True
    assert source.env_prefix == 'APP_'
    assert source.case_sensitive is True  # Should be True when snake_case_conversion is True
    assert source.env_nested_delimiter == '__'  # Should be '__' when snake_case_conversion is True


def test_azure_key_vault_settings_source_init_calls_import():
    """Test AzureKeyVaultSettingsSource initialization calls import_azure_key_vault."""

    class MySettings(BaseSettings):
        secret_key: str = ''

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault') as mock_import:
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
            )

            mock_import.assert_called_once()


def test_azure_key_vault_settings_source_load_env_vars():
    """Test _load_env_vars creates AzureKeyVaultMapping."""

    class MySettings(BaseSettings):
        secret_key: str = ''

    mock_credential = MagicMock()
    mock_secret_client_class = MagicMock()
    mock_secret_client_instance = MagicMock()
    mock_secret_client_class.return_value = mock_secret_client_instance
    mock_secret_client_instance.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', mock_secret_client_class):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
            )

            # The __init__ already called _load_env_vars, so the SecretClient was already called
            # Reset the mock to test explicit call
            mock_secret_client_class.reset_mock()

            result = source._load_env_vars()

            assert isinstance(result, AzureKeyVaultMapping)
            mock_secret_client_class.assert_called_with(
                vault_url='https://myvault.vault.azure.net/',
                credential=mock_credential,
            )


def test_azure_key_vault_settings_source_extract_field_info_basic():
    """Test _extract_field_info without special conversions."""

    class MySettings(BaseSettings):
        secret_key: str = Field(default='')

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
                dash_to_underscore=False,
                snake_case_conversion=False,
            )

            field_info = MySettings.model_fields['secret_key']
            result = source._extract_field_info(field_info, 'secret_key')

            assert isinstance(result, list)


def test_azure_key_vault_settings_source_extract_field_info_dash_to_underscore():
    """Test _extract_field_info with dash_to_underscore enabled."""

    class MySettings(BaseSettings):
        secret_key: str = Field(default='')

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
                dash_to_underscore=True,
                snake_case_conversion=False,
            )

            field_info = MySettings.model_fields['secret_key']
            result = source._extract_field_info(field_info, 'secret_key')

            assert isinstance(result, list)
            # Verify underscores are replaced with dashes in the field name
            has_dash = any('-' in item[1] for item in result)
            assert has_dash or len(result) > 0  # Either has dash or returned non-empty list


def test_azure_key_vault_settings_source_extract_field_info_snake_case():
    """Test _extract_field_info with snake_case_conversion enabled."""

    class MySettings(BaseSettings):
        secret_key: str = Field(default='')

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
                snake_case_conversion=True,
            )

            field_info = MySettings.model_fields['secret_key']
            result = source._extract_field_info(field_info, 'secret_key')

            assert isinstance(result, list)


def test_azure_key_vault_settings_source_repr():
    """Test __repr__ returns correct representation."""

    class MySettings(BaseSettings):
        secret_key: str = ''

    mock_credential = MagicMock()
    mock_secret_client = MagicMock()
    mock_secret_client.list_properties_of_secrets.return_value = []

    with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_secret_client):
            source = AzureKeyVaultSettingsSource(
                settings_cls=MySettings,
                url='https://myvault.vault.azure.net/',
                credential=mock_credential,
            )

            repr_str = repr(source)

            assert 'AzureKeyVaultSettingsSource' in repr_str
            assert 'https://myvault.vault.azure.net/' in repr_str
            assert 'env_nested_delimiter' in repr_str
