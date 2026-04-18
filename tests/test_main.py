"""Tests for pydantic_settings.main module."""

from __future__ import annotations

import asyncio
import io
import warnings
from typing import Any, Optional
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources import (
    CliSettingsSource,
    CliSubCommand,
    DefaultSettingsSource,
    DotEnvSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SecretsSettingsSource,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
    get_subcommand,
)


# ──────────────────────────────────────────────────────────────────────
# BaseSettings.__init__
# ──────────────────────────────────────────────────────────────────────


class TestBaseSettingsInit:
    def test_basic_init_with_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings(my_var='hello')
        assert s.my_var == 'hello'

    def test_init_defaults(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings()
        assert s.my_var == 'default'

    def test_init_with_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAR', 'from_env')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings()
        assert s.my_var == 'from_env'

    def test_init_values_override_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAR', 'from_env')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings(my_var='from_init')
        assert s.my_var == 'from_init'

    def test_init_with_case_sensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAR', 'lower')
        monkeypatch.setenv('my_var', 'exact')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings(_case_sensitive=True)
        assert s.my_var == 'exact'

    def test_init_with_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('APP_MY_VAR', 'prefixed')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings(_env_prefix='APP_')
        assert s.my_var == 'prefixed'

    def test_init_with_env_nested_delimiter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('SUB__NAME', 'nested_val')

        class SubModel(BaseModel):
            name: str = 'default_sub'

        class MySettings(BaseSettings):
            sub: SubModel = SubModel()

        s = MySettings(_env_nested_delimiter='__')
        assert s.sub.name == 'nested_val'

    def test_init_with_build_sources(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources(my_var='built')
        s = MySettings(_build_sources=(sources, init_kwargs))
        assert s.my_var == 'built'

    def test_init_with_cli_parse_args(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings(_cli_parse_args=['--my_var', 'cli_val'])
        assert s.my_var == 'cli_val'

    def test_init_with_env_ignore_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAR', '')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings(_env_ignore_empty=True)
        assert s.my_var == 'default'


# ──────────────────────────────────────────────────────────────────────
# BaseSettings.settings_customise_sources
# ──────────────────────────────────────────────────────────────────────


class TestSettingsCustomiseSources:
    def test_default_source_order(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        init_src = InitSettingsSource(MySettings, init_kwargs={})
        env_src = EnvSettingsSource(MySettings)
        dotenv_src = DotEnvSettingsSource(MySettings)
        secrets_src = SecretsSettingsSource(MySettings)

        result = MySettings.settings_customise_sources(
            MySettings,
            init_settings=init_src,
            env_settings=env_src,
            dotenv_settings=dotenv_src,
            file_secret_settings=secrets_src,
        )
        assert result == (init_src, env_src, dotenv_src, secrets_src)

    def test_custom_source_order(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

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

        sources, _ = MySettings._settings_init_sources(my_var='test')
        source_types = [type(s) for s in sources]
        assert EnvSettingsSource in source_types
        assert InitSettingsSource in source_types


# ──────────────────────────────────────────────────────────────────────
# BaseSettings._settings_init_sources
# ──────────────────────────────────────────────────────────────────────


class TestSettingsInitSources:
    def test_returns_tuple_of_sources_and_kwargs(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        result = MySettings._settings_init_sources(my_var='test')
        assert isinstance(result, tuple)
        assert len(result) == 2
        sources, init_kwargs = result
        assert isinstance(sources, tuple)
        assert isinstance(init_kwargs, dict)

    def test_default_sources_created(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, _ = MySettings._settings_init_sources()
        source_types = [type(s) for s in sources]
        assert InitSettingsSource in source_types
        assert EnvSettingsSource in source_types
        assert DotEnvSettingsSource in source_types
        assert SecretsSettingsSource in source_types
        assert DefaultSettingsSource in source_types

    def test_cli_parse_args_adds_cli_source(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, _ = MySettings._settings_init_sources(_cli_parse_args=['--my_var', 'test'])
        source_types = [type(s) for s in sources]
        assert CliSettingsSource in source_types

    def test_cli_settings_source_passed_directly(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=['--my_var', 'direct'])
        sources, _ = MySettings._settings_init_sources(_cli_settings_source=cli_source)
        assert cli_source in sources

    def test_env_prefix_passed_to_env_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('TEST_MY_VAR', 'prefixed')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources(_env_prefix='TEST_')
        values = MySettings._settings_build_values(sources, init_kwargs)
        assert values.get('my_var') == 'prefixed'

    def test_model_config_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('CFG_MY_VAR', 'from_config')

        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix='CFG_')
            my_var: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources()
        values = MySettings._settings_build_values(sources, init_kwargs)
        assert values.get('my_var') == 'from_config'

    def test_init_kwargs_preserved(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        _, init_kwargs = MySettings._settings_init_sources(my_var='preserved')
        assert init_kwargs['my_var'] == 'preserved'

    def test_env_parse_none_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAR', 'null')

        class MySettings(BaseSettings):
            my_var: Optional[str] = 'default'

        s = MySettings(_env_parse_none_str='null')
        assert s.my_var is None

    def test_env_nested_max_split(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('A__B__C', 'val')

        class Inner(BaseModel):
            c: str = 'inner_default'

        class Sub(BaseModel):
            b: Inner = Inner()

        class MySettings(BaseSettings):
            a: Sub = Sub()

        s = MySettings(_env_nested_delimiter='__', _env_nested_max_split=1)
        # With max_split=1, only the first delimiter is split
        assert isinstance(s.a, Sub)

    def test_cli_with_all_options(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, _ = MySettings._settings_init_sources(
            _cli_parse_args=['--my_var', 'test'],
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
        assert len(cli_sources) == 1

    def test_warns_unused_config_keys(self) -> None:
        class MySettings(BaseSettings):
            model_config = SettingsConfigDict(json_file='test.json')
            my_var: str = 'default'

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            MySettings._settings_init_sources()
            json_warnings = [x for x in w if 'json_file' in str(x.message)]
            assert len(json_warnings) >= 1

    def test_custom_sources_with_cli_already_included(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

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
                    CliSettingsSource(settings_cls, cli_parse_args=['--my_var', 'custom_cli']),
                    init_settings,
                    env_settings,
                )

        sources, _ = MySettings._settings_init_sources()
        cli_sources = [s for s in sources if isinstance(s, CliSettingsSource)]
        assert len(cli_sources) == 1

    def test_nested_model_default_partial_update(self) -> None:
        class Sub(BaseModel):
            a: str = 'default_a'
            b: str = 'default_b'

        class MySettings(BaseSettings):
            sub: Sub = Sub()

        s = MySettings(_nested_model_default_partial_update=True, sub={'a': 'changed'})
        assert s.sub.a == 'changed'
        assert s.sub.b == 'default_b'


# ──────────────────────────────────────────────────────────────────────
# BaseSettings._settings_build_values
# ──────────────────────────────────────────────────────────────────────


class TestSettingsBuildValues:
    def test_build_values_with_sources(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources(my_var='test_val')
        values = MySettings._settings_build_values(sources, init_kwargs)
        assert values['my_var'] == 'test_val'

    def test_build_values_empty_sources(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        result = MySettings._settings_build_values((), {})
        assert result == {}

    def test_build_values_strips_defaults(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'
            other: str = 'other_default'

        sources, init_kwargs = MySettings._settings_init_sources(my_var='changed')
        values = MySettings._settings_build_values(sources, init_kwargs)
        assert 'my_var' in values
        assert 'other' not in values

    def test_build_values_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv('MY_VAR', 'env_val')

        class MySettings(BaseSettings):
            my_var: str = 'default'

        sources, init_kwargs = MySettings._settings_init_sources()
        values = MySettings._settings_build_values(sources, init_kwargs)
        assert values['my_var'] == 'env_val'


# ──────────────────────────────────────────────────────────────────────
# BaseSettings._settings_restore_init_kwarg_names
# ──────────────────────────────────────────────────────────────────────


class TestRestoreInitKwargNames:
    def test_no_init_kwargs_no_change(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        state: dict[str, Any] = {'my_var': 'val'}
        MySettings._settings_restore_init_kwarg_names(MySettings, {}, state)
        assert state == {'my_var': 'val'}

    def test_no_state_no_change(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        state: dict[str, Any] = {}
        MySettings._settings_restore_init_kwarg_names(MySettings, {'my_var': 'x'}, state)
        assert state == {}

    def test_restores_aliased_init_kwarg(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = Field(default='default', alias='myVar')
            model_config = SettingsConfigDict(populate_by_name=True)

        state: dict[str, Any] = {'myVar': 'val'}
        MySettings._settings_restore_init_kwarg_names(MySettings, {'my_var': 'val'}, state)
        assert 'my_var' in state
        assert state['my_var'] == 'val'


# ──────────────────────────────────────────────────────────────────────
# BaseSettings._settings_warn_unused_config_keys
# ──────────────────────────────────────────────────────────────────────


class TestSettingsWarnUnusedConfigKeys:
    def test_warns_on_json_file_without_json_source(self) -> None:
        sources = (InitSettingsSource(BaseSettings, init_kwargs={}),)
        config = SettingsConfigDict(json_file='test.json')  # type: ignore[typeddict-unknown-key]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, config)
            messages = [str(x.message) for x in w]
            assert any('json_file' in m for m in messages)

    def test_warns_on_toml_file_without_toml_source(self) -> None:
        sources = (InitSettingsSource(BaseSettings, init_kwargs={}),)
        config = SettingsConfigDict(toml_file='test.toml')  # type: ignore[typeddict-unknown-key]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, config)
            messages = [str(x.message) for x in w]
            assert any('toml_file' in m for m in messages)

    def test_warns_on_yaml_file_without_yaml_source(self) -> None:
        sources = (InitSettingsSource(BaseSettings, init_kwargs={}),)
        config = SettingsConfigDict(yaml_file='test.yaml')  # type: ignore[typeddict-unknown-key]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, config)
            messages = [str(x.message) for x in w]
            assert any('yaml_file' in m for m in messages)

    def test_warns_on_pyproject_toml_without_pyproject_source(self) -> None:
        sources = (InitSettingsSource(BaseSettings, init_kwargs={}),)
        config = SettingsConfigDict(pyproject_toml_depth=2)  # type: ignore[typeddict-unknown-key]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, config)
            messages = [str(x.message) for x in w]
            assert any('pyproject_toml_depth' in m for m in messages)

    def test_no_warning_when_source_present(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        json_source = JsonConfigSettingsSource(MySettings)
        sources = (InitSettingsSource(MySettings, init_kwargs={}), json_source)
        config = SettingsConfigDict(json_file='test.json')  # type: ignore[typeddict-unknown-key]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, config)
            json_warnings = [x for x in w if 'json_file' in str(x.message)]
            assert len(json_warnings) == 0

    def test_no_warning_when_config_not_set(self) -> None:
        sources = (InitSettingsSource(BaseSettings, init_kwargs={}),)
        config = SettingsConfigDict()  # type: ignore[typeddict-unknown-key]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            BaseSettings._settings_warn_unused_config_keys(sources, config)
            assert len(w) == 0


# ──────────────────────────────────────────────────────────────────────
# CliApp._get_base_settings_cls
# ──────────────────────────────────────────────────────────────────────


class TestCliAppGetBaseSettingsCls:
    def test_returns_same_cls_for_base_settings_subclass(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        result = CliApp._get_base_settings_cls(MySettings)
        assert result is MySettings

    def test_wraps_base_model_in_settings(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert issubclass(result, MyModel)

    def test_wrapped_model_has_correct_config(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.model_config.get('cli_avoid_json') is True
        assert result.model_config.get('cli_enforce_required') is True
        assert result.model_config.get('cli_kebab_case') is True

    def test_wrapped_model_preserves_docstring(self) -> None:
        class MyModel(BaseModel):
            """My model docstring."""

            my_var: str = 'default'

        result = CliApp._get_base_settings_cls(MyModel)
        assert result.__doc__ == 'My model docstring.'


# ──────────────────────────────────────────────────────────────────────
# CliApp._run_cli_cmd
# ──────────────────────────────────────────────────────────────────────


class TestCliAppRunCliCmd:
    def test_run_sync_command(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                self.my_var = 'ran'  # type: ignore[misc]

        model = MyModel(my_var='initial')
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_run_missing_optional_command(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model

    def test_run_missing_required_command_raises(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

        model = MyModel()
        with pytest.raises(SettingsError, match='missing cli_cmd entrypoint'):
            CliApp._run_cli_cmd(model, 'cli_cmd', is_required=True)

    def test_run_async_command(self) -> None:
        ran = []

        class MyModel(BaseModel):
            my_var: str = 'default'

            async def cli_cmd(self) -> None:
                ran.append(True)

        model = MyModel()
        result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
        assert result is model
        assert ran == [True]

    def test_run_async_command_in_running_loop(self) -> None:
        ran = []

        class MyModel(BaseModel):
            my_var: str = 'default'

            async def cli_cmd(self) -> None:
                ran.append(True)

        async def _inner() -> None:
            model = MyModel()
            result = CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)
            assert result is model

        asyncio.run(_inner())
        assert ran == [True]

    def test_run_async_command_exception_propagated(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

            async def cli_cmd(self) -> None:
                raise ValueError('async error')

        async def _inner() -> None:
            model = MyModel()
            with pytest.raises(ValueError, match='async error'):
                CliApp._run_cli_cmd(model, 'cli_cmd', is_required=False)

        asyncio.run(_inner())


# ──────────────────────────────────────────────────────────────────────
# CliApp.run
# ──────────────────────────────────────────────────────────────────────


class TestCliAppRun:
    def test_run_base_settings_subclass(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MySettings, cli_args=['--my_var', 'cli_val'])
        assert result.my_var == 'cli_val'

    def test_run_base_model(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MyModel, cli_args=['--my-var', 'cli_val'])
        assert result.my_var == 'cli_val'

    def test_run_pydantic_dataclass(self) -> None:
        @pydantic_dataclass
        class MyDataclass:
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MyDataclass, cli_args=['--my-var', 'dc_val'])
        assert result.my_var == 'dc_val'

    def test_run_invalid_class_raises(self) -> None:
        class NotAModel:
            pass

        with pytest.raises(SettingsError, match='is not subclass of BaseModel'):
            CliApp.run(NotAModel, cli_args=[])  # type: ignore[arg-type]

    def test_run_with_cli_settings_source(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=['--my_var', 'src_val'])
        result = CliApp.run(MySettings, cli_args=['--my_var', 'src_val'], cli_settings_source=cli_source)
        assert result.my_var == 'src_val'

    def test_run_with_dict_cli_args_requires_source(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        with pytest.raises(SettingsError, match='cli_args.*must be list'):
            CliApp.run(MySettings, cli_args={'my_var': 'val'})  # type: ignore[arg-type]

    def test_run_with_dict_cli_args_and_source(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        result = CliApp.run(MySettings, cli_args={'my_var': 'dict_val'}, cli_settings_source=cli_source)
        assert result.my_var == 'dict_val'

    def test_run_without_cli_cmd(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        result = CliApp.run(MySettings, cli_args=['--my_var', 'val'])
        assert result.my_var == 'val'

    def test_run_with_model_init_data(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MySettings, cli_args=[], my_var='init_data')
        assert result.my_var == 'init_data'

    def test_run_with_cli_exit_on_error(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

            def cli_cmd(self) -> None:
                pass

        result = CliApp.run(MySettings, cli_args=['--my_var', 'val'], cli_exit_on_error=False)
        assert result.my_var == 'val'


# ──────────────────────────────────────────────────────────────────────
# CliApp.run_subcommand
# ──────────────────────────────────────────────────────────────────────


class TestCliAppRunSubcommand:
    def test_run_subcommand_basic(self) -> None:
        class SubCmd(BaseModel):
            name: str = 'sub_default'

            def cli_cmd(self) -> None:
                pass

        class MySettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self)

        result = CliApp.run(MySettings, cli_args=['sub', '--name', 'sub_val'])
        assert result.sub.name == 'sub_val'

    def test_run_subcommand_missing_raises(self) -> None:
        class SubCmd(BaseModel):
            name: str = 'sub_default'

            def cli_cmd(self) -> None:
                pass

        class MySettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

            def cli_cmd(self) -> None:
                CliApp.run_subcommand(self, cli_exit_on_error=False)

        with pytest.raises((SystemExit, SettingsError)):
            CliApp.run(MySettings, cli_args=[], cli_exit_on_error=False)

    def test_run_subcommand_not_in_stack(self) -> None:
        ran = []

        class SubCmd(BaseModel):
            name: str = 'sub_default'

            def cli_cmd(self) -> None:
                ran.append(True)

        class MySettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

        # Create instance directly (not through CliApp.run), so id is not in _subcommand_stack
        model = MySettings(_cli_parse_args=['sub', '--name', 'test_val'])
        assert id(model) not in CliApp._subcommand_stack

        # This will hit the else branch: lines 775-777
        result = CliApp.run_subcommand(model)
        assert ran == [True]
        assert model.sub.name == 'test_val'

    def test_run_subcommand_error_reraise_with_cause(self) -> None:
        class SubCmd(BaseModel):
            name: str = 'sub_default'

            def cli_cmd(self) -> None:
                pass

        class MySettings(BaseSettings):
            sub: CliSubCommand[SubCmd]

        model = MySettings(_cli_parse_args=['sub', '--name', 'val'])

        original_err = ValueError('original')
        caused_err = SettingsError('Error: CLI subcommand is required {sub}')
        caused_err.__cause__ = original_err

        def mock_get_subcommand(model, is_required=True, cli_exit_on_error=None, _suppress_errors=None):
            if _suppress_errors is not None:
                _suppress_errors.append(caused_err)
            return None

        with patch('pydantic_settings.main.get_subcommand', side_effect=mock_get_subcommand):
            with pytest.raises(SettingsError, match='CLI subcommand is required') as exc_info:
                CliApp.run_subcommand(model, cli_exit_on_error=False)
        assert exc_info.value.__cause__ is original_err


# ──────────────────────────────────────────────────────────────────────
# CliApp.serialize
# ──────────────────────────────────────────────────────────────────────


class TestCliAppSerialize:
    def test_serialize_basic(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'hello'

        model = MyModel(my_var='world')
        result = CliApp.serialize(model)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_serialize_settings_model(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'hello'

        model = MySettings(my_var='hello')
        result = CliApp.serialize(model)
        assert isinstance(result, list)

    def test_serialize_list_style_argparse(self) -> None:
        class MyModel(BaseModel):
            items: list[str] = ['a', 'b']

        model = MyModel()
        result = CliApp.serialize(model, list_style='argparse')
        assert isinstance(result, list)

    def test_serialize_list_style_lazy(self) -> None:
        class MyModel(BaseModel):
            items: list[str] = ['a', 'b']

        model = MyModel()
        result = CliApp.serialize(model, list_style='lazy')
        assert isinstance(result, list)


# ──────────────────────────────────────────────────────────────────────
# CliApp.format_help
# ──────────────────────────────────────────────────────────────────────


class TestCliAppFormatHelp:
    def test_format_help_from_class(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        help_text = CliApp.format_help(MySettings)
        assert isinstance(help_text, str)
        assert 'my_var' in help_text or 'my-var' in help_text

    def test_format_help_from_instance(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings()
        help_text = CliApp.format_help(s)
        assert isinstance(help_text, str)

    def test_format_help_strip_ansi_color(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        help_text = CliApp.format_help(MySettings, strip_ansi_color=True)
        assert '\x1b[' not in help_text

    def test_format_help_base_model(self) -> None:
        class MyModel(BaseModel):
            my_var: str = 'default'

        help_text = CliApp.format_help(MyModel)
        assert isinstance(help_text, str)

    def test_format_help_with_custom_cli_source(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        help_text = CliApp.format_help(MySettings, cli_settings_source=cli_source)
        assert isinstance(help_text, str)


# ──────────────────────────────────────────────────────────────────────
# CliApp.print_help
# ──────────────────────────────────────────────────────────────────────


class TestCliAppPrintHelp:
    def test_print_help_to_file(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        buf = io.StringIO()
        CliApp.print_help(MySettings, file=buf)
        output = buf.getvalue()
        assert len(output) > 0

    def test_print_help_strip_ansi(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        buf = io.StringIO()
        CliApp.print_help(MySettings, file=buf, strip_ansi_color=True)
        output = buf.getvalue()
        assert '\x1b[' not in output

    def test_print_help_with_cli_source(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        cli_source = CliSettingsSource(MySettings, cli_parse_args=[])
        buf = io.StringIO()
        CliApp.print_help(MySettings, cli_settings_source=cli_source, file=buf)
        output = buf.getvalue()
        assert len(output) > 0

    def test_print_help_from_instance(self) -> None:
        class MySettings(BaseSettings):
            my_var: str = 'default'

        s = MySettings()
        buf = io.StringIO()
        CliApp.print_help(s, file=buf)
        output = buf.getvalue()
        assert len(output) > 0
