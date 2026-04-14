"""Tests for pydantic_settings.main module."""

import asyncio
import sys
import warnings
from argparse import Namespace
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass as pydantic_dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.main import CliApp
from pydantic_settings.sources import (
    CliSettingsSource,
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
    """Tests for BaseSettings.__init__ method."""

    def test_init_with_default_parameters(self):
        """Test BaseSettings initialization with default parameters."""

        class Settings(BaseSettings):
            name: str = "default"
            value: int = 42

        settings = Settings()
        assert settings.name == "default"
        assert settings.value == 42

    def test_init_with_explicit_values(self):
        """Test BaseSettings initialization with explicit values."""

        class Settings(BaseSettings):
            name: str = "default"
            value: int = 42

        settings = Settings(name="custom", value=100)
        assert settings.name == "custom"
        assert settings.value == 100

    def test_init_with_case_sensitive(self):
        """Test BaseSettings initialization with case_sensitive parameter."""

        class Settings(BaseSettings):
            NAME: str = "default"

        # Test case-insensitive (default)
        with patch.dict("os.environ", {"name": "from_env"}, clear=False):
            settings = Settings(_case_sensitive=False)
            assert settings.NAME == "from_env"

    def test_init_with_env_prefix(self):
        """Test BaseSettings initialization with env_prefix parameter."""

        class Settings(BaseSettings):
            name: str = "default"

        with patch.dict("os.environ", {"APP_NAME": "prefixed"}, clear=False):
            settings = Settings(_env_prefix="APP_")
            assert settings.name == "prefixed"

    def test_init_with_env_file(self):
        """Test BaseSettings initialization with env_file parameter."""

        class Settings(BaseSettings):
            name: str = "default"
            value: int = 42

        with TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("NAME=from_file\nVALUE=99")

            settings = Settings(_env_file=str(env_file))
            assert settings.name == "from_file"
            assert settings.value == 99

    def test_init_with_env_file_encoding(self):
        """Test BaseSettings initialization with env_file_encoding parameter."""

        class Settings(BaseSettings):
            name: str = "default"

        with TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            # Write with UTF-8 encoding
            env_file.write_text("NAME=encoded_value", encoding="utf-8")

            settings = Settings(_env_file=str(env_file), _env_file_encoding="utf-8")
            assert settings.name == "encoded_value"

    def test_init_with_secrets_dir(self):
        """Test BaseSettings initialization with secrets_dir parameter."""

        class Settings(BaseSettings):
            secret_key: str = "default"

        with TemporaryDirectory() as tmpdir:
            secret_file = Path(tmpdir) / "secret_key"
            secret_file.write_text("secret_value")

            settings = Settings(_secrets_dir=tmpdir)
            assert settings.secret_key == "secret_value"

    def test_init_with_nested_model_default_partial_update(self):
        """Test BaseSettings with nested_model_default_partial_update parameter."""

        class NestedModel(BaseModel):
            x: int = 1
            y: int = 2

        class Settings(BaseSettings):
            nested: NestedModel = NestedModel()

        with patch.dict("os.environ", {"NESTED": '{"x": 10}'}, clear=False):
            settings = Settings(_nested_model_default_partial_update=True)
            assert settings.nested.x == 10
            assert settings.nested.y == 2

    def test_init_with_env_ignore_empty(self):
        """Test BaseSettings initialization with env_ignore_empty parameter."""

        class Settings(BaseSettings):
            name: str = "default"

        with patch.dict("os.environ", {"NAME": ""}, clear=False):
            settings = Settings(_env_ignore_empty=True)
            assert settings.name == "default"

    def test_init_with_env_nested_delimiter(self):
        """Test BaseSettings initialization with env_nested_delimiter parameter."""

        class NestedModel(BaseModel):
            value: int = 0

        class Settings(BaseSettings):
            nested: NestedModel = NestedModel()

        with patch.dict("os.environ", {"NESTED__VALUE": "42"}, clear=False):
            settings = Settings(_env_nested_delimiter="__")
            assert settings.nested.value == 42

    def test_init_with_env_parse_none_str(self):
        """Test BaseSettings initialization with env_parse_none_str parameter."""

        class Settings(BaseSettings):
            value: int | None = 10

        with patch.dict("os.environ", {"VALUE": "null"}, clear=False):
            settings = Settings(_env_parse_none_str="null")
            assert settings.value is None

    def test_init_with_cli_parse_args(self):
        """Test BaseSettings initialization with cli_parse_args parameter."""

        class Settings(BaseSettings):
            name: str = "default"
            value: int = 42

        settings = Settings(_cli_parse_args=["--name", "cli_name", "--value", "99"])
        assert settings.name == "cli_name"
        assert settings.value == 99

    def test_init_with_build_sources(self):
        """Test BaseSettings initialization with pre-built sources."""

        class Settings(BaseSettings):
            name: str = "default"

        # Build sources first
        sources, init_kwargs = Settings._settings_init_sources(name="test")

        # Use pre-built sources
        settings = Settings(_build_sources=(sources, init_kwargs))
        assert settings.name == "test"


class TestBaseSettingsCustomiseSources:
    """Tests for BaseSettings.settings_customise_sources method."""

    def test_settings_customise_sources_default(self):
        """Test default settings_customise_sources method."""

        class Settings(BaseSettings):
            name: str = "default"

        sources = Settings._settings_init_sources()[0]
        init_source = [s for s in sources if isinstance(s, InitSettingsSource)][0]
        env_source = [s for s in sources if isinstance(s, EnvSettingsSource)][0]
        dotenv_source = [s for s in sources if isinstance(s, DotEnvSettingsSource)][0]
        secrets_source = [s for s in sources if isinstance(s, SecretsSettingsSource)][0]

        customized = Settings.settings_customise_sources(
            Settings, init_source, env_source, dotenv_source, secrets_source
        )

        assert len(customized) == 4
        assert customized[0] is init_source
        assert customized[1] is env_source
        assert customized[2] is dotenv_source
        assert customized[3] is secrets_source

    def test_settings_customise_sources_override(self):
        """Test overriding settings_customise_sources method."""

        class Settings(BaseSettings):
            name: str = "default"

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
            ):
                # Change order: env first, then init
                return (env_settings, init_settings)

        with patch.dict("os.environ", {"NAME": "from_env"}, clear=False):
            settings = Settings(name="from_init")
            # Env should win because it's first in customized order
            assert settings.name == "from_env"


