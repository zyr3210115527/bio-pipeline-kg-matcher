// 1. Tool - HAS_FUNCTION -> Function
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_has_function.csv' AS row
MATCH (t:tool {tool_id: row.tool_id})
MATCH (f:function {function: row.function})
MERGE (t)-[:has_function]->(f);

// 2. Tool - INPUT -> Format
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_has_semantic_input.csv' AS row
MATCH (t:tool {tool_id: row.tool_id})
MATCH (f:format {format: row.format})
MERGE (t)-[:input]->(f);

// 3. Tool - OUTPUT -> Format
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_has_semantic_output.csv' AS row
MATCH (t:tool {tool_id: row.tool_id})
MATCH (f:format {format: row.format})
MERGE (t)-[:output]->(f);

// 4. Tool - NEXT -> Tool
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_relationship.csv' AS row
MATCH (t1:tool {tool_id: row.tool_id})
MATCH (t2:tool {tool_id: row.next_tool_id})
MERGE (t1)-[:next_tool {kind: row.kind}]->(t2);

// 5. Tool - SUITABLE_FOR -> Modal
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_suitable_for_modal.csv' AS row
MATCH (t:tool {tool_id: row.tool_id})
MATCH (m:modal {modal: row.modal})
MERGE (t)-[:suitable_for]->(m);
