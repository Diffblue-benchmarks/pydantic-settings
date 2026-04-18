"""Tests for pydantic_settings.main module."""
import asyncio
import io
import sys
import warnings
from typing import Optional

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, CliApp
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources import (
    CliSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)


class TestBaseSettingsInit:
    """Tests for BaseSettings.__init__ method."""

    def test_basic_instantiation(self):
        """Test basic settings instantiation with default values."""

        class MySettings(BaseSettings):
            name: str = 'default'
            value: int = 42

        settings = MySettings()
        assert settings.name == 'default'
        assert settings.value == 42

    def test_instantiation_with_values(self):
        """Test settings instantiation with provided values."""

        class MySettings(BaseSettings):
            name: str = 'default'
            value: int = 0

        settings = MySettings(name='custom', value=100)
        assert settings.name == 'custom'
        assert settings.value == 100

    def test_instantiation_with_env_prefix(self, monkeypatch):
        """Test settings instantiation with env_prefix parameter."""
        monkeypatch.setenv('APP_NAME', 'from_env')

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings(_env_prefix='APP_')
        assert settings.name == 'from_env'

    def test_instantiation_with_case_sensitive(self, monkeypatch):
        """Test settings instantiation with case_sensitive parameter."""
        monkeypatch.setenv('NAME', 'upper_env')
        monkeypatch.setenv('name', 'lower_env')

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings(_case_sensitive=True)
        assert settings.name == 'lower_env'

    def test_instantiation_with_env_nested_delimiter(self, monkeypatch):
        """Test settings instantiation with env_nested_delimiter parameter."""
        monkeypatch.setenv('NESTED__VALUE', 'nested_value')

        class NestedModel(BaseModel):
            value: str = 'default'

        class MySettings(BaseSettings):
            nested: NestedModel = NestedModel()

        settings = MySettings(_env_nested_delimiter='__')
        assert settings.nested.value == 'nested_value'

    def test_instantiation_with_cli_parse_args(self):
        """Test settings instantiation with CLI arguments."""

        class MySettings(BaseSettings):
            name: str = 'default'
            value: int = 0

        settings = MySettings(_cli_parse_args=['--name', 'cli_name', '--value', '50'])
        assert settings.name == 'cli_name'
        assert settings.value == 50

    def test_instantiation_with_build_sources(self):
        """Test settings instantiation with pre-built sources."""

        class MySettings(BaseSettings):
            name: str = 'default'
            value: int = 42

        sources, init_kwargs = MySettings._settings_init_sources()
        settings = MySettings(_build_sources=(sources, init_kwargs))
        assert settings.name == 'default'
        assert settings.value == 42

    def test_instantiation_with_secrets_dir(self, tmp_path):
        """Test settings instantiation with secrets_dir parameter."""
        secrets_dir = tmp_path / 'secrets'
        secrets_dir.mkdir()
        secret_file = secrets_dir / 'api_key'
        secret_file.write_text('secret123')

        class MySettings(BaseSettings):
            api_key: str = 'default'

        settings = MySettings(_secrets_dir=secrets_dir)
        assert settings.api_key == 'secret123'


class TestSettingsCustomiseSources:
    """Tests for BaseSettings.settings_customise_sources method."""

    def test_default_sources_order(self):
        """Test that default sources are returned in correct order."""

        class MySettings(BaseSettings):
            name: str = 'default'

        sources, _ = MySettings._settings_init_sources()

        # Default should return 5 sources: init, env, dotenv, secrets, default
        assert len(sources) == 5

    def test_custom_sources_order(self):
        """Test customizing the order of sources."""

        class MySettings(BaseSettings):
            name: str = 'default'

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            ):
                # Reverse the order
                return file_secret_settings, dotenv_settings, env_settings, init_settings

        sources, _ = MySettings._settings_init_sources()
        # 4 custom + 1 default
        assert len(sources) == 5


