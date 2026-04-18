"""Unit tests for Azure Key Vault settings source."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.azure import AzureKeyVaultMapping, AzureKeyVaultSettingsSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SecretProperties:
    def __init__(self, name: str | None, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled


class _SecretBundle:
    def __init__(self, value: str | None) -> None:
        self.value = value


def _make_client(secrets: list[tuple[str, str | None, bool]]) -> MagicMock:
    """Return a mock SecretClient pre-configured with the given secrets.

    Each entry is (name, value, enabled).
    """
    client = MagicMock()
    client.list_properties_of_secrets.return_value = [_SecretProperties(n, e) for n, _, e in secrets]
    values: dict[str, str | None] = {n: v for n, v, _ in secrets}
    client.get_secret.side_effect = lambda name: _SecretBundle(values.get(name))
    return client


# ---------------------------------------------------------------------------
# import_azure_key_vault
# ---------------------------------------------------------------------------


def test_import_azure_key_vault_sets_globals() -> None:
    import pydantic_settings.sources.providers.azure as azure_module

    try:
        azure_module.import_azure_key_vault()
    except ImportError:
        pytest.skip('azure-keyvault-secrets is not installed')

    assert azure_module.SecretClient is not None
    assert azure_module.TokenCredential is not None
    assert azure_module.ResourceNotFoundError is not None


# ---------------------------------------------------------------------------
# AzureKeyVaultMapping – __init__ / _load_remote
# ---------------------------------------------------------------------------


def test_mapping_init_case_insensitive() -> None:
    client = _make_client([('MySecret', 'val1', True), ('OTHER', 'val2', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert 'mysecret' in mapping._secret_map
    assert 'other' in mapping._secret_map
    assert len(mapping._secret_map) == 2


def test_mapping_init_case_sensitive() -> None:
    client = _make_client([('MySecret', 'val1', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert 'MySecret' in mapping._secret_map
    assert 'mysecret' not in mapping._secret_map


def test_mapping_init_skips_disabled_secrets() -> None:
    client = _make_client([('enabled', 'val1', True), ('disabled', 'val2', False)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert 'enabled' in mapping._secret_map
    assert 'disabled' not in mapping._secret_map


def test_mapping_init_skips_none_name() -> None:
    client = MagicMock()
    client.list_properties_of_secrets.return_value = [
        _SecretProperties(None, True),
        _SecretProperties('valid', True),
    ]
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert 'valid' in mapping._secret_map
    assert len(mapping._secret_map) == 1


def test_mapping_init_snake_case_with_prefix() -> None:
    from pydantic.alias_generators import to_snake

    client = _make_client([('app-myField', 'val', True), ('other-name', 'val2', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=True,
        env_prefix='app-',
    )
    expected_prefixed = f'app-{to_snake("myField")}'
    expected_other = to_snake('other-name')
    assert expected_prefixed in mapping._secret_map
    assert expected_other in mapping._secret_map


def test_mapping_init_snake_case_no_prefix() -> None:
    from pydantic.alias_generators import to_snake

    client = _make_client([('myField', 'val', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=True,
        env_prefix=None,
    )
    assert to_snake('myField') in mapping._secret_map


def test_mapping_init_empty_secrets() -> None:
    client = _make_client([])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert mapping._secret_map == {}


# ---------------------------------------------------------------------------
# AzureKeyVaultMapping – __getitem__
# ---------------------------------------------------------------------------


def test_mapping_getitem_case_insensitive() -> None:
    client = _make_client([('MySecret', 'my_value', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert mapping['mysecret'] == 'my_value'


def test_mapping_getitem_case_sensitive() -> None:
    client = _make_client([('MySecret', 'my_value', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert mapping['MySecret'] == 'my_value'


def test_mapping_getitem_raises_key_error() -> None:
    client = _make_client([('MySecret', 'my_value', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    with pytest.raises(KeyError):
        _ = mapping['nonexistent']


def test_mapping_getitem_caches_loaded_secrets() -> None:
    client = _make_client([('my-secret', 'cached_val', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    first = mapping['my-secret']
    second = mapping['my-secret']
    assert first == second == 'cached_val'
    client.get_secret.assert_called_once_with('my-secret')


def test_mapping_getitem_snake_case_with_prefix() -> None:
    client = _make_client([('app-myField', 'snake_val', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=True,
        env_prefix='app-',
    )
    assert mapping['app-myField'] == 'snake_val'


def test_mapping_getitem_snake_case_no_prefix() -> None:
    client = _make_client([('myField', 'snake_val', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=True,
        env_prefix=None,
    )
    assert mapping['myField'] == 'snake_val'


def test_mapping_getitem_case_insensitive_key() -> None:
    client = _make_client([('UPPER', 'upper_val', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=False,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert mapping['UPPER'] == 'upper_val'


# ---------------------------------------------------------------------------
# AzureKeyVaultMapping – __len__ and __iter__
# ---------------------------------------------------------------------------


def test_mapping_len() -> None:
    client = _make_client([('a', 'v1', True), ('b', 'v2', True), ('c', 'v3', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert len(mapping) == 3


def test_mapping_len_empty() -> None:
    client = _make_client([])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert len(mapping) == 0


def test_mapping_iter() -> None:
    client = _make_client([('a', 'v1', True), ('b', 'v2', True)])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    keys = list(mapping)
    assert set(keys) == {'a', 'b'}


def test_mapping_iter_empty() -> None:
    client = _make_client([])
    mapping = AzureKeyVaultMapping(
        secret_client=client,
        case_sensitive=True,
        snake_case_conversion=False,
        env_prefix=None,
    )
    assert list(mapping) == []


# ---------------------------------------------------------------------------
# Fixtures shared by AzureKeyVaultSettingsSource tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_settings_cls():
    class MySettings(BaseSettings):
        my_field: str = 'default'

    return MySettings


@pytest.fixture()
def mock_azure(mocker):
    """Patch import_azure_key_vault and return a pre-configured mock SecretClient."""
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = []
    mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
    mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)
    return mock_client


# ---------------------------------------------------------------------------
# AzureKeyVaultSettingsSource – __init__
# ---------------------------------------------------------------------------


def test_settings_source_init_defaults(simple_settings_cls, mock_azure) -> None:
    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
    )
    assert source._url == 'https://my-vault.vault.azure.net'
    assert source._credential is credential
    assert source.env_nested_delimiter == '--'
    assert source._dash_to_underscore is False
    assert source._snake_case_conversion is False


def test_settings_source_init_snake_case(simple_settings_cls, mock_azure) -> None:
    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
        snake_case_conversion=True,
    )
    assert source.env_nested_delimiter == '__'
    assert source.case_sensitive is True
    assert source._snake_case_conversion is True


def test_settings_source_init_calls_import(simple_settings_cls, mocker) -> None:
    mock_import = mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = []
    mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)

    credential = MagicMock()
    AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
    )
    mock_import.assert_called_once()


def test_settings_source_init_with_dash_to_underscore(simple_settings_cls, mock_azure) -> None:
    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
        dash_to_underscore=True,
    )
    assert source._dash_to_underscore is True
    assert source.env_nested_delimiter == '--'


def test_settings_source_init_with_env_prefix(simple_settings_cls, mock_azure) -> None:
    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
        env_prefix='APP_',
    )
    assert source.env_prefix == 'APP_'


# ---------------------------------------------------------------------------
# AzureKeyVaultSettingsSource – _load_env_vars
# ---------------------------------------------------------------------------


def test_settings_source_load_env_vars_returns_mapping(simple_settings_cls, mocker) -> None:
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = [_SecretProperties('my-field')]
    mock_client.get_secret.return_value = _SecretBundle('hello')
    mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')
    mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)

    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
    )
    assert isinstance(source.env_vars, AzureKeyVaultMapping)


def test_settings_source_load_env_vars_creates_secret_client(simple_settings_cls, mocker) -> None:
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = []
    mock_cls = mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)
    mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')

    credential = MagicMock()
    AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
    )
    mock_cls.assert_called_once_with(vault_url='https://my-vault.vault.azure.net', credential=credential)


# ---------------------------------------------------------------------------
# AzureKeyVaultSettingsSource – __repr__
# ---------------------------------------------------------------------------


def test_settings_source_repr(simple_settings_cls, mock_azure) -> None:
    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
    )
    r = repr(source)
    assert 'AzureKeyVaultSettingsSource' in r
    assert 'https://my-vault.vault.azure.net' in r
    assert '--' in r


def test_settings_source_repr_snake_case(simple_settings_cls, mock_azure) -> None:
    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
        snake_case_conversion=True,
    )
    r = repr(source)
    assert '__' in r


# ---------------------------------------------------------------------------
# AzureKeyVaultSettingsSource – _extract_field_info
# ---------------------------------------------------------------------------


def test_settings_source_extract_field_info_snake_case(simple_settings_cls, mocker) -> None:
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = []
    mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)
    mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')

    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
        snake_case_conversion=True,
    )
    field = simple_settings_cls.model_fields['my_field']
    result = source._extract_field_info(field, 'my_field')
    assert isinstance(result, list)
    assert all(len(t) == 3 for t in result)


def test_settings_source_extract_field_info_dash_to_underscore(simple_settings_cls, mocker) -> None:
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = []
    mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)
    mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')

    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
        dash_to_underscore=True,
    )
    field = simple_settings_cls.model_fields['my_field']
    result = source._extract_field_info(field, 'my_field')
    assert isinstance(result, list)
    # The env_name (second element) should have underscores replaced with dashes
    for _, env_name, _ in result:
        assert '_' not in env_name


def test_settings_source_extract_field_info_default(simple_settings_cls, mocker) -> None:
    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = []
    mocker.patch('pydantic_settings.sources.providers.azure.SecretClient', return_value=mock_client)
    mocker.patch('pydantic_settings.sources.providers.azure.import_azure_key_vault')

    credential = MagicMock()
    source = AzureKeyVaultSettingsSource(
        settings_cls=simple_settings_cls,
        url='https://my-vault.vault.azure.net',
        credential=credential,
    )
    field = simple_settings_cls.model_fields['my_field']
    result = source._extract_field_info(field, 'my_field')
    assert isinstance(result, list)
    assert all(len(t) == 3 for t in result)
    # env_name should contain the field name
    assert any('my_field' in env_name for _, env_name, _ in result)
