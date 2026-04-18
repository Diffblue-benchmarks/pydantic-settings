"""Tests for pydantic_settings.sources.providers.yaml module."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.yaml import (
    YamlConfigSettingsSource,
    import_yaml,
)


# ── import_yaml ──────────────────────────────────────────────────────────


def test_import_yaml_success():
    """import_yaml should successfully import yaml without error."""
    import_yaml()
    # After calling, the module-level yaml should not be None
    from pydantic_settings.sources.providers import yaml as yaml_mod

    assert yaml_mod.yaml is not None


def test_import_yaml_noop_when_already_imported():
    """import_yaml should be a no-op when yaml is already imported."""
    import_yaml()
    import_yaml()  # second call should not raise


def test_import_yaml_raises_when_missing():
    """import_yaml should raise ImportError when pyyaml is not installed."""
    import pydantic_settings.sources.providers.yaml as yaml_mod

    original = yaml_mod.yaml
    try:
        yaml_mod.yaml = None
        with patch.dict('sys.modules', {'yaml': None}):
            with pytest.raises(ImportError, match='PyYAML is not installed'):
                import_yaml()
    finally:
        yaml_mod.yaml = original


# ── YamlConfigSettingsSource.__init__ ────────────────────────────────────


class SimpleYamlSettings(BaseSettings):
    model_config = {'yaml_file': None}
    name: str = 'default'
    value: int = 0


def test_init_with_yaml_file(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('name: hello\nvalue: 42\n')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file)
    assert source.yaml_file_path == yaml_file
    assert source.yaml_data == {'name': 'hello', 'value': 42}


def test_init_with_no_file():
    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=None)
    assert source.yaml_file_path is None
    assert source.yaml_data == {}


def test_init_uses_model_config_defaults():
    class SettingsWithYamlConfig(BaseSettings):
        model_config = {
            'yaml_file': None,
            'yaml_file_encoding': 'utf-8',
            'yaml_config_section': None,
        }
        x: str = ''

    source = YamlConfigSettingsSource(SettingsWithYamlConfig)
    assert source.yaml_file_encoding == 'utf-8'


def test_init_with_default_path_reads_model_config(tmp_path):
    yaml_file = tmp_path / 'app.yaml'
    yaml_file.write_text('x: fromconfig\n')

    class SettingsFromConfig(BaseSettings):
        model_config = {'yaml_file': yaml_file}
        x: str = ''

    source = YamlConfigSettingsSource(SettingsFromConfig)
    assert source.yaml_file_path == yaml_file
    assert source.yaml_data == {'x': 'fromconfig'}


def test_init_with_encoding(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('name: héllo\n', encoding='utf-8')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file, yaml_file_encoding='utf-8')
    assert source.yaml_file_encoding == 'utf-8'
    assert source.yaml_data['name'] == 'héllo'


def test_init_with_config_section(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('app:\n  name: sectioned\n  value: 99\n')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file, yaml_config_section='app')
    assert source.yaml_data == {'name': 'sectioned', 'value': 99}


def test_init_with_deep_merge(tmp_path):
    f1 = tmp_path / 'a.yaml'
    f1.write_text('name: first\nvalue: 1\n')
    f2 = tmp_path / 'b.yaml'
    f2.write_text('value: 2\n')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=[f1, f2], deep_merge=True)
    assert source.yaml_data == {'name': 'first', 'value': 2}


# ── YamlConfigSettingsSource._read_file ──────────────────────────────────


def test_read_file_returns_dict(tmp_path):
    yaml_file = tmp_path / 'test.yaml'
    yaml_file.write_text('key: value\n')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file)
    result = source._read_file(yaml_file)
    assert result == {'key': 'value'}


def test_read_file_returns_empty_dict_for_empty_file(tmp_path):
    yaml_file = tmp_path / 'empty.yaml'
    yaml_file.write_text('')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file)
    result = source._read_file(yaml_file)
    assert result == {}


# ── YamlConfigSettingsSource._traverse_nested_section ────────────────────


def _make_source_with_data(tmp_path, data):
    """Helper to create a YamlConfigSettingsSource with specific YAML data."""
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text(yaml.dump(data))
    return YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file)


def test_traverse_simple_key(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('app:\n  name: hello\n  value: 1\n')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file)
    result = source._traverse_nested_section({'app': {'name': 'hello'}}, 'app')
    assert result == {'name': 'hello'}


def test_traverse_dotted_path(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    data = {'a': {'b': {'c': 'deep'}}}
    result = source._traverse_nested_section(data, 'a.b.c')
    assert result == 'deep'


def test_traverse_literal_dot_key(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    data = {'a.b': {'c': 'found'}}
    result = source._traverse_nested_section(data, 'a.b.c')
    assert result == 'found'


def test_traverse_full_literal_key(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    data = {'a.b.c': 'literal'}
    result = source._traverse_nested_section(data, 'a.b.c')
    assert result == 'literal'


def test_traverse_empty_path_raises(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    with pytest.raises(ValueError, match='yaml_config_section cannot be empty'):
        source._traverse_nested_section({}, '')


def test_traverse_missing_key_raises(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    with pytest.raises(KeyError, match='not found'):
        source._traverse_nested_section({'other': 1}, 'missing')


def test_traverse_missing_dotted_key_raises(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    with pytest.raises(KeyError, match='not found'):
        source._traverse_nested_section({'a': {'x': 1}}, 'a.b.c')


def test_traverse_type_error_on_non_dict_intermediate(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    with pytest.raises(TypeError, match='not a dictionary'):
        source._traverse_nested_section({'a': 'string_not_dict'}, 'a.b')


def test_traverse_type_error_on_literal_key_non_dict(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    # data is not a dict, trigger the TypeError path on the first try
    with pytest.raises(TypeError, match='not a dictionary'):
        source._traverse_nested_section('not_a_dict', 'key')


def test_traverse_preserves_original_path_in_error(tmp_path):
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    with pytest.raises(KeyError, match='a.b.c.d'):
        source._traverse_nested_section({'a': {'b': {'x': 1}}}, 'a.b.c.d')


def test_traverse_greedy_prefix_matching(tmp_path):
    """Greedy matching should prefer longer prefix keys."""
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    data = {'a': {'b.c': 'greedy'}, 'a.b': {'c': 'less_greedy'}}
    # With greedy approach (longest prefix first), 'a.b' is tried before 'a'
    result = source._traverse_nested_section(data, 'a.b.c')
    assert result == 'less_greedy'


def test_traverse_original_path_none_defaults(tmp_path):
    """When original_path is None, it should default to section_path."""
    source = _make_source_with_data(tmp_path, {'name': 'x'})
    result = source._traverse_nested_section({'key': 'val'}, 'key', original_path=None)
    assert result == 'val'


# ── YamlConfigSettingsSource.__repr__ ────────────────────────────────────


def test_repr(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('name: test\n')

    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=yaml_file)
    assert repr(source) == f'YamlConfigSettingsSource(yaml_file={yaml_file})'


def test_repr_no_file():
    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=None)
    assert repr(source) == 'YamlConfigSettingsSource(yaml_file=None)'


# ── Integration: Full settings load from YAML ───────────────────────────


def test_full_settings_from_yaml(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('name: integrated\nvalue: 123\n')

    class MySettings(BaseSettings):
        model_config = {'yaml_file': yaml_file}
        name: str = ''
        value: int = 0

    source = YamlConfigSettingsSource(MySettings)
    assert source.yaml_data == {'name': 'integrated', 'value': 123}


def test_init_with_nonexistent_file(tmp_path):
    """Non-existent file should result in empty data (handled by _read_files)."""
    nonexistent = tmp_path / 'does_not_exist.yaml'
    source = YamlConfigSettingsSource(SimpleYamlSettings, yaml_file=nonexistent)
    assert source.yaml_data == {}
