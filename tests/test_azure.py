"""Tests for Azure Key Vault settings source."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.azure import (
    AzureKeyVaultMapping,
    AzureKeyVaultSettingsSource,
    import_azure_key_vault,
)


@pytest.fixture
def mock_secret_client():
    """Create a mock SecretClient."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_secret_properties():
    """Create mock secret properties."""
    def create_secret_property(name, enabled=True):
        prop = MagicMock()
        prop.name = name
        prop.enabled = enabled
        return prop
    return create_secret_property


@pytest.fixture
def mock_secret():
    """Create a mock secret."""
    def create_secret(value):
        secret = MagicMock()
        secret.value = value
        return secret
    return create_secret


def test_import_azure_key_vault_success():
    """Test successful import of Azure Key Vault dependencies."""
    with patch('pydantic_settings.sources.providers.azure.TokenCredential', None):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', None):
            with patch('pydantic_settings.sources.providers.azure.ResourceNotFoundError', None):
                # Mock successful imports
                mock_token_credential = Mock()
                mock_secret_client = Mock()
                mock_resource_not_found = Mock()

                with patch.dict('sys.modules', {
                    'azure.core.credentials': Mock(TokenCredential=mock_token_credential),
                    'azure.keyvault.secrets': Mock(SecretClient=mock_secret_client),
                    'azure.core.exceptions': Mock(ResourceNotFoundError=mock_resource_not_found),
                }):
                    import_azure_key_vault()


def test_import_azure_key_vault_missing_dependency():
    """Test import failure when Azure dependencies are missing."""
    with patch('pydantic_settings.sources.providers.azure.TokenCredential', None):
        with patch('pydantic_settings.sources.providers.azure.SecretClient', None):
            # Simulate import error
            def raise_import_error(*args, **kwargs):
                raise ImportError("No module named 'azure'")

            with patch('builtins.__import__', side_effect=raise_import_error):
                with pytest.raises(ImportError) as exc_info:
                    import_azure_key_vault()
                assert 'Azure Key Vault dependencies are not installed' in str(exc_info.value)


def test_azure_key_vault_mapping_init_basic(mock_secret_client, mock_secret_properties):
    """Test AzureKeyVaultMapping initialization with basic settings."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('secret1'),
        mock_secret_properties('secret2'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert mapping._secret_client == mock_secret_client
    assert mapping._case_sensitive is True
    assert mapping._snake_case_conversion is False
    assert mapping._env_prefix == ''
    assert len(mapping._secret_map) == 2


def test_azure_key_vault_mapping_init_with_prefix(mock_secret_client, mock_secret_properties):
    """Test AzureKeyVaultMapping initialization with env prefix."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('APP_SECRET1'),
        mock_secret_properties('APP_SECRET2'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix='APP_',
    )

    assert mapping._env_prefix == 'APP_'
    assert len(mapping._secret_map) == 2


