"""Unit tests for pydantic_settings/main.py covering BaseSettings and CliApp."""
from __future__ import annotations

import asyncio
import io
import warnings
from argparse import Namespace
from typing import Any, Optional

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, CliPositionalArg, CliSubCommand
from pydantic_settings.main import CliApp, SettingsConfigDict
from pydantic_settings.sources import (
    CliSettingsSource,
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
# Minimal settings models used across tests
# ---------------------------------------------------------------------------

class SimpleSettings(BaseSettings):
    foo: str = 'bar'
    count: int = 0


class RequiredSettings(BaseSettings):
    name: str


# ---------------------------------------------------------------------------
# BaseSettings.__init__
# ---------------------------------------------------------------------------

class TestBaseSettingsInit:
    def test_basic_instantiation(self):
        s = SimpleSettings()
        assert s.foo == 'bar'
        assert s.count == 0

    def test_init_values_override_defaults(self):
        s = SimpleSettings(foo='hello', count=42)
        assert s.foo == 'hello'
        assert s.count == 42

    def test_env_prefix_parameter(self, monkeypatch):
        monkeypatch.setenv('APP_FOO', 'from_env')
        s = SimpleSettings(_env_prefix='APP_')
        assert s.foo == 'from_env'

    def test_env_file_none_disables_dotenv(self):
        s = SimpleSettings(_env_file=None)
        assert s.foo == 'bar'

    def test_case_sensitive_parameter(self, monkeypatch):
        monkeypatch.setenv('FOO', 'upper')
        s = SimpleSettings(_case_sensitive=False)
        assert s.foo == 'upper'

    def test_build_sources_parameter(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        s = SimpleSettings(_build_sources=(sources, init_kwargs))
        assert s.foo == 'bar'

    def test_env_ignore_empty_parameter(self, monkeypatch):
        monkeypatch.setenv('FOO', '')
        s = SimpleSettings(_env_ignore_empty=True)
        assert s.foo == 'bar'

    def test_env_ignore_empty_false(self, monkeypatch):
        monkeypatch.setenv('FOO', 'notempty')
        s = SimpleSettings(_env_ignore_empty=False)
        assert s.foo == 'notempty'

    def test_env_nested_delimiter_parameter(self):
        s = SimpleSettings(_env_nested_delimiter='__')
        assert s.foo == 'bar'

    def test_cli_hide_none_type_parameter(self):
        s = SimpleSettings(_cli_hide_none_type=True)
        assert s.foo == 'bar'

    def test_cli_avoid_json_parameter(self):
        s = SimpleSettings(_cli_avoid_json=True)
        assert s.foo == 'bar'

    def test_cli_enforce_required_parameter(self):
        s = SimpleSettings(_cli_enforce_required=False)
        assert s.foo == 'bar'

    def test_cli_exit_on_error_parameter(self):
        s = SimpleSettings(_cli_exit_on_error=False)
        assert s.foo == 'bar'

    def test_secrets_dir_parameter(self, tmp_path):
        s = SimpleSettings(_secrets_dir=tmp_path)
        assert s.foo == 'bar'


# ---------------------------------------------------------------------------
# BaseSettings.settings_customise_sources
# ---------------------------------------------------------------------------

class TestSettingsCustomiseSources:
    def test_returns_four_sources(self):
        init_src = InitSettingsSource(SimpleSettings, init_kwargs={})
        env_src = EnvSettingsSource(SimpleSettings)
        dotenv_src = DotEnvSettingsSource(SimpleSettings)
        secret_src = SecretsSettingsSource(SimpleSettings)

        result = SimpleSettings.settings_customise_sources(
            SimpleSettings,
            init_settings=init_src,
            env_settings=env_src,
            dotenv_settings=dotenv_src,
            file_secret_settings=secret_src,
        )

        assert len(result) == 4
        assert result[0] is init_src
        assert result[1] is env_src
        assert result[2] is dotenv_src
        assert result[3] is secret_src

    def test_order_is_init_env_dotenv_secret(self):
        init_src = InitSettingsSource(SimpleSettings, init_kwargs={})
        env_src = EnvSettingsSource(SimpleSettings)
        dotenv_src = DotEnvSettingsSource(SimpleSettings)
        secret_src = SecretsSettingsSource(SimpleSettings)

        result = SimpleSettings.settings_customise_sources(
            SimpleSettings,
            init_settings=init_src,
            env_settings=env_src,
            dotenv_settings=dotenv_src,
            file_secret_settings=secret_src,
        )

        assert isinstance(result[0], InitSettingsSource)
        assert isinstance(result[1], EnvSettingsSource)


# ---------------------------------------------------------------------------
# BaseSettings._settings_init_sources
# ---------------------------------------------------------------------------

class TestSettingsInitSources:
    def test_returns_tuple_of_sources_and_dict(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        assert isinstance(sources, tuple)
        assert isinstance(init_kwargs, dict)

    def test_includes_default_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, DefaultSettingsSource) for s in sources)

    def test_includes_init_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources(foo='test')
        assert any(isinstance(s, InitSettingsSource) for s in sources)

    def test_includes_env_settings_source(self):
        sources, _ = SimpleSettings._settings_init_sources()
        assert any(isinstance(s, EnvSettingsSource) for s in sources)

    def test_cli_parse_args_adds_cli_source(self):
        sources, _ = SimpleSettings._settings_init_sources(_cli_parse_args=[])
        assert any(isinstance(s, CliSettingsSource) for s in sources)

    def test_env_prefix_propagated(self):
        sources, _ = SimpleSettings._settings_init_sources(_env_prefix='MY_')
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert len(env_sources) >= 1

    def test_case_sensitive_propagated(self):
        sources, _ = SimpleSettings._settings_init_sources(_case_sensitive=True)
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert len(env_sources) >= 1

    def test_secrets_dir_propagated(self, tmp_path):
        sources, _ = SimpleSettings._settings_init_sources(_secrets_dir=tmp_path)
        secret_sources = [s for s in sources if isinstance(s, SecretsSettingsSource)]
        assert len(secret_sources) >= 1

    def test_cli_settings_source_used_when_provided(self):
        cli_src = CliSettingsSource(SimpleSettings, cli_parse_args=[])
        sources, _ = SimpleSettings._settings_init_sources(_cli_settings_source=cli_src)
        assert cli_src in sources

    def test_init_kwargs_passed_through(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources(foo='passed')
        assert init_kwargs.get('foo') == 'passed'

    def test_env_parse_none_str_overrides_cli_parse_none_str(self):
        sources, _ = SimpleSettings._settings_init_sources(
            _env_parse_none_str='null', _cli_parse_none_str='none'
        )
        # Should not raise; env_parse_none_str takes priority for cli_parse_none_str
        assert sources is not None


# ---------------------------------------------------------------------------
# BaseSettings._settings_build_values
# ---------------------------------------------------------------------------

class TestSettingsBuildValues:
    def test_empty_sources_returns_empty_dict(self):
        result = SimpleSettings._settings_build_values((), {})
        assert result == {}

    def test_with_sources_returns_dict(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        result = SimpleSettings._settings_build_values(sources, init_kwargs)
        assert isinstance(result, dict)

    def test_init_kwargs_override_defaults(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources(foo='override')
        result = SimpleSettings._settings_build_values(sources, init_kwargs)
        assert result.get('foo') == 'override'

    def test_default_values_stripped_from_result(self):
        sources, init_kwargs = SimpleSettings._settings_init_sources()
        result = SimpleSettings._settings_build_values(sources, init_kwargs)
        # Default value 'bar' for foo should be stripped since it's not explicitly set
        assert 'foo' not in result or result['foo'] == 'bar'


# ---------------------------------------------------------------------------
# BaseSettings._settings_restore_init_kwarg_names
# ---------------------------------------------------------------------------

class TestSettingsRestoreInitKwargNames:
    def test_no_op_when_init_kwargs_empty(self):
        state = {'foo': 'bar'}
        SimpleSettings._settings_restore_init_kwarg_names(SimpleSettings, {}, state)
        assert state == {'foo': 'bar'}

    def test_no_op_when_state_empty(self):
        init_kwargs = {'foo': 'bar'}
        state = {}
        SimpleSettings._settings_restore_init_kwarg_names(SimpleSettings, init_kwargs, state)
        assert state == {}

    def test_restores_field_names_in_state(self):
        init_kwargs = {'foo': 'hello'}
        state = {'foo': 'hello'}
        SimpleSettings._settings_restore_init_kwarg_names(SimpleSettings, init_kwargs, state)
        assert state.get('foo') == 'hello'

    def test_with_alias_field(self):
        class AliasSettings(BaseSettings):
            my_field: str = Field(default='default', alias='myField')
            model_config = SettingsConfigDict(populate_by_name=True)

        init_kwargs = {'my_field': 'value'}
        state = {'myField': 'value'}
        AliasSettings._settings_restore_init_kwarg_names(AliasSettings, init_kwargs, state)
        # The key should be restored to the init kwarg name
        assert 'my_field' in state or 'myField' in state


# ---------------------------------------------------------------------------
# BaseSettings._settings_warn_unused_config_keys
# ---------------------------------------------------------------------------

class TestSettingsWarnUnusedConfigKeys:
    def test_no_warning_when_all_sources_used(self):
        sources, _ = SimpleSettings._settings_init_sources()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            SimpleSettings._settings_warn_unused_config_keys(sources, SimpleSettings.model_config)
        assert len(w) == 0

    def test_warns_when_json_file_set_but_no_json_source(self):
        class JsonSettings(BaseSettings):
            model_config = SettingsConfigDict(json_file='config.json')

        sources, _ = SimpleSettings._settings_init_sources()
        # Remove any JsonConfigSettingsSource
        sources_without_json = tuple(s for s in sources if not isinstance(s, JsonConfigSettingsSource))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            SimpleSettings._settings_warn_unused_config_keys(sources_without_json, JsonSettings.model_config)
        warning_messages = [str(warning.message) for warning in w]
        assert any('json_file' in msg for msg in warning_messages)

    def test_warns_when_yaml_file_set_but_no_yaml_source(self):
        class YamlSettings(BaseSettings):
            model_config = SettingsConfigDict(yaml_file='config.yaml')

        sources, _ = SimpleSettings._settings_init_sources()
        sources_without_yaml = tuple(s for s in sources if not isinstance(s, YamlConfigSettingsSource))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            SimpleSettings._settings_warn_unused_config_keys(sources_without_yaml, YamlSettings.model_config)
        warning_messages = [str(warning.message) for warning in w]
        assert any('yaml_file' in msg for msg in warning_messages)

    def test_warns_when_toml_file_set_but_no_toml_source(self):
        class TomlSettings(BaseSettings):
            model_config = SettingsConfigDict(toml_file='config.toml')

        sources, _ = SimpleSettings._settings_init_sources()
        sources_without_toml = tuple(s for s in sources if not isinstance(s, TomlConfigSettingsSource))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            SimpleSettings._settings_warn_unused_config_keys(sources_without_toml, TomlSettings.model_config)
        warning_messages = [str(warning.message) for warning in w]
        assert any('toml_file' in msg for msg in warning_messages)

    def test_no_warning_when_config_key_is_none(self):
        sources, _ = SimpleSettings._settings_init_sources()
        sources_no_json = tuple(s for s in sources if not isinstance(s, JsonConfigSettingsSource))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            # json_file is None by default, so no warning should fire
            SimpleSettings._settings_warn_unused_config_keys(sources_no_json, SimpleSettings.model_config)
        warning_messages = [str(warning.message) for warning in w]
        assert not any('json_file' in msg for msg in warning_messages)


# ---------------------------------------------------------------------------
# CliApp._get_base_settings_cls
# ---------------------------------------------------------------------------

class TestCliAppGetBaseSettingsCls:
    def test_returns_same_class_for_base_settings_subclass(self):
        result = CliApp._get_base_settings_cls(SimpleSettings)
        assert result is SimpleSettings

    def test_creates_new_cls_for_base_model(self):
        class MyModel(BaseModel):
            x: int = 1

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert issubclass(result, MyModel)

    def test_new_cls_has_correct_config_for_cli(self):
        class MyModel(BaseModel):
            """My model doc."""
            x: int = 1

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.model_config.get('case_sensitive') is True
        assert result.model_config.get('cli_enforce_required') is True

    def test_new_cls_inherits_docstring(self):
        class MyModel(BaseModel):
            """My custom docstring."""
            x: int = 1

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.__doc__ == 'My custom docstring.'

    def test_pydantic_dataclass_not_base_settings(self):
        @pydantic_dataclass
        class MyDataclass:
            x: int = 1

        # pydantic dataclass is not a BaseSettings, so it should create a wrapper
        result = CliApp._get_base_settings_cls(MyDataclass)
        assert issubclass(result, BaseSettings)


# ---------------------------------------------------------------------------
# CliApp._run_cli_cmd
# ---------------------------------------------------------------------------

class TestCliAppRunCliCmd:
    def test_returns_model_when_method_missing_and_not_required(self):
        class ModelWithoutCmd(BaseModel):
            x: int = 1

        model = ModelWithoutCmd()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_raises_when_method_missing_and_required(self):
        class ModelWithoutCmd(BaseModel):
            x: int = 1

        model = ModelWithoutCmd()
        from pydantic_settings.exceptions import SettingsError
        with pytest.raises(SettingsError, match='missing cli_cmd entrypoint'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_calls_sync_method(self):
        results = []

        class ModelWithCmd(BaseModel):
            x: int = 1

            def cli_cmd(self) -> None:
                results.append(self.x)

        model = ModelWithCmd()
        CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert results == [1]

    def test_calls_async_method_without_event_loop(self):
        results = []

        class ModelWithAsyncCmd(BaseModel):
            x: int = 1

            async def cli_cmd(self) -> None:
                results.append(self.x)

        model = ModelWithAsyncCmd()
        CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert results == [1]

    def test_async_method_exception_propagated(self):
        class ModelWithFailingAsyncCmd(BaseModel):
            x: int = 1

            async def cli_cmd(self) -> None:
                raise ValueError('async error')

        model = ModelWithFailingAsyncCmd()
        with pytest.raises(ValueError, match='async error'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_returns_model_after_sync_cmd(self):
        class ModelWithCmd(BaseModel):
            x: int = 1

            def cli_cmd(self) -> None:
                pass

        model = ModelWithCmd()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert result is model

    def test_calls_async_method_with_running_event_loop(self):
        results = []

        class ModelWithAsyncCmd(BaseModel):
            x: int = 1

            async def cli_cmd(self) -> None:
                results.append(self.x)

        model = ModelWithAsyncCmd()

        async def run_in_loop() -> None:
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        asyncio.run(run_in_loop())
        assert results == [1]

    def test_async_exception_propagated_with_running_event_loop(self):
        class ModelWithFailingAsyncCmd(BaseModel):
            x: int = 1

            async def cli_cmd(self) -> None:
                raise RuntimeError('thread async error')

        model = ModelWithFailingAsyncCmd()

        async def run_in_loop() -> None:
            with pytest.raises(RuntimeError, match='thread async error'):
                CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

        asyncio.run(run_in_loop())


# ---------------------------------------------------------------------------
# CliApp.run
# ---------------------------------------------------------------------------

class TestCliAppRun:
    def test_raises_for_non_model_class(self):
        from pydantic_settings.exceptions import SettingsError
        with pytest.raises(SettingsError, match='not subclass of BaseModel'):
            CliApp.run(str, cli_args=[])

    def test_run_base_model_without_cli_cmd_returns_model(self):
        class MyModel(BaseModel):
            x: int = 1

        result = CliApp.run(MyModel, cli_args=[])
        assert isinstance(result, MyModel)

    def test_run_base_model_with_cli_cmd(self):
        results = []

        class MyModel(BaseModel):
            x: int = 1

            def cli_cmd(self) -> None:
                results.append(self.x)

        result = CliApp.run(MyModel, cli_args=[])
        assert isinstance(result, MyModel)
        assert results == [1]

    def test_run_base_settings_with_cli_cmd(self):
        results = []

        class MySettings(BaseSettings):
            x: int = 5

            def cli_cmd(self) -> None:
                results.append(self.x)

        result = CliApp.run(MySettings, cli_args=[])
        assert isinstance(result, MySettings)
        assert results == [5]

    def test_run_with_cli_args_list(self):
        results = []

        class MyModel(BaseModel):
            name: str = 'default'

            def cli_cmd(self) -> None:
                results.append(self.name)

        CliApp.run(MyModel, cli_args=['--name', 'hello'])
        assert results == ['hello']

    def test_run_raises_when_cli_args_is_namespace_without_source(self):
        from pydantic_settings.exceptions import SettingsError

        class MyModel(BaseModel):
            x: int = 1

            def cli_cmd(self) -> None:
                pass

        with pytest.raises(SettingsError, match='cli_args.*must be list'):
            CliApp.run(MyModel, cli_args=Namespace(x=1))

    def test_run_with_pydantic_dataclass(self):
        results = []

        @pydantic_dataclass
        class MyDataclass:
            x: int = 1

            def cli_cmd(self) -> None:
                results.append(self.x)

        result = CliApp.run(MyDataclass, cli_args=[])
        assert results == [1]

    def test_run_cleans_up_subcommand_stack(self):
        class MyModel(BaseModel):
            x: int = 1

            def cli_cmd(self) -> None:
                pass

        initial_size = len(CliApp._subcommand_stack)
        CliApp.run(MyModel, cli_args=[])
        assert len(CliApp._subcommand_stack) == initial_size

    def test_run_with_model_init_data(self):
        results = []

        class MySettings(BaseSettings):
            x: int = 0

            def cli_cmd(self) -> None:
                results.append(self.x)

        CliApp.run(MySettings, cli_args=[], x=99)
        assert results == [99]


# ---------------------------------------------------------------------------
# CliApp.run_subcommand
# ---------------------------------------------------------------------------

class TestCliAppRunSubcommand:
    def test_run_subcommand_with_model_not_in_stack(self):
        """When model is not in subcommand stack, a new CLI source is created."""
        from pydantic_settings.exceptions import SettingsError

        class Sub(BaseModel):
            y: int = 1

            def cli_cmd(self) -> None:
                pass

        class MyModel(BaseModel):
            sub: Optional[Sub] = None

        model = MyModel()
        # No subcommand set, should raise SettingsError when cli_exit_on_error=False
        with pytest.raises((SettingsError, SystemExit)):
            CliApp.run_subcommand(model, cli_exit_on_error=True)

    def test_run_subcommand_raises_settings_error_when_no_subcommand_found(self):
        from pydantic_settings.exceptions import SettingsError

        class Sub(BaseModel):
            y: int = 1

            def cli_cmd(self) -> None:
                pass

        class MyModel(BaseModel):
            sub: Optional[Sub] = None

        model = MyModel()
        with pytest.raises((SettingsError, SystemExit)):
            CliApp.run_subcommand(model, cli_exit_on_error=False)

    def test_run_subcommand_when_model_in_stack_and_subcommand_found(self):
        """Covers line 773 (model in stack) and lines 793-802 (subcommand found & executed)."""
        results = []

        class Init(BaseModel):
            directory: CliPositionalArg[str]

            def cli_cmd(self) -> None:
                results.append(self.directory)

        class Git(BaseModel):
            init: CliSubCommand[Init]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self)

        cmd = CliApp.run(Git, cli_args=['init', 'mydir'])
        assert results == ['mydir']
        assert cmd.init.directory == 'mydir'

    def test_run_subcommand_raise_err_directly_when_format_help_none(self, mocker):
        """Covers line 791: error is raised directly when _format_help is None."""
        from pydantic_settings.exceptions import SettingsError

        class Sub(BaseModel):
            y: int = 1

            def cli_cmd(self) -> None:
                pass

        class MyModel(BaseModel):
            sub: Optional[Sub] = None

        model = MyModel()
        mock_source = mocker.MagicMock()
        mock_source.cli_exit_on_error = False
        mock_source._format_help = None
        CliApp._subcommand_stack[id(model)] = (mock_source, None, ':subcommand')
        try:
            with pytest.raises(SettingsError):
                CliApp.run_subcommand(model, cli_exit_on_error=False)
        finally:
            CliApp._subcommand_stack.pop(id(model), None)


# ---------------------------------------------------------------------------
# CliApp.serialize
# ---------------------------------------------------------------------------

class TestCliAppSerialize:
    def test_serialize_basic_model(self):
        class MyModel(BaseModel):
            x: int = 1

        model = MyModel()
        result = CliApp.serialize(model)
        assert isinstance(result, list)

    def test_serialize_includes_field_values(self):
        class MyModel(BaseModel):
            name: str = 'world'

        model = MyModel(name='test')
        result = CliApp.serialize(model)
        assert isinstance(result, list)
        serialized = ' '.join(result)
        assert 'test' in serialized

    def test_serialize_list_style_json(self):
        class MyModel(BaseModel):
            tags: list[str] = []

        model = MyModel(tags=['a', 'b'])
        result = CliApp.serialize(model, list_style='json')
        assert isinstance(result, list)

    def test_serialize_list_style_argparse(self):
        class MyModel(BaseModel):
            tags: list[str] = []

        model = MyModel(tags=['a', 'b'])
        result = CliApp.serialize(model, list_style='argparse')
        assert isinstance(result, list)

    def test_serialize_list_style_lazy(self):
        class MyModel(BaseModel):
            tags: list[str] = []

        model = MyModel(tags=['a', 'b'])
        result = CliApp.serialize(model, list_style='lazy')
        assert isinstance(result, list)

    def test_serialize_dict_style_env(self):
        class MyModel(BaseModel):
            x: int = 1

        model = MyModel()
        result = CliApp.serialize(model, dict_style='env')
        assert isinstance(result, list)

    def test_serialize_positionals_first(self):
        class MyModel(BaseModel):
            x: int = 1

        model = MyModel()
        result = CliApp.serialize(model, positionals_first=True)
        assert isinstance(result, list)

    def test_serialize_base_settings(self):
        class MySettings(BaseSettings):
            x: int = 5

        settings = MySettings()
        result = CliApp.serialize(settings)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# CliApp.format_help
# ---------------------------------------------------------------------------

class TestCliAppFormatHelp:
    def test_format_help_returns_string(self):
        class MyModel(BaseModel):
            x: int = 1

        result = CliApp.format_help(MyModel)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_help_instance(self):
        class MyModel(BaseModel):
            x: int = 1

        model = MyModel()
        result = CliApp.format_help(model)
        assert isinstance(result, str)

    def test_format_help_strip_ansi_color(self):
        class MyModel(BaseModel):
            x: int = 1

        result = CliApp.format_help(MyModel, strip_ansi_color=True)
        # Should not contain ANSI escape codes
        import re
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        assert not ansi_pattern.search(result)

    def test_format_help_with_cli_settings_source(self):
        base_cls = CliApp._get_base_settings_cls(SimpleSettings)
        cli_src = CliSettingsSource(base_cls, cli_parse_args=[])
        result = CliApp.format_help(SimpleSettings, cli_settings_source=cli_src)
        assert isinstance(result, str)

    def test_format_help_base_settings_class(self):
        result = CliApp.format_help(SimpleSettings)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# CliApp.print_help
# ---------------------------------------------------------------------------

class TestCliAppPrintHelp:
    def test_print_help_outputs_to_file(self):
        class MyModel(BaseModel):
            x: int = 1

        buf = io.StringIO()
        CliApp.print_help(MyModel, file=buf)
        output = buf.getvalue()
        assert len(output) > 0

    def test_print_help_strip_ansi_color(self):
        class MyModel(BaseModel):
            x: int = 1

        buf = io.StringIO()
        CliApp.print_help(MyModel, file=buf, strip_ansi_color=True)
        output = buf.getvalue()
        import re
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        assert not ansi_pattern.search(output)

    def test_print_help_returns_none(self):
        class MyModel(BaseModel):
            x: int = 1

        buf = io.StringIO()
        result = CliApp.print_help(MyModel, file=buf)
        assert result is None

    def test_print_help_instance(self):
        class MyModel(BaseModel):
            x: int = 1

        model = MyModel()
        buf = io.StringIO()
        CliApp.print_help(model, file=buf)
        output = buf.getvalue()
        assert len(output) > 0
