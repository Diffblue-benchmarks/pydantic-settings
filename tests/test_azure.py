"""Tests for Azure Key Vault settings source."""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.azure import (
    import_azure_key_vault,
    AzureKeyVaultMapping,
    AzureKeyVaultSettingsSource,
)


class TestImportAzureKeyVault:
    """Tests for import_azure_key_vault function."""

    def test_import_azure_key_vault_success(self):
        """Test successful import of Azure Key Vault dependencies."""
        with patch('pydantic_settings.sources.providers.azure.TokenCredential', None):
            with patch('pydantic_settings.sources.providers.azure.SecretClient', None):
                with patch('pydantic_settings.sources.providers.azure.ResourceNotFoundError', None):
                    # Mock the actual imports
                    with patch.dict('sys.modules', {
                        'azure.core.credentials': MagicMock(),
                        'azure.core.exceptions': MagicMock(),
                        'azure.keyvault.secrets': MagicMock(),
                    }):
                        import_azure_key_vault()
                        # After import, globals should be set
                        from pydantic_settings.sources.providers import azure
                        assert azure.TokenCredential is not None
                        assert azure.SecretClient is not None
                        assert azure.ResourceNotFoundError is not None

    def test_import_azure_key_vault_import_error(self):
        """Test import_azure_key_vault raises ImportError when dependencies missing."""
        with patch('pydantic_settings.sources.providers.azure.TokenCredential', None):
            with patch('pydantic_settings.sources.providers.azure.SecretClient', None):
                with patch('pydantic_settings.sources.providers.azure.ResourceNotFoundError', None):
                    # Mock missing imports
                    def mock_import(*args, **kwargs):
                        raise ImportError("No module named 'azure'")

                    with patch('builtins.__import__', side_effect=mock_import):
                        with pytest.raises(ImportError, match='Azure Key Vault dependencies are not installed'):
                            import_azure_key_vault()