def test_azure_key_vault_mapping_load_remote_case_sensitive(mock_secret_client, mock_secret_properties):
    """Test loading remote secrets with case-sensitive mode."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('SecretOne'),
        mock_secret_properties('SecretTwo'),
        mock_secret_properties('DisabledSecret', enabled=False),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert 'SecretOne' in mapping._secret_map
    assert 'SecretTwo' in mapping._secret_map
    assert 'DisabledSecret' not in mapping._secret_map
    assert mapping._secret_map['SecretOne'] == 'SecretOne'


def test_azure_key_vault_mapping_load_remote_case_insensitive(mock_secret_client, mock_secret_properties):
    """Test loading remote secrets with case-insensitive mode."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('SecretOne'),
        mock_secret_properties('SecretTwo'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert 'secretone' in mapping._secret_map
    assert 'secrettwo' in mapping._secret_map
    assert mapping._secret_map['secretone'] == 'SecretOne'


def test_azure_key_vault_mapping_load_remote_snake_case_no_prefix(mock_secret_client, mock_secret_properties):
    """Test loading remote secrets with snake case conversion and no prefix."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('SecretOne'),
        mock_secret_properties('AnotherSecret'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix=None,
    )

    assert 'secret_one' in mapping._secret_map
    assert 'another_secret' in mapping._secret_map
    assert mapping._secret_map['secret_one'] == 'SecretOne'


def test_azure_key_vault_mapping_load_remote_snake_case_with_prefix(mock_secret_client, mock_secret_properties):
    """Test loading remote secrets with snake case conversion and prefix."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('APP_SecretOne'),
        mock_secret_properties('APP_AnotherSecret'),
        mock_secret_properties('OtherSecret'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix='APP_',
    )

    assert 'APP_secret_one' in mapping._secret_map
    assert 'APP_another_secret' in mapping._secret_map
    assert 'other_secret' in mapping._secret_map
    assert mapping._secret_map['APP_secret_one'] == 'APP_SecretOne'


def test_azure_key_vault_mapping_getitem_case_sensitive(mock_secret_client, mock_secret_properties, mock_secret):
    """Test retrieving secrets in case-sensitive mode."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('MySecret'),
    ]
    mock_secret_client.get_secret.return_value = mock_secret('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    value = mapping['MySecret']
    assert value == 'secret_value'
    assert 'MySecret' in mapping._loaded_secrets


def test_azure_key_vault_mapping_getitem_case_insensitive(mock_secret_client, mock_secret_properties, mock_secret):
    """Test retrieving secrets in case-insensitive mode."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('MySecret'),
    ]
    mock_secret_client.get_secret.return_value = mock_secret('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )

    value = mapping['mysecret']
    assert value == 'secret_value'
    mock_secret_client.get_secret.assert_called_once_with('MySecret')


def test_azure_key_vault_mapping_getitem_snake_case_no_prefix(mock_secret_client, mock_secret_properties, mock_secret):
    """Test retrieving secrets with snake case conversion without prefix."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('MySecret'),
    ]
    mock_secret_client.get_secret.return_value = mock_secret('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix=None,
    )

    value = mapping['MySecret']
    assert value == 'secret_value'


def test_azure_key_vault_mapping_getitem_snake_case_with_prefix(mock_secret_client, mock_secret_properties, mock_secret):
    """Test retrieving secrets with snake case conversion with prefix."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('APP_MySecret'),
    ]
    mock_secret_client.get_secret.return_value = mock_secret('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=True,
        env_prefix='APP_',
    )

    value = mapping['APP_MySecret']
    assert value == 'secret_value'


def test_azure_key_vault_mapping_getitem_key_not_found(mock_secret_client, mock_secret_properties):
    """Test KeyError when secret does not exist."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('ExistingSecret'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    with pytest.raises(KeyError) as exc_info:
        _ = mapping['NonExistentSecret']
    assert 'NonExistentSecret' in str(exc_info.value)


def test_azure_key_vault_mapping_getitem_cached(mock_secret_client, mock_secret_properties, mock_secret):
    """Test that secrets are cached after first retrieval."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('MySecret'),
    ]
    mock_secret_client.get_secret.return_value = mock_secret('secret_value')

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    # First access - should call get_secret
    value1 = mapping['MySecret']
    assert value1 == 'secret_value'

    # Second access - should use cached value
    value2 = mapping['MySecret']
    assert value2 == 'secret_value'

    # get_secret should only be called once
    assert mock_secret_client.get_secret.call_count == 1


