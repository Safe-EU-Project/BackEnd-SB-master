import subprocess

def run_sql(sql):
    r = subprocess.run(
        ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak", "-c", sql],
        capture_output=True, text=True
    )
    return r.stdout.strip()

# Verify current state
check = run_sql("SELECT u.username, r.name FROM user_entity u JOIN user_role_mapping urm ON u.id=urm.user_id JOIN keycloak_role r ON urm.role_id=r.id WHERE r.name IN ('trainee','trainer');")
print("Current trainee/trainer assignments:")
print(check)

# Parse: check for actual data rows (not just "(0 rows)")
if "(0 rows)" in check:
    print("\nNO ROLES ASSIGNED - assigning now...")
    
    # IDs we already know
    trainee_uuid = "1425f9cb-ceb7-4c0f-8e53-582e0f7be2ca"
    trainer_uuid = "ee5cd884-92b2-463f-b1f7-3cc9b2a515eb"
    nchar_uuid   = "83af1bc1-fb23-40df-b1d0-9a6a8f8b77e3"
    test_uuid    = "6249a441-2ec4-498a-ae10-9f48f283c9f3"
    test_trainee_uuid = "eec386d9-9fce-4889-ba51-181f40bd1c1f"
    
    inserts = [
        (test_trainee_uuid, trainee_uuid, "test_trainee → trainee"),
        (test_uuid,         trainee_uuid, "test → trainee"),
        (nchar_uuid,        trainee_uuid, "nchar → trainee"),
        (nchar_uuid,        trainer_uuid, "nchar → trainer"),
    ]
    
    for user_id, role_id, label in inserts:
        r = run_sql(f"INSERT INTO user_role_mapping (user_id, role_id) VALUES ('{user_id}', '{role_id}') ON CONFLICT DO NOTHING;")
        print(f"  Inserted {label}: {r}")
    
    # Verify again
    final = run_sql("SELECT u.username, r.name FROM user_entity u JOIN user_role_mapping urm ON u.id=urm.user_id JOIN keycloak_role r ON urm.role_id=r.id WHERE r.name IN ('trainee','trainer') ORDER BY u.username, r.name;")
    print("\nFinal state:")
    print(final)
else:
    print("Roles already assigned OK!")
