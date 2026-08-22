"""图谱可达性闸门。

用途只有一个：把"图谱连不上"和"代码坏了"分开。

0822 排查时，图谱一断，套件里报出来的是满屏「未知 tool_id: star」「NEXT 不允许」
「0 != 1」——看着像目录坏了、像编排逻辑坏了，实际全是 bolt 连不上的连锁反应。
一次误判就够浪费半天。

闸门只卡一个确凿前提：**工具目录非空**。工具目录只从图谱来（见
RegisteredMethodCatalog 的 docstring），目录为空时，任何关于工具链的断言都不可能
有意义——这是前提失效，不是"测试太严"。

刻意不做的事：
  - 不因为"某条断言失败"就跳过。那是拿 skip 掩盖 bug，正是这套代码一直在修的
    那类问题。闸门之后仍然失败的，就是真问题。
  - 不静默跳过。skip 理由里必须带上图谱地址和具体错误，且明说**不等于通过**。
"""

import os
import unittest

_CACHE = {}


def graph_catalog_state():
    """返回 (工具数, 说明)。构造一次缓存复用——每次连不上都要等一个超时。"""
    if "state" not in _CACHE:
        try:
            from workflow_composer import RegisteredMethodCatalog

            catalog = RegisteredMethodCatalog()
            count = len(catalog.all_methods)
            if count:
                note = f"图谱工具目录 {count} 个工具"
            else:
                state = "未连接" if not catalog.connected else "已连接但未返回工具"
                note = f"图谱{state}（{catalog.error or 'unknown'}）"
            _CACHE["state"] = (count, note)
        except Exception as exc:  # 构造本身就炸，同样属于图谱不可达
            _CACHE["state"] = (0, f"图谱目录构造失败：{type(exc).__name__}: {exc}")
    return _CACHE["state"]


def require_graph_catalog():
    """在 setUpClass 里调用。目录为空则 skip 并说清原因。"""
    count, note = graph_catalog_state()
    if count:
        return
    uri = os.environ.get("NEO4J_URI", "(未设 NEO4J_URI)")
    raise unittest.SkipTest(
        f"{note}；地址 {uri}。本套件断言的是工具链编排，目录为空时无从判断，"
        f"因此跳过——**跳过不等于通过**，图谱恢复后必须重跑。"
    )
