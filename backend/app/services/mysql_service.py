"""MySQL 数据库服务（支持多数据源：mysql + maxcompute）"""
from __future__ import annotations

import mysql.connector
from mysql.connector import pooling
from typing import List, Optional, Dict, Any
from ..core.config import settings


class MySQLService:
    """MySQL 数据库服务单例（懒加载 + 多数据源）"""

    _instance: Optional["MySQLService"] = None
    _pools: Dict[str, pooling.MySQLConnectionPool] = {}
    _initialized_keys: set = set()

    # 数据源 key -> 配置前缀的映射
    _data_sources: Dict[str, Dict[str, Any]] = {
        "mysql": {
            "label": "mysql",
        },
        "pipeline": {
            "label": "pipeline (数仓层)",
        },
        "clickhouse": {
            "label": "clickhouse",
        },
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ----------- 连接池初始化 -----------

    def _ensure_pool(self, data_source: str):
        """确保某个数据源的连接池存在"""
        data_source = (data_source or "mysql").lower()

        # 只处理 MySQL 类数据源；clickhouse 由 clickhouse_service 处理
        if data_source not in ("mysql", "pipeline"):
            return

        if data_source in self._pools or data_source in self._initialized_keys:
            return

        self._initialized_keys.add(data_source)

        if data_source == "mysql":
            host = settings.MYSQL_HOST
            port = int(settings.MYSQL_PORT)
            user = settings.MYSQL_USER
            password = str(settings.MYSQL_PASSWORD) if settings.MYSQL_PASSWORD else None
            database = settings.MYSQL_DATABASE
            charset = settings.MYSQL_CHARSET
        else:  # pipeline（数仓层）
            host = settings.PIPELINE_HOST
            port = int(settings.PIPELINE_PORT)
            user = settings.PIPELINE_USER
            password = str(settings.PIPELINE_PASSWORD) if settings.PIPELINE_PASSWORD else None
            database = settings.PIPELINE_DATABASE
            charset = settings.PIPELINE_CHARSET

        if not host:
            print(f"[MySQLService] {data_source} 未配置 host，跳过连接池初始化")
            return

        try:
            self._pools[data_source] = pooling.MySQLConnectionPool(
                pool_name=f"{data_source}_pool",
                pool_size=5,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset=charset or "utf8mb4",
                autocommit=True,
                use_pure=True,
            )
            print(f"[MySQLService] {data_source} 连接池初始化成功")
        except mysql.connector.Error as e:
            print(f"[MySQLService] {data_source} 连接池初始化失败: {e}")

    def get_connection(self, data_source: str = "mysql"):
        """获取指定数据源的数据库连接"""
        data_source = (data_source or "mysql").lower()
        self._ensure_pool(data_source)

        pool = self._pools.get(data_source)
        if not pool:
            return None
        try:
            return pool.get_connection()
        except mysql.connector.Error as e:
            print(f"[MySQLService] 获取 {data_source} 连接失败: {e}")
            return None

    # ----------- 执行方法 -----------

    def execute_query(self, query: str, params: tuple = None, data_source: str = "mysql") -> List[Dict[str, Any]]:
        """执行查询语句，返回字典列表"""
        conn = self.get_connection(data_source)
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            return results
        except mysql.connector.Error as e:
            print(f"[MySQLService] 查询执行失败 (ds={data_source}): {e}")
            raise  # 重新抛出，让上层感知失败
        finally:
            conn.close()

    def execute_update(self, query: str, params: tuple = None, data_source: str = "mysql") -> int:
        """执行更新语句，返回影响的行数"""
        conn = self.get_connection(data_source)
        if not conn:
            raise Exception(f"无法连接数据源: {data_source}")

        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except mysql.connector.Error as e:
            print(f"[MySQLService] 更新执行失败 (ds={data_source}): {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            raise  # 重新抛出，让上层感知失败
        finally:
            conn.close()

    def execute_insert(self, query: str, params: tuple = None, data_source: str = "mysql") -> int:
        """执行插入语句，返回自增ID"""
        conn = self.get_connection(data_source)
        if not conn:
            raise Exception(f"无法连接数据源: {data_source}")

        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            inserted_id = cursor.lastrowid
            cursor.close()
            return inserted_id
        except mysql.connector.Error as e:
            print(f"[MySQLService] 插入执行失败 (ds={data_source}): {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            raise  # 重新抛出，让上层感知失败
        finally:
            conn.close()

    # 为保持向后兼容，提供一个 "以分号切分执行多条 SQL" 的 helper
    def execute_script(
        self,
        sql_content: str,
        data_source: str = "mysql",
        split_by_semicolon: bool = True,
    ) -> Dict[str, Any]:
        """执行多条 SQL 语句，返回 {total_affected, errors, statements}"""
        statements: List[str] = []

        if split_by_semicolon:
            buffer = []
            in_string = False
            escape_next = False
            for ch in sql_content:
                if escape_next:
                    buffer.append(ch)
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    buffer.append(ch)
                    continue
                if ch == "'":
                    in_string = not in_string
                    buffer.append(ch)
                    continue
                if ch == ";" and not in_string:
                    stmt = "".join(buffer).strip()
                    if stmt:
                        statements.append(stmt)
                    buffer = []
                    continue
                buffer.append(ch)

            tail = "".join(buffer).strip()
            if tail:
                statements.append(tail)
        else:
            statements = [sql_content.strip()]

        total_affected = 0
        errors: List[str] = []

        for i, stmt in enumerate(statements):
            try:
                affected = self.execute_update(stmt, data_source=data_source)
                total_affected += affected if affected else 0
            except Exception as e:  # noqa: BLE001
                errors.append(f"语句 #{i + 1} 执行失败: {e}")
                print(f"[MySQLService] 语句 #{i + 1} 执行失败: {e}")

        return {
            "total_affected": total_affected,
            "errors": errors,
            "statements": len(statements),
        }


    # ==================== 工作流表初始化 ====================

    def ensure_workflow_tables(self, data_source: str = "mysql") -> None:
        """确保工作流相关表存在（workflow_folders / workflow_scripts / workflow_logs）
        同时补齐可能缺失的字段（如 sql_content、data_source、bizdate 等）。
        """
        conn = self.get_connection(data_source)
        if not conn:
            print("[MySQLService] 无法连接 MySQL，跳过工作流表初始化")
            return

        try:
            cursor = conn.cursor()

            # 1) workflow_folders
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_folders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200) NOT NULL COMMENT '目录名，如 DWD层 / DWS层',
                    parent_id INT DEFAULT NULL COMMENT '父目录ID（预留）',
                    sort_order INT DEFAULT 0 COMMENT '排序序号',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_name_parent (name, parent_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流目录表'
                """
            )

            # 2) workflow_scripts（含 sql_content、data_source）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_scripts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(200) NOT NULL COMMENT '脚本名称',
                    folder_id INT NOT NULL COMMENT '所属目录ID',
                    data_source VARCHAR(50) DEFAULT 'pipeline' COMMENT '数据源：mysql/pipeline/clickhouse',
                    sql_content TEXT COMMENT 'SQL 脚本内容（支持 ${bizdate} 变量）',
                    schedule_cron VARCHAR(100) DEFAULT NULL COMMENT '调度 Cron 表达式',
                    schedule_label VARCHAR(100) DEFAULT NULL COMMENT '调度周期标签',
                    status VARCHAR(20) DEFAULT 'idle' COMMENT '状态：idle/running/success/failed',
                    last_run_at DATETIME DEFAULT NULL COMMENT '上次运行时间',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_folder (folder_id),
                    KEY idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流脚本表'
                """
            )

            # 3) workflow_logs（含 data_source、bizdate）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    script_id INT NOT NULL COMMENT '脚本ID',
                    data_source VARCHAR(50) DEFAULT NULL COMMENT '执行时使用的数据源',
                    bizdate VARCHAR(20) DEFAULT NULL COMMENT '业务日期 YYYY-MM-DD',
                    status VARCHAR(20) NOT NULL COMMENT '执行状态：success/failed',
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME DEFAULT NULL,
                    duration_ms INT DEFAULT NULL COMMENT '执行耗时(毫秒)',
                    error_message TEXT COMMENT '错误信息',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_script (script_id),
                    KEY idx_status (status),
                    KEY idx_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流执行日志表'
                """
            )

            # --- 补齐缺失字段（防止老表缺少新增字段）---
            def _add_column_if_missing(table: str, column: str, definition: str):
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS cnt FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                      AND table_name = '{table}'
                      AND column_name = '{column}'
                    """
                )
                row = cursor.fetchone()
                if (row and row[0] == 0) or (isinstance(row, dict) and row.get("cnt") == 0):
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                        print(f"[MySQLService] 为 {table} 补齐字段 {column}")
                    except Exception as e:
                        print(f"[MySQLService] 补齐字段 {table}.{column} 失败: {e}")

            _add_column_if_missing(
                "workflow_scripts", "data_source",
                "VARCHAR(50) DEFAULT 'pipeline' COMMENT '数据源' AFTER folder_id",
            )
            _add_column_if_missing(
                "workflow_scripts", "sql_content",
                "TEXT COMMENT 'SQL 脚本内容' AFTER data_source",
            )
            _add_column_if_missing(
                "workflow_logs", "data_source",
                "VARCHAR(50) DEFAULT NULL COMMENT '执行时使用的数据源' AFTER script_id",
            )
            _add_column_if_missing(
                "workflow_logs", "bizdate",
                "VARCHAR(20) DEFAULT NULL COMMENT '业务日期 YYYY-MM-DD' AFTER data_source",
            )

            conn.commit()
            cursor.close()
            print("[MySQLService] 工作流表初始化完成")
        except Exception as e:
            print(f"[MySQLService] 工作流表初始化失败: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()


# 全局服务实例（懒加载）
mysql_service = MySQLService()
