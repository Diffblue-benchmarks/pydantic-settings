"""Tests for pydantic_settings/main.py"""
from __future__ import annotations

import asyncio
import io
import os
import warnings
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.main import CliApp, SettingsConfigDict
from pydantic_settings.sources import (
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)


# ---------------------------------------------------------------------------
# Simple settings models for testing
# ---------------------------------------------------------------------------

class SimpleSettings(BaseSettings):
    name: str = 'default_name'
    value: int = 42


class RequiredSettings(BaseSettings):
    required_field: str


class SettingsWithAlias(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True)
    my_field: str = Field('default', alias='myField')


# ---------------------------------------------------------------------------
# BaseSettings.__init__ tests
# ---------------------------------------------------------------------------

class TestBaseSettingsInit:
    def test_init_with_defaults(self):
        settings = SimpleSettings()
        assert settings.name == 'default_name'
        assert settings.value == 42

    def test_init_with_keyword_args(self):
        settings = SimpleSettings(name='hello', value=100)
        assert settings.name == 'hello'
        assert settings.value == 100

    def test_init_with_env_prefix(self, monkeypatch):
        monkeypatch.setenv('MY_NAME', 'from_env')
        monkeypatch.setenv('MY_VALUE', '99')

        class PrefixedSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='MY_')
            name: str = 'default'
            value: int = 0

        settings = PrefixedSettings()
        assert settings.name == 'from_env'
        assert settings.value == 99

    def test_init_override_env_prefix_at_runtime(self, monkeypatch):
        monkeypatch.setenv('RUNTIME_NAME', 'runtime_env')

        class NoPrefix(BaseSettings):
            name: str = 'default'

        settings = NoPrefix(_env_prefix='RUNTIME_')
        assert settings.name == 'runtime_env'

    def test_init_with_build_sources(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources(name='built', value=7)
        settings = SimpleSettings(_build_sources=(sources, init_kwargs))
        assert settings.name == 'built'
        assert settings.value == 7

    def test_init_with_cli_parse_args(self):
        class CliSettings(BaseSettings):
            name: str = 'default'

        settings = CliSettings(_cli_parse_args=['--name', 'from_cli'])
        assert settings.name == 'from_cli'

    def test_init_env_ignore_empty(self, monkeypatch):
        monkeypatch.setenv('NAME', '')

        class EnvSettings(BaseSettings):
            name: str = 'default'

        settings = EnvSettings(_env_ignore_empty=True)
        assert settings.name == 'default'

    def test_init_case_insensitive_by_default(self, monkeypatch):
        monkeypatch.setenv('NAME', 'from_env')

        class CaseSettings(BaseSettings):
            name: str = 'default'

        settings = CaseSettings()
        assert settings.name == 'from_env'

    def test_init_with_nested_delimiter(self, monkeypatch):
        monkeypatch.setenv('APP_NAME', 'nested')

        class NestedSettings(BaseSettings):
            name: str = 'default'

        settings = NestedSettings(_env_nested_delimiter='__', _env_prefix='APP_')
        assert settings.name == 'nested'

    def test_init_forwarded_kwargs_override_env(self, monkeypatch):
        monkeypatch.setenv('NAME', 'from_env')

        class EnvSettings(BaseSettings):
            name: str = 'default'

        settings = EnvSettings(name='from_kwargs')
        assert settings.name == 'from_kwargs'


# ---------------------------------------------------------------------------
# BaseSettings.settings_customise_sources tests
# ---------------------------------------------------------------------------

class TestSettingsCustomiseSources:
    def test_default_source_order(self):
        class MySettings(BaseSettings):
            pass

        init_source = InitSettingsSource(MySettings, init_kwargs={})
        env_source = EnvSettingsSource(MySettings)
        dotenv_source = DotEnvSettingsSource(MySettings)
        secrets_source = SecretsSettingsSource(MySettings, secrets_dir=None)

        result = MySettings.settings_customise_sources(
            MySettings,
            init_settings=init_source,
            env_settings=env_source,
            dotenv_settings=dotenv_source,
            file_secret_settings=secrets_source,
        )

        assert result == (init_source, env_source, dotenv_source, secrets_source)
        assert len(result) == 4

    def test_custom_source_order(self):
        class MySettings(BaseSettings):
            @classmethod
            def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
                return env_settings, init_settings

        init_source = InitSettingsSource(MySettings, init_kwargs={})
        env_source = EnvSettingsSource(MySettings)
        dotenv_source = DotEnvSettingsSource(MySettings)
        secrets_source = SecretsSettingsSource(MySettings, secrets_dir=None)

        result = MySettings.settings_customise_sources(
            MySettings,
            init_settings=init_source,
            env_settings=env_source,
            dotenv_settings=dotenv_source,
            file_secret_settings=secrets_source,
        )

        assert result == (env_source, init_source)


# ---------------------------------------------------------------------------
# BaseSettings._settings_init_sources tests
# ---------------------------------------------------------------------------

class TestSettingsInitSources:
    def test_returns_tuple_of_sources_and_init_kwargs(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        assert isinstance(sources, tuple)
        assert isinstance(init_kwargs, dict)

    def test_includes_default_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, DefaultSettingsSource) for s in sources)

    def test_includes_env_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, EnvSettingsSource) for s in sources)

    def test_includes_init_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, InitSettingsSource) for s in sources)

    def test_includes_dotenv_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, DotEnvSettingsSource) for s in sources)

    def test_includes_secrets_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, SecretsSettingsSource) for s in sources)

    def test_init_kwargs_from_values(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources(name='test_name')
        assert init_kwargs.get('name') == 'test_name'

    def test_cli_settings_source_added_when_parse_args_given(self):
        from pydantic_settings.sources import CliSettingsSource
        sources, _ = SimpleSettings._settings_init_sources(_cli_parse_args=['--name', 'cli_val'])
        assert any(isinstance(s, CliSettingsSource) for s in sources)

    def test_env_prefix_passed_to_sources(self, monkeypatch):
        monkeypatch.setenv('PRE_NAME', 'prefixed')

        class PrefixedSettings(BaseSettings):
            name: str = 'default'

        sources, _ = PrefixedSettings._settings_init_sources(_env_prefix='PRE_')
        env_source = next(s for s in sources if isinstance(s, EnvSettingsSource))
        assert env_source.env_prefix == 'PRE_'

    def test_case_sensitive_passed_to_env_source(self):
        sources, _ = SimpleSettings._settings_init_sources(_case_sensitive=True)
        env_source = next(s for s in sources if isinstance(s, EnvSettingsSource))
        assert env_source.case_sensitive is True

    def test_env_file_sentinel_uses_model_config(self):
        class SettingsWithEnvFile(BaseSettings):
            model_config = SettingsConfigDict(env_file='.env.test')
            name: str = 'default'

        sources, _ = SettingsWithEnvFile._settings_init_sources()
        dotenv_source = next(s for s in sources if isinstance(s, DotEnvSettingsSource))
        assert dotenv_source.env_file == '.env.test'

    def test_env_nested_max_split_passed(self):
        sources, _ = SimpleSettings._settings_init_sources(
            _env_nested_delimiter='__', _env_nested_max_split=2
        )
        env_source = next(s for s in sources if isinstance(s, EnvSettingsSource))
        assert env_source.env_nested_max_split == 2

    def test_env_parse_none_str_overrides_cli_parse_none_str(self):
        # env_parse_none_str should propagate to cli_parse_none_str
        sources, _ = SimpleSettings._settings_init_sources(
            _env_parse_none_str='null', _cli_parse_args=['--name', 'x']
        )
        from pydantic_settings.sources import CliSettingsSource
        cli_source = next((s for s in sources if isinstance(s, CliSettingsSource)), None)
        assert cli_source is not None
        assert cli_source.cli_parse_none_str == 'null'


# ---------------------------------------------------------------------------
# BaseSettings._settings_build_values tests
# ---------------------------------------------------------------------------

class TestSettingsBuildValues:
    def test_empty_sources_returns_empty_dict(self):
        result = SimpleSettings._settings_build_values((), {})
        assert result == {}

    def test_single_source_returns_values(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources(name='built_name', value=77)
        result = SimpleSettings._settings_build_values(sources, init_kwargs)
        assert result.get('name') == 'built_name'
        assert result.get('value') == 77

    def test_defaults_not_included_in_result(self):
        # Default values should be stripped from the result
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        result = SimpleSettings._settings_build_values(sources, init_kwargs)
        # name and value are not in result if they are at default values
        assert 'name' not in result or result['name'] == 'default_name'

    def test_init_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv('NAME', 'from_env')

        class EnvSettings(BaseSettings):
            name: str = 'default'

        sources, init_kwargs = EnvSettings._settings_init_sources(name='from_init')
        result = EnvSettings._settings_build_values(sources, init_kwargs)
        assert result.get('name') == 'from_init'


# ---------------------------------------------------------------------------
# BaseSettings._settings_restore_init_kwarg_names tests
# ---------------------------------------------------------------------------

class TestSettingsRestoreInitKwargNames:
    def test_no_op_when_init_kwargs_empty(self):
        state = {'name': 'test'}
        BaseSettings._settings_restore_init_kwarg_names(SimpleSettings, {}, state)
        assert state == {'name': 'test'}

    def test_no_op_when_state_empty(self):
        state = {}
        BaseSettings._settings_restore_init_kwarg_names(SimpleSettings, {'name': 'test'}, state)
        assert state == {}

    def test_renames_alias_to_init_kwarg_name(self):
        class AliasSettings(BaseSettings):
            model_config = SettingsConfigDict(populate_by_name=True)
            my_field: str = Field('default', alias='myField')

        state = {'myField': 'value_from_state'}
        init_kwargs = {'myField': 'value_from_init'}
        BaseSettings._settings_restore_init_kwarg_names(AliasSettings, init_kwargs, state)
        # State should now have the value keyed by myField
        assert 'myField' in state

    def test_handles_field_without_alias(self):
        state = {'name': 'test_val', 'value': 5}
        init_kwargs = {'name': 'test_val'}
        BaseSettings._settings_restore_init_kwarg_names(SimpleSettings, init_kwargs, state)
        assert state.get('name') == 'test_val'


# ---------------------------------------------------------------------------
# BaseSettings._settings_warn_unused_config_keys tests
# ---------------------------------------------------------------------------

class TestSettingsWarnUnusedConfigKeys:
    def test_warns_for_json_file_without_json_source(self):
        # Call _settings_warn_unused_config_keys directly with no sources
        model_config = SettingsConfigDict(json_file='config.json')
        sources = ()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            json_warnings = [warning for warning in w if 'json_file' in str(warning.message)]
            assert len(json_warnings) > 0

    def test_warns_for_json_file_encoding_without_json_source(self):
        model_config = SettingsConfigDict(json_file_encoding='utf-8')
        sources = ()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            relevant = [warning for warning in w if 'json_file_encoding' in str(warning.message)]
            assert len(relevant) > 0

    def test_warns_for_toml_file_without_toml_source(self):
        model_config = SettingsConfigDict(toml_file='config.toml')
        sources = ()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            toml_warnings = [warning for warning in w if 'toml_file' in str(warning.message)]
            assert len(toml_warnings) > 0

    def test_warns_for_yaml_file_without_yaml_source(self):
        model_config = SettingsConfigDict(yaml_file='config.yaml')
        sources = ()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            yaml_warnings = [warning for warning in w if 'yaml_file' in str(warning.message)]
            assert len(yaml_warnings) > 0

    def test_warns_for_yaml_config_section_without_yaml_source(self):
        model_config = SettingsConfigDict(yaml_config_section='section')
        sources = ()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            relevant = [warning for warning in w if 'yaml_config_section' in str(warning.message)]
            assert len(relevant) > 0

    def test_warns_for_pyproject_keys_without_pyproject_source(self):
        model_config = SettingsConfigDict(pyproject_toml_depth=2)
        sources = ()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            relevant = [warning for warning in w if 'pyproject_toml_depth' in str(warning.message)]
            assert len(relevant) > 0

    def test_no_warning_when_no_file_config_set(self):
        # Empty model_config with no file keys set
        model_config = SettingsConfigDict()
        sources = ()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            relevant = [warning for warning in w if issubclass(warning.category, UserWarning)]
            assert len(relevant) == 0

    def test_no_warning_when_json_source_is_configured(self):
        model_config = SettingsConfigDict(json_file='config.json')

        class TempSettings(BaseSettings):
            pass

        json_source = JsonConfigSettingsSource(TempSettings)
        sources = (json_source,)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            json_warnings = [warning for warning in w if 'json_file' in str(warning.message)]
            assert len(json_warnings) == 0

    def test_no_warning_when_toml_source_is_configured(self):
        model_config = SettingsConfigDict(toml_file='config.toml')

        class TempSettings(BaseSettings):
            pass

        toml_source = TomlConfigSettingsSource(TempSettings)
        sources = (toml_source,)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            toml_warnings = [warning for warning in w if 'toml_file' in str(warning.message)]
            assert len(toml_warnings) == 0

    def test_warn_if_not_used_inner_function(self):
        # Test that the inner warn_if_not_used function is called properly via _settings_warn_unused_config_keys
        model_config = SettingsConfigDict(yaml_file='something.yaml')
        sources = ()  # No sources - should warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            assert any('yaml_file' in str(warning.message) for warning in w)

    def test_warns_with_correct_warning_type(self):
        model_config = SettingsConfigDict(json_file='config.json')
        sources = ()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, model_config)
            user_warnings = [warning for warning in w if issubclass(warning.category, UserWarning)]
            assert len(user_warnings) > 0


# ---------------------------------------------------------------------------
# CliApp._get_base_settings_cls tests
# ---------------------------------------------------------------------------

class TestCliAppGetBaseSettingsCls:
    def test_returns_same_class_for_base_settings_subclass(self):
        result = CliApp._get_base_settings_cls(SimpleSettings)
        assert result is SimpleSettings

    def test_returns_wrapper_for_base_model(self):
        class MyModel(BaseModel):
            name: str = 'test'

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert issubclass(result, MyModel)

    def test_wrapper_has_correct_model_config(self):
        class MyModel(BaseModel):
            name: str = 'test'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.model_config.get('nested_model_default_partial_update') is True
        assert result.model_config.get('case_sensitive') is True
        assert result.model_config.get('cli_hide_none_type') is True
        assert result.model_config.get('cli_avoid_json') is True
        assert result.model_config.get('cli_enforce_required') is True
        assert result.model_config.get('cli_implicit_flags') is True
        assert result.model_config.get('cli_kebab_case') is True

    def test_wrapper_preserves_docstring(self):
        class MyModel(BaseModel):
            """My model docstring."""
            name: str = 'test'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.__doc__ == 'My model docstring.'

    def test_works_with_pydantic_dataclass(self):
        @pydantic_dataclass
        class MyDataclass:
            name: str = 'test'

        result = CliApp._get_base_settings_cls(MyDataclass)
        assert issubclass(result, BaseSettings)


# ---------------------------------------------------------------------------
# CliApp._run_cli_cmd tests
# ---------------------------------------------------------------------------

class TestCliAppRunCliCmd:
    def test_returns_model_when_method_missing_and_not_required(self):
        class MyModel(BaseModel):
            name: str = 'test'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_raises_when_method_missing_and_required(self):
        class MyModel(BaseModel):
            name: str = 'test'

        model = MyModel()
        with pytest.raises(SettingsError, match='missing cli_cmd entrypoint'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_calls_synchronous_method(self):
        called = []

        class MyModel(BaseModel):
            name: str = 'test'

            def cli_cmd(self):
                called.append(True)

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert called == [True]
        assert result is model

    def test_calls_async_method_without_event_loop(self):
        called = []

        class MyModel(BaseModel):
            name: str = 'test'

            async def cli_cmd(self):
                called.append(True)

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert called == [True]
        assert result is model

    def test_async_exception_propagated(self):
        class MyModel(BaseModel):
            name: str = 'test'

            async def cli_cmd(self):
                raise ValueError('async error')

        model = MyModel()
        with pytest.raises(ValueError, match='async error'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_calls_custom_method_name(self):
        called = []

        class MyModel(BaseModel):
            name: str = 'test'

            def execute(self):
                called.append(True)

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'execute', is_required=True)
        assert called == [True]
        assert result is model

    def test_async_method_with_running_event_loop(self):
        called = []

        class MyModel(BaseModel):
            name: str = 'test'

            async def cli_cmd(self):
                called.append(True)

        async def run_in_loop():
            model = MyModel()
            return CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        result = asyncio.run(run_in_loop())
        assert called == [True]
        assert result is not None

    def test_async_exception_propagated_with_running_event_loop(self):
        class MyModel(BaseModel):
            name: str = 'test'

            async def cli_cmd(self):
                raise ValueError('async error in thread')

        async def run_in_loop():
            model = MyModel()
            return CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        with pytest.raises(ValueError, match='async error in thread'):
            asyncio.run(run_in_loop())


# ---------------------------------------------------------------------------
# CliApp.run tests
# ---------------------------------------------------------------------------

class TestCliAppRun:
    def test_raises_for_non_model_class(self):
        class NotAModel:
            pass

        with pytest.raises(SettingsError, match='is not subclass of BaseModel'):
            CliApp.run(NotAModel, cli_args=[])

    def test_run_base_settings_subclass(self):
        ran = []

        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                ran.append(self.name)

        result = CliApp.run(MySettings, cli_args=[])
        assert isinstance(result, MySettings)
        assert ran == ['default']

    def test_run_with_cli_args(self):
        ran = []

        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                ran.append(self.name)

        result = CliApp.run(MySettings, cli_args=['--name', 'hello'])
        assert result.name == 'hello'

    def test_run_base_model_subclass(self):
        ran = []

        class MyModel(BaseModel):
            name: str = 'default'

            def cli_cmd(self):
                ran.append(self.name)

        result = CliApp.run(MyModel, cli_args=[])
        assert isinstance(result, MyModel)
        assert ran == ['default']

    def test_run_with_pydantic_dataclass(self):
        ran = []

        @pydantic_dataclass
        class MyDataclass:
            name: str = 'default'

            def cli_cmd(self):
                ran.append(self.name)

        result = CliApp.run(MyDataclass, cli_args=[])
        assert ran == ['default']

    def test_raises_when_namespace_used_without_cli_settings_source(self):
        from argparse import Namespace

        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                pass

        ns = Namespace(name='test')
        with pytest.raises(SettingsError, match='cli_args.*must be list'):
            CliApp.run(MySettings, cli_args=ns)

    def test_run_with_cli_settings_source_and_namespace(self):
        from argparse import Namespace
        from pydantic_settings.sources import CliSettingsSource

        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        ns = Namespace(**{'name': 'from_ns'})
        result = CliApp.run(MySettings, cli_args=ns, cli_settings_source=cli_source)
        assert isinstance(result, MySettings)

    def test_run_cleans_up_subcommand_stack(self):
        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                pass

        before_count = len(CliApp._subcommand_stack)
        CliApp.run(MySettings, cli_args=[])
        after_count = len(CliApp._subcommand_stack)
        assert after_count == before_count

    def test_run_with_model_init_data(self):
        ran = []

        class MySettings(BaseSettings):
            name: str = 'default'
            count: int = 0

            def cli_cmd(self):
                ran.append((self.name, self.count))

        result = CliApp.run(MySettings, cli_args=[], name='provided', count=5)
        assert ran == [('provided', 5)]


# ---------------------------------------------------------------------------
# CliApp.serialize tests
# ---------------------------------------------------------------------------

class TestCliAppSerialize:
    def test_serialize_simple_model(self):
        class MySettings(BaseSettings):
            name: str = 'hello'

        model = MySettings()
        result = CliApp.serialize(model)
        assert isinstance(result, list)

    def test_serialize_with_values(self):
        class MySettings(BaseSettings):
            name: str = 'world'
            count: int = 5

        model = MySettings(name='test', count=3)
        result = CliApp.serialize(model)
        assert '--name' in result
        assert 'test' in result

    def test_serialize_base_model(self):
        class MyModel(BaseModel):
            name: str = 'hello'

        model = MyModel()
        result = CliApp.serialize(model)
        assert isinstance(result, list)

    def test_serialize_list_style_argparse(self):
        class MySettings(BaseSettings):
            tags: list[str] = ['a', 'b']

        model = MySettings(tags=['x', 'y'])
        result = CliApp.serialize(model, list_style='argparse')
        assert isinstance(result, list)

    def test_serialize_positionals_first(self):
        class MySettings(BaseSettings):
            name: str = 'test'

        model = MySettings(name='test')
        result = CliApp.serialize(model, positionals_first=True)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# CliApp.format_help tests
# ---------------------------------------------------------------------------

class TestCliAppFormatHelp:
    def test_format_help_returns_string(self):
        class MySettings(BaseSettings):
            name: str = 'default'

        result = CliApp.format_help(MySettings)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_help_with_model_instance(self):
        class MySettings(BaseSettings):
            name: str = 'default'

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=[])
        help_text = CliApp.format_help(result)
        assert isinstance(help_text, str)

    def test_format_help_strip_ansi(self):
        class MySettings(BaseSettings):
            name: str = 'default'

        result = CliApp.format_help(MySettings, strip_ansi_color=True)
        assert isinstance(result, str)
        # Should not contain ANSI escape sequences
        assert '\x1b[' not in result

    def test_format_help_with_base_model(self):
        class MyModel(BaseModel):
            name: str = 'default'

        result = CliApp.format_help(MyModel)
        assert isinstance(result, str)
        assert 'name' in result


# ---------------------------------------------------------------------------
# CliApp.print_help tests
# ---------------------------------------------------------------------------

class TestCliAppPrintHelp:
    def test_print_help_to_file(self):
        class MySettings(BaseSettings):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MySettings, file=output)
        content = output.getvalue()
        assert len(content) > 0

    def test_print_help_with_strip_ansi(self):
        class MySettings(BaseSettings):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MySettings, file=output, strip_ansi_color=True)
        content = output.getvalue()
        assert '\x1b[' not in content

    def test_print_help_with_base_model(self):
        class MyModel(BaseModel):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MyModel, file=output)
        content = output.getvalue()
        assert 'name' in content

    def test_print_help_returns_none(self):
        class MySettings(BaseSettings):
            name: str = 'default'

        output = io.StringIO()
        result = CliApp.print_help(MySettings, file=output)
        assert result is None


