"""Tests for YamlConfigSettingsSource."""

from pathlib import Path

import pytest

from pydantic_settings import BaseSettings
from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource, import_yaml


@pytest.fixture
def tmp_yaml_file(tmp_path):
    """Create a temporary YAML file with sample settings."""
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('app_name: test_app\ndebug: true\n')
    return yaml_file


@pytest.fixture
def tmp_yaml_file_encoded(tmp_path):
    """Create a temporary YAML file with UTF-8 encoded content."""
    yaml_file = tmp_path / 'settings_encoded.yaml'
    yaml_file.write_text('app_name: tëst_àpp\n', encoding='utf-8')
    return yaml_file


class SimpleSettings(BaseSettings):
    app_name: str = 'default'
    debug: bool = False


def test_import_yaml_success():
    import_yaml()
    import yaml

    assert yaml is not None


def test_import_yaml_idempotent():
    import_yaml()
    import_yaml()  # calling twice should not raise


def test_init_with_explicit_yaml_file(tmp_yaml_file):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=tmp_yaml_file)

    assert source.yaml_file_path == tmp_yaml_file
    assert source.yaml_file_encoding is None
    assert source.yaml_data == {'app_name': 'test_app', 'debug': True}


def test_init_with_encoding(tmp_yaml_file_encoded):
    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=tmp_yaml_file_encoded, yaml_file_encoding='utf-8'
    )

    assert source.yaml_file_encoding == 'utf-8'
    assert source.yaml_data == {'app_name': 'tëst_àpp'}


def test_init_with_default_path_uses_model_config(tmp_yaml_file):
    class SettingsWithYamlFile(BaseSettings):
        model_config = {'yaml_file': tmp_yaml_file, 'yaml_file_encoding': 'utf-8'}  # type: ignore[assignment]
        app_name: str = 'default'
        debug: bool = False

    source = YamlConfigSettingsSource(SettingsWithYamlFile)

    assert source.yaml_file_path == tmp_yaml_file
    assert source.yaml_file_encoding == 'utf-8'
    assert source.yaml_data == {'app_name': 'test_app', 'debug': True}


def test_init_with_no_file():
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)

    assert source.yaml_file_path is None
    assert source.yaml_data == {}


def test_init_with_nonexistent_file(tmp_path):
    nonexistent = tmp_path / 'nonexistent.yaml'
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=nonexistent)

    assert source.yaml_file_path == nonexistent
    assert source.yaml_data == {}


def test_init_with_deep_merge(tmp_path):
    file1 = tmp_path / 'a.yaml'
    file2 = tmp_path / 'b.yaml'
    file1.write_text('app_name: app1\ndebug: false\n')
    file2.write_text('app_name: app2\n')

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=[file1, file2], deep_merge=True
    )

    assert source.yaml_data == {'app_name': 'app2', 'debug': False}


def test_read_file(tmp_yaml_file):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=tmp_yaml_file)
    result = source._read_file(tmp_yaml_file)

    assert result == {'app_name': 'test_app', 'debug': True}


def test_read_file_empty(tmp_path):
    empty_file = tmp_path / 'empty.yaml'
    empty_file.write_text('')
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=empty_file)
    result = source._read_file(empty_file)

    assert result == {}


def test_repr_with_file(tmp_yaml_file):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=tmp_yaml_file)

    assert repr(source) == f'YamlConfigSettingsSource(yaml_file={tmp_yaml_file})'


def test_repr_with_none():
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)

    assert repr(source) == 'YamlConfigSettingsSource(yaml_file=None)'


def test_init_encoding_from_model_config(tmp_yaml_file_encoded):
    class SettingsWithEncoding(BaseSettings):
        model_config = {'yaml_file_encoding': 'utf-8'}  # type: ignore[assignment]
        app_name: str = 'default'

    source = YamlConfigSettingsSource(
        SettingsWithEncoding, yaml_file=tmp_yaml_file_encoded
    )

    assert source.yaml_file_encoding == 'utf-8'
    assert source.yaml_data == {'app_name': 'tëst_àpp'}


def test_init_config_section(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('section:\n  app_name: from_section\n  debug: true\n')

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=yaml_file, yaml_config_section='section'
    )

    assert source.yaml_data == {'app_name': 'from_section', 'debug': True}


def test_init_config_section_from_model_config(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('section:\n  app_name: from_section\n')

    class SettingsWithSection(BaseSettings):
        model_config = {'yaml_config_section': 'section'}  # type: ignore[assignment]
        app_name: str = 'default'

    source = YamlConfigSettingsSource(SettingsWithSection, yaml_file=yaml_file)

    assert source.yaml_data == {'app_name': 'from_section'}


def test_traverse_nested_section_dot_notation(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('level1:\n  level2:\n    app_name: nested_value\n')

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=yaml_file, yaml_config_section='level1.level2'
    )

    assert source.yaml_data == {'app_name': 'nested_value'}


def test_traverse_nested_section_literal_dot_key(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('"a.b":\n  app_name: literal_dot\n')

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=yaml_file, yaml_config_section='a.b'
    )

    assert source.yaml_data == {'app_name': 'literal_dot'}


def test_traverse_nested_section_key_not_found(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('other:\n  app_name: value\n')

    with pytest.raises(KeyError, match='yaml_config_section key'):
        YamlConfigSettingsSource(
            SimpleSettings, yaml_file=yaml_file, yaml_config_section='missing'
        )


def test_traverse_nested_section_empty_path(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('app_name: value\n')

    with pytest.raises(ValueError, match='yaml_config_section cannot be empty'):
        YamlConfigSettingsSource(
            SimpleSettings, yaml_file=yaml_file, yaml_config_section=''
        )


def test_traverse_nested_section_intermediate_not_dict(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('level1: not_a_dict\n')

    with pytest.raises(TypeError, match='cannot be traversed'):
        YamlConfigSettingsSource(
            SimpleSettings, yaml_file=yaml_file, yaml_config_section='level1.level2'
        )


def test_traverse_nested_section_dotted_key_not_found(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('a:\n  b:\n    app_name: value\n')

    with pytest.raises(KeyError, match='yaml_config_section key'):
        YamlConfigSettingsSource(
            SimpleSettings, yaml_file=yaml_file, yaml_config_section='a.c'
        )


def test_traverse_nested_section_greedy_prefix_match(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('"a.b":\n  c:\n    app_name: greedy_match\n')

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=yaml_file, yaml_config_section='a.b.c'
    )

    assert source.yaml_data == {'app_name': 'greedy_match'}


def test_traverse_nested_section_three_levels(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('a:\n  b:\n    c:\n      app_name: deep\n')

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=yaml_file, yaml_config_section='a.b.c'
    )

    assert source.yaml_data == {'app_name': 'deep'}


def test_traverse_nested_intermediate_type_error_in_recursive_call(tmp_path):
    yaml_file = tmp_path / 'settings.yaml'
    yaml_file.write_text('"a.b": not_a_dict\n')

    with pytest.raises(TypeError, match='cannot be traversed'):
        YamlConfigSettingsSource(
            SimpleSettings, yaml_file=yaml_file, yaml_config_section='a.b.c'
        )
