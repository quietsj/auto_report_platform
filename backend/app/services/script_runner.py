"""SQL 脚本运行器服务"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from .mysql_service import mysql_service
from .clickhouse_service import clickhouse_service


class ScriptRunner:
    """统一 SQL 脚本运行器，支持 MySQL / MaxCompute / ClickHouse"""

    def run(
        self,
        script_id: int,
        sql_content: str,
        script_type: str = "mysql",
        data_source: str = "mysql",
        bizdate: str = None,
    ) -> Dict[str, Any]:
        """
        执行 SQL 脚本

        Args:
            script_id: 脚本 ID
            sql_content: SQL 内容（若含多条语句则以分号分隔）
            script_type: "mysql" / "clickhouse"
            data_source: 执行数据源 key，与 mysql_service.get_connection(data_source) 对应
            bizdate: 业务日期（仅用于日志回显）

        Returns:
            {
                status: 'success' | 'failed',
                duration_ms: int,
                affected_rows: int,
                error_message: Optional[str],
                executed_statements: int,
                data_source: str,
                script_type: str,
            }
        """
        start_time = time.time()
        total_affected = 0
        errors: List[str] = []

        # 按分号拆分语句
        statements = self._split_statements(sql_content)
        print(
            f"[ScriptRunner] 开始执行 script_id={script_id}, "
            f"ds={data_source}, type={script_type}, bizdate={bizdate}, "
            f"语句数={len(statements)}"
        )

        for i, stmt in enumerate(statements):
            stmt = stmt.strip()
            if not stmt:
                continue

            try:
                if script_type == "clickhouse":
                    # 智能判断：是跨库同步脚本（MySQL -> ClickHouse）还是纯 ClickHouse SQL
                    if self._is_mysql_to_clickhouse_sync(stmt):
                        affected = self._run_mysql_to_clickhouse_sync(stmt, data_source)
                        total_affected += affected
                    else:
                        result = clickhouse_service.command(stmt)
                        if isinstance(result, int):
                            total_affected += result
                else:
                    # mysql / maxcompute 都走 mysql_service，通过 data_source 路由连接池
                    affected = mysql_service.execute_update(stmt, data_source=data_source)
                    total_affected += affected if affected else 0

                print(f"[ScriptRunner] 语句 #{i + 1} 执行成功: {stmt[:80]}...")

            except Exception as e:  # noqa: BLE001
                error_msg = str(e)
                errors.append(f"语句 #{i + 1} 失败: {error_msg}")
                print(f"[ScriptRunner] 语句 #{i + 1} 执行失败: {error_msg}")

        duration_ms = int((time.time() - start_time) * 1000)
        final_status = "success" if len(errors) == 0 else "failed"
        error_message = "; ".join(errors) if errors else None

        # 更新脚本状态和 last_run_at
        self._update_script_status(script_id, final_status)

        # 写入运行日志
        self._write_log(script_id, final_status, duration_ms, error_message, data_source, bizdate)

        return {
            "status": final_status,
            "duration_ms": duration_ms,
            "affected_rows": total_affected,
            "error_message": error_message,
            "executed_statements": len(statements),
            "data_source": data_source,
            "script_type": script_type,
        }

    def _split_statements(self, sql: str) -> List[str]:
        """按分号拆分 SQL 语句（不拆分字符串内部的分号）"""
        statements: List[str] = []
        buffer: List[str] = []
        in_string = False
        escape_next = False

        for ch in sql:
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

        return statements

    # ========== MySQL → ClickHouse 跨库同步支持 ==========

    def _is_mysql_to_clickhouse_sync(self, stmt: str) -> bool:
        """
        判断一条语句是否为 MySQL 到 ClickHouse 的跨库同步语句

        识别规则：
        - INSERT INTO report.xxx (...) SELECT ... FROM pipeline.yyy
        """
        stmt_upper = stmt.upper()
        if "INSERT INTO" not in stmt_upper:
            return False
        if "SELECT" not in stmt_upper:
            return False
        # 检查是否引用了 MySQL（pipeline）表
        if "PIPELINE." in stmt_upper:
            return True
        return False

    def _parse_sync_statement(self, stmt: str) -> Optional[Dict[str, Any]]:
        """
        解析 MySQL → ClickHouse 同步语句

        输入格式：
        INSERT INTO report.target_table (col1, col2, ...)
        SELECT col1, col2, ...
        FROM pipeline.source_table
        WHERE dt = '2024-01-15'

        返回：
        {
            "target_table": "report.target_table",
            "columns": ["col1", "col2", ...],
            "source_table": "pipeline.source_table",
            "where_clause": "dt = '2024-01-15'"  # 可能为空
        }
        """
        try:
            stmt_upper = stmt.upper()

            # 提取目标表和列名
            # INSERT INTO report.xxx (col1, col2, ...)
            insert_match_pos = stmt_upper.index("INSERT INTO")
            select_match_pos = stmt_upper.index("SELECT")

            # 提取目标表部分
            after_into = stmt[insert_match_pos + len("INSERT INTO"):select_match_pos].strip()
            # 去掉末尾的括号及其内容，得到表名
            paren_start = after_into.find("(")
            if paren_start == -1:
                return None
            target_table = after_into[:paren_start].strip()

            # 提取列名
            paren_end = after_into.rfind(")")
            if paren_end == -1 or paren_end <= paren_start:
                return None
            columns_str = after_into[paren_start + 1:paren_end].strip()
            columns = [c.strip() for c in columns_str.split(",") if c.strip()]

            # 提取源表
            from_pos = stmt_upper.find("FROM", select_match_pos)
            if from_pos == -1:
                return None

            # 找到 FROM 之后的表名和可选的 WHERE 子句
            after_from = stmt[from_pos + len("FROM"):].strip()
            # 查找 WHERE（大小写不敏感）
            where_pos_lower = after_from.lower().find("where")
            if where_pos_lower != -1:
                source_table = after_from[:where_pos_lower].strip()
                where_clause = after_from[where_pos_lower + len("where"):].strip()
            else:
                source_table = after_from.strip()
                where_clause = ""

            # 去掉末尾的分号
            source_table = source_table.rstrip(";").strip()

            return {
                "target_table": target_table,
                "columns": columns,
                "source_table": source_table,
                "where_clause": where_clause,
            }
        except Exception as e:
            print(f"[ScriptRunner] 解析同步语句失败: {e}")
            return None

    def _run_mysql_to_clickhouse_sync(self, stmt: str, data_source: str) -> int:
        """
        执行 MySQL → ClickHouse 跨库数据同步

        流程：
        1. 解析同步语句
        2. 从 MySQL 读取数据（SELECT columns FROM source_table WHERE ...）
        3. 写入 ClickHouse

        返回：同步的数据行数
        """
        parsed = self._parse_sync_statement(stmt)
        if not parsed:
            raise Exception(f"无法解析同步语句: {stmt[:120]}")

        target_table = parsed["target_table"]
        columns = parsed["columns"]
        source_table = parsed["source_table"]
        where_clause = parsed["where_clause"]

        print(f"[ScriptRunner] 同步: {source_table} -> {target_table}, columns={len(columns)}, where={where_clause or '无'}")

        # 1. 构建 MySQL SELECT 语句
        columns_str = ", ".join(columns)
        select_sql = f"SELECT {columns_str} FROM {source_table}"
        if where_clause:
            select_sql += f" WHERE {where_clause}"

        # 2. 从 MySQL 读取数据
        print(f"[ScriptRunner] 从 MySQL 读取数据: {select_sql[:80]}...")
        rows = mysql_service.execute_query(select_sql, data_source="pipeline")
        if not rows:
            print(f"[ScriptRunner] MySQL 源表为空，跳过同步")
            return 0

        print(f"[ScriptRunner] 从 MySQL 读取到 {len(rows)} 行数据")

        # 3. 转换为 tuple 列表，准备写入 ClickHouse
        data = [tuple(row[col] for col in columns) for row in rows]

        # 4. 写入 ClickHouse
        # 解析目标表，去掉 "report." 前缀（clickhouse_service.insert_data 会通过 database 参数指定数据库）
        ch_table = target_table
        if ch_table.startswith("report."):
            ch_table = ch_table[len("report."):]

        print(f"[ScriptRunner] 写入 ClickHouse: report.{ch_table}, {len(data)} 行")
        success = clickhouse_service.insert_data(ch_table, data, columns, database="report")

        if not success:
            raise Exception(f"写入 ClickHouse 失败: report.{ch_table}")

        print(f"[ScriptRunner] ClickHouse 同步完成: {len(data)} 行")
        return len(data)

    def detect_script_type(self, sql_content: str, folder_name: str = "") -> str:
        """
        自动检测脚本类型，决定用 clickhouse_service 还是 mysql_service 执行

        判断规则：
        1. 目录名含 "clickhouse"/"ch_" -> clickhouse
        2. SQL 含 "MergeTree" / "ReplacingMergeTree" / "PARTITION BY" -> clickhouse
        3. 其他默认 -> mysql
        """
        folder_lower = (folder_name or "").lower()
        if any(k in folder_lower for k in ("clickhouse", "ch_", "ads_ch", "clickhouse同步")):
            return "clickhouse"

        sql_upper = (sql_content or "").upper()
        if "MERGETREE" in sql_upper or "REPLACINGMERGETREE" in sql_upper or "PARTITION BY" in sql_upper:
            return "clickhouse"

        return "mysql"

    def _update_script_status(self, script_id: int, status: str, error_message: str = None):
        """更新脚本状态和上次运行时间"""
        query = """
            UPDATE workflow_scripts
            SET status = %s, last_run_at = NOW()
            WHERE id = %s
        """
        mysql_service.execute_update(query, (status, script_id))

    def _write_log(
        self,
        script_id: int,
        status: str,
        duration_ms: int,
        error_message: Optional[str],
        data_source: Optional[str] = None,
        bizdate: Optional[str] = None,
    ):
        """写入运行日志"""
        end_time = datetime.now()

        mysql_service.execute_insert(
            """INSERT INTO workflow_logs
               (script_id, data_source, bizdate, status, start_time, end_time, duration_ms, error_message)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (script_id, data_source, bizdate, status, end_time, end_time, duration_ms, error_message),
        )


# 全局单例
script_runner = ScriptRunner()
