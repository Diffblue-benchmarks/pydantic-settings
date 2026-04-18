"""Tests for Azure Key Vault settings source."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.azure import (
    AzureKeyVaultMapping,
    AzureKeyVaultSettingsSource,
    import_azure_key_vault,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class MockSecretProperties:
    """Mock for azure.keyvault.secrets.SecretProperties."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled


class MockSecret:
    """Mock for azure.keyvault.secrets.KeyVaultSecret."""

    def __init__(self, value: str):
        self.value = value


class MockSecretClient:
    """Mock for azure.keyvault.secrets.SecretClient."""

    def __init__(self, secrets: dict[str, str], vault_url: str = '', credential: object = None):
        self._secrets = secrets
        self._enabled = {k: True for k in secrets}

    def list_properties_of_secrets(self) -> list[MockSecretProperties]:
        return [MockSecretProperties(name, self._enabled.get(name, True)) for name in self._secrets]

    def get_secret(self, name: str) -> MockSecret:
        if name in self._secrets:
            return MockSecret(self._secrets[name])
        raise KeyError(name)


class TestImportAzureKeyVault:
    """Tests for the import_azure_key_vault function."""

    def test_import_azure_key_vault_success(self, mocker: MockerFixture):
        """Test successful import of Azure Key Vault dependencies."""
        mock_token_credential = MagicMock()
        mock_secret_client = MagicMock()
        mock_resource_not_found_error = MagicMock()

        mocker.patch.dict(
            'sys.modules',
            {
                'azure': MagicMock(),
                'azure.core': MagicMock(),
                'azure.core.credentials': MagicMock(TokenCredential=mock_token_credential),
                'azure.core.exceptions': MagicMock(ResourceNotFoundError=mock_resource_not_found_error),
                'azure.keyvault': MagicMock(),
                'azure.keyvault.secrets': MagicMock(SecretClient=mock_secret_client),
            },
        )

        import_azure_key_vault()

    def test_import_azure_key_vault_import_error(self, mocker: MockerFixture):
        """Test import_azure_key_vault raises ImportError when Azure is not installed."""
        mocker.patch.dict('sys.modules', {'azure': None, 'azure.core': None, 'azure.keyvault': None})
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            side_effect=ImportError('Azure Key Vault dependencies are not installed'),
        )

        with pytest.raises(ImportError, match='Azure Key Vault dependencies are not installed'):
            import_azure_key_vault()


