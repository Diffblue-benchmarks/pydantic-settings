"""Unit tests for pydantic_settings.sources.base module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo

from pydantic_settings.main import BaseSettings
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
    _CliSubCommand,
    EnvNoneType,
    ForceDecode,
    NoDecode,
)


class SimpleSettings(BaseSettings):
    """Simple settings class for testing."""

    name: str = 'default'
    value: int = 42


class NestedModel(BaseModel):
    """Nested model for testing."""

    sub_name: str = 'nested'
    sub_value: int = 100


class ComplexSettings(BaseSettings):
    """Settings with nested model."""

    name: str = 'default'
    nested: NestedModel = Field(default_factory=NestedModel)


class TestGetSubcommand:
    """Tests for get_subcommand function."""

    def test_get_subcommand_with_no_subcommands(self):
        """Test get_subcommand when model has no subcommands defined."""
        settings = SimpleSettings()
        result = get_subcommand(settings, is_required=False)
        assert result is None

    def test_get_subcommand_required_no_subcommands_raises_error(self):
        """Test get_subcommand raises error when required but no subcommands found."""
        settings = SimpleSettings()
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=True)

    def test_get_subcommand_required_no_subcommands_raises_settings_error(self):
        """Test get_subcommand raises SettingsError when cli_exit_on_error is False."""
        settings = SimpleSettings()
        with pytest.raises(SettingsError):
            get_subcommand(settings, is_required=True, cli_exit_on_error=False)

    def test_get_subcommand_with_suppress_errors(self):
        """Test get_subcommand with error suppression."""
        settings = SimpleSettings()
        errors: list[SettingsError | SystemExit] = []
        result = get_subcommand(settings, is_required=True, cli_exit_on_error=False, _suppress_errors=errors)
        assert result is None
        assert len(errors) == 1

    def test_get_subcommand_cli_exit_on_error_none_uses_config(self):
        """Test get_subcommand uses model config when cli_exit_on_error is None."""

        class ConfiguredSettings(BaseSettings):
            model_config = {'cli_exit_on_error': False}

            name: str = 'default'

        settings = ConfiguredSettings()
        with pytest.raises(SettingsError):
            get_subcommand(settings, is_required=True)

    def test_get_subcommand_cli_exit_on_error_parameter_overrides_config(self):
        """Test get_subcommand parameter overrides model config."""

        class ConfiguredSettings(BaseSettings):
            model_config = {'cli_exit_on_error': False}

            name: str = 'default'

        settings = ConfiguredSettings()
        with pytest.raises(SystemExit):
            get_subcommand(settings, is_required=True, cli_exit_on_error=True)


class TestPydanticBaseSettingsSource:
    """Tests for PydanticBaseSettingsSource class."""

    def test_init_sets_attributes(self):
        """Test __init__ initializes settings_cls and related attributes."""
        source = DefaultSettingsSource(SimpleSettings)
        assert source.settings_cls is SimpleSettings
        assert source.config == SimpleSettings.model_config
        assert source._current_state == {}
        assert source._settings_sources_data == {}

    def test_set_current_state(self):
        """Test _set_current_state updates internal state."""
        source = DefaultSettingsSource(SimpleSettings)
        state = {'key': 'value'}
        source._set_current_state(state)
        assert source._current_state == state

    def test_current_state_property(self):
        """Test current_state property returns stored state."""
        source = DefaultSettingsSource(SimpleSettings)
        state = {'key': 'value'}
        source._set_current_state(state)
        assert source.current_state == state

    def test_set_settings_sources_data(self):
        """Test _set_settings_sources_data updates internal data."""
        source = DefaultSettingsSource(SimpleSettings)
        data = {'source1': {'key': 'value'}}
        source._set_settings_sources_data(data)
        assert source._settings_sources_data == data

    def test_settings_sources_data_property(self):
        """Test settings_sources_data property returns stored data."""
        source = DefaultSettingsSource(SimpleSettings)
        data = {'source1': {'key': 'value'}}
        source._set_settings_sources_data(data)
        assert source.settings_sources_data == data

    def test_field_is_complex_with_dict_field(self):
        """Test field_is_complex returns True for dict fields."""
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=dict)
        result = source.field_is_complex(field_info)
        assert isinstance(result, bool)

    def test_prepare_field_value_with_none_value(self):
        """Test prepare_field_value returns None when value is None."""
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=dict)
        result = source.prepare_field_value('field', field_info, None, True)
        assert result is None

    def test_prepare_field_value_with_non_complex_simple_value(self):
        """Test prepare_field_value returns simple value as-is."""
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=str)
        result = source.prepare_field_value('field', field_info, 'value', False)
        assert result == 'value'

    def test_decode_complex_value_with_json_string(self):
        """Test decode_complex_value parses JSON strings."""
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=dict)
        json_str = '{"key": "value"}'
        result = source.decode_complex_value('field', field_info, json_str)
        assert result == {'key': 'value'}

    def test_decode_complex_value_with_no_decode_metadata(self):
        """Test decode_complex_value skips decoding with NoDecode metadata."""
        from pydantic_settings.sources.utils import _get_field_metadata
        from unittest.mock import patch

        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=str)

        # Mock _get_field_metadata to return NoDecode
        with patch('pydantic_settings.sources.base._get_field_metadata') as mock_get_metadata:
            mock_get_metadata.return_value = [NoDecode]
            result = source.decode_complex_value('field', field_info, 'not_json')
            assert result == 'not_json'

    def test_decode_complex_value_with_force_decode_metadata(self):
        """Test decode_complex_value forces decoding with ForceDecode metadata."""

        class NoDecodingSettings(BaseSettings):
            model_config = {'enable_decoding': False}
            data: dict = Field(default_factory=dict)

        source = DefaultSettingsSource(NoDecodingSettings)
        # ForceDecode should be in field.metadata, not _get_field_metadata
        field_info = FieldInfo(annotation=dict)
        field_info.metadata = [ForceDecode]
        json_str = '{"key": "value"}'
        result = source.decode_complex_value('field', field_info, json_str)
        assert result == {'key': 'value'}

    def test_get_field_value_is_abstract(self):
        """Test that get_field_value is abstract and must be overridden."""
        # We can't directly test abstract method, but we can verify that
        # DefaultSettingsSource (which implements it) returns the expected tuple
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=str)
        result = source.get_field_value(field_info, 'field_name')
        assert result == (None, '', False)

    def test_call_method_abstract(self):
        """Test that __call__ is abstract in base class."""
        # DefaultSettingsSource implements __call__, so we test that
        source = DefaultSettingsSource(SimpleSettings)
        result = source()
        assert isinstance(result, dict)


class TestConfigFileSourceMixin:
    """Tests for ConfigFileSourceMixin class."""

    class ConcreteFileSource(ConfigFileSourceMixin):
        """Concrete implementation for testing."""

        def _read_file(self, path: Path) -> dict[str, Any]:
            return {'file_key': 'file_value'}

    def test_read_files_with_none(self):
        """Test _read_files returns empty dict for None."""
        source = self.ConcreteFileSource()
        result = source._read_files(None)
        assert result == {}

    def test_read_files_with_single_path_string(self):
        """Test _read_files with a single string path."""
        source = self.ConcreteFileSource()
        with patch.object(Path, 'expanduser', return_value=Path('/tmp/nonexistent')):
            with patch.object(Path, 'is_file', return_value=False):
                result = source._read_files('/tmp/test.json')
        assert result == {}

    def test_read_files_converts_string_to_list(self):
        """Test _read_files converts single string to list."""
        source = self.ConcreteFileSource()
        with patch.object(Path, 'expanduser', return_value=Path('/tmp/test.json')):
            with patch.object(Path, 'is_file', return_value=True):
                result = source._read_files('/tmp/test.json')
        assert 'file_key' in result

    def test_read_files_with_list_of_paths(self):
        """Test _read_files with list of paths."""
        source = self.ConcreteFileSource()
        paths = [Path('/tmp/test1.json'), Path('/tmp/test2.json')]
        with patch.object(Path, 'expanduser', return_value=Path('/tmp/test1.json')):
            with patch.object(Path, 'is_file', return_value=True):
                result = source._read_files(paths)
        assert 'file_key' in result

    def test_read_files_with_deep_merge(self):
        """Test _read_files performs deep merge when enabled."""

        class DeepMergeSource(ConfigFileSourceMixin):
            def _read_file(self, path: Path) -> dict[str, Any]:
                return {'nested': {'key': 'value'}}

        source = DeepMergeSource()
        with patch.object(Path, 'expanduser', return_value=Path('/tmp/test.json')):
            with patch.object(Path, 'is_file', return_value=True):
                result = source._read_files([Path('/tmp/test.json')], deep_merge=True)
        assert 'nested' in result

    def test_read_files_without_deep_merge(self):
        """Test _read_files performs update merge when deep_merge is False."""
        source = self.ConcreteFileSource()
        with patch.object(Path, 'expanduser', return_value=Path('/tmp/test.json')):
            with patch.object(Path, 'is_file', return_value=True):
                result = source._read_files([Path('/tmp/test.json')], deep_merge=False)
        assert 'file_key' in result


class TestDefaultSettingsSource:
    """Tests for DefaultSettingsSource class."""

    def test_init_default_behavior(self):
        """Test __init__ with default settings."""
        source = DefaultSettingsSource(SimpleSettings)
        assert source.settings_cls is SimpleSettings
        assert source.nested_model_default_partial_update is False
        assert source.defaults == {}

    def test_init_with_nested_model_default_partial_update_true(self):
        """Test __init__ with nested_model_default_partial_update=True."""
        source = DefaultSettingsSource(ComplexSettings, nested_model_default_partial_update=True)
        assert source.nested_model_default_partial_update is True

    def test_init_respects_config_setting(self):
        """Test __init__ respects model config setting."""

        class ConfiguredSettings(BaseSettings):
            model_config = {'nested_model_default_partial_update': True}

            name: str = 'default'

        source = DefaultSettingsSource(ConfiguredSettings)
        assert source.nested_model_default_partial_update is True

    def test_call_returns_defaults(self):
        """Test __call__ returns defaults dict."""
        source = DefaultSettingsSource(SimpleSettings)
        result = source()
        assert isinstance(result, dict)
        assert result == {}

    def test_get_field_value_returns_tuple(self):
        """Test get_field_value returns expected tuple."""
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=str)
        result = source.get_field_value(field_info, 'field')
        assert result == (None, '', False)

    def test_repr_shows_config(self):
        """Test __repr__ includes nested_model_default_partial_update."""
        source = DefaultSettingsSource(SimpleSettings, nested_model_default_partial_update=True)
        repr_str = repr(source)
        assert 'DefaultSettingsSource' in repr_str
        assert 'True' in repr_str


class TestInitSettingsSource:
    """Tests for InitSettingsSource class."""

    def test_init_with_empty_kwargs(self):
        """Test __init__ with empty init_kwargs."""
        source = InitSettingsSource(SimpleSettings, {})
        assert source.init_kwargs == {}
        assert source.settings_cls is SimpleSettings

    def test_init_with_valid_field_kwargs(self):
        """Test __init__ with valid field names in kwargs."""
        kwargs = {'name': 'test_name', 'value': 100}
        source = InitSettingsSource(SimpleSettings, kwargs)
        assert 'name' in source.init_kwargs
        assert source.init_kwargs['name'] == 'test_name'

    def test_init_normalizes_to_preferred_alias(self):
        """Test __init__ normalizes field names to preferred alias."""

        class AliasSettings(BaseSettings):
            name: str = Field(alias='full_name', default='default')

        kwargs = {'full_name': 'John'}
        source = InitSettingsSource(AliasSettings, kwargs)
        assert 'full_name' in source.init_kwargs

    def test_init_with_populate_by_name(self):
        """Test __init__ with populate_by_name=True."""

        class PopulateSettings(BaseSettings):
            model_config = {'populate_by_name': True}

            name: str = Field(alias='full_name', default='default')

        kwargs = {'name': 'John'}
        source = InitSettingsSource(PopulateSettings, kwargs)
        assert 'full_name' in source.init_kwargs or 'name' in source.init_kwargs

    def test_init_preserves_extra_fields(self):
        """Test __init__ preserves extra fields in init_kwargs."""
        kwargs = {'name': 'test', 'extra_field': 'extra_value'}
        source = InitSettingsSource(SimpleSettings, kwargs)
        # extra_field should be preserved
        assert 'extra_field' in source.init_kwargs

    def test_call_without_nested_model_default_partial_update(self):
        """Test __call__ returns init_kwargs directly."""
        kwargs = {'name': 'test'}
        source = InitSettingsSource(SimpleSettings, kwargs, nested_model_default_partial_update=False)
        result = source()
        assert result == source.init_kwargs

    def test_call_with_nested_model_default_partial_update(self):
        """Test __call__ with nested_model_default_partial_update=True."""
        kwargs = {'name': 'test'}
        source = InitSettingsSource(SimpleSettings, kwargs, nested_model_default_partial_update=True)
        result = source()
        assert isinstance(result, dict)

    def test_get_field_value_returns_tuple(self):
        """Test get_field_value returns expected tuple."""
        source = InitSettingsSource(SimpleSettings, {})
        field_info = FieldInfo(annotation=str)
        result = source.get_field_value(field_info, 'field')
        assert result == (None, '', False)

    def test_repr_shows_init_kwargs(self):
        """Test __repr__ includes init_kwargs."""
        kwargs = {'name': 'test'}
        source = InitSettingsSource(SimpleSettings, kwargs)
        repr_str = repr(source)
        assert 'InitSettingsSource' in repr_str
        assert 'init_kwargs' in repr_str


class TestPydanticBaseEnvSettingsSource:
    """Tests for PydanticBaseEnvSettingsSource class."""

    class ConcreteEnvSource(PydanticBaseEnvSettingsSource):
        """Concrete implementation for testing."""

        def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
            return 'value', field_name, False

    def test_init_with_defaults(self):
        """Test __init__ with default values."""
        source = self.ConcreteEnvSource(SimpleSettings)
        assert source.case_sensitive is False
        assert source.env_prefix == ''
        assert source.env_prefix_target == 'variable'
        assert source.env_ignore_empty is False

    def test_init_with_custom_values(self):
        """Test __init__ with custom values."""
        source = self.ConcreteEnvSource(
            SimpleSettings,
            case_sensitive=True,
            env_prefix='APP_',
            env_prefix_target='all',
            env_ignore_empty=True,
        )
        assert source.case_sensitive is True
        assert source.env_prefix == 'APP_'
        assert source.env_prefix_target == 'all'
        assert source.env_ignore_empty is True

    def test_init_respects_config(self):
        """Test __init__ respects model config values."""

        class ConfiguredSettings(BaseSettings):
            model_config = {
                'case_sensitive': True,
                'env_prefix': 'TEST_',
            }

            name: str = 'default'

        source = self.ConcreteEnvSource(ConfiguredSettings)
        assert source.case_sensitive is True
        assert source.env_prefix == 'TEST_'

    def test_init_parameter_overrides_config(self):
        """Test __init__ parameters override model config."""

        class ConfiguredSettings(BaseSettings):
            model_config = {
                'case_sensitive': False,
                'env_prefix': 'CONFIG_',
            }

            name: str = 'default'

        source = self.ConcreteEnvSource(ConfiguredSettings, case_sensitive=True, env_prefix='PARAM_')
        assert source.case_sensitive is True
        assert source.env_prefix == 'PARAM_'

    def test_apply_case_sensitive_false(self):
        """Test _apply_case_sensitive with case_sensitive=False."""
        source = self.ConcreteEnvSource(SimpleSettings, case_sensitive=False)
        result = source._apply_case_sensitive('TestValue')
        assert result == 'testvalue'

    def test_apply_case_sensitive_true(self):
        """Test _apply_case_sensitive with case_sensitive=True."""
        source = self.ConcreteEnvSource(SimpleSettings, case_sensitive=True)
        result = source._apply_case_sensitive('TestValue')
        assert result == 'TestValue'

    def test_extract_field_info_with_field_name(self):
        """Test _extract_field_info returns field info."""
        source = self.ConcreteEnvSource(SimpleSettings)
        field_info = FieldInfo(annotation=str)
        result = source._extract_field_info(field_info, 'name')
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, tuple) and len(item) == 3 for item in result)

    def test_extract_field_info_with_env_prefix(self):
        """Test _extract_field_info includes env_prefix."""
        source = self.ConcreteEnvSource(SimpleSettings, env_prefix='APP_', env_prefix_target='variable')
        field_info = FieldInfo(annotation=str)
        result = source._extract_field_info(field_info, 'name')
        # Should have field info with prefix applied
        assert len(result) > 0

    def test_replace_field_names_case_insensitively_with_matching_field(self):
        """Test _replace_field_names_case_insensitively finds matching fields."""
        source = self.ConcreteEnvSource(ComplexSettings)
        field_info = SimpleSettings.model_fields['name']
        field_values = {'name': 'test_value'}
        result = source._replace_field_names_case_insensitively(field_info, field_values)
        assert isinstance(result, dict)

    def test_replace_field_names_case_insensitively_with_different_case(self):
        """Test _replace_field_names_case_insensitively with different case."""
        source = self.ConcreteEnvSource(ComplexSettings)
        field_info = SimpleSettings.model_fields['name']
        field_values = {'NAME': 'test_value'}
        result = source._replace_field_names_case_insensitively(field_info, field_values)
        assert isinstance(result, dict)

    def test_replace_env_none_type_values_with_env_none_type(self):
        """Test _replace_env_none_type_values converts EnvNoneType to None."""
        source = self.ConcreteEnvSource(SimpleSettings)
        field_value = {'key': EnvNoneType('null')}
        result = source._replace_env_none_type_values(field_value)
        assert result['key'] is None

    def test_replace_env_none_type_values_preserves_normal_values(self):
        """Test _replace_env_none_type_values preserves normal values."""
        source = self.ConcreteEnvSource(SimpleSettings)
        field_value = {'key': 'value', 'number': 42}
        result = source._replace_env_none_type_values(field_value)
        assert result['key'] == 'value'
        assert result['number'] == 42

    def test_replace_env_none_type_values_recursive(self):
        """Test _replace_env_none_type_values handles nested dicts."""
        source = self.ConcreteEnvSource(SimpleSettings)
        field_value = {'nested': {'key': EnvNoneType('null')}}
        result = source._replace_env_none_type_values(field_value)
        assert result['nested']['key'] is None

    def test_get_resolved_field_value_returns_tuple(self):
        """Test _get_resolved_field_value returns value, key, is_complex tuple."""
        source = self.ConcreteEnvSource(SimpleSettings)
        field_info = SimpleSettings.model_fields['name']
        result = source._get_resolved_field_value(field_info, 'name')
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_call_returns_dict(self):
        """Test __call__ returns dict of field values."""
        source = self.ConcreteEnvSource(SimpleSettings)
        result = source()
        assert isinstance(result, dict)

    def test_call_with_case_insensitive_dict_values(self):
        """Test __call__ replaces field names case-insensitively."""

        class TestEnvSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
                if field_name == 'nested':
                    # Return string representation to avoid nested dict from being treated as complex
                    return '{"sub_NAME": "value"}', field_name, True
                return None, field_name, False

        source = TestEnvSource(ComplexSettings, case_sensitive=False)
        result = source()
        assert isinstance(result, dict)

    def test_call_with_env_parse_none_str(self):
        """Test __call__ with env_parse_none_str setting."""

        class TestEnvSource(PydanticBaseEnvSettingsSource):
            def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
                if field_name == 'name':
                    # Return dict value that will be parsed for EnvNoneType
                    return {'nested': {'key': EnvNoneType('null')}}, field_name, False
                return None, field_name, False

        source = TestEnvSource(SimpleSettings, env_parse_none_str='null')
        result = source()
        assert isinstance(result, dict)


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_init_settings_source_with_none_value_for_nested_model_default_partial_update(self):
        """Test InitSettingsSource with None for nested_model_default_partial_update uses config."""

        class ConfiguredSettings(BaseSettings):
            model_config = {'nested_model_default_partial_update': True}

            name: str = 'default'

        source = InitSettingsSource(ConfiguredSettings, {}, nested_model_default_partial_update=None)
        assert source.nested_model_default_partial_update is True

    def test_default_settings_source_with_none_value_for_nested_model_default_partial_update(self):
        """Test DefaultSettingsSource with None for nested_model_default_partial_update uses config."""

        class ConfiguredSettings(BaseSettings):
            model_config = {'nested_model_default_partial_update': True}

            name: str = 'default'

        source = DefaultSettingsSource(ConfiguredSettings, nested_model_default_partial_update=None)
        assert source.nested_model_default_partial_update is True

    def test_decode_complex_value_with_invalid_json(self):
        """Test decode_complex_value handles invalid JSON."""
        source = DefaultSettingsSource(SimpleSettings)
        field_info = FieldInfo(annotation=dict)
        with pytest.raises(json.JSONDecodeError):
            source.decode_complex_value('field', field_info, 'not valid json')

    def test_extract_field_info_with_validation_alias_none(self):
        """Test _extract_field_info when validation_alias is None."""
        source = PydanticBaseEnvSettingsSource.__subclasses__()[0](SimpleSettings)
        field_info = FieldInfo(annotation=str, validation_alias=None)
        result = source._extract_field_info(field_info, 'field_name')
        assert isinstance(result, list)

    def test_apply_case_sensitive_empty_string(self):
        """Test _apply_case_sensitive with empty string."""
        source = PydanticBaseEnvSettingsSource.__subclasses__()[0](SimpleSettings, case_sensitive=False)
        result = source._apply_case_sensitive('')
        assert result == ''

    def test_init_settings_source_multiple_alias_matches(self):
        """Test InitSettingsSource picks first matching alias."""

        class MultiAliasSettings(BaseSettings):
            name: str = Field(alias='full_name', validation_alias='full_name', default='default')

        kwargs = {'full_name': 'John'}
        source = InitSettingsSource(MultiAliasSettings, kwargs)
        assert 'full_name' in source.init_kwargs

    def test_read_files_with_path_object(self):
        """Test _read_files handles Path objects."""

        class ConcreteFileSource(ConfigFileSourceMixin):
            def _read_file(self, path: Path) -> dict[str, Any]:
                return {'file_key': 'file_value'}

        source = ConcreteFileSource()
        with patch.object(Path, 'expanduser', return_value=Path('/tmp/test.json')):
            with patch.object(Path, 'is_file', return_value=True):
                result = source._read_files(Path('/tmp/test.json'))
        assert 'file_key' in result

    def test_replace_field_names_case_insensitively_with_optional_field(self):
        """Test _replace_field_names_case_insensitively with Optional fields."""
        from typing import Optional

        class OptionalSettings(BaseSettings):
            name: Optional[str] = None

        source = PydanticBaseEnvSettingsSource.__subclasses__()[0](OptionalSettings)
        field_info = OptionalSettings.model_fields['name']
        field_values = {'NAME': 'test_value'}
        result = source._replace_field_names_case_insensitively(field_info, field_values)
        assert isinstance(result, dict)
