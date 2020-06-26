"""Integration tests for Active24"""

from unittest import TestCase

import pytest

from lexicon.tests.providers.integration_tests import IntegrationTestsV2

# Re-usable marks
no_record_sets = pytest.mark.skip(reason="Active24 does not support record sets")


# Hook into testing framework by inheriting unittest.TestCase and reuse
# the tests which *each and every* implementation of the interface must
# pass, by inheritance from integration_tests.IntegrationTests
class Active24ProviderTests(TestCase, IntegrationTestsV2):
    """Integration tests for Active24 provider"""

    provider_name = "active24"
    domain = "khardix.cz"

    def _filter_headers(self):
        return ["Authorization"]

    @no_record_sets
    def test_provider_when_calling_create_record_multiple_times_should_create_record_set(
        self,
    ):
        pass

    @no_record_sets
    def test_provider_when_calling_list_records_should_handle_record_sets(self):
        pass

    @no_record_sets
    def test_provider_when_calling_delete_record_with_record_set_name_remove_all(self):
        pass

    @no_record_sets
    def test_provider_when_calling_delete_record_with_record_set_by_content_should_leave_others_untouched(
        self,
    ):
        pass
