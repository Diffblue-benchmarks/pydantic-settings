"""Tests for SecretsSettingsSource."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings, SecretsSettingsSource
from pydantic_settings.exceptions import SettingsError


class SimpleSettings(BaseSettings):
    my_secret: str = 'default'
    other_field: int = 0


class TestSecretsSettingsSourceInit:
    def test_init_with_secrets_dir(self, tmp_path: Path) -> None:
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        assert source.secrets_dir == tmp_path

    def test_init_without_secrets_dir_uses_config(self) -> None:
        class SettingsWithDir(BaseSettings):
            my_secret: str = 'default'

            model_config = {'secrets_dir': '/some/path'}

        source = SecretsSettingsSource(SettingsWithDir)
        assert source.secrets_dir == '/some/path'

    def test_init_without_secrets_dir_defaults_none(self) -> None:
        source = SecretsSettingsSource(SimpleSettings)
        assert source.secrets_dir is None

    def test_init_case_sensitive(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, case_sensitive=True)
        assert source.case_sensitive is True

    def test_init_env_prefix(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, env_prefix='APP_')
        assert source.env_prefix == 'APP_'

    def test_init_env_ignore_empty(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, env_ignore_empty=True)
        assert source.env_ignore_empty is True

    def test_init_env_parse_none_str(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, env_parse_none_str='null')
        assert source.env_parse_none_str == 'null'

    def test_init_env_parse_enums(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, env_parse_enums=True)
        assert source.env_parse_enums is True


class TestSecretsSettingsSourceCall:
    def test_call_returns_empty_when_secrets_dir_none(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        result = source()
        assert result == {}

    def test_call_warns_when_dir_does_not_exist(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / 'nonexistent'
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=nonexistent)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = source()
        assert result == {}
        assert len(w) == 1
        assert 'does not exist' in str(w[0].message)

    def test_call_returns_empty_when_all_dirs_nonexistent(self, tmp_path: Path) -> None:
        dirs = [tmp_path / 'a', tmp_path / 'b']
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=dirs)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            result = source()
        assert result == {}
        assert len(w) == 2

    def test_call_raises_when_secrets_dir_is_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / 'not_a_dir'
        file_path.write_text('data')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=file_path)
        with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
            source()

    def test_call_reads_secret_from_directory(self, tmp_path: Path) -> None:
        secret_file = tmp_path / 'my_secret'
        secret_file.write_text('secret_value')
        settings = SimpleSettings(_secrets_dir=tmp_path)
        assert settings.my_secret == 'secret_value'

    def test_call_with_multiple_dirs(self, tmp_path: Path) -> None:
        dir1 = tmp_path / 'dir1'
        dir1.mkdir()
        dir2 = tmp_path / 'dir2'
        dir2.mkdir()
        secret1 = dir1 / 'my_secret'
        secret1.write_text('from_dir1')
        settings = SimpleSettings(_secrets_dir=[dir1, dir2])
        assert settings.my_secret == 'from_dir1'

    def test_call_last_dir_wins(self, tmp_path: Path) -> None:
        dir1 = tmp_path / 'dir1'
        dir1.mkdir()
        dir2 = tmp_path / 'dir2'
        dir2.mkdir()
        (dir1 / 'my_secret').write_text('from_dir1')
        (dir2 / 'my_secret').write_text('from_dir2')
        settings = SimpleSettings(_secrets_dir=[dir1, dir2])
        assert settings.my_secret == 'from_dir2'

    def test_call_with_string_path(self, tmp_path: Path) -> None:
        secret_file = tmp_path / 'my_secret'
        secret_file.write_text('string_path_value')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=str(tmp_path))
        result = source()
        assert result.get('my_secret') == 'string_path_value'


class TestFindCasePath:
    def test_find_exact_match(self, tmp_path: Path) -> None:
        (tmp_path / 'MY_SECRET').write_text('val')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'MY_SECRET', case_sensitive=True)
        assert result is not None
        assert result.name == 'MY_SECRET'

    def test_find_case_insensitive_match(self, tmp_path: Path) -> None:
        (tmp_path / 'MY_SECRET').write_text('val')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=False)
        assert result is not None
        assert result.name == 'MY_SECRET'

    def test_find_no_match_case_sensitive(self, tmp_path: Path) -> None:
        (tmp_path / 'MY_SECRET').write_text('val')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=True)
        assert result is None

    def test_find_no_match_at_all(self, tmp_path: Path) -> None:
        (tmp_path / 'other_file').write_text('val')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=False)
        assert result is None

    def test_find_returns_none_empty_dir(self, tmp_path: Path) -> None:
        result = SecretsSettingsSource.find_case_path(tmp_path, 'anything', case_sensitive=True)
        assert result is None

    def test_find_exact_match_preferred_over_case_insensitive(self, tmp_path: Path) -> None:
        (tmp_path / 'my_secret').write_text('exact')
        result = SecretsSettingsSource.find_case_path(tmp_path, 'my_secret', case_sensitive=False)
        assert result is not None
        assert result.name == 'my_secret'


class TestGetFieldValue:
    def test_get_field_value_reads_file(self, tmp_path: Path) -> None:
        (tmp_path / 'my_secret').write_text('  secret_value  ')
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source()
        field = SimpleSettings.model_fields['my_secret']
        value, key, is_complex = source.get_field_value(field, 'my_secret')
        assert value == 'secret_value'
        assert key == 'my_secret'
        assert is_complex is False

    def test_get_field_value_returns_none_when_no_file(self, tmp_path: Path) -> None:
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source()
        field = SimpleSettings.model_fields['my_secret']
        value, key, is_complex = source.get_field_value(field, 'my_secret')
        assert value is None

    def test_get_field_value_warns_when_path_is_directory(self, tmp_path: Path) -> None:
        subdir = tmp_path / 'my_secret'
        subdir.mkdir()
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        with pytest.warns(UserWarning, match='found a directory instead'):
            source()


class TestRepr:
    def test_repr_with_path(self, tmp_path: Path) -> None:
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        repr_str = repr(source)
        assert 'SecretsSettingsSource' in repr_str
        assert str(tmp_path) in repr_str

    def test_repr_with_none(self) -> None:
        source = SecretsSettingsSource(SimpleSettings, secrets_dir=None)
        repr_str = repr(source)
        assert repr_str == "SecretsSettingsSource(secrets_dir=None)"
