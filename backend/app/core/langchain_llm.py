"""LangChain LLM 客户端 - 使用 LCEL (RunnableWithMessageHistory) 管理多轮对话"""
from __future__ import annotations

import json
import re
from typing import List, Dict, Any, Optional, Type, Callable
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, PrivateAttr
from .config import settings


# ============================================================
# 自定义 ChatMessageHistory: 实现 Summary Buffer 逻辑
# ============================================================

class SummaryBufferChatHistory(InMemoryChatMessageHistory):
    """
    基于 Token 阈值的摘要缓冲历史记录（独立类，不继承 pydantic，支持鸭子类型）。

    由 RunnableWithMessageHistory 通过 get_session_history 获取，只要具备：
      - messages 属性 (List[BaseMessage])
      - add_message(message) 方法
      - clear() 方法
    就能正常工作。

    当累积消息超过 max_token_limit 时：
      - 保留最近的消息
      - 把旧消息交给 LLM 生成摘要
      - 摘要作为一条 SystemMessage 放在最前面
    """
    # ---------- Token 估算 & 摘要 ----------


# ============================================================
# LLM 客户端
# ============================================================

class LangChainLLMClient:
    """统一的 LLM 调用客户端"""

    def __init__(self):
        self.api_base = settings.LITELLM_API_BASE
        if not self.api_base.endswith("/v1"):
            self.api_base = self.api_base.rstrip("/") + "/v1"
        self.api_key = settings.LITELLM_MASTER_KEY
        self.model_list = settings.LITELLM_MODEL_LIST

    def build_chat_model(self, model: str, **kwargs) -> ChatOpenAI:
        """构建 ChatOpenAI 实例"""
        return ChatOpenAI(
            model=model,
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=600.0,
            max_retries=2,
            **kwargs,
        )

    # ---------- 多轮对话（核心入口） ----------

    async def chat_with_history(
        self,
        model: str,
        user_input: str,
        get_session_history: Callable[[], BaseChatMessageHistory],
        system_message: str = "",
        temperature: float = 0.7,
        max_tokens: int = 8000,
    ) -> Dict[str, Any]:
        """
        使用 LCEL + RunnableWithMessageHistory 进行多轮对话。

        由调用方通过 `get_session_history` 提供会话历史的获取函数，
        使本方法不耦合具体的 SessionManager 实现。

        Args:
            model: 模型名称
            user_input: 用户输入
            get_session_history: 返回当前会话的 BaseChatMessageHistory 实例
            system_message: 系统提示词
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            {"success": bool, "content": str, "model": str, "error": str}
        """
        try:
            llm = self.build_chat_model(
                model, temperature=temperature, max_tokens=max_tokens
            )

            # ---- 构建 prompt：system_message 直接嵌入字符串 ----
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ])

            # ---- LCEL 链：prompt -> llm -> 字符串输出（必须带 () 实例化） ----
            chain = prompt | llm | StrOutputParser()

            # ---- 用 RunnableWithMessageHistory 管理历史 ----
            # 注意：get_session_history 由 RunnableWithMessageHistory 内部调用，会传入 session_id
            # 这里用 lambda session_id: get_session_history() 忽略它，因为我们已经拿到具体对象
            with_message_history = RunnableWithMessageHistory(
                runnable=chain,
                get_session_history=lambda session_id: get_session_history(),
                input_messages_key="input",
                history_messages_key="history",
            )

            print(f"[LLM][LCEL] 调用模型: model={model}")
            print(f"[LLM][LCEL] 用户输入前 200 字: {user_input[:200]}...")

            # 执行调用
            content = await with_message_history.ainvoke(
                {"input": user_input},
                config={"configurable": {"session_id": "current"}},
            )

            if not isinstance(content, str):
                content = str(content)

            print(f"[LLM][LCEL] 调用成功，返回长度: {len(content)}")
            return {"success": True, "content": content, "model": model}

        except Exception as e:
            print(f"[LLM][LCEL] 调用失败: {e}")
            return {"success": False, "error": str(e)}

    # ---------- 无状态对话（不管理历史） ----------

    async def chat_with_messages(
        self,
        model: str,
        messages: List[BaseMessage],
        temperature: float = 0.7,
        max_tokens: int = 8000,
    ) -> Dict[str, Any]:
        """
        使用 BaseMessage 列表进行一次性聊天调用。
        """
        try:
            llm = self.build_chat_model(
                model, temperature=temperature, max_tokens=max_tokens
            )

            print(f"[LLM] 调用模型: model={model}, messages={len(messages)}")
            for i, msg in enumerate(messages):
                role = type(msg).__name__
                preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                print(f"[LLM] Message[{i}] {role}: {preview}")

            response = llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            if not isinstance(content, str):
                content = str(content)

            print(f"[LLM] 调用成功，返回长度: {len(content)}")
            return {"success": True, "content": content, "model": model}

        except Exception as e:
            print(f"[LLM] 调用失败: {e}")
            return {"success": False, "error": str(e)}

    # ---------- 结构化输出 ----------

    async def call_with_structured_output(
        self,
        model: str,
        prompt: ChatPromptTemplate,
        response_format: Type[BaseModel],
        temperature: float = 0.7,
        max_tokens: int = 8000,
        **prompt_vars,
    ) -> Dict[str, Any]:
        """
        使用 ChatPromptTemplate 进行带结构化输出的调用。
        优先使用 with_structured_output，失败回退到普通调用 + JSON 解析。
        """
        # Step 1: 尝试 LangChain structured output
        try:
            llm = self.build_chat_model(
                model, temperature=temperature, max_tokens=max_tokens
            )
            structured_llm = llm.with_structured_output(response_format)

            messages = prompt.format_messages(**prompt_vars)

            print(f"[LLM] 尝试 structured output: {response_format.__name__}, messages={len(messages)}")
            response = await structured_llm.ainvoke(messages)

            result_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict()
            print(f"[LLM] structured output 成功")
            return {"success": True, "data": result_dict, "model": model}

        except Exception as struct_err:
            print(f"[LLM] structured output 不支持: {struct_err}")

        # Step 2: 回退到普通调用 + 手动解析 JSON
        try:
            print(f"[LLM] 回退到普通调用 + JSON 解析")

            llm = self.build_chat_model(
                model, temperature=temperature, max_tokens=max_tokens
            )

            messages = prompt.format_messages(**prompt_vars)

            json_schema = response_format.model_json_schema() if hasattr(response_format, 'model_json_schema') else response_format.schema()
            format_instruction = SystemMessage(
                content=f"你必须返回严格的 JSON 格式，符合以下 Schema:\n{json.dumps(json_schema, ensure_ascii=False, indent=2)}\n不要输出任何额外文本，只返回 JSON。"
            )
            messages.append(format_instruction)

            print(f"[LLM][Fallback] 消息数量: {len(messages)}")
            for i, msg in enumerate(messages):
                role = type(msg).__name__
                preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                print(f"[LLM][Fallback] Message[{i}] {role}: {preview}")

            response = await llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            if not isinstance(content, str):
                content = str(content)

            print(f"[LLM][Fallback] 调用成功，返回长度: {len(content)}")

            # 解析 JSON
            data = None

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                pass

            if data is None:
                match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1).strip())
                    except json.JSONDecodeError:
                        pass

            if data is None:
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    try:
                        data = json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass

            if data is None:
                return {
                    "success": False,
                    "error": "无法解析输出为 JSON 格式",
                    "content": content[:1500],
                }

            print(f"[LLM] JSON 解析成功")
            return {"success": True, "data": data, "model": model, "fallback": True}

        except Exception as e:
            print(f"[LLM] 回退调用失败: {e}")
            return {"success": False, "error": str(e)}


# 全局单例
llm_client = LangChainLLMClient()
