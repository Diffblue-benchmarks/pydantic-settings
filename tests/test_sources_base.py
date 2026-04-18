"""Tests for pydantic_settings.sources.base module."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Optional

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.base import (
    ConfigFileSourceMixin,
    DefaultSettingsSource,
    InitSettingsSource,
    PydanticBaseEnvSettingsSource,
    PydanticBaseSettingsSource,
    get_subcommand,
)
from pydantic_settings.sources.types import EnvNoneType, ForceDecode, NoDecode, _CliSubCommand


# Test get_subcommand function


def test_get_subcommand_with_valid_subcommand():
    """Test get_subcommand returns the subcommand when set."""

    class SubModel(BaseModel):
        value: str = "sub"

    class MainModel(BaseSettings):
        sub: Annotated[Optional[SubModel], _CliSubCommand] = None

    model = MainModel(sub=SubModel(value="test"))
    result = get_subcommand(model)

    assert result is not None
    assert isinstance(result, SubModel)
    assert result.value == "test"


def test_get_subcommand_without_subcommand_required_exit_on_error():
    """Test get_subcommand raises SystemExit when subcommand is required and missing."""

    class SubModel(BaseModel):
        value: str = "sub"

    class MainModel(BaseSettings):
        sub: Annotated[Optional[SubModel], _CliSubCommand] = None

    model = MainModel()

    with pytest.raises(SystemExit):
        get_subcommand(model, is_required=True, cli_exit_on_error=True)


def test_get_subcommand_without_subcommand_required_no_exit_on_error():
    """Test get_subcommand raises SettingsError when subcommand is required and cli_exit_on_error is False."""

    class SubModel(BaseModel):
        value: str = "sub"

    class MainModel(BaseSettings):
        sub: Annotated[Optional[SubModel], _CliSubCommand] = None

    model = MainModel()

    with pytest.raises(SettingsError):
        get_subcommand(model, is_required=True, cli_exit_on_error=False)


def test_get_subcommand_without_subcommand_not_required():
    """Test get_subcommand returns None when subcommand is not required."""

    class SubModel(BaseModel):
        value: str = "sub"

    class MainModel(BaseSettings):
        sub: Annotated[Optional[SubModel], _CliSubCommand] = None

    model = MainModel()
    result = get_subcommand(model, is_required=False)

    assert result is None


def test_get_subcommand_with_model_config_cli_exit_on_error():
    """Test get_subcommand uses model_config cli_exit_on_error."""

    class SubModel(BaseModel):
        value: str = "sub"

    class MainModel(BaseSettings):
        model_config = {"cli_exit_on_error": False}
        sub: Annotated[Optional[SubModel], _CliSubCommand] = None

    model = MainModel()

    with pytest.raises(SettingsError):
        get_subcommand(model, is_required=True)


def test_get_subcommand_with_suppress_errors():
    """Test get_subcommand appends errors to suppress_errors list."""

    class SubModel(BaseModel):
        value: str = "sub"

    class MainModel(BaseSettings):
        sub: Annotated[Optional[SubModel], _CliSubCommand] = None

    model = MainModel()
    suppress_errors = []

    result = get_subcommand(model, is_required=True, cli_exit_on_error=True, _suppress_errors=suppress_errors)

    assert result is None
    assert len(suppress_errors) == 1
    assert isinstance(suppress_errors[0], SystemExit)


def test_get_subcommand_no_subcommands_found():
    """Test get_subcommand with model that has no subcommands."""

    class MainModel(BaseSettings):
        value: str = "test"

    model = MainModel()

    with pytest.raises(SystemExit) as exc_info:
        get_subcommand(model, is_required=True)

    assert "no subcommands were found" in str(exc_info.value)


def test_get_subcommand_multiple_subcommands():
    """Test get_subcommand with multiple subcommand fields."""

    class SubModel1(BaseModel):
        value: str = "sub1"

    class SubModel2(BaseModel):
        value: str = "sub2"

    class MainModel(BaseSettings):
        sub1: Annotated[Optional[SubModel1], _CliSubCommand] = None
        sub2: Annotated[Optional[SubModel2], _CliSubCommand] = None

    model = MainModel(sub2=SubModel2(value="test"))
    result = get_subcommand(model)

    assert result is not None
    assert isinstance(result, SubModel2)


# Test PydanticBaseSettingsSource


class MockSettingsSource(PydanticBaseSettingsSource):
    """Mock implementation for testing abstract base class."""

    def get_field_value(self, field: FieldInfo, field_name: str):
        return None, field_name, False

    def __call__(self):
        return {}


def test_pydantic_base_settings_source_init():
    """Test PydanticBaseSettingsSource initialization."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockSettingsSource(TestSettings)

    assert source.settings_cls == TestSettings
    assert source.config == TestSettings.model_config
    assert source._current_state == {}
    assert source._settings_sources_data == {}


