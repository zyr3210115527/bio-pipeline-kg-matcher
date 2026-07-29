"""Run key Cypher queries for the paired-sample exploration appendix."""
import json
import os
import runtime_config  # loads .env.local before os.environ is read
from collections import Counter
from neo4j import GraphDatabase

URI = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD")


def run_query(driver, query):
    with driver.session(database="neo4j") as session:
        result = session.run(query)
        return [dict(record) for record in result]


def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    results = {}
    try:
        # 1. Specimen type combo counts (sort combos in Python)
        raw = run_query(driver, """
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WITH i, collect(DISTINCT s.specimen_types) AS combo
WHERE size(combo) > 1
RETURN i.individual_id AS individual_id, combo
""")
        combo_counts = Counter(tuple(sorted(c)) for c in [r["combo"] for r in raw])
        results["specimen_combo_counts"] = [
            {"combo": list(k), "individual_count": v}
            for k, v in combo_counts.most_common()
        ]

        # 2. Per-combo study + file format
        def combo_detail(types):
            return run_query(driver, f"""
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.specimen_types IN {types!r}
WITH i, collect(DISTINCT s.specimen_types) AS types_seen
WHERE size(types_seen) > 1
WITH i
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(f:t1)
RETURN s2.study_accession AS study, f.format AS format, count(*) AS cnt
ORDER BY study, format
""")

        results["pst_peri_files"] = combo_detail(["Patient Solid Tissue", "Peritumoral"])
        results["pst_organoid_files"] = combo_detail(["Patient Solid Tissue", "Organoid"])
        results["pst_blood_files"] = combo_detail(["Patient Solid Tissue", "Blood"])

        # 3. Strategy per relevant study (sample.strategy)
        results["study_strategy"] = run_query(driver, """
MATCH (s:sample)
WHERE s.study_accession IN ['HRA000873','HRA000021','HRA006499','HRA000122','HRA000071','HRA007169','HRA001748','HRA001749','HRA001272','HRA003107']
RETURN s.study_accession AS study, s.strategy AS strategy, count(*) AS n
ORDER BY study, n DESC
""")

        # 4. HRA000873 / HRA000021 sample count distribution
        results["hra000873_sample_dist"] = run_query(driver, """
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA000873'
WITH i, count(DISTINCT s) AS sample_count
RETURN sample_count, count(i) AS individual_count ORDER BY sample_count
""")
        results["hra000021_sample_dist"] = run_query(driver, """
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA000021'
WITH i, count(DISTINCT s) AS sample_count
RETURN sample_count, count(i) AS individual_count ORDER BY sample_count
""")

        # 5. HRA006499 _T/_N naming individuals
        results["hra006499_tn_individuals"] = run_query(driver, """
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA006499' AND s.sample_name =~ '.*_[TN]$'
WITH i, collect(DISTINCT s.specimen_types) AS types
RETURN count(DISTINCT i) AS tn_individual_count, types
""")
        results["hra006499_tn_files"] = run_query(driver, """
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA006499' AND s.sample_name =~ '.*_[TN]$'
WITH i
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(f:t1)
RETURN f.format AS format, count(*) AS cnt ORDER BY cnt DESC
""")
        results["hra006499_tn_specimens"] = run_query(driver, """
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA006499' AND s.sample_name =~ '.*_[TN]$'
RETURN s.specimen_types AS specimen_types, count(*) AS n ORDER BY n DESC
""")

        # 6. Organoid / Bone Marrow / Blood attribution
        results["organoid_studies"] = run_query(driver, """
MATCH (s:sample)
WHERE s.specimen_types = 'Organoid'
RETURN s.study_accession AS study, count(*) AS n ORDER BY n DESC
""")
        results["bone_marrow_studies"] = run_query(driver, """
MATCH (s:sample)
WHERE s.specimen_types = 'Bone Marrow'
RETURN s.study_accession AS study, count(*) AS n ORDER BY n DESC
""")
        results["blood_studies"] = run_query(driver, """
MATCH (s:sample)
WHERE s.specimen_types = 'Blood'
RETURN s.study_accession AS study, count(*) AS n ORDER BY n DESC
""")

        # Co-occurring types (only for samples actually linked to individuals)
        for typ in ["Organoid", "Blood"]:
            results[f"{typ.lower()}_cooccurring"] = run_query(driver, f"""
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.specimen_types = '{typ}'
WITH i
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)
RETURN s2.specimen_types AS co_type, count(*) AS n ORDER BY n DESC
""")

        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