def test_azure_key_vault_mapping_len(mock_secret_client, mock_secret_properties):
    """Test length of mapping."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('secret1'),
        mock_secret_properties('secret2'),
        mock_secret_properties('secret3'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    assert len(mapping) == 3


def test_azure_key_vault_mapping_iter(mock_secret_client, mock_secret_properties):
    """Test iteration over mapping keys."""
    mock_secret_client.list_properties_of_secrets.return_value = [
        mock_secret_properties('secret1'),
        mock_secret_properties('secret2'),
    ]

    mapping = AzureKeyVaultMapping(
        secret_client=mock_secret_client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )

    keys = list(mapping)
    assert 'secret1' in keys
    assert 'secret2' in keys
    assert len(keys) == 2


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_init_basic(mock_import, mock_client_class):
    """Test AzureKeyVaultSettingsSource initialization with basic settings."""
    class Settings(BaseSettings):
        field1: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
    )

    assert source._url == 'https://test.vault.azure.net/'
    assert source._credential == mock_credential
    assert source._dash_to_underscore is False
    assert source._snake_case_conversion is False
    mock_import.assert_called_once()


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_init_with_options(mock_import, mock_client_class):
    """Test AzureKeyVaultSettingsSource initialization with all options."""
    class Settings(BaseSettings):
        field1: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
        dash_to_underscore=True,
        case_sensitive=False,
        snake_case_conversion=True,
        env_prefix='APP_',
        env_parse_none_str='null',
        env_parse_enums=True,
    )

    assert source._dash_to_underscore is True
    assert source._snake_case_conversion is True
    assert source.env_prefix == 'APP_'
    assert source.env_nested_delimiter == '__'
    assert source.case_sensitive is True  # True when snake_case_conversion is True


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_init_without_snake_case(mock_import, mock_client_class):
    """Test AzureKeyVaultSettingsSource initialization without snake case conversion."""
    class Settings(BaseSettings):
        field1: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
        case_sensitive=False,
        snake_case_conversion=False,
    )

    assert source.case_sensitive is False
    assert source.env_nested_delimiter == '--'


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_load_env_vars(mock_import, mock_client_class, mock_secret_properties):
    """Test _load_env_vars method."""
    class Settings(BaseSettings):
        field1: str = ''

    mock_credential = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_class.return_value = mock_client_instance
    mock_client_instance.list_properties_of_secrets.return_value = [
        mock_secret_properties('secret1'),
    ]

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
    )

    env_vars = source._load_env_vars()

    mock_client_class.assert_called_with(
        vault_url='https://test.vault.azure.net/',
        credential=mock_credential
    )
    assert isinstance(env_vars, AzureKeyVaultMapping)


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_extract_field_info_snake_case(mock_import, mock_client_class):
    """Test _extract_field_info with snake case conversion."""
    class Settings(BaseSettings):
        my_field: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
        snake_case_conversion=True,
    )

    field_info = Settings.model_fields['my_field']
    result = source._extract_field_info(field_info, 'my_field')

    assert isinstance(result, list)


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_extract_field_info_dash_to_underscore(mock_import, mock_client_class):
    """Test _extract_field_info with dash to underscore."""
    class Settings(BaseSettings):
        my_field: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
        dash_to_underscore=True,
    )

    field_info = Settings.model_fields['my_field']
    result = source._extract_field_info(field_info, 'my_field')

    # Check that underscores are replaced with dashes
    for field_name_tuple in result:
        assert '_' not in field_name_tuple[1] or '-' in field_name_tuple[1]


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_extract_field_info_default(mock_import, mock_client_class):
    """Test _extract_field_info with default settings."""
    class Settings(BaseSettings):
        my_field: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
    )

    field_info = Settings.model_fields['my_field']
    result = source._extract_field_info(field_info, 'my_field')

    assert isinstance(result, list)


@patch('pydantic_settings.sources.providers.azure.SecretClient')
@patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
def test_azure_key_vault_settings_source_repr(mock_import, mock_client_class):
    """Test __repr__ method."""
    class Settings(BaseSettings):
        field1: str = ''

    mock_credential = MagicMock()

    source = AzureKeyVaultSettingsSource(
        settings_cls=Settings,
        url='https://test.vault.azure.net/',
        credential=mock_credential,
    )

    repr_str = repr(source)
    assert 'AzureKeyVaultSettingsSource' in repr_str
    assert 'https://test.vault.azure.net/' in repr_str
    assert 'env_nested_delimiter' in repr_str