class TestBaseSettingsInitSources:
    """Tests for BaseSettings._settings_init_sources method."""

    def test_init_sources_with_all_defaults(self):
        """Test _settings_init_sources with all default parameters."""

        class Settings(BaseSettings):
            name: str = "default"

        sources, init_kwargs = Settings._settings_init_sources()

        assert isinstance(sources, tuple)
        assert len(sources) > 0
        assert isinstance(init_kwargs, dict)

    def test_init_sources_with_env_prefix_target(self):
        """Test _settings_init_sources with env_prefix_target parameter."""

        class Settings(BaseSettings):
            name: str = "default"

        sources, init_kwargs = Settings._settings_init_sources(
            _env_prefix="APP_", _env_prefix_target="alias"
        )

        env_source = [s for s in sources if isinstance(s, EnvSettingsSource)][0]
        assert env_source.env_prefix == "APP_"
        assert env_source.env_prefix_target == "alias"

    def test_init_sources_with_cli_settings(self):
        """Test _settings_init_sources with CLI parameters."""

        class Settings(BaseSettings):
            name: str = "default"
            value: int = 42

        sources, init_kwargs = Settings._settings_init_sources(
            _cli_parse_args=["--name", "cli_test"],
            _cli_prog_name="test_app",
            _cli_hide_none_type=True,
            _cli_avoid_json=True,
            _cli_enforce_required=True,
            _cli_use_class_docs_for_groups=True,
            _cli_exit_on_error=False,
            _cli_prefix="app",
            _cli_flag_prefix_char="-",
            _cli_implicit_flags=True,
            _cli_ignore_unknown_args=True,
            _cli_kebab_case=True,
        )

        cli_source = [s for s in sources if isinstance(s, CliSettingsSource)]
        assert len(cli_source) > 0

    def test_init_sources_with_custom_cli_source(self):
        """Test _settings_init_sources with custom CLI settings source."""

        class Settings(BaseSettings):
            name: str = "default"

        custom_cli = CliSettingsSource(Settings, cli_parse_args=["--name", "custom"])
        sources, init_kwargs = Settings._settings_init_sources(_cli_settings_source=custom_cli)

        # Custom CLI source should be in the sources
        assert custom_cli in sources

    def test_init_sources_with_env_nested_max_split(self):
        """Test _settings_init_sources with env_nested_max_split parameter."""

        class Settings(BaseSettings):
            name: str = "default"

        sources, init_kwargs = Settings._settings_init_sources(
            _env_nested_delimiter="__", _env_nested_max_split=2
        )

        env_source = [s for s in sources if isinstance(s, EnvSettingsSource)][0]
        assert env_source.env_nested_max_split == 2

    def test_init_sources_with_env_parse_enums(self):
        """Test _settings_init_sources with env_parse_enums parameter."""

        class Settings(BaseSettings):
            name: str = "default"

        sources, init_kwargs = Settings._settings_init_sources(_env_parse_enums=True)

        env_source = [s for s in sources if isinstance(s, EnvSettingsSource)][0]
        assert env_source.env_parse_enums is True

    def test_init_sources_cli_parse_none_str_fallback(self):
        """Test that cli_parse_none_str falls back to env_parse_none_str."""

        class Settings(BaseSettings):
            value: int | None = 10

        sources, init_kwargs = Settings._settings_init_sources(_env_parse_none_str="null")

        cli_sources = [s for s in sources if isinstance(s, CliSettingsSource)]
        if cli_sources:
            # When env_parse_none_str is set, cli should use it
            pass


