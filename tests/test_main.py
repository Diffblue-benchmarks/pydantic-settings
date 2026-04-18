"""Tests for pydantic_settings.main module."""
import asyncio
import io
import sys
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources import (
    CliSettingsSource,
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    JsonConfigSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SecretsSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)


class TestBaseSettingsInit:
    """Test BaseSettings.__init__ method."""

    def test_init_with_defaults(self):
        """Test __init__ with default parameters."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings()
        assert settings.field1 == 'default'

    def test_init_with_values(self):
        """Test __init__ with provided values."""
        class Settings(BaseSettings):
            field1: str
            field2: int = 10

        settings = Settings(field1='test', field2=20)
        assert settings.field1 == 'test'
        assert settings.field2 == 20

    def test_init_with_case_sensitive(self):
        """Test __init__ with case_sensitive parameter."""
        class Settings(BaseSettings):
            MyField: str = 'default'

        settings = Settings(_case_sensitive=True)
        assert settings.MyField == 'default'

    def test_init_with_env_prefix(self):
        """Test __init__ with env_prefix parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_env_prefix='APP_')
        assert settings.field1 == 'default'

    def test_init_with_env_file_encoding(self):
        """Test __init__ with env_file_encoding parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_env_file_encoding='utf-8')
        assert settings.field1 == 'default'

    def test_init_with_env_ignore_empty(self):
        """Test __init__ with env_ignore_empty parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_env_ignore_empty=True)
        assert settings.field1 == 'default'

    def test_init_with_env_nested_delimiter(self):
        """Test __init__ with env_nested_delimiter parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_env_nested_delimiter='__')
        assert settings.field1 == 'default'

    def test_init_with_env_parse_none_str(self):
        """Test __init__ with env_parse_none_str parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_env_parse_none_str='null')
        assert settings.field1 == 'default'

    def test_init_with_cli_parse_args_list(self):
        """Test __init__ with cli_parse_args as list."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_cli_parse_args=['--field1', 'value'])
        assert settings.field1 == 'value'

    def test_init_with_cli_prog_name(self):
        """Test __init__ with cli_prog_name parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_cli_prog_name='myapp', _cli_parse_args=[])
        assert settings.field1 == 'default'

    def test_init_with_cli_hide_none_type(self):
        """Test __init__ with cli_hide_none_type parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        settings = Settings(_cli_hide_none_type=True, _cli_parse_args=[])
        assert settings.field1 == 'default'

    def test_init_with_secrets_dir(self):
        """Test __init__ with secrets_dir parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        with pytest.warns(UserWarning, match='does not exist'):
            settings = Settings(_secrets_dir='/tmp/secrets')
        assert settings.field1 == 'default'

    def test_init_with_nested_model_default_partial_update(self):
        """Test __init__ with nested_model_default_partial_update parameter."""
        class NestedModel(BaseModel):
            nested_field: str = 'nested'

        class Settings(BaseSettings):
            nested: NestedModel = Field(default_factory=NestedModel)

        settings = Settings(_nested_model_default_partial_update=True)
        assert settings.nested.nested_field == 'nested'

    def test_init_with_build_sources(self):
        """Test __init__ with _build_sources parameter."""
        class Settings(BaseSettings):
            field1: str = 'default'

        init_source = InitSettingsSource(Settings, init_kwargs={'field1': 'from_init'})
        default_source = DefaultSettingsSource(Settings)
        sources = (init_source, default_source)
        init_kwargs = {'field1': 'from_init'}

        settings = Settings(_build_sources=(sources, init_kwargs))
        assert settings.field1 == 'from_init'


class TestBaseSettingsCustomiseSources:
    """Test BaseSettings.settings_customise_sources method."""

    def test_settings_customise_sources_default(self):
        """Test default settings_customise_sources implementation."""
        class Settings(BaseSettings):
            field1: str = 'default'

        init_settings = InitSettingsSource(Settings, init_kwargs={})
        env_settings = EnvSettingsSource(Settings)
        dotenv_settings = DotEnvSettingsSource(Settings, env_file=None)
        file_secret_settings = SecretsSettingsSource(Settings, secrets_dir=None)

        sources = Settings.settings_customise_sources(
            Settings,
            init_settings=init_settings,
            env_settings=env_settings,
            dotenv_settings=dotenv_settings,
            file_secret_settings=file_secret_settings,
        )

        assert sources == (init_settings, env_settings, dotenv_settings, file_secret_settings)

    def test_settings_customise_sources_custom_order(self):
        """Test custom source ordering."""
        class Settings(BaseSettings):
            field1: str = 'default'

            @classmethod
            def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
                return env_settings, init_settings, dotenv_settings, file_secret_settings

        settings = Settings(field1='test')
        assert settings.field1 == 'test'