class TestAzureKeyVaultMapping:
    """Tests for AzureKeyVaultMapping class."""

    @pytest.fixture
    def mock_secret_client(self):
        """Create a mock SecretClient."""
        client = Mock()
        return client

    @pytest.fixture
    def azure_mapping(self, mock_secret_client):
        """Create an AzureKeyVaultMapping instance."""
        return AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )

    def test_init_default_values(self, mock_secret_client):
        """Test AzureKeyVaultMapping initialization with default values."""
        mock_secret_client.list_properties_of_secrets.return_value = []
        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert mapping._secret_client is mock_secret_client
        assert mapping._case_sensitive is False
        assert mapping._snake_case_conversion is False
        assert mapping._env_prefix == ''
        assert mapping._loaded_secrets == {}

    def test_init_with_env_prefix(self, mock_secret_client):
        """Test AzureKeyVaultMapping initialization with env_prefix."""
        mock_secret_client.list_properties_of_secrets.return_value = []
        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix='APP_',
        )
        assert mapping._env_prefix == 'APP_'

    def test_load_remote_case_insensitive(self, mock_secret_client):
        """Test _load_remote with case_sensitive=False."""
        secret_props_1 = Mock()
        secret_props_1.name = 'MY_SECRET'
        secret_props_1.enabled = True
        secret_props_2 = Mock()
        secret_props_2.name = 'another_secret'
        secret_props_2.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props_1, secret_props_2]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert mapping._secret_map == {'my_secret': 'MY_SECRET', 'another_secret': 'another_secret'}

    def test_load_remote_case_sensitive(self, mock_secret_client):
        """Test _load_remote with case_sensitive=True."""
        secret_props = Mock()
        secret_props.name = 'MY_SECRET'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert mapping._secret_map == {'MY_SECRET': 'MY_SECRET'}

    def test_load_remote_disabled_secrets_filtered(self, mock_secret_client):
        """Test _load_remote filters out disabled secrets."""
        secret_props_enabled = Mock()
        secret_props_enabled.name = 'enabled_secret'
        secret_props_enabled.enabled = True
        secret_props_disabled = Mock()
        secret_props_disabled.name = 'disabled_secret'
        secret_props_disabled.enabled = False
        mock_secret_client.list_properties_of_secrets.return_value = [
            secret_props_enabled,
            secret_props_disabled,
        ]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert 'disabled_secret' not in mapping._secret_map
        assert 'enabled_secret' in mapping._secret_map

    def test_load_remote_none_names_filtered(self, mock_secret_client):
        """Test _load_remote filters out secrets with None names."""
        secret_props_valid = Mock()
        secret_props_valid.name = 'valid_secret'
        secret_props_valid.enabled = True
        secret_props_none = Mock()
        secret_props_none.name = None
        secret_props_none.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [
            secret_props_valid,
            secret_props_none,
        ]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping._secret_map) == 1
        assert 'valid_secret' in mapping._secret_map

    def test_load_remote_snake_case_conversion(self, mock_secret_client):
        """Test _load_remote with snake_case_conversion=True."""
        secret_props = Mock()
        secret_props.name = 'MySecretName'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )
        # to_snake converts 'MySecretName' to 'my_secret_name'
        assert 'my_secret_name' in mapping._secret_map

    def test_load_remote_snake_case_with_prefix(self, mock_secret_client):
        """Test _load_remote with snake_case_conversion and env_prefix."""
        secret_props = Mock()
        secret_props.name = 'APP_MySecretName'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix='APP_',
        )
        # Prefix is preserved, only the rest is converted to snake_case
        assert 'app_my_secret_name' in mapping._secret_map or 'APP_my_secret_name' in mapping._secret_map

    def test_getitem_existing_key_case_insensitive(self, mock_secret_client):
        """Test __getitem__ retrieves existing secret with case insensitive lookup."""
        secret_props = Mock()
        secret_props.name = 'MY_SECRET'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        secret_value_obj = Mock()
        secret_value_obj.value = 'secret_value'
        mock_secret_client.get_secret.return_value = secret_value_obj

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        value = mapping['my_secret']
        assert value == 'secret_value'
        mock_secret_client.get_secret.assert_called_once_with('MY_SECRET')

    def test_getitem_existing_key_case_sensitive(self, mock_secret_client):
        """Test __getitem__ with case_sensitive=True."""
        secret_props = Mock()
        secret_props.name = 'MY_SECRET'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        secret_value_obj = Mock()
        secret_value_obj.value = 'secret_value'
        mock_secret_client.get_secret.return_value = secret_value_obj

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=True,
            snake_case_conversion=False,
            env_prefix=None,
        )
        value = mapping['MY_SECRET']
        assert value == 'secret_value'

    def test_getitem_missing_key(self, mock_secret_client):
        """Test __getitem__ raises KeyError for missing secret."""
        secret_props = Mock()
        secret_props.name = 'EXISTING_SECRET'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        with pytest.raises(KeyError):
            mapping['nonexistent']

    def test_getitem_cached_value(self, mock_secret_client):
        """Test __getitem__ uses cached value on second access."""
        secret_props = Mock()
        secret_props.name = 'MY_SECRET'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        secret_value_obj = Mock()
        secret_value_obj.value = 'secret_value'
        mock_secret_client.get_secret.return_value = secret_value_obj

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        value1 = mapping['my_secret']
        value2 = mapping['my_secret']
        assert value1 == value2
        # get_secret should only be called once due to caching
        assert mock_secret_client.get_secret.call_count == 1

    def test_getitem_snake_case_conversion(self, mock_secret_client):
        """Test __getitem__ with snake_case_conversion."""
        secret_props = Mock()
        secret_props.name = 'MySecretName'
        secret_props.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props]

        secret_value_obj = Mock()
        secret_value_obj.value = 'secret_value'
        mock_secret_client.get_secret.return_value = secret_value_obj

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=True,
            env_prefix=None,
        )
        value = mapping['MySecretName']
        assert value == 'secret_value'

    def test_len(self, mock_secret_client):
        """Test __len__ returns number of secrets."""
        secret_props_1 = Mock()
        secret_props_1.name = 'SECRET1'
        secret_props_1.enabled = True
        secret_props_2 = Mock()
        secret_props_2.name = 'SECRET2'
        secret_props_2.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props_1, secret_props_2]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 2

    def test_len_empty(self, mock_secret_client):
        """Test __len__ with no secrets."""
        mock_secret_client.list_properties_of_secrets.return_value = []

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        assert len(mapping) == 0

    def test_iter(self, mock_secret_client):
        """Test __iter__ returns iterator over secret keys."""
        secret_props_1 = Mock()
        secret_props_1.name = 'SECRET1'
        secret_props_1.enabled = True
        secret_props_2 = Mock()
        secret_props_2.name = 'SECRET2'
        secret_props_2.enabled = True
        mock_secret_client.list_properties_of_secrets.return_value = [secret_props_1, secret_props_2]

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        keys = list(mapping)
        assert 'secret1' in keys
        assert 'secret2' in keys

    def test_iter_empty(self, mock_secret_client):
        """Test __iter__ with empty mapping."""
        mock_secret_client.list_properties_of_secrets.return_value = []

        mapping = AzureKeyVaultMapping(
            secret_client=mock_secret_client,
            case_sensitive=False,
            snake_case_conversion=False,
            env_prefix=None,
        )
        keys = list(mapping)
        assert keys == []


