"""Provider for Active24 registrar"""
from __future__ import absolute_import

import logging

import requests

from lexicon.providers.base import Provider as BaseProvider

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin


LOGGER = logging.getLogger(__name__)

NAMESERVER_DOMAINS = ["active24.cz", "active24.sk"]

CONTENT_FIELD_MAP = {
    "A": "ip",
}


def adapt_content(record):
    """Adapt provider response to expected API."""

    content_field = CONTENT_FIELD_MAP.get(record["type"])
    if not content_field:
        return record

    record["content"] = record.pop(content_field)
    return record


def provider_parser(subparser):
    """Add provider-specific CLI options."""

    subparser.description = "Active24 DNS registrar"

    subparser.add_argument(
        "--auth-token", help="Provide authentication token for DNS editing.",
    )
    subparser.add_argument(
        "--api-endpoint",
        default="https://api.active24.com/",
        help="Communicate with the specified API endpoint.",
    )


class Provider(BaseProvider):
    """Interact with Active24 registrar."""

    def __init__(self, config):
        super(Provider, self).__init__(config)

        #: The target API endpoint
        self._endpoint = self._get_provider_option("api_endpoint")

        #: Pre-authorized HTTP session
        token = self._get_provider_option("auth_token")
        if not token:
            raise RuntimeError("No authentication token provided")
        self._http_session = requests.Session()
        self._http_session.headers = {
            "Authorization": "Bearer {token}".format(token=token),
            "Content-Type": "application/json",
        }

    def _request(self, action="GET", url="/", data=None, query_params=None):
        """Make an authorized request to the REST API."""

        if data is None:
            data = {}
        if query_params is None:
            query_params = {}

        response = self._http_session.request(
            action,
            urljoin(base=self._endpoint, url=url),
            params=query_params,
            json=data,
        )
        response.raise_for_status()
        return response.json()

    def _list_records(self, rtype=None, name=None, content=None):
        """List all records.

        Arguments:
            type, name and content are used to filter records.

        Returns: An empty list if no records found.
        """

        def filter_rtype(record):
            return record["type"] == rtype

        def filter_content(record):
            return record["content"] == content

        url = "/dns/{domain}/records/v1".format(domain=self.domain)

        # Name is accepted beforehand
        query_params = {"name": name} if name is not None else {}

        response = self._request("GET", url, query_params=query_params)
        response = filter(filter_rtype, response)
        response = map(adapt_content, response)
        response = filter(filter_content, response)

        return list(response)

    def _authenticate(self, *_):
        pass
