from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.pipeline.grounding import locate_quote, resolve_when, verify_quote
from app.pipeline.metrics import compute_metrics, count_questions

SEGS = [
    {"role": "agent", "start": 0.0, "end": 4.0, "text": "Hello, this is Aman from The Sleep Company."},
    {"role": "customer", "start": 4.5, "end": 7.0, "text": "Ortho Pro ka price kya hai?"},
    {"role": "agent", "start": 7.5, "end": 12.0, "text": "Hello, this is Aman from The Sleep Company."},
    {"role": "agent", "start": 12.0, "end": 14.0, "text": "It is 39,000 with the offer. Would you like EMI?"},
    {"role": "customer", "start": 13.5, "end": 15.0, "text": "Haan ok"},
]


def test_metrics_hand_checked():
    m = compute_metrics(SEGS, duration_s=20)
    # agent speech 4 + 4.5 + 2 = 10.5 s, customer 2.5 + 1.5 = 4 s → 72 % agent
    assert m["talk_listen_agent_pct"] == 72
    assert (
        m["agent_turns"] == 2 and m["customer_turns"] == 2
    )  # consecutive agent segments merge into one turn
    assert m["agent_repeated_lines"] == 1  # the greeting was repeated word for word
    assert m["questions_by_agent"] == 1  # "Would you like EMI?"
    assert m["customer_short_replies_pct"] == 50.0  # "Haan ok" ≤ 3 words
    assert m["interruptions"] == 1  # customer started at 13.5 while the agent spoke until 14.0
    assert m["is_detailed"] is False


def test_question_counting_handles_hindi_words():
    assert count_questions("Kya aap kal aa sakte hain") == 1
    assert count_questions("Theek hai. Price kitna hai?") == 1
    assert count_questions("Okay.") == 0


def test_quote_verification_is_fuzzy_but_strict():
    text = " ".join(s["text"] for s in SEGS)
    assert verify_quote("ortho pro ka price kya hai", text)
    assert verify_quote("It is 39,000 with the offer", text)
    assert not verify_quote("The customer wants a refund", text)
    assert not verify_quote("", text)
    assert locate_quote("price kya hai", SEGS)["start"] == 4.5


def test_relative_dates_resolve_against_call_date():
    call = datetime(2026, 10, 7, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata"))  # a Wednesday
    assert resolve_when("kal shaam 6 baje", call) == date(2026, 10, 8)
    assert resolve_when("tomorrow evening", call) == date(2026, 10, 8)
    assert resolve_when("parso", call) == date(2026, 10, 9)
    assert resolve_when("aaj raat", call) == date(2026, 10, 7)
    assert resolve_when("Monday", call) == date(2026, 10, 12)
    assert resolve_when("somvar ko", call) == date(2026, 10, 12)
    assert resolve_when("in 3 days", call) == date(2026, 10, 10)
    assert resolve_when("12 Oct", call) == date(2026, 10, 12)
    assert resolve_when("2 Jan", call) == date(2027, 1, 2)  # already passed this year → next year
    assert resolve_when("", call) is None
    assert resolve_when("whenever", call) is None


def test_hindi_words_are_counted_whole():
    from app.pipeline.metrics import words

    assert words("मैं जान सकती हूँ कि क्या इश्यू था?") == ["मैं", "जान", "सकती", "हूँ", "कि", "क्या", "इश्यू", "था"]
