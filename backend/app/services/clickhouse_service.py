"""ClickHouse 数据库服务"""
from typing import List, Dict, Any, Optional
import clickhouse_connect
from ..core.config import settings


class ClickHouseService:
    def __init__(self):
        self.host = settings.CLICKHOUSE_HOST
        self.port = settings.CLICKHOUSE_PORT
        self.user = settings.CLICKHOUSE_USER
        self.password = settings.CLICKHOUSE_PASSWORD
        self.database = settings.CLICKHOUSE_DATABASE
        self._client = None
    
    @property
    def client(self):
        """懒加载连接"""
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.database
            )
        return self._client
    
    def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """执行 SQL 查询，返回字典列表"""
        try:
            result = self.client.query_df(sql)
            # 转换为字典列表
            if result is None or result.empty:
                return []
            return result.to_dict('records')
        except Exception as e:
            raise Exception(f"ClickHouse query failed: {str(e)}")
    
    def get_databases(self) -> List[str]:
        """获取所有数据库"""
        result = self.client.query("SHOW DATABASES")
        databases = []
        for row in result.result_rows:
            name = row[0]
            if name and name not in ('system', 'information_schema'):
                databases.append(name)
        return databases
    
    def get_tables(self, database: str = None) -> List[Dict[str, str]]:
        """获取指定数据库的表列表"""
        db = database or self.database
        result = self.client.query(f"SHOW TABLES FROM {db}")
        tables = []
        for row in result.result_rows:
            tables.append({"name": row[0], "database": db})
        return tables
    
    def get_table_schema(self, table_name: str, database: str = None) -> List[Dict[str, Any]]:
        """获取表的字段结构"""
        db = database or self.database
        sql = f"DESCRIBE TABLE {db}.{table_name}"
        result = self.client.query(sql)
        
        fields = []
        for row in result.result_rows:
            fields.append({
                "name": row[0],
                "type": row[1],
                "default_type": row[2] if len(row) > 2 else None,
                "default_expression": row[3] if len(row) > 3 else None,
                "comment": row[4] if len(row) > 4 else None,
                "codec_expression": row[5] if len(row) > 5 else None,
                "ttl_expression": row[6] if len(row) > 6 else None
            })
        return fields
    
    def get_sample_data(self, table_name: str, database: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """获取表的样本数据"""
        db = database or self.database
        sql = f"SELECT * FROM {db}.{table_name} LIMIT {limit}"
        return self.execute_query(sql)
    
    def get_column_stats(self, table_name: str, column_name: str, database: str = None) -> Dict[str, Any]:
        """获取字段统计信息"""
        db = database or self.database
        sql = f"""
            SELECT 
                min({column_name}) as min_value,
                max({column_name}) as max_value,
                avg({column_name}) as avg_value,
                count({column_name}) as count_value
            FROM {db}.{table_name}
        """
        result = self.execute_query(sql)
        return result[0] if result else {}
    
    def insert_data(self, table_name: str, data: List[tuple], column_names: List[str], database: str = None) -> bool:
        """插入数据"""
        db = database or self.database
        try:
            self.client.insert(
                table=f"{db}.{table_name}",
                data=data,
                column_names=column_names
            )
            return True
        except Exception as e:
            raise Exception(f"ClickHouse insert failed: {str(e)}")
    
    def command(self, sql: str) -> Any:
        """执行命令（如 DDL）"""
        return self.client.command(sql)
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            self._client = None


clickhouse_service = ClickHouseService()
