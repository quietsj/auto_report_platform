"""MySQL 数据库服务"""
import mysql.connector
from mysql.connector import pooling
from typing import List, Optional, Dict, Any
from ..core.config import settings


class MySQLService:
    """MySQL 数据库服务单例（懒加载）"""

    _instance: Optional['MySQLService'] = None
    _pool: Optional[pooling.MySQLConnectionPool] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_pool(self):
        """延迟初始化连接池"""
        if self._pool is None and not self._initialized:
            self._initialized = True
            try:
                self._pool = pooling.MySQLConnectionPool(
                    pool_name="workflow_pool",
                    pool_size=5,
                    host=settings.MYSQL_HOST,
                    port=int(settings.MYSQL_PORT),
                    user=settings.MYSQL_USER,
                    password=str(settings.MYSQL_PASSWORD) if settings.MYSQL_PASSWORD else None,
                    database=settings.MYSQL_DATABASE,
                    charset=settings.MYSQL_CHARSET,
                    autocommit=True,
                    use_pure=True,
                )
            except mysql.connector.Error as e:
                print(f"MySQL 连接池初始化失败: {e}")
                self._pool = None

    def get_connection(self):
        """获取数据库连接"""
        self._ensure_pool()
        if self._pool:
            try:
                return self._pool.get_connection()
            except mysql.connector.Error as e:
                print(f"获取连接失败: {e}")
                return None
        return None

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询语句，返回字典列表"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            cursor.close()
            return results
        except mysql.connector.Error as e:
            print(f"查询执行失败: {e}")
            return []
        finally:
            conn.close()

    def execute_update(self, query: str, params: tuple = None) -> int:
        """执行更新语句，返回影响的行数"""
        conn = self.get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except mysql.connector.Error as e:
            print(f"更新执行失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def execute_insert(self, query: str, params: tuple = None) -> int:
        """执行插入语句，返回自增ID"""
        conn = self.get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            inserted_id = cursor.lastrowid
            cursor.close()
            return inserted_id
        except mysql.connector.Error as e:
            print(f"插入执行失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()


# 全局服务实例（懒加载）
mysql_service = MySQLService()
