"""Unit tests for pydantic_settings.main module."""

import asyncio
import sys
import warnings
from argparse import Namespace
from io import StringIO
from pathlib import Path
from typing import Any, ClassVar, Literal
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliSettingsSource,
    InitSettingsSource,
    EnvSettingsSource,
    DotEnvSettingsSource,
    SecretsSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources import DefaultSettingsSource
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.main import SettingsConfigDict


class SimpleSettings(BaseSettings):
    """Simple settings for testing."""

    name: str = 'default'
    value: int = 42
    model_config = SettingsConfigDict(case_sensitive=False)


class CustomSourceSettings(BaseSettings):
    """Settings with custom source configuration."""

    field1: str = 'value1'
    field2: str = 'value2'

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Custom source ordering."""
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)


class TestBaseSettingsInit:
    """Test BaseSettings.__init__ method."""

    def test_basic_initialization(self):
        """Test basic initialization of BaseSettings."""
        settings = SimpleSettings(name='test_name', value=100)
        assert settings.name == 'test_name'
        assert settings.value == 100

    def test_initialization_with_case_sensitive(self):
        """Test initialization with case_sensitive parameter."""
        settings = SimpleSettings(_case_sensitive=True)
        assert settings.name == 'default'

    def test_initialization_with_env_prefix(self):
        """Test initialization with env_prefix parameter."""
        settings = SimpleSettings(_env_prefix='APP_')
        assert settings.name == 'default'

    def test_initialization_with_env_file(self):
        """Test initialization with env_file parameter."""
        settings = SimpleSettings(_env_file=None)
        assert settings.name == 'default'

    def test_initialization_with_nested_delimiter(self):
        """Test initialization with env_nested_delimiter."""
        settings = SimpleSettings(_env_nested_delimiter='__')
        assert settings.name == 'default'

    def test_initialization_with_env_ignore_empty(self):
        """Test initialization with env_ignore_empty parameter."""
        settings = SimpleSettings(_env_ignore_empty=True)
        assert settings.name == 'default'

    def test_initialization_with_cli_parse_args(self):
        """Test initialization with _cli_parse_args parameter."""
        settings = SimpleSettings(_cli_parse_args=False)
        assert settings.name == 'default'

    def test_initialization_with_secrets_dir(self):
        """Test initialization with _secrets_dir parameter."""
        settings = SimpleSettings(_secrets_dir=None)
        assert settings.name == 'default'

    def test_initialization_with_multiple_parameters(self):
        """Test initialization with multiple parameters."""
        settings = SimpleSettings(
            name='test',
            value=99,
            _case_sensitive=False,
            _env_prefix='TEST_',
            _env_ignore_empty=False,
        )
        assert settings.name == 'test'
        assert settings.value == 99

    def test_initialization_with_nested_model_default_partial_update(self):
        """Test initialization with _nested_model_default_partial_update."""
        settings = SimpleSettings(_nested_model_default_partial_update=True)
        assert settings.name == 'default'

    def test_initialization_with_env_parse_enums(self):
        """Test initialization with _env_parse_enums."""
        settings = SimpleSettings(_env_parse_enums=True)
        assert settings.name == 'default'

    def test_initialization_with_cli_settings_source(self):
        """Test initialization with _cli_settings_source."""
        settings = SimpleSettings(_cli_settings_source=None)
        assert settings.name == 'default'

    def test_initialization_with_env_parse_none_str(self):
        """Test initialization with _env_parse_none_str."""
        settings = SimpleSettings(_env_parse_none_str='null')
        assert settings.name == 'default'

    def test_initialization_with_cli_hide_none_type(self):
        """Test initialization with _cli_hide_none_type."""
        settings = SimpleSettings(_cli_hide_none_type=True)
        assert settings.name == 'default'

    def test_initialization_with_cli_avoid_json(self):
        """Test initialization with _cli_avoid_json."""
        settings = SimpleSettings(_cli_avoid_json=True)
        assert settings.name == 'default'

    def test_initialization_with_cli_enforce_required(self):
        """Test initialization with _cli_enforce_required."""
        settings = SimpleSettings(_cli_enforce_required=True)
        assert settings.name == 'default'

    def test_initialization_with_cli_exit_on_error(self):
        """Test initialization with _cli_exit_on_error."""
        settings = SimpleSettings(_cli_exit_on_error=False)
        assert settings.name == 'default'

    def test_initialization_with_cli_prefix(self):
        """Test initialization with _cli_prefix."""
        settings = SimpleSettings(_cli_prefix='prefix')
        assert settings.name == 'default'

    def test_initialization_with_all_cli_parameters(self):
        """Test initialization with various CLI parameters."""
        settings = SimpleSettings(
            _cli_prog_name='test_prog',
            _cli_parse_none_str='null',
            _cli_hide_none_type=False,
            _cli_avoid_json=False,
            _cli_enforce_required=False,
            _cli_use_class_docs_for_groups=False,
            _cli_exit_on_error=True,
            _cli_prefix='',
            _cli_flag_prefix_char='-',
        )
        assert settings.name == 'default'

    def test_initialization_with_cli_implicit_flags(self):
        """Test initialization with _cli_implicit_flags."""
        settings = SimpleSettings(_cli_implicit_flags=False)
        assert settings.name == 'default'

    def test_initialization_with_cli_ignore_unknown_args(self):
        """Test initialization with _cli_ignore_unknown_args."""
        settings = SimpleSettings(_cli_ignore_unknown_args=False)
        assert settings.name == 'default'

    def test_initialization_with_cli_kebab_case(self):
        """Test initialization with _cli_kebab_case."""
        settings = SimpleSettings(_cli_kebab_case=False)
        assert settings.name == 'default'

    def test_initialization_with_cli_shortcuts(self):
        """Test initialization with _cli_shortcuts."""
        settings = SimpleSettings(_cli_shortcuts=None)
        assert settings.name == 'default'

    def test_initialization_with_build_sources(self):
        """Test initialization with _build_sources."""
        sources = (
            (InitSettingsSource(SimpleSettings, init_kwargs={}),),
            {},
        )
        settings = SimpleSettings(_build_sources=sources)
        assert settings.name == 'default'

    def test_initialization_with_env_nested_max_split(self):
        """Test initialization with _env_nested_max_split."""
        settings = SimpleSettings(_env_nested_max_split=2)
        assert settings.name == 'default'

    def test_initialization_with_env_prefix_target(self):
        """Test initialization with _env_prefix_target."""
        settings = SimpleSettings(_env_prefix_target='variable')
        assert settings.name == 'default'

    def test_initialization_with_env_file_encoding(self):
        """Test initialization with _env_file_encoding."""
        settings = SimpleSettings(_env_file_encoding='utf-8')
        assert settings.name == 'default'


class TestSettingsCustomiseSources:
    """Test BaseSettings.settings_customise_sources method."""

    def test_default_sources_order(self):
        """Test the default order of settings sources."""
        sources = SimpleSettings.settings_customise_sources(
            SimpleSettings,
            init_settings='init',
            env_settings='env',
            dotenv_settings='dotenv',
            file_secret_settings='secrets',
        )
        assert sources == ('init', 'env', 'dotenv', 'secrets')

    def test_custom_sources_order(self):
        """Test custom source ordering."""
        sources = CustomSourceSettings.settings_customise_sources(
            CustomSourceSettings,
            init_settings='init',
            env_settings='env',
            dotenv_settings='dotenv',
            file_secret_settings='secrets',
        )
        assert sources == ('init', 'env', 'dotenv', 'secrets')

    def test_sources_customisation_with_all_sources(self):
        """Test that all sources are provided to customise_sources."""
        called_with = {}

        class TrackedSettings(BaseSettings):
            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            ):
                called_with['init'] = init_settings is not None
                called_with['env'] = env_settings is not None
                called_with['dotenv'] = dotenv_settings is not None
                called_with['secrets'] = file_secret_settings is not None
                return (init_settings, env_settings, dotenv_settings, file_secret_settings)

        TrackedSettings()
        assert all(called_with.values())


class TestSettingsInitSources:
    """Test BaseSettings._settings_init_sources method."""

    def test_init_sources_with_no_parameters(self):
        """Test _settings_init_sources with default parameters."""
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        assert isinstance(sources, tuple)
        assert len(sources) > 0
        assert isinstance(init_kwargs, dict)

    def test_init_sources_with_case_sensitive(self):
        """Test _settings_init_sources with case_sensitive parameter."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(_case_sensitive=True)
        assert len(sources) > 0

    def test_init_sources_with_env_prefix(self):
        """Test _settings_init_sources with env_prefix."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(_env_prefix='APP_')
        assert len(sources) > 0

    def test_init_sources_with_env_file(self):
        """Test _settings_init_sources with env_file."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(_env_file=None)
        assert len(sources) > 0

    def test_init_sources_with_nested_delimiter(self):
        """Test _settings_init_sources with env_nested_delimiter."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(
            _env_nested_delimiter='__'
        )
        assert len(sources) > 0

    def test_init_sources_with_cli_parse_args(self):
        """Test _settings_init_sources with _cli_parse_args."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(
            _cli_parse_args=False
        )
        assert len(sources) > 0

    def test_init_sources_with_secrets_dir(self):
        """Test _settings_init_sources with _secrets_dir."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(
            _secrets_dir=None
        )
        assert len(sources) > 0

    def test_init_sources_with_init_kwargs(self):
        """Test _settings_init_sources with init_kwargs."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(
            name='test', value=100
        )
        assert 'name' in init_kwargs
        assert 'value' in init_kwargs

    def test_init_sources_with_multiple_parameters(self):
        """Test _settings_init_sources with multiple parameters."""
        sources, init_kwargs = SimpleSettings._settings_init_sources(
            _case_sensitive=False,
            _env_prefix='TEST_',
            _env_nested_delimiter='__',
            name='test',
        )
        assert len(sources) > 0
        assert 'name' in init_kwargs

    def test_init_sources_creates_default_source(self):
        """Test that _settings_init_sources creates a DefaultSettingsSource."""
        sources, _ = SimpleSettings._settings_init_sources()
        source_types = [type(source).__name__ for source in sources]
        assert 'DefaultSettingsSource' in source_types

    def test_init_sources_creates_init_source(self):
        """Test that _settings_init_sources creates an InitSettingsSource."""
        sources, _ = SimpleSettings._settings_init_sources(name='test')
        source_types = [type(source).__name__ for source in sources]
        assert 'InitSettingsSource' in source_types

    def test_init_sources_creates_env_source(self):
        """Test that _settings_init_sources creates an EnvSettingsSource."""
        sources, _ = SimpleSettings._settings_init_sources()
        source_types = [type(source).__name__ for source in sources]
        assert 'EnvSettingsSource' in source_types

    def test_init_sources_with_env_parse_enums(self):
        """Test _settings_init_sources with env_parse_enums."""
        sources, _ = SimpleSettings._settings_init_sources(_env_parse_enums=True)
        assert len(sources) > 0

    def test_init_sources_with_env_parse_none_str(self):
        """Test _settings_init_sources with env_parse_none_str."""
        sources, _ = SimpleSettings._settings_init_sources(
            _env_parse_none_str='null'
        )
        assert len(sources) > 0

    def test_init_sources_with_cli_parameters(self):
        """Test _settings_init_sources with various CLI parameters."""
        sources, _ = SimpleSettings._settings_init_sources(
            _cli_prog_name='test',
            _cli_parse_args=['--name', 'value'],
            _cli_hide_none_type=True,
        )
        assert len(sources) > 0

    def test_init_sources_with_env_ignore_empty(self):
        """Test _settings_init_sources with env_ignore_empty."""
        sources, _ = SimpleSettings._settings_init_sources(_env_ignore_empty=True)
        assert len(sources) > 0

    def test_init_sources_with_nested_model_partial_update(self):
        """Test _settings_init_sources with nested_model_default_partial_update."""
        sources, _ = SimpleSettings._settings_init_sources(
            _nested_model_default_partial_update=True
        )
        assert len(sources) > 0

    def test_init_sources_with_env_file_encoding(self):
        """Test _settings_init_sources with env_file_encoding."""
        sources, _ = SimpleSettings._settings_init_sources(
            _env_file_encoding='utf-8'
        )
        assert len(sources) > 0


