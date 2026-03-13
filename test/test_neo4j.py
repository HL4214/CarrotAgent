import neo4j
from neo4j import GraphDatabase

# URI examples: "neo4j://localhost", "neo4j+s://xxx.databases.neo4j.io"
URI = "neo4j+ssc://874b625a.databases.neo4j.io"
AUTH = ("neo4j", "Vc1vrxOiD7WsioOmJB0BNGyayT6g6_9dzkdzZvbknOU")

with GraphDatabase.driver(URI,
                          auth=AUTH) as driver:
    driver.verify_connectivity()