def test_pydantic_base_settings_source_set_current_state():
    """Test _set_current_state method."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockSettingsSource(TestSettings)
    state = {"key": "value"}
    source._set_current_state(state)

    assert source._current_state == state


def test_pydantic_base_settings_source_set_settings_sources_data():
    """Test _set_settings_sources_data method."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockSettingsSource(TestSettings)
    states = {"source1": {"key": "value"}}
    source._set_settings_sources_data(states)

    assert source._settings_sources_data == states


def test_pydantic_base_settings_source_current_state_property():
    """Test current_state property."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockSettingsSource(TestSettings)
    state = {"key": "value"}
    source._set_current_state(state)

    assert source.current_state == state


def test_pydantic_base_settings_source_settings_sources_data_property():
    """Test settings_sources_data property."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockSettingsSource(TestSettings)
    states = {"source1": {"key": "value"}}
    source._set_settings_sources_data(states)

    assert source.settings_sources_data == states


def test_pydantic_base_settings_source_field_is_complex():
    """Test field_is_complex method."""

    class TestSettings(BaseSettings):
        simple: str = "test"
        complex_field: dict = {}

    source = MockSettingsSource(TestSettings)
    simple_field = TestSettings.model_fields["simple"]
    complex_field_info = TestSettings.model_fields["complex_field"]

    assert not source.field_is_complex(simple_field)
    assert source.field_is_complex(complex_field_info)