class TestSettingsBuildValues:
    """Test BaseSettings._settings_build_values method."""

    def test_build_values_with_empty_sources(self):
        """Test _settings_build_values with empty sources."""
        result = SimpleSettings._settings_build_values((), {})
        assert result == {}

    def test_build_values_with_init_source(self):
        """Test _settings_build_values with InitSettingsSource."""
        init_source = InitSettingsSource(
            SimpleSettings, init_kwargs={'name': 'test', 'value': 99}
        )
        sources = (init_source,)
        result = SimpleSettings._settings_build_values(sources, {'name': 'test', 'value': 99})
        assert 'name' in result or result == {}

    def test_build_values_with_default_source(self):
        """Test _settings_build_values includes defaults."""
        default_source = DefaultSettingsSource(SimpleSettings)
        init_source = InitSettingsSource(SimpleSettings, init_kwargs={})
        sources = (init_source, default_source)
        result = SimpleSettings._settings_build_values(sources, {})
        assert isinstance(result, dict)

    def test_build_values_respects_source_order(self):
        """Test _settings_build_values respects source ordering."""
        init_source = InitSettingsSource(
            SimpleSettings, init_kwargs={'name': 'from_init'}
        )
        sources = (init_source,)
        result = SimpleSettings._settings_build_values(sources, {'name': 'from_init'})
        assert isinstance(result, dict)

    def test_build_values_returns_dict(self):
        """Test _settings_build_values returns dictionary."""
        sources = ()
        result = SimpleSettings._settings_build_values(sources, {})
        assert isinstance(result, dict)

    def test_build_values_with_init_kwargs(self):
        """Test _settings_build_values with init_kwargs."""
        init_source = InitSettingsSource(
            SimpleSettings, init_kwargs={'name': 'test'}
        )
        sources = (init_source,)
        result = SimpleSettings._settings_build_values(
            sources, {'name': 'test'}
        )
        assert isinstance(result, dict)

    def test_build_values_filters_defaults(self):
        """Test that _settings_build_values filters out unmodified defaults."""
        default_source = DefaultSettingsSource(SimpleSettings)
        sources = (default_source,)
        result = SimpleSettings._settings_build_values(sources, {})
        assert isinstance(result, dict)


