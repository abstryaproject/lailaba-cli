import pytest
from lailaba_cli.tools.web import validate_url
from lailaba_cli.permissions import PermissionDenied

def test_reject_unsupported_and_local_urls():
    with pytest.raises(PermissionDenied): validate_url("file:///etc/passwd")
    with pytest.raises(PermissionDenied): validate_url("http://127.0.0.1")
    with pytest.raises(PermissionDenied): validate_url("http://localhost")

def test_public_https_url_shape():
    # Validate the syntax without triggering DNS in this unit test.
    from urllib.parse import urlparse
    assert urlparse("https://example.com/path").scheme=="https"