def test_pydantic_base_settings_source_prepare_field_value_simple():
    """Test prepare_field_value with simple value."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source.prepare_field_value("value", field, "simple_value", False)
    assert result == "simple_value"


def test_pydantic_base_settings_source_prepare_field_value_complex():
    """Test prepare_field_value with complex value."""

    class TestSettings(BaseSettings):
        value: dict = {}

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    json_value = '{"key": "value"}'
    result = source.prepare_field_value("value", field, json_value, True)
    assert result == {"key": "value"}


def test_pydantic_base_settings_source_prepare_field_value_none():
    """Test prepare_field_value with None value."""

    class TestSettings(BaseSettings):
        value: Optional[dict] = None

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source.prepare_field_value("value", field, None, True)
    assert result is None


def test_pydantic_base_settings_source_decode_complex_value():
    """Test decode_complex_value method."""

    class TestSettings(BaseSettings):
        value: dict = {}

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    json_value = '{"key": "value", "nested": {"inner": "data"}}'
    result = source.decode_complex_value("value", field, json_value)
    assert result == {"key": "value", "nested": {"inner": "data"}}


def test_pydantic_base_settings_source_decode_complex_value_no_decode():
    """Test decode_complex_value with NoDecode metadata."""

    class TestSettings(BaseSettings):
        value: Annotated[dict, NoDecode] = {}

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    json_value = '{"key": "value"}'
    result = source.decode_complex_value("value", field, json_value)
    assert result == json_value


def test_pydantic_base_settings_source_decode_complex_value_decoding_disabled():
    """Test decode_complex_value when enable_decoding is False."""

    class TestSettings(BaseSettings):
        model_config = {"enable_decoding": False}
        value: dict = {}

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    json_value = '{"key": "value"}'
    result = source.decode_complex_value("value", field, json_value)
    assert result == json_value


def test_pydantic_base_settings_source_decode_complex_value_force_decode():
    """Test decode_complex_value with ForceDecode metadata overriding enable_decoding."""

    class TestSettings(BaseSettings):
        model_config = {"enable_decoding": False}
        value: Annotated[dict, ForceDecode] = {}

    source = MockSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    json_value = '{"key": "value"}'
    result = source.decode_complex_value("value", field, json_value)
    assert result == {"key": "value"}


# Test ConfigFileSourceMixin


class MockConfigFileSource(ConfigFileSourceMixin):
    """Mock implementation for testing mixin."""

    def _read_file(self, path: Path) -> dict[str, Any]:
        return {"from_file": str(path)}


def test_config_file_source_mixin_read_files_none():
    """Test _read_files with None."""
    source = MockConfigFileSource()
    result = source._read_files(None)
    assert result == {}


def test_config_file_source_mixin_read_files_string(tmp_path):
    """Test _read_files with string path."""
    test_file = tmp_path / "test.conf"
    test_file.write_text("content")

    source = MockConfigFileSource()
    result = source._read_files(str(test_file))

    assert "from_file" in result


def test_config_file_source_mixin_read_files_path(tmp_path):
    """Test _read_files with Path object."""
    test_file = tmp_path / "test.conf"
    test_file.write_text("content")

    source = MockConfigFileSource()
    result = source._read_files(test_file)

    assert "from_file" in result


def test_config_file_source_mixin_read_files_list(tmp_path):
    """Test _read_files with list of files."""
    test_file1 = tmp_path / "test1.conf"
    test_file2 = tmp_path / "test2.conf"
    test_file1.write_text("content1")
    test_file2.write_text("content2")

    source = MockConfigFileSource()
    result = source._read_files([test_file1, test_file2])

    assert "from_file" in result


def test_config_file_source_mixin_read_files_missing_file(tmp_path):
    """Test _read_files skips missing files."""
    missing_file = tmp_path / "missing.conf"

    source = MockConfigFileSource()
    result = source._read_files(missing_file)

    assert result == {}


def test_config_file_source_mixin_read_files_expanduser(tmp_path, monkeypatch):
    """Test _read_files expands user home directory."""
    test_file = tmp_path / "test.conf"
    test_file.write_text("content")

    monkeypatch.setenv("HOME", str(tmp_path))

    source = MockConfigFileSource()
    # This would expand ~ to HOME
    result = source._read_files(test_file)

    assert "from_file" in result


def test_config_file_source_mixin_read_files_deep_merge(tmp_path):
    """Test _read_files with deep_merge=True."""

    class DeepMergeConfigFileSource(ConfigFileSourceMixin):
        def __init__(self):
            self.file_count = 0

        def _read_file(self, path: Path) -> dict[str, Any]:
            self.file_count += 1
            if self.file_count == 1:
                return {"key1": "value1", "nested": {"a": 1}}
            else:
                return {"key2": "value2", "nested": {"b": 2}}

    test_file1 = tmp_path / "test1.conf"
    test_file2 = tmp_path / "test2.conf"
    test_file1.write_text("content1")
    test_file2.write_text("content2")

    source = DeepMergeConfigFileSource()
    result = source._read_files([test_file1, test_file2], deep_merge=True)

    assert "key1" in result
    assert "key2" in result
    assert "nested" in result


def test_config_file_source_mixin_read_files_no_deep_merge(tmp_path):
    """Test _read_files with deep_merge=False (default)."""

    class NoDeepMergeConfigFileSource(ConfigFileSourceMixin):
        def __init__(self):
            self.file_count = 0

        def _read_file(self, path: Path) -> dict[str, Any]:
            self.file_count += 1
            if self.file_count == 1:
                return {"key1": "value1", "nested": {"a": 1}}
            else:
                return {"key2": "value2", "nested": {"b": 2}}

    test_file1 = tmp_path / "test1.conf"
    test_file2 = tmp_path / "test2.conf"
    test_file1.write_text("content1")
    test_file2.write_text("content2")

    source = NoDeepMergeConfigFileSource()
    result = source._read_files([test_file1, test_file2], deep_merge=False)

    assert result.get("nested") == {"b": 2}


# Test DefaultSettingsSource


def test_default_settings_source_init():
    """Test DefaultSettingsSource initialization."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = DefaultSettingsSource(TestSettings)

    assert source.settings_cls == TestSettings
    assert source.defaults == {}
    assert source.nested_model_default_partial_update is False