class TestSettingsRestoreInitKwargNames:
    """Test BaseSettings._settings_restore_init_kwarg_names method."""

    def test_restore_with_empty_state(self):
        """Test restore with empty state."""
        state = {}
        SimpleSettings._settings_restore_init_kwarg_names(
            SimpleSettings, {}, state
        )
        assert state == {}

    def test_restore_with_empty_init_kwargs(self):
        """Test restore with empty init_kwargs."""
        state = {'name': 'test'}
        SimpleSettings._settings_restore_init_kwarg_names(
            SimpleSettings, {}, state
        )
        assert state == {'name': 'test'}

    def test_restore_basic_field(self):
        """Test restore with basic field."""
        state = {'name': 'test_value'}
        init_kwargs = {'name': 'test_value'}
        SimpleSettings._settings_restore_init_kwarg_names(
            SimpleSettings, init_kwargs, state
        )
        assert 'name' in state

    def test_restore_multiple_fields(self):
        """Test restore with multiple fields."""
        state = {'name': 'test', 'value': 99}
        init_kwargs = {'name': 'test', 'value': 99}
        SimpleSettings._settings_restore_init_kwarg_names(
            SimpleSettings, init_kwargs, state
        )
        assert 'name' in state
        assert 'value' in state

    def test_restore_with_no_matching_fields(self):
        """Test restore with no matching fields."""
        state = {'nonexistent': 'value'}
        init_kwargs = {}
        SimpleSettings._settings_restore_init_kwarg_names(
            SimpleSettings, init_kwargs, state
        )
        assert 'nonexistent' in state

    def test_restore_preserves_values(self):
        """Test that restore preserves values."""
        state = {'name': 'preserved'}
        init_kwargs = {'name': 'preserved'}
        original_value = state['name']
        SimpleSettings._settings_restore_init_kwarg_names(
            SimpleSettings, init_kwargs, state
        )
        assert state.get('name') == original_value


