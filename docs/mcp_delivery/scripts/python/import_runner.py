#!/usr/bin/env python3

import argparse
from pathlib import Path
from neo4j import GraphDatabase


def read_cypher_file(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def split_cypher_statements(cypher_text: str):
    """
    Split a cypher file into individual statements by semicolon.
    This is a simple splitter suitable for current prototype files,
    assuming no semicolons appear inside string literals.
    """
    lines = []
    for line in cypher_text.splitlines():
        stripped = line.strip()

        # skip full-line comments and empty lines
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue

        lines.append(line)

    cleaned = "\n".join(lines)
    statements = [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]
    return statements


def execute_statement(session, statement: str, file_name: str, index: int):
    print(f"    [STMT {index}] {statement.splitlines()[0][:100]}")
    result = session.run(statement)
    result.consume()


def execute_cypher_file(driver, database: str, file_path: Path):
    print(f"[RUN] {file_path}")
    cypher = read_cypher_file(file_path)
    statements = split_cypher_statements(cypher)

    if not statements:
        print(f"[SKIP] {file_path.name} (no executable statements)")
        return

    with driver.session(database=database) as session:
        for idx, statement in enumerate(statements, start=1):
            execute_statement(session, statement, file_path.name, idx)

    print(f"[OK ] {file_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Run Neo4j import cypher pipeline.")
    parser.add_argument("--project-root", required=True, help="Project root path")
    parser.add_argument("--uri", required=True, help="Neo4j URI, e.g. bolt://localhost:7687")
    parser.add_argument("--user", required=True, help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--database", default="neo4j", help="Neo4j database name")
    parser.add_argument("--run-clear", action="store_true", help="Run clear graph before import")

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()

    cypher_files = []

    if args.run_clear:
        cypher_files.append(project_root / "cypher" / "import" / "00_clear.cypher")

    cypher_files.extend([
        project_root / "cypher" / "schema" / "constraints.cypher",
        project_root / "cypher" / "schema" / "indexes.cypher",
        project_root / "cypher" / "import" / "01_import_reference.cypher",
        project_root / "cypher" / "import" / "02_import_entities.cypher",
        project_root / "cypher" / "import" / "03_import_ontology_relations.cypher",
        project_root / "cypher" / "import" / "04_import_workflow_relations.cypher",
        project_root / "cypher" / "import" / "05_validation.cypher",
    ])

    for file_path in cypher_files:
        if not file_path.exists():
            raise FileNotFoundError(f"Cypher file not found: {file_path}")

    print("============================================")
    print("Neo4j Import Runner")
    print("============================================")
    print(f"Project root : {project_root}")
    print(f"Neo4j URI    : {args.uri}")
    print(f"Database     : {args.database}")
    print(f"Run clear    : {args.run_clear}")
    print("============================================")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    try:
        for file_path in cypher_files:
            execute_cypher_file(driver, args.database, file_path)

        print("============================================")
        print("Import pipeline completed successfully.")
        print("============================================")

    finally:
        driver.close()


if __name__ == "__main__":
    main()