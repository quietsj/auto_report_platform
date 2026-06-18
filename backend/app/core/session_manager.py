"""会话管理器 - 使用 LCEL 原生的 ChatMessageHistory 管理多轮对话"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from .langchain_llm import SummaryBufferChatHistory, llm_client


# ============================================================
# 数据模型
# ============================================================

class Message(BaseModel):
    """单条对话消息（业务层存储，供前端展示）"""
    role: str  # user / assistant
    content: str
    pipeline_result: Optional[Dict[str, Any]] = None
    timestamp: str


class Session(BaseModel):
    """会话对象"""
    session_id: str
    messages: List[Message] = []
    created_at: str
    updated_at: str

    class Config:
        arbitrary_types_allowed = True

    # LLM 层面的消息历史（SummaryBufferChatHistory 负责摘要与 token 管理）
    llm_history: Optional[BaseChatMessageHistory] = None


# ============================================================
# SessionManager
# ============================================================

class SessionManager:
    """会话管理器 - 内存存储会话历史

    设计：
    - 每个 session_id 对应一个 Session
    - Session 内部有两个层面的消息：
        1. messages: 业务层消息（供前端展示、保存链路结果）
        2. llm_history: LLM 层面的消息历史（SummaryBufferChatHistory，
           自动做 token 摘要压缩）
    - get_llm_history() 供 pipeline_agent / chat_with_history 使用
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    # ---------- 会话 CRUD ----------

    def create_session(self, session_id: Optional[str] = None) -> str:
        """创建新会话，返回 session_id"""
        if session_id is None:
            session_id = f"sess_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(self)}"

        now = datetime.now().isoformat()
        self._sessions[session_id] = Session(
            session_id=session_id,
            messages=[],
            created_at=now,
            updated_at=now,
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return [
            {
                "session_id": s.session_id,
                "message_count": len(s.messages),
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "last_message": s.messages[-1].content[:50] + "..." if s.messages else "",
            }
            for s in self._sessions.values()
        ]

    # ---------- LLM 历史管理 ----------

    def get_llm_history(self, session_id: str) -> Optional[BaseChatMessageHistory]:
        """
        获取指定会话的 LLM 消息历史。
        若会话不存在或尚未初始化，会自动创建 SummaryBufferChatHistory。

        Args:
            session_id: 会话 ID
            model: 模型名称（用于摘要生成时使用相同的模型）

        Returns:
            BaseChatMessageHistory 实例（实际为 SummaryBufferChatHistory）
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.llm_history is None:
            session.llm_history = SummaryBufferChatHistory()

        return session.llm_history

    async def prune_history(self, session_id: str) -> None:
        """触发会话的历史摘要（超过 token 阈值时自动调用）"""
        session = self._sessions.get(session_id)
        if session and session.llm_history and isinstance(session.llm_history, SummaryBufferChatHistory):
            await session.llm_history.prune_and_summarize()

    # ---------- 业务消息管理 ----------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        pipeline_result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """添加业务消息到会话"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        message = Message(
            role=role,
            content=content,
            pipeline_result=pipeline_result,
            timestamp=datetime.now().isoformat(),
        )
        session.messages.append(message)
        session.updated_at = datetime.now().isoformat()
        return True

    def get_messages(self, session_id: str) -> List[Message]:
        """获取会话的所有业务消息"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.messages

    def get_conversation_history(self, session_id: str, max_turns: int = 10) -> List[Dict[str, str]]:
        """获取对话历史（精简版，role + content）"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        messages = session.messages[-max_turns * 2:]
        return [{"role": m.role, "content": m.content} for m in messages]

    def clear_session(self, session_id: str) -> bool:
        """清空会话历史（同时清空业务消息和 LLM 历史）"""
        if session_id in self._sessions:
            self._sessions[session_id].messages = []
            if self._sessions[session_id].llm_history:
                self._sessions[session_id].llm_history.clear()
            self._sessions[session_id].updated_at = datetime.now().isoformat()
            return True
        return False


# 全局会话管理器实例
session_manager = SessionManager()