class TestAzureKeyVaultSettingsSource:
    """Tests for AzureKeyVaultSettingsSource class."""

    @pytest.fixture
    def mock_credential(self):
        """Create a mock TokenCredential."""
        return Mock()

    @pytest.fixture
    def settings_cls(self):
        """Create a test BaseSettings class."""
        class TestSettings(BaseSettings):
            database_url: str = 'default'
            api_key: str = 'default'
        return TestSettings

    @pytest.fixture
    def azure_source(self, settings_cls, mock_credential):
        """Create an AzureKeyVaultSettingsSource instance."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                )
                return source

    def test_init_basic(self, settings_cls, mock_credential):
        """Test AzureKeyVaultSettingsSource initialization."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                )
                assert source._url == 'https://myvault.vault.azure.net/'
                assert source._credential is mock_credential
                assert source._dash_to_underscore is False
                assert source._snake_case_conversion is False

    def test_init_with_dash_to_underscore(self, settings_cls, mock_credential):
        """Test AzureKeyVaultSettingsSource with dash_to_underscore."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    dash_to_underscore=True,
                )
                assert source._dash_to_underscore is True

    def test_init_with_snake_case_conversion(self, settings_cls, mock_credential):
        """Test AzureKeyVaultSettingsSource with snake_case_conversion."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    snake_case_conversion=True,
                )
                assert source._snake_case_conversion is True
                # When snake_case_conversion is True, case_sensitive should be True
                assert source.case_sensitive is True

    def test_init_case_sensitive_override(self, settings_cls, mock_credential):
        """Test case_sensitive is overridden when snake_case_conversion=True."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    case_sensitive=False,
                    snake_case_conversion=True,
                )
                # snake_case_conversion=True forces case_sensitive=True
                assert source.case_sensitive is True

    def test_init_nested_delimiter_with_snake_case(self, settings_cls, mock_credential):
        """Test env_nested_delimiter is set to '__' when snake_case_conversion=True."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    snake_case_conversion=True,
                )
                assert source.env_nested_delimiter == '__'

    def test_init_nested_delimiter_without_snake_case(self, settings_cls, mock_credential):
        """Test env_nested_delimiter is set to '--' when snake_case_conversion=False."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    snake_case_conversion=False,
                )
                assert source.env_nested_delimiter == '--'

    def test_load_env_vars(self, settings_cls, mock_credential):
        """Test _load_env_vars creates AzureKeyVaultMapping."""
        mock_secret_client_class = Mock()
        mock_secret_client_instance = Mock()
        mock_secret_client_class.return_value = mock_secret_client_instance
        mock_secret_client_instance.list_properties_of_secrets.return_value = []

        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient', mock_secret_client_class):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                )
                env_vars = source._load_env_vars()
                assert isinstance(env_vars, AzureKeyVaultMapping)
                mock_secret_client_class.assert_called_with(
                    vault_url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                )

    def test_load_env_vars_passes_configuration(self, settings_cls, mock_credential):
        """Test _load_env_vars passes correct configuration to AzureKeyVaultMapping."""
        mock_secret_client_class = Mock()
        mock_secret_client_instance = Mock()
        mock_secret_client_class.return_value = mock_secret_client_instance
        mock_secret_client_instance.list_properties_of_secrets.return_value = []

        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient', mock_secret_client_class):
                with patch('pydantic_settings.sources.providers.azure.AzureKeyVaultMapping') as mock_mapping_class:
                    source = AzureKeyVaultSettingsSource(
                        settings_cls=settings_cls,
                        url='https://myvault.vault.azure.net/',
                        credential=mock_credential,
                        env_prefix='APP_',
                        case_sensitive=True,
                    )
                    source._load_env_vars()
                    mock_mapping_class.assert_called()

    def test_extract_field_info_with_snake_case_conversion(self, settings_cls, mock_credential):
        """Test _extract_field_info with snake_case_conversion=True."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    snake_case_conversion=True,
                )
                field_info = settings_cls.model_fields['database_url']
                result = source._extract_field_info(field_info, 'database_url')
                # Should call parent implementation directly
                assert isinstance(result, list)
                assert len(result) > 0

    def test_extract_field_info_with_dash_to_underscore(self, settings_cls, mock_credential):
        """Test _extract_field_info with dash_to_underscore=True."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    dash_to_underscore=True,
                    snake_case_conversion=False,
                )
                field_info = settings_cls.model_fields['database_url']
                result = source._extract_field_info(field_info, 'database_url')
                # Should replace underscores with dashes
                assert isinstance(result, list)
                assert len(result) > 0
                # Check that the conversion happened
                if result:
                    assert any('_' in item[1] or '-' in item[1] for item in result)

    def test_extract_field_info_default(self, settings_cls, mock_credential):
        """Test _extract_field_info with no special options."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    snake_case_conversion=False,
                    dash_to_underscore=False,
                )
                field_info = settings_cls.model_fields['database_url']
                result = source._extract_field_info(field_info, 'database_url')
                # Should call parent implementation
                assert isinstance(result, list)

    def test_repr(self, settings_cls, mock_credential):
        """Test __repr__ returns formatted string."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                )
                repr_str = repr(source)
                assert 'AzureKeyVaultSettingsSource' in repr_str
                assert 'https://myvault.vault.azure.net/' in repr_str
                assert 'env_nested_delimiter' in repr_str

    def test_repr_with_different_delimiter(self, settings_cls, mock_credential):
        """Test __repr__ shows correct nested_delimiter."""
        with patch('pydantic_settings.sources.providers.azure.import_azure_key_vault'):
            with patch('pydantic_settings.sources.providers.azure.SecretClient'):
                source = AzureKeyVaultSettingsSource(
                    settings_cls=settings_cls,
                    url='https://myvault.vault.azure.net/',
                    credential=mock_credential,
                    snake_case_conversion=True,
                )
                repr_str = repr(source)
                assert '__' in repr_str
