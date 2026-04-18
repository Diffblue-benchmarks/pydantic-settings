import sys
from pathlib import Path
from typing import get_origin
from unittest.mock import patch

import pytest

from pydantic_settings.utils import _lenient_issubclass, path_type_label


class TestPathTypeLabel:
    def test_returns_file_for_regular_file(self, tmp_path):
        f = tmp_path / 'test.txt'
        f.write_text('hello')
        assert path_type_label(f) == 'file'

    def test_returns_directory_for_dir(self, tmp_path):
        d = tmp_path / 'subdir'
        d.mkdir()
        assert path_type_label(d) == 'directory'

    def test_returns_fifo_for_named_pipe(self, tmp_path):
        import os

        fifo = tmp_path / 'pipe'
        os.mkfifo(fifo)
        assert path_type_label(fifo) == 'FIFO'

    def test_raises_assertion_for_nonexistent_path(self, tmp_path):
        p = tmp_path / 'nonexistent'
        with pytest.raises(AssertionError, match='path does not exist'):
            path_type_label(p)


class TestLenientIssubclass:
    def test_returns_true_for_regular_subclass(self):
        assert _lenient_issubclass(bool, int) is True

    def test_returns_true_for_same_class(self):
        assert _lenient_issubclass(int, int) is True

    def test_returns_false_for_non_subclass(self):
        assert _lenient_issubclass(str, int) is False

    def test_returns_false_for_non_type_instance(self):
        assert _lenient_issubclass('not_a_type', int) is False

    def test_returns_false_for_generic_alias(self):
        assert _lenient_issubclass(list[int], list) is False

    def test_returns_true_for_tuple_of_classes(self):
        assert _lenient_issubclass(bool, (int, str)) is True

    def test_returns_false_for_none(self):
        assert _lenient_issubclass(None, int) is False

    def test_reraises_type_error_for_non_generic_alias(self):
        with pytest.raises(TypeError):
            _lenient_issubclass(int, 123)