class TestSettingsInitSources:
    """Tests for BaseSettings._settings_init_sources method."""

    def test_init_sources_basic(self):
        """Test basic _settings_init_sources call."""

        class MySettings(BaseSettings):
            name: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources()
        assert isinstance(sources, tuple)
        assert isinstance(init_kwargs, dict)

    def test_init_sources_with_cli_settings_source(self):
        """Test _settings_init_sources with custom CLI settings source."""

        class MySettings(BaseSettings):
            name: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=['--name', 'cli_value'])
        sources, _ = MySettings._settings_init_sources(_cli_settings_source=cli_source)

        cli_sources = [s for s in sources if isinstance(s, CliSettingsSource)]
        assert len(cli_sources) >= 1

    def test_init_sources_env_parse_none_str(self, monkeypatch):
        """Test _settings_init_sources with env_parse_none_str."""
        monkeypatch.setenv('NAME', 'null')

        class MySettings(BaseSettings):
            name: Optional[str] = 'default'

        settings = MySettings(_env_parse_none_str='null')
        assert settings.name is None

    def test_init_sources_env_ignore_empty(self, monkeypatch):
        """Test _settings_init_sources with env_ignore_empty."""
        monkeypatch.setenv('NAME', '')

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings(_env_ignore_empty=True)
        assert settings.name == 'default'

    def test_init_sources_env_nested_max_split(self, monkeypatch):
        """Test _settings_init_sources with env_nested_max_split."""
        monkeypatch.setenv('A__B__C', 'value')

        class Inner(BaseModel):
            c: str = 'default'

        class Middle(BaseModel):
            b: Inner = Inner()

        class MySettings(BaseSettings):
            a: Middle = Middle()

        settings = MySettings(_env_nested_delimiter='__', _env_nested_max_split=1)
        # With max_split=1, only first delimiter is split
        assert settings.a.b.c == 'default'

    def test_init_sources_cli_options(self):
        """Test _settings_init_sources with various CLI options."""

        class MySettings(BaseSettings):
            name: str = 'default'

        sources, _ = MySettings._settings_init_sources(
            _cli_parse_args=['--name', 'cli'],
            _cli_prog_name='myapp',
            _cli_hide_none_type=True,
            _cli_avoid_json=True,
            _cli_enforce_required=False,  # Don't enforce required for this test
            _cli_use_class_docs_for_groups=True,
            _cli_exit_on_error=False,
        )

        cli_sources = [s for s in sources if isinstance(s, CliSettingsSource)]
        assert len(cli_sources) == 1


class TestSettingsBuildValues:
    """Tests for BaseSettings._settings_build_values method."""

    def test_build_values_basic(self):
        """Test basic _settings_build_values call."""

        class MySettings(BaseSettings):
            name: str = 'default'
            value: int = 42

        sources, init_kwargs = MySettings._settings_init_sources(name='init_name')
        values = MySettings._settings_build_values(sources, init_kwargs)
        assert 'name' in values
        assert values['name'] == 'init_name'

    def test_build_values_empty_sources(self):
        """Test _settings_build_values with empty sources."""

        class MySettings(BaseSettings):
            name: str = 'default'

        values = MySettings._settings_build_values((), {})
        assert values == {}

    def test_build_values_source_priority(self, monkeypatch):
        """Test that source priority is correct in _settings_build_values."""
        monkeypatch.setenv('NAME', 'env_name')

        class MySettings(BaseSettings):
            name: str = 'default'

        # Init should override env
        settings = MySettings(name='init_name')
        assert settings.name == 'init_name'


class TestSettingsRestoreInitKwargNames:
    """Tests for BaseSettings._settings_restore_init_kwarg_names method."""

    def test_restore_init_kwarg_names_with_alias(self):
        """Test _settings_restore_init_kwarg_names with aliased field."""

        class MySettings(BaseSettings):
            model_config = {'populate_by_name': True}
            my_field: str = Field(default='default', alias='myField')

        sources, init_kwargs = MySettings._settings_init_sources(myField='alias_value')
        state = MySettings._settings_build_values(sources, init_kwargs)

        # The state should have the aliased key name
        assert 'myField' in state or 'my_field' in state

    def test_restore_init_kwarg_names_empty(self):
        """Test _settings_restore_init_kwarg_names with empty state."""

        class MySettings(BaseSettings):
            name: str = 'default'

        MySettings._settings_restore_init_kwarg_names(MySettings, {}, {})
        # No error should be raised