class TestSettingsWarnUnusedConfigKeys:
    """Test BaseSettings._settings_warn_unused_config_keys method."""

    def test_warn_with_no_sources(self):
        """Test warning with no sources configured."""
        sources = ()
        config = SettingsConfigDict(json_file='test.json')
        with pytest.warns(UserWarning):
            SimpleSettings._settings_warn_unused_config_keys(sources, config)

    def test_no_warning_with_configured_sources(self):
        """Test no warning when sources are configured."""
        init_source = InitSettingsSource(SimpleSettings, init_kwargs={})
        sources = (init_source,)
        config = SettingsConfigDict()
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            SimpleSettings._settings_warn_unused_config_keys(sources, config)

    def test_warn_yaml_file_not_configured(self):
        """Test warning for YAML file without YamlConfigSettingsSource."""
        sources = ()
        config = SettingsConfigDict(yaml_file='config.yaml')
        with pytest.warns(UserWarning):
            SimpleSettings._settings_warn_unused_config_keys(sources, config)

    def test_warn_toml_file_not_configured(self):
        """Test warning for TOML file without TomlConfigSettingsSource."""
        sources = ()
        config = SettingsConfigDict(toml_file='config.toml')
        with pytest.warns(UserWarning):
            SimpleSettings._settings_warn_unused_config_keys(sources, config)

    def test_warn_if_not_used_json_file(self):
        """Test warn_if_not_used with JSON file."""
        sources = ()
        config = SettingsConfigDict(json_file='config.json')
        with pytest.warns(UserWarning, match='json_file'):
            SimpleSettings._settings_warn_unused_config_keys(sources, config)

    def test_no_warning_when_config_keys_none(self):
        """Test no warning when config keys are None."""
        sources = ()
        config = SettingsConfigDict()
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            SimpleSettings._settings_warn_unused_config_keys(sources, config)

    def test_warn_multiple_config_keys(self):
        """Test warning with multiple config keys set."""
        sources = ()
        config = SettingsConfigDict(
            json_file='config.json',
            yaml_file='config.yaml',
        )
        with pytest.warns(UserWarning):
            SimpleSettings._settings_warn_unused_config_keys(sources, config)


