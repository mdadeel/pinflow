import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Check if running in test environment
is_test = os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING")

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"] if not is_test else ["10000/minute"],
    storage_uri="memory://",
)

# Custom limits per endpoint category (higher limits for tests)
if is_test:
    UPLOAD_LIMIT = "10000/minute"
    PIPELINE_LIMIT = "10000/minute"
    READ_LIMIT = "10000/minute"
    WRITE_LIMIT = "10000/minute"
    HEALTH_LIMIT = "10000/minute"
else:
    UPLOAD_LIMIT = "10/minute"
    PIPELINE_LIMIT = "2/minute"
    READ_LIMIT = "200/minute"
    WRITE_LIMIT = "50/minute"
    HEALTH_LIMIT = "60/minute"