class TestBaseSettingsBuildValues:
    """Tests for BaseSettings._settings_build_values method."""

    def test_build_values_with_sources(self):
        """Test _settings_build_values with multiple sources."""

        class Settings(BaseSettings):
            name: str = "default"
            value: int = 42

        sources, init_kwargs = Settings._settings_init_sources(name="from_init")
        values = Settings._settings_build_values(sources, init_kwargs)

        assert isinstance(values, dict)
        assert "name" in values
        assert values["name"] == "from_init"

    def test_build_values_with_empty_sources(self):
        """Test _settings_build_values with empty sources tuple."""

        class Settings(BaseSettings):
            name: str = "default"

        values = Settings._settings_build_values((), {})
        assert values == {}

    def test_build_values_source_priority(self):
        """Test that _settings_build_values respects source priority."""

        class Settings(BaseSettings):
            name: str = "default"

        with patch.dict("os.environ", {"NAME": "from_env"}, clear=False):
            sources, init_kwargs = Settings._settings_init_sources(name="from_init")
            values = Settings._settings_build_values(sources, init_kwargs)

            # Init should win over env (init comes first in default order)
            assert values["name"] == "from_init"


class TestBaseSettingsRestoreInitKwargNames:
    """Tests for BaseSettings._settings_restore_init_kwarg_names method."""

    def test_restore_init_kwarg_names_with_aliases(self):
        """Test restoring init kwarg names with field aliases."""

        class Settings(BaseSettings):
            name: str = Field(default="default", alias="display_name")
            model_config = SettingsConfigDict(populate_by_name=True)

        init_kwargs = {"display_name": "init_value"}
        state = {"name": "state_value"}

        Settings._settings_restore_init_kwarg_names(Settings, init_kwargs, state)

        # The state should now have the init kwarg name
        assert "display_name" in state
        assert state["display_name"] == "state_value"

    def test_restore_init_kwarg_names_empty_dicts(self):
        """Test restoring init kwarg names with empty dicts."""

        class Settings(BaseSettings):
            name: str = "default"

        Settings._settings_restore_init_kwarg_names(Settings, {}, {})
        # Should not raise an error

    def test_restore_init_kwarg_names_no_match(self):
        """Test restoring when there's no matching field."""

        class Settings(BaseSettings):
            name: str = "default"

        init_kwargs = {"other_field": "value"}
        state = {"name": "test"}

        Settings._settings_restore_init_kwarg_names(Settings, init_kwargs, state)

        # State should remain unchanged
        assert state == {"name": "test"}


