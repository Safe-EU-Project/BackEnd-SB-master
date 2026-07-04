import requests
import time
from typing import Optional
from env import EnvConfig

''' some custom exceptions:'''
# here we define an exception, in the case the refresh
# token is expired, that cant do, auto refresh, so
# catching the exception, will redirect the user into
# log in page
class AuthException(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

'''User Client class'''
class AuthClient:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, session: Optional[requests.Session] = None):
        self.username = username
        self.password = password
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: Optional[float] = None
        self.session = session or requests.Session()

    def login(self) -> None:
        if not self.username or not self.password:
            raise RuntimeError("Username and password required for login")
        url = f"{EnvConfig.BASE_AUTH}/login"
        resp = self.session.post(url, json={"username": self.username, "password": self.password})
        if resp.status_code != 200:
            raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text}")
        data = resp.json()
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in")
        if expires_in:
            self.token_expiry = time.time() + int(expires_in)

    def refresh(self) -> None:
        if not self.refresh_token:
            raise RuntimeError("No refresh token available.")
        url = f"{EnvConfig.BASE_AUTH}/refresh"
        resp = self.session.post(url, json={"refresh_token": self.refresh_token})
        if resp.status_code != 200:
            raise AuthException(f"refresh failed: {resp.text}", resp.status_code)
        data = resp.json()
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        expires_in = data.get("expires_in")
        if expires_in:
            self.token_expiry = time.time() + int(expires_in)

    def _ensure_token(self):
        if not self.access_token:
            if not self.username or not self.password:
                raise RuntimeError("No access token and no credentials available")
            self.login()
        if self.token_expiry and time.time() >= (self.token_expiry - 60):
            self.refresh()

    def _auth_headers(self):
        self._ensure_token()
        return {"Authorization": f"Bearer {self.access_token}"}

    def request_with_auto_refresh(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers())
        resp = self.session.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            self.refresh()
            headers = kwargs.pop("headers", {})
            headers.update(self._auth_headers())
            resp = self.session.request(method, url, headers=headers, **kwargs)
        return resp

    ''''''
    # SCENARIO METHODS
    ''''''
    def create_scenario(self, scenario_name: str, instructions: str) -> dict:
        body = {"scenario_name": scenario_name, "instructions": instructions}
        resp = self.request_with_auto_refresh("POST", EnvConfig.CREATE_SCENARIO_URL, json=body)
        if not resp.ok:
            raise RuntimeError(f"Create scenario failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def get_scenario(self) -> dict:
        resp = self.request_with_auto_refresh("GET", EnvConfig.CREATE_SCENARIO_URL)
        if not resp.ok:
            raise RuntimeError(f"get scenario failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def update_feedback_scenario(self, context: dict, scenario_id: str):
        resp = self.request_with_auto_refresh(
            "PATCH",
            f"{EnvConfig.UPDATE_SCENARIO_URL}/{scenario_id}",
            json={"context": context},
        )
        if not resp.ok:
            raise RuntimeError(f"update scenario failed ({resp.status_code}): {resp.text}")
        return resp.json()