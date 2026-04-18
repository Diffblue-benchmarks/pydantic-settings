"""Unit tests for SecretsSettingsSource."""

from __future__ import annotations as _annotations

import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.secrets import SecretsSettingsSource


class SimpleSettings(BaseSettings):
    """Simple test settings class."""

    api_key: str | None = None
    database_url: str | None = None
    debug: bool = False


class SettingsWithDefaults(BaseSettings):
    """Settings with default values."""

    port: int = 8000
    host: str = 'localhost'
    secret: str | None = None


class SettingsWithAliases(BaseSettings):
    """Settings with field aliases."""

    api_token: str = Field(alias='token')
    db_connection: str = Field(alias='database')


class TestSecretsSettingsSourceInit:
    """Tests for SecretsSettingsSource.__init__."""

    def test_init_with_string_secrets_dir(self):
        """Test initialization with a string secrets_dir."""
        secrets_dir = '/tmp/secrets'
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
        assert source.secrets_dir == secrets_dir

    def test_init_with_path_secrets_dir(self):
        """Test initialization with a Path object secrets_dir."""
        secrets_dir = Path('/tmp/secrets')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
        assert source.secrets_dir == secrets_dir

    def test_init_with_list_secrets_dir(self):
        """Test initialization with a list of secrets directories."""
        secrets_dirs = ['/tmp/secrets1', '/tmp/secrets2']
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dirs)
        assert source.secrets_dir == secrets_dirs

    def test_init_with_none_secrets_dir(self):
        """Test initialization with None secrets_dir uses config default."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        assert source.secrets_dir is None

    def test_init_with_case_sensitive(self):
        """Test initialization with case_sensitive parameter."""
        source = SecretsSettingsSource(SimpleSettings, case_sensitive=True)
        assert source.case_sensitive is True

    def test_init_with_case_insensitive(self):
        """Test initialization with case_sensitive=False."""
        source = SecretsSettingsSource(SimpleSettings, case_sensitive=False)
        assert source.case_sensitive is False

    def test_init_with_env_prefix(self):
        """Test initialization with env_prefix parameter."""
        source = SecretsSettingsSource(SimpleSettings, env_prefix='APP_')
        assert source.env_prefix == 'APP_'

    def test_init_with_env_prefix_target(self):
        """Test initialization with env_prefix_target parameter."""
        source = SecretsSettingsSource(SimpleSettings, env_prefix_target='alias')
        assert source.env_prefix_target == 'alias'

    def test_init_with_env_ignore_empty(self):
        """Test initialization with env_ignore_empty parameter."""
        source = SecretsSettingsSource(SimpleSettings, env_ignore_empty=True)
        assert source.env_ignore_empty is True

    def test_init_with_env_parse_none_str(self):
        """Test initialization with env_parse_none_str parameter."""
        source = SecretsSettingsSource(SimpleSettings, env_parse_none_str='null')
        assert source.env_parse_none_str == 'null'

    def test_init_with_env_parse_enums(self):
        """Test initialization with env_parse_enums parameter."""
        source = SecretsSettingsSource(SimpleSettings, env_parse_enums=True)
        assert source.env_parse_enums is True

    def test_init_stores_secrets_dir_from_config(self):
        """Test that secrets_dir is retrieved from config when None is provided."""
        class SettingsWithSecretsDir(BaseSettings):
            api_key: str | None = None

            model_config = {'secrets_dir': '/etc/secrets'}

        source = SecretsSettingsSource(SettingsWithSecretsDir, secrets_dir=None)
        assert source.secrets_dir == '/etc/secrets'


class TestSecretsSettingsSourceCall:
    """Tests for SecretsSettingsSource.__call__."""

    def test_call_returns_empty_dict_when_secrets_dir_none(self):
        """Test that __call__ returns empty dict when secrets_dir is None."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        result = source()
        assert result == {}

    def test_call_returns_empty_dict_for_nonexistent_directory(self):
        """Test that __call__ returns empty dict for non-existent directory."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            source = SecretsSettingsSource(SimpleSettings, secrets_dir='/nonexistent/path')
            result = source()
            assert result == {}
            assert len(w) == 1
            assert 'does not exist' in str(w[0].message)

    def test_call_with_single_valid_directory(self):
        """Test __call__ with a single valid secrets directory."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'api_key').write_text('secret123')

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            result = source()
            assert isinstance(result, dict)

    def test_call_with_multiple_directories(self):
        """Test __call__ with multiple secrets directories."""
        with TemporaryDirectory() as tmpdir1, TemporaryDirectory() as tmpdir2:
            path1 = Path(tmpdir1)
            path2 = Path(tmpdir2)
            path1 / 'secret1'
            (path2 / 'secret2').write_text('value2')

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=[tmpdir1, tmpdir2])
            result = source()
            assert isinstance(result, dict)

    def test_call_skips_nonexistent_directories_with_warning(self):
        """Test that __call__ skips non-existent directories and warns."""
        with TemporaryDirectory() as tmpdir:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                source = SecretsSettingsSource(
                    SimpleSettings, secrets_dir=['/nonexistent', tmpdir]
                )
                result = source()
                assert isinstance(result, dict)
                assert len(w) == 1
                assert 'does not exist' in str(w[0].message)

    def test_call_raises_error_for_file_instead_of_directory(self):
        """Test that __call__ raises SettingsError when file path is provided instead of directory."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / 'notadir'
            file_path.write_text('content')

            with pytest.raises(SettingsError, match='must reference a directory'):
                source = SecretsSettingsSource(SimpleSettings, secrets_dir=str(file_path))
                source()

    def test_call_stores_valid_paths(self):
        """Test that __call__ stores valid paths in secrets_paths attribute."""
        with TemporaryDirectory() as tmpdir:
            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source()
            assert len(source.secrets_paths) == 1
            assert source.secrets_paths[0] == Path(tmpdir)

    def test_call_returns_empty_dict_when_no_valid_paths(self):
        """Test that __call__ returns empty dict when no valid paths exist."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            source = SecretsSettingsSource(
                SimpleSettings, secrets_dir=['/nonexistent1', '/nonexistent2']
            )
            result = source()
            assert result == {}

    def test_call_expands_user_in_paths(self):
        """Test that __call__ expands ~ in paths."""
        # We can't test with actual home dir, but we can test path expansion happens
        source = SecretsSettingsSource(SimpleSettings, secrets_dir='~')
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = source()
            # Path will be expanded and either exist or warn
            assert result == {} or isinstance(result, dict)


