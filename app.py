#!/usr/bin/env python3
"""轻量 Web 后端：让 demo.html 变成可交互的实时路由页面。

- GET  /            → 返回 demo.html
- POST /api/ask     → {"query": "...", "top_k": 5} → 实时调用 route_pipeline_request，
                      返回前端 case 结构（intent / pipelines / feasibility /
                      selection_summary / files / pipeline_id / file_details / llm）
- GET  /api/health  → LLM 配置状态 + Neo4j 只读连通性

Web 层使用 Python 标准库；LLM 与 Neo4j 客户端依赖分别见 requirements 文件。
私密配置从 .env.local 读取，显式进程环境变量优先。

启动：
    python3 app.py                      # 默认 127.0.0.1:8000
    PORT=9000 python3 app.py            # 换端口
    FORCE_RULE=1 python3 app.py         # 强制规则模式（离线、不调 LLM）
"""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
WEB_DIST = HERE / "web-dist"
GLASS_DEMO_HTML = HERE / "demo.html"

from runtime_config import get_llm_health, initialize_runtime  # noqa: E402

initialize_runtime()

from pipeline_router import route_pipeline_request  # noqa: E402
from neo4j_observability import Neo4jClient  # noqa: E402


NEO4J_CLIENT = Neo4jClient()


def _shape_case(
    query: str,
    raw: Dict[str, Any],
    kg_evidence: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """把 route_pipeline_request 的返回裁剪成前端渲染需要的 case 结构。"""
    intent = raw.get("intent") or {}
    candidates = raw.get("candidates") or []
    recommendations = raw.get("recommendations") or []
    planner_llm = raw.get("planner_metadata") or {}
    pipelines = [
        {
            "pipeline_id": candidate.get("match_id"),
            "name": f"候选链 {candidate.get('rank')}",
            "confidence": None,
            "reason": candidate.get("match_note"),
            "steps": candidate.get("tool_chain") or [],
            "assets": candidate.get("assets") or [],
            "selection_reason": candidate.get("selection_reason"),
            "extensions": candidate.get("extensions") or {},
            "source": "neo4j-atomic",
        }
        for candidate in candidates
    ]
    primary = candidates[0] if candidates else {}
    file_details = [
        {
            "path": asset.get("path"),
            "files": Path(str(asset.get("path") or "")).name,
            "input_role": asset.get("role"),
            "format": asset.get("format"),
            "source": asset.get("source"),
            "match_reason": "知识图谱资产匹配",
            "individual_accession": asset.get("individual_accession"),
            "sample_role": asset.get("sample_role"),
        }
        for asset in primary.get("assets") or []
    ]

    if candidates:
        workflow_mode = "candidate"
        workflow_label = "Top-3 原子工具候选链"
        workflow_reason = f"返回 {len(candidates)} 条通过工具目录、NEXT 关系和用户资产校验的候选链。"
    elif recommendations:
        workflow_mode = "recommendation"
        workflow_label = "Neo4j 业务流程推荐"
        workflow_reason = f"返回 {len(recommendations)} 条业务流程信息；未原子化的流程不会被编造成内部步骤。"
    else:
        workflow_mode = "unsupported"
        workflow_label = "当前需求不支持"
        workflow_reason = raw.get("unsupported_reason") or "没有通过校验的候选链。"
    return {
        "q": query,
        "intent": {k: intent.get(k) for k in
                   ("analysis_goal", "disease", "omics_type", "input_hint", "requested_outputs", "source")},
        "pipelines": pipelines,
        "candidates": candidates,
        "recommendations": recommendations,
        "candidate_count": raw.get("candidate_count", len(candidates)),
        "recommendation_count": raw.get("recommendation_count", len(recommendations)),
        "unsupported_reason": raw.get("unsupported_reason"),
        "feasibility": {
            "status": primary.get("feasibility_status") or raw.get("selection_status"),
            "message": raw.get("answer"),
            "missing_assets": [],
        },
        "selection_summary": (
            primary.get("match_note")
            or (recommendations[0].get("match_note") if recommendations else None)
            or raw.get("unsupported_reason")
        ),
        "files": [asset.get("path") for asset in primary.get("assets") or []],
        "pipeline_id": primary.get("match_id"),
        "file_details": file_details,
        "workflow_mode": workflow_mode,
        "workflow_plan": {
            "label": workflow_label,
            "reason": workflow_reason,
            "analysis": raw.get("analysis") or {},
        },
        "analysis": raw.get("analysis") or {},
        "atomic_candidate_unavailable_reason": (
            (raw.get("extensions") or {}).get("atomic_candidate_unavailable_reason")
            or raw.get("unsupported_reason")
        ),
        "business_pipelines": recommendations,
        "capability_answer": raw.get("capability_answer"),
        "selection_status": raw.get("selection_status"),
        "orchestration_status": raw.get("selection_status"),
        "orchestration_ready": bool(candidates or recommendations),
        "orchestration_message": raw.get("answer"),
        "llm": {
            "total_tokens": planner_llm.get("total_tokens"),
            "used": bool(planner_llm.get("used")),
            "model": planner_llm.get("model"),
            "status": planner_llm.get("status"),
            "degraded": planner_llm.get("status") in {
                "failed_or_unavailable", "timeout", "request_failed",
                "not_configured", "intent_llm_unavailable",
                "invalid_json", "invalid_response",
            },
        },
        "kg_evidence": kg_evidence or {
            "source": "neo4j-runtime",
            "connected": False,
            "matched_tool_ids": [],
            "missing_tool_ids": [],
            "slot_evidence": [],
            "query_ms": None,
            "error": "unavailable",
        },
        "message": raw.get("unsupported_reason"),
        "status": raw.get("selection_status"),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BioRouterDemo/1.0"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            llm = get_llm_health()
            self._send_json(200, {
                "ok": True,
                "mode": "rule" if (os.environ.get("FORCE_RULE") or "").strip() in ("1", "true", "on") else "llm",
                "llm": llm,
                "neo4j": NEO4J_CLIENT.health(),
            })
        elif path.startswith("/api/"):
            self._send_json(404, {"error": "not found"})
        else:
            if path in ("/", "/index.html", "/demo.html") and GLASS_DEMO_HTML.is_file():
                self._send(200, GLASS_DEMO_HTML.read_bytes(), "text/html; charset=utf-8")
                return
            relative = path.lstrip("/") or "index.html"
            target = (WEB_DIST / relative).resolve()
            if not str(target).startswith(str(WEB_DIST.resolve())) or not target.is_file():
                target = WEB_DIST / "index.html"
            try:
                body = target.read_bytes()
            except Exception as e:
                self._send_json(500, {"error": f"读取前端构建产物失败: {e}"})
                return
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in {"application/javascript", "application/json"}:
                ctype += "; charset=utf-8"
            self._send(200, body, ctype)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/api/ask":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b"{}"
            req = json.loads(body or b"{}")
            query = str(req.get("query") or "").strip()
            top_k = max(1, min(3, int(req.get("top_k") or 3)))
        except Exception as e:
            self._send_json(400, {"error": f"请求解析失败: {e}"})
            return
        if not query:
            self._send_json(400, {"error": "query 不能为空"})
            return
        try:
            raw = route_pipeline_request(query, top_k=top_k)
            evidence_tool_ids = list(dict.fromkeys(
                tool_id
                for candidate in raw.get("candidates") or []
                for tool_id in (candidate.get("extensions") or {}).get("internal_tool_ids") or []
                if tool_id
            ))
            kg_evidence = NEO4J_CLIENT.evidence(evidence_tool_ids)
            self._send_json(200, _shape_case(query, raw, kg_evidence))
        except Exception as e:
            self._send_json(500, {"error": f"路由失败: {type(e).__name__}: {e}"})

    def log_message(self, fmt: str, *args: Any) -> None:
        # 精简日志：只打 POST /api/ask
        if args and str(args[0]).startswith("POST /api/ask"):
            super().log_message(fmt, *args)


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    mode = "规则(离线)" if (os.environ.get("FORCE_RULE") or "").strip() in ("1", "true", "on") else "LLM"
    llm = get_llm_health()
    srv = ThreadingHTTPServer((host, port), Handler)
    print("=" * 56)
    print(f"  BioRouter Demo 已启动")
    print(f"  地址   : http://{host}:{port}")
    print(f"  模式   : {mode}")
    print(f"  模型   : {llm['model'] or '-'}")
    print(f"  端点   : {llm['endpoint_host'] or '-'}  credentials={'configured' if llm['configured'] else 'missing'}")
    print(f"  停止   : Ctrl+C")
    print("=" * 56)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
        srv.shutdown()


if __name__ == "__main__":
    main()
