import pytest
from pathlib import Path

from pydantic_settings.utils import path_type_label, _lenient_issubclass


class TestPathTypeLabel:
    def test_directory(self, tmp_path):
        assert path_type_label(tmp_path) == 'directory'

    def test_file(self, tmp_path):
        f = tmp_path / 'test.txt'
        f.write_text('hello')
        assert path_type_label(f) == 'file'

    def test_nonexistent_path_raises(self, tmp_path):
        nonexistent = tmp_path / 'nonexistent'
        with pytest.raises(AssertionError, match='path does not exist'):
            path_type_label(nonexistent)


class TestLenientIssubclass:
    def test_returns_true_for_subclass(self):
        assert _lenient_issubclass(int, object) is True

    def test_returns_true_for_exact_match(self):
        assert _lenient_issubclass(str, str) is True

    def test_returns_false_for_non_subclass(self):
        assert _lenient_issubclass(int, str) is False

    def test_returns_false_for_non_type(self):
        assert _lenient_issubclass('hello', str) is False

    def test_returns_false_for_generic_alias(self):
        # list[int] is a generic alias; get_origin returns list (not None)
        assert _lenient_issubclass(list[int], list) is False

    def test_returns_true_with_tuple_of_classes(self):
        assert _lenient_issubclass(bool, (int, str)) is True

    def test_raises_type_error_for_invalid_second_arg(self):
        # isinstance(int, type) is True, issubclass(int, 42) raises TypeError,
        # get_origin(int) is None so the TypeError is re-raised
        with pytest.raises(TypeError):
            _lenient_issubclass(int, 42)
