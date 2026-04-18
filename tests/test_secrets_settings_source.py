"""Tests for SecretsSettingsSource."""

import warnings
from pathlib import Path
from typing import Optional

import pytest
from pydantic import Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple settings model for testing."""

    api_key: str = ''
    database_url: str = ''
    optional_value: Optional[str] = None


class TestSecretsSettingsSourceInit:
    """Tests for SecretsSettingsSource.__init__."""

    def test_init_with_secrets_dir(self, tmp_path: Path) -> None:
        """Test initialization with an explicit secrets_dir."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        assert source.secrets_dir == tmp_path

    def test_init_with_none_secrets_dir(self) -> None:
        """Test initialization with None secrets_dir uses config default."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        assert source.secrets_dir is None

    def test_init_with_case_sensitive(self, tmp_path: Path) -> None:
        """Test initialization with case_sensitive parameter."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path, case_sensitive=True)
        assert source.case_sensitive is True

    def test_init_with_env_prefix(self, tmp_path: Path) -> None:
        """Test initialization with env_prefix parameter."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path, env_prefix='APP_')
        assert source.env_prefix == 'APP_'

    def test_init_with_multiple_params(self, tmp_path: Path) -> None:
        """Test initialization with multiple configuration parameters."""
        source = SecretsSettingsSource(
            SimpleSettings,
            secrets_dir=tmp_path,
            case_sensitive=True,
            env_prefix='PREFIX_',
            env_ignore_empty=True,
            env_parse_none_str='null',
        )
        assert source.secrets_dir == tmp_path
        assert source.case_sensitive is True
        assert source.env_prefix == 'PREFIX_'
        assert source.env_ignore_empty is True
        assert source.env_parse_none_str == 'null'


class TestSecretsSettingsSourceCall:
    """Tests for SecretsSettingsSource.__call__."""

    def test_call_with_no_secrets_dir(self) -> None:
        """Test __call__ returns empty dict when secrets_dir is None."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        result = source()
        assert result == {}

    def test_call_with_nonexistent_secrets_dir(self, tmp_path: Path) -> None:
        """Test __call__ warns and returns empty dict when secrets_dir does not exist."""
        nonexistent = tmp_path / 'nonexistent'
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=nonexistent)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = source()
            assert result == {}
            assert len(w) == 1
            assert 'does not exist' in str(w[0].message)

    def test_call_with_file_instead_of_dir(self, tmp_path: Path) -> None:
        """Test __call__ raises error when secrets_dir is a file, not a directory."""
        secret_file = tmp_path / 'secret_file'
        secret_file.write_text('value')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secret_file)
        with pytest.raises(SettingsError) as exc_info:
            source()
        assert 'must reference a directory' in str(exc_info.value)

    def test_call_with_valid_secrets_dir(self, tmp_path: Path) -> None:
        """Test __call__ loads secrets from a valid directory."""
        secret_file = tmp_path / 'api_key'
        secret_file.write_text('my-secret-key')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        result = source()
        assert result.get('api_key') == 'my-secret-key'

    def test_call_with_multiple_secrets(self, tmp_path: Path) -> None:
        """Test __call__ loads multiple secrets from a directory."""
        (tmp_path / 'api_key').write_text('key123')
        (tmp_path / 'database_url').write_text('postgres://localhost/db')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        result = source()
        assert result.get('api_key') == 'key123'
        assert result.get('database_url') == 'postgres://localhost/db'

    def test_call_with_multiple_secrets_dirs(self, tmp_path: Path) -> None:
        """Test __call__ with multiple secrets directories."""
        dir1 = tmp_path / 'secrets1'
        dir1.mkdir()
        dir2 = tmp_path / 'secrets2'
        dir2.mkdir()
        (dir1 / 'api_key').write_text('key1')
        (dir2 / 'api_key').write_text('key2')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=[dir1, dir2])
        result = source()
        assert result.get('api_key') == 'key2'

    def test_call_strips_whitespace_from_secrets(self, tmp_path: Path) -> None:
        """Test __call__ strips whitespace from secret values."""
        secret_file = tmp_path / 'api_key'
        secret_file.write_text('  my-secret-key  \n')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        result = source()
        assert result.get('api_key') == 'my-secret-key'