class TestSettingsWarnUnusedConfigKeys:
    """Tests for BaseSettings._settings_warn_unused_config_keys method."""

    def test_warn_unused_json_config(self):
        """Test warning for unused json_file config."""

        class MySettings(BaseSettings):
            model_config = {'json_file': 'config.json'}
            name: str = 'default'

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings()
            json_warnings = [x for x in w if 'json_file' in str(x.message)]
            assert len(json_warnings) >= 1

    def test_warn_unused_yaml_config(self):
        """Test warning for unused yaml_file config."""

        class MySettings(BaseSettings):
            model_config = {'yaml_file': 'config.yaml'}
            name: str = 'default'

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings()
            yaml_warnings = [x for x in w if 'yaml_file' in str(x.message)]
            assert len(yaml_warnings) >= 1

    def test_warn_unused_toml_config(self):
        """Test warning for unused toml_file config."""

        class MySettings(BaseSettings):
            model_config = {'toml_file': 'config.toml'}
            name: str = 'default'

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings()
            toml_warnings = [x for x in w if 'toml_file' in str(x.message)]
            assert len(toml_warnings) >= 1

    def test_warn_unused_pyproject_config(self):
        """Test warning for unused pyproject_toml_depth config."""

        class MySettings(BaseSettings):
            model_config = {'pyproject_toml_depth': 2}
            name: str = 'default'

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings()
            pyproject_warnings = [x for x in w if 'pyproject_toml_depth' in str(x.message)]
            assert len(pyproject_warnings) >= 1

    def test_no_warning_when_source_configured(self):
        """Test no warning when the source is properly configured."""

        class MySettings(BaseSettings):
            model_config = {'json_file': 'config.json'}
            name: str = 'default'

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            ):
                return (
                    init_settings,
                    JsonConfigSettingsSource(settings_cls),
                    env_settings,
                    dotenv_settings,
                    file_secret_settings,
                )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings()
            json_warnings = [x for x in w if 'json_file' in str(x.message)]
            assert len(json_warnings) == 0


class TestCliAppGetBaseSettingsCls:
    """Tests for CliApp._get_base_settings_cls method."""

    def test_get_base_settings_cls_from_base_settings(self):
        """Test _get_base_settings_cls with a BaseSettings subclass."""

        class MySettings(BaseSettings):
            name: str = 'default'

        result = CliApp._get_base_settings_cls(MySettings)
        assert result is MySettings

    def test_get_base_settings_cls_from_base_model(self):
        """Test _get_base_settings_cls with a BaseModel subclass."""

        class MyModel(BaseModel):
            name: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert result.__doc__ == MyModel.__doc__


