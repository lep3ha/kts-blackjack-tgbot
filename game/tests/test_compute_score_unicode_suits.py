from app.services.blackjack_service import compute_score


def test_compute_score_handles_unicode_suits_face_cards():
    score, blackjack = compute_score(["K♥️", "A♣️"])
    assert score == 21
    assert blackjack is True


def test_compute_score_handles_unicode_suits_number_cards():
    score, blackjack = compute_score(["10♠️", "7♦️"])
    assert score == 17
    assert blackjack is False
