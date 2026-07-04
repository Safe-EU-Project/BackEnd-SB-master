import subprocess, json

r = subprocess.run(
    ["curl", "-s", "http://localhost:6002/openapi.json"],
    capture_output=True, text=True
)
d = json.loads(r.stdout)
print("LLM service routes:")
for path in sorted(d["paths"].keys()):
    print(" ", path)