class TestFindCasePath:
    """Tests for SecretsSettingsSource.find_case_path."""

    def test_find_case_path_exact_match(self, tmp_path: Path) -> None:
        """Test find_case_path returns file with exact name match."""
        secret_file = tmp_path / 'my_secret'
        secret_file.write_text('value')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=True)
        assert result == secret_file

    def test_find_case_path_case_sensitive_no_match(self, tmp_path: Path) -> None:
        """Test find_case_path returns None for case mismatch when case_sensitive=True."""
        secret_file = tmp_path / 'MY_SECRET'
        secret_file.write_text('value')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=True)
        assert result is None

    def test_find_case_path_case_insensitive_match(self, tmp_path: Path) -> None:
        """Test find_case_path returns file when case_sensitive=False."""
        secret_file = tmp_path / 'MY_SECRET'
        secret_file.write_text('value')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=False)
        assert result == secret_file

    def test_find_case_path_not_found(self, tmp_path: Path) -> None:
        """Test find_case_path returns None when file does not exist."""
        result = SecretsSettingsSource.find_case_path(tmp_path, 'nonexistent', case_sensitive=True)
        assert result is None


class TestGetFieldValue:
    """Tests for SecretsSettingsSource.get_field_value."""

    def test_get_field_value_with_secret_file(self, tmp_path: Path) -> None:
        """Test get_field_value returns value from secret file."""
        secret_file = tmp_path / 'api_key'
        secret_file.write_text('secret123')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source()
        field_info = SimpleSettings.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value == 'secret123'

    def test_get_field_value_file_not_found(self, tmp_path: Path) -> None:
        """Test get_field_value returns None when secret file does not exist."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source()
        field_info = SimpleSettings.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field_info, 'api_key')
        assert value is None

    def test_get_field_value_warns_on_directory(self, tmp_path: Path) -> None:
        """Test get_field_value warns when secret path is a directory."""
        secret_dir = tmp_path / 'api_key'
        secret_dir.mkdir()
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            source()
            assert any('found a directory instead' in str(warning.message) for warning in w)


class TestSecretsSettingsSourceRepr:
    """Tests for SecretsSettingsSource.__repr__."""

    def test_repr_with_secrets_dir(self, tmp_path: Path) -> None:
        """Test __repr__ shows secrets_dir."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        result = repr(source)
        assert 'SecretsSettingsSource' in result
        assert str(tmp_path) in result

    def test_repr_with_none_secrets_dir(self) -> None:
        """Test __repr__ shows None for secrets_dir."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        result = repr(source)
        assert 'SecretsSettingsSource' in result
        assert 'None' in result


class TestSecretsSettingsIntegration:
    """Integration tests for SecretsSettingsSource with BaseSettings."""

    def test_basesettings_loads_from_secrets_dir(self, tmp_path: Path) -> None:
        """Test that BaseSettings can load values from a secrets directory."""
        (tmp_path / 'api_key').write_text('integration-test-key')

        class IntegrationSettings(BaseSettings):
            api_key: str = ''
            model_config = {'secrets_dir': tmp_path}

        settings = IntegrationSettings()
        assert settings.api_key == 'integration-test-key'

    def test_basesettings_with_env_prefix(self, tmp_path: Path) -> None:
        """Test that BaseSettings respects env_prefix with secrets."""
        (tmp_path / 'APP_api_key').write_text('prefixed-key')

        class PrefixedSettings(BaseSettings):
            api_key: str = ''
            model_config = {'secrets_dir': tmp_path, 'env_prefix': 'APP_'}

        settings = PrefixedSettings()
        assert settings.api_key == 'prefixed-key'

    def test_basesettings_with_init_override(self, tmp_path: Path) -> None:
        """Test that init values override secrets."""
        (tmp_path / 'api_key').write_text('secret-key')

        class OverrideSettings(BaseSettings):
            api_key: str = ''
            model_config = {'secrets_dir': tmp_path}

        settings = OverrideSettings(api_key='init-override-key')
        assert settings.api_key == 'init-override-key'