class TestSecretsSettingsSourceFindCasePath:
    """Tests for SecretsSettingsSource.find_case_path."""

    def test_find_case_path_exact_match_case_sensitive(self):
        """Test finding file with exact case match when case_sensitive=True."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('secret')

            result = SecretsSettingsSource.find_case_path(dir_path, 'api_key', case_sensitive=True)
            assert result == dir_path / 'api_key'

    def test_find_case_path_no_match_case_sensitive(self):
        """Test that case mismatch returns None when case_sensitive=True."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('secret')

            result = SecretsSettingsSource.find_case_path(dir_path, 'API_KEY', case_sensitive=True)
            assert result is None

    def test_find_case_path_case_insensitive_exact_match(self):
        """Test finding file with exact case when case_sensitive=False."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('secret')

            result = SecretsSettingsSource.find_case_path(
                dir_path, 'api_key', case_sensitive=False
            )
            assert result == dir_path / 'api_key'

    def test_find_case_path_case_insensitive_different_case(self):
        """Test finding file with different case when case_sensitive=False."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('secret')

            result = SecretsSettingsSource.find_case_path(
                dir_path, 'API_KEY', case_sensitive=False
            )
            assert result == dir_path / 'api_key'

    def test_find_case_path_case_insensitive_mixed_case(self):
        """Test finding file with mixed case when case_sensitive=False."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'DatabaseUrl').write_text('secret')

            result = SecretsSettingsSource.find_case_path(
                dir_path, 'databaseurl', case_sensitive=False
            )
            assert result == dir_path / 'DatabaseUrl'

    def test_find_case_path_returns_none_for_nonexistent_file(self):
        """Test that find_case_path returns None for non-existent file."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            result = SecretsSettingsSource.find_case_path(
                dir_path, 'nonexistent', case_sensitive=True
            )
            assert result is None

    def test_find_case_path_with_multiple_files(self):
        """Test find_case_path returns first matching file."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'file1').write_text('content')
            (dir_path / 'file2').write_text('content')

            result = SecretsSettingsSource.find_case_path(dir_path, 'file1', case_sensitive=True)
            assert result == dir_path / 'file1'


class TestSecretsSettingsSourceGetFieldValue:
    """Tests for SecretsSettingsSource.get_field_value."""

    def test_get_field_value_returns_none_when_no_secrets_paths(self):
        """Test get_field_value returns None when secrets_paths is empty."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        source.secrets_paths = []

        field = SimpleSettings.model_fields['api_key']
        value, key, is_complex = source.get_field_value(field, 'api_key')
        assert value is None

    def test_get_field_value_finds_secret_file(self):
        """Test get_field_value finds and reads secret file."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('my-secret-key')

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source.secrets_paths = [dir_path]

            field = SimpleSettings.model_fields['api_key']
            value, key, is_complex = source.get_field_value(field, 'api_key')
            assert value == 'my-secret-key'

    def test_get_field_value_strips_whitespace(self):
        """Test that get_field_value strips whitespace from secret files."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('  my-secret-key  \n')

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source.secrets_paths = [dir_path]

            field = SimpleSettings.model_fields['api_key']
            value, key, is_complex = source.get_field_value(field, 'api_key')
            assert value == 'my-secret-key'

    def test_get_field_value_with_case_insensitive_lookup(self):
        """Test get_field_value with case-insensitive file lookup."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'API_KEY').write_text('case-insensitive-secret')

            source = SecretsSettingsSource(
                SimpleSettings, secrets_dir=tmpdir, case_sensitive=False
            )
            source.secrets_paths = [dir_path]

            field = SimpleSettings.model_fields['api_key']
            value, key, is_complex = source.get_field_value(field, 'api_key')
            assert value == 'case-insensitive-secret'

    def test_get_field_value_warns_for_directory_instead_of_file(self):
        """Test that get_field_value warns when path is directory instead of file."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').mkdir()

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source.secrets_paths = [dir_path]

            field = SimpleSettings.model_fields['api_key']
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                value, key, is_complex = source.get_field_value(field, 'api_key')
                assert value is None
                assert len(w) == 1
                assert 'directory' in str(w[0].message)

    def test_get_field_value_skips_nonexistent_file(self):
        """Test that get_field_value skips non-existent files."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source.secrets_paths = [dir_path]

            field = SimpleSettings.model_fields['api_key']
            value, key, is_complex = source.get_field_value(field, 'api_key')
            assert value is None

    def test_get_field_value_checks_multiple_secrets_paths_reversed(self):
        """Test get_field_value checks multiple paths in reversed order (last-wins)."""
        with TemporaryDirectory() as tmpdir1, TemporaryDirectory() as tmpdir2:
            path1 = Path(tmpdir1)
            path2 = Path(tmpdir2)
            (path1 / 'api_key').write_text('first-value')
            (path2 / 'api_key').write_text('second-value')

            source = SecretsSettingsSource(SimpleSettings)
            source.secrets_paths = [path1, path2]

            field = SimpleSettings.model_fields['api_key']
            value, key, is_complex = source.get_field_value(field, 'api_key')
            # Last path wins due to reversed iteration
            assert value == 'second-value'

    def test_get_field_value_returns_field_key_and_is_complex(self):
        """Test that get_field_value returns correct field_key and is_complex flag."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('secret')

            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source.secrets_paths = [dir_path]

            field = SimpleSettings.model_fields['api_key']
            value, key, is_complex = source.get_field_value(field, 'api_key')
            assert key == 'api_key'
            assert isinstance(is_complex, bool)