class TestCliAppRunCliCmd:
    """Tests for CliApp._run_cli_cmd method."""

    def test_run_cli_cmd_no_method(self):
        """Test _run_cli_cmd when method does not exist and not required."""

        class MyModel(BaseModel):
            name: str = 'default'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_run_cli_cmd_missing_required_method(self):
        """Test _run_cli_cmd raises error when required method is missing."""

        class MyModel(BaseModel):
            name: str = 'default'

        model = MyModel()
        with pytest.raises(SettingsError, match='missing.*cli_cmd.*entrypoint'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_run_cli_cmd_sync_method(self):
        """Test _run_cli_cmd with synchronous method."""
        execution_log = []

        class MyModel(BaseModel):
            name: str = 'default'

            def cli_cmd(self):
                execution_log.append('executed')

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert result is model
        assert execution_log == ['executed']

    def test_run_cli_cmd_async_method_no_loop(self):
        """Test _run_cli_cmd with async method when no event loop is running."""
        execution_log = []

        class MyModel(BaseModel):
            name: str = 'default'

            async def cli_cmd(self):
                execution_log.append('executed')

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert result is model
        assert execution_log == ['executed']


class TestCliAppRun:
    """Tests for CliApp.run method."""

    def test_run_base_model(self):
        """Test CliApp.run with a BaseModel subclass."""

        class MyModel(BaseModel):
            name: str = 'default'
            value: int = 42

            def cli_cmd(self):
                pass

        result = CliApp.run(MyModel, cli_args=['--name', 'test'])
        assert result.name == 'test'
        assert result.value == 42

    def test_run_base_settings(self):
        """Test CliApp.run with a BaseSettings subclass."""

        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=['--name', 'test'])
        assert result.name == 'test'

    def test_run_dataclass(self):
        """Test CliApp.run with a pydantic dataclass."""

        @pydantic_dataclass
        class MyDataclass:
            name: str = 'default'
            value: int = 42

            def cli_cmd(self):
                pass

        result = CliApp.run(MyDataclass, cli_args=['--name', 'test'])
        assert result.name == 'test'
        assert result.value == 42

    def test_run_invalid_model_class(self):
        """Test CliApp.run raises error for invalid model class."""

        class NotAModel:
            pass

        with pytest.raises(SettingsError, match='not subclass of BaseModel'):
            CliApp.run(NotAModel, cli_args=[])

    def test_run_with_custom_cli_settings_source(self):
        """Test CliApp.run with custom cli_settings_source."""

        class MyModel(BaseModel):
            name: str = 'default'

            def cli_cmd(self):
                pass

        base_settings_cls = CliApp._get_base_settings_cls(MyModel)
        cli_source = CliSettingsSource(base_settings_cls, cli_parse_args=['--name', 'custom'])

        result = CliApp.run(MyModel, cli_args=['--name', 'override'], cli_settings_source=cli_source)
        assert isinstance(result, MyModel)

    def test_run_with_namespace_cli_args_without_source(self):
        """Test CliApp.run raises error with Namespace args but no cli_settings_source."""
        from argparse import Namespace

        class MyModel(BaseModel):
            name: str = 'default'

        with pytest.raises(SettingsError, match='cli_args.*must be list.*when.*cli_settings_source.*not used'):
            CliApp.run(MyModel, cli_args=Namespace(name='test'))


class TestCliAppRunSubcommand:
    """Tests for CliApp.run_subcommand method."""

    def test_run_subcommand_no_subcommand(self):
        """Test run_subcommand when no subcommand is found."""

        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                pass

        settings = MySettings()
        with pytest.raises((SystemExit, SettingsError)):
            CliApp.run_subcommand(settings, cli_exit_on_error=False)


class TestCliAppSerialize:
    """Tests for CliApp.serialize method."""

    def test_serialize_basic(self):
        """Test basic serialization."""

        class MyModel(BaseModel):
            name: str
            value: int

        model = MyModel(name='test', value=42)
        args = CliApp.serialize(model)
        assert '--name' in args
        assert 'test' in args
        assert '--value' in args
        assert '42' in args

    def test_serialize_list_json_style(self):
        """Test serialization with list in JSON style."""

        class MyModel(BaseModel):
            tags: list[str]

        model = MyModel(tags=['a', 'b'])
        args = CliApp.serialize(model, list_style='json')
        assert '--tags' in args

    def test_serialize_list_argparse_style(self):
        """Test serialization with list in argparse style."""

        class MyModel(BaseModel):
            tags: list[str]

        model = MyModel(tags=['a', 'b'])
        args = CliApp.serialize(model, list_style='argparse')
        assert args.count('--tags') == 2

    def test_serialize_list_lazy_style(self):
        """Test serialization with list in lazy style."""

        class MyModel(BaseModel):
            tags: list[str]

        model = MyModel(tags=['a', 'b'])
        args = CliApp.serialize(model, list_style='lazy')
        assert '--tags' in args
        assert 'a,b' in args

    def test_serialize_dict_json_style(self):
        """Test serialization with dict in JSON style."""

        class MyModel(BaseModel):
            config: dict[str, str]

        model = MyModel(config={'key': 'value'})
        args = CliApp.serialize(model, dict_style='json')
        assert '--config' in args

    def test_serialize_dict_env_style(self):
        """Test serialization with dict in env style."""

        class MyModel(BaseModel):
            config: dict[str, str]

        model = MyModel(config={'key': 'value'})
        args = CliApp.serialize(model, dict_style='env')
        assert '--config' in args


