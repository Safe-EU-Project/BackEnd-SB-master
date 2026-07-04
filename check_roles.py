import urllib.request, urllib.parse, json

# Get admin token
data = urllib.parse.urlencode({
    "client_id": "admin-cli",
    "username": "admin",
    "password": "admin",
    "grant_type": "password"
}).encode()
r = urllib.request.urlopen("http://localhost:8080/realms/master/protocol/openid-connect/token", data, timeout=5)
token = json.load(r)["access_token"]

# List users in scenariobuilder realm
req = urllib.request.Request(
    "http://localhost:8080/admin/realms/scenariobuilder/users",
    headers={"Authorization": f"Bearer {token}"}
)
users = json.load(urllib.request.urlopen(req, timeout=5))
print(f"Found {len(users)} users:")
for u in users:
    print(f"  {u['username']} ({u.get('email','')}) - enabled:{u['enabled']}")

    # Get roles for each user
    req2 = urllib.request.Request(
        f"http://localhost:8080/admin/realms/scenariobuilder/users/{u['id']}/role-mappings/realm",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        roles = json.load(urllib.request.urlopen(req2, timeout=5))
        role_names = [r["name"] for r in roles]
        print(f"    roles: {role_names}")
    except Exception as e:
        print(f"    roles: error {e}")