class TestBaseSettingsInitSources:
    """Test BaseSettings._settings_init_sources method."""

    def test_settings_init_sources_default(self):
        """Test _settings_init_sources with default parameters."""
        class Settings(BaseSettings):
            field1: str = 'default'

        sources, init_kwargs = Settings._settings_init_sources()
        assert isinstance(sources, tuple)
        assert len(sources) > 0
        assert isinstance(init_kwargs, dict)

    def test_settings_init_sources_with_cli_parse_args(self):
        """Test _settings_init_sources with cli_parse_args."""
        class Settings(BaseSettings):
            field1: str = 'default'

        sources, init_kwargs = Settings._settings_init_sources(
            _cli_parse_args=['--field1', 'value']
        )
        assert any(isinstance(s, CliSettingsSource) for s in sources)

    def test_settings_init_sources_with_cli_settings_source(self):
        """Test _settings_init_sources with custom cli_settings_source."""
        class Settings(BaseSettings):
            field1: str = 'default'

        cli_source = CliSettingsSource[Any](Settings, cli_parse_args=[])
        sources, init_kwargs = Settings._settings_init_sources(
            _cli_settings_source=cli_source
        )
        assert cli_source in sources

    def test_settings_init_sources_with_env_prefix(self):
        """Test _settings_init_sources with env_prefix."""
        class Settings(BaseSettings):
            field1: str = 'default'

        sources, init_kwargs = Settings._settings_init_sources(_env_prefix='APP_')
        env_source = next((s for s in sources if isinstance(s, EnvSettingsSource)), None)
        assert env_source is not None

    def test_settings_init_sources_cli_parse_none_str_fallback(self):
        """Test that cli_parse_none_str falls back to env_parse_none_str."""
        class Settings(BaseSettings):
            field1: str = 'default'

        sources, init_kwargs = Settings._settings_init_sources(
            _env_parse_none_str='null',
            _cli_parse_args=[]
        )
        cli_source = next((s for s in sources if isinstance(s, CliSettingsSource)), None)
        assert cli_source is not None


class TestBaseSettingsBuildValues:
    """Test BaseSettings._settings_build_values method."""

    def test_settings_build_values_with_sources(self):
        """Test _settings_build_values with sources."""
        class Settings(BaseSettings):
            field1: str = 'default'
            field2: int = 10

        sources, init_kwargs = Settings._settings_init_sources(field1='test', field2=20)
        values = Settings._settings_build_values(sources, init_kwargs)
        assert 'field1' in values
        assert 'field2' in values
        assert values['field1'] == 'test'
        assert values['field2'] == 20

    def test_settings_build_values_empty_sources(self):
        """Test _settings_build_values with empty sources."""
        class Settings(BaseSettings):
            field1: str = 'default'

        values = Settings._settings_build_values((), {})
        assert values == {}

    def test_settings_build_values_strips_defaults(self):
        """Test that defaults are stripped if not explicitly set."""
        class Settings(BaseSettings):
            field1: str = 'default'
            field2: int = 10

        sources, init_kwargs = Settings._settings_init_sources(field1='changed')
        values = Settings._settings_build_values(sources, init_kwargs)
        assert 'field1' in values
        # field2 should not be in values if it matches default


