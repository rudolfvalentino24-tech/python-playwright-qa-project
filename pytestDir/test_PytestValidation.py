#Fixtures
import pytestDir

@pytestDir.fixture(scope="function")
def preWork():
    print("Setup module")
    return("fail")

@pytestDir.fixture(scope="module")
def secondWork():
    print("Second Setup module")
    yield #will continue with the test case, and then come back and finish the code
    print("teardown module")

@pytestDir.mark.smoke
def test_initialCheck(secondWork, preWork):
    print("This is the first test")
    assert preWork == "fail"

@pytestDir.mark.skip
def test_SecondCheck(preWork, secondWork):
    print("This is the second test")