# -*- coding: utf-8 -*-
"""Czech registrar Active24 – https://www.active24.cz/"""
from __future__ import absolute_import
from __future__ import unicode_literals

import requests

from . import base

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

#: FQDN patters of the provider name servers
NAMESERVER_DOMAINS = ["ns.active24.cz", "ns.active24.sk"]


def provider_parser(subparser):
    """Add provider-specific CLI options."""

    subparser.add_argument(
        "--auth-token", help="Specify authentication token for the rest API.",
    )
    subparser.add_argument(
        "--api-endpoint",
        default="https://api.active24.com",
        help="Specify the API endpoint to connect to.",
    )


class Provider(base.Provider):
    """Interface to the Active24 REST API."""

    def __init__(self, config):
        super(Provider, self).__init__(config)

        self.api_endpoint = self._get_provider_option("api_endpoint")

        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"

    # ### Setup and helpers ###

    def _authenticate(self):
        """Authenticate any future requests to the API."""

        token = self._get_provider_option("auth_token")
        self.session.headers["Authorization"] = "Bearer {token}".format(token=token)

    def _request(self, action="GET", url="/", data=None, query_params=None):
        """Request data from the API.

        Arguments:
            action (str): Which HTTP verb to use for the request.
            url (str): A URL path (relative to an endpoint) to the request.
            data (dict,list): A JSON payload to attach to the request.
            query_params (dict): Additional query parameters.

        Returns:
            dict: Decoded JSON response.

        Raises:
            requests.HTTPError: The API responded with no-success status code.
            requests.ConnectionError: The API endpoint could not be reached.
        """

        if data is None:
            data = {}
        if query_params is None:
            query_params = {}

        target_url = urljoin(self.api_endpoint, url, allow_fragments=False)

        response = self.session.request(
            action, target_url, params=query_params, json=data
        )
        response.raise_for_status()
        return response.json()

    # ### CRUD methods ###

    def _create_record(self, rtype, name, content):
        """Create new record.

        If an identical record already exists, do nothing.

        Arguments:
            rtype (str): Record type.
            name (str): Record FQDN.
            content (Any): Appropriate record content (i.e. IP address).

        Returns:
            True: Record was created (or already existed).
        """

    def _list_records(self, rtype=None, name=None, content=None):
        """List all records that match the arguments.

        Arguments:
            rtype (str): Only list records of this type.
            name (str): Only list records for this FQDN.
            content (Any): Only list records with this content.

        Returns:
            list: Matching records in canonical format.
        """

        target_url = "/dns/{domain}/records/v1".format(domain=self.domain)

        record_iter = self._get(target_url)
        if rtype:
            record_iter = filter(lambda r: r["type"] == rtype, record_iter)
        # FIXME: Normalize
        # FIXME: Filter by content

        return list(record_iter)

    def _update_record(self, identifier, rtype=None, name=None, content=None):
        """Update (or create) a record.

        Arguments:
            identifier (str): Provider-specific unique ID.
            rtype (str): Type of the record.
            name (str): FQDN of the record.
            content (Any): Content of the record.

        Returns:
            True: Record was sucessfully updated.
        """

    def _delete_record(self, identifier, rtype=None, name=None, content=None):
        """Remove existing record.

        If the record does not exist, do nothing.

        Arguments:
            identifier (str): Provider-specific unique ID.
            rtype (str): Type of the record.
            name (str): FQDN of the record.
            content (Any): Content of the record.

        Returns:
            True: Record was sucessfully updated.
        """