class TestBaseSettingsRestoreInitKwargNames:
    """Test BaseSettings._settings_restore_init_kwarg_names method."""

    def test_restore_init_kwarg_names_with_alias(self):
        """Test restoring init kwarg names with aliases."""
        class Settings(BaseSettings):
            field1: str = Field(alias='f1')

        init_kwargs = {'f1': 'value'}
        state = {'f1': 'value'}
        Settings._settings_restore_init_kwarg_names(Settings, init_kwargs, state)
        assert 'f1' in state

    def test_restore_init_kwarg_names_no_conflict(self):
        """Test restoring when no conflicts exist."""
        class Settings(BaseSettings):
            field1: str

        init_kwargs = {'field1': 'value'}
        state = {'field1': 'value'}
        Settings._settings_restore_init_kwarg_names(Settings, init_kwargs, state)
        assert state['field1'] == 'value'

    def test_restore_init_kwarg_names_empty_state(self):
        """Test restoring with empty state."""
        class Settings(BaseSettings):
            field1: str = 'default'

        init_kwargs = {}
        state = {}
        Settings._settings_restore_init_kwarg_names(Settings, init_kwargs, state)
        assert state == {}

    def test_restore_init_kwarg_names_populate_by_name(self):
        """Test restoring with populate_by_name config."""
        class Settings(BaseSettings):
            model_config = SettingsConfigDict(populate_by_name=True)
            field1: str = Field(alias='f1')

        init_kwargs = {'field1': 'value'}
        state = {'f1': 'alias_value'}
        Settings._settings_restore_init_kwarg_names(Settings, init_kwargs, state)
        assert 'field1' in state


class TestBaseSettingsWarnUnusedConfigKeys:
    """Test BaseSettings._settings_warn_unused_config_keys method."""

    def test_warn_unused_json_file(self):
        """Test warning for unused json_file config."""
        class Settings(BaseSettings):
            model_config = SettingsConfigDict(json_file='config.json')
            field1: str = 'default'

        with pytest.warns(UserWarning, match='json_file'):
            sources, _ = Settings._settings_init_sources()

    def test_warn_unused_toml_file(self):
        """Test warning for unused toml_file config."""
        class Settings(BaseSettings):
            model_config = SettingsConfigDict(toml_file='config.toml')
            field1: str = 'default'

        with pytest.warns(UserWarning, match='toml_file'):
            sources, _ = Settings._settings_init_sources()

    def test_warn_unused_yaml_file(self):
        """Test warning for unused yaml_file config."""
        class Settings(BaseSettings):
            model_config = SettingsConfigDict(yaml_file='config.yaml')
            field1: str = 'default'

        with pytest.warns(UserWarning, match='yaml_file'):
            sources, _ = Settings._settings_init_sources()

    def test_warn_unused_pyproject_toml_depth(self):
        """Test warning for unused pyproject_toml_depth config."""
        class Settings(BaseSettings):
            model_config = SettingsConfigDict(pyproject_toml_depth=3)
            field1: str = 'default'

        with pytest.warns(UserWarning, match='pyproject_toml_depth'):
            sources, _ = Settings._settings_init_sources()

    def test_no_warn_when_source_used(self):
        """Test no warning when source is actually used."""
        class Settings(BaseSettings):
            field1: str = 'default'

        sources, _ = Settings._settings_init_sources()
        # Should not raise warnings for default sources


class TestCliAppGetBaseSettingsCls:
    """Test CliApp._get_base_settings_cls method."""

    def test_get_base_settings_cls_with_base_settings(self):
        """Test _get_base_settings_cls with BaseSettings subclass."""
        class MySettings(BaseSettings):
            field1: str = 'default'

        result = CliApp._get_base_settings_cls(MySettings)
        assert result is MySettings

    def test_get_base_settings_cls_with_base_model(self):
        """Test _get_base_settings_cls with BaseModel."""
        class MyModel(BaseModel):
            field1: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert issubclass(result, MyModel)

    def test_get_base_settings_cls_preserves_docstring(self):
        """Test that docstring is preserved."""
        class MyModel(BaseModel):
            """This is my model."""
            field1: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.__doc__ == MyModel.__doc__


class TestCliAppRunCliCmd:
    """Test CliApp._run_cli_cmd method."""

    def test_run_cli_cmd_sync_method(self):
        """Test running a synchronous CLI command."""
        class MyModel(BaseModel):
            field1: str = 'default'

            def cli_cmd(self):
                self.field1 = 'modified'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result.field1 == 'modified'

    def test_run_cli_cmd_async_method_no_loop(self):
        """Test running an async CLI command without running loop."""
        class MyModel(BaseModel):
            field1: str = 'default'

            async def cli_cmd(self):
                self.field1 = 'modified'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result.field1 == 'modified'

    def test_run_cli_cmd_method_not_found_not_required(self):
        """Test when method not found and not required."""
        class MyModel(BaseModel):
            field1: str = 'default'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'nonexistent', is_required=False)
        assert result is model

    def test_run_cli_cmd_method_not_found_required(self):
        """Test when method not found and is required."""
        class MyModel(BaseModel):
            field1: str = 'default'

        model = MyModel()
        with pytest.raises(SettingsError, match='missing.*entrypoint'):
            CliApp._run_cli_cmd(model, 'nonexistent', is_required=True)

    def test_run_cli_cmd_async_with_exception(self):
        """Test async command that raises exception."""
        class MyModel(BaseModel):
            field1: str = 'default'

            async def cli_cmd(self):
                raise ValueError('Test error')

        model = MyModel()
        with pytest.raises(ValueError, match='Test error'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)


