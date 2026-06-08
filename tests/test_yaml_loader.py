# -*- coding: utf-8 -*-
"""
YAML 加载器测试

覆盖：文件读写、字符串解析、多文件合并。
"""

import pytest
from pathlib import Path
from app.shared.yaml_loader import (
    read_yaml_file,
    read_yaml_string,
    read_yaml_files,
    read_yaml_multi_document,
    write_yaml_file,
    dump_yaml_string,
    merge_yaml_files,
    _deep_merge,
)


# =============================================================================
# read_yaml_file
# =============================================================================

class TestReadYamlFile:
    """测试 YAML 文件读取"""

    def test_read_valid_file(self, tmp_path):
        f = tmp_path / "test.yml"
        f.write_text("name: test\nvalue: 42", encoding="utf-8")
        data = read_yaml_file(f)
        assert data["name"] == "test"
        assert data["value"] == 42

    def test_read_empty_file(self, tmp_path):
        f = tmp_path / "empty.yml"
        f.write_text("", encoding="utf-8")
        data = read_yaml_file(f)
        assert data is None

    def test_read_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_yaml_file(tmp_path / "nonexistent.yml")

    def test_read_chinese_content(self, tmp_path):
        f = tmp_path / "cn.yml"
        f.write_text("greeting: 你好\nname: 测试", encoding="utf-8")
        data = read_yaml_file(f)
        assert data["greeting"] == "你好"

    def test_read_nested_structure(self, tmp_path):
        f = tmp_path / "nested.yml"
        f.write_text("outer:\n  inner: value\n  list:\n    - a\n    - b", encoding="utf-8")
        data = read_yaml_file(f)
        assert data["outer"]["inner"] == "value"
        assert data["outer"]["list"] == ["a", "b"]


# =============================================================================
# read_yaml_string
# =============================================================================

class TestReadYamlString:
    """测试 YAML 字符串解析"""

    def test_parse_valid_string(self):
        data = read_yaml_string("name: test\nvalue: 42")
        assert data["name"] == "test"
        assert data["value"] == 42

    def test_parse_empty_string(self):
        assert read_yaml_string("") is None

    def test_parse_none_string(self):
        # yaml.safe_load 不接受 None，这是预期行为
        with pytest.raises(Exception):
            read_yaml_string(None)


# =============================================================================
# read_yaml_files
# =============================================================================

class TestReadYamlFiles:
    """测试多文件读取"""

    def test_read_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.yml"
        f1.write_text("a: 1", encoding="utf-8")
        f2 = tmp_path / "b.yml"
        f2.write_text("b: 2", encoding="utf-8")
        results = read_yaml_files([f1, f2])
        assert len(results) == 2
        assert results[0]["a"] == 1
        assert results[1]["b"] == 2

    def test_read_with_empty_file(self, tmp_path):
        f1 = tmp_path / "a.yml"
        f1.write_text("a: 1", encoding="utf-8")
        f2 = tmp_path / "empty.yml"
        f2.write_text("", encoding="utf-8")
        results = read_yaml_files([f1, f2])
        assert len(results) == 1  # 空文件被过滤


# =============================================================================
# read_yaml_multi_document
# =============================================================================

class TestReadYamlMultiDocument:
    """测试多文档 YAML"""

    def test_read_multi_doc(self, tmp_path):
        f = tmp_path / "multi.yml"
        f.write_text("doc: 1\n---\ndoc: 2", encoding="utf-8")
        docs = read_yaml_multi_document(f)
        assert len(docs) == 2
        assert docs[0]["doc"] == 1
        assert docs[1]["doc"] == 2


# =============================================================================
# write_yaml_file
# =============================================================================

class TestWriteYamlFile:
    """测试 YAML 文件写入"""

    def test_write_and_read(self, tmp_path):
        f = tmp_path / "out.yml"
        data = {"name": "test", "value": 42, "list": [1, 2, 3]}
        write_yaml_file(data, f)
        assert f.exists()
        restored = read_yaml_file(f)
        assert restored["name"] == "test"
        assert restored["value"] == 42

    def test_write_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "sub" / "dir" / "out.yml"
        write_yaml_file({"key": "val"}, f)
        assert f.exists()

    def test_write_chinese(self, tmp_path):
        f = tmp_path / "cn.yml"
        write_yaml_file({"greeting": "你好"}, f)
        restored = read_yaml_file(f)
        assert restored["greeting"] == "你好"


# =============================================================================
# dump_yaml_string
# =============================================================================

class TestDumpYamlString:
    """测试 YAML 字符串输出"""

    def test_dump(self):
        s = dump_yaml_string({"name": "test"})
        assert "name: test" in s

    def test_dump_unicode(self):
        s = dump_yaml_string({"greeting": "你好"})
        assert "你好" in s


# =============================================================================
# merge_yaml_files
# =============================================================================

class TestMergeYamlFiles:
    """测试多文件合并"""

    def test_merge(self, tmp_path):
        f1 = tmp_path / "a.yml"
        f1.write_text("a: 1\nb: 2", encoding="utf-8")
        f2 = tmp_path / "b.yml"
        f2.write_text("b: 3\nc: 4", encoding="utf-8")
        merged = merge_yaml_files([f1, f2])
        assert merged["a"] == 1
        assert merged["b"] == 3  # 后者覆盖
        assert merged["c"] == 4


# =============================================================================
# _deep_merge
# =============================================================================

class TestDeepMerge:
    """测试深度合并"""

    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_override_replaces_non_dict(self):
        base = {"x": [1, 2]}
        override = {"x": [3, 4]}
        result = _deep_merge(base, override)
        assert result["x"] == [3, 4]