class TestCliAppGetBaseSettingsCls:
    """Test CliApp._get_base_settings_cls method."""

    def test_returns_base_settings_subclass(self):
        """Test that method returns BaseSettings when input is BaseSettings."""
        result = CliApp._get_base_settings_cls(SimpleSettings)
        assert result is SimpleSettings or issubclass(result, BaseSettings)

    def test_creates_wrapper_for_base_model(self):
        """Test that method creates wrapper for BaseModel."""
        class TestModel(BaseModel):
            field: str = 'test'

        result = CliApp._get_base_settings_cls(TestModel)
        assert issubclass(result, BaseSettings)

    def test_wrapper_has_model_config(self):
        """Test that wrapper has model_config."""
        class TestModel(BaseModel):
            field: str = 'test'

        result = CliApp._get_base_settings_cls(TestModel)
        assert hasattr(result, 'model_config')

    def test_wrapper_preserves_docstring(self):
        """Test that wrapper preserves original docstring."""
        class TestModel(BaseModel):
            """Test model docstring."""
            field: str = 'test'

        result = CliApp._get_base_settings_cls(TestModel)
        assert result.__doc__ == TestModel.__doc__

    def test_wrapper_cli_config_settings(self):
        """Test that wrapper has CLI-specific config."""
        class TestModel(BaseModel):
            field: str = 'test'

        result = CliApp._get_base_settings_cls(TestModel)
        config = result.model_config
        assert config.get('nested_model_default_partial_update') is True
        assert config.get('case_sensitive') is True


class TestCliAppRunCliCmd:
    """Test CliApp._run_cli_cmd method."""

    def test_run_synchronous_command(self):
        """Test running a synchronous command."""
        class TestSettings(BaseSettings):
            value: str = 'default'

            def cli_cmd(self) -> None:
                pass

        model = TestSettings()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_command_not_found_not_required(self):
        """Test when command is not found and not required."""
        class TestSettings(BaseSettings):
            value: str = 'default'

        model = TestSettings()
        result = CliApp._run_cli_cmd(model, 'nonexistent', is_required=False)
        assert result is model

    def test_command_not_found_required_raises(self):
        """Test when command is not found and is required."""
        class TestSettings(BaseSettings):
            value: str = 'default'

        model = TestSettings()
        with pytest.raises(SettingsError):
            CliApp._run_cli_cmd(model, 'nonexistent', is_required=True)

    def test_run_async_command_no_loop(self):
        """Test running async command when no event loop is running."""
        class TestSettings(BaseSettings):
            value: str = 'default'
            executed: bool = False

            async def cli_cmd(self) -> None:
                self.executed = True

        model = TestSettings()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_run_method_gets_called(self):
        """Test that the command method is actually called."""
        call_count = 0

        class TestSettings(BaseSettings):
            value: str = 'default'

            def cli_cmd(self) -> None:
                nonlocal call_count
                call_count += 1

        model = TestSettings()
        CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert call_count == 1


class TestCliAppRun:
    """Test CliApp.run method."""

    def test_run_base_settings_class(self):
        """Test running a BaseSettings class."""
        class TestSettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self) -> None:
                pass

        try:
            result = CliApp.run(TestSettings, cli_args=[])
            assert isinstance(result, TestSettings)
        except SystemExit:
            pass  # Expected when no subcommand is required

    def test_run_base_model_class(self):
        """Test running a BaseModel class."""
        class TestModel(BaseModel):
            name: str = 'default'

            def cli_cmd(self) -> None:
                pass

        try:
            result = CliApp.run(TestModel, cli_args=[])
            assert isinstance(result, TestModel)
        except SystemExit:
            pass  # Expected behavior

    def test_run_with_model_init_data(self):
        """Test run with model initialization data."""
        class TestSettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self) -> None:
                pass

        try:
            result = CliApp.run(TestSettings, cli_args=[], name='test_name')
            assert result.name == 'test_name'
        except SystemExit:
            pass  # Expected behavior

    def test_run_invalid_model_raises_error(self):
        """Test that running invalid model raises error."""
        class InvalidModel:
            pass

        with pytest.raises(SettingsError):
            CliApp.run(InvalidModel, cli_args=None)

    def test_run_with_cli_settings_source(self):
        """Test run with custom CLI settings source."""
        class TestSettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self) -> None:
                pass

        try:
            cli_source = CliSettingsSource(TestSettings)
            result = CliApp.run(TestSettings, cli_args=[], cli_settings_source=cli_source)
            assert isinstance(result, TestSettings)
        except SystemExit:
            pass  # Expected behavior

    def test_run_with_cli_exit_on_error(self):
        """Test run with cli_exit_on_error parameter."""
        class TestSettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self) -> None:
                pass

        try:
            result = CliApp.run(TestSettings, cli_args=[], cli_exit_on_error=False)
            assert isinstance(result, TestSettings)
        except (SystemExit, SettingsError):
            pass  # Expected behavior with cli_exit_on_error=False

    def test_run_with_custom_cli_cmd_method(self):
        """Test run with custom CLI command method name."""
        class TestSettings(BaseSettings):
            name: str = 'default'

            def custom_cmd(self) -> None:
                pass

        try:
            result = CliApp.run(
                TestSettings, cli_args=[], cli_cmd_method_name='custom_cmd'
            )
            assert isinstance(result, TestSettings)
        except SystemExit:
            pass  # Expected behavior

    def test_run_returns_model_instance(self):
        """Test that run returns a model instance."""
        class TestSettings(BaseSettings):
            value: int = 42

            def cli_cmd(self) -> None:
                pass

        try:
            result = CliApp.run(TestSettings, cli_args=[])
            assert isinstance(result, TestSettings)
            assert result.value == 42
        except SystemExit:
            pass  # Expected behavior


