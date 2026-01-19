import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        # Only mark items in this directory (tests/integration)
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