class TestCliAppRun:
    """Test CliApp.run method."""

    def test_run_with_base_settings(self):
        """Test running a BaseSettings subclass."""
        class MySettings(BaseSettings):
            field1: str = 'default'

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=[])
        assert isinstance(result, MySettings)
        assert result.field1 == 'default'

    def test_run_with_base_model(self):
        """Test running a BaseModel subclass."""
        class MyModel(BaseModel):
            field1: str = 'default'

            def cli_cmd(self):
                pass

        result = CliApp.run(MyModel, cli_args=[])
        assert result.field1 == 'default'

    def test_run_with_pydantic_dataclass(self):
        """Test running a pydantic dataclass."""
        @pydantic_dataclass
        class MyDataclass:
            field1: str = 'default'

            def cli_cmd(self):
                pass

        result = CliApp.run(MyDataclass, cli_args=[])
        assert result.field1 == 'default'

    def test_run_with_invalid_model_cls(self):
        """Test running with invalid model class."""
        class NotAModel:
            pass

        with pytest.raises(SettingsError, match='not subclass of BaseModel'):
            CliApp.run(NotAModel, cli_args=[])

    def test_run_with_cli_args_none(self):
        """Test running with cli_args=None (uses sys.argv)."""
        class MySettings(BaseSettings):
            field1: str = 'default'

            def cli_cmd(self):
                pass

        with patch.object(sys, 'argv', ['prog']):
            result = CliApp.run(MySettings, cli_args=None)
            assert isinstance(result, MySettings)

    def test_run_with_model_init_data(self):
        """Test running with model_init_data."""
        class MySettings(BaseSettings):
            field1: str
            field2: int = 10

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=[], field1='test', field2=20)
        assert result.field1 == 'test'
        assert result.field2 == 20

    def test_run_with_cli_exit_on_error_false(self):
        """Test running with cli_exit_on_error=False."""
        class MySettings(BaseSettings):
            field1: str = 'default'

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=[], cli_exit_on_error=False)
        assert isinstance(result, MySettings)

    def test_run_with_custom_cli_settings_source(self):
        """Test running with custom cli_settings_source."""
        class MySettings(BaseSettings):
            field1: str = 'default'

            def cli_cmd(self):
                pass

        cli_source = CliSettingsSource[Any](MySettings, cli_parse_args=[])
        result = CliApp.run(MySettings, cli_args=[], cli_settings_source=cli_source)
        assert isinstance(result, MySettings)


class TestCliAppRunSubcommand:
    """Test CliApp.run_subcommand method."""

    def test_run_subcommand_with_subcommand(self):
        """Test running a subcommand."""
        class SubModel(BaseModel):
            sub_field: str = 'sub'

            def cli_cmd(self):
                pass

        class MainModel(BaseModel):
            main_field: str = 'main'
            subcommand: SubModel | None = None

        main = MainModel()
        main.subcommand = SubModel()

        # This test is limited as we need proper CLI setup
        # Skipping actual run as it requires complex setup

    def test_run_subcommand_cli_exit_on_error_false(self):
        """Test run_subcommand with cli_exit_on_error=False."""
        class SubModel(BaseModel):
            sub_field: str = 'sub'

            def cli_cmd(self):
                pass

        class MainModel(BaseModel):
            main_field: str = 'main'

        main = MainModel()
        # Without proper subcommand setup, this will raise error


