"""Tests for CliSettingsSource.__init__ method - targeting uncovered lines."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from pydantic_settings import BaseSettings, CliSettingsSource, SettingsError


class TestCliSettingsSourceInitPrefix:
    """Tests for cli_prefix handling in __init__."""

    def test_valid_prefix_gets_dot_appended(self):
        """Test that a valid cli_prefix gets a dot appended (line 385)."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prefix='myprefix')
        assert source.cli_prefix == 'myprefix.'

    def test_valid_prefix_with_dot_separator(self):
        """Test that a valid prefix with internal dot separator works."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_prefix='my.prefix')
        assert source.cli_prefix == 'my.prefix.'


class TestCliSettingsSourceInitParseArgs:
    """Tests for cli_parse_args handling in __init__."""

    def test_cli_parse_args_true_uses_sys_argv(self):
        """Test that cli_parse_args=True uses sys.argv[1:] (lines 442-443)."""

        class Settings(BaseSettings):
            name: str = 'default'

        with patch.object(sys, 'argv', ['prog', '--name', 'from_argv']):
            source = CliSettingsSource(Settings, cli_parse_args=True)

        result = source()
        assert result.get('name') == 'from_argv'

    def test_cli_parse_args_list_parses_args(self):
        """Test that cli_parse_args with list parses arguments (line 448)."""

        class Settings(BaseSettings):
            name: str = 'default'
            count: int = 0

        source = CliSettingsSource(Settings, cli_parse_args=['--name', 'test', '--count', '42'])
        result = source()
        assert result.get('name') == 'test'
        assert result.get('count') == '42'

    def test_cli_parse_args_tuple_parses_args(self):
        """Test that cli_parse_args with tuple parses arguments."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_parse_args=('--name', 'tuple_value'))
        result = source()
        assert result.get('name') == 'tuple_value'

    def test_cli_parse_args_invalid_type_raises_error(self):
        """Test that cli_parse_args with invalid type raises SettingsError (lines 444-447)."""

        class Settings(BaseSettings):
            name: str = 'default'

        with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple of strings'):
            CliSettingsSource(Settings, cli_parse_args='invalid_string')

    def test_cli_parse_args_invalid_type_dict_raises_error(self):
        """Test that cli_parse_args with dict type raises SettingsError."""

        class Settings(BaseSettings):
            name: str = 'default'

        with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple of strings'):
            CliSettingsSource(Settings, cli_parse_args={'key': 'value'})

    def test_cli_parse_args_invalid_type_int_raises_error(self):
        """Test that cli_parse_args with int type raises SettingsError."""

        class Settings(BaseSettings):
            name: str = 'default'

        with pytest.raises(SettingsError, match='cli_parse_args must be a list or tuple of strings'):
            CliSettingsSource(Settings, cli_parse_args=123)

    def test_cli_parse_args_none_does_not_parse(self):
        """Test that cli_parse_args=None does not parse arguments."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_parse_args=None)
        result = source()
        assert result == {}

    def test_cli_parse_args_false_does_not_parse(self):
        """Test that cli_parse_args=False does not parse arguments."""

        class Settings(BaseSettings):
            name: str = 'default'

        source = CliSettingsSource(Settings, cli_parse_args=False)
        result = source()
        assert result == {}
