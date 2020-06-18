"""Czech registrar Active24 – https://www.active24.cz/"""
from __future__ import absolute_import
from __future__ import unicode_literals

from . import base

#: FQDN patters of the provider name servers
NAMESERVER_DOMAINS = []


def provider_parser(subparser):
    """Add provider-specific CLI options."""


class Provider(base.Provider):
    """Interface to the Active24 REST API."""

    # ### Setup and helpers ###

    def _authenticate(self):
        """Authenticate any future requests to the API."""

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

    def _list_records(self, rtype=None, name=None, content=None):
        """List all records that match the arguments.

        Arguments:
            rtype (str): Only list records of this type.
            name (str): Only list records for this FQDN.
            content (Any): Only list records with this content.

        Returns:
            list: Matching records in canonical format.
        """

        return []

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
