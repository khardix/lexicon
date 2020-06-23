# -*- coding: utf-8 -*-
"""Czech registrar Active24 – https://www.active24.cz/"""
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from datetime import timedelta

import requests

from . import base

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

#: FQDN patters of the provider name servers
NAMESERVER_DOMAINS = ["ns.active24.cz", "ns.active24.sk"]

#: Default TTL if not specified by the user
DEFAULT_TTL = timedelta(hours=1).seconds

#: Content name by record type
_CONTENT_NAME_MAP = {
    "A": "ip",
    "AAAA": "ip",
    "CAA": "caaValue",
    "CNAME": "alias",
    "MX": "mailserver",
    "NS": "nameServer",
    "SRV": "target",
    "SSHFP": "text",
    "TLSA": "hash",
    "TXT": "text",
}
#: Set of record types which accept priority setting
_PRIORITY_TYPE_SET = {"MX", "SRV"}

_LOG = logging.getLogger(__name__)


class UnsupportedRecordType(RuntimeError):
    """The record type is not supported by the provider."""


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


def get_content_name(record_type):
    """Retrieve name of the content field for the respective record type.

    Arguments:
        record_type (str): The type of the record to query.

    Returns:
        str: Name of the content field.

    Raises:
        UnsupportedRecordType:
            The record_type does not name a supported record type.
    """

    try:
        return _CONTENT_NAME_MAP[record_type.upper()]
    except KeyError:
        message = "{rtype} record is not supported".format(rtype=record_type)
        raise UnsupportedRecordType(message)


def normalize_record(provider_record):
    """Convert from provider response to format expected by lexicon.

    Returns:
        dict: Normalized record.

    Raises:
        UnsupportedRecordType: The record type is not supported.
    """

    rtype = provider_record["type"].upper()
    content = get_content_name(rtype)

    normalized = {"type": rtype}
    normalized["id"] = provider_record.pop("hashId")
    normalized["name"] = provider_record.pop("name")
    normalized["ttl"] = provider_record.pop("ttl")
    normalized["content"] = provider_record.pop(content)
    if provider_record:
        normalized["options"] = {rtype.lower(): provider_record}

    return normalized


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
        try:
            return response.json()
        except ValueError:  # No JSON content
            return {}

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

        target_url = "/dns/{domain}/{rtype}/v1".format(
            domain=self.domain, rtype=rtype.lower(),
        )

        record = {
            "name": name,
            get_content_name(rtype): content,
            "ttl": self._get_lexicon_option("ttl") or DEFAULT_TTL,
        }
        if rtype in _PRIORITY_TYPE_SET:
            record["priority"] = self._get_lexicon_option("priority") or 0

        self._post(target_url, data=record)
        return True

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

        record_iter = iter(self._get(target_url))
        if rtype:
            record_iter = filter(lambda r: r["type"] == rtype, record_iter)
        record_iter = map(normalize_record, record_iter)
        if content:
            record_iter = filter(lambda r: r["content"] == content, record_iter)

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

        if not all((identifier, rtype, name, content)):
            try:
                (matching,) = self._list_records(rtype, name)
            except ValueError:
                raise Exception("Cannot find exact match, won't update")

        if rtype is None:
            rtype = matching["type"]

        target_url = "/dns/{domain}/{rtype}/v1".format(
            domain=self.domain, rtype=rtype.lower()
        )

        record = {
            "hashId": identifier or matching["id"],
            "name": name or matching["name"],
            get_content_name(rtype): content or matching["content"],
            "ttl": self._get_lexicon_option("ttl") or matching["ttl"],
        }
        if rtype in _PRIORITY_TYPE_SET:
            record["priority"] = (
                self._get_lexicon_option("priority")
                or matching["options"][rtype.lower()]["priority"]
            )

        _LOG.debug("Putting record: %s", record)
        self._put(target_url, data=record)
        return True

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

        if not identifier:
            try:
                (matching,) = self._list_records(rtype, name)
            except ValueError:
                _LOG.warning("Cannot find exact match, won't delete")
                return False
            else:
                identifier = matching["id"]

        target_url = "/dns/{domain}/{hashId}/v1".format(
            domain=self.domain, hashId=identifier
        )

        self._delete(target_url)
        return True
