"""A1: Probe system behavior under three LLM failure modes."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUERY = "我有双端 FASTQ 想做 RNA-seq 上游分析,需要表达矩阵和基因计数"

SCENARIOS = [
    ("empty_key", {"LLM_API_KEY": "", "DEEPSEEK_API_KEY": ""}),
    ("timeout", {"LLM_TIMEOUT": "0.001"}),
    ("http_5xx", {"LLM_BASE_URL": "https://httpbin.org/status/500"}),
]

PY_CODE = f'''
import json
import sys
sys.path.insert(0, {str(REPO)!r})
from pipeline_router import route_pipeline_request

result = route_pipeline_request({QUERY!r}, top_k=3)
planner = result.get("planner_metadata") or {{}}
intent = result.get("intent") or {{}}
out = {{
    "schema_version": result.get("schema_version"),
    "selection_status": result.get("selection_status"),
    "intent_source": intent.get("source"),
    "intent_degraded": intent.get("degraded"),
    "planner_metadata_status": planner.get("status"),
    "planner_metadata_used": planner.get("used"),
    "planner_metadata_calls": planner.get("calls"),
    "candidate_count": result.get("candidate_count"),
    "unsupported_reason": result.get("unsupported_reason"),
}}
print(json.dumps(out, ensure_ascii=False))
'''


def main():
    out = {}
    env_base = os.environ.copy()
    for name, overrides in SCENARIOS:
        env = env_base.copy()
        env.update(overrides)
        print(f"=== scenario: {name} ===")
        proc = subprocess.run(
            [sys.executable, "-c", PY_CODE],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
        )
        stderr = proc.stderr.strip()
        if stderr:
            print(stderr[-500:])
        if proc.returncode != 0:
            out[name] = {"error": proc.stderr.strip()[-500:]}
        else:
            out[name] = json.loads(proc.stdout.strip().splitlines()[-1])
        print(json.dumps(out[name], ensure_ascii=False, indent=2))

    with open("docs/a1_llm_failure_probe.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved docs/a1_llm_failure_probe.json")


if __name__ == "__main__":
    main()