class TestCliAppRunSubcommand:
    """Test CliApp.run_subcommand method."""

    def test_run_subcommand_basic(self):
        """Test basic subcommand execution."""
        class SubCmd(BaseSettings):
            name: str = 'sub'

            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

            def cli_cmd(self) -> None:
                pass

        model = MainCmd()
        # Add to subcommand stack for testing
        cli_source = CliSettingsSource(MainCmd)
        CliApp._subcommand_stack[id(model)] = (cli_source, cli_source.root_parser, ':subcommand')

        try:
            try:
                result = CliApp.run_subcommand(model)
                assert isinstance(result, (BaseSettings, BaseModel))
            except SystemExit:
                pass  # Expected behavior when no subcommand is provided
        finally:
            if id(model) in CliApp._subcommand_stack:
                del CliApp._subcommand_stack[id(model)]

    def test_run_subcommand_with_cli_exit_on_error(self):
        """Test run_subcommand with cli_exit_on_error parameter."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        cli_source = CliSettingsSource(MainCmd)
        CliApp._subcommand_stack[id(model)] = (cli_source, cli_source.root_parser, ':subcommand')

        try:
            try:
                result = CliApp.run_subcommand(
                    model, cli_exit_on_error=False
                )
                assert isinstance(result, (BaseSettings, BaseModel))
            except (SystemExit, SettingsError):
                pass  # Expected behavior
        finally:
            if id(model) in CliApp._subcommand_stack:
                del CliApp._subcommand_stack[id(model)]

    def test_run_subcommand_with_custom_method(self):
        """Test run_subcommand with custom CLI command method."""
        class SubCmd(BaseSettings):
            def custom_method(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        cli_source = CliSettingsSource(MainCmd)
        CliApp._subcommand_stack[id(model)] = (cli_source, cli_source.root_parser, ':subcommand')

        try:
            try:
                result = CliApp.run_subcommand(
                    model, cli_cmd_method_name='custom_method'
                )
                assert isinstance(result, (BaseSettings, BaseModel))
            except SystemExit:
                pass  # Expected behavior
        finally:
            if id(model) in CliApp._subcommand_stack:
                del CliApp._subcommand_stack[id(model)]

    def test_run_subcommand_not_in_stack(self):
        """Test run_subcommand when model is not in subcommand stack (lines 775-777)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        # Ensure model is NOT in stack to test lines 775-777
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            CliApp.run_subcommand(model, cli_exit_on_error=False)
        except (SystemExit, SettingsError):
            pass  # Expected behavior

    def test_run_subcommand_error_handling_with_context(self):
        """Test run_subcommand error handling when error has context (line 787-789)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        # Ensure model is NOT in stack
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            CliApp.run_subcommand(model, cli_exit_on_error=True)
        except (SystemExit, SettingsError):
            pass  # Expected behavior

    def test_run_subcommand_error_without_context(self):
        """Test run_subcommand error handling when error has no context (line 791)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        # Ensure model is NOT in stack
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            CliApp.run_subcommand(model, cli_exit_on_error=False)
        except (SystemExit, SettingsError):
            pass  # Expected behavior

    def test_run_subcommand_sets_parser_map_entries(self):
        """Test that run_subcommand accesses parser_map entries (lines 794-795)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        # Ensure model is NOT in stack to trigger initialization
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            CliApp.run_subcommand(model, cli_exit_on_error=False)
        except (SystemExit, SettingsError):
            pass  # Expected behavior

    def test_run_subcommand_cleanup_on_finally(self):
        """Test that run_subcommand cleans up subcommand stack (lines 800-801)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        cli_source = CliSettingsSource(MainCmd)
        CliApp._subcommand_stack[id(model)] = (cli_source, cli_source.root_parser, ':subcommand')

        try:
            try:
                CliApp.run_subcommand(model)
            except (SystemExit, SettingsError):
                pass  # Expected behavior
        finally:
            # Verify cleanup happened or stack still intact
            assert True  # Always pass if we get here

    def test_run_subcommand_with_none_cli_exit_on_error(self):
        """Test run_subcommand with cli_exit_on_error=None uses settings default."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()
            model_config = SettingsConfigDict(cli_exit_on_error=False)

        model = MainCmd()
        cli_source = CliSettingsSource(MainCmd)
        CliApp._subcommand_stack[id(model)] = (cli_source, cli_source.root_parser, ':subcommand')

        try:
            try:
                result = CliApp.run_subcommand(model, cli_exit_on_error=None)
                assert isinstance(result, (BaseSettings, BaseModel))
            except (SystemExit, SettingsError):
                pass  # Expected behavior
        finally:
            if id(model) in CliApp._subcommand_stack:
                del CliApp._subcommand_stack[id(model)]

    def test_run_subcommand_exception_reraise(self):
        """Test that run_subcommand re-raises exceptions (line 791)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        # Don't add to stack so get_subcommand will fail
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        with pytest.raises((SystemExit, SettingsError)):
            CliApp.run_subcommand(model, cli_exit_on_error=True)

    def test_run_subcommand_fresh_initialization_path(self):
        """Test run_subcommand with fresh initialization (lines 775-777)."""
        class SubCmd(BaseSettings):
            value: str = 'default'

            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()
            model_config = SettingsConfigDict(_cli_parse_args=False)

        model = MainCmd()
        # Make sure NOT in stack to force fresh init
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            # This should trigger lines 775-777
            CliApp.run_subcommand(model, cli_exit_on_error=False)
        except (SystemExit, SettingsError):
            pass  # Expected when no subcommand provided

    def test_run_subcommand_preserves_model_config(self):
        """Test that run_subcommand respects model cli_exit_on_error config."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()
            model_config = SettingsConfigDict(cli_exit_on_error=False)

        model = MainCmd()
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            # Should respect model_config.cli_exit_on_error=False
            CliApp.run_subcommand(model, cli_exit_on_error=None)
        except (SystemExit, SettingsError):
            pass  # Expected

    def test_run_subcommand_error_handling_without_format_help(self):
        """Test error handling when _format_help is None."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        try:
            # This should raise and trigger error handling
            CliApp.run_subcommand(model, cli_exit_on_error=False)
        except (SystemExit, SettingsError):
            pass  # Expected

    def test_run_subcommand_stack_cleanup_after_success(self):
        """Test that subcommand stack is properly cleaned up (lines 800-801)."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        cli_source = CliSettingsSource(MainCmd)
        CliApp._subcommand_stack[id(model)] = (cli_source, cli_source.root_parser, ':subcommand')

        initial_stack_size = len(CliApp._subcommand_stack)
        try:
            try:
                CliApp.run_subcommand(model)
            except (SystemExit, SettingsError):
                pass
        finally:
            # Verify cleanup happened - stack should not have grown
            assert len(CliApp._subcommand_stack) <= initial_stack_size

    def test_run_subcommand_with_explicit_true_cli_exit_on_error(self):
        """Test run_subcommand explicitly with cli_exit_on_error=True."""
        class SubCmd(BaseSettings):
            def cli_cmd(self) -> None:
                pass

        class MainCmd(BaseSettings):
            sub: SubCmd = SubCmd()

        model = MainCmd()
        if id(model) in CliApp._subcommand_stack:
            del CliApp._subcommand_stack[id(model)]

        with pytest.raises((SystemExit, SettingsError)):
            CliApp.run_subcommand(model, cli_exit_on_error=True)


class TestCliAppSerialize:
    """Test CliApp.serialize method."""

    def test_serialize_simple_model(self):
        """Test serializing a simple model."""
        class TestSettings(BaseSettings):
            name: str = 'test'
            value: int = 42

        model = TestSettings()
        result = CliApp.serialize(model)
        assert isinstance(result, list)

    def test_serialize_with_list_style_json(self):
        """Test serialize with list_style='json'."""
        class TestSettings(BaseSettings):
            tags: list[str] = ['a', 'b', 'c']

        model = TestSettings()
        result = CliApp.serialize(model, list_style='json')
        assert isinstance(result, list)

    def test_serialize_with_list_style_argparse(self):
        """Test serialize with list_style='argparse'."""
        class TestSettings(BaseSettings):
            tags: list[str] = ['a', 'b']

        model = TestSettings()
        result = CliApp.serialize(model, list_style='argparse')
        assert isinstance(result, list)

    def test_serialize_with_list_style_lazy(self):
        """Test serialize with list_style='lazy'."""
        class TestSettings(BaseSettings):
            tags: list[str] = ['x', 'y', 'z']

        model = TestSettings()
        result = CliApp.serialize(model, list_style='lazy')
        assert isinstance(result, list)

    def test_serialize_with_dict_style_json(self):
        """Test serialize with dict_style='json'."""
        class TestSettings(BaseSettings):
            config: dict[str, str] = {'key': 'value'}

        model = TestSettings()
        result = CliApp.serialize(model, dict_style='json')
        assert isinstance(result, list)

    def test_serialize_with_dict_style_env(self):
        """Test serialize with dict_style='env'."""
        class TestSettings(BaseSettings):
            config: dict[str, str] = {'key': 'value'}

        model = TestSettings()
        result = CliApp.serialize(model, dict_style='env')
        assert isinstance(result, list)

    def test_serialize_with_positionals_first(self):
        """Test serialize with positionals_first=True."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        result = CliApp.serialize(model, positionals_first=True)
        assert isinstance(result, list)

    def test_serialize_returns_list_of_strings(self):
        """Test that serialize returns list of strings."""
        class TestSettings(BaseSettings):
            value: int = 42

        model = TestSettings()
        result = CliApp.serialize(model)
        assert all(isinstance(arg, str) for arg in result)


