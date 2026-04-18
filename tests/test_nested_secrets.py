"""Tests for NestedSecretsSettingsSource."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

from pydantic_settings import BaseSettings, NestedSecretsSettingsSource, SecretsSettingsSource
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.providers.nested_secrets import first_not_none


class SimpleSettings(BaseSettings):
    my_secret: str = 'default'
    other_field: int = 0


class TestFirstNotNone:
    def test_returns_first_non_none(self) -> None:
        assert first_not_none(None, None, 'a', 'b') == 'a'

    def test_returns_none_when_all_none(self) -> None:
        assert first_not_none(None, None, None) is None

    def test_returns_first_arg_if_not_none(self) -> None:
        assert first_not_none('x', 'y') == 'x'

    def test_returns_false_not_none(self) -> None:
        assert first_not_none(None, False, 'a') is False

    def test_returns_zero_not_none(self) -> None:
        assert first_not_none(None, 0, 'a') == 0

    def test_empty_args(self) -> None:
        assert first_not_none() is None


class TestNestedSecretsRepr:
    def test_repr_with_path(self, tmp_path: Path) -> None:
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path),
            secrets_dir=tmp_path,
        )
        assert repr(source) == f'NestedSecretsSettingsSource(secrets_dir={tmp_path!r})'

    def test_repr_with_none(self) -> None:
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
        )
        assert repr(source) == 'NestedSecretsSettingsSource(secrets_dir=None)'


class TestLoadSecrets:
    def test_load_secrets_reads_files(self, tmp_path: Path) -> None:
        (tmp_path / 'key1').write_text('value1')
        (tmp_path / 'key2').write_text('value2  ')
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {'key1': 'value1', 'key2': 'value2'}

    def test_load_secrets_empty_dir(self, tmp_path: Path) -> None:
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {}

    def test_load_secrets_nested_files(self, tmp_path: Path) -> None:
        subdir = tmp_path / 'sub'
        subdir.mkdir()
        (subdir / 'nested_key').write_text('nested_value')
        result = NestedSecretsSettingsSource.load_secrets(tmp_path)
        assert result == {str(Path('sub') / 'nested_key'): 'nested_value'}


class TestValidateSecretsPath:
    def test_missing_dir_ok(self, tmp_path: Path) -> None:
        missing = tmp_path / 'nonexistent'
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=missing,
            secrets_dir_missing='ok',
        )
        assert source.secrets_paths == [missing.expanduser().resolve()]

    def test_missing_dir_warn(self, tmp_path: Path) -> None:
        missing = tmp_path / 'nonexistent'
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=missing,
                secrets_dir_missing='warn',
            )
        assert len(w) == 1
        assert 'does not exist' in str(w[0].message)

    def test_missing_dir_error(self, tmp_path: Path) -> None:
        missing = tmp_path / 'nonexistent'
        with pytest.raises(SettingsError, match='does not exist'):
            NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=missing,
                secrets_dir_missing='error',
            )

    def test_path_is_file_raises(self, tmp_path: Path) -> None:
        filepath = tmp_path / 'afile'
        filepath.write_text('content')
        with pytest.raises(SettingsError, match='secrets_dir must reference a directory'):
            NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=filepath,
            )

    def test_dir_too_large(self, tmp_path: Path) -> None:
        bigfile = tmp_path / 'bigfile'
        bigfile.write_text('x' * 100)
        with pytest.raises(SettingsError, match='secrets_dir size is above'):
            NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=tmp_path,
                secrets_dir_max_size=50,
            )


class TestNestedSecretsInit:
    def test_init_with_settings_cls_directly(self, tmp_path: Path) -> None:
        """NestedSecretsSettingsSource can accept settings_cls as the first argument."""
        (tmp_path / 'my_secret').write_text('from_file')
        source = NestedSecretsSettingsSource(
            SimpleSettings,  # type: ignore[arg-type]
            secrets_dir=tmp_path,
        )
        assert source.secrets_dir == tmp_path

    def test_init_with_secrets_source(self, tmp_path: Path) -> None:
        (tmp_path / 'my_secret').write_text('from_file')
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source = NestedSecretsSettingsSource(
            secrets_source,
            secrets_dir=tmp_path,
        )
        assert source.secrets_dir == tmp_path

    def test_secrets_dir_none_gives_empty_env_vars(self) -> None:
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=None,
        )
        assert source.env_vars == {}

    def test_secrets_dir_from_config(self, tmp_path: Path) -> None:
        (tmp_path / 'my_secret').write_text('from_config')

        class SettingsWithConfig(BaseSettings):
            my_secret: str = 'default'
            model_config = {'secrets_dir': str(tmp_path)}

        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SettingsWithConfig, secrets_dir=tmp_path),
        )
        assert 'my_secret' in source.env_vars

    def test_secrets_dir_from_source_overrides_arg(self, tmp_path: Path) -> None:
        """secrets_dir from SecretsSettingsSource takes priority."""
        (tmp_path / 'my_secret').write_text('val')
        other = tmp_path / 'other'
        other.mkdir()
        secrets_source = SecretsSettingsSource(SimpleSettings, secrets_dir=tmp_path)
        source = NestedSecretsSettingsSource(
            secrets_source,
            secrets_dir=other,
        )
        # source from SecretsSettingsSource takes precedence
        assert source.secrets_dir == tmp_path

    def test_case_sensitive(self, tmp_path: Path) -> None:
        (tmp_path / 'MY_SECRET').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
            secrets_case_sensitive=True,
        )
        assert source.case_sensitive is True
        assert 'MY_SECRET' in source.env_vars

    def test_case_insensitive_default(self, tmp_path: Path) -> None:
        (tmp_path / 'MY_SECRET').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
        )
        assert source.case_sensitive is False
        assert 'my_secret' in source.env_vars

    def test_secrets_prefix(self, tmp_path: Path) -> None:
        (tmp_path / 'APP_my_secret').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
            secrets_prefix='APP_',
        )
        assert source.secrets_prefix == 'APP_'

    def test_secrets_prefix_from_env_prefix(self, tmp_path: Path) -> None:
        (tmp_path / 'APP_my_secret').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
            env_prefix='APP_',
        )
        assert source.secrets_prefix == 'APP_'

    def test_secrets_nested_delimiter(self, tmp_path: Path) -> None:
        (tmp_path / 'a__b').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
            secrets_nested_delimiter='__',
        )
        assert source.secrets_nested_delimiter == '__'

    def test_secrets_nested_subdir(self, tmp_path: Path) -> None:
        subdir = tmp_path / 'sub'
        subdir.mkdir()
        (subdir / 'key').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
            secrets_nested_subdir=True,
        )
        assert source.secrets_nested_delimiter == os.sep
        assert source.secrets_nested_subdir is True

    def test_nested_delimiter_and_subdir_mutually_exclusive(self, tmp_path: Path) -> None:
        with pytest.raises(SettingsError, match='mutually exclusive'):
            NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=tmp_path,
                secrets_nested_delimiter='__',
                secrets_nested_subdir=True,
            )

    def test_invalid_secrets_dir_missing(self, tmp_path: Path) -> None:
        with pytest.raises(SettingsError, match='invalid secrets_dir_missing value'):
            NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=tmp_path,
                secrets_dir_missing='invalid',  # type: ignore[arg-type]
            )

    def test_secrets_dir_max_size_from_config(self, tmp_path: Path) -> None:
        class SettingsWithMaxSize(BaseSettings):
            my_secret: str = 'default'
            model_config = {'secrets_dir_max_size': 1024}

        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SettingsWithMaxSize),
            secrets_dir=tmp_path,
        )
        assert source.secrets_dir_max_size == 1024

    def test_multiple_secrets_dirs(self, tmp_path: Path) -> None:
        dir1 = tmp_path / 'dir1'
        dir1.mkdir()
        (dir1 / 'key1').write_text('val1')
        dir2 = tmp_path / 'dir2'
        dir2.mkdir()
        (dir2 / 'key2').write_text('val2')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=[dir1, dir2],
        )
        assert 'key1' in source.env_vars
        assert 'key2' in source.env_vars

    def test_env_vars_populated_from_secrets(self, tmp_path: Path) -> None:
        (tmp_path / 'my_secret').write_text('secret_value')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SimpleSettings),
            secrets_dir=tmp_path,
        )
        assert source.env_vars.get('my_secret') == 'secret_value'

    def test_secrets_dir_missing_default_is_warn(self, tmp_path: Path) -> None:
        missing = tmp_path / 'nonexistent'
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            source = NestedSecretsSettingsSource(
                SecretsSettingsSource(SimpleSettings),
                secrets_dir=missing,
            )
        assert len(w) == 1
        assert source.secrets_dir_missing == 'warn'

    def test_case_sensitive_from_config(self, tmp_path: Path) -> None:
        class CaseSensitiveSettings(BaseSettings):
            my_secret: str = 'default'
            model_config = {'secrets_case_sensitive': True}

        (tmp_path / 'MY_SECRET').write_text('val')
        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(CaseSensitiveSettings),
            secrets_dir=tmp_path,
        )
        assert source.case_sensitive is True

    def test_nested_delimiter_from_env_nested_delimiter_config(self, tmp_path: Path) -> None:
        class DelimSettings(BaseSettings):
            my_secret: str = 'default'
            model_config = {'env_nested_delimiter': '__'}

        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(DelimSettings),
            secrets_dir=tmp_path,
        )
        assert source.secrets_nested_delimiter == '__'

    def test_secrets_nested_subdir_from_config(self, tmp_path: Path) -> None:
        class SubdirSettings(BaseSettings):
            my_secret: str = 'default'
            model_config = {'secrets_nested_subdir': True}

        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(SubdirSettings),
            secrets_dir=tmp_path,
        )
        assert source.secrets_nested_subdir is True
        assert source.secrets_nested_delimiter == os.sep

    def test_secrets_prefix_from_config(self, tmp_path: Path) -> None:
        class PrefixSettings(BaseSettings):
            my_secret: str = 'default'
            model_config = {'secrets_prefix': 'APP_'}

        source = NestedSecretsSettingsSource(
            SecretsSettingsSource(PrefixSettings),
            secrets_dir=tmp_path,
        )
        assert source.secrets_prefix == 'APP_'
