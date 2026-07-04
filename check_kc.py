import subprocess, json

# Try to find admin password from env files
result = subprocess.run(
    ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak", 
     "-c", "SELECT u.username, u.email FROM user_entity u JOIN realm r ON u.realm_id=r.id WHERE r.name='scenariobuilder' LIMIT 20;"],
    capture_output=True, text=True
)
print("USERS:", result.stdout or result.stderr)

# Also try to find roles
result2 = subprocess.run(
    ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak",
     "-c", "SELECT u.username, r.name as role FROM user_entity u JOIN user_role_mapping urm ON u.id=urm.user_id JOIN keycloak_role r ON urm.role_id=r.id JOIN realm realm ON u.realm_id=realm.id WHERE realm.name='scenariobuilder' AND r.client_realm_constraint=realm.id LIMIT 30;"],
    capture_output=True, text=True
)
print("ROLES:", result2.stdout or result2.stderr)
