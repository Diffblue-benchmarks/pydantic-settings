"""Tests for YamlConfigSettingsSource."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource, import_yaml


# ---------- Helpers ----------


class SimpleSettings(BaseSettings):
    model_config = {'yaml_file': None}

    name: str = 'default'
    value: int = 0


class SettingsWithYamlConfig(BaseSettings):
    model_config = {'yaml_file': None, 'yaml_file_encoding': 'utf-8', 'yaml_config_section': None}

    name: str = 'default'
    value: int = 0


def _write_yaml(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding='utf-8')
    return p


# ---------- import_yaml ----------


def test_import_yaml_succeeds():
    # yaml should be importable in the test environment
    import_yaml()
    import pydantic_settings.sources.providers.yaml as yaml_module
    assert yaml_module.yaml is not None


def test_import_yaml_idempotent():
    import_yaml()
    import_yaml()  # calling a second time should not raise
    import pydantic_settings.sources.providers.yaml as yaml_module
    assert yaml_module.yaml is not None


def test_import_yaml_raises_when_not_installed(mocker):
    import pydantic_settings.sources.providers.yaml as yaml_module
    original = yaml_module.yaml
    yaml_module.yaml = None

    mocker.patch('builtins.__import__', side_effect=ImportError('No module named yaml'))

    with pytest.raises(ImportError, match='PyYAML is not installed'):
        import_yaml()

    yaml_module.yaml = original


# ---------- YamlConfigSettingsSource.__init__ ----------


def test_init_with_explicit_yaml_file(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', 'name: hello\nvalue: 42\n')

    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'
        value: int = 0

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
    assert source.yaml_file_path == yaml_file
    assert source.yaml_data == {'name': 'hello', 'value': 42}


def test_init_uses_model_config_yaml_file(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', 'name: fromconfig\n')

    class Settings(BaseSettings):
        model_config = {'yaml_file': str(yaml_file)}
        name: str = 'default'

    source = YamlConfigSettingsSource(Settings)
    assert source.yaml_data == {'name': 'fromconfig'}


def test_init_yaml_file_none_returns_empty(tmp_path):
    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    assert source.yaml_data == {}


def test_init_with_yaml_file_encoding(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('name: encoded\n', encoding='utf-8')

    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file, yaml_file_encoding='utf-8')
    assert source.yaml_file_encoding == 'utf-8'
    assert source.yaml_data == {'name': 'encoded'}


def test_init_encoding_from_model_config(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', 'name: enc\n')

    class Settings(BaseSettings):
        model_config = {'yaml_file_encoding': 'utf-8'}
        name: str = 'default'

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
    assert source.yaml_file_encoding == 'utf-8'


def test_init_with_yaml_config_section(tmp_path):
    content = 'app:\n  name: sectionval\n  value: 7\n'
    yaml_file = _write_yaml(tmp_path, 'config.yaml', content)

    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'
        value: int = 0

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file, yaml_config_section='app')
    assert source.yaml_data == {'name': 'sectionval', 'value': 7}


def test_init_yaml_config_section_from_model_config(tmp_path):
    content = 'myapp:\n  name: frommodel\n'
    yaml_file = _write_yaml(tmp_path, 'config.yaml', content)

    class Settings(BaseSettings):
        model_config = {'yaml_config_section': 'myapp'}
        name: str = 'default'

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
    assert source.yaml_data == {'name': 'frommodel'}


def test_init_with_deep_merge(tmp_path):
    file1 = _write_yaml(tmp_path, 'base.yaml', 'name: base\nvalue: 1\n')
    file2 = _write_yaml(tmp_path, 'override.yaml', 'value: 2\n')

    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'
        value: int = 0

    source = YamlConfigSettingsSource(Settings, yaml_file=[file1, file2], deep_merge=True)
    assert source.yaml_data == {'name': 'base', 'value': 2}


def test_init_nonexistent_file_returns_empty():
    class Settings(BaseSettings):
        model_config = {}
        name: str = 'default'

    source = YamlConfigSettingsSource(Settings, yaml_file='/nonexistent/path/config.yaml')
    assert source.yaml_data == {}


# ---------- YamlConfigSettingsSource._read_file ----------


def test_read_file_basic(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'test.yaml', 'key: value\nnumber: 123\n')

    class Settings(BaseSettings):
        model_config = {}
        key: str = ''
        number: int = 0

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    result = source._read_file(yaml_file)
    assert result == {'key': 'value', 'number': 123}


def test_read_file_empty_returns_empty_dict(tmp_path):
    yaml_file = tmp_path / 'empty.yaml'
    yaml_file.write_text('', encoding='utf-8')

    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    result = source._read_file(yaml_file)
    assert result == {}


def test_read_file_with_encoding(tmp_path):
    yaml_file = tmp_path / 'config.yaml'
    yaml_file.write_text('name: test\n', encoding='utf-8')

    class Settings(BaseSettings):
        model_config = {}
        name: str = ''

    source = YamlConfigSettingsSource(Settings, yaml_file=None, yaml_file_encoding='utf-8')
    result = source._read_file(yaml_file)
    assert result == {'name': 'test'}


# ---------- YamlConfigSettingsSource._traverse_nested_section ----------


def test_traverse_nested_section_simple_key(tmp_path):
    content = 'app:\n  name: hello\n'
    yaml_file = _write_yaml(tmp_path, 'config.yaml', content)

    class Settings(BaseSettings):
        model_config = {}
        name: str = ''

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    data = {'app': {'name': 'hello'}}
    result = source._traverse_nested_section(data, 'app')
    assert result == {'name': 'hello'}


def test_traverse_nested_section_dot_notation(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', '')

    class Settings(BaseSettings):
        model_config = {}
        name: str = ''

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    data = {'a': {'b': {'name': 'deep'}}}
    result = source._traverse_nested_section(data, 'a.b')
    assert result == {'name': 'deep'}


def test_traverse_nested_section_three_levels(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', '')

    class Settings(BaseSettings):
        model_config = {}
        name: str = ''

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    data = {'a': {'b': {'c': {'name': 'deep3'}}}}
    result = source._traverse_nested_section(data, 'a.b.c')
    assert result == {'name': 'deep3'}


def test_traverse_nested_section_literal_key_with_dot(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', '')

    class Settings(BaseSettings):
        model_config = {}
        name: str = ''

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    # Key contains a literal dot
    data = {'a.b': {'name': 'literal'}}
    result = source._traverse_nested_section(data, 'a.b')
    assert result == {'name': 'literal'}


def test_traverse_nested_section_empty_path_raises_value_error(tmp_path):
    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = tmp_path / 'config.yaml'
    with pytest.raises(ValueError, match='yaml_config_section cannot be empty'):
        source._traverse_nested_section({}, '')


def test_traverse_nested_section_key_not_found_raises_key_error(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', 'other: val\n')

    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    with pytest.raises(KeyError, match='yaml_config_section key'):
        source._traverse_nested_section({'other': 'val'}, 'missing')


def test_traverse_nested_section_intermediate_not_dict_raises_type_error(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', '')

    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    # 'a' exists but its value is not a dict
    data = {'a': 'not_a_dict'}
    with pytest.raises(TypeError, match='cannot be traversed'):
        source._traverse_nested_section(data, 'a.b')


def test_traverse_nested_section_dot_path_not_found_raises_key_error(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', '')

    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    data = {'x': {'y': 1}}
    with pytest.raises(KeyError):
        source._traverse_nested_section(data, 'a.b')


def test_traverse_nested_section_top_level_not_dict_raises_type_error(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', '')

    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    source.yaml_file_path = yaml_file
    # data is not a dict at all — passing a non-dict value should hit TypeError
    with pytest.raises(TypeError, match='cannot be traversed'):
        source._traverse_nested_section('not_a_dict', 'key')  # type: ignore[arg-type]


def test_traverse_via_init_with_nested_section(tmp_path):
    content = 'database:\n  host: localhost\n  port: 5432\n'
    yaml_file = _write_yaml(tmp_path, 'config.yaml', content)

    class Settings(BaseSettings):
        model_config = {}
        host: str = ''
        port: int = 0

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file, yaml_config_section='database')
    assert source.yaml_data == {'host': 'localhost', 'port': 5432}


# ---------- YamlConfigSettingsSource.__repr__ ----------


def test_repr_with_file_path(tmp_path):
    yaml_file = _write_yaml(tmp_path, 'config.yaml', 'name: x\n')

    class Settings(BaseSettings):
        model_config = {}
        name: str = ''

    source = YamlConfigSettingsSource(Settings, yaml_file=yaml_file)
    result = repr(source)
    assert result.startswith('YamlConfigSettingsSource(')
    assert 'yaml_file=' in result


def test_repr_with_none_yaml_file():
    class Settings(BaseSettings):
        model_config = {}

    source = YamlConfigSettingsSource(Settings, yaml_file=None)
    result = repr(source)
    assert result == 'YamlConfigSettingsSource(yaml_file=None)'
