import logging
import os
import platform
import threading
import time
import urllib.parse
from contextlib import contextmanager
from functools import lru_cache
from typing import Any
from typing import Dict
from typing import List

import requests
from requests.adapters import HTTPAdapter
from requests.adapters import Retry

logger = logging.getLogger(__name__)


class Session:
    MAX_COROUTINE_COUNT = 8
    ANNOTATION_VERSION = "V1.00"

    def __init__(
        self,
        token: str,
        team_id: int,
        api_url: str = "https://api.superannotate.com",
        auth_type: str = "sdk",
        version: str = "4.4.20",
    ):
        self._token = token
        self._team_id = team_id
        self._api_url = api_url
        self._auth_type = auth_type
        self._verify_ssl = os.environ.get("VERIFY_SSL", True)
        self.default_headers = {
            "Authorization": self._token,
            "authtype": self._auth_type,
            "Content-Type": "application/json",
            "User-Agent": f"Python-SDK-Version: {version}; Python: {platform.python_version()};"
            f"OS: {platform.system()}; Team: {self._team_id}",
        }
        self.ASSETS_PROVIDER_VERSION = os.environ.get(
            "SA_ASSETS_PROVIDER_VERSION", "v3.01"
        )
        self.ASSETS_PROVIDER_URL = os.environ.get(
            "SA_ASSETS_PROVIDER_URL", "https://assets-provider.superannotate.com/api/"
        )

    @property
    def assets_provider_url(self):
        if self._api_url == "https://api.devsuperannotate.com":
            return f"https://assets-provider.devsuperannotate.com/api/{self.ASSETS_PROVIDER_VERSION}/"
        return self.ASSETS_PROVIDER_URL

    @property
    def team_id(self):
        return self._team_id

    @lru_cache(maxsize=32)
    def _get_cached_session(self, thread_id, ttl=None):  # noqa
        del ttl
        del thread_id
        retries = Retry(total=3, backoff_factor=0.1, status_forcelist=[502, 503, 504])

        session = requests.Session()
        session.mount("http://", HTTPAdapter(max_retries=retries))  # noqa
        session.mount("https://", HTTPAdapter(max_retries=retries))
        session.headers.update(self.default_headers)
        return session

    def _get_session(self):
        return self._get_cached_session(
            thread_id=threading.get_ident(), ttl=round(time.time() / 360)
        )

    @property
    def safe_api(self):
        """
        Context manager which will handle requests calls.
        """

        @contextmanager
        def safe_api():
            """
            Context manager which handles Requests error.
            """
            try:
                yield None
            except (requests.RequestException, ConnectionError) as exc:
                raise Exception(f"Unknown exception: {exc}.")  # todo update exception

        return safe_api

    def _request(self, url: str, method: str, session, retried: int = 0, **kwargs):
        with self.safe_api():
            req = requests.Request(
                method=method,
                url=url,
                **kwargs,
            )
            prepared = session.prepare_request(req)
            response = session.send(request=prepared, verify=self._verify_ssl)

        if response.status_code == 404 and retried < 3:
            time.sleep(retried * 0.1)
            return self._request(
                url, method=method, session=session, retried=retried + 1, **kwargs
            )
        if response.status_code > 299:
            logger.debug(
                f"Got {response.status_code} response from backend: {response.text}"
            )
        return response

    def _build_url(self, url):
        if not url.startswith("htt"):
            return urllib.parse.urljoin(self._api_url, url)
        return url

    def request(
        self,
        url,
        method="get",
        data=None,
        json=None,
        headers=None,
        params=None,
        files=None,
        build_url=True,
    ) -> requests.Response:
        if build_url:
            url = self._build_url(url)
        kwargs = {"params": {"team_id": self._team_id}}
        if data:
            kwargs["data"] = data
        if json:
            kwargs["json"] = json
        if params:
            kwargs["params"].update(params)
        session = self._get_session()
        if files and session.headers.get("Content-Type"):
            del session.headers["Content-Type"]
        session.headers.update(headers if headers else {})
        response = self._request(url, method, session=session, **kwargs)
        if files:
            session.headers.update(self.default_headers)
        return response

    def paginate(
        self,
        url: str,
        chunk_size: int = 2000,
        query_params: Dict[str, Any] = None,
    ) -> List[dict]:
        offset = 0
        total = []
        splitter = "&" if "?" in url else "?"

        while True:
            _url = f"{url}{splitter}offset={offset}"
            _response = self.request(_url, method="get", params=query_params)
            if _response.ok:
                response_data = _response.json()
                if isinstance(response_data, list):
                    payload = response_data
                else:
                    payload = response_data["data"]
                if payload:
                    total.extend(payload)
                else:
                    break
                data_len = len(payload)
                offset += data_len
                if data_len < chunk_size or response_data["count"] - offset < 0:
                    break
            else:
                break
        if not _response.ok:
            _response.raise_for_status()
        return total
