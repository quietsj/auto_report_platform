from pydantic_settings import BaseSettings
from typing import Optional, List, Dict
import yaml
import os


def load_yaml_config(filename: str):
    """加载指定的 YAML 配置文件"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "config", filename
    )
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _resolve_env_value(value):
    """解析 os.environ/XXX 格式的环境变量引用"""
    if isinstance(value, str) and value.startswith("os.environ/"):
        env_key = value[len("os.environ/"):]
        return os.environ.get(env_key, "")
    return value


class Settings(BaseSettings):
    """全局配置，所有值从 config 目录的 yaml 文件加载"""

    # === 应用基础配置 ===
    APP_NAME: str = ""
    APP_VERSION: str = ""
    DEBUG: bool = True

    # === LiteLLM ===
    LITELLM_API_BASE: str = ""
    LITELLM_MASTER_KEY: str = ""
    LITELLM_MODEL_LIST: List[Dict] = []

    # === Embedding 服务 ===
    EMBEDDING_SERVICE_URL: str = ""

    # === Chroma 向量数据库 ===
    CHROMA_HOST: str = ""
    CHROMA_PORT: int = 0
    CHROMA_PERSIST_DIR: str = ""

    # === DataWorks ===
    DATAWORKS_REGION: str = ""
    DATAWORKS_ACCESS_KEY_ID: str = ""
    DATAWORKS_ACCESS_KEY_SECRET: str = ""
    DATAWORKS_PROJECT_ID: str = ""

    # === ClickHouse ===
    CLICKHOUSE_HOST: str = ""
    CLICKHOUSE_PORT: int = 0
    CLICKHOUSE_USER: str = ""
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_DATABASE: str = ""

    # === MySQL ===
    MYSQL_HOST: str = ""
    MYSQL_PORT: int = 0
    MYSQL_USER: str = ""
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = ""
    MYSQL_CHARSET: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_all_configs()

    def _load_all_configs(self):
        """从 config 目录的各 yaml 文件加载配置"""

        # --- local.yaml (包含基础配置、chroma、embedding、mysql) ---
        local = load_yaml_config("local.yaml")
        app_cfg = local.get("app", {})
        self.APP_NAME = app_cfg.get("name", "")
        self.APP_VERSION = app_cfg.get("version", "")
        self.DEBUG = app_cfg.get("debug", True)

        chroma_cfg = local.get("chroma", {})
        self.CHROMA_HOST = chroma_cfg.get("host", "")
        self.CHROMA_PORT = int(chroma_cfg.get("port", 0) or 0)
        self.CHROMA_PERSIST_DIR = chroma_cfg.get("persist_dir", "")

        emb_cfg = local.get("embedding", {})
        self.EMBEDDING_SERVICE_URL = emb_cfg.get("url", "")

        mysql_cfg = local.get("mysql", {})
        self.MYSQL_HOST = mysql_cfg.get("host", "")
        self.MYSQL_PORT = int(mysql_cfg.get("port", 0) or 0)
        self.MYSQL_USER = mysql_cfg.get("user", "")
        self.MYSQL_PASSWORD = mysql_cfg.get("password", "") or ""
        self.MYSQL_DATABASE = mysql_cfg.get("database", "")
        self.MYSQL_CHARSET = mysql_cfg.get("charset", "")

        # --- clickhouse-config.yaml ---
        ch = load_yaml_config("clickhouse-config.yaml")
        self.CLICKHOUSE_HOST = ch.get("host", "")
        self.CLICKHOUSE_PORT = int(ch.get("port", 0) or 0)
        self.CLICKHOUSE_USER = ch.get("user", "")
        self.CLICKHOUSE_PASSWORD = ch.get("password", "") or ""
        self.CLICKHOUSE_DATABASE = ch.get("database", "")

        # --- dataworks-config.yaml ---
        dw = load_yaml_config("dataworks-config.yaml")
        self.DATAWORKS_REGION = dw.get("region", "")
        self.DATAWORKS_ACCESS_KEY_ID = _resolve_env_value(dw.get("access_key_id", ""))
        self.DATAWORKS_ACCESS_KEY_SECRET = _resolve_env_value(dw.get("access_key_secret", ""))
        self.DATAWORKS_PROJECT_ID = str(dw.get("project_id", "") or "")

        # --- litellm-config.yaml ---
        llm = load_yaml_config("litellm-config.yaml")
        general = llm.get("general_settings", {})
        self.LITELLM_MASTER_KEY = _resolve_env_value(general.get("master_key", ""))
        self.LITELLM_API_BASE = llm.get("api_base", general.get("api_base", "") or "")
        self.LITELLM_MODEL_LIST = []
        for model in llm.get("model_list", []):
            params = model.get("litellm_params", {})
            # 解析环境变量中的 api_key
            params["api_key"] = _resolve_env_value(params.get("api_key", ""))
            model["litellm_params"] = params
            self.LITELLM_MODEL_LIST.append(model)


settings = Settings()