class TestAzureKeyVaultMapping:
    """Tests for AzureKeyVaultMapping class."""

    def test_init_basic(self):
        """Test basic initialization of AzureKeyVaultMapping."""
        secrets = {'secret1': 'value1', 'secret2': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 2

    def test_init_with_prefix(self):
        """Test initialization with env_prefix."""
        secrets = {'APP_SECRET1': 'value1', 'OTHER_SECRET': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix='APP_',
        )

        assert len(mapping) == 2

    def test_load_remote_case_sensitive(self):
        """Test _load_remote with case sensitive mode."""
        secrets = {'MySecret': 'value1', 'AnotherSecret': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert 'MySecret' in mapping
        assert 'AnotherSecret' in mapping

    def test_load_remote_case_insensitive(self):
        """Test _load_remote with case insensitive mode."""
        secrets = {'MySecret': 'value1', 'AnotherSecret': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert 'mysecret' in mapping
        assert 'anothersecret' in mapping

    def test_load_remote_snake_case_conversion(self):
        """Test _load_remote with snake_case_conversion enabled."""
        secrets = {'MySecretName': 'value1', 'AnotherSecretName': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=True,
            env_prefix=None,
        )

        assert 'my_secret_name' in mapping
        assert 'another_secret_name' in mapping

    def test_load_remote_snake_case_with_prefix(self):
        """Test _load_remote with snake_case_conversion and prefix."""
        secrets = {'APP_MySecretName': 'value1', 'OtherSecret': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=True,
            env_prefix='APP_',
        )

        assert 'APP_my_secret_name' in mapping
        assert 'other_secret' in mapping

    def test_getitem_basic(self):
        """Test __getitem__ retrieves secret values correctly."""
        secrets = {'secret1': 'value1', 'secret2': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert mapping['secret1'] == 'value1'
        assert mapping['secret2'] == 'value2'

    def test_getitem_case_insensitive(self):
        """Test __getitem__ with case insensitive mode."""
        secrets = {'MySecret': 'value1'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert mapping['MYSECRET'] == 'value1'
        assert mapping['mysecret'] == 'value1'

    def test_getitem_snake_case_conversion(self):
        """Test __getitem__ with snake_case_conversion."""
        secrets = {'MySecretName': 'value1'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=True,
            env_prefix=None,
        )

        assert mapping['MySecretName'] == 'value1'

    def test_getitem_snake_case_with_prefix(self):
        """Test __getitem__ with snake_case_conversion and prefix."""
        secrets = {'APP_MySecretName': 'value1'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=True,
            env_prefix='APP_',
        )

        assert mapping['APP_MySecretName'] == 'value1'

    def test_getitem_key_not_found(self):
        """Test __getitem__ raises KeyError for missing secrets."""
        secrets = {'secret1': 'value1'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        with pytest.raises(KeyError):
            _ = mapping['nonexistent']

    def test_getitem_caches_values(self):
        """Test that __getitem__ caches retrieved values."""
        secrets = {'secret1': 'value1'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        value1 = mapping['secret1']
        value2 = mapping['secret1']
        assert value1 == value2

    def test_len(self):
        """Test __len__ returns correct number of secrets."""
        secrets = {'secret1': 'value1', 'secret2': 'value2', 'secret3': 'value3'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert len(mapping) == 3

    def test_iter(self):
        """Test __iter__ returns iterator over secret names."""
        secrets = {'secret1': 'value1', 'secret2': 'value2'}
        client = MockSecretClient(secrets)

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        keys = list(mapping)
        assert 'secret1' in keys
        assert 'secret2' in keys


class TestAzureKeyVaultSettingsSource:
    """Tests for AzureKeyVaultSettingsSource class."""

    def test_init_basic(self, mocker: MockerFixture):
        """Test basic initialization of AzureKeyVaultSettingsSource."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        assert source._url == 'https://myvault.vault.azure.net/'
        assert source._credential is credential
        assert source.env_nested_delimiter == '--'

    def test_init_with_snake_case_conversion(self, mocker: MockerFixture):
        """Test initialization with snake_case_conversion enabled."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            snake_case_conversion=True,
        )

        assert source._snake_case_conversion is True
        assert source.case_sensitive is True
        assert source.env_nested_delimiter == '__'

    def test_init_with_custom_options(self, mocker: MockerFixture):
        """Test initialization with custom options."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            dash_to_underscore=True,
            case_sensitive=False,
            env_prefix='APP_',
            env_parse_none_str='null',
        )

        assert source._dash_to_underscore is True
        assert source.case_sensitive is False
        assert source.env_prefix == 'APP_'
        assert source.env_parse_none_str == 'null'

    def test_load_env_vars(self, mocker: MockerFixture):
        """Test _load_env_vars creates AzureKeyVaultMapping."""
        mock_secret_client_class = mocker.patch(
            'pydantic_settings.sources.providers.azure.SecretClient',
        )
        mock_client_instance = MagicMock()
        mock_client_instance.list_properties_of_secrets.return_value = []
        mock_secret_client_class.return_value = mock_client_instance

        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        env_vars = source._load_env_vars()
        assert isinstance(env_vars, AzureKeyVaultMapping)

    def test_extract_field_info_snake_case(self, mocker: MockerFixture):
        """Test _extract_field_info with snake_case_conversion."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            my_secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            snake_case_conversion=True,
        )

        field_info = Settings.model_fields['my_secret']
        result = source._extract_field_info(field_info, 'my_secret')

        assert len(result) > 0

    def test_extract_field_info_dash_to_underscore(self, mocker: MockerFixture):
        """Test _extract_field_info with dash_to_underscore."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            my_secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
            dash_to_underscore=True,
        )

        field_info = Settings.model_fields['my_secret']
        result = source._extract_field_info(field_info, 'my_secret')

        assert len(result) > 0
        field_key, env_name, is_complex = result[0]
        assert '-' in env_name

    def test_extract_field_info_default(self, mocker: MockerFixture):
        """Test _extract_field_info with default settings."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            my_secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        field_info = Settings.model_fields['my_secret']
        result = source._extract_field_info(field_info, 'my_secret')

        assert len(result) > 0

    def test_repr(self, mocker: MockerFixture):
        """Test __repr__ returns expected string."""
        mocker.patch(
            'pydantic_settings.sources.providers.azure.import_azure_key_vault',
            return_value=None,
        )

        class Settings(BaseSettings):
            secret: str = ''

        credential = MagicMock()
        source = AzureKeyVaultSettingsSource(
            settings_cls=Settings,
            url='https://myvault.vault.azure.net/',
            credential=credential,
        )

        repr_str = repr(source)
        assert 'AzureKeyVaultSettingsSource' in repr_str
        assert 'https://myvault.vault.azure.net/' in repr_str
        assert 'env_nested_delimiter' in repr_str


class TestAzureKeyVaultMappingDisabledSecrets:
    """Tests for disabled secrets in AzureKeyVaultMapping."""

    def test_disabled_secrets_excluded(self):
        """Test that disabled secrets are excluded from the mapping."""
        secrets = {'enabled_secret': 'value1', 'disabled_secret': 'value2'}
        client = MockSecretClient(secrets)
        client._enabled['disabled_secret'] = False

        mapping = AzureKeyVaultMapping(
            secret_client=client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )

        assert 'enabled_secret' in mapping
        assert 'disabled_secret' not in mapping
        assert len(mapping) == 1
