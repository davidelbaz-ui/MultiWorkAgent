import integration_connection_test


def test_not_connected_skips_api():
    result = integration_connection_test.test_integration_connection(
        provider_slug="github",
        auth_type="oauth",
        status="pending",
        credentials=None,
    )
    assert not result.ok
    assert result.probe == "connection_status"


def test_unknown_provider_no_probe():
    result = integration_connection_test.test_integration_connection(
        provider_slug="unknown-vendor-xyz",
        auth_type="api_key",
        status="connected",
        credentials={"api_key": "test-key"},
    )
    assert not result.ok
    assert result.probe == "unsupported"
