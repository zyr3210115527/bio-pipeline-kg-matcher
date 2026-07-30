"""
NL intent layer (closed-set) in front of deterministic recommend_workflow.
Phase 4: never raise to callers — always degrade gracefully.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from runtime_config import set_llm_last_status

try:
    from kg_tool import FORMAT_VOCAB, GENERIC, KGTool, norm_fmt
except Exception:  # pragma: no cover - pipeline-first mode can run without Neo4j deps
    KGTool = Any  # type: ignore
    FORMAT_VOCAB = {"bam", "csv", "dir", "fq.gz", "gz", "json", "list", "maf", "pdf", "png", "tsv", "txt", "vcf", "xls", "xlsx"}
    GENERIC = {"tsv", "xls", "xlsx", "csv", "txt", "pdf", "png", "json", "gz", "list", "dir"}

    def norm_fmt(s):
        if s is None:
            return []
        text = str(s).strip().lstrip(".")
        if text in {"fastq.gz", ".fastq.gz"}:
            text = "fq.gz"
        return [x.strip() for x in text.split(",") if x.strip()]
from pipeline_router import route_pipeline_request

try:
    import config as _cfg
except Exception:  # pragma: no cover
    _cfg = None

# ---------------------------------------------------------------------------
# Minimal OpenAI-compatible client (reuses repo config when present)
# ---------------------------------------------------------------------------
def _llm_settings() -> Dict[str, Any]:
    mode = os.environ.get("LLM_MODE") or (getattr(_cfg, "LLM_MODE", "api") if _cfg else "api")
    # Never reuse generic OPENAI_* credentials for this explicitly configured endpoint.
    return {
        "mode": mode,
        "api_key": os.environ.get("LLM_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or (getattr(_cfg, "API_KEY", None) if _cfg else None),
        "api_base": os.environ.get("LLM_BASE_URL")
        or os.environ.get("DEEPSEEK_BASE_URL")
        or (getattr(_cfg, "API_BASE", None) if _cfg else None),
        "model": os.environ.get("LLM_MODEL")
        or os.environ.get("DEEPSEEK_MODEL")
        or (getattr(_cfg, "API_MODEL", "deepseek-chat") if _cfg else "deepseek-chat"),
        "ollama_url": os.environ.get("OLLAMA_URL")
        or (
            getattr(_cfg, "OLLAMA_URL", "http://localhost:11434/api/generate")
            if _cfg
            else "http://localhost:11434/api/generate"
        ),
        "local_model": os.environ.get("LOCAL_MODEL")
        or (getattr(_cfg, "LOCAL_MODEL", "qwen2.5:7b") if _cfg else "qwen2.5:7b"),
    }


def _force_rule() -> bool:
    v = (os.environ.get("FORCE_RULE") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _log_llm(msg: str) -> None:
    print(f"[LLM] {msg}", file=sys.stderr, flush=True)


def _extract_json_object(content: str) -> Optional[Dict[str, Any]]:
    """Strip fences / noise and parse the first {...} JSON object."""
    if content is None:
        return None
    text = str(content).strip()
    if not text:
        return None
    # strip ```json ... ```
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        if m:
            text = m.group(1).strip()
    # direct loads
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # regex first balanced-ish {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    blob = m.group(0)
    try:
        obj = json.loads(blob)
        if isinstance(obj, dict):
            return obj
    except Exception:
        # A nested object from truncated JSON is not a valid planner response.
        return None
    return None


# ---------------------------------------------------------------------------
# Demo replay / record cassettes for deterministic offline demos
# ---------------------------------------------------------------------------
import hashlib  # noqa: E402


def _cassette_path(system: str, user: str, model: str, mode: str) -> Path:
    """Return a deterministic cassette path based on request content."""
    here = Path(__file__).resolve().parent
    cassette_dir = here / "demo" / "cassettes"
    cassette_dir.mkdir(parents=True, exist_ok=True)
    payload = f"{mode}|{model}|{system}|{user}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return cassette_dir / f"{digest}.json"


def _load_cassette(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cassette(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _call_llm(system: str, user: str) -> Optional[Dict[str, Any]]:
    """Return parsed JSON dict, or None if LLM unavailable / failed. Never raises."""
    replay_mode = (os.environ.get("DEMO_REPLAY") or "").strip().lower() in ("1", "true", "on")
    try:
        s = _llm_settings()
        try:
            timeout = max(0.1, float(os.environ.get("LLM_TIMEOUT", "60")))
        except (TypeError, ValueError):
            timeout = 60.0
        endpoint_host = urlparse(str(s["api_base"] or "")).hostname or "unconfigured"
        _log_llm(
            f"settings mode={s['mode']!r} model={s['model']!r} "
            f"endpoint_host={endpoint_host!r} credentials="
            f"{'configured' if s['api_key'] else 'missing'} timeout={timeout}s"
        )
        cassette_path = _cassette_path(system, user, s["model"], s["mode"])
        record_mode = (os.environ.get("DEMO_RECORD") or "").strip().lower() in ("1", "true", "on")
        if replay_mode:
            _log_llm(f"replay lookup {cassette_path.name}")
            cached = _load_cassette(cassette_path)
            if cached is None:
                raise FileNotFoundError(
                    f"DEMO_REPLAY=1 but cassette missing: {cassette_path} "
                    f"(system={system[:40]}... user={user[:40]}...)"
                )
            _log_llm(f"replay hit keys={list(cached.keys())}")
            set_llm_last_status("replay")
            return cached
        if s["mode"] == "local":
            payload = {
                "model": s["local_model"],
                "prompt": f"System:\n{system}\n\nUser:\n{user}",
                "stream": False,
                "format": "json",
                "options": {"num_predict": 800, "temperature": 0},
            }
            _log_llm("POST local ollama")
            resp = requests.post(s["ollama_url"], json=payload, timeout=timeout)
            _log_llm(f"ollama status={resp.status_code}")
            if resp.status_code != 200:
                _log_llm("fail reason=http_status_not_200 (local)")
                set_llm_last_status(f"http_{resp.status_code}")
                return None
            data = resp.json()
            parsed = _extract_json_object(data.get("response", ""))
            if parsed is None:
                _log_llm("fail reason=json_extract (local)")
                set_llm_last_status("invalid_json")
                return None
            _log_llm(f"ok local parse keys={list(parsed.keys())}")
            set_llm_last_status("ok")
            if record_mode:
                _save_cassette(cassette_path, parsed)
                _log_llm(f"recorded {cassette_path.name}")
            return parsed

        if not s["api_key"] or not s["api_base"]:
            _log_llm(
                f"fail reason=missing_credentials "
                f"has_key={bool(s['api_key'])} has_base={bool(s['api_base'])}"
            )
            set_llm_last_status("not_configured")
            return None

        headers = {
            "Authorization": f"Bearer {s['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": s["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "4000")),
            "thinking": {
                "type": (os.environ.get("LLM_THINKING", "enabled") or "enabled").strip()
            },
            "reasoning_effort": (
                os.environ.get("LLM_REASONING_EFFORT", "high") or "high"
            ).strip(),
        }

        def post_api() -> Any:
            for attempt in range(2):
                try:
                    return requests.post(
                        s["api_base"], headers=headers, json=payload, timeout=timeout
                    )
                except requests.RequestException:
                    if attempt:
                        raise
                    _log_llm("retry reason=transient_request_error")
            raise RuntimeError("unreachable")

        _log_llm(f"POST api endpoint_host={endpoint_host} model={s['model']}")
        resp = post_api()
        _log_llm(f"api status={resp.status_code}")
        if resp.status_code != 200:
            _log_llm("retry without response_format")
            payload.pop("response_format", None)
            resp = post_api()
            _log_llm(f"retry status={resp.status_code}")
            if resp.status_code != 200:
                _log_llm("fail reason=http_status_not_200 (api)")
                set_llm_last_status(f"http_{resp.status_code}")
                return None
        data = resp.json()
        if "choices" not in data:
            _log_llm(f"fail reason=response_structure_missing_choices keys={list(data.keys())}")
            set_llm_last_status("invalid_response")
            return None
        msg = data["choices"][0].get("message") or {}
        content = msg.get("content") or ""
        parsed = _extract_json_object(content)
        if parsed is None:
            _log_llm("fail reason=json_extract")
            set_llm_last_status("invalid_json")
            return None
        usage = data.get("usage") or {}
        parsed["__llm_usage"] = usage
        parsed["__llm_model"] = data.get("model") or s["model"]
        _log_llm(f"ok api parse keys={list(parsed.keys())}")
        set_llm_last_status("ok")
        if record_mode:
            _save_cassette(cassette_path, parsed)
            _log_llm(f"recorded {cassette_path.name}")
        return parsed
    except Exception as e:
        if replay_mode and isinstance(e, FileNotFoundError):
            raise
        status = "timeout" if "timeout" in type(e).__name__.lower() else "request_failed"
        _log_llm(f"fail reason=exception type={type(e).__name__}")
        set_llm_last_status(status)
        return None


# ---------------------------------------------------------------------------
# Rule-based fallback (offline / eval baseline)
# ---------------------------------------------------------------------------
_FORMAT_HINTS = [
    (["fq.gz", "fastq.gz", "fastq", "原始测序", "原始数据", "测序数据", "reads"], "fq.gz"),
    (["maf", "突变文件", "突变注释", "体细胞突变文件"], "maf"),
    (["bam", "比对", "alignment"], "bam"),
    (["vcf", "变异检测"], "vcf"),
    (["表达矩阵", "tpm", "fpkm", "count矩阵", "count 矩阵", "表达量"], "tsv"),
    (["xlsx", "excel", "表格"], "xlsx"),
    (["xls"], "xls"),
    (["tsv", "表格文件"], "tsv"),
    (["csv"], "csv"),
]

_FUNCTION_HINTS = [
    (["肿瘤突变负荷", "tmb", "突变负荷"], "肿瘤突变负荷生存分析流程"),
    (["体细胞突变景观", "突变景观", "oncoplot", "maf 景观", "MAF 景观"], "WES 体细胞突变 MAF 景观分析流程"),
    (["免疫浸润", "cibersort", "iobr"], "免疫浸润分析 (IOBR CIBERSORT)"),
    (["wgcna", "共表达"], "WGCNA 加权基因共表达网络分析"),
    (["her2", "无进展生存", "pfs"], "HER2 表达与无进展生存期分析"),
    (["驱动基因", "性别分层"], "驱动基因突变频率性别分层分析"),
    (["生存分析"], "生存分析流程"),
    (["无监督聚类", "聚类"], "RNA-seq 无监督聚类分析流程"),
    (["reactome", "通路富集", "kegg"], "差异表达与 Reactome 通路富集分析流程"),
    (["go 富集", "go富集", "差异表达与 go"], "差异表达与 GO 富集分析"),
    (["差异表达"], "差异表达与 GO 富集分析"),
    (["fastq", "转未比对", "ubam", "未比对 bam"], "双端 FASTQ 转未比对 BAM"),
]

_COHORT_HINTS = [
    "食管癌",
    "食管鳞癌",
    "胶质瘤",
    "肝癌",
    "肺癌",
    "结直肠癌",
    "黑色素瘤",
    "乳腺癌",
    "胃癌",
]


def _rule_based_intent(
    nl_text: str, capabilities: List[Dict[str, Any]], degraded: bool = False
) -> Dict[str, Any]:
    try:
        text = nl_text or ""
        text_l = text.lower()

        function_menu = [c["function"] for c in capabilities if c.get("function")]
        target_function = None
        for keys, fn in _FUNCTION_HINTS:
            if any(k.lower() in text_l or k in text for k in keys):
                if fn in function_menu:
                    target_function = fn
                    break
                for m in function_menu:
                    if any(k in m for k in keys if len(k) >= 2):
                        target_function = m
                        break
            if target_function:
                break
        if target_function is None:
            for m in function_menu:
                if m in text:
                    target_function = m
                    break

        input_format = None
        for keys, fmt in _FORMAT_HINTS:
            if any(k.lower() in text_l or k in text for k in keys):
                input_format = fmt
                break
        if input_format is None and target_function is not None:
            for c in capabilities:
                if c["function"] == target_function:
                    prefs = c.get("input_formats") or []
                    non_gen = [f for f in prefs if f not in GENERIC]
                    input_format = non_gen[0] if non_gen else (prefs[0] if prefs else None)
                    break

        cohort = None
        for c in _COHORT_HINTS:
            if c in text:
                cohort = c
                break

        # closed-set validation
        if target_function is not None and target_function not in function_menu:
            target_function = None
        if input_format is not None and input_format not in FORMAT_VOCAB:
            input_format = None

        ambiguous = target_function is None
        return {
            "input_format": input_format,
            "target_function": target_function,
            "cohort": cohort,
            "ambiguous": ambiguous,
            "source": "rule",
            "degraded": bool(degraded),
        }
    except Exception as e:
        _log_llm(f"rule fallback itself failed: {type(e).__name__}: {e}")
        return {
            "input_format": None,
            "target_function": None,
            "cohort": None,
            "ambiguous": True,
            "source": "rule",
            "degraded": True,
        }


def _validate_intent(
    raw: Dict[str, Any], capabilities: List[Dict[str, Any]]
) -> Dict[str, Any]:
    function_menu = {c["function"] for c in capabilities if c.get("function")}
    tf = raw.get("target_function")
    if tf is not None:
        tf = str(tf).strip()
        if tf.lower() in ("null", "none", ""):
            tf = None
    if tf is not None and tf not in function_menu:
        hit = None
        for m in function_menu:
            if tf in m or m in tf:
                hit = m
                break
        tf = hit  # may become None → ambiguous

    fmt = raw.get("input_format")
    if fmt is not None:
        toks = norm_fmt(str(fmt))
        fmt = toks[0] if toks else None
        if fmt is not None and fmt not in FORMAT_VOCAB:
            fmt = None

    cohort = raw.get("cohort")
    if cohort is not None:
        cohort = str(cohort).strip()
        if cohort.lower() in ("null", "none", ""):
            cohort = None

    ambiguous = bool(raw.get("ambiguous", False)) or (tf is None)
    return {
        "input_format": fmt,
        "target_function": tf,
        "cohort": cohort,
        "ambiguous": ambiguous,
        "degraded": False,
    }


def extract_intent(nl_text: str, capabilities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Closed-set intent extraction.
    Prefer LLM; on any failure degrade to rules. Never raises.
    """
    try:
        if not isinstance(nl_text, str):
            nl_text = "" if nl_text is None else str(nl_text)

        if _force_rule():
            _log_llm("FORCE_RULE=1 → skip LLM, use rule")
            return _rule_based_intent(nl_text, capabilities, degraded=True)

        menu_lines = []
        for c in capabilities or []:
            menu_lines.append(
                f"- function={c.get('function')!r} | tool_id={c.get('tool_id')} | "
                f"inputs={c.get('input_formats')} | outputs={c.get('output_formats')}"
            )
        formats = sorted(FORMAT_VOCAB)
        system = (
            "你是生物医学分析意图解析器。必须从给定菜单中闭集选择，禁止自造功能名。\n"
            "输出严格 json，字段: input_format, target_function, cohort, ambiguous。\n"
            "规则:\n"
            "1) target_function 必须是菜单里某个 function 的原文；没有合适的则 target_function=null 且 ambiguous=true。\n"
            "2) input_format 必须归一化到词表之一；用户没说清时按语义推断"
            "（原始测序数据→fq.gz，突变文件/maf→maf，表达矩阵→tsv）。\n"
            "3) cohort 抽癌种字符串，没有则 null。\n"
            "4) 不要输出多余文字。\n"
            f"format 词表: {formats}\n"
            "能力菜单:\n" + "\n".join(menu_lines)
        )
        user = f"用户需求: {nl_text}"

        llm_raw = _call_llm(system, user)
        if llm_raw and isinstance(llm_raw, dict):
            intent = _validate_intent(llm_raw, capabilities)
            intent["source"] = "llm"
            if intent["input_format"] is None and intent["target_function"] is not None:
                for c in capabilities:
                    if c.get("function") == intent["target_function"]:
                        prefs = c.get("input_formats") or []
                        non_gen = [f for f in prefs if f not in GENERIC]
                        intent["input_format"] = (
                            non_gen[0] if non_gen else (prefs[0] if prefs else None)
                        )
                        break
            # re-check format vocab after inference
            if intent["input_format"] is not None and intent["input_format"] not in FORMAT_VOCAB:
                intent["input_format"] = None
            return intent

        _log_llm("degrade → rule fallback")
        return _rule_based_intent(nl_text, capabilities, degraded=True)
    except Exception as e:
        _log_llm(f"extract_intent outer fail: {type(e).__name__}: {e}")
        return _rule_based_intent(nl_text or "", capabilities or [], degraded=True)


