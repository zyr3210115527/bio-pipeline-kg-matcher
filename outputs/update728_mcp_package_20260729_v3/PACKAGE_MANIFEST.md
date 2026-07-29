# Package Manifest

文件数（不含本 manifest）: 50  
内容清单 fingerprint: `95af1af0652efe7d877d6424ff41f3c2529a38cb7edac7695c64594591e2ad4b`  
`PACKAGE_MANIFEST.md` 因自引用不能包含自身稳定 hash。

| Path | Bytes | SHA-256 | Purpose |
|---|---:|---|---|
| `96_case_business_validation.json` | 1090 | `d67016a3cb0df8863ceb8cc802e9f8a29956981ad0457e099b5bfa66a4291546` | 机器可读 manifest/验证证据/回放磁带 |
| `96_case_business_validation_live.json` | 37265 | `1965a867492ea10653075477460d136451511bfd64666c36795d6fcf2a9e65ba` | 机器可读 manifest/验证证据/回放磁带 |
| `app/.env.local.example` | 629 | `c46ac86065bea5c90d29b87e7d7998f61a485df2835977035502ad04cf5bc4a5` | 可启动 MCP 应用代码或依赖 |
| `app/app.py` | 10835 | `03a6f02871a4e09a22b5fc3ef2bbe92b9bc5ab097d74898993af640742cbff7a` | 可启动 MCP 应用代码或依赖 |
| `app/config/data_matcher_diff_allowlist.json` | 620 | `fe692a2b1d9730985d71ab56d58b6e1209c6786cc9b190e4973406d20b065e7a` | 运行时验证/allowlist 配置 |
| `app/config/datagraph_representation_allowlist.json` | 1001 | `5d9187a8838a3011a03d8ebcea2e63bcb04756e955ebfca49466af211a9f195c` | 运行时验证/allowlist 配置 |
| `app/config/knowledge_card_execution_contracts.json` | 10495 | `ca1dac037a0ffb06f472465d9b5415ed6016b95c65916ca9d1cd1e87e7051e36` | 运行时验证/allowlist 配置 |
| `app/config/question_tool_data_benchmark.json` | 31288 | `52c3adb894edf4f15353fec506165f42cb0bb8c762582f3b26505ca64d397eab` | 运行时验证/allowlist 配置 |
| `app/config/unified_graph_expectations.json` | 1007 | `fefcdef5ca789046cd78d5a7b330f5ed9de14bc1aa214d1d64083aa68fb29871` | 运行时验证/allowlist 配置 |
| `app/data/csv/catalog/artifact_type.csv` | 3779 | `7e0417d9a2ab08209808c4c0acc21535c9015e8eaf9703fbca6f89887900455c` | CSV 回退/双读基准数据 |
| `app/data/csv/catalog/format.csv` | 1260 | `33327916fcd3d55b8fe7961589d7cdee938bd4c27d23913352f78e692e5fdc2d` | CSV 回退/双读基准数据 |
| `app/data/csv/catalog/function.csv` | 5588 | `644d4dcf5c9185042a4b86a3e216fff6df2dd31fa504d2684246dfc2fede6d6d` | CSV 回退/双读基准数据 |
| `app/data/csv/catalog/io_slot.csv` | 20459 | `ef5b67a3c51c1ea8f5e09c91b13f93bf6036d560eead8c7e75a9dbc3a55fa20c` | CSV 回退/双读基准数据 |
| `app/data/csv/catalog/relationships.csv` | 43344 | `8b6174e9b8573bff5f786c68bb7be2e2339f315316f5a4674fc1ba7d95f43bee` | CSV 回退/双读基准数据 |
| `app/data/csv/catalog/tool_id.csv` | 6608 | `a59f3056ea3ec20c8eb10365856219c74cef8546001a5b6eef0e16c23503bb7b` | CSV 回退/双读基准数据 |
| `app/data/csv/entities/tool.csv` | 3144 | `b7867e3bf84da642e787fc2a8495b356716eed4e3c28ef8bcdbc03cc5a584636` | CSV 回退/双读基准数据 |
| `app/data/csv/relations/tool_has_function.csv` | 570 | `cfbadb94db29978647dce8855dc9e65fc8b29ba3a73cedc50808fa996d2ac28d` | CSV 回退/双读基准数据 |
| `app/data/csv/relations/tool_input_format.csv` | 759 | `a25703157112262c928b73dacc24b83056046c7fdbdd08ffd974c75ea7979908` | CSV 回退/双读基准数据 |
| `app/data/csv/relations/tool_output_format.csv` | 542 | `afc3164dc30c0faf1a8b0ea3b88674cde909e28dad04e97c4b719f18878df211` | CSV 回退/双读基准数据 |
| `app/data/csv/relations/tool_relationship.csv` | 944 | `247f435b1e3d1c710d48add130b00625d5f53e835216b18a3672244a4db0025b` | CSV 回退/双读基准数据 |
| `app/data_matcher/__init__.py` | 187 | `f8c2ec1bfdfa9bcaef0472b73579c8ba2c7652de30374789a0c714e316b1e734` | 数据 matcher 实现 |
| `app/data_matcher/base.py` | 593 | `e675b859260ce6e5ecaf9314cf3223d9bc56b83b535c868fc68502c227eede36` | 数据 matcher 实现 |
| `app/data_matcher/comparison.py` | 6572 | `105ce2831dd84e5e0045cd357aeac271952378e6c0a3bf4cfb32f84cee868acd` | 数据 matcher 实现 |
| `app/data_matcher/csv_matcher.py` | 146 | `2e23ca43daece5a8cbeff106c7c1013492d051826e8bc2c308a5d711c80ea1ae` | 数据 matcher 实现 |
| `app/data_matcher/dual_read.py` | 4684 | `27444653b1981762cc414290b660cb280f2723a09468249595fee33e3cd4a075` | 数据 matcher 实现 |
| `app/data_matcher/expectations.py` | 1858 | `aa3b5e332a54051c25402cb295e5966d7a019386302f164d6a5b7377b3ee999d` | 数据 matcher 实现 |
| `app/data_matcher/factory.py` | 880 | `9aef58610402ba83bb6a901202a500ea3f4665447e9b40ac19822a989dece624` | 数据 matcher 实现 |
| `app/data_matcher/neo4j_matcher.py` | 12592 | `a9e252cf48acf7df88d30b531f2a12137fc3aa33928b75b6f33c88d1f9242d71` | 数据 matcher 实现 |
| `app/docs/mcp_smoke_cassette.json` | 130327 | `80bd368c738baf0726841dbdb95ded0663e2825db7042592cacbabefb23c9bfb` | 可启动 MCP 应用代码或依赖 |
| `app/intent.py` | 27707 | `edc9152638e053556b1b4fecd86fe1b7d6b5cdbe6014620b513024f865859a27` | 可启动 MCP 应用代码或依赖 |
| `app/knowledge_card_execution.py` | 17888 | `c2dd3f62c0c6b8647ae0d095433d4109eeac04e1ed5fd9fb3f8237cbcad3ebc3` | 可启动 MCP 应用代码或依赖 |
| `app/neo4j_observability.py` | 15722 | `55a07a606c72db812ef7251c3c80357daa0f1f38857163e5ea5aaf2033894c40` | 可启动 MCP 应用代码或依赖 |
| `app/pipeline_router.py` | 67112 | `70768435ff73d9cd1749a94eafd5c8c5161a0835e505bf2ef507c51b8e638dcf` | 可启动 MCP 应用代码或依赖 |
| `app/question_benchmark.py` | 1525 | `171d203c88791117b703270cbcd44cf9dcf077d6ede1df834216abc1e9126038` | 可启动 MCP 应用代码或依赖 |
| `app/requirements-llm.txt` | 18 | `dfb599a9b86d5de859901751a5562b7103217f4de74f4313c95998ea422c345a` | 可启动 MCP 应用代码或依赖 |
| `app/requirements-neo4j.txt` | 14 | `dde2002ae887a9ca82ba77438ab23457add81683aa5b61281786328b81b3c338` | 可启动 MCP 应用代码或依赖 |
| `app/runtime_config.py` | 4439 | `b358ada0136f8b506709666e3adbb2e1e388f20ce2a7014bf46468c91ecc0ca7` | 可启动 MCP 应用代码或依赖 |
| `app/scripts/python/mcp_smoke_test.py` | 9502 | `c9a237a39c654fc479b6ea73fb0b0da2890a7e451658a83479668e9725be54c9` | 可启动 MCP 应用代码或依赖 |
| `app/scripts/python/sync_neo4j_tool_catalog.py` | 22336 | `c4fc9c15d3a98e5fb1b6d3c41bd683c36cd95da8341fa0512b53e5f0bc329c0b` | 可启动 MCP 应用代码或依赖 |
| `app/scripts/python/validate_real_backend.py` | 11194 | `6554b300f43a92645ea2dfb6fd9f5c88831995c1db5c1b41688bd56d400b925b` | 可启动 MCP 应用代码或依赖 |
| `app/server.py` | 43023 | `daba1980f89213f50cfe2afa77faa527738ee5dfcb65ff732795a0d7ba616ccf` | 可启动 MCP 应用代码或依赖 |
| `app/test_real_backend_agent_contract.py` | 2825 | `822097b550c9b8fda3e7646698807580acb474fa686c0e43ef4456a69fcb1a8a` | 可启动 MCP 应用代码或依赖 |
| `app/workflow_composer.py` | 100478 | `2b7c8e77f24e9f5a03d51ec446e721acc16c066508c34c91623c9909bc3c56f9` | 可启动 MCP 应用代码或依赖 |
| `backend_required_changes_zh.md` | 7819 | `8e974d643101e57d9b656ce0c858175e6657518d079665855898d322ae261832` | 交付说明或验证报告 |
| `integration_guide_zh.md` | 4185 | `90969840f16cae19b56070b863a31986dc028824a5abc5d0f17bcd77b57b80e5` | 交付说明或验证报告 |
| `mcp_output_json_instance.json` | 1849 | `a7a03d5b99019040de92ed40c564f3d9ab00e1a8ff2b481549cada278f7f1bf5` | 机器可读 manifest/验证证据/回放磁带 |
| `mcp_stdio_smoke_result.json` | 130327 | `d9dcccd1fb2c639ee129421b5a33654471857c2c2d0465e29d508eb18ee9f621` | 机器可读 manifest/验证证据/回放磁带 |
| `package_manifest_zh.md` | 2147 | `5f579a2ca0f684f35af385a9918617132e2706270813fb0e13a5ac6a992fba18` | 交付说明或验证报告 |
| `package_smoke_runtime.json` | 130327 | `80bd368c738baf0726841dbdb95ded0663e2825db7042592cacbabefb23c9bfb` | 机器可读 manifest/验证证据/回放磁带 |
| `real_backend_validation.json` | 65446 | `6a6f824403b64e53eee9055a358c8c71c7f00bd280d417c5d9f554473f1473a2` | 机器可读 manifest/验证证据/回放磁带 |