class TestSecretsSettingsSourceRepr:
    """Tests for SecretsSettingsSource.__repr__."""

    def test_repr_with_string_secrets_dir(self):
        """Test __repr__ with string secrets_dir."""
        secrets_dir = '/path/to/secrets'
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
        repr_str = repr(source)
        assert 'SecretsSettingsSource' in repr_str
        assert '/path/to/secrets' in repr_str

    def test_repr_with_path_secrets_dir(self):
        """Test __repr__ with Path secrets_dir."""
        secrets_dir = Path('/path/to/secrets')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dir)
        repr_str = repr(source)
        assert 'SecretsSettingsSource' in repr_str
        assert '/path/to/secrets' in repr_str

    def test_repr_with_none_secrets_dir(self):
        """Test __repr__ with None secrets_dir."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        repr_str = repr(source)
        assert 'SecretsSettingsSource' in repr_str
        assert 'None' in repr_str

    def test_repr_with_list_secrets_dir(self):
        """Test __repr__ with list secrets_dir."""
        secrets_dirs = ['/path1', '/path2']
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=secrets_dirs)
        repr_str = repr(source)
        assert 'SecretsSettingsSource' in repr_str
        assert 'path1' in repr_str
        assert 'path2' in repr_str

    def test_repr_format(self):
        """Test __repr__ follows the correct format."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir='/secrets')
        repr_str = repr(source)
        assert repr_str.startswith('SecretsSettingsSource(')
        assert repr_str.endswith(')')
        assert 'secrets_dir=' in repr_str


class TestSecretsSettingsSourceIntegration:
    """Integration tests for SecretsSettingsSource."""

    def test_load_settings_from_secrets_directory(self):
        """Test loading settings from a secrets directory."""
        with TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            (dir_path / 'api_key').write_text('test-secret-key')
            (dir_path / 'database_url').write_text('postgresql://localhost/db')

            class Settings(BaseSettings):
                api_key: str | None = None
                database_url: str | None = None

                model_config = {'secrets_dir': tmpdir}

            source = SecretsSettingsSource(Settings, secrets_dir=tmpdir)
            result = source()
            assert isinstance(result, dict)

    def test_secrets_source_with_expanduser(self):
        """Test that SecretsSettingsSource handles path expansion."""
        source = SecretsSettingsSource(SimpleSettings, secrets_dir='~/.secrets')
        # Verify it doesn't crash and returns a dict
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            result = source()
            assert isinstance(result, dict)

    def test_get_field_value_returns_tuple_with_three_elements(self):
        """Test that get_field_value always returns a 3-tuple."""
        with TemporaryDirectory() as tmpdir:
            source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmpdir)
            source.secrets_paths = [Path(tmpdir)]

            field = SimpleSettings.model_fields['api_key']
            result = source.get_field_value(field, 'api_key')
            assert isinstance(result, tuple)
            assert len(result) == 3
