import urllib.request, json
r = urllib.request.urlopen("http://localhost:6002/openapi.json", timeout=5)
d = json.load(r)
print("LLM API routes:")
for p in d.get("paths", {}):
    print(" ", p)