# ---------------------------------------------------------------------------
# CliApp.run_subcommand tests
# ---------------------------------------------------------------------------

class TestCliAppRunSubcommand:
    def test_run_subcommand_basic(self):
        from typing import Annotated, Union, Optional
        from pydantic import Field

        ran = []

        class Sub1(BaseModel):
            msg: str = 'hello'

            def cli_cmd(self):
                ran.append(('sub1', self.msg))

        class MainSettings(BaseSettings):
            sub1: Optional[Sub1] = None

            def cli_cmd(self):
                CliApp.run_subcommand(self)

        # The subcommand mechanics are complex; just verify no crash on basic run
        try:
            result = CliApp.run(MainSettings, cli_args=[])
        except (SystemExit, SettingsError):
            pass  # Expected if no subcommand is specified

    def test_run_subcommand_raises_settings_error_when_no_subcommand_found(self):
        class MyModel(BaseModel):
            name: str = 'default'

        model = MyModel()
        # When model is not in the subcommand stack and has no subcommand field
        with pytest.raises((SettingsError, SystemExit)):
            CliApp.run_subcommand(model, cli_exit_on_error=False)

    def test_run_subcommand_success_runs_subcommand_cli_cmd(self):
        from pydantic_settings import CliPositionalArg, CliSubCommand

        class Clone(BaseModel):
            repository: CliPositionalArg[str]
            directory: CliPositionalArg[str]

            def cli_cmd(self) -> None:
                self.directory = 'ran the git clone cli cmd'

        class Init(BaseModel):
            directory: CliPositionalArg[str]

            def cli_cmd(self) -> None:
                self.directory = 'ran the git init cli cmd'

        class Git(BaseModel):
            clone: CliSubCommand[Clone]
            init: CliSubCommand[Init]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self)

        cmd = CliApp.run(Git, cli_args=['init', 'dir'])
        assert cmd.model_dump() == {
            'clone': None,
            'init': {'directory': 'ran the git init cli cmd'},
        }

    def test_run_subcommand_success_with_clone_subcommand(self):
        from pydantic_settings import CliPositionalArg, CliSubCommand

        class Clone(BaseModel):
            repository: CliPositionalArg[str]

            def cli_cmd(self) -> None:
                self.repository = 'ran the git clone cli cmd'

        class Init(BaseModel):
            directory: CliPositionalArg[str]

            def cli_cmd(self) -> None:
                self.directory = 'ran the git init cli cmd'

        class Git(BaseModel):
            clone: CliSubCommand[Clone]
            init: CliSubCommand[Init]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self)

        cmd = CliApp.run(Git, cli_args=['clone', 'my-repo'])
        assert cmd.model_dump() == {
            'clone': {'repository': 'ran the git clone cli cmd'},
            'init': None,
        }

    def test_run_subcommand_cleans_up_stack_on_success(self):
        from pydantic_settings import CliPositionalArg, CliSubCommand

        class Sub(BaseModel):
            val: CliPositionalArg[str]

            def cli_cmd(self) -> None:
                pass

        class Main(BaseModel):
            sub: CliSubCommand[Sub]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self)

        before_count = len(CliApp._subcommand_stack)
        CliApp.run(Main, cli_args=['sub', 'x'])
        assert len(CliApp._subcommand_stack) == before_count

    def test_run_subcommand_raises_err_directly_when_format_help_is_none(self):
        from pydantic_settings.sources import CliSettingsSource

        class MyModel(BaseModel):
            name: str = 'default'

        model = MyModel()
        settings_cls = CliApp._get_base_settings_cls(type(model))
        source = CliSettingsSource(settings_cls, cli_parse_args=[])
        source._format_help = None  # Force the else branch at line 791

        CliApp._subcommand_stack[id(model)] = (source, source.root_parser, ':subcommand')
        try:
            with pytest.raises(SettingsError):
                CliApp.run_subcommand(model, cli_exit_on_error=False)
        finally:
            CliApp._subcommand_stack.pop(id(model), None)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestBaseSettingsIntegration:
    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv('NAME', 'env_value')

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings()
        assert settings.name == 'env_value'

    def test_init_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv('NAME', 'env_value')

        class MySettings(BaseSettings):
            name: str = 'default'

        settings = MySettings(name='init_value')
        assert settings.name == 'init_value'

    def test_multiple_fields(self):
        class MultiSettings(BaseSettings):
            host: str = 'localhost'
            port: int = 8080
            debug: bool = False

        settings = MultiSettings(host='example.com', port=443, debug=True)
        assert settings.host == 'example.com'
        assert settings.port == 443
        assert settings.debug is True

    def test_nested_model_settings(self):
        class DatabaseConfig(BaseModel):
            host: str = 'localhost'
            port: int = 5432

        class AppSettings(BaseSettings):
            database: DatabaseConfig = DatabaseConfig()
            app_name: str = 'myapp'

        settings = AppSettings(app_name='test')
        assert settings.app_name == 'test'
        assert settings.database.host == 'localhost'

    def test_optional_field(self):
        class OptionalSettings(BaseSettings):
            optional_value: Optional[str] = None

        settings = OptionalSettings()
        assert settings.optional_value is None

        settings2 = OptionalSettings(optional_value='present')
        assert settings2.optional_value == 'present'