class TestCliAppFormatHelp:
    """Tests for CliApp.format_help method."""

    def test_format_help_from_class(self):
        """Test format_help with model class."""

        class MyModel(BaseModel):
            """My model description."""

            name: str = 'default'

        help_text = CliApp.format_help(MyModel)
        assert 'name' in help_text.lower()

    def test_format_help_from_instance(self):
        """Test format_help with model instance."""

        class MyModel(BaseModel):
            name: str = 'default'

        model = MyModel()
        help_text = CliApp.format_help(model)
        assert 'name' in help_text.lower()

    def test_format_help_strip_ansi_color(self):
        """Test format_help strips ANSI color codes."""

        class MyModel(BaseModel):
            name: str = 'default'

        help_text = CliApp.format_help(MyModel, strip_ansi_color=True)
        # Should not contain ANSI escape codes
        assert '\x1b[' not in help_text

    def test_format_help_with_custom_source(self):
        """Test format_help with custom cli_settings_source."""

        class MyModel(BaseModel):
            name: str = 'default'

        base_settings_cls = CliApp._get_base_settings_cls(MyModel)
        cli_source = CliSettingsSource(base_settings_cls)

        help_text = CliApp.format_help(MyModel, cli_settings_source=cli_source)
        assert 'name' in help_text.lower()


class TestCliAppPrintHelp:
    """Tests for CliApp.print_help method."""

    def test_print_help_to_file(self):
        """Test print_help outputs to specified file."""

        class MyModel(BaseModel):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MyModel, file=output)
        help_text = output.getvalue()
        assert 'name' in help_text.lower()

    def test_print_help_strip_ansi_color(self):
        """Test print_help strips ANSI color codes."""

        class MyModel(BaseModel):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MyModel, file=output, strip_ansi_color=True)
        help_text = output.getvalue()
        assert '\x1b[' not in help_text


class TestBaseSettingsConfigOptions:
    """Tests for various BaseSettings model_config options."""

    def test_env_prefix_target(self, monkeypatch):
        """Test env_prefix_target configuration."""
        monkeypatch.setenv('PREFIX_NAME', 'from_env')

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings(_env_prefix='PREFIX_', _env_prefix_target='variable')
        assert settings.name == 'from_env'

    def test_nested_model_default_partial_update(self, monkeypatch):
        """Test nested_model_default_partial_update configuration."""
        monkeypatch.setenv('NESTED__VALUE', 'updated')

        class NestedModel(BaseModel):
            value: str = 'default'
            other: str = 'other_default'

        class MySettings(BaseSettings):
            nested: NestedModel = NestedModel()

        settings = MySettings(_env_nested_delimiter='__', _nested_model_default_partial_update=True)
        assert settings.nested.value == 'updated'
        assert settings.nested.other == 'other_default'

    def test_cli_implicit_flags(self):
        """Test cli_implicit_flags configuration."""

        class MySettings(BaseSettings):
            flag: bool = False

        settings = MySettings(_cli_parse_args=['--flag'], _cli_implicit_flags=True)
        assert settings.flag is True

    def test_cli_kebab_case(self):
        """Test cli_kebab_case configuration."""

        class MySettings(BaseSettings):
            my_value: str = 'default'

        settings = MySettings(_cli_parse_args=['--my-value', 'test'], _cli_kebab_case=True)
        assert settings.my_value == 'test'

    def test_cli_ignore_unknown_args(self):
        """Test cli_ignore_unknown_args configuration."""

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings(_cli_parse_args=['--name', 'test', '--unknown', 'arg'], _cli_ignore_unknown_args=True)
        assert settings.name == 'test'

    def test_env_parse_enums(self, monkeypatch):
        """Test env_parse_enums configuration."""
        from enum import Enum

        class Color(Enum):
            RED = 'red'
            GREEN = 'green'
            BLUE = 'blue'

        monkeypatch.setenv('COLOR', 'RED')

        class MySettings(BaseSettings):
            color: Color = Color.GREEN

        settings = MySettings(_env_parse_enums=True)
        assert settings.color == Color.RED