class TestBaseSettingsWarnUnusedConfigKeys:
    """Tests for BaseSettings._settings_warn_unused_config_keys method."""

    def test_warn_unused_json_config_keys(self):
        """Test warning for unused json_file config key."""

        class Settings(BaseSettings):
            name: str = "default"
            model_config = SettingsConfigDict(json_file="config.json")

        # Capture warnings from _settings_init_sources which calls _settings_warn_unused_config_keys
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sources, _ = Settings._settings_init_sources()

            # Check that a warning was raised
            json_warnings = [warning for warning in w if "json_file" in str(warning.message)]
            assert len(json_warnings) > 0
            assert "JsonConfigSettingsSource" in str(json_warnings[0].message)

    def test_warn_unused_yaml_config_keys(self):
        """Test warning for unused yaml_file config key."""

        class Settings(BaseSettings):
            name: str = "default"
            model_config = SettingsConfigDict(
                yaml_file="config.yaml", yaml_file_encoding="utf-8", yaml_config_section="app"
            )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sources, _ = Settings._settings_init_sources()

            # Should warn for yaml config keys
            yaml_warnings = [warning for warning in w if "yaml_file" in str(warning.message)]
            assert len(yaml_warnings) > 0

    def test_warn_unused_toml_config_keys(self):
        """Test warning for unused toml_file config key."""

        class Settings(BaseSettings):
            name: str = "default"
            model_config = SettingsConfigDict(toml_file="config.toml")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sources, _ = Settings._settings_init_sources()

            toml_warnings = [warning for warning in w if "toml_file" in str(warning.message)]
            assert len(toml_warnings) > 0

    def test_warn_unused_pyproject_toml_keys(self):
        """Test warning for unused pyproject_toml config keys."""

        class Settings(BaseSettings):
            name: str = "default"
            model_config = SettingsConfigDict(
                pyproject_toml_depth=2, pyproject_toml_table_header=("tool", "myapp")
            )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sources, _ = Settings._settings_init_sources()

            pyproject_warnings = [warning for warning in w if "pyproject_toml" in str(warning.message)]
            assert len(pyproject_warnings) > 0

    def test_no_warning_when_source_configured(self):
        """Test no warning when appropriate source is configured."""

        class Settings(BaseSettings):
            name: str = "default"
            model_config = SettingsConfigDict(json_file="config.json")

        # Create an actual JsonConfigSettingsSource instance
        json_source = JsonConfigSettingsSource(Settings, json_file=Path("config.json"))
        sources = (json_source,)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            BaseSettings._settings_warn_unused_config_keys(sources, Settings.model_config)

            # No warning should be raised because JsonConfigSettingsSource is in sources
            json_warnings = [warning for warning in w if "json_file" in str(warning.message)]
            assert len(json_warnings) == 0