# ---------------------------------------------------------------------------
# Orchestration + render
# ---------------------------------------------------------------------------
def render_answer(result: Dict[str, Any], intent: Optional[Dict[str, Any]] = None) -> str:
    """Template render; facts come only from structured result. Never raises."""
    try:
        lines: List[str] = []
        if intent is not None:
            lines.append(
                "理解到的意图: "
                f"input_format={intent.get('input_format')}, "
                f"target_function={intent.get('target_function')}, "
                f"cohort={intent.get('cohort')}, "
                f"ambiguous={intent.get('ambiguous')} "
                f"(source={intent.get('source')}, degraded={intent.get('degraded')})"
            )

        status = result.get("status")
        if status == "ok":
            lines.append("为你推荐以下工具流（按置信优先、路径更短优先）：")
            for i, wf in enumerate(result.get("workflows", []), 1):
                lines.append(
                    f"\n方案 {i}（长度={wf['length']}，low 置信边数={wf['low_confidence_edges']}）："
                )
                for j, step in enumerate(wf["steps"], 1):
                    lines.append(
                        f"  {j}. {step['tool_name']}（{step['tool_id']}）"
                        f"  {step['inputs']} → {step['outputs']}"
                    )
                for hop in wf.get("hops", []):
                    conf = hop["confidence"]
                    note = "；格式通用，可能需人工确认" if conf == "low" else ""
                    lines.append(
                        f"     └ 衔接 {hop['from']} → {hop['to']} "
                        f"via {hop['join_formats']} [{conf}{note}]"
                    )
            if result.get("cohort_note"):
                lines.append(f"\n备注: {result['cohort_note']}")
        elif status == "no_complete_path":
            lines.append("未找到从输入格式到目标功能的完整工具链。")
            if result.get("diagnosis"):
                lines.append(f"诊断: {result['diagnosis']}")
            if result.get("target_tool_details"):
                lines.append("目标工具本身：")
                for t in result["target_tool_details"]:
                    lines.append(
                        f"  - {t['tool_name']}（{t['tool_id']}）"
                        f" 需要 {t['inputs']} → 产出 {t['outputs']}"
                    )
            if result.get("reachable_from_input"):
                lines.append("从当前输入格式能到达的工具：")
                for t in result["reachable_from_input"]:
                    lines.append(
                        f"  - dist={t['distance']} {t['tool_name']}（{t['tool_id']}）"
                        f"  {t['inputs']} → {t['outputs']}"
                    )
            if result.get("cohort_note"):
                lines.append(f"备注: {result['cohort_note']}")
        elif status in ("no_intent", "unknown_format", "no_target", "no_entry"):
            lines.append(result.get("message") or f"无法处理该请求（{status}）。")
            if result.get("hint"):
                lines.append(f"提示: {result['hint']}")
        elif status == "sorry":
            lines.append(result.get("message") or "抱歉,没能处理这个请求")
        else:
            lines.append(result.get("message") or f"未处理状态: {status}")

        fmt = (intent or {}).get("input_format") or result.get("input_format")
        if fmt in GENERIC and status == "ok":
            lines.append(
                f"\n提示: 入口格式 '{fmt}' 属于通用格式，衔接边多为 low 置信，建议人工确认数据是否匹配。"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"抱歉,没能处理这个请求（render 失败: {type(e).__name__}）"


def nl_to_workflow(nl_text: str, kg: Optional[KGTool] = None) -> Dict[str, Any]:
    """
    nl → pipeline router → matched Neo4j pipelines/tools + KG data candidates.
    Outer try/except: never raises to caller.
    """
    return route_pipeline_request(nl_text)


def _legacy_nl_to_workflow(nl_text: str, kg: Optional[KGTool] = None) -> Dict[str, Any]:
    """Legacy Phase-4 path kept for comparison/debugging."""
    own = False
    try:
        if kg is None:
            own = True
            kg = KGTool()
            kg.connect()
            kg.reload()

        if nl_text is None or (isinstance(nl_text, str) and not nl_text.strip()):
            intent = {
                "input_format": None,
                "target_function": None,
                "cohort": None,
                "ambiguous": True,
                "source": "rule",
                "degraded": False,
            }
            result = {
                "status": "no_intent",
                "message": "输入为空，请描述你的数据格式和分析目标。",
                "hint": "例如：我有 maf 文件，想做肿瘤突变负荷生存分析。",
            }
            answer = render_answer(result, intent)
            return {
                "nl": nl_text,
                "intent": intent,
                "capabilities_count": len(kg.list_capabilities()) if kg else 0,
                "result": result,
                "answer": answer,
            }

        caps = kg.list_capabilities()
        intent = extract_intent(nl_text, caps)

        if intent.get("ambiguous") or not intent.get("target_function"):
            # may still have format only
            if intent.get("input_format") and not intent.get("target_function"):
                result = {
                    "status": "no_target",
                    "message": "识别到了输入格式，但没能确定分析目标。",
                    "hint": "请补充想做什么分析，例如生存分析、突变景观、免疫浸润等。",
                    "input_format": intent.get("input_format"),
                }
            elif not intent.get("input_format") and not intent.get("target_function"):
                result = {
                    "status": "no_intent",
                    "message": "没能从这句话里识别出可用的分析意图。",
                    "hint": "请说明数据格式（如 maf / fq.gz / tsv）和想做的分析。",
                }
            else:
                result = {
                    "status": "no_target",
                    "message": "无法从闭集菜单确定目标功能。",
                    "hint": "请换一种说法，或直接点名功能（如免疫浸润、生存分析）。",
                }
        elif not intent.get("input_format"):
            result = {
                "status": "unknown_format",
                "message": "识别到了分析目标，但无法确定输入格式。",
                "hint": "请补充数据格式，例如 maf、fq.gz、tsv。",
                "target_function": intent.get("target_function"),
            }
        else:
            result = kg.recommend_workflow(
                input_format=intent["input_format"],
                target_function=intent["target_function"],
                cohort=intent.get("cohort"),
            )

        answer = render_answer(result, intent)
        return {
            "nl": nl_text,
            "intent": intent,
            "capabilities_count": len(caps),
            "result": result,
            "answer": answer,
        }
    except Exception as e:
        _log_llm(f"nl_to_workflow fatal: {type(e).__name__}: {e}")
        traceback.print_exc()
        intent = {
            "input_format": None,
            "target_function": None,
            "cohort": None,
            "ambiguous": True,
            "source": "rule",
            "degraded": True,
        }
        result = {
            "status": "sorry",
            "message": "抱歉,没能处理这个请求",
            "error_type": type(e).__name__,
        }
        return {
            "nl": nl_text,
            "intent": intent,
            "capabilities_count": 0,
            "result": result,
            "answer": "抱歉,没能处理这个请求",
        }
    finally:
        if own and kg is not None:
            try:
                kg.close()
            except Exception:
                pass
