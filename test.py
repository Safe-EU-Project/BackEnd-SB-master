import requests


# env_llm = get_LLM_settings()
LLM_BASE_URL= "http://10.240.138.254:6002" # hardoced for testing

class ClientLLM():
    
    def __init__():
        pass

    @staticmethod
    def get_llm_response(instructions):
        # logger.info('Scenario Service Sends Request at LLM Service to get a new scenario ...')
        # API configuration
        # BASE_URL = env_llm.LLM_BASE_URL
        QUERY_ENDPOINT = LLM_BASE_URL + "/api/v1/query"
        # Query request
        query_data = {
            "query": instructions,
            "top_k": 20,
            "use_reranking": True,
            "use_hybrid": False
        }

        # Make request
        response = requests.post(QUERY_ENDPOINT, json=query_data)

        # Check response
        if response.status_code == 200:
            result = response.json()
            # set the message and continue for transformations:
            # logger.info(f"Response: {response.status_code} - {result['answer']}\n")
            # logger.info('---------------------------------------------------------')
            print(result['answer'])
            return result['answer']
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"LLM response is not available", #TODO FIX IT
            )

    @staticmethod
    def send_back_scenario_for_feedback_loop(fixed_scenario:str):
        # API configuration
        BASE_URL = env_llm.LLM_BASE_URL
        INGEST_ENDPOINT = f"{BASE_URL}/api/v1/ingest_scenario"


        # Prepare request
        ingest_data = {
            "content": fixed_scenario
        }

        print("Sending scenario to ingestion endpoint...")
        print("-" * 60)

        # Make request
        response = requests.post(INGEST_ENDPOINT, json=ingest_data)

        # Check response
        if response.status_code == 200:
            return response.json()
            print("SUCCESS!")
            print(f"Status: {result['status']}")
            print(f"Message: {result['message']}")
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Details: {response.text}")


if __name__ == "__main__":
    ClientLLM.get_llm_response('chat create a datacenter cyber attack')