import pytestDir

@pytestDir.fixture(scope="session")
def preSetupWork():
    print("browser instance")