def test_default_settings_source_with_nested_model_default():
    """Test DefaultSettingsSource with nested model default."""

    class NestedModel(BaseModel):
        nested_value: str = "nested"

    class TestSettings(BaseSettings):
        nested: NestedModel = NestedModel(nested_value="default")

    source = DefaultSettingsSource(TestSettings, nested_model_default_partial_update=True)

    assert "nested" in source.defaults
    assert source.defaults["nested"]["nested_value"] == "default"


def test_default_settings_source_with_dataclass_default():
    """Test DefaultSettingsSource with dataclass default."""

    @dataclass
    class NestedData:
        nested_value: str = "nested"

    class TestSettings(BaseSettings):
        nested: NestedData = NestedData(nested_value="default")

    source = DefaultSettingsSource(TestSettings, nested_model_default_partial_update=True)

    assert "nested" in source.defaults
    assert source.defaults["nested"]["nested_value"] == "default"


def test_default_settings_source_with_model_config():
    """Test DefaultSettingsSource uses model_config for nested_model_default_partial_update."""

    class NestedModel(BaseModel):
        nested_value: str = "nested"

    class TestSettings(BaseSettings):
        model_config = {"nested_model_default_partial_update": True}
        nested: NestedModel = NestedModel(nested_value="default")

    source = DefaultSettingsSource(TestSettings)

    assert source.nested_model_default_partial_update is True


def test_default_settings_source_get_field_value():
    """Test DefaultSettingsSource.get_field_value."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = DefaultSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source.get_field_value(field, "value")
    assert result == (None, '', False)


def test_default_settings_source_call():
    """Test DefaultSettingsSource.__call__."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = DefaultSettingsSource(TestSettings)
    result = source()

    assert result == {}


