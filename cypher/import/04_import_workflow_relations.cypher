// 1. Tool input formats
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_input_format.csv' AS row
MATCH (t:Tool {tool_id: row.tool_id})
MATCH (f:Format {format: row['语义输入格式']})
MERGE (t)-[:INPUT]->(f);

// 2. Tool output formats
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_output_format.csv' AS row
MATCH (t:Tool {tool_id: row.tool_id})
MATCH (f:Format {format: row['语义输出格式']})
MERGE (t)-[:OUTPUT]->(f);

// 3. Tool ordering
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_relationship.csv' AS row
MATCH (t1:Tool {tool_id: row.tool_id})
MATCH (t2:Tool {tool_id: row.next_tool_id})
MERGE (t1)-[:NEXT]->(t2);
