"""补图 step 3: add dimension / dimension_value to the paired slots so the
mate-swap + sample_role-swap contract checks (workflow_composer
_validate_internal_agent_contract, lines ~2181/2192) can fire.

Values mirror the reviewed apply_slot_model_csv.py exactly:
  fastp/bwa r1/r2  -> dimension=mate,        dimension_value=r1|r2
  samtools bai     -> dimension=sample_role, dimension_value=inherit
  gatk tumor_*     -> dimension=sample_role, dimension_value=tumor
  gatk normal_*    -> dimension=sample_role, dimension_value=normal
Idempotent.
"""
env = {}
for line in open(".env.local"):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")

from neo4j import GraphDatabase

drv = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))

# slot_id -> (dimension, dimension_value)
DIMS = {
    "fastp::input::raw_fastq_read_r1":   ("mate", "r1"),
    "fastp::input::raw_fastq_read_r2":   ("mate", "r2"),
    "fastp::output::clean_fastq_read_r1": ("mate", "r1"),
    "fastp::output::clean_fastq_read_r2": ("mate", "r2"),
    "bwa::input::clean_fastq_read_r1":   ("mate", "r1"),
    "bwa::input::clean_fastq_read_r2":   ("mate", "r2"),
    "samtools::output::bai":             ("sample_role", "inherit"),
    "gatk::input::tumor_bam":            ("sample_role", "tumor"),
    "gatk::input::tumor_bai":            ("sample_role", "tumor"),
    "gatk::input::normal_bam":           ("sample_role", "normal"),
    "gatk::input::normal_bai":           ("sample_role", "normal"),
}

with drv.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
    with s.begin_transaction() as tx:
        for slot_id, (dim, val) in DIMS.items():
            tx.run(
                "MATCH (sl:io_slot {slot_id:$sid}) "
                "SET sl.dimension=$dim, sl.dimension_value=$val",
                sid=slot_id, dim=dim, val=val,
            )
        tx.commit()

with drv.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
    for r in s.run(
        "MATCH (sl:io_slot) WHERE sl.dimension IS NOT NULL AND sl.dimension<>'' "
        "RETURN sl.slot_id AS id, sl.dimension AS d, sl.dimension_value AS v ORDER BY id"
    ):
        print(f"  {r['id']:<40} {r['d']}/{r['v']}")
drv.close()
