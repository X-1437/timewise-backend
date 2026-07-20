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

    def _direct_reply_content(self, reply_key: str) -> str:
        # W5-10: 所有非分析输入统一返回同一结构的引导回复
        # 不再按寒暄/天气/未知算法等分散处理
        if reply_key == "non_analysis":
            return (
                "我是时间序列数据分析助手，当前主要支持以下分析能力：\n\n"
                "- **EDA 概览**：查看数据基本情况和统计信息\n"
                "- **预处理**：缺失值填充、异常值移除\n"
                "- **特征提取**：趋势分析、周期性、相关性、季节性、傅里叶、小波\n"
                "- **朴素预测**：相邻两行、相同时间点、按天累加三种基线方法\n"
                "- **导出报告**：一键导出分析报告（ZIP 离线包，含图片和数据）\n\n"
                "**下一步你可以**：\n"
                "- 上传一个 CSV 文件，然后告诉我你想做的分析\n"
                "- 或者直接说\"帮我运行全流程\"，我会自动执行标准主流程并导出报告"
            )
        if reply_key == "empty":
            return "请输入你希望我执行的分析任务，我会按当前能力范围帮你完成。"
        # 保留历史兼容：旧版 per-case reply_key 仍然可用，但已不再由新逻辑触发
        if reply_key == "greeting":
            return (
                "你好，我可以帮你做时间序列数据分析。\n\n"
                "你可以继续让我执行这些任务：\n"
                "- 做 EDA 概览\n"
                "- 清洗数据\n"
                "- 分析趋势、周期性、相关性、季节性、傅里叶、小波\n"
                "- 做朴素预测\n"
                "- 导出 Markdown 报告"
            )
        return "请输入你希望我执行的分析任务，我会按当前能力范围帮你完成。"

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

        if tool_name == "direct_reply":
            assistant_msg = await self._message_service.create_assistant_message(
                session_id=session_id,
                content=self._direct_reply_content(str(tool_args.get("reply_key") or "")),
                tool_calls=None,
                actions=None,
                file_id=file_id,
            )
            return session_id, assistant_msg

        if tool_name == "run_full_flow":
            if not file_id:
                assistant_msg = await self._message_service.create_assistant_message(
                    session_id=session_id,
                    content="请先上传 CSV 文件后再运行全流程。",
                    tool_calls=None,
                    actions=None,
                    file_id=None,
                )
                return session_id, assistant_msg

            steps: list[tuple[str, str, dict[str, Any]]] = [
                ("upload_data", "数据上传确认", {}),
                ("eda_analysis", "EDA（原始数据）", {"data_version": "raw"}),
                ("preprocessing", "预处理（异常值处理）", {"method": "outlier_remove"}),
                ("feature_analysis", "特征提取（预处理后数据）", {"data_version": "preprocessed"}),
                (
                    "naive_forecast",
                    "朴素预测（相邻两行）",
                    {"data_version": "preprocessed", "method": "next_row", "periods": 7},
                ),
                (
                    "naive_forecast",
                    "朴素预测（相同时间点）",
                    {"data_version": "preprocessed", "method": "same_time", "periods": 7},
                ),
                (
                    "naive_forecast",
                    "朴素预测（按天累加）",
                    {"data_version": "preprocessed", "method": "daily_sum", "periods": 7},
                ),
            ]

            tool_calls: list[ToolCall] = []
            step_blocks: list[str] = []

            for i, (step_tool, step_title, step_args) in enumerate(steps, start=1):
                call_args = dict(step_args)
                call_args.setdefault("session_id", session_id)
                call_args.setdefault("file_id", file_id)
                try:
                    tool_output = await self._mcp_client.call_tool(step_tool, call_args)
                except Exception as e:
                    assistant_msg = await self._message_service.create_assistant_message(
                        session_id=session_id,
                        content="\n".join(
                            [
                                "## 全流程执行失败",
                                "",
                                f"- 失败步骤：{i}. {step_title}",
                                f"- 失败原因：{type(e).__name__}: {str(e)}",
                                "",
                                "建议：请重试；若持续失败，我可以帮你定位是哪一步的输入/数据导致的。",
                            ]
                        ).strip(),
                        tool_calls=tool_calls or None,
                        actions=None,
                        file_id=file_id,
                    )
                    return session_id, assistant_msg

                output_data_version = self._extract_output_data_version(tool_output)
                artifact_path = self._extract_artifact_path(tool_output)
                warning_flags = self._extract_warning_flags(step_tool, tool_output)

                tool_call = ToolCall(
                    tool_name=step_tool,
                    tool_args=call_args,
                    tool_result=tool_output,
                    timestamp=datetime.now(timezone.utc),
                    data_version=output_data_version,
                    artifact_path=artifact_path,
                    warning_flags=warning_flags,
                )
                tool_calls.append(tool_call)
                if step_tool != "upload_data":
                    report_step_no = len(step_blocks) + 1
                    step_blocks.append(f"### {report_step_no}. {step_title}\n\n{tool_output}".strip())

            export_args: dict[str, Any] = {
                "session_id": session_id,
                "file_id": file_id,
                "scope": "standard_flow",
                "step_blocks": step_blocks,
            }
            try:
                export_output = await self._mcp_client.call_tool("export_markdown", export_args)
            except Exception as e:
                assistant_msg = await self._message_service.create_assistant_message(
                    session_id=session_id,
                    content="\n".join(
                        [
                            "## 全流程已完成（导出失败）",
                            "",
                            "- 各步骤分析已完成，但在导出报告时失败。",
                            f"- 失败原因：{type(e).__name__}: {str(e)}",
                            "",
                            "建议：请稍后重试“导出报告”；或把错误信息发我，我来定位修复。",
                        ]
                    ).strip(),
                    tool_calls=tool_calls or None,
                    actions=None,
                    file_id=file_id,
                )
                return session_id, assistant_msg

            export_call = ToolCall(
                tool_name="export_markdown",
                tool_args=export_args,
                tool_result=export_output,
                timestamp=datetime.now(timezone.utc),
                data_version=None,
                artifact_path=self._extract_artifact_path(export_output),
                warning_flags=self._extract_warning_flags("export_markdown", export_output),
            )
            tool_calls.append(export_call)

            assistant_msg = await self._message_service.create_assistant_message(
                session_id=session_id,
                content="\n".join(
                    [
                        "## 全流程执行完成",
                        "",
                        "- 已按标准主流程依次完成：EDA → 预处理 → 特征提取 → 朴素预测（三种方法）→ 导出。",
                        "",
                        export_output.strip(),
                    ]
                ).strip(),
                tool_calls=tool_calls,
                actions=None,
                file_id=file_id,
            )
            return session_id, assistant_msg

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