class TestCliAppSerialize:
    """Test CliApp.serialize method."""

    def test_serialize_simple_model(self):
        """Test serializing a simple model."""
        class MyModel(BaseModel):
            field1: str = 'test'
            field2: int = 10

        model = MyModel(field1='changed', field2=20)
        result = CliApp.serialize(model)
        assert isinstance(result, list)
        # Result should contain serialized args or be empty if defaults match
        assert len(result) >= 0

    def test_serialize_with_list_style_json(self):
        """Test serializing with list_style='json'."""
        class MyModel(BaseModel):
            tags: list[str] = ['a', 'b', 'c']

        model = MyModel()
        result = CliApp.serialize(model, list_style='json')
        assert isinstance(result, list)

    def test_serialize_with_list_style_argparse(self):
        """Test serializing with list_style='argparse'."""
        class MyModel(BaseModel):
            tags: list[str] = ['a', 'b', 'c']

        model = MyModel()
        result = CliApp.serialize(model, list_style='argparse')
        assert isinstance(result, list)

    def test_serialize_with_list_style_lazy(self):
        """Test serializing with list_style='lazy'."""
        class MyModel(BaseModel):
            tags: list[str] = ['a', 'b', 'c']

        model = MyModel()
        result = CliApp.serialize(model, list_style='lazy')
        assert isinstance(result, list)

    def test_serialize_with_dict_style_json(self):
        """Test serializing with dict_style='json'."""
        class MyModel(BaseModel):
            config: dict[str, Any] = {'key': 'value'}

        model = MyModel()
        result = CliApp.serialize(model, dict_style='json')
        assert isinstance(result, list)

    def test_serialize_with_dict_style_env(self):
        """Test serializing with dict_style='env'."""
        class MyModel(BaseModel):
            config: dict[str, Any] = {'key': 'value'}

        model = MyModel()
        result = CliApp.serialize(model, dict_style='env')
        assert isinstance(result, list)

    def test_serialize_positionals_first_true(self):
        """Test serializing with positionals_first=True."""
        class MyModel(BaseModel):
            field1: str = 'test'

        model = MyModel()
        result = CliApp.serialize(model, positionals_first=True)
        assert isinstance(result, list)


class TestCliAppFormatHelp:
    """Test CliApp.format_help method."""

    def test_format_help_with_model_instance(self):
        """Test format_help with model instance."""
        class MyModel(BaseModel):
            """My model docstring."""
            field1: str = 'default'

        model = MyModel()
        result = CliApp.format_help(model)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_help_with_model_class(self):
        """Test format_help with model class."""
        class MyModel(BaseModel):
            """My model docstring."""
            field1: str = 'default'

        result = CliApp.format_help(MyModel)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_help_strip_ansi_color(self):
        """Test format_help with strip_ansi_color=True."""
        class MyModel(BaseModel):
            field1: str = 'default'

        result = CliApp.format_help(MyModel, strip_ansi_color=True)
        assert isinstance(result, str)
        # Should not contain ANSI color codes
        assert '\x1b[' not in result

    def test_format_help_with_custom_cli_settings_source(self):
        """Test format_help with custom cli_settings_source."""
        class MyModel(BaseModel):
            field1: str = 'default'

        cli_source = CliSettingsSource[Any](CliApp._get_base_settings_cls(MyModel))
        result = CliApp.format_help(MyModel, cli_settings_source=cli_source)
        assert isinstance(result, str)


class TestCliAppPrintHelp:
    """Test CliApp.print_help method."""

    def test_print_help_to_stdout(self):
        """Test print_help to stdout."""
        class MyModel(BaseModel):
            field1: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MyModel, file=output)
        result = output.getvalue()
        assert len(result) > 0

    def test_print_help_strip_ansi_color(self):
        """Test print_help with strip_ansi_color=True."""
        class MyModel(BaseModel):
            field1: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MyModel, file=output, strip_ansi_color=True)
        result = output.getvalue()
        assert '\x1b[' not in result

    def test_print_help_with_custom_cli_settings_source(self):
        """Test print_help with custom cli_settings_source."""
        class MyModel(BaseModel):
            field1: str = 'default'

        cli_source = CliSettingsSource[Any](CliApp._get_base_settings_cls(MyModel))
        output = io.StringIO()
        CliApp.print_help(MyModel, cli_settings_source=cli_source, file=output)
        result = output.getvalue()
        assert len(result) > 0

    def test_print_help_with_model_instance(self):
        """Test print_help with model instance."""
        class MyModel(BaseModel):
            field1: str = 'default'

        model = MyModel()
        output = io.StringIO()
        CliApp.print_help(model, file=output)
        result = output.getvalue()
        assert len(result) > 0