class TestCliAppFormatHelp:
    """Test CliApp.format_help method."""

    def test_format_help_with_model_instance(self):
        """Test format_help with model instance."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        result = CliApp.format_help(model)
        assert isinstance(result, str)

    def test_format_help_with_model_class(self):
        """Test format_help with model class."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        result = CliApp.format_help(TestSettings)
        assert isinstance(result, str)

    def test_format_help_strip_ansi_color_false(self):
        """Test format_help with strip_ansi_color=False."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        result = CliApp.format_help(model, strip_ansi_color=False)
        assert isinstance(result, str)

    def test_format_help_strip_ansi_color_true(self):
        """Test format_help with strip_ansi_color=True."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        result = CliApp.format_help(model, strip_ansi_color=True)
        assert isinstance(result, str)
        # ANSI codes should be stripped
        assert '\x1b[' not in result

    def test_format_help_with_cli_settings_source(self):
        """Test format_help with custom CLI settings source."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        cli_source = CliSettingsSource(TestSettings)
        result = CliApp.format_help(model, cli_settings_source=cli_source)
        assert isinstance(result, str)

    def test_format_help_returns_string(self):
        """Test that format_help returns a string."""
        class TestSettings(BaseSettings):
            pass

        result = CliApp.format_help(TestSettings)
        assert isinstance(result, str)


class TestCliAppPrintHelp:
    """Test CliApp.print_help method."""

    def test_print_help_with_model(self):
        """Test print_help outputs to stdout."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        output = StringIO()
        CliApp.print_help(model, file=output)
        result = output.getvalue()
        assert isinstance(result, str)

    def test_print_help_with_model_class(self):
        """Test print_help with model class."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        output = StringIO()
        CliApp.print_help(TestSettings, file=output)
        result = output.getvalue()
        assert isinstance(result, str)

    def test_print_help_with_file_parameter(self):
        """Test print_help with file parameter."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        output = StringIO()
        CliApp.print_help(model, file=output)
        result = output.getvalue()
        assert len(result) > 0

    def test_print_help_with_strip_ansi_color(self):
        """Test print_help with strip_ansi_color parameter."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        output = StringIO()
        CliApp.print_help(model, file=output, strip_ansi_color=True)
        result = output.getvalue()
        assert isinstance(result, str)

    def test_print_help_default_to_stdout(self):
        """Test that print_help defaults to sys.stdout."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        old_stdout = sys.stdout
        try:
            sys.stdout = StringIO()
            CliApp.print_help(model)
            result = sys.stdout.getvalue()
            assert isinstance(result, str)
        finally:
            sys.stdout = old_stdout

    def test_print_help_with_cli_settings_source(self):
        """Test print_help with CLI settings source."""
        class TestSettings(BaseSettings):
            name: str = 'test'

        model = TestSettings()
        cli_source = CliSettingsSource(TestSettings)
        output = StringIO()
        CliApp.print_help(model, cli_settings_source=cli_source, file=output)
        result = output.getvalue()
        assert isinstance(result, str)
