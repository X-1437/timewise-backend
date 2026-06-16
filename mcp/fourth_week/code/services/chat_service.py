from datetime import datetime, timezone
import re
from typing import Any

from dal.mongodb.utils import to_object_id
from llm.client import LLMClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from mcp_layer.client import MCPClient
from models.message import AssistantAction, Message, ToolCall
from services.message_service import MessageService
from services.session_service import SessionService


class ChatService:
    def __init__(
        self,
        *,
        db: AsyncIOMotorDatabase,
        session_service: SessionService,
        message_service: MessageService,
        llm_client: LLMClient,
        mcp_client: MCPClient,
    ):
        self._db = db
        self._session_service = session_service
        self._message_service = message_service
        self._llm_client = llm_client
        self._mcp_client = mcp_client

    def _extract_data_version(self, content: str) -> str | None:
        q = (content or "").strip().lower()
        if any(k in q for k in ["预处理后", "清洗后", "处理后", "preprocessed"]):
            return "preprocessed"
        if any(k in q for k in ["原始数据", "原始", "原表", "未清洗", "raw"]):
            return "raw"
        return None

    def _extract_artifact_path(self, text: str) -> str | None:
        match = re.search(r"- 路径：([^\r\n]+)", text or "")
        return match.group(1).strip() if match else None

    def _extract_output_data_version(self, text: str) -> str | None:
        match = re.search(r"- 数据版本：([^\r\n]+)", text or "")
        return match.group(1).strip() if match else None

    def _extract_warning_flags(self, tool_name: str, text: str) -> list[str] | None:
        flags: list[str] = []
        raw = text or ""
        if tool_name == "feature_analysis" and "尚未进行预处理" in raw:
            flags.append("feature_without_preprocess")
        if tool_name == "naive_forecast" and "尚未进行预处理" in raw:
            flags.append("forecast_without_preprocess")
        if "未找到可用的预处理产物" in raw or "未找到预处理产物，已回退" in raw:
            flags.append("preprocessed_fallback_to_raw")
        return flags or None

    async def _has_preprocessed_artifact(self, *, session_id: str, file_id: str) -> bool:
        doc = await self._db.artifacts.find_one(
            {
                "type": "preprocessed_csv",
                "sessionId": to_object_id(session_id),
                "fileId": to_object_id(file_id),
            },
            projection={"_id": 1},
        )
        return doc is not None

    def _is_generic_analysis_request(self, content: str) -> bool:
        q = (content or "").strip().lower()
        if not q:
            return False
        if any(k in q for k in ["特征", "预测", "清洗", "预处理", "导出", "报告"]):
            return False
        if any(k in q for k in ["eda", "概览", "缺失", "异常", "分布", "统计", "简单分析"]):
            return False
        return any(k in q for k in ["帮我分析", "分析一下", "看看这个数据", "数据怎么样", "看看怎么样"])

    def _confirmation_message(self, *, tool_name: str) -> tuple[str, list[AssistantAction]]:
        if tool_name == "naive_forecast":
            message = "\n".join(
                [
                    "## 需要确认",
                    "",
                    "- 当前尚未进行预处理，原始数据中的缺失值、异常值或类型问题可能直接影响预测结果。",
                    "- 建议先完成预处理后再进行预测。",
                    "",
                    "请选择下一步：",
                ]
            ).strip()
            actions = [
                AssistantAction(
                    type="call_tool",
                    id="preprocess",
                    label="先进行预处理（推荐）",
                    tool_name="preprocessing",
                    tool_args={"method": "outlier_remove"},
                ),
                AssistantAction(
                    type="call_tool",
                    id="forecast_raw",
                    label="直接基于原始数据预测",
                    tool_name="naive_forecast",
                    tool_args={"data_version": "raw"},
                ),
                AssistantAction(
                    type="call_tool",
                    id="eda_raw",
                    label="先查看 EDA",
                    tool_name="eda_analysis",
                    tool_args={"data_version": "raw"},
                ),
            ]
            return message, actions

        message = "\n".join(
            [
                "## 需要确认",
                "",
                "- 当前尚未进行预处理，原始数据可能包含缺失值、异常值或类型问题，这会影响特征分析结果。",
                "- 建议先进行预处理后再分析。",
                "",
                "请选择下一步：",
            ]
        ).strip()
        actions = [
            AssistantAction(
                type="call_tool",
                id="preprocess",
                label="先进行预处理（推荐）",
                tool_name="preprocessing",
                tool_args={"method": "outlier_remove"},
            ),
            AssistantAction(
                type="call_tool",
                id="feature_raw",
                label="直接基于原始数据分析",
                tool_name="feature_analysis",
                tool_args={"data_version": "raw"},
            ),
            AssistantAction(
                type="call_tool",
                id="eda_raw",
                label="先查看 EDA",
                tool_name="eda_analysis",
                tool_args={"data_version": "raw"},
            ),
        ]
        return message, actions

    def _eda_disambiguation_message(self) -> tuple[str, list[AssistantAction]]:
        message = "\n".join(
            [
                "## 需要确认",
                "",
                "- 当前同时存在原始数据与预处理后数据。",
                "- 你希望我查看哪一份数据的 EDA？",
                "",
                "请选择下一步：",
            ]
        ).strip()
        actions = [
            AssistantAction(
                type="call_tool",
                id="eda_preprocessed",
                label="查看预处理后 EDA（推荐）",
                tool_name="eda_analysis",
                tool_args={"data_version": "preprocessed"},
            ),
            AssistantAction(
                type="call_tool",
                id="eda_raw",
                label="查看原始数据 EDA",
                tool_name="eda_analysis",
                tool_args={"data_version": "raw"},
            ),
        ]
        return message, actions

    def _version_disambiguation_message(self, *, tool_name: str) -> tuple[str, list[AssistantAction]]:
        message = "\n".join(
            [
                "## 需要确认",
                "",
                "- 当前存在原始数据与预处理后数据两种分析对象。",
                "- 你希望我基于哪一版数据继续？",
                "",
                "请选择下一步：",
            ]
        ).strip()
        actions = [
            AssistantAction(
                type="call_tool",
                id="continue_preprocessed",
                label="基于预处理后数据继续（推荐）",
                tool_name=tool_name,
                tool_args={"data_version": "preprocessed"},
            ),
            AssistantAction(
                type="call_tool",
                id="continue_raw",
                label="基于原始数据继续",
                tool_name=tool_name,
                tool_args={"data_version": "raw"},
            ),
        ]
        return message, actions

    async def send_message(
        self,
        *,
        content: str,
        session_id: str | None = None,
        file_id: str | None = None,
        action: dict[str, Any] | None = None,
    ) -> tuple[str, Message]:
        session = None
        if session_id:
            session = await self._session_service.get(session_id)
        if session is None:
            session = await self._session_service.create()
            session_id = session.id

        await self._message_service.create_user_message(
            session_id=session_id, content=content, file_id=file_id
        )

        if action and action.get("type") == "call_tool":
            tool_name = (action.get("tool_name") or "").strip()
            tool_args = dict(action.get("tool_args") or {})
        else:
            intent = self._llm_client.analyze_intent(content)
            tool_name = intent["tool"]
            tool_args = dict(intent["args"])

        tool_args.setdefault("session_id", session_id)
        if file_id:
            tool_args.setdefault("file_id", file_id)
        if tool_name in {"eda_analysis", "feature_analysis", "naive_forecast"}:
            explicit_data_version = self._extract_data_version(content)
            if explicit_data_version:
                tool_args["data_version"] = explicit_data_version

        if tool_name == "preprocessing":
            q = (content or "").strip().lower()
            method = (tool_args.get("method") or "").strip().lower()
            if any(k in q for k in ["清洗", "clean"]):
                if method in {"", "missing_fill"}:
                    tool_args["method"] = "outlier_remove"
            if any(k in q for k in ["异常", "outlier"]):
                tool_args["method"] = "outlier_remove"

        requires_file = tool_name in {
            "upload_data",
            "eda_analysis",
            "preprocessing",
            "feature_analysis",
            "naive_forecast",
            "export_markdown",
        }
        if requires_file and not file_id:
            assistant_msg = await self._message_service.create_assistant_message(
                session_id=session_id,
                content="请先上传 CSV 文件后再进行分析或导出。",
                tool_calls=None,
                actions=None,
                file_id=None,
            )
            return session_id, assistant_msg

        if (
            not action
            and tool_name == "eda_analysis"
            and file_id
            and await self._has_preprocessed_artifact(session_id=session_id, file_id=file_id)
        ):
            explicit_data_version = self._extract_data_version(content)
            if not explicit_data_version:
                if self._is_generic_analysis_request(content):
                    msg, actions = self._version_disambiguation_message(tool_name=tool_name)
                else:
                    msg, actions = self._eda_disambiguation_message()
                assistant_msg = await self._message_service.create_assistant_message(
                    session_id=session_id,
                    content=msg,
                    tool_calls=None,
                    actions=actions,
                    file_id=file_id,
                )
                return session_id, assistant_msg

        if (
            not action
            and tool_name in {"feature_analysis", "naive_forecast"}
            and file_id
            and not await self._has_preprocessed_artifact(session_id=session_id, file_id=file_id)
        ):
            explicit_data_version = self._extract_data_version(content)
            if explicit_data_version != "raw":
                msg, actions = self._confirmation_message(tool_name=tool_name)
                assistant_msg = await self._message_service.create_assistant_message(
                    session_id=session_id,
                    content=msg,
                    tool_calls=None,
                    actions=actions,
                    file_id=file_id,
                )
                return session_id, assistant_msg

        tool_output = await self._mcp_client.call_tool(tool_name, tool_args)
        output_data_version = self._extract_output_data_version(tool_output)
        artifact_path = self._extract_artifact_path(tool_output)
        warning_flags = self._extract_warning_flags(tool_name, tool_output)

        tool_call = ToolCall(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_output,
            timestamp=datetime.now(timezone.utc),
            data_version=output_data_version,
            artifact_path=artifact_path,
            warning_flags=warning_flags,
        )

        assistant_content = tool_output
        assistant_msg = await self._message_service.create_assistant_message(
            session_id=session_id,
            content=assistant_content,
            tool_calls=[tool_call],
            actions=None,
            file_id=file_id,
        )
        return session_id, assistant_msg
