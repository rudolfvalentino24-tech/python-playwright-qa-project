import pytest

@pytest.fixture(scope="session")
def preSetupWork():
    print("browser instance")