"""Tests for YamlConfigSettingsSource."""

import pytest

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources.providers.yaml import YamlConfigSettingsSource


class SimpleSettings(BaseSettings):
    model_config = SettingsConfigDict(yaml_file=None)

    name: str = "default"
    value: int = 0


@pytest.fixture
def yaml_file(tmp_path):
    file = tmp_path / "settings.yaml"
    file.write_text("name: test_name\nvalue: 42\n")
    return file


@pytest.fixture
def yaml_file_utf8(tmp_path):
    file = tmp_path / "settings_utf8.yaml"
    file.write_text("name: héllo\n", encoding="utf-8")
    return file


def test_init_with_explicit_yaml_file(yaml_file):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=yaml_file)
    assert source.yaml_file_path == yaml_file
    assert source.yaml_data == {"name": "test_name", "value": 42}


def test_init_uses_model_config_yaml_file(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text("name: from_config\n")

    class ConfigSettings(BaseSettings):
        model_config = SettingsConfigDict(yaml_file=str(file))
        name: str = "default"

    source = YamlConfigSettingsSource(ConfigSettings)
    assert source.yaml_data.get("name") == "from_config"


def test_init_with_explicit_encoding(yaml_file_utf8):
    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=yaml_file_utf8, yaml_file_encoding="utf-8"
    )
    assert source.yaml_file_encoding == "utf-8"
    assert source.yaml_data["name"] == "héllo"


def test_init_uses_model_config_encoding(tmp_path):
    file = tmp_path / "settings_enc.yaml"
    file.write_text("name: héllo\n", encoding="utf-8")

    class EncodingSettings(BaseSettings):
        model_config = SettingsConfigDict(yaml_file=str(file), yaml_file_encoding="utf-8")
        name: str = "default"

    source = YamlConfigSettingsSource(EncodingSettings)
    assert source.yaml_file_encoding == "utf-8"
    assert source.yaml_data["name"] == "héllo"


def test_init_no_yaml_file():
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    assert source.yaml_file_path is None
    assert source.yaml_data == {}


def test_init_deep_merge(tmp_path):
    file1 = tmp_path / "s1.yaml"
    file2 = tmp_path / "s2.yaml"
    file1.write_text("name: first\nvalue: 1\n")
    file2.write_text("name: second\n")

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=[file1, file2], deep_merge=True
    )
    assert source.yaml_data["name"] == "second"
    assert source.yaml_data["value"] == 1


def test_init_with_yaml_config_section(tmp_path):
    file = tmp_path / "settings.yaml"
    file.write_text("section:\n  name: sectioned\n  value: 99\n")

    source = YamlConfigSettingsSource(
        SimpleSettings, yaml_file=file, yaml_config_section="section"
    )
    assert source.yaml_data == {"name": "sectioned", "value": 99}


def test_init_uses_model_config_yaml_config_section(tmp_path):
    file = tmp_path / "settings.yaml"
    file.write_text("app:\n  name: from_section\n")

    class SectionSettings(BaseSettings):
        model_config = SettingsConfigDict(yaml_file=str(file), yaml_config_section="app")
        name: str = "default"

    source = YamlConfigSettingsSource(SectionSettings)
    assert source.yaml_data.get("name") == "from_section"


def test_read_file(yaml_file):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_encoding = None
    result = source._read_file(yaml_file)
    assert result == {"name": "test_name", "value": 42}


def test_read_file_with_encoding(yaml_file_utf8):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_encoding = "utf-8"
    result = source._read_file(yaml_file_utf8)
    assert result["name"] == "héllo"


def test_read_file_empty(tmp_path):
    file = tmp_path / "empty.yaml"
    file.write_text("")
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_encoding = None
    result = source._read_file(file)
    assert result == {}


def test_traverse_nested_section_simple(yaml_file, tmp_path):
    file = tmp_path / "nested.yaml"
    file.write_text("section:\n  name: nested_name\n")
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    data = {"section": {"name": "nested_name"}}
    result = source._traverse_nested_section(data, "section")
    assert result == {"name": "nested_name"}


def test_traverse_nested_section_dot_notation(tmp_path):
    file = tmp_path / "nested.yaml"
    file.write_text("a:\n  b:\n    name: deep\n")
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    data = {"a": {"b": {"name": "deep"}}}
    result = source._traverse_nested_section(data, "a.b")
    assert result == {"name": "deep"}


def test_traverse_nested_section_literal_key_with_dot(tmp_path):
    file = tmp_path / "nested.yaml"
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    data = {"a.b": {"name": "literal"}}
    result = source._traverse_nested_section(data, "a.b")
    assert result == {"name": "literal"}


def test_traverse_nested_section_empty_raises(tmp_path):
    file = tmp_path / "settings.yaml"
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    with pytest.raises(ValueError, match="yaml_config_section cannot be empty"):
        source._traverse_nested_section({}, "")


def test_traverse_nested_section_key_not_found(tmp_path):
    file = tmp_path / "settings.yaml"
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    with pytest.raises(KeyError):
        source._traverse_nested_section({"other": {}}, "missing")


def test_traverse_nested_section_key_not_found_dot(tmp_path):
    file = tmp_path / "settings.yaml"
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    with pytest.raises(KeyError):
        source._traverse_nested_section({"other": {}}, "missing.key")


def test_traverse_nested_section_intermediate_not_dict(tmp_path):
    file = tmp_path / "settings.yaml"
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    data = {"a": "not_a_dict"}
    with pytest.raises(TypeError):
        source._traverse_nested_section(data, "a.b")


def test_traverse_nested_section_three_levels(tmp_path):
    file = tmp_path / "settings.yaml"
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    source.yaml_file_path = file
    data = {"a": {"b": {"c": {"name": "deep"}}}}
    result = source._traverse_nested_section(data, "a.b.c")
    assert result == {"name": "deep"}


def test_repr_with_file(yaml_file):
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=yaml_file)
    repr_str = repr(source)
    assert "YamlConfigSettingsSource" in repr_str
    assert "yaml_file=" in repr_str


def test_repr_without_file():
    source = YamlConfigSettingsSource(SimpleSettings, yaml_file=None)
    assert repr(source) == "YamlConfigSettingsSource(yaml_file=None)"
