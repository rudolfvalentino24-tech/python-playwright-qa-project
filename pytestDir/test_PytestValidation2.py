#Fixtures
import pytestDir

@pytestDir.mark.smoke
def test_thirdCheck(preSetupWork):
    print("This is the third test")