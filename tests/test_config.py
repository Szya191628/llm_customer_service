# -*- coding: utf-8 -*-
"""
配置系统测试

覆盖：LLMConfig、EndpointsConfig、TrackerStoreConfig、环境变量解析。
"""

import os
import pytest
from app.shared.config import (
    LLMConfig,
    EmbeddingsConfig,
    TrackerStoreConfig,
    RetrievalConfig,
    NLGConfig,
    VectorStoreConfig,
    EndpointsConfig,
    _resolve_env_vars,
)
from app.shared.constants import LLM_TYPE_OPENAI, LLM_TYPE_QWEN


# =============================================================================
# 环境变量解析
# =============================================================================

class TestResolveEnvVars:
    """测试环境变量解析"""

    def test_resolve_existing_var(self, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "sk-12345")
        result = _resolve_env_vars("${TEST_API_KEY}")
        assert result == "sk-12345"

    def test_resolve_with_default(self):
        result = _resolve_env_vars("${NONEXISTENT_VAR:default_val}")
        assert result == "default_val"

    def test_resolve_missing_no_default(self):
        result = _resolve_env_vars("${TOTALLY_NONEXISTENT_VAR_XYZ}")
        assert result == ""

    def test_resolve_in_dict(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret")
        data = {"api_key": "${MY_KEY}", "model": "gpt-4"}
        resolved = _resolve_env_vars(data)
        assert resolved["api_key"] == "secret"
        assert resolved["model"] == "gpt-4"

    def test_resolve_in_list(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "val")
        data = ["${MY_VAR}", "static"]
        resolved = _resolve_env_vars(data)
        assert resolved == ["val", "static"]

    def test_non_string_passthrough(self):
        assert _resolve_env_vars(42) == 42
        assert _resolve_env_vars(True) is True
        assert _resolve_env_vars(None) is None


# =============================================================================
# LLMConfig
# =============================================================================

class TestLLMConfig:
    """测试 LLM 配置"""

    def test_default_values(self):
        config = LLMConfig()
        assert config.type == LLM_TYPE_OPENAI
        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.0

    def test_from_dict(self):
        data = {
            "type": "qwen",
            "model": "qwen-turbo",
            "api_key": "sk-test",
            "temperature": 0.5,
        }
        config = LLMConfig.from_dict(data)
        assert config.type == "qwen"
        assert config.model == "qwen-turbo"
        assert config.api_key == "sk-test"
        assert config.temperature == 0.5

    def test_from_dict_with_env_var(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "resolved-key")
        data = {"api_key": "${TEST_KEY}", "model": "gpt-4"}
        config = LLMConfig.from_dict(data)
        assert config.api_key == "resolved-key"

    def test_from_dict_extra_params(self):
        data = {"model": "gpt-4", "azure_endpoint": "https://xxx"}
        config = LLMConfig.from_dict(data)
        assert config.extra["azure_endpoint"] == "https://xxx"


# =============================================================================
# EmbeddingsConfig
# =============================================================================

class TestEmbeddingsConfig:
    """测试向量化配置"""

    def test_default_values(self):
        config = EmbeddingsConfig()
        assert config.model == "text-embedding-ada-002"

    def test_from_dict(self):
        data = {"model": "text-embedding-3-small", "dimensions": 512}
        config = EmbeddingsConfig.from_dict(data)
        assert config.model == "text-embedding-3-small"
        assert config.dimensions == 512


# =============================================================================
# TrackerStoreConfig
# =============================================================================

class TestTrackerStoreConfig:
    """测试 Tracker 存储配置"""

    def test_default_values(self):
        config = TrackerStoreConfig()
        assert config.type == "json"
        assert config.path == "trackers"

    def test_from_dict(self):
        data = {"type": "mysql", "host": "localhost", "port": 3306}
        config = TrackerStoreConfig.from_dict(data)
        assert config.type == "mysql"
        assert config.host == "localhost"
        assert config.port == 3306


# =============================================================================
# RetrievalConfig
# =============================================================================

class TestRetrievalConfig:
    """测试检索配置"""

    def test_default_values(self):
        config = RetrievalConfig()
        assert config.flow_retrieval_enabled is True
        assert config.knowledge_retrieval_enabled is False
        assert config.retriever_type == "faiss"

    def test_from_dict(self):
        data = {
            "flow_retrieval": {"enabled": False, "top_k": 10},
            "knowledge_retrieval": {"enabled": True, "top_k": 5},
        }
        config = RetrievalConfig.from_dict(data)
        assert config.flow_retrieval_enabled is False
        assert config.flow_retrieval_top_k == 10
        assert config.knowledge_retrieval_enabled is True

    def test_to_retriever_config(self):
        config = RetrievalConfig(retriever_type="faiss", embedding_dimension=768)
        rc = config.to_retriever_config()
        assert rc["type"] == "faiss"
        assert rc["embedding_dimension"] == 768


# =============================================================================
# NLGConfig
# =============================================================================

class TestNLGConfig:
    """测试 NLG 配置"""

    def test_default_values(self):
        config = NLGConfig()
        assert config.rephrase_enabled is False
        assert config.rephrase_style == "friendly"

    def test_from_dict(self):
        data = {
            "rephrase": {
                "enabled": True,
                "style": "professional",
                "threshold": 20,
            }
        }
        config = NLGConfig.from_dict(data)
        assert config.rephrase_enabled is True
        assert config.rephrase_style == "professional"
        assert config.rephrase_threshold == 20


# =============================================================================
# EndpointsConfig
# =============================================================================

class TestEndpointsConfig:
    """测试端点配置"""

    def test_default_values(self):
        config = EndpointsConfig()
        assert config.models == {}
        assert config.embeddings == {}

    def test_from_dict_with_models(self):
        data = {
            "models": {
                "default": {"type": "qwen", "model": "qwen-turbo", "api_key": "k1"},
                "gpt4": {"type": "openai", "model": "gpt-4", "api_key": "k2"},
            }
        }
        config = EndpointsConfig.from_dict(data)
        assert "default" in config.models
        assert "gpt4" in config.models
        assert config.models["default"].model == "qwen-turbo"

    def test_get_model_config(self):
        data = {
            "models": {
                "default": {"type": "qwen", "model": "qwen-turbo"},
            }
        }
        config = EndpointsConfig.from_dict(data)
        assert config.get_model_config("default") is not None
        assert config.get_model_config("nonexistent") is None

    def test_get_embeddings_config(self):
        data = {
            "embeddings": {
                "default": {"model": "text-embedding-3-small"},
            }
        }
        config = EndpointsConfig.from_dict(data)
        assert config.get_embeddings_config("default") is not None

    def test_from_dict_with_tracker_store(self):
        data = {"tracker_store": {"type": "memory"}}
        config = EndpointsConfig.from_dict(data)
        assert config.tracker_store.type == "memory"

    def test_from_dict_with_nlg(self):
        data = {"nlg": {"rephrase": {"enabled": True, "style": "casual"}}}
        config = EndpointsConfig.from_dict(data)
        assert config.nlg is not None
        assert config.nlg.rephrase_enabled is True

    def test_load_nonexistent_file(self, tmp_path):
        config = EndpointsConfig.load(tmp_path / "nonexistent.yml")
        assert config.models == {}  # 返回默认值


# =============================================================================
# VectorStoreConfig
# =============================================================================

class TestVectorStoreConfig:
    """测试向量存储配置"""

    def test_from_dict(self):
        data = {"uri": "bolt://localhost:7687", "user": "neo4j"}
        config = VectorStoreConfig.from_dict(data)
        assert config.config["uri"] == "bolt://localhost:7687"

    def test_to_connect_config(self):
        data = {"uri": "bolt://localhost:7687"}
        config = VectorStoreConfig.from_dict(data)
        cc = config.to_connect_config()
        assert cc == {"uri": "bolt://localhost:7687"}
        # 确保是副本
        cc["extra"] = "val"
        assert "extra" not in config.config
