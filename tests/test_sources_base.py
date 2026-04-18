"""Tests for pydantic_settings/sources/base.py"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Optional
from unittest.mock import MagicMock

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field

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
from pydantic_settings.sources.types import (
    EnvNoneType,
    ForceDecode,
    NoDecode,
    _CliSubCommand,
)


# --- Test Models ---


class SimpleSettings(BaseSettings):
    name: str = 'default'
    value: int = 42


class NestedModel(BaseModel):
    inner_name: str = 'inner_default'


class NestedSettings(BaseSettings):
    name: str = 'default'
    nested: NestedModel = NestedModel()


@dataclass
class DataclassDefault:
    name: str = 'dc_default'


class SettingsWithDataclassDefault(BaseSettings):
    item: DataclassDefault = DataclassDefault()


class NestedModelDefault(BaseModel):
    name: str = 'model_default'


class SettingsWithModelDefault(BaseSettings):
    item: NestedModelDefault = NestedModelDefault()


class SettingsWithAlias(BaseSettings):
    model_config = {'populate_by_name': True}

    my_field: str = Field(default='default', alias='myField')


class SubCommandModel(BaseModel):
    sub_name: str = 'sub_default'


class SettingsWithSubCommand(BaseSettings):
    model_config = {'cli_exit_on_error': False}

    main_field: str = 'main_default'
    subcommand: Annotated[SubCommandModel | None, _CliSubCommand] = None


class SettingsWithRequiredSubCommand(BaseSettings):
    model_config = {'cli_exit_on_error': True}

    subcommand: Annotated[SubCommandModel | None, _CliSubCommand] = None


class ComplexSettings(BaseSettings):
    data: dict[str, Any] = {}


class SettingsWithNoDecode(BaseSettings):
    model_config = {'enable_decoding': True}

    raw_data: Annotated[str, NoDecode] = ''


class SettingsWithForceDecode(BaseSettings):
    model_config = {'enable_decoding': False}

    force_data: Annotated[str, ForceDecode] = ''


class SettingsWithAliasPath(BaseSettings):
    model_config = {'populate_by_name': True}

    field_with_alias_path: str = Field(default='default', validation_alias=AliasPath('nested', 'value'))


class SettingsWithAliasChoices(BaseSettings):
    my_field: str = Field(default='default', validation_alias=AliasChoices('alias1', 'alias2'))


class SettingsEnvPrefixAlias(BaseSettings):
    model_config = {'env_prefix': 'TEST_', 'env_prefix_target': 'alias'}

    my_field: str = Field(default='default', alias='myField')


class SettingsEnvPrefixAll(BaseSettings):
    model_config = {'env_prefix': 'TEST_', 'env_prefix_target': 'all'}

    my_field: str = Field(default='default', alias='myField')


# --- Tests for get_subcommand ---


class TestGetSubcommand:
    def test_get_subcommand_returns_subcommand_when_set(self):
        sub = SubCommandModel(sub_name='test')
        settings = SettingsWithSubCommand(subcommand=sub)
        result = get_subcommand(settings, is_required=False)
        assert result is sub
        assert result.sub_name == 'test'

    def test_get_subcommand_returns_none_when_not_required_and_not_set(self):
        settings = SettingsWithSubCommand()
        result = get_subcommand(settings, is_required=False)
        assert result is None

    def test_get_subcommand_raises_settings_error_when_required_and_not_set(self):
        settings = SettingsWithSubCommand()
        with pytest.raises(SettingsError, match='CLI subcommand is required'):
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)

    def test_get_subcommand_raises_system_exit_when_required_and_exit_on_error(self):
        settings = SettingsWithSubCommand()
        with pytest.raises(SystemExit, match='CLI subcommand is required'):
            get_subcommand(settings, is_required=True, cli_exit_on_error=True)

    def test_get_subcommand_uses_model_config_for_exit_on_error(self):
        settings = SettingsWithRequiredSubCommand()
        with pytest.raises(SystemExit, match='CLI subcommand is required'):
            get_subcommand(settings, is_required=True)

    def test_get_subcommand_suppresses_errors_when_list_provided(self):
        settings = SettingsWithSubCommand()
        errors: list[SettingsError | SystemExit] = []
        result = get_subcommand(settings, is_required=True, cli_exit_on_error=False, _suppress_errors=errors)
        assert result is None
        assert len(errors) == 1
        assert isinstance(errors[0], SettingsError)

    def test_get_subcommand_with_no_subcommand_fields(self):
        settings = SimpleSettings()
        with pytest.raises(SettingsError, match='no subcommands were found'):
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)


# --- Tests for PydanticBaseSettingsSource ---


class ConcretePydanticBaseSettingsSource(PydanticBaseSettingsSource):
    """Concrete implementation for testing abstract base class."""

    def get_field_value(self, field, field_name):
        return None, field_name, False

    def __call__(self):
        return {}


class TestPydanticBaseSettingsSource:
    def test_init_sets_settings_cls_and_config(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        assert source.settings_cls is SimpleSettings
        assert source.config is SimpleSettings.model_config

    def test_set_current_state(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        state = {'name': 'test'}
        source._set_current_state(state)
        assert source.current_state == state

    def test_set_settings_sources_data(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        data = {'source1': {'name': 'val1'}, 'source2': {'name': 'val2'}}
        source._set_settings_sources_data(data)
        assert source.settings_sources_data == data

    def test_current_state_property_returns_internal_state(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        source._current_state = {'test': 'value'}
        assert source.current_state == {'test': 'value'}

    def test_settings_sources_data_property_returns_internal_data(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        source._settings_sources_data = {'source': {'data': 'value'}}
        assert source.settings_sources_data == {'source': {'data': 'value'}}

    def test_field_is_complex_for_simple_type(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        field_info = SimpleSettings.model_fields['name']
        assert source.field_is_complex(field_info) is False

    def test_field_is_complex_for_dict_type(self):
        source = ConcretePydanticBaseSettingsSource(ComplexSettings)
        field_info = ComplexSettings.model_fields['data']
        assert source.field_is_complex(field_info) is True

    def test_prepare_field_value_simple_value(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        field_info = SimpleSettings.model_fields['name']
        result = source.prepare_field_value('name', field_info, 'test', False)
        assert result == 'test'

    def test_prepare_field_value_none_value(self):
        source = ConcretePydanticBaseSettingsSource(SimpleSettings)
        field_info = SimpleSettings.model_fields['name']
        result = source.prepare_field_value('name', field_info, None, True)
        assert result is None

    def test_prepare_field_value_complex_value(self):
        source = ConcretePydanticBaseSettingsSource(ComplexSettings)
        field_info = ComplexSettings.model_fields['data']
        result = source.prepare_field_value('data', field_info, '{"key": "value"}', True)
        assert result == {'key': 'value'}

    def test_decode_complex_value(self):
        source = ConcretePydanticBaseSettingsSource(ComplexSettings)
        field_info = ComplexSettings.model_fields['data']
        result = source.decode_complex_value('data', field_info, '{"key": "value"}')
        assert result == {'key': 'value'}

    def test_decode_complex_value_with_no_decode(self):
        source = ConcretePydanticBaseSettingsSource(SettingsWithNoDecode)
        field_info = SettingsWithNoDecode.model_fields['raw_data']
        result = source.decode_complex_value('raw_data', field_info, '{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_decode_complex_value_with_enable_decoding_false_no_force(self):
        class SettingsDecodingDisabled(BaseSettings):
            model_config = {'enable_decoding': False}
            data: str = ''

        source = ConcretePydanticBaseSettingsSource(SettingsDecodingDisabled)
        field_info = SettingsDecodingDisabled.model_fields['data']
        result = source.decode_complex_value('data', field_info, '{"key": "value"}')
        assert result == '{"key": "value"}'


# --- Tests for ConfigFileSourceMixin ---


class ConcreteConfigFileSource(ConfigFileSourceMixin):
    """Concrete implementation for testing mixin."""

    def _read_file(self, path: Path) -> dict[str, Any]:
        return {'file': str(path)}


class TestConfigFileSourceMixin:
    def test_read_files_none(self):
        source = ConcreteConfigFileSource()
        result = source._read_files(None)
        assert result == {}

    def test_read_files_single_string(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / 'config.json'
            file_path.touch()
            source = ConcreteConfigFileSource()
            result = source._read_files(str(file_path))
            assert result == {'file': str(file_path)}

    def test_read_files_single_path(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / 'config.json'
            file_path.touch()
            source = ConcreteConfigFileSource()
            result = source._read_files(file_path)
            assert result == {'file': str(file_path)}

    def test_read_files_multiple(self):
        with TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'config1.json'
            file2 = Path(tmpdir) / 'config2.json'
            file1.touch()
            file2.touch()
            source = ConcreteConfigFileSource()
            result = source._read_files([str(file1), str(file2)])
            assert result == {'file': str(file2)}

    def test_read_files_skip_nonexistent(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / 'nonexistent.json'
            source = ConcreteConfigFileSource()
            result = source._read_files(str(file_path))
            assert result == {}

    def test_read_files_deep_merge(self):
        with TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / 'config1.json'
            file1.touch()

            class DeepMergeConfigSource(ConfigFileSourceMixin):
                def __init__(self):
                    self.call_count = 0

                def _read_file(self, path: Path) -> dict[str, Any]:
                    self.call_count += 1
                    if self.call_count == 1:
                        return {'a': {'b': 1}}
                    return {'a': {'c': 2}}

            file2 = Path(tmpdir) / 'config2.json'
            file2.touch()
            source = DeepMergeConfigSource()
            result = source._read_files([str(file1), str(file2)], deep_merge=True)
            assert result == {'a': {'b': 1, 'c': 2}}


# --- Tests for DefaultSettingsSource ---


class TestDefaultSettingsSource:
    def test_init_without_partial_update(self):
        source = DefaultSettingsSource(SimpleSettings)
        assert source.defaults == {}
        assert source.nested_model_default_partial_update is False

    def test_init_with_partial_update_dataclass_default(self):
        source = DefaultSettingsSource(SettingsWithDataclassDefault, nested_model_default_partial_update=True)
        assert source.nested_model_default_partial_update is True
        assert 'item' in source.defaults
        assert source.defaults['item'] == {'name': 'dc_default'}

    def test_init_with_partial_update_model_default(self):
        source = DefaultSettingsSource(SettingsWithModelDefault, nested_model_default_partial_update=True)
        assert source.nested_model_default_partial_update is True
        assert 'item' in source.defaults
        assert source.defaults['item'] == {'name': 'model_default'}

    def test_get_field_value_returns_defaults(self):
        source = DefaultSettingsSource(SimpleSettings)
        result = source.get_field_value(SimpleSettings.model_fields['name'], 'name')
        assert result == (None, '', False)

    def test_call_returns_defaults(self):
        source = DefaultSettingsSource(SettingsWithModelDefault, nested_model_default_partial_update=True)
        result = source()
        assert 'item' in result
        assert result['item'] == {'name': 'model_default'}

    def test_repr(self):
        source = DefaultSettingsSource(SimpleSettings, nested_model_default_partial_update=True)
        assert 'nested_model_default_partial_update=True' in repr(source)


# --- Tests for InitSettingsSource ---


class TestInitSettingsSource:
    def test_init_basic(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'test'})
        assert 'name' in source.init_kwargs
        assert source.init_kwargs['name'] == 'test'

    def test_init_with_alias(self):
        source = InitSettingsSource(SettingsWithAlias, init_kwargs={'myField': 'test'})
        assert 'myField' in source.init_kwargs

    def test_init_with_field_name_when_populate_by_name(self):
        source = InitSettingsSource(SettingsWithAlias, init_kwargs={'my_field': 'test'})
        assert 'myField' in source.init_kwargs

    def test_init_extra_kwargs(self):
        class SettingsWithExtra(BaseSettings):
            model_config = {'extra': 'allow'}
            name: str = 'default'

        source = InitSettingsSource(SettingsWithExtra, init_kwargs={'name': 'test', 'extra_field': 'extra'})
        assert 'name' in source.init_kwargs
        assert 'extra_field' in source.init_kwargs

    def test_get_field_value_returns_defaults(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'test'})
        result = source.get_field_value(SimpleSettings.model_fields['name'], 'name')
        assert result == (None, '', False)

    def test_call_returns_init_kwargs(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'test', 'value': 100})
        result = source()
        assert result == {'name': 'test', 'value': 100}

    def test_call_with_nested_model_partial_update(self):
        source = InitSettingsSource(
            NestedSettings,
            init_kwargs={'nested': NestedModel(inner_name='custom')},
            nested_model_default_partial_update=True
        )
        result = source()
        assert 'nested' in result

    def test_repr(self):
        source = InitSettingsSource(SimpleSettings, init_kwargs={'name': 'test'})
        assert 'init_kwargs=' in repr(source)


# --- Tests for PydanticBaseEnvSettingsSource ---


class ConcreteEnvSettingsSource(PydanticBaseEnvSettingsSource):
    """Concrete implementation for testing."""

    def __init__(self, settings_cls, env_vars=None, **kwargs):
        super().__init__(settings_cls, **kwargs)
        self._env_vars = env_vars or {}

    def get_field_value(self, field, field_name):
        key = self._apply_case_sensitive(self.env_prefix + field_name)
        if key in self._env_vars:
            return self._env_vars[key], field_name, False
        return None, field_name, False


class TestPydanticBaseEnvSettingsSource:
    def test_init_defaults(self):
        source = ConcreteEnvSettingsSource(SimpleSettings)
        assert source.case_sensitive is False
        assert source.env_prefix == ''
        assert source.env_prefix_target == 'variable'
        assert source.env_ignore_empty is False
        assert source.env_parse_none_str is None
        assert source.env_parse_enums is None

    def test_init_with_custom_values(self):
        source = ConcreteEnvSettingsSource(
            SimpleSettings,
            case_sensitive=True,
            env_prefix='TEST_',
            env_prefix_target='alias',
            env_ignore_empty=True,
            env_parse_none_str='null',
            env_parse_enums=True,
        )
        assert source.case_sensitive is True
        assert source.env_prefix == 'TEST_'
        assert source.env_prefix_target == 'alias'
        assert source.env_ignore_empty is True
        assert source.env_parse_none_str == 'null'
        assert source.env_parse_enums is True

    def test_apply_case_sensitive_true(self):
        source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=True)
        assert source._apply_case_sensitive('TestValue') == 'TestValue'

    def test_apply_case_sensitive_false(self):
        source = ConcreteEnvSettingsSource(SimpleSettings, case_sensitive=False)
        assert source._apply_case_sensitive('TestValue') == 'testvalue'

    def test_extract_field_info_simple(self):
        source = ConcreteEnvSettingsSource(SimpleSettings)
        field_info = source._extract_field_info(SimpleSettings.model_fields['name'], 'name')
        assert len(field_info) >= 1
        assert field_info[0][0] == 'name'

    def test_extract_field_info_with_validation_alias(self):
        source = ConcreteEnvSettingsSource(SettingsWithAliasChoices)
        field_info = source._extract_field_info(
            SettingsWithAliasChoices.model_fields['my_field'],
            'my_field'
        )
        assert len(field_info) >= 1

    def test_extract_field_info_with_alias_path(self):
        source = ConcreteEnvSettingsSource(SettingsWithAliasPath)
        field_info = source._extract_field_info(
            SettingsWithAliasPath.model_fields['field_with_alias_path'],
            'field_with_alias_path'
        )
        assert len(field_info) >= 1

    def test_extract_field_info_with_env_prefix_alias(self):
        source = ConcreteEnvSettingsSource(
            SettingsEnvPrefixAlias,
            env_prefix='TEST_',
            env_prefix_target='alias'
        )
        field_info = source._extract_field_info(
            SettingsEnvPrefixAlias.model_fields['my_field'],
            'my_field'
        )
        assert len(field_info) >= 1

    def test_replace_field_names_case_insensitively(self):
        class SubModel(BaseModel):
            Val1: str

        class SettingsWithSub(BaseSettings):
            nested: SubModel

        source = ConcreteEnvSettingsSource(SettingsWithSub, case_sensitive=False)
        field_info = SettingsWithSub.model_fields['nested']
        result = source._replace_field_names_case_insensitively(field_info, {'val1': 'value1'})
        assert result == {'Val1': 'value1'}

    def test_replace_field_names_preserves_unknown(self):
        class SubModel(BaseModel):
            known: str

        class SettingsWithSub(BaseSettings):
            nested: SubModel

        source = ConcreteEnvSettingsSource(SettingsWithSub, case_sensitive=False)
        field_info = SettingsWithSub.model_fields['nested']
        result = source._replace_field_names_case_insensitively(field_info, {'unknown': 'value'})
        assert result == {'unknown': 'value'}

    def test_replace_env_none_type_values_simple(self):
        source = ConcreteEnvSettingsSource(SimpleSettings)
        result = source._replace_env_none_type_values({'key': EnvNoneType('null')})
        assert result == {'key': None}

    def test_replace_env_none_type_values_nested(self):
        source = ConcreteEnvSettingsSource(SimpleSettings)
        result = source._replace_env_none_type_values({
            'key1': 'value',
            'nested': {'key2': EnvNoneType('null')}
        })
        assert result == {'key1': 'value', 'nested': {'key2': None}}

    def test_replace_env_none_type_values_preserves_regular_values(self):
        source = ConcreteEnvSettingsSource(SimpleSettings)
        result = source._replace_env_none_type_values({'key': 'regular_value'})
        assert result == {'key': 'regular_value'}

    def test_call_returns_data_dict(self):
        source = ConcreteEnvSettingsSource(
            SimpleSettings,
            env_vars={'name': 'test_name'}
        )
        result = source()
        assert 'name' in result
        assert result['name'] == 'test_name'

    def test_call_with_env_parse_none_str(self):
        source = ConcreteEnvSettingsSource(
            SimpleSettings,
            env_vars={'name': EnvNoneType('null')},
            env_parse_none_str='null'
        )
        result = source()
        assert 'name' in result
        assert result['name'] is None

    def test_get_resolved_field_value(self):
        source = ConcreteEnvSettingsSource(
            SimpleSettings,
            env_vars={'name': 'test'}
        )
        value, key, is_complex = source._get_resolved_field_value(
            SimpleSettings.model_fields['name'],
            'name'
        )
        assert value == 'test'

    def test_call_raises_settings_error_on_get_field_value_exception(self):
        """Test lines 545-546: SettingsError raised when _get_resolved_field_value fails."""

        class FailingEnvSource(PydanticBaseEnvSettingsSource):
            """Source that fails during get_field_value."""

            def get_field_value(self, field, field_name):
                raise RuntimeError('Simulated failure in get_field_value')

        source = FailingEnvSource(SimpleSettings)
        with pytest.raises(SettingsError) as exc_info:
            source()

        assert 'error getting value for field "name"' in str(exc_info.value)
        assert 'FailingEnvSource' in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_call_raises_settings_error_on_prepare_field_value_error(self):
        """Test lines 552-553: SettingsError raised when prepare_field_value raises ValueError."""

        class FailingPrepareEnvSource(PydanticBaseEnvSettingsSource):
            """Source that fails during prepare_field_value."""

            def get_field_value(self, field, field_name):
                return 'invalid_json', field_name, True

            def prepare_field_value(self, field_name, field, value, value_is_complex):
                raise ValueError('Simulated failure in prepare_field_value')

        source = FailingPrepareEnvSource(SimpleSettings)
        with pytest.raises(SettingsError) as exc_info:
            source()

        assert 'error parsing value for field "name"' in str(exc_info.value)
        assert 'FailingPrepareEnvSource' in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_call_replaces_env_none_type_in_dict(self):
        """Test line 560: _replace_env_none_type_values called for dict field_value."""

        class DictEnvSource(PydanticBaseEnvSettingsSource):
            """Source that returns a dict containing EnvNoneType values."""

            def get_field_value(self, field, field_name):
                if field_name == 'data':
                    # Return dict already decoded, mark as not complex to skip decoding
                    return {'key1': 'value1', 'key2': EnvNoneType('null')}, field_name, False

                return None, field_name, False

            def prepare_field_value(self, field_name, field, value, value_is_complex):
                # Return value as-is without decoding
                return value

        source = DictEnvSource(ComplexSettings, env_parse_none_str='null')
        result = source()

        assert 'data' in result
        assert result['data']['key1'] == 'value1'
        assert result['data']['key2'] is None

    def test_call_replaces_field_names_case_insensitively(self):
        """Test line 568: _replace_field_names_case_insensitively called for dict field_value."""

        class CamelCaseModel(BaseModel):
            FirstName: str = ''
            LastName: str = ''

        class CaseInsensitiveSettings(BaseSettings):
            person: CamelCaseModel = CamelCaseModel()

        class CaseInsensitiveEnvSource(PydanticBaseEnvSettingsSource):
            """Source that returns dict with lowercase field names."""

            def get_field_value(self, field, field_name):
                if field_name == 'person':
                    # Return already decoded dict
                    return {'firstname': 'John', 'lastname': 'Doe'}, field_name, False
                return None, field_name, False

            def prepare_field_value(self, field_name, field, value, value_is_complex):
                # Return value as-is without decoding
                return value

        source = CaseInsensitiveEnvSource(CaseInsensitiveSettings, case_sensitive=False)
        result = source()

        assert 'person' in result
        assert result['person']['FirstName'] == 'John'
        assert result['person']['LastName'] == 'Doe'


# --- Integration tests ---


class TestIntegration:
    def test_simple_settings_with_env(self, monkeypatch):
        monkeypatch.setenv('NAME', 'env_name')
        monkeypatch.setenv('VALUE', '100')

        settings = SimpleSettings()
        assert settings.name == 'env_name'
        assert settings.value == 100

    def test_settings_with_init_values(self):
        settings = SimpleSettings(name='init_name', value=200)
        assert settings.name == 'init_name'
        assert settings.value == 200

    def test_nested_settings_with_default_partial_update(self):
        class PartialNestedSettings(BaseSettings):
            model_config = {'nested_model_default_partial_update': True}
            nested: NestedModel = NestedModel()

        settings = PartialNestedSettings()
        assert settings.nested.inner_name == 'inner_default'
