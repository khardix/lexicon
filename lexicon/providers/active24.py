# -*- coding: utf-8 -*-
"""Czech registrar Active24 – https://www.active24.cz/"""
from __future__ import absolute_import
from __future__ import print_function
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

#: Default API endpoint if not specified
DEFAULT_API_ENDPOINT = "https://api.active24.com"
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


class UnownedDomain(Exception):
    """The domain is not owned by the authorized user."""


def provider_parser(subparser):
    """Add provider-specific CLI options."""

    subparser.add_argument(
        "--auth-token", help="Specify authentication token for the rest API.",
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

        #: Provider identifier of authorized domain
        self.domain_id = None

        #: Endpoint for all API calls
        self.api_endpoint = DEFAULT_API_ENDPOINT

        #: Authorized requests session
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["Authorization"] = "Bearer {token}".format(
            token=self._get_provider_option("auth_token")
        )

    # ### Helpers ###

    def __assemble_lexicon_record(self, identifier, rtype, name, content):
        """Assemble lexicon record dictionary from constituent parts."""

        record = {
            "type": rtype.upper(),
            "name": name,
            "content": content,
            "ttl": self._get_lexicon_option("ttl") or DEFAULT_TTL,
        }
        if identifier:
            record["id"] = identifier

        return record

    def __normalize_for_lexicon(self, provider_record):
        """Convert provider record dictionary to lexicon record dictionary.

        Arguments:
            provider_record (dict): DNS record dictionary in Active24 format.

        Returns:
            dict: DNS record dictionary in format expected by lexicon.

        Raises:
            UnsupportedRecordType: The record type is not supported by the provider.
        """

        def make_fqdn(name):
            """Active24 always returns the record name without the domain."""

            return ".".join((name, self.domain, ""))

        def extract_content(provider_record, rtype):
            """Active24 names record contents differently for different types."""

            try:
                name = _CONTENT_NAME_MAP[rtype.upper()]
            except KeyError:
                message = "{rtype} record is not supported".format(rtype=rtype)
                raise UnsupportedRecordType(message)

            return provider_record.pop(name)

        rtype = provider_record.pop("type").upper()
        normalized = {
            "id": provider_record.pop("hashId", None),
            "type": rtype,
            "name": make_fqdn(provider_record.pop("name")),
            "ttl": provider_record.pop("ttl"),
            "content": extract_content(provider_record, rtype),
        }
        if provider_record:  # there is something left
            normalized["options"] = {rtype.lower(): provider_record}

        return normalized

    def __normalize_for_provider(self, lexicon_record):
        """Convert lexicon_record dictionary to provider record dictionary.

        Arguments:
            lexicon_record (dict): DNS record in lexicon format.

        Returns:
            (str, dict):
                1. Record type
                2. DNS record dictionary in format expected by the provider.

        Raises:
            UnsupportedRecordType: The record type is not supported by the provider.
        """

        def make_name_prefix(fqdn):
            """Active24 accepts only name prefixes
            and attaches the domain implicitly.
            """

            prefix = fqdn.rstrip(
                "."
            )  # Really *fully* qualified name has a dot at the end

            if prefix.endswith(self.domain):
                end = len(prefix) - len(self.domain)
                prefix = prefix[:end].rstrip(".")

            return prefix

        def query_content_name(rtype):
            """Active24 names different record type contents differently."""

            try:
                return _CONTENT_NAME_MAP[rtype.upper()]
            except KeyError:
                message = "{rtype} record is not supported".format(rtype=rtype)
                raise UnsupportedRecordType(message)

        rtype = lexicon_record["type"]
        normalized = {
            "name": make_name_prefix(lexicon_record["name"]),
            query_content_name(rtype): lexicon_record["content"],
            "ttl": lexicon_record["ttl"],
        }

        if lexicon_record.get("id"):
            normalized["hashId"] = lexicon_record["id"]
        if lexicon_record.get("options"):
            normalized.update(lexicon_record["options"][rtype.lower()])

        return rtype, normalized

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

    # ### Setup ###

    def _authenticate(self):
        """Verify ownership of the modified domain."""

        target_url = "/domains/v1"

        owned_domains = {domain["name"] for domain in self._get(target_url)}
        if self.domain in owned_domains:
            # Active24 uses domain name as identifier
            self.domain_id = self.domain
        else:
            raise UnownedDomain(
                "{domain} is not in list of owned domains".format(domain=self.domain)
            )

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

        # The API reject duplicate entries with code 400, have to check beforehand
        if self._list_records(rtype, name, content):
            return True

        target_url = "/dns/{domain}/{rtype}/v1".format(
            domain=self.domain, rtype=rtype.lower(),
        )

        record = self.__normalize_for_provider(
            self.__assemble_lexicon_record(None, rtype, name, content)
        )
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

        match_type = (lambda r: r["type"] == rtype) if rtype else None
        match_name = (lambda r: r["name"] == name) if name else None
        match_content = (lambda r: r["content"] == content) if content else None

        record_iter = iter(self._get(target_url))

        record_iter = map(self.__normalize_for_lexicon, record_iter)
        record_iter = filter(match_type, record_iter)
        record_iter = filter(match_name, record_iter)
        record_iter = filter(match_content, record_iter)

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
                (lexicon_record,) = self._list_records(rtype, name)
            except ValueError:
                raise Exception("Cannot find exact match, won't update")
        else:
            lexicon_record = self.__assemble_lexicon_record(
                identifier, rtype, name, content
            )

        if rtype:
            lexicon_record["type"] = rtype
        else:
            rtype = lexicon_record["type"]

        if identifier:
            lexicon_record["id"] = identifier
        if name:
            lexicon_record["name"] = name
        if content:
            lexicon_record["content"] = content

        if rtype in _PRIORITY_TYPE_SET:
            priority = self._get_lexicon_option("priority")
        else:
            priority = None

        if priority:
            options = lexicon_record.setdefault("options", {})
            record_options = options.setdefault(rtype.lower(), {})
            record_options["priority"] = priority

        target_url = "/dns/{domain}/{rtype}/v1".format(
            domain=self.domain, rtype=rtype.lower()
        )

        record = self.__normalize_for_provider(lexicon_record)
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
