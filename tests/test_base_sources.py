"""Tests for pydantic_settings/sources/base.py"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Optional

import pytest
from pydantic import AliasChoices, BaseModel, Field
from pydantic.fields import FieldInfo

from pydantic_settings import BaseSettings, ForceDecode, NoDecode, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError
from pydantic_settings.sources.base import (
    ConfigFileSourceMixin,
    DefaultSettingsSource,
    InitSettingsSource,
    PydanticBaseEnvSettingsSource,
    PydanticBaseSettingsSource,
    get_subcommand,
)
from pydantic_settings.sources.types import EnvNoneType, _CliSubCommand


# ---------------------------------------------------------------------------
# Base test settings
# ---------------------------------------------------------------------------


class SimpleSettings(BaseSettings):
    name: str = 'default'
    age: int = 30


# ---------------------------------------------------------------------------
# Concrete helper implementations
# ---------------------------------------------------------------------------


class ConcreteSettingsSource(PydanticBaseSettingsSource):
    """Minimal concrete implementation for testing the abstract base class."""

    def __init__(self, settings_cls: type[BaseSettings], return_data: dict[str, Any] | None = None):
        super().__init__(settings_cls)
        self._return_data = return_data or {}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._return_data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._return_data


class ConcreteEnvSettingsSource(PydanticBaseEnvSettingsSource):
    """Minimal concrete implementation for testing PydanticBaseEnvSettingsSource."""

    def __init__(self, settings_cls: type[BaseSettings], env_data: dict[str, Any] | None = None, **kwargs: Any):
        super().__init__(settings_cls, **kwargs)
        self._env_data = env_data or {}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return self._env_data.get(field_name), field_name, False


class ConcreteConfigFileSource(ConfigFileSourceMixin):
    """Minimal concrete implementation for testing ConfigFileSourceMixin."""

    def __init__(self, file_data: dict[str, Any] | None = None):
        self._file_data = file_data or {}

    def _read_file(self, path: Path) -> dict[str, Any]:
        return dict(self._file_data)


# ---------------------------------------------------------------------------
# Subcommand test models
# ---------------------------------------------------------------------------


class SubCmdA(BaseModel):
    value: str = 'a'


class SubCmdB(BaseModel):
    value: str = 'b'


class ModelWithSubCommands(BaseModel):
    cmd_a: Annotated[Optional[SubCmdA], _CliSubCommand] = None
    cmd_b: Annotated[Optional[SubCmdB], _CliSubCommand] = None


class ModelNoSubCommands(BaseModel):
    name: str = 'test'


# ===========================================================================
# get_subcommand tests
# ===========================================================================


def test_get_subcommand_no_subcommand_fields_not_required():
    model = ModelNoSubCommands()
    result = get_subcommand(model, is_required=False)
    assert result is None


def test_get_subcommand_no_subcommand_fields_required_exit():
    model = ModelNoSubCommands()
    with pytest.raises(SystemExit):
        get_subcommand(model, is_required=True, cli_exit_on_error=True)


def test_get_subcommand_no_subcommand_fields_required_settings_error():
    model = ModelNoSubCommands()
    with pytest.raises(SettingsError):
        get_subcommand(model, is_required=True, cli_exit_on_error=False)


def test_get_subcommand_field_set_returns_subcommand():
    sub = SubCmdA(value='test')
    model = ModelWithSubCommands(cmd_a=sub)
    result = get_subcommand(model, is_required=True)
    assert result is sub


def test_get_subcommand_second_field_set():
    sub = SubCmdB(value='b_value')
    model = ModelWithSubCommands(cmd_b=sub)
    result = get_subcommand(model, is_required=True)
    assert result is sub


def test_get_subcommand_no_field_set_required_raises_system_exit():
    model = ModelWithSubCommands()
    with pytest.raises(SystemExit) as exc_info:
        get_subcommand(model, is_required=True, cli_exit_on_error=True)
    msg = str(exc_info.value)
    assert 'cmd_a' in msg or 'cmd_b' in msg


def test_get_subcommand_no_field_set_required_raises_settings_error():
    model = ModelWithSubCommands()
    with pytest.raises(SettingsError) as exc_info:
        get_subcommand(model, is_required=True, cli_exit_on_error=False)
    msg = str(exc_info.value)
    assert 'cmd_a' in msg or 'cmd_b' in msg


def test_get_subcommand_not_required_returns_none():
    model = ModelWithSubCommands()
    result = get_subcommand(model, is_required=False)
    assert result is None


def test_get_subcommand_suppress_errors_system_exit():
    model = ModelWithSubCommands()
    errors: list[SettingsError | SystemExit] = []
    result = get_subcommand(model, is_required=True, cli_exit_on_error=True, _suppress_errors=errors)
    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], SystemExit)


def test_get_subcommand_suppress_errors_settings_error():
    model = ModelWithSubCommands()
    errors: list[SettingsError | SystemExit] = []
    result = get_subcommand(model, is_required=True, cli_exit_on_error=False, _suppress_errors=errors)
    assert result is None
    assert len(errors) == 1
    assert isinstance(errors[0], SettingsError)


def test_get_subcommand_model_config_cli_exit_on_error():
    """cli_exit_on_error from model_config is used when not passed explicitly."""

    class SettingsNoExit(BaseSettings):
        cmd: Annotated[Optional[SubCmdA], _CliSubCommand] = None
        model_config = SettingsConfigDict(cli_exit_on_error=False)

    model = SettingsNoExit()
    with pytest.raises(SettingsError):
        get_subcommand(model, is_required=True)


def test_get_subcommand_error_message_includes_field_names():
    model = ModelWithSubCommands()
    with pytest.raises(SettingsError, match='cmd_a') as exc_info:
        get_subcommand(model, is_required=True, cli_exit_on_error=False)
    assert 'Error: CLI subcommand is required' in str(exc_info.value)


# ===========================================================================
# PydanticBaseSettingsSource tests
# ===========================================================================


def test_pydantic_base_settings_source_init():
    source = ConcreteSettingsSource(SimpleSettings)
    assert source.settings_cls is SimpleSettings
    assert source.config is SimpleSettings.model_config
    assert source._current_state == {}
    assert source._settings_sources_data == {}


def test_pydantic_base_settings_source_set_current_state():
    source = ConcreteSettingsSource(SimpleSettings)
    state = {'name': 'foo'}
    source._set_current_state(state)
    assert source._current_state == {'name': 'foo'}


def test_pydantic_base_settings_source_set_settings_sources_data():
    source = ConcreteSettingsSource(SimpleSettings)
    states = {'source1': {'name': 'foo'}}
    source._set_settings_sources_data(states)
    assert source._settings_sources_data == {'source1': {'name': 'foo'}}


def test_pydantic_base_settings_source_current_state_property():
    source = ConcreteSettingsSource(SimpleSettings)
    source._current_state = {'key': 'val'}
    assert source.current_state == {'key': 'val'}


def test_pydantic_base_settings_source_settings_sources_data_property():
    source = ConcreteSettingsSource(SimpleSettings)
    source._settings_sources_data = {'s': {'k': 'v'}}
    assert source.settings_sources_data == {'s': {'k': 'v'}}


def test_field_is_complex_str():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    assert source.field_is_complex(field) is False


def test_field_is_complex_int():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['age']
    assert source.field_is_complex(field) is False


def test_field_is_complex_dict():
    class DictSettings(BaseSettings):
        data: dict = {}  # type: ignore[type-arg]

    source = ConcreteSettingsSource(DictSettings)
    field = DictSettings.model_fields['data']
    assert source.field_is_complex(field) is True


def test_field_is_complex_nested_model():
    class Inner(BaseModel):
        x: int = 1

    class NestedSettings(BaseSettings):
        inner: Inner = Inner()

    source = ConcreteSettingsSource(NestedSettings)
    field = NestedSettings.model_fields['inner']
    assert source.field_is_complex(field) is True


def test_prepare_field_value_none():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    result = source.prepare_field_value('name', field, None, False)
    assert result is None


def test_prepare_field_value_simple_string():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    result = source.prepare_field_value('name', field, 'hello', False)
    assert result == 'hello'


def test_prepare_field_value_complex_field_decodes_json():
    class DictSettings(BaseSettings):
        data: dict = {}  # type: ignore[type-arg]

    source = ConcreteSettingsSource(DictSettings)
    field = DictSettings.model_fields['data']
    result = source.prepare_field_value('data', field, '{"key": "val"}', False)
    assert result == {'key': 'val'}


def test_prepare_field_value_value_is_complex_flag():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    result = source.prepare_field_value('name', field, '{"key": "val"}', True)
    assert result == {'key': 'val'}


def test_decode_complex_value_json_object():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    result = source.decode_complex_value('name', field, '{"key": "value"}')
    assert result == {'key': 'value'}


def test_decode_complex_value_json_list():
    source = ConcreteSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    result = source.decode_complex_value('name', field, '[1, 2, 3]')
    assert result == [1, 2, 3]


def test_decode_complex_value_no_decode_annotation():
    class NoDecodeSettings(BaseSettings):
        data: Annotated[str, NoDecode] = ''

    source = ConcreteSettingsSource(NoDecodeSettings)
    field = NoDecodeSettings.model_fields['data']
    value = '{"key": "value"}'
    result = source.decode_complex_value('data', field, value)
    assert result == value


def test_decode_complex_value_enable_decoding_false():
    class NoDecodingSettings(BaseSettings):
        data: str = ''
        model_config = SettingsConfigDict(enable_decoding=False)

    source = ConcreteSettingsSource(NoDecodingSettings)
    field = NoDecodingSettings.model_fields['data']
    value = '{"key": "value"}'
    result = source.decode_complex_value('data', field, value)
    assert result == value


def test_decode_complex_value_force_decode_overrides_no_decoding():
    class ForceDecodeSettings(BaseSettings):
        data: Annotated[dict, ForceDecode] = {}  # type: ignore[type-arg]
        model_config = SettingsConfigDict(enable_decoding=False)

    source = ConcreteSettingsSource(ForceDecodeSettings)
    field = ForceDecodeSettings.model_fields['data']
    result = source.decode_complex_value('data', field, '{"key": "value"}')
    assert result == {'key': 'value'}


# ===========================================================================
# ConfigFileSourceMixin tests
# ===========================================================================


def test_read_files_none():
    source = ConcreteConfigFileSource({'key': 'value'})
    result = source._read_files(None)
    assert result == {}


def test_read_files_nonexistent_path():
    source = ConcreteConfigFileSource({'key': 'value'})
    result = source._read_files('/nonexistent/path/that/does/not/exist.json')
    assert result == {}


def test_read_files_existing_path_object(tmp_path: Path):
    test_file = tmp_path / 'test.json'
    test_file.write_text('{}')
    source = ConcreteConfigFileSource({'key': 'value'})
    result = source._read_files(test_file)
    assert result == {'key': 'value'}


def test_read_files_string_path(tmp_path: Path):
    test_file = tmp_path / 'test.json'
    test_file.write_text('{}')
    source = ConcreteConfigFileSource({'key': 'value'})
    result = source._read_files(str(test_file))
    assert result == {'key': 'value'}


def test_read_files_sequence_of_paths(tmp_path: Path):
    file1 = tmp_path / 'file1.json'
    file1.write_text('{}')
    file2 = tmp_path / 'file2.json'
    file2.write_text('{}')
    source = ConcreteConfigFileSource({'key': 'value'})
    result = source._read_files([file1, file2])
    assert result == {'key': 'value'}


def test_read_files_skips_nonexistent_in_sequence(tmp_path: Path):
    existing = tmp_path / 'exists.json'
    existing.write_text('{}')
    missing = tmp_path / 'missing.json'
    source = ConcreteConfigFileSource({'found': True})
    result = source._read_files([missing, existing])
    assert result == {'found': True}


def test_read_files_deep_merge(tmp_path: Path):
    file1 = tmp_path / 'file1.json'
    file1.write_text('{}')
    file2 = tmp_path / 'file2.json'
    file2.write_text('{}')
    call_count = 0

    class CountingSource(ConfigFileSourceMixin):
        def _read_file(self, path: Path) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {'a': {'x': 1}} if call_count == 1 else {'a': {'y': 2}}

    source = CountingSource()
    result = source._read_files([file1, file2], deep_merge=True)
    assert result == {'a': {'x': 1, 'y': 2}}


def test_read_files_no_deep_merge_overrides(tmp_path: Path):
    file1 = tmp_path / 'file1.json'
    file1.write_text('{}')
    file2 = tmp_path / 'file2.json'
    file2.write_text('{}')
    call_count = 0

    class OverrideSource(ConfigFileSourceMixin):
        def _read_file(self, path: Path) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return {'a': 1} if call_count == 1 else {'a': 2}

    source = OverrideSource()
    result = source._read_files([file1, file2])
    assert result == {'a': 2}


# ===========================================================================
# DefaultSettingsSource tests
# ===========================================================================


def test_default_settings_source_init():
    source = DefaultSettingsSource(SimpleSettings)
    assert source.settings_cls is SimpleSettings
    assert isinstance(source.defaults, dict)
    assert source.nested_model_default_partial_update is False


def test_default_settings_source_call_returns_defaults():
    source = DefaultSettingsSource(SimpleSettings)
    result = source()
    assert result is source.defaults


def test_default_settings_source_get_field_value():
    source = DefaultSettingsSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    value, key, is_complex = source.get_field_value(field, 'name')
    assert value is None
    assert key == ''
    assert is_complex is False


def test_default_settings_source_repr():
    source = DefaultSettingsSource(SimpleSettings)
    r = repr(source)
    assert 'DefaultSettingsSource' in r
    assert 'nested_model_default_partial_update' in r


def test_default_settings_source_no_nested_update():
    source = DefaultSettingsSource(SimpleSettings, nested_model_default_partial_update=False)
    assert source.nested_model_default_partial_update is False
    assert source.defaults == {}


def test_default_settings_source_nested_model_partial_update_via_arg():
    source = DefaultSettingsSource(SimpleSettings, nested_model_default_partial_update=True)
    assert source.nested_model_default_partial_update is True


def test_default_settings_source_nested_model_partial_update_from_config():
    class InnerModel(BaseModel):
        x: int = 1

    class NestedSettings(BaseSettings):
        inner: InnerModel = InnerModel()
        model_config = SettingsConfigDict(nested_model_default_partial_update=True)

    source = DefaultSettingsSource(NestedSettings)
    assert source.nested_model_default_partial_update is True
    assert 'inner' in source.defaults
    assert source.defaults['inner'] == {'x': 1}


def test_default_settings_source_nested_dataclass_partial_update():
    @dataclass
    class DataCls:
        x: int = 5

    class DataclsSettings(BaseSettings):
        dc: DataCls = DataCls()  # type: ignore[call-arg]
        model_config = SettingsConfigDict(nested_model_default_partial_update=True)

    source = DefaultSettingsSource(DataclsSettings)
    assert source.nested_model_default_partial_update is True
    assert 'dc' in source.defaults
    assert source.defaults['dc'] == {'x': 5}


# ===========================================================================
# InitSettingsSource tests
# ===========================================================================


def test_init_settings_source_init():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'foo'})
    assert source.settings_cls is SimpleSettings
    assert source.init_kwargs.get('name') == 'foo'


def test_init_settings_source_empty_init_kwargs():
    source = InitSettingsSource(SimpleSettings, init_kwargs={})
    assert source.init_kwargs == {}


def test_init_settings_source_call():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'foo'})
    result = source()
    assert result == source.init_kwargs


def test_init_settings_source_get_field_value():
    source = InitSettingsSource(SimpleSettings, init_kwargs={})
    field = SimpleSettings.model_fields['name']
    value, key, is_complex = source.get_field_value(field, 'name')
    assert value is None
    assert key == ''
    assert is_complex is False


def test_init_settings_source_repr():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'foo'})
    r = repr(source)
    assert 'InitSettingsSource' in r
    assert 'init_kwargs' in r


def test_init_settings_source_nested_model_partial_update_arg():
    source = InitSettingsSource(SimpleSettings, init_kwargs={}, nested_model_default_partial_update=True)
    assert source.nested_model_default_partial_update is True


def test_init_settings_source_call_with_nested_partial_update():
    source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'foo'}, nested_model_default_partial_update=True)
    result = source()
    assert isinstance(result, dict)
    assert result.get('name') == 'foo'


def test_init_settings_source_populate_by_name():
    class AliasSettings(BaseSettings):
        model_config = SettingsConfigDict(populate_by_name=True)
        my_name: str = Field(default='default', alias='myName')

    source = InitSettingsSource(AliasSettings, init_kwargs={'my_name': 'by_field_name'})
    # populate_by_name=True normalizes to the preferred alias
    assert source.init_kwargs.get('myName') == 'by_field_name'


def test_init_settings_source_alias_key():
    class AliasSettings(BaseSettings):
        my_name: str = Field(default='default', alias='myName')

    source = InitSettingsSource(AliasSettings, init_kwargs={'myName': 'by_alias'})
    assert source.init_kwargs.get('myName') == 'by_alias'


def test_init_settings_source_extra_kwargs_included():
    class ExtraSettings(BaseSettings):
        name: str = 'default'
        model_config = SettingsConfigDict(extra='allow')

    source = InitSettingsSource(ExtraSettings, init_kwargs={'name': 'foo', 'extra_key': 'extra_val'})
    assert source.init_kwargs.get('name') == 'foo'
    assert source.init_kwargs.get('extra_key') == 'extra_val'


# ===========================================================================
# PydanticBaseEnvSettingsSource tests
# ===========================================================================


def test_pydantic_base_env_settings_source_init_defaults():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    assert source.settings_cls is SimpleSettings
    assert source.case_sensitive is False
    assert source.env_prefix == ''
    assert source.env_prefix_target == 'variable'
    assert source.env_ignore_empty is False
    assert source.env_parse_none_str is None
    assert source.env_parse_enums is None


def test_pydantic_base_env_settings_source_init_with_args():
    source = ConcreteEnvSettingsSource(
        SimpleSettings,
        case_sensitive=True,
        env_prefix='MY_',
        env_prefix_target='alias',
        env_ignore_empty=True,
        env_parse_none_str='null',
        env_parse_enums=True,
    )
    assert source.case_sensitive is True
    assert source.env_prefix == 'MY_'
    assert source.env_prefix_target == 'alias'
    assert source.env_ignore_empty is True
    assert source.env_parse_none_str == 'null'
    assert source.env_parse_enums is True


def test_apply_case_sensitive_insensitive():
    source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=False)
    assert source._apply_case_sensitive('MY_VAR') == 'my_var'


def test_apply_case_sensitive_sensitive():
    source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=True)
    assert source._apply_case_sensitive('MY_VAR') == 'MY_VAR'


def test_apply_case_sensitive_already_lower():
    source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=False)
    assert source._apply_case_sensitive('my_var') == 'my_var'


def test_extract_field_info_simple_field():
    source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=False)
    field = SimpleSettings.model_fields['name']
    result = source._extract_field_info(field, 'name')
    assert len(result) >= 1
    field_key, env_name, value_is_complex = result[0]
    assert field_key == 'name'
    assert env_name == 'name'
    assert value_is_complex is False


def test_extract_field_info_with_env_prefix():
    source = ConcreteEnvSettingsSource(SimpleSettings, env_prefix='APP_', case_sensitive=False)
    field = SimpleSettings.model_fields['name']
    result = source._extract_field_info(field, 'name')
    assert any(env_name == 'app_name' for _, env_name, _ in result)


def test_extract_field_info_with_validation_alias():
    class AliasSettings(BaseSettings):
        my_name: str = Field(default='', validation_alias='my_alias')

    source = ConcreteEnvSettingsSource(AliasSettings, case_sensitive=False)
    field = AliasSettings.model_fields['my_name']
    result = source._extract_field_info(field, 'my_name')
    assert any(env_name == 'my_alias' for _, env_name, _ in result)


def test_extract_field_info_with_alias_choices():
    class AliasChoicesSettings(BaseSettings):
        my_name: str = Field(default='', validation_alias=AliasChoices('alias_a', 'alias_b'))

    source = ConcreteEnvSettingsSource(AliasChoicesSettings, case_sensitive=False)
    field = AliasChoicesSettings.model_fields['my_name']
    result = source._extract_field_info(field, 'my_name')
    env_names = [env_name for _, env_name, _ in result]
    assert 'alias_a' in env_names or 'alias_b' in env_names


def test_replace_env_none_type_values_plain_values():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    result = source._replace_env_none_type_values({'key': 'value', 'other': 'data'})
    assert result == {'key': 'value', 'other': 'data'}


def test_replace_env_none_type_values_replaces_env_none_type():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    result = source._replace_env_none_type_values({'key': EnvNoneType('null'), 'other': 'data'})
    assert result['key'] is None
    assert result['other'] == 'data'


def test_replace_env_none_type_values_nested_dict():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    result = source._replace_env_none_type_values({'outer': {'inner': EnvNoneType('null')}})
    assert result['outer']['inner'] is None


def test_replace_env_none_type_values_mixed():
    source = ConcreteEnvSettingsSource(SimpleSettings)
    result = source._replace_env_none_type_values({
        'a': EnvNoneType('null'),
        'b': 'keep',
        'c': {'nested': EnvNoneType('null'), 'd': 'keep_nested'},
    })
    assert result['a'] is None
    assert result['b'] == 'keep'
    assert result['c']['nested'] is None
    assert result['c']['d'] == 'keep_nested'


def test_replace_field_names_case_insensitively_no_model():
    """Passes through unchanged when field annotation has no model_fields."""
    source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=False)
    field = SimpleSettings.model_fields['name']  # str, no model_fields
    result = source._replace_field_names_case_insensitively(field, {'key': 'value'})
    assert result == {'key': 'value'}


def test_replace_field_names_case_insensitively_normalizes_key():
    class SubModel(BaseModel):
        MyField: str = 'default'

    class SubSettings(BaseSettings):
        sub: Optional[SubModel] = None

    source = ConcreteEnvSettingsSource(SubSettings, case_sensitive=False)
    field = SubSettings.model_fields['sub']
    result = source._replace_field_names_case_insensitively(field, {'myfield': 'test_value'})
    assert 'MyField' in result
    assert result['MyField'] == 'test_value'


def test_replace_field_names_case_insensitively_unknown_key_passes_through():
    class SubModel(BaseModel):
        known: str = 'default'

    class SubSettings(BaseSettings):
        sub: Optional[SubModel] = None

    source = ConcreteEnvSettingsSource(SubSettings, case_sensitive=False)
    field = SubSettings.model_fields['sub']
    result = source._replace_field_names_case_insensitively(field, {'unknown_key': 'value'})
    assert result == {'unknown_key': 'value'}


def test_get_resolved_field_value_returns_value():
    class SimpleEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            return 'test_val', field_name, False

    source = SimpleEnvSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    field_value, field_key, value_is_complex = source._get_resolved_field_value(field, 'name')
    assert field_value == 'test_val'
    assert field_key == 'name'
    assert value_is_complex is False


def test_get_resolved_field_value_complex_uses_original_key():
    class ComplexEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            return {'x': 1}, field_name, True  # value_is_complex=True

    source = ComplexEnvSource(SimpleSettings)
    field = SimpleSettings.model_fields['name']
    field_value, field_key, value_is_complex = source._get_resolved_field_value(field, 'name')
    assert field_value == {'x': 1}
    assert value_is_complex is True


def test_pydantic_base_env_settings_source_call_returns_data():
    class DataEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            return 'from_env', field_name, False

    source = DataEnvSource(SimpleSettings)
    result = source()
    assert result.get('name') == 'from_env'
    assert result.get('age') == 'from_env'


def test_pydantic_base_env_settings_source_call_empty():
    class EmptyEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            return None, field_name, False

    source = EmptyEnvSource(SimpleSettings)
    result = source()
    assert result == {}


def test_pydantic_base_env_settings_source_call_with_none_str_replaces_env_none_type():
    class NoneStrEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            if field_name == 'name':
                return EnvNoneType('null'), field_name, False
            return None, field_name, False

    source = NoneStrEnvSource(SimpleSettings, env_parse_none_str='null')
    result = source()
    assert result.get('name') is None


def test_pydantic_base_env_settings_source_call_with_dict_value_case_insensitive():
    class SubModel(BaseModel):
        MyKey: str = 'default'

    class SubSettings(BaseSettings):
        sub: Optional[SubModel] = None

    class DictEnvSource(PydanticBaseEnvSettingsSource):
        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            if field_name == 'sub':
                return {'mykey': 'val'}, field_name, False
            return None, field_name, False

    source = DictEnvSource(SubSettings, case_sensitive=False)
    result = source()
    # case-insensitive mode should normalize keys in the dict value
    assert 'sub' in result
    assert 'MyKey' in result['sub']