def test_default_settings_source_repr():
    """Test DefaultSettingsSource.__repr__."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = DefaultSettingsSource(TestSettings, nested_model_default_partial_update=True)
    repr_str = repr(source)

    assert "DefaultSettingsSource" in repr_str
    assert "nested_model_default_partial_update=True" in repr_str


def test_default_settings_source_with_alias():
    """Test DefaultSettingsSource with field aliases."""

    class NestedModel(BaseModel):
        nested_value: str = "nested"

    class TestSettings(BaseSettings):
        nested: NestedModel = Field(default=NestedModel(nested_value="default"), alias="nested_alias")

    source = DefaultSettingsSource(TestSettings, nested_model_default_partial_update=True)

    assert "nested_alias" in source.defaults


# Test InitSettingsSource


def test_init_settings_source_basic():
    """Test InitSettingsSource with basic init_kwargs."""

    class TestSettings(BaseSettings):
        value: str = "test"

    init_kwargs = {"value": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    assert source.init_kwargs == {"value": "init_value"}


def test_init_settings_source_with_alias():
    """Test InitSettingsSource with field alias."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", alias="value_alias")

    init_kwargs = {"value_alias": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    assert source.init_kwargs == {"value_alias": "init_value"}


def test_init_settings_source_populate_by_name():
    """Test InitSettingsSource with populate_by_name."""

    class TestSettings(BaseSettings):
        model_config = {"populate_by_name": True}
        value: str = Field(default="test", alias="value_alias")

    init_kwargs = {"value": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    assert source.init_kwargs == {"value_alias": "init_value"}


def test_init_settings_source_validate_by_name():
    """Test InitSettingsSource with validate_by_name."""

    class TestSettings(BaseSettings):
        model_config = {"validate_by_name": True}
        value: str = Field(default="test", alias="value_alias")

    init_kwargs = {"value": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    assert source.init_kwargs == {"value_alias": "init_value"}


def test_init_settings_source_extra_kwargs():
    """Test InitSettingsSource preserves extra kwargs."""

    class TestSettings(BaseSettings):
        value: str = "test"

    init_kwargs = {"value": "init_value", "extra_key": "extra_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    assert "extra_key" in source.init_kwargs


def test_init_settings_source_get_field_value():
    """Test InitSettingsSource.get_field_value."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = InitSettingsSource(TestSettings, {})
    field = TestSettings.model_fields["value"]

    result = source.get_field_value(field, "value")
    assert result == (None, '', False)


def test_init_settings_source_call_without_partial_update():
    """Test InitSettingsSource.__call__ without partial update."""

    class TestSettings(BaseSettings):
        value: str = "test"

    init_kwargs = {"value": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    result = source()
    assert result == {"value": "init_value"}


def test_init_settings_source_call_with_partial_update():
    """Test InitSettingsSource.__call__ with nested_model_default_partial_update."""

    class TestSettings(BaseSettings):
        value: str = "test"

    init_kwargs = {"value": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs, nested_model_default_partial_update=True)

    result = source()
    assert "value" in result


def test_init_settings_source_repr():
    """Test InitSettingsSource.__repr__."""

    class TestSettings(BaseSettings):
        value: str = "test"

    init_kwargs = {"value": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    repr_str = repr(source)
    assert "InitSettingsSource" in repr_str
    assert "init_kwargs" in repr_str


def test_init_settings_source_multiple_aliases():
    """Test InitSettingsSource with AliasChoices."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", validation_alias=AliasChoices("alias1", "alias2"))

    init_kwargs = {"alias1": "init_value"}
    source = InitSettingsSource(TestSettings, init_kwargs)

    assert "alias1" in source.init_kwargs


# Test PydanticBaseEnvSettingsSource


class MockEnvSettingsSource(PydanticBaseEnvSettingsSource):
    """Mock implementation for testing."""

    def get_field_value(self, field: FieldInfo, field_name: str):
        return None, field_name, False


def test_pydantic_base_env_settings_source_init():
    """Test PydanticBaseEnvSettingsSource initialization."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)

    assert source.case_sensitive is False
    assert source.env_prefix == ''
    assert source.env_ignore_empty is False


def test_pydantic_base_env_settings_source_init_with_params():
    """Test PydanticBaseEnvSettingsSource initialization with parameters."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(
        TestSettings,
        case_sensitive=True,
        env_prefix="TEST_",
        env_prefix_target="alias",
        env_ignore_empty=True,
        env_parse_none_str="null",
        env_parse_enums=True,
    )

    assert source.case_sensitive is True
    assert source.env_prefix == "TEST_"
    assert source.env_prefix_target == "alias"
    assert source.env_ignore_empty is True
    assert source.env_parse_none_str == "null"
    assert source.env_parse_enums is True


def test_pydantic_base_env_settings_source_apply_case_sensitive():
    """Test _apply_case_sensitive method."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings, case_sensitive=False)
    assert source._apply_case_sensitive("VALUE") == "value"

    source2 = MockEnvSettingsSource(TestSettings, case_sensitive=True)
    assert source2._apply_case_sensitive("VALUE") == "VALUE"


def test_pydantic_base_env_settings_source_extract_field_info():
    """Test _extract_field_info method."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    assert len(result) > 0
    assert result[0][0] == "value"


def test_pydantic_base_env_settings_source_extract_field_info_with_alias():
    """Test _extract_field_info with validation_alias."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", validation_alias="value_alias")

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    assert any(item[0] == "value_alias" for item in result)


def test_pydantic_base_env_settings_source_extract_field_info_alias_choices():
    """Test _extract_field_info with AliasChoices."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", validation_alias=AliasChoices("alias1", "alias2"))

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    field_keys = [item[0] for item in result]
    assert "alias1" in field_keys


def test_pydantic_base_env_settings_source_extract_field_info_alias_path():
    """Test _extract_field_info with AliasPath."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", validation_alias=AliasPath("nested", "path"))

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    assert len(result) > 0


def test_pydantic_base_env_settings_source_extract_field_info_with_env_prefix():
    """Test _extract_field_info with env_prefix."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings, env_prefix="APP_", env_prefix_target="variable")
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    assert any("app_value" in item[1] for item in result)


def test_pydantic_base_env_settings_source_replace_field_names_case_insensitively():
    """Test _replace_field_names_case_insensitively method."""

    class NestedModel(BaseModel):
        NestedValue: str = "nested"

    class TestSettings(BaseSettings):
        model_config = {"case_sensitive": False}
        nested: NestedModel = NestedModel()

    source = MockEnvSettingsSource(TestSettings, case_sensitive=False)
    field = TestSettings.model_fields["nested"]

    field_values = {"nestedvalue": "test"}
    result = source._replace_field_names_case_insensitively(field, field_values)

    assert "NestedValue" in result
    assert result["NestedValue"] == "test"


def test_pydantic_base_env_settings_source_replace_field_names_non_model():
    """Test _replace_field_names_case_insensitively with non-model field."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    field_values = {"key": "value"}
    result = source._replace_field_names_case_insensitively(field, field_values)

    assert result == {"key": "value"}


def test_pydantic_base_env_settings_source_replace_field_names_with_optional():
    """Test _replace_field_names_case_insensitively with Optional field."""

    class NestedModel(BaseModel):
        NestedValue: str = "nested"

    class TestSettings(BaseSettings):
        nested: Optional[NestedModel] = None

    source = MockEnvSettingsSource(TestSettings, case_sensitive=False)
    field = TestSettings.model_fields["nested"]

    field_values = {"nestedvalue": "test"}
    result = source._replace_field_names_case_insensitively(field, field_values)

    assert "NestedValue" in result


def test_pydantic_base_env_settings_source_replace_env_none_type_values():
    """Test _replace_env_none_type_values method."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)

    field_value = {"key1": "value1", "key2": EnvNoneType("null")}
    result = source._replace_env_none_type_values(field_value)

    assert result["key1"] == "value1"
    assert result["key2"] is None


def test_pydantic_base_env_settings_source_replace_env_none_type_values_nested():
    """Test _replace_env_none_type_values with nested dict."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)

    field_value = {
        "key1": "value1",
        "nested": {"key2": EnvNoneType("null"), "key3": "value3"}
    }
    result = source._replace_env_none_type_values(field_value)

    assert result["nested"]["key2"] is None
    assert result["nested"]["key3"] == "value3"


def test_pydantic_base_env_settings_source_get_resolved_field_value():
    """Test _get_resolved_field_value method."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._get_resolved_field_value(field, "value")
    assert result[1] == "value"


def test_pydantic_base_env_settings_source_get_resolved_field_value_with_alias():
    """Test _get_resolved_field_value with alias."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", alias="value_alias")

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._get_resolved_field_value(field, "value")
    assert result[1] in ["value", "value_alias"]


def test_pydantic_base_env_settings_source_call():
    """Test PydanticBaseEnvSettingsSource.__call__."""

    class TestSettings(BaseSettings):
        value: str = "test"

    source = MockEnvSettingsSource(TestSettings)
    result = source()

    assert isinstance(result, dict)


def test_pydantic_base_env_settings_source_call_with_error():
    """Test PydanticBaseEnvSettingsSource.__call__ with SettingsError."""

    class ErrorEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str):
            raise ValueError("Test error")

    class TestSettings(BaseSettings):
        value: str = "test"

    source = ErrorEnvSource(TestSettings)

    with pytest.raises(SettingsError) as exc_info:
        source()

    assert "error getting value" in str(exc_info.value)


def test_pydantic_base_env_settings_source_call_with_parse_error():
    """Test PydanticBaseEnvSettingsSource.__call__ with ValueError during prepare."""

    class ParseErrorEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str):
            return "invalid_json", field_name, True

        def decode_complex_value(self, field_name: str, field: FieldInfo, value: Any) -> Any:
            raise ValueError("Invalid JSON")

    class TestSettings(BaseSettings):
        value: dict = {}

    source = ParseErrorEnvSource(TestSettings)

    with pytest.raises(SettingsError) as exc_info:
        source()

    assert "error parsing value" in str(exc_info.value)


def test_pydantic_base_env_settings_source_call_with_env_parse_none_str():
    """Test PydanticBaseEnvSettingsSource.__call__ with env_parse_none_str."""

    class NoneStrEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str):
            return EnvNoneType("null"), field_name, False

    class TestSettings(BaseSettings):
        value: Optional[str] = None

    source = NoneStrEnvSource(TestSettings, env_parse_none_str="null")
    result = source()

    assert result["value"] is None


def test_pydantic_base_env_settings_source_call_with_case_insensitive_dict():
    """Test PydanticBaseEnvSettingsSource.__call__ with case insensitive dict."""

    class NestedModel(BaseModel):
        NestedValue: str = "nested"

    class DictEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str):
            if field_name == "nested":
                return {"nestedvalue": "test"}, field_name, False  # Not complex, dict value
            return None, field_name, False

        def field_is_complex(self, field: FieldInfo) -> bool:
            # Override to return False for nested model to avoid JSON parsing
            return False

    class TestSettings(BaseSettings):
        nested: NestedModel = NestedModel()

    source = DictEnvSource(TestSettings, case_sensitive=False)
    result = source()

    assert "nested" in result
    assert "NestedValue" in result["nested"]


def test_pydantic_base_env_settings_source_extract_field_info_populate_by_name():
    """Test _extract_field_info with populate_by_name."""

    class TestSettings(BaseSettings):
        model_config = {"populate_by_name": True}
        value: str = Field(default="test", alias="value_alias")

    source = MockEnvSettingsSource(TestSettings)
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    field_keys = [item[0] for item in result]
    assert "value" in field_keys
    assert "value_alias" in field_keys


def test_pydantic_base_env_settings_source_extract_field_info_env_prefix_all():
    """Test _extract_field_info with env_prefix_target='all'."""

    class TestSettings(BaseSettings):
        value: str = Field(default="test", alias="value_alias")

    source = MockEnvSettingsSource(TestSettings, env_prefix="APP_", env_prefix_target="all")
    field = TestSettings.model_fields["value"]

    result = source._extract_field_info(field, "value")
    env_names = [item[1] for item in result]
    assert any("app_" in name for name in env_names)


def test_pydantic_base_env_settings_source_replace_field_names_nested_optional():
    """Test _replace_field_names_case_insensitively with nested optional models."""

    class NestedModel(BaseModel):
        NestedValue: str = "nested"

    class TestSettings(BaseSettings):
        nested: Optional[NestedModel] = None

    source = MockEnvSettingsSource(TestSettings, case_sensitive=False)
    field = TestSettings.model_fields["nested"]

    field_values = {
        "nestedvalue": "test"
    }
    result = source._replace_field_names_case_insensitively(field, field_values)

    assert "NestedValue" in result
    assert result["NestedValue"] == "test"