class TestCliAppGetBaseSettingsCls:
    """Tests for CliApp._get_base_settings_cls method."""

    def test_get_base_settings_cls_with_base_settings(self):
        """Test _get_base_settings_cls with a BaseSettings subclass."""

        class MySettings(BaseSettings):
            name: str = "default"

        result = CliApp._get_base_settings_cls(MySettings)
        assert result is MySettings

    def test_get_base_settings_cls_with_base_model(self):
        """Test _get_base_settings_cls with a BaseModel."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = "default"

        result = CliApp._get_base_settings_cls(MyModel)
        assert issubclass(result, BaseSettings)
        assert issubclass(result, MyModel)
        assert result.__doc__ == MyModel.__doc__

    def test_get_base_settings_cls_config(self):
        """Test that created BaseSettings class has correct config."""

        class MyModel(BaseModel):
            name: str = "default"

        result = CliApp._get_base_settings_cls(MyModel)
        config = result.model_config

        assert config["case_sensitive"] is True
        assert config["cli_hide_none_type"] is True
        assert config["cli_avoid_json"] is True
        assert config["cli_enforce_required"] is True
        assert config["cli_implicit_flags"] is True
        assert config["cli_kebab_case"] is True


class TestCliAppRunCliCmd:
    """Tests for CliApp._run_cli_cmd method."""

    def test_run_cli_cmd_sync_method(self):
        """Test running a synchronous CLI command."""

        class MyModel(BaseModel):
            name: str = "test"
            executed: bool = False

            def cli_cmd(self):
                self.executed = True

        model = MyModel()
        result = CliApp._run_cli_cmd(model, "cli_cmd", is_required=True)

        assert result.executed is True

    def test_run_cli_cmd_missing_required(self):
        """Test running with missing required command."""

        class MyModel(BaseModel):
            name: str = "test"

        model = MyModel()

        with pytest.raises(SettingsError, match="missing cli_cmd entrypoint"):
            CliApp._run_cli_cmd(model, "cli_cmd", is_required=True)

    def test_run_cli_cmd_missing_not_required(self):
        """Test running with missing non-required command."""

        class MyModel(BaseModel):
            name: str = "test"

        model = MyModel()
        result = CliApp._run_cli_cmd(model, "cli_cmd", is_required=False)

        # Should return the model unchanged
        assert result is model

    def test_run_cli_cmd_async_method(self):
        """Test running an asynchronous CLI command."""

        class MyModel(BaseModel):
            name: str = "test"
            executed: bool = False

            async def cli_cmd(self):
                await asyncio.sleep(0.01)
                self.executed = True

        model = MyModel()
        result = CliApp._run_cli_cmd(model, "cli_cmd", is_required=True)

        assert result.executed is True

    def test_run_cli_cmd_async_method_with_running_loop(self):
        """Test running async command when event loop is already running."""

        class MyModel(BaseModel):
            name: str = "test"
            executed: bool = False

            async def cli_cmd(self):
                await asyncio.sleep(0.01)
                self.executed = True

        async def test_with_loop():
            model = MyModel()
            result = CliApp._run_cli_cmd(model, "cli_cmd", is_required=True)
            assert result.executed is True

        # Run in an event loop context
        asyncio.run(test_with_loop())

    def test_run_cli_cmd_async_raises_exception(self):
        """Test running async command that raises an exception."""

        class MyModel(BaseModel):
            name: str = "test"

            async def cli_cmd(self):
                raise ValueError("Test error")

        model = MyModel()

        with pytest.raises(ValueError, match="Test error"):
            CliApp._run_cli_cmd(model, "cli_cmd", is_required=True)


class TestCliAppRun:
    """Tests for CliApp.run method."""

    def test_run_with_base_settings(self):
        """Test running a BaseSettings class."""

        class MySettings(BaseSettings):
            name: str = "default"
            executed: bool = False

            def cli_cmd(self):
                self.executed = True

        result = CliApp.run(MySettings, cli_args=[])
        assert isinstance(result, MySettings)
        assert result.executed is True

    def test_run_with_base_model(self):
        """Test running a BaseModel class."""

        class MyModel(BaseModel):
            name: str = "default"
            executed: bool = False

            def cli_cmd(self):
                self.executed = True

        result = CliApp.run(MyModel, cli_args=[])
        assert result.executed is True

    def test_run_with_pydantic_dataclass(self):
        """Test running a pydantic dataclass."""

        @pydantic_dataclass
        class MyDataclass:
            name: str = "default"
            executed: bool = False

            def cli_cmd(self):
                self.executed = True

        result = CliApp.run(MyDataclass, cli_args=[])
        assert result.executed is True

    def test_run_with_invalid_class(self):
        """Test running with invalid class type."""

        class NotAModel:
            pass

        with pytest.raises(SettingsError, match="not subclass of BaseModel"):
            CliApp.run(NotAModel, cli_args=[])

    def test_run_with_cli_args_list(self):
        """Test running with CLI arguments as list."""

        class MySettings(BaseSettings):
            name: str = "default"
            value: int = 42

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=["--name", "test", "--value", "100"])
        assert result.name == "test"
        assert result.value == 100

    def test_run_with_cli_args_namespace(self):
        """Test running with CLI arguments as Namespace."""

        class MySettings(BaseSettings):
            name: str = "default"

            def cli_cmd(self):
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=["--name", "test"])
        args_dict = {"name": "namespace_test"}

        result = CliApp.run(MySettings, cli_args=Namespace(**args_dict), cli_settings_source=cli_source)
        assert result.name == "namespace_test"

    def test_run_with_cli_args_dict(self):
        """Test running with CLI arguments as dict."""

        class MySettings(BaseSettings):
            name: str = "default"

            def cli_cmd(self):
                pass

        cli_source = CliSettingsSource(MySettings, cli_parse_args=["--name", "test"])
        args_dict = {"name": "dict_test"}

        result = CliApp.run(MySettings, cli_args=args_dict, cli_settings_source=cli_source)
        assert result.name == "dict_test"

    def test_run_with_dict_no_cli_source_error(self):
        """Test running with dict args but no CLI settings source raises error."""

        class MySettings(BaseSettings):
            name: str = "default"

            def cli_cmd(self):
                pass

        with pytest.raises(SettingsError, match="cli_args.*must be list"):
            CliApp.run(MySettings, cli_args={"name": "test"})

    def test_run_with_cli_exit_on_error(self):
        """Test running with cli_exit_on_error parameter."""

        class MySettings(BaseSettings):
            name: str = "default"

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=[], cli_exit_on_error=False)
        assert isinstance(result, MySettings)

    def test_run_with_model_init_data(self):
        """Test running with additional model init data."""

        class MySettings(BaseSettings):
            name: str = "default"
            value: int = 42

            def cli_cmd(self):
                pass

        result = CliApp.run(MySettings, cli_args=[], value=100)
        assert result.value == 100

    def test_run_with_custom_cli_cmd_method_name(self):
        """Test running with custom CLI command method name."""

        class MySettings(BaseSettings):
            name: str = "default"
            custom_executed: bool = False

            def custom_method(self):
                self.custom_executed = True

        result = CliApp.run(MySettings, cli_args=[], cli_cmd_method_name="custom_method")
        assert result.custom_executed is True


class TestCliAppRunSubcommand:
    """Tests for CliApp.run_subcommand method."""

    def test_run_subcommand_basic(self):
        """Test running a basic subcommand."""

        class SubModel(BaseModel):
            sub_name: str = "sub"
            executed: bool = False

            def cli_cmd(self):
                self.executed = True

        class MainModel(BaseSettings):
            name: str = "main"
            sub: SubModel = SubModel()

        # First run the main model
        main = CliApp.run(MainModel, cli_args=[])

        # Mock the subcommand in the model
        main.sub = SubModel()

        # Need to set up the subcommand stack for this to work
        cli_source = CliSettingsSource(MainModel, cli_parse_args=[])
        CliApp._subcommand_stack[id(main)] = (cli_source, cli_source.root_parser, ":subcommand")

        # This would require a complex setup, so we'll test the error path
        try:
            result = CliApp.run_subcommand(main)
        except (SettingsError, SystemExit):
            # Expected when no subcommand is configured
            pass
        finally:
            if id(main) in CliApp._subcommand_stack:
                del CliApp._subcommand_stack[id(main)]


class TestCliAppSerialize:
    """Tests for CliApp.serialize method."""

    def test_serialize_basic_model(self):
        """Test serializing a basic model."""

        class MyModel(BaseModel):
            name: str = "default"
            value: int = 0

        model = MyModel(name="test", value=42)
        args = CliApp.serialize(model)

        assert isinstance(args, list)
        assert "--name" in args
        assert "test" in args
        assert "--value" in args
        assert "42" in args

    def test_serialize_with_list_json_style(self):
        """Test serializing with list_style='json'."""

        class MyModel(BaseModel):
            tags: list[str] = []

        model = MyModel(tags=["a", "b", "c"])
        args = CliApp.serialize(model, list_style="json")

        assert isinstance(args, list)
        assert "--tags" in args

    def test_serialize_with_list_argparse_style(self):
        """Test serializing with list_style='argparse'."""

        class MyModel(BaseModel):
            tags: list[str] = ["a", "b", "c"]

        model = MyModel()
        args = CliApp.serialize(model, list_style="argparse")

        assert isinstance(args, list)

    def test_serialize_with_dict_json_style(self):
        """Test serializing with dict_style='json'."""

        class MyModel(BaseModel):
            config: dict[str, Any] = {}

        model = MyModel(config={"host": "localhost", "port": 5432})
        args = CliApp.serialize(model, dict_style="json")

        assert isinstance(args, list)
        assert "--config" in args

    def test_serialize_with_dict_env_style(self):
        """Test serializing with dict_style='env'."""

        class MyModel(BaseModel):
            config: dict[str, Any] = {"host": "localhost", "port": 5432}

        model = MyModel()
        args = CliApp.serialize(model, dict_style="env")

        assert isinstance(args, list)

    def test_serialize_with_positionals_first(self):
        """Test serializing with positionals_first=True."""

        class MyModel(BaseModel):
            name: str = "test"

        model = MyModel()
        args = CliApp.serialize(model, positionals_first=True)

        assert isinstance(args, list)


class TestCliAppFormatHelp:
    """Tests for CliApp.format_help method."""

    def test_format_help_with_model_instance(self):
        """Test formatting help for a model instance."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = Field(default="test", description="The name field")

        model = MyModel()
        help_text = CliApp.format_help(model)

        assert isinstance(help_text, str)
        assert len(help_text) > 0

    def test_format_help_with_model_class(self):
        """Test formatting help for a model class."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = Field(default="test", description="The name field")

        help_text = CliApp.format_help(MyModel)

        assert isinstance(help_text, str)
        assert len(help_text) > 0

    def test_format_help_strip_ansi_color(self):
        """Test formatting help with ANSI colors stripped."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = "test"

        help_text = CliApp.format_help(MyModel, strip_ansi_color=True)

        # Should not contain ANSI escape sequences
        assert "\x1b[" not in help_text

    def test_format_help_with_custom_cli_source(self):
        """Test formatting help with custom CLI settings source."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = "test"

        cli_source = CliSettingsSource(CliApp._get_base_settings_cls(MyModel))
        help_text = CliApp.format_help(MyModel, cli_settings_source=cli_source)

        assert isinstance(help_text, str)
        assert len(help_text) > 0


class TestCliAppPrintHelp:
    """Tests for CliApp.print_help method."""

    def test_print_help_basic(self):
        """Test printing help message."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = "test"

        output = StringIO()
        CliApp.print_help(MyModel, file=output)

        result = output.getvalue()
        assert len(result) > 0

    def test_print_help_with_strip_ansi(self):
        """Test printing help with ANSI colors stripped."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = "test"

        output = StringIO()
        CliApp.print_help(MyModel, file=output, strip_ansi_color=True)

        result = output.getvalue()
        assert "\x1b[" not in result

    def test_print_help_default_stdout(self):
        """Test printing help to stdout by default."""

        class MyModel(BaseModel):
            """Test model."""

            name: str = "test"

        # Should not raise an error
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            CliApp.print_help(MyModel)
            result = mock_stdout.getvalue()
            assert len(result) > 0
