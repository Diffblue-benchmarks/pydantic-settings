"""Tests for pydantic_settings/sources/base.py"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Optional

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources import (
    CliSubCommand,
    DefaultSettingsSource,
    EnvSettingsSource,
    InitSettingsSource,
    PydanticBaseEnvSettingsSource,
    PydanticBaseSettingsSource,
    get_subcommand,
)
from pydantic_settings.sources.base import ConfigFileSourceMixin
from pydantic_settings.sources.types import EnvNoneType, ForceDecode, NoDecode


# ---------------------------------------------------------------------------
# Simple settings classes for tests
# ---------------------------------------------------------------------------


class SimpleSettings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}
    name: str = "default_name"
    value: int = 42


class NestedModel(BaseModel):
    x: int = 1
    y: str = "hello"


class NestedSettings(BaseSettings):
    model_config = {"env_prefix": "", "env_nested_delimiter": "__"}
    nested: NestedModel = NestedModel()


# ---------------------------------------------------------------------------
# get_subcommand tests
# ---------------------------------------------------------------------------


class SubCmdA(BaseSettings):
    flag: str = "a"


class SubCmdB(BaseSettings):
    flag: str = "b"


class RootModelWithSubcommand(BaseSettings):
    model_config = {"cli_exit_on_error": False}
    sub_a: CliSubCommand[SubCmdA] = None  # type: ignore[assignment]


class RootModelNoSubcommands(BaseSettings):
    model_config = {"cli_exit_on_error": False}
    name: str = "test"


def test_get_subcommand_returns_subcommand_when_set():
    sub = SubCmdA(flag="set")
    root = RootModelWithSubcommand(sub_a=sub)
    result = get_subcommand(root, is_required=False)
    assert result is sub


def test_get_subcommand_returns_none_when_not_required():
    root = RootModelWithSubcommand()
    result = get_subcommand(root, is_required=False)
    assert result is None


def test_get_subcommand_raises_settings_error_when_required_and_no_exit():
    root = RootModelWithSubcommand()
    with pytest.raises(SettingsError, match="CLI subcommand is required"):
        get_subcommand(root, is_required=True, cli_exit_on_error=False)


def test_get_subcommand_raises_system_exit_when_required_and_exit_on_error():
    root = RootModelWithSubcommand()
    with pytest.raises(SystemExit):
        get_subcommand(root, is_required=True, cli_exit_on_error=True)


def test_get_subcommand_suppresses_errors():
    root = RootModelWithSubcommand()
    errors: list = []
    result = get_subcommand(root, is_required=True, cli_exit_on_error=False, _suppress_errors=errors)
    assert result is None
    assert len(errors) == 1


def test_get_subcommand_no_subcommand_fields_raises_settings_error():
    root = RootModelNoSubcommands()
    with pytest.raises(SettingsError, match="no subcommands were found"):
        get_subcommand(root, is_required=True, cli_exit_on_error=False)


def test_get_subcommand_uses_model_config_cli_exit_on_error():
    root = RootModelWithSubcommand()
    # model_config sets cli_exit_on_error=False, so SettingsError should be raised
    with pytest.raises(SettingsError):
        get_subcommand(root, is_required=True)


def test_get_subcommand_explicit_exit_on_error_true_raises_system_exit():
    root = RootModelNoSubcommands()
    # Explicitly passing cli_exit_on_error=True should always raise SystemExit
    with pytest.raises(SystemExit):
        get_subcommand(root, is_required=True, cli_exit_on_error=True)


# ---------------------------------------------------------------------------
# PydanticBaseSettingsSource tests (via concrete subclass)
# ---------------------------------------------------------------------------


class ConcreteSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {}


def test_pydantic_base_settings_source_init():
    src = ConcreteSettingsSource(SimpleSettings)
    assert src.settings_cls is SimpleSettings
    assert src.config is SimpleSettings.model_config
    assert src._current_state == {}
    assert src._settings_sources_data == {}


def test_pydantic_base_settings_source_set_current_state():
    src = ConcreteSettingsSource(SimpleSettings)
    state = {"name": "foo"}
    src._set_current_state(state)
    assert src._current_state == {"name": "foo"}


def test_pydantic_base_settings_source_current_state_property():
    src = ConcreteSettingsSource(SimpleSettings)
    src._set_current_state({"x": 1})
    assert src.current_state == {"x": 1}


def test_pydantic_base_settings_source_set_settings_sources_data():
    src = ConcreteSettingsSource(SimpleSettings)
    data = {"src1": {"a": 1}}
    src._set_settings_sources_data(data)
    assert src._settings_sources_data == {"src1": {"a": 1}}


def test_pydantic_base_settings_source_settings_sources_data_property():
    src = ConcreteSettingsSource(SimpleSettings)
    src._set_settings_sources_data({"s": {"v": 2}})
    assert src.settings_sources_data == {"s": {"v": 2}}


def test_pydantic_base_settings_source_field_is_complex_simple():
    src = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    assert src.field_is_complex(field) is False


def test_pydantic_base_settings_source_field_is_complex_nested():
    src = ConcreteSettingsSource(NestedSettings)
    field = NestedSettings.model_fields["nested"]
    assert src.field_is_complex(field) is True


def test_prepare_field_value_returns_value_directly_when_not_complex():
    src = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    result = src.prepare_field_value("name", field, "hello", False)
    assert result == "hello"


def test_prepare_field_value_returns_none_as_is():
    src = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    result = src.prepare_field_value("name", field, None, False)
    assert result is None


def test_prepare_field_value_decodes_complex_value():
    src = ConcreteSettingsSource(NestedSettings)
    field = NestedSettings.model_fields["nested"]
    value = json.dumps({"x": 5, "y": "world"})
    result = src.prepare_field_value("nested", field, value, False)
    assert result == {"x": 5, "y": "world"}


def test_prepare_field_value_decodes_when_value_is_complex_flag():
    src = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    result = src.prepare_field_value("name", field, '{"key": "val"}', True)
    assert result == {"key": "val"}


def test_decode_complex_value_parses_json():
    src = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    result = src.decode_complex_value("name", field, '["a", "b"]')
    assert result == ["a", "b"]


def test_decode_complex_value_no_decode_annotation():
    class SettingsNoDecode(BaseSettings):
        items: Annotated[list[str], NoDecode] = []

    src = ConcreteSettingsSource(SettingsNoDecode)
    field = SettingsNoDecode.model_fields["items"]
    raw = '["a", "b"]'
    result = src.decode_complex_value("items", field, raw)
    assert result == raw


def test_decode_complex_value_enable_decoding_false():
    class SettingsNoDecodeConfig(BaseSettings):
        model_config = {"enable_decoding": False}
        items: list[str] = []

    src = ConcreteSettingsSource(SettingsNoDecodeConfig)
    field = SettingsNoDecodeConfig.model_fields["items"]
    raw = '["a", "b"]'
    result = src.decode_complex_value("items", field, raw)
    assert result == raw


def test_decode_complex_value_force_decode_overrides_enable_decoding_false():
    class SettingsForce(BaseSettings):
        model_config = {"enable_decoding": False}
        items: Annotated[list[str], ForceDecode] = []

    src = ConcreteSettingsSource(SettingsForce)
    field = SettingsForce.model_fields["items"]
    raw = '["x", "y"]'
    result = src.decode_complex_value("items", field, raw)
    assert result == ["x", "y"]


def test_concrete_settings_source_call():
    src = ConcreteSettingsSource(SimpleSettings)
    assert src() == {}


# ---------------------------------------------------------------------------
# ConfigFileSourceMixin tests
# ---------------------------------------------------------------------------


class ConcreteConfigFileMixin(ConfigFileSourceMixin, PydanticBaseSettingsSource):
    def _read_file(self, path: Path) -> dict[str, Any]:
        import json

        with open(path) as f:
            return json.load(f)

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {}


def test_config_file_mixin_read_files_none_returns_empty():
    src = ConcreteConfigFileMixin(SimpleSettings)
    assert src._read_files(None) == {}


def test_config_file_mixin_read_files_missing_file_skipped(tmp_path):
    src = ConcreteConfigFileMixin(SimpleSettings)
    result = src._read_files(str(tmp_path / "nonexistent.json"))
    assert result == {}


def test_config_file_mixin_read_files_single_file(tmp_path):
    f = tmp_path / "config.json"
    f.write_text('{"name": "from_file"}')
    src = ConcreteConfigFileMixin(SimpleSettings)
    result = src._read_files(str(f))
    assert result == {"name": "from_file"}


def test_config_file_mixin_read_files_list_of_files(tmp_path):
    f1 = tmp_path / "a.json"
    f1.write_text('{"key1": "v1"}')
    f2 = tmp_path / "b.json"
    f2.write_text('{"key2": "v2"}')
    src = ConcreteConfigFileMixin(SimpleSettings)
    result = src._read_files([str(f1), str(f2)])
    assert result == {"key1": "v1", "key2": "v2"}


def test_config_file_mixin_read_files_deep_merge(tmp_path):
    f1 = tmp_path / "a.json"
    f1.write_text('{"nested": {"a": 1}}')
    f2 = tmp_path / "b.json"
    f2.write_text('{"nested": {"b": 2}}')
    src = ConcreteConfigFileMixin(SimpleSettings)
    result = src._read_files([str(f1), str(f2)], deep_merge=True)
    assert result == {"nested": {"a": 1, "b": 2}}


def test_config_file_mixin_read_files_path_object(tmp_path):
    f = tmp_path / "config.json"
    f.write_text('{"value": 99}')
    src = ConcreteConfigFileMixin(SimpleSettings)
    result = src._read_files(f)
    assert result == {"value": 99}


# ---------------------------------------------------------------------------
# DefaultSettingsSource tests
# ---------------------------------------------------------------------------


def test_default_settings_source_init_basic():
    src = DefaultSettingsSource(SimpleSettings)
    assert src.defaults == {}
    assert src.nested_model_default_partial_update is False


def test_default_settings_source_call_empty():
    src = DefaultSettingsSource(SimpleSettings)
    result = src()
    assert result == {}


def test_default_settings_source_get_field_value():
    src = DefaultSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    val, key, is_complex = src.get_field_value(field, "name")
    assert val is None
    assert key == ""
    assert is_complex is False


def test_default_settings_source_repr():
    src = DefaultSettingsSource(SimpleSettings)
    r = repr(src)
    assert "DefaultSettingsSource" in r
    assert "nested_model_default_partial_update=False" in r


def test_default_settings_source_nested_model_default_partial_update():
    class SubModel(BaseModel):
        x: int = 10

    class SettingsWithNested(BaseSettings):
        model_config = {"nested_model_default_partial_update": True}
        sub: SubModel = SubModel()

    src = DefaultSettingsSource(SettingsWithNested)
    assert src.nested_model_default_partial_update is True
    assert "sub" in src.defaults


def test_default_settings_source_nested_model_partial_override():
    class SubModel(BaseModel):
        x: int = 10

    class SettingsWithNested(BaseSettings):
        model_config = {}
        sub: SubModel = SubModel()

    src = DefaultSettingsSource(SettingsWithNested, nested_model_default_partial_update=True)
    assert src.nested_model_default_partial_update is True


# ---------------------------------------------------------------------------
# InitSettingsSource tests
# ---------------------------------------------------------------------------


def test_init_settings_source_basic():
    src = InitSettingsSource(SimpleSettings, {"name": "overridden"})
    assert src.init_kwargs == {"name": "overridden"}


def test_init_settings_source_call():
    src = InitSettingsSource(SimpleSettings, {"name": "hi"})
    result = src()
    assert result == {"name": "hi"}


def test_init_settings_source_get_field_value():
    src = InitSettingsSource(SimpleSettings, {})
    field = SimpleSettings.model_fields["name"]
    val, key, is_complex = src.get_field_value(field, "name")
    assert val is None
    assert key == ""
    assert is_complex is False


def test_init_settings_source_repr():
    src = InitSettingsSource(SimpleSettings, {"name": "test"})
    r = repr(src)
    assert "InitSettingsSource" in r
    assert "init_kwargs" in r


def test_init_settings_source_nested_model_default_partial_update_call():
    class Sub(BaseModel):
        x: int = 1

    class SettingsPartial(BaseSettings):
        model_config = {"nested_model_default_partial_update": True}
        sub: Sub = Sub()

    src = InitSettingsSource(SettingsPartial, {"sub": {"x": 99}})
    result = src()
    assert result["sub"] == {"x": 99}


def test_init_settings_source_populate_by_name():
    class AliasedSettings(BaseSettings):
        model_config = {"populate_by_name": True}
        name: str = Field(default="default", alias="full_name")

    src = InitSettingsSource(AliasedSettings, {"name": "by_name"})
    # When populate_by_name is True, using field name should work
    assert "full_name" in src.init_kwargs or "name" in src.init_kwargs


def test_init_settings_source_extra_kwargs():
    src = InitSettingsSource(SimpleSettings, {"name": "x", "extra_field": "extra_val"})
    assert "extra_field" in src.init_kwargs


# ---------------------------------------------------------------------------
# PydanticBaseEnvSettingsSource tests (via EnvSettingsSource)
# ---------------------------------------------------------------------------


def test_env_settings_source_init_defaults(monkeypatch):
    monkeypatch.delenv("NAME", raising=False)
    src = EnvSettingsSource(SimpleSettings)
    assert src.case_sensitive is False
    assert src.env_prefix == ""
    assert src.env_prefix_target == "variable"
    assert src.env_ignore_empty is False
    assert src.env_parse_none_str is None
    assert src.env_parse_enums is None


def test_env_settings_source_init_with_params(monkeypatch):
    class PrefixedSettings(BaseSettings):
        model_config = {"env_prefix": "MYAPP_", "case_sensitive": True}
        name: str = "default"

    src = EnvSettingsSource(PrefixedSettings, case_sensitive=False, env_prefix="OVERRIDE_")
    assert src.case_sensitive is False
    assert src.env_prefix == "OVERRIDE_"


def test_apply_case_sensitive_lowercases_when_not_case_sensitive():
    src = EnvSettingsSource(SimpleSettings)
    assert src._apply_case_sensitive("FOO_BAR") == "foo_bar"


def test_apply_case_sensitive_preserves_case_when_sensitive():
    class CaseSensitiveSettings(BaseSettings):
        model_config = {"case_sensitive": True}
        NAME: str = "default"

    src = EnvSettingsSource(CaseSensitiveSettings)
    assert src._apply_case_sensitive("FOO_BAR") == "FOO_BAR"


def test_extract_field_info_simple_field():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    info = src._extract_field_info(field, "name")
    assert len(info) >= 1
    field_key, env_name, is_complex = info[0]
    assert field_key == "name"
    assert env_name == "name"
    assert is_complex is False


def test_extract_field_info_with_prefix():
    class PrefixedSettings(BaseSettings):
        model_config = {"env_prefix": "APP_"}
        value: int = 0

    src = EnvSettingsSource(PrefixedSettings)
    field = PrefixedSettings.model_fields["value"]
    info = src._extract_field_info(field, "value")
    assert len(info) >= 1
    _, env_name, _ = info[0]
    assert env_name == "app_value"


def test_extract_field_info_with_string_validation_alias():
    class AliasedSettings(BaseSettings):
        model_config = {"env_prefix": ""}
        name: str = Field(default="default", validation_alias="full_name")

    src = EnvSettingsSource(AliasedSettings)
    field = AliasedSettings.model_fields["name"]
    info = src._extract_field_info(field, "name")
    # Should have an entry for "full_name"
    env_names = [entry[1] for entry in info]
    assert "full_name" in env_names


def test_extract_field_info_with_alias_choices():
    class AliasChoicesSettings(BaseSettings):
        model_config = {"env_prefix": ""}
        name: str = Field(default="default", validation_alias=AliasChoices("alias1", "alias2"))

    src = EnvSettingsSource(AliasChoicesSettings)
    field = AliasChoicesSettings.model_fields["name"]
    info = src._extract_field_info(field, "name")
    keys = [entry[0] for entry in info]
    assert "alias1" in keys or "alias2" in keys


def test_extract_field_info_with_alias_path():
    class AliasPathSettings(BaseSettings):
        model_config = {"env_prefix": ""}
        name: str = Field(default="default", validation_alias=AliasPath("nested", "name"))

    src = EnvSettingsSource(AliasPathSettings)
    field = AliasPathSettings.model_fields["name"]
    info = src._extract_field_info(field, "name")
    assert len(info) >= 1


def test_replace_env_none_type_values():
    src = EnvSettingsSource(SimpleSettings)
    value = {"a": "real_value", "b": EnvNoneType("none_str"), "c": {"nested": EnvNoneType("null")}}
    result = src._replace_env_none_type_values(value)
    assert result["a"] == "real_value"
    assert result["b"] is None
    assert result["c"]["nested"] is None


def test_env_settings_source_reads_from_env(monkeypatch):
    monkeypatch.setenv("NAME", "from_env")
    monkeypatch.setenv("VALUE", "99")
    src = EnvSettingsSource(SimpleSettings)
    data = src()
    assert data.get("name") == "from_env"


def test_env_settings_source_empty_env(monkeypatch):
    monkeypatch.delenv("NAME", raising=False)
    monkeypatch.delenv("VALUE", raising=False)
    src = EnvSettingsSource(SimpleSettings)
    data = src()
    assert "name" not in data or data.get("name") == "default_name"


def test_env_settings_source_ignore_empty(monkeypatch):
    monkeypatch.setenv("NAME", "")
    monkeypatch.setenv("VALUE", "10")

    class IgnoreEmptySettings(BaseSettings):
        model_config = {"env_prefix": "", "env_ignore_empty": True}
        name: str = "default"

    src = EnvSettingsSource(IgnoreEmptySettings)
    data = src()
    assert "name" not in data


def test_replace_field_names_case_insensitively():
    class SubModel(BaseModel):
        MyField: str = "default"

    class CISettings(BaseSettings):
        model_config = {"env_prefix": "", "env_nested_delimiter": "__"}
        sub: SubModel = SubModel()

    src = EnvSettingsSource(CISettings)
    field = CISettings.model_fields["sub"]
    result = src._replace_field_names_case_insensitively(field, {"myfield": "replaced"})
    assert "MyField" in result
    assert result["MyField"] == "replaced"


def test_replace_field_names_no_model_fields():
    src = EnvSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields["name"]
    # name field has str annotation, no model_fields
    result = src._replace_field_names_case_insensitively(field, {"anything": "val"})
    assert result == {"anything": "val"}


def test_get_resolved_field_value_returns_preferred_key():
    class AliasedSettings(BaseSettings):
        model_config = {"env_prefix": ""}
        name: str = Field(default="default", validation_alias="full_name")

    monkeypatch_env = {"full_name": "test_value"}

    class FakeEnvSource(EnvSettingsSource):
        def _load_env_vars(self):
            return monkeypatch_env

    src = FakeEnvSource(AliasedSettings)
    field = AliasedSettings.model_fields["name"]
    field_value, field_key, value_is_complex = src._get_resolved_field_value(field, "name")
    assert field_key == "full_name"


def test_env_settings_source_parse_none_str(monkeypatch):
    monkeypatch.setenv("NAME", "null")

    class NoneStrSettings(BaseSettings):
        model_config = {"env_prefix": "", "env_parse_none_str": "null"}
        name: Optional[str] = "default"

    src = EnvSettingsSource(NoneStrSettings)
    data = src()
    assert data.get("name") is None
