"""Tests for pydantic_settings.main module covering BaseSettings and CliApp."""

import asyncio
import io
import warnings
from typing import Any, Optional
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
    SettingsError,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
    get_subcommand,
)
from pydantic_settings.sources import DefaultSettingsSource


# ── BaseSettings.__init__ tests ──


class TestBaseSettingsInit:
    def test_simple_init_with_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('MY_VAL', raising=False)

        class MySettings(BaseSettings):
            my_val: str = 'default'

        s = MySettings(my_val='hello')
        assert s.my_val == 'hello'

    def test_init_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('MY_VAL', raising=False)

        class MySettings(BaseSettings):
            my_val: str = 'default'

        s = MySettings()
        assert s.my_val == 'default'

    def test_init_reads_env_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAL', 'from_env')

        class MySettings(BaseSettings):
            my_val: str = 'default'

        s = MySettings()
        assert s.my_val == 'from_env'

    def test_init_with_case_sensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAL', 'lower')
        monkeypatch.setenv('my_val', 'exact')

        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(case_sensitive=True)
            my_val: str = 'default'

        s = MySettings(_case_sensitive=True)
        assert isinstance(s.my_val, str)

    def test_init_with_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('APP_MY_VAL', 'prefixed')

        class MySettings(BaseSettings):
            my_val: str = 'default'

        s = MySettings(_env_prefix='APP_')
        assert s.my_val == 'prefixed'

    def test_init_with_env_nested_delimiter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('SUB__NAME', 'nested_val')

        class SubModel(BaseModel):
            name: str = 'sub_default'

        class MySettings(BaseSettings):
            sub: SubModel = SubModel()

        s = MySettings(_env_nested_delimiter='__')
        assert s.sub.name == 'nested_val'

    def test_init_with_build_sources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('MY_VAL', raising=False)

        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources(my_val='built')
        s = MySettings(_build_sources=(sources, init_kwargs))
        assert s.my_val == 'built'

    def test_init_with_env_ignore_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAL', '')

        class MySettings(BaseSettings):
            my_val: str = 'default'

        s = MySettings(_env_ignore_empty=True)
        assert s.my_val == 'default'

    def test_init_with_env_parse_none_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAL', 'null')

        class MySettings(BaseSettings):
            my_val: Optional[str] = 'default'

        s = MySettings(_env_parse_none_str='null')
        assert s.my_val is None

    def test_init_with_cli_parse_args(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        s = MySettings(_cli_parse_args=['--my_val', 'from_cli'])
        assert s.my_val == 'from_cli'


# ── BaseSettings.settings_customise_sources tests ──


class TestSettingsCustomiseSources:
    def test_default_source_order(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        init_src = InitSettingsSource(MySettings, init_kwargs={})
        env_src = EnvSettingsSource(MySettings)
        dotenv_src = DotEnvSettingsSource(MySettings, env_file=None)
        secret_src = SecretsSettingsSource(MySettings, secrets_dir=None)

        result = MySettings.settings_customise_sources(
            MySettings,
            init_settings=init_src,
            env_settings=env_src,
            dotenv_settings=dotenv_src,
            file_secret_settings=secret_src,
        )
        assert result == (init_src, env_src, dotenv_src, secret_src)

    def test_custom_source_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('MY_VAL', raising=False)

        class MySettings(BaseSettings):
            my_val: str = 'default'

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: type[BaseSettings],
                init_settings: PydanticBaseSettingsSource,
                env_settings: PydanticBaseSettingsSource,
                dotenv_settings: PydanticBaseSettingsSource,
                file_secret_settings: PydanticBaseSettingsSource,
            ) -> tuple[PydanticBaseSettingsSource, ...]:
                return (env_settings, init_settings)

        s = MySettings(my_val='init_val')
        assert s.my_val == 'init_val'


# ── BaseSettings._settings_init_sources tests ──


class TestSettingsInitSources:
    def test_returns_sources_and_init_kwargs(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources(my_val='test')
        assert isinstance(sources, tuple)
        assert isinstance(init_kwargs, dict)
        assert 'my_val' in init_kwargs

    def test_sources_include_default_types(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        source_types = [type(s) for s in sources]
        assert InitSettingsSource in source_types
        assert EnvSettingsSource in source_types
        assert DotEnvSettingsSource in source_types
        assert SecretsSettingsSource in source_types
        assert DefaultSettingsSource in source_types

    def test_cli_source_added_when_cli_parse_args(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(_cli_parse_args=['--my_val', 'cli_val'])
        source_types = [type(s) for s in sources]
        assert CliSettingsSource in source_types

    def test_cli_settings_source_override(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=['--my_val', 'override'])
        sources, _ = MySettings._settings_init_sources(_cli_settings_source=cli_source)
        assert cli_source in sources

    def test_config_values_from_model_config(self) -> None:
        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='TEST_')
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert len(env_sources) > 0
        assert env_sources[0].env_prefix == 'TEST_'

    def test_parameter_overrides_model_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('OVERRIDE_MY_VAL', 'found')

        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='CONFIG_')
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(_env_prefix='OVERRIDE_')
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert env_sources[0].env_prefix == 'OVERRIDE_'

    def test_env_nested_max_split_passed(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(_env_nested_max_split=2)
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert len(env_sources) > 0

    def test_secrets_dir_passed(self, tmp_path: Any) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(_secrets_dir=str(tmp_path))
        secret_sources = [s for s in sources if isinstance(s, SecretsSettingsSource)]
        assert len(secret_sources) > 0

    def test_env_parse_enums_passed(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(_env_parse_enums=True)
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert len(env_sources) > 0

    def test_cli_parse_args_with_custom_cli_source_in_customise_sources(self) -> None:
        """When a custom CliSettingsSource is in customise_sources, cli_parse_args triggers parsing."""

        class MySettings(BaseSettings):
            my_val: str = 'default'

            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: type[BaseSettings],
                init_settings: PydanticBaseSettingsSource,
                env_settings: PydanticBaseSettingsSource,
                dotenv_settings: PydanticBaseSettingsSource,
                file_secret_settings: PydanticBaseSettingsSource,
            ) -> tuple[PydanticBaseSettingsSource, ...]:
                return (
                    CliSettingsSource(settings_cls, cli_parse_args=['--my_val', 'custom']),
                    init_settings,
                    env_settings,
                    dotenv_settings,
                    file_secret_settings,
                )

        s = MySettings()
        assert s.my_val == 'custom'

    def test_nested_model_default_partial_update(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('SUB', raising=False)
        monkeypatch.delenv('SUB__A', raising=False)
        monkeypatch.delenv('SUB__B', raising=False)

        class SubModel(BaseModel):
            a: str = 'a_default'
            b: str = 'b_default'

        class MySettings(BaseSettings):
            sub: SubModel = SubModel()

        s = MySettings(_nested_model_default_partial_update=True)
        assert s.sub.a == 'a_default'

    def test_env_prefix_target_passed(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(_env_prefix_target='alias')
        env_sources = [s for s in sources if isinstance(s, EnvSettingsSource)]
        assert len(env_sources) > 0

    def test_cli_various_options(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources(
            _cli_parse_args=['--my_val', 'val'],
            _cli_prog_name='test_prog',
            _cli_hide_none_type=True,
            _cli_avoid_json=True,
            _cli_enforce_required=False,
            _cli_use_class_docs_for_groups=False,
            _cli_exit_on_error=False,
            _cli_prefix='',
            _cli_flag_prefix_char='-',
            _cli_implicit_flags=False,
            _cli_ignore_unknown_args=False,
            _cli_kebab_case=False,
        )
        cli_sources = [s for s in sources if isinstance(s, CliSettingsSource)]
        assert len(cli_sources) > 0


# ── BaseSettings._settings_build_values tests ──


class TestSettingsBuildValues:
    def test_empty_sources_returns_empty_dict(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        result = MySettings._settings_build_values((), {})
        assert result == {}

    def test_build_values_with_init_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources(my_val='built')
        result = MySettings._settings_build_values(sources, init_kwargs)
        assert result['my_val'] == 'built'

    def test_build_values_strips_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('MY_VAL', raising=False)

        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources()
        result = MySettings._settings_build_values(sources, init_kwargs)
        # Default values should be stripped from the result
        assert 'my_val' not in result


# ── BaseSettings._settings_restore_init_kwarg_names tests ──


class TestSettingsRestoreInitKwargNames:
    def test_no_init_kwargs_no_change(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        state: dict[str, Any] = {'my_val': 'test'}
        MySettings._settings_restore_init_kwarg_names(MySettings, {}, state)
        assert state == {'my_val': 'test'}

    def test_no_state_no_change(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        state: dict[str, Any] = {}
        MySettings._settings_restore_init_kwarg_names(MySettings, {'my_val': 'test'}, state)
        assert state == {}

    def test_with_alias_restores_init_kwarg_name(self) -> None:
        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(populate_by_name=True)
            my_val: str = Field(default='default', alias='myVal')

        state: dict[str, Any] = {'myVal': 'aliased'}
        init_kwargs: dict[str, Any] = {'myVal': 'init_val'}
        MySettings._settings_restore_init_kwarg_names(MySettings, init_kwargs, state)
        assert 'myVal' in state

    def test_with_field_name_and_alias_in_state(self) -> None:
        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(populate_by_name=True)
            my_val: str = Field(default='default', alias='myVal')

        state: dict[str, Any] = {'my_val': 'field_val'}
        init_kwargs: dict[str, Any] = {'my_val': 'init_val'}
        MySettings._settings_restore_init_kwarg_names(MySettings, init_kwargs, state)
        assert 'my_val' in state


# ── BaseSettings._settings_warn_unused_config_keys tests ──


class TestSettingsWarnUnusedConfigKeys:
    def test_warns_for_json_file_without_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        non_json_sources = tuple(s for s in sources if not isinstance(s, JsonConfigSettingsSource))
        config = SettingsConfigDict(json_file='config.json')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_warn_unused_config_keys(non_json_sources, config)
            json_warnings = [x for x in w if 'json_file' in str(x.message)]
            assert len(json_warnings) > 0

    def test_warns_for_toml_file_without_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        non_toml_sources = tuple(s for s in sources if not isinstance(s, TomlConfigSettingsSource))
        config = SettingsConfigDict(toml_file='config.toml')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_warn_unused_config_keys(non_toml_sources, config)
            toml_warnings = [x for x in w if 'toml_file' in str(x.message)]
            assert len(toml_warnings) > 0

    def test_warns_for_yaml_file_without_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        non_yaml_sources = tuple(s for s in sources if not isinstance(s, YamlConfigSettingsSource))
        config = SettingsConfigDict(yaml_file='config.yaml')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_warn_unused_config_keys(non_yaml_sources, config)
            yaml_warnings = [x for x in w if 'yaml_file' in str(x.message)]
            assert len(yaml_warnings) > 0

    def test_warns_for_pyproject_toml_without_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        non_pyproject_sources = tuple(s for s in sources if not isinstance(s, PyprojectTomlConfigSettingsSource))
        config = SettingsConfigDict(pyproject_toml_depth=2)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_warn_unused_config_keys(non_pyproject_sources, config)
            pyproject_warnings = [x for x in w if 'pyproject_toml_depth' in str(x.message)]
            assert len(pyproject_warnings) > 0

    def test_no_warning_when_source_present(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        json_source = JsonConfigSettingsSource(MySettings, json_file='config.json')
        sources_with_json = sources + (json_source,)
        config = SettingsConfigDict(json_file='config.json')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_warn_unused_config_keys(sources_with_json, config)
            json_warnings = [x for x in w if 'json_file' in str(x.message)]
            assert len(json_warnings) == 0

    def test_no_warning_when_config_not_set(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        sources, _ = MySettings._settings_init_sources()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_warn_unused_config_keys(sources, MySettings.model_config)
            relevant_warnings = [
                x
                for x in w
                if any(
                    key in str(x.message)
                    for key in ('json_file', 'toml_file', 'yaml_file', 'pyproject_toml_depth')
                )
            ]
            assert len(relevant_warnings) == 0


# ── CliApp._get_base_settings_cls tests ──


class TestCliAppGetBaseSettingsCls:
    def test_returns_same_class_for_base_settings_subclass(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        result = CliApp._get_base_settings_cls(MySettings)
        assert result is MySettings

    def test_wraps_base_model_in_base_settings(self) -> None:
        class MyModel(BaseModel):
            my_val: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert issubclass(result, MyModel)

    def test_wrapped_model_has_correct_config(self) -> None:
        class MyModel(BaseModel):
            my_val: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.model_config.get('cli_avoid_json') is True
        assert result.model_config.get('cli_enforce_required') is True
        assert result.model_config.get('cli_kebab_case') is True
        assert result.model_config.get('case_sensitive') is True

    def test_wrapped_model_preserves_docstring(self) -> None:
        class MyModel(BaseModel):
            """My custom model docstring."""

            my_val: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.__doc__ == 'My custom model docstring.'


# ── CliApp._run_cli_cmd tests ──


class TestCliAppRunCliCmd:
    def test_returns_model_when_no_command(self) -> None:
        class MyModel(BaseModel):
            val: str = 'test'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_raises_when_command_required_but_missing(self) -> None:
        class MyModel(BaseModel):
            val: str = 'test'

        model = MyModel()
        with pytest.raises(SettingsError, match='missing cli_cmd entrypoint'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_runs_sync_command(self) -> None:
        class MyModel(BaseModel):
            val: str = 'test'
            executed: bool = False

            def cli_cmd(self) -> None:
                self.executed = True

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert result is model
        assert model.executed is True

    def test_runs_async_command(self) -> None:
        class MyModel(BaseModel):
            val: str = 'test'
            executed: bool = False

            async def cli_cmd(self) -> None:
                self.executed = True

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
        assert result is model
        assert model.executed is True

    def test_async_command_propagates_exception(self) -> None:
        class MyModel(BaseModel):
            val: str = 'test'

            async def cli_cmd(self) -> None:
                raise ValueError('async error')

        model = MyModel()
        with pytest.raises(ValueError, match='async error'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_async_command_in_running_loop(self) -> None:
        """Test async command when event loop is already running."""

        class MyModel(BaseModel):
            val: str = 'test'
            executed: bool = False

            async def cli_cmd(self) -> None:
                self.executed = True

        model = MyModel()

        async def _run_in_loop() -> None:
            import threading

            exception_container: list[Exception] = []

            def run_in_thread() -> None:
                try:
                    CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
                except Exception as e:
                    exception_container.append(e)

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            if exception_container:
                raise exception_container[0]

        asyncio.run(_run_in_loop())
        assert model.executed is True


# ── CliApp.run tests ──


class TestCliAppRun:
    def test_run_base_settings_subclass(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MySettings, cli_args=['--my_val', 'from_cli'])
        assert result.my_val == 'from_cli'

    def test_run_base_model(self) -> None:
        class MyModel(BaseModel):
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MyModel, cli_args=['--my-val', 'from_cli'])
        assert result.my_val == 'from_cli'

    def test_run_raises_for_non_model_class(self) -> None:
        with pytest.raises(SettingsError, match='is not subclass of BaseModel'):
            CliApp.run(str, cli_args=[])  # type: ignore

    def test_run_with_cli_settings_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=['--my_val', 'sourced'])
        result = CliApp.run(MySettings, cli_args=['--my_val', 'sourced'], cli_settings_source=cli_source)
        assert result.my_val == 'sourced'

    def test_run_with_dict_cli_args_and_settings_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        result = CliApp.run(
            MySettings,
            cli_args={'my_val': 'dict_val'},
            cli_settings_source=cli_source,
        )
        assert result.my_val == 'dict_val'

    def test_run_raises_for_dict_args_without_source(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

        with pytest.raises(SettingsError, match='must be list'):
            CliApp.run(MySettings, cli_args={'my_val': 'val'})  # type: ignore

    def test_run_with_model_init_data(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MySettings, cli_args=[], my_val='init_data')
        assert result.my_val == 'init_data'

    def test_run_with_cli_exit_on_error(self) -> None:
        class MySettings(BaseSettings):
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MySettings, cli_args=[], cli_exit_on_error=False)
        assert result.my_val == 'default'

    def test_run_pydantic_dataclass(self) -> None:
        @pydantic_dataclass
        class MyDataclass:
            my_val: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MyDataclass, cli_args=['--my-val', 'dc_val'])
        assert result.my_val == 'dc_val'

    def test_run_without_cli_cmd(self) -> None:
        """When cli_cmd is not required and not present, run still works."""

        class MySettings(BaseSettings):
            my_val: str = 'default'

        result = CliApp.run(MySettings, cli_args=['--my_val', 'val'])
        assert result.my_val == 'val'


# ── CliApp.serialize tests ──


class TestCliAppSerialize:
    def test_serialize_basic_model(self) -> None:
        class MyModel(BaseModel):
            name: str = 'test'
            count: int = 5

        model = MyModel(name='hello', count=10)
        result = CliApp.serialize(model)
        assert isinstance(result, list)
        assert '--name' in result
        assert 'hello' in result

    def test_serialize_base_settings(self) -> None:
        class MySettings(BaseSettings):
            name: str = 'test'

        s = MySettings(name='world')
        result = CliApp.serialize(s)
        assert isinstance(result, list)

    def test_serialize_with_list_style_argparse(self) -> None:
        class MyModel(BaseModel):
            tags: list[str] = ['a', 'b']

        model = MyModel()
        result = CliApp.serialize(model, list_style='argparse')
        assert isinstance(result, list)

    def test_serialize_with_dict_style_env(self) -> None:
        class MyModel(BaseModel):
            config: dict[str, str] = {'key': 'val'}

        model = MyModel()
        result = CliApp.serialize(model, dict_style='env')
        assert isinstance(result, list)


# ── CliApp.format_help tests ──


class TestCliAppFormatHelp:
    def test_format_help_for_model_class(self) -> None:
        class MyModel(BaseModel):
            """A test model."""

            name: str = 'default'

        help_text = CliApp.format_help(MyModel)
        assert isinstance(help_text, str)
        assert len(help_text) > 0

    def test_format_help_for_model_instance(self) -> None:
        class MySettings(BaseSettings):
            name: str = 'default'

        s = MySettings()
        help_text = CliApp.format_help(s)
        assert isinstance(help_text, str)

    def test_format_help_strip_ansi(self) -> None:
        class MyModel(BaseModel):
            name: str = 'default'

        help_text = CliApp.format_help(MyModel, strip_ansi_color=True)
        assert '\x1b[' not in help_text

    def test_format_help_with_custom_cli_source(self) -> None:
        class MySettings(BaseSettings):
            name: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        help_text = CliApp.format_help(MySettings, cli_settings_source=cli_source)
        assert isinstance(help_text, str)


# ── CliApp.print_help tests ──


class TestCliAppPrintHelp:
    def test_print_help_to_stream(self) -> None:
        class MyModel(BaseModel):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MyModel, file=output, strip_ansi_color=True)
        text = output.getvalue()
        assert len(text) > 0

    def test_print_help_model_class(self) -> None:
        class MySettings(BaseSettings):
            name: str = 'default'

        output = io.StringIO()
        CliApp.print_help(MySettings, file=output)
        assert len(output.getvalue()) > 0

    def test_print_help_with_cli_source(self) -> None:
        class MySettings(BaseSettings):
            name: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        output = io.StringIO()
        CliApp.print_help(MySettings, cli_settings_source=cli_source, file=output)
        assert len(output.getvalue()) > 0


# ── CliApp.run_subcommand tests ──


class TestCliAppRunSubcommand:
    def test_run_subcommand_basic(self) -> None:
        from typing import Annotated

        from pydantic_settings.sources.types import _CliSubCommand

        class SubCmd(BaseModel):
            val: str = 'sub_default'

            def cli_cmd(self) -> None:
                pass

        class MySettings(BaseSettings):
            sub: Annotated[SubCmd | None, _CliSubCommand]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self)

        result = CliApp.run(MySettings, cli_args=['sub', '--val', 'sub_val'])
        assert result is not None


# ── CliApp.run_coro (inner function) test ──


class TestCliAppRunCoro:
    def test_async_error_in_running_loop_propagates(self) -> None:
        """Test that exceptions from async commands in threads are propagated."""

        class MyModel(BaseModel):
            val: str = 'test'

            async def cli_cmd(self) -> None:
                raise RuntimeError('thread error')

        model = MyModel()
        with pytest.raises(RuntimeError, match='thread error'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)
