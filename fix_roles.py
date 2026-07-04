import subprocess

# Check all realm roles available
result = subprocess.run(
    ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak",
     "-c", "SELECT r.name FROM keycloak_role r JOIN realm realm ON r.realm_id=realm.id WHERE realm.name='scenariobuilder' ORDER BY r.name;"],
    capture_output=True, text=True
)
print("ALL REALM ROLES:", result.stdout)

# Check composite roles (default-roles might include trainee)
result2 = subprocess.run(
    ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak",
     "-c", "SELECT cr.name as composite_role, r.name as child_role FROM composite_role c JOIN keycloak_role cr ON c.composite=cr.id JOIN keycloak_role r ON c.child_role=r.id JOIN realm realm ON cr.realm_id=realm.id WHERE realm.name='scenariobuilder' LIMIT 30;"],
    capture_output=True, text=True
)
print("COMPOSITE ROLES:", result2.stdout)

# Check all users and ALL their role mappings including composite
result3 = subprocess.run(
    ["docker", "exec", "keycloak_postgres", "psql", "-U", "keycloak", "-d", "keycloak",
     "-c", "SELECT u.username, r.name as role, r.client_role FROM user_entity u JOIN user_role_mapping urm ON u.id=urm.user_id JOIN keycloak_role r ON urm.role_id=r.id JOIN realm realm ON u.realm_id=realm.id WHERE realm.name='scenariobuilder' LIMIT 40;"],
    capture_output=True, text=True
)
print("ALL ROLE MAPPINGS (incl client roles):", result3.stdout)
