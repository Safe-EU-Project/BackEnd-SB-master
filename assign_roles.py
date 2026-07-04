import subprocess

def run_sql(sql):
    r = subprocess.run(
        ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak", "-c", sql],
        capture_output=True, text=True
    )
    return r.stdout.strip() or r.stderr.strip()

# Assign trainee role to: test_trainee, test, nchar (so all can access trainee features)
# Assign trainer role to: nchar (so the main dev can also access trainer features)

# Get role IDs
trainee_id = run_sql("SELECT id FROM keycloak_role WHERE name='trainee' AND realm_id=(SELECT id FROM realm WHERE name='scenariobuilder');")
trainer_id = run_sql("SELECT id FROM keycloak_role WHERE name='trainer' AND realm_id=(SELECT id FROM realm WHERE name='scenariobuilder');")
print("trainee role row:", trainee_id)
print("trainer role row:", trainer_id)

# Get user IDs
users = run_sql("SELECT id, username FROM user_entity WHERE realm_id=(SELECT id FROM realm WHERE name='scenariobuilder') AND username NOT LIKE 'service-account%';")
print("users:", users)

# Parse role IDs - extract just the UUID
def extract_uuid(psql_output):
    lines = [l.strip() for l in psql_output.split('\n') if l.strip() and '---' not in l and 'id' not in l.lower()[:5] and l.strip() != '(1 row)']
    return lines[0].strip() if lines else None

trainee_uuid = extract_uuid(trainee_id)
trainer_uuid = extract_uuid(trainer_id)
print(f"trainee uuid: {trainee_uuid}")
print(f"trainer uuid: {trainer_uuid}")

if not trainee_uuid or not trainer_uuid:
    print("ERROR: could not parse role UUIDs")
    exit(1)

# Get user UUIDs
nchar_id_raw = run_sql("SELECT id FROM user_entity WHERE username='nchar' AND realm_id=(SELECT id FROM realm WHERE name='scenariobuilder');")
test_id_raw = run_sql("SELECT id FROM user_entity WHERE username='test' AND realm_id=(SELECT id FROM realm WHERE name='scenariobuilder');")
test_trainee_id_raw = run_sql("SELECT id FROM user_entity WHERE username='test_trainee' AND realm_id=(SELECT id FROM realm WHERE name='scenariobuilder');")

nchar_uuid = extract_uuid(nchar_id_raw)
test_uuid = extract_uuid(test_id_raw)
test_trainee_uuid = extract_uuid(test_trainee_id_raw)

print(f"nchar uuid: {nchar_uuid}")
print(f"test uuid: {test_uuid}")
print(f"test_trainee uuid: {test_trainee_uuid}")

def assign_role(user_uuid, role_uuid, username, role_name):
    if not user_uuid or not role_uuid:
        print(f"SKIP: missing uuid for {username}/{role_name}")
        return
    # Check if already assigned
    check = run_sql(f"SELECT count(*) FROM user_role_mapping WHERE user_id='{user_uuid}' AND role_id='{role_uuid}';")
    if '1' in check or '2' in check:
        print(f"ALREADY: {username} has {role_name}")
        return
    result = run_sql(f"INSERT INTO user_role_mapping (user_id, role_id) VALUES ('{user_uuid}', '{role_uuid}');")
    print(f"ASSIGNED {role_name} to {username}: {result}")

# Assign trainee to all test users + nchar
assign_role(test_trainee_uuid, trainee_uuid, "test_trainee", "trainee")
assign_role(test_uuid, trainee_uuid, "test", "trainee")
assign_role(nchar_uuid, trainee_uuid, "nchar", "trainee")

# Assign trainer to nchar (for trainer features)
assign_role(nchar_uuid, trainer_uuid, "nchar", "trainer")

print("\nDone! Verifying...")
result = run_sql("""
SELECT u.username, r.name as role 
FROM user_entity u 
JOIN user_role_mapping urm ON u.id=urm.user_id 
JOIN keycloak_role r ON urm.role_id=r.id 
JOIN realm realm ON u.realm_id=realm.id 
WHERE realm.name='scenariobuilder' AND r.name IN ('trainee','trainer')
ORDER BY u.username, r.name;
""")
print("Final role assignments:", result)
