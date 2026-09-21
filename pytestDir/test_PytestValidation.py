#Fixtures
import pytest

@pytest.fixture(scope="function")
def preWork():
    print("Setup module")
    return("fail")

@pytest.fixture(scope="module")
def secondWork():
    print("Second Setup module")
    yield #will continue with the test case, and then come back and finish the code
    print("teardown module")

@pytest.mark.smoke
def test_initialCheck(secondWork, preWork):
    print("This is the first test")
    assert preWork == "fail"

@pytest.mark.skip
def test_SecondCheck(preWork, secondWork):
    print("This is the second test")