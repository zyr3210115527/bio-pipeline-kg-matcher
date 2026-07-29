"""补图: translate 师姐 reference catalog's paired/dual-end slot model into the
live (hand-maintained) runtime graph so paired-WES + dual-end validation passes.

Idempotent (MERGE). Adds:
  - fastp / gatk  input_variants_json + input_aliases_json + exactly_one_variant
  - fastp  raw_fastq_read_r1/_r2 (in) + clean_fastq_read_r1/_r2 (out)
  - bwa    clean_fastq_read_r1/_r2 (in)
  - samtools  bai (out)
  - gatk   tumor_bam/tumor_bai/normal_bam/normal_bai/interval_list (in)
  - variant / variant_alias_for on the pre-existing single slots (raw_fastq_read,
    clean_fastq_read, sorted_dedup_bam) so alias-collapse + single-variant work.
Property names + values mirror data/update728/csv/catalog exactly.
Backup of prior state: scratchpad/graph_toolslot_backup.json
"""
import os

env = {}
for line in open(".env.local"):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")

from neo4j import GraphDatabase

drv = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))

# ---- tool-level variant metadata (exactly the catalog values) ----
TOOL_META = {
    "fastp": {
        "input_variants_json": '{"single_end":["raw_fastq_read_r1"],"paired_end":["raw_fastq_read_r1","raw_fastq_read_r2"]}',
        "input_aliases_json": '{"raw_fastq_read":"raw_fastq_read_r1"}',
        "exactly_one_variant": True,
    },
    "gatk": {
        "input_variants_json": '{"single":["sorted_dedup_bam"],"paired":["tumor_bam","tumor_bai","normal_bam","normal_bai"]}',
        "input_aliases_json": "{}",
        "exactly_one_variant": True,
    },
}

# ---- new slots: (tool, direction, slot_name, required, artifact, variant, variant_alias_for) ----
NEW_SLOTS = [
    ("fastp", "input",  "raw_fastq_read_r1",  False, "raw_fastq_read",  "single_end|paired_end", ""),
    ("fastp", "input",  "raw_fastq_read_r2",  False, "raw_fastq_read",  "paired_end",            ""),
    ("fastp", "output", "clean_fastq_read_r1", False, "clean_fastq_read", "",                     ""),
    ("fastp", "output", "clean_fastq_read_r2", False, "clean_fastq_read", "",                     ""),
    ("bwa",   "input",  "clean_fastq_read_r1", False, "clean_fastq_read", "",                     ""),
    ("bwa",   "input",  "clean_fastq_read_r2", False, "clean_fastq_read", "",                     ""),
    ("samtools", "output", "bai",             False, "bai",             "",                      ""),
    ("gatk",  "input",  "tumor_bam",          False, "sorted_dedup_bam", "paired",               ""),
    ("gatk",  "input",  "tumor_bai",          False, "bai",             "paired",                ""),
    ("gatk",  "input",  "normal_bam",         False, "sorted_dedup_bam", "paired",               ""),
    ("gatk",  "input",  "normal_bai",         False, "bai",             "paired",                ""),
    ("gatk",  "input",  "interval_list",      True,  "interval_list",   "",                      ""),
]

# ---- property updates on existing single slots (alias / variant) ----
EXISTING_SLOT_UPDATES = [
    # slot_id, set required, set variant, set variant_alias_for
    ("fastp::input::raw_fastq_read",  False, "",       "raw_fastq_read_r1"),
    ("fastp::output::clean_fastq_read", False, "",     "clean_fastq_read_r1"),
    ("bwa::input::clean_fastq_read",  False, "",       "clean_fastq_read_r1"),
    ("gatk::input::sorted_dedup_bam", False, "single", ""),
]

with drv.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
    with s.begin_transaction() as tx:
        # 1) tool variant metadata
        for tool, meta in TOOL_META.items():
            tx.run(
                "MATCH (t:tool_id {tool_id:$tool}) SET t.input_variants_json=$iv, "
                "t.input_aliases_json=$ia, t.exactly_one_variant=$eov",
                tool=tool, iv=meta["input_variants_json"],
                ia=meta["input_aliases_json"], eov=meta["exactly_one_variant"],
            )
        # 2) new slots + artifact edges (mirror sister-tool-csv provenance)
        for tool, direction, name, required, artifact, variant, alias in NEW_SLOTS:
            slot_id = f"{tool}::{direction}::{name}"
            tx.run(
                "MATCH (t:tool_id {tool_id:$tool}) "
                "MERGE (sl:io_slot {slot_id:$slot_id}) "
                "SET sl:IOSlot, sl.tool_id=$tool, sl.slot_name=$name, sl.direction=$direction, "
                "    sl.required=$required, sl.wdl_type='File', sl.catalog_source='sister-tool-csv', "
                "    sl.description=$name, sl.variant=$variant, sl.variant_alias_for=$alias "
                "WITH t, sl "
                "CALL { WITH t, sl "
                "  WITH t, sl WHERE $direction='input' "
                "  MERGE (t)-[:HAS_INPUT_SLOT]->(sl) } "
                "WITH t, sl "
                "CALL { WITH t, sl "
                "  WITH t, sl WHERE $direction='output' "
                "  MERGE (t)-[:HAS_OUTPUT_SLOT]->(sl) } "
                "WITH sl "
                "MERGE (a:artifact_type {artifact_type:$artifact}) SET a:ArtifactType "
                "WITH sl, a "
                "CALL { WITH sl, a "
                "  WITH sl, a WHERE sl.direction='input' "
                "  MERGE (sl)-[:REQUIRES]->(a) } "
                "CALL { WITH sl, a "
                "  WITH sl, a WHERE sl.direction='output' "
                "  MERGE (sl)-[:PRODUCES]->(a) } "
                "RETURN sl.slot_id",
                tool=tool, slot_id=slot_id, name=name, direction=direction,
                required=required, variant=variant, alias=alias, artifact=artifact,
            )
        # 3) existing single-slot alias/variant updates
        for slot_id, required, variant, alias in EXISTING_SLOT_UPDATES:
            tx.run(
                "MATCH (sl:io_slot {slot_id:$slot_id}) "
                "SET sl.required=$required, sl.variant=$variant, sl.variant_alias_for=$alias",
                slot_id=slot_id, required=required, variant=variant, alias=alias,
            )
        tx.commit()

# ---- verify ----
with drv.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
    print("=== fastp ===", dict(s.run(
        "MATCH (t:tool_id{tool_id:'fastp'}) RETURN t.input_variants_json AS iv, t.exactly_one_variant AS e").single()))
    print("=== gatk ===", dict(s.run(
        "MATCH (t:tool_id{tool_id:'gatk'}) RETURN t.input_variants_json AS iv, t.exactly_one_variant AS e").single()))
    for tool in ("fastp", "bwa", "gatk", "samtools"):
        rows = [dict(r) for r in s.run(
            "MATCH (t:tool_id{tool_id:$t})-[e:HAS_INPUT_SLOT|HAS_OUTPUT_SLOT]->(sl:io_slot) "
            "RETURN type(e) AS e, sl.slot_name AS n, sl.variant AS v ORDER BY e,n", t=tool)]
        print(f"[{tool}]", [(r["e"][4:7], r["n"], r["v"]) for r in rows])
drv.close()
