from typing import List, Dict, Any
import httpx
from ..core.config import settings


class ClickHouseService:
    def __init__(self):
        self.host = settings.CLICKHOUSE_HOST
        self.port = settings.CLICKHOUSE_PORT
        self.user = settings.CLICKHOUSE_USER
        self.password = settings.CLICKHOUSE_PASSWORD
        self.database = settings.CLICKHOUSE_DATABASE
    
    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        url = f"http://{self.host}:{self.port}"
        params = {
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "query": sql
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return self._parse_response(response.text)
        except Exception as e:
            raise Exception(f"ClickHouse query failed: {str(e)}")
    
    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        lines = text.strip().split('\n')
        if not lines:
            return []
        return [{"data": line} for line in lines]


clickhouse_service = ClickHouseService()
