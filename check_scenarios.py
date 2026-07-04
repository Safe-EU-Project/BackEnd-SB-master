import subprocess

result = subprocess.run(
    ["docker", "exec", "safe_mongodb", "mongosh", "--quiet", "--eval",
     "printjson(db.getSiblingDB('scenario_builder').scenarios.find({},{title:1}).toArray())"],
    capture_output=True, text=True
)
print(result.stdout or result.stderr)

# Also check what databases exist
result2 = subprocess.run(
    ["docker", "exec", "safe_mongodb", "mongosh", "--quiet", "--eval",
     "printjson(db.adminCommand('listDatabases').databases.map(d=>d.name))"],
    capture_output=True, text=True
)
print("DBs:", result2.stdout or result2.stderr)
