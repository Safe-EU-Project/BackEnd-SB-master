class EnvConfig:
    # for the docker network
    BASE_AUTH = "http://backend:8000/v1/user"
    CREATE_SCENARIO_URL = "http://backend:8000/v1/scenario/user"
    UPDATE_SCENARIO_URL = "http://backend:8000/v1/scenario/incidents"
    
    # for localhost backend with Docker frontend (for development)
    # BASE_AUTH = "http://host.docker.internal:8000/api/v1/user"
    # CREATE_SCENARIO_URL = "http://host.docker.internal:8000/api/v1/scenario/user"
    # UPDATE_SCENARIO_URL = "http://host.docker.internal:8000/api/v1/scenario/incidents"