"""Demo preflight checks. Run with: python scripts/python/demo_preflight.py"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from runtime_config import initialize_runtime

initialize_runtime()


def check(name: str) -> Tuple[bool, str, Any]:
    """Run a single check and return (ok, message, detail)."""
    if name == "neo4j_connectivity":
        try:
            from neo4j_observability import Neo4jClient
            client = Neo4jClient()
            info = client.health(force=True)
            if not info.get("connected"):
                return False, f"Neo4j 未连通: {info.get('error')}", info
            return True, f"Neo4j 连通 ({info.get('database')}, {info.get('version')}, latency={info.get('latency_ms')}ms)", info
        except Exception as e:
            return False, f"Neo4j 检查异常: {type(e).__name__}: {e}", None

    if name == "neo4j_tool_count":
        try:
            from neo4j_observability import Neo4jClient
            client = Neo4jClient()
            driver = client._get_driver()
            with driver.session(database=client.database, default_access_mode=client._read_access) as session:
                tool_count = session.run(
                    "MATCH (t:Tool) RETURN count(t) AS c"
                ).single()["c"]
                next_count = session.run(
                    "MATCH ()-[r:NEXT]->() RETURN count(r) AS c"
                ).single()["c"]
                data_next = session.run(
                    "MATCH ()-[r:NEXT {kind:'data'}]->() RETURN count(r) AS c"
                ).single()["c"]
                order_next = session.run(
                    "MATCH ()-[r:NEXT {kind:'order'}]->() RETURN count(r) AS c"
                ).single()["c"]
            detail = {"tool_count": tool_count, "next_total": next_count, "data_next": data_next, "order_next": order_next}
            ok = tool_count == 24
            msg = f"工具节点 {tool_count}/24；NEXT 边 {next_count} 条（data {data_next} / order {order_next}）"
            return ok, msg, detail
        except Exception as e:
            return False, f"Neo4j 目录统计异常: {type(e).__name__}: {e}", None

    if name == "llm_config":
        key = os.environ.get("LLM_API_KEY")
        base = os.environ.get("LLM_BASE_URL")
        model = os.environ.get("LLM_MODEL")
        if not key or not base or not model:
            return False, "LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 未全部配置", {"key": bool(key), "base": bool(base), "model": bool(model)}
        return True, f"LLM 配置完整（model={model}）", {"key": bool(key), "base": bool(base), "model": model}

    if name == "llm_ping":
        try:
            import requests
            base = os.environ.get("LLM_BASE_URL", "")
            key = os.environ.get("LLM_API_KEY", "")
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": os.environ.get("LLM_MODEL", "deepseek-v4-pro"),
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            }
            start = time.time()
            resp = requests.post(base, headers=headers, json=payload, timeout=10)
            elapsed = time.time() - start
            if resp.status_code == 200:
                return True, f"LLM 最小请求通 ({elapsed:.2f}s)", {"status": resp.status_code, "elapsed_ms": int(elapsed*1000)}
            return False, f"LLM 最小请求返回 {resp.status_code}", {"status": resp.status_code, "body": resp.text[:200]}
        except Exception as e:
            return False, f"LLM ping 异常: {type(e).__name__}: {e}", None

    if name == "env_local":
        env_path = REPO / ".env.local"
        if not env_path.exists():
            return False, f"{env_path} 不存在", None
        keys = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
        missing = [k for k in keys if not os.environ.get(k)]
        if missing:
            return False, f".env.local 加载后仍缺变量: {', '.join(missing)}", {"missing": missing}
        return True, ".env.local 关键变量已加载", None

    if name == "csv_validate":
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/python/validate_csv.py", "--project-root", str(REPO)],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0:
                return True, "validate_csv.py 通过", {"stdout": proc.stdout.strip()[-300:]}
            return False, f"validate_csv.py 失败: {proc.stderr.strip()[-300:]}", {"stdout": proc.stdout.strip()[-300:], "stderr": proc.stderr.strip()[-300:]}
        except Exception as e:
            return False, f"validate_csv.py 执行异常: {type(e).__name__}: {e}", None

    if name == "app_health":
        import http.client
        import threading
        from app import main as app_main
        # Start server in background thread
        started = threading.Event()
        server_instance = []
        def run_server():
            from http.server import ThreadingHTTPServer
            from app import Handler
            srv = ThreadingHTTPServer(("127.0.0.1", 18080), Handler)
            server_instance.append(srv)
            started.set()
            srv.serve_forever()
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        if not started.wait(5):
            return False, "app.py 启动超时", None
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 18080, timeout=5)
            conn.request("GET", "/api/health")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            conn.close()
            if resp.status == 200:
                data = json.loads(body)
                return True, f"/api/health 正常 (LLM configured={data.get('llm',{}).get('configured')}, Neo4j ok={data.get('neo4j',{}).get('ok')})", data
            return False, f"/api/health 返回 {resp.status}", {"body": body[:200]}
        except Exception as e:
            return False, f"/api/health 请求异常: {type(e).__name__}: {e}", None
        finally:
            if server_instance:
                server_instance[0].shutdown()

    return False, f"未知检查项: {name}", None


CHECKS = [
    ("Neo4j 连通性", "neo4j_connectivity"),
    ("Neo4j 目录计数", "neo4j_tool_count"),
    (".env.local 关键变量", "env_local"),
    ("LLM 配置", "llm_config"),
    ("LLM 最小请求", "llm_ping"),
    ("CSV 校验", "csv_validate"),
    ("app.py /api/health", "app_health"),
]


def main():
    print("=" * 60)
    print("Demo 预检清单")
    print("=" * 60)
    results: List[Dict[str, Any]] = []
    for label, key in CHECKS:
        ok, msg, detail = check(key)
        mark = "✅" if ok else "❌"
        print(f"{mark} {label}: {msg}")
        results.append({"name": label, "ok": ok, "message": msg, "detail": detail})
    all_ok = all(r["ok"] for r in results)
    print("=" * 60)
    print(f"总体: {'全部通过' if all_ok else '存在失败项'}")
    print("=" * 60)
    out_path = REPO / "docs" / "demo_preflight_result.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"详细结果已保存: {out_path}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
