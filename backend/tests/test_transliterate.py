"""Hindi in English letters: same words, same language, never translated."""

import pytest

from app.pipeline.transliterate import has_devanagari, to_roman


@pytest.mark.parametrize(("hindi", "roman"), [
    ("हाँ बोलिए", "haan boliye"),
    ("गलती से होगा या बच्चों ने कर दिया होगा", "galti se hoga ya bachchon ne kar diya hoga"),
    ("मैं जान सकती हूँ कि क्या इश्यू था?", "main jaan sakti hoon ki kya ishyu tha?"),
    ("नहीं हमने तो परचेज कर लिया था", "nahin hamne to parchej kar liya tha"),
    ("साहब के नंबर से", "saahab ke nambar se"),  # anusvara before b → "m"
    ("समझना बोलना कमल नमस्ते ज्ञान", "samajhna bolna kamal namaste gyaan"),  # silent "a" dropped correctly
    ("हम आपके बारे में जल्दी बताएंगे।", "ham aapke baare mein jaldi bataayenge."),
    ("सोफा चेयर ऑफिस", "sofa cheyar ofis"),
])  # fmt: skip
def test_common_phrases(hindi, roman):
    assert to_roman(hindi) == roman


def test_english_letters_numbers_and_mixed_text_are_left_alone():
    assert to_roman("Ortho Pro ₹39,000 ठीक है") == "Ortho Pro ₹39,000 theek hai"
    assert to_roman("Hello, how are you?") == "Hello, how are you?"
    assert to_roman("४० डेंसिटी") == "40 densiti"


def test_detects_devanagari():
    assert has_devanagari("हाँ ji") and not has_devanagari("haan ji")
