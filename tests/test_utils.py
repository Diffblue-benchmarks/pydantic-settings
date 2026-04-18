from pathlib import Path
from typing import get_origin

import pytest

from pydantic_settings.utils import _lenient_issubclass, path_type_label


class TestPathTypeLabel:
    def test_file(self, tmp_path):
        f = tmp_path / 'test.txt'
        f.write_text('hello')
        assert path_type_label(f) == 'file'

    def test_directory(self, tmp_path):
        d = tmp_path / 'subdir'
        d.mkdir()
        assert path_type_label(d) == 'directory'

    def test_symlink_to_file_reports_file(self, tmp_path):
        # Symlinks to files match is_file first in the dict iteration order
        target = tmp_path / 'target.txt'
        target.write_text('hello')
        link = tmp_path / 'link.txt'
        link.symlink_to(target)
        assert path_type_label(link) == 'file'

    def test_symlink_to_dir_reports_directory(self, tmp_path):
        target = tmp_path / 'subdir'
        target.mkdir()
        link = tmp_path / 'link_dir'
        link.symlink_to(target)
        assert path_type_label(link) == 'directory'

    def test_fifo(self, tmp_path):
        import os

        fifo = tmp_path / 'test.fifo'
        os.mkfifo(fifo)
        assert path_type_label(fifo) == 'FIFO'

    def test_nonexistent_path_raises(self, tmp_path):
        p = tmp_path / 'nonexistent'
        with pytest.raises(AssertionError, match='path does not exist'):
            path_type_label(p)


class TestLenientIssubclass:
    def test_true_for_regular_subclass(self):
        assert _lenient_issubclass(bool, int) is True

    def test_true_for_same_class(self):
        assert _lenient_issubclass(int, int) is True

    def test_false_for_non_subclass(self):
        assert _lenient_issubclass(str, int) is False

    def test_false_for_non_type(self):
        assert _lenient_issubclass('not_a_type', int) is False

    def test_false_for_generic_alias(self):
        # list[int] is a generic alias; on Python 3.10 isinstance(list[int], type) is True
        # so this tests the TypeError + get_origin path
        assert _lenient_issubclass(list[int], str) is False

    def test_true_with_tuple_of_classes(self):
        assert _lenient_issubclass(bool, (int, str)) is True

    def test_false_with_tuple_of_classes(self):
        assert _lenient_issubclass(float, (int, str)) is False

    def test_raises_type_error_for_invalid_class_or_tuple(self):
        # When cls is a real type but class_or_tuple is invalid and cls has no origin
        with pytest.raises(TypeError):
            _lenient_issubclass(int, 123)
