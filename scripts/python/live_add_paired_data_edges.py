"""补图 step 2: add the paired-mate `data` NEXT edges that the reviewed
tool_relationship.csv defines but the live single-slot graph lacked.

  fastp   -> bwa   : clean_fastq_read_r1 -> clean_fastq_read_r1
                     clean_fastq_read_r2 -> clean_fastq_read_r2
  samtools-> gatk  : sorted_dedup_bam -> tumor_bam
                     bai              -> tumor_bai
                     sorted_dedup_bam -> normal_bam
                     bai              -> normal_bai

These are ADDITIONAL parallel NEXT edges alongside the existing single-mate
edges (fastp.clean_fastq_read->bwa.clean_fastq_read, samtools.sorted_dedup_bam
->gatk.sorted_dedup_bam), so single-end + paired chains both validate.
MERGE key = (source, output, input) to keep them distinct. Idempotent.
Property shape mirrors existing curated-next-csv edges exactly.
"""
env = {}
for line in open(".env.local"):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")

from neo4j import GraphDatabase

drv = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))

# (source_tool, target_tool, output, input)
DATA_EDGES = [
    ("fastp", "bwa", "clean_fastq_read_r1", "clean_fastq_read_r1"),
    ("fastp", "bwa", "clean_fastq_read_r2", "clean_fastq_read_r2"),
    ("samtools", "gatk", "sorted_dedup_bam", "tumor_bam"),
    ("samtools", "gatk", "bai", "tumor_bai"),
    ("samtools", "gatk", "sorted_dedup_bam", "normal_bam"),
    ("samtools", "gatk", "bai", "normal_bai"),
]

with drv.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
    with s.begin_transaction() as tx:
        for src, tgt, out, inp in DATA_EDGES:
            tx.run(
                "MATCH (a:tool_id {tool_id:$src}), (b:tool_id {tool_id:$tgt}) "
                "MERGE (a)-[e:NEXT {source:'curated-next-csv', output:$out, input:$inp}]->(b) "
                "SET e.kind='data', e.reviewed=true, e.review_version='2026-07-29'",
                src=src, tgt=tgt, out=out, inp=inp,
            )
        tx.commit()

with drv.session(database=env.get("NEO4J_DATABASE", "neo4j")) as s:
    for r in s.run(
        "MATCH (a:tool_id)-[e:NEXT {source:'curated-next-csv'}]->(b:tool_id) "
        "WHERE a.tool_id IN ['fastp','samtools'] AND e.kind='data' "
        "RETURN a.tool_id AS s, b.tool_id AS t, e.output AS o, e.input AS i ORDER BY s,t,i"
    ):
        print(f"  {r['s']:<9}-> {r['t']:<9} {r['o']} -> {r['i']}")
drv.close()
