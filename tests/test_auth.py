from pain_tracker.auth import verify_password


def test_correct_password():
    assert verify_password("correct horse", "correct horse")


def test_wrong_password():
    assert not verify_password("wrong", "correct horse")
    assert not verify_password("correct horse ", "correct horse")


def test_empty_expected_never_matches():
    assert not verify_password("", "")
    assert not verify_password("anything", "")


def test_unicode_passwords():
    assert verify_password("pässwörd✓", "pässwörd✓")
    assert not verify_password("passwörd", "pässwörd")
