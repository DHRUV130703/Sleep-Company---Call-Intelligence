"""Generate demo call recordings with macOS text-to-speech (no real customer data needed).

    python3 scripts/make_sample_calls.py        → writes samples/*.mp3 and samples/calls.csv

Agent lines use an Indian-English voice, customer lines a Hindi voice, so calls sound Hinglish.
Requires macOS (`say`) and ffmpeg.
"""

import csv
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples"

AGENT_VOICE = "Aman"   # en_IN
BOT_VOICE = "Tara"     # en_IN
CUSTOMER_VOICE = "Lekha"  # hi_IN

CALLS = {
    # A good human call: answers the price, handles the objection, books a store visit.
    "human_call_nithin": [
        ("A", "Hello, am I speaking with Nithin? This is Aman calling from The Sleep Company about your mattress enquiry."),
        ("C", "हाँ, मैं नितिन बोल रहा हूँ। मुझे ऑर्थो प्रो मैट्रेस का प्राइस जानना था।"),
        ("A", "Sure Nithin. The Ortho Pro in seventy five by sixty is thirty nine thousand rupees with the current offer. The MRP is fifty eight thousand."),
        ("C", "पिछली बार तो सत्ताईस हज़ार नौ सौ नब्बे बताया था। इतना ज़्यादा क्यों?"),
        ("A", "I understand. Twenty seven nine ninety was for the single size. For your size it is thirty nine thousand. I can also share the EMI option at three thousand two hundred per month."),
        ("C", "ठीक है। मुझे कमर में दर्द रहता है, क्या यह उसके लिए सही है?"),
        ("A", "Yes, the Ortho Pro is designed for back support. Would you like to try it at our Hilite Mall store tomorrow evening?"),
        ("C", "हाँ, कल शाम को आ सकता हूँ।"),
        ("A", "Perfect, I have booked your visit for tomorrow at six pm. I will send the details on WhatsApp. Thank you Nithin!"),
    ],
    # A human call that ends with a callback.
    "human_call_priya": [
        ("A", "Hi, this is Aman from The Sleep Company. You had checked our SmartGRID mattress online. Is this a good time?"),
        ("C", "अभी मैं ऑफिस में हूँ। आप शाम को कॉल कर सकते हैं?"),
        ("A", "Of course. Shall I call you at seven pm today?"),
        ("C", "हाँ, सात बजे ठीक है।"),
        ("A", "Great, I will call you at seven. Thank you!"),
    ],
    # An AI bot call that ignores the price question and repeats its script.
    "ai_call_1": [
        ("A", "Hello! I am calling from The Sleep Company. We have exciting offers on our SmartGRID mattresses this week."),
        ("C", "क्वीन साइज़ का प्राइस क्या है?"),
        ("A", "Hello! I am calling from The Sleep Company. We have exciting offers on our SmartGRID mattresses this week."),
        ("C", "मैंने प्राइस पूछा। क्वीन साइज़ कितने का है?"),
        ("A", "Our mattresses come with a hundred night trial. Would you like a callback from our expert?"),
        ("C", "ठीक है, कल कॉल कर देना।"),
        ("A", "Thank you. Our expert will call you. Have a nice day."),
    ],
    # An AI bot call that keeps pitching after the customer refuses.
    "ai_call_2": [
        ("A", "Hello! I am calling from The Sleep Company about our SmartGRID mattress offers."),
        ("C", "नहीं चाहिए, मैंने पहले ही ले लिया है।"),
        ("A", "Our SmartGRID technology gives you better sleep and comes with a ten year warranty."),
        ("C", "बोला ना, नहीं चाहिए।"),
        ("A", "We also have free delivery and easy EMI options. Shall I book a store visit?"),
        ("C", "नहीं। फ़ोन रखो।"),
    ],
    # Too short: should be marked "not connected".
    "ai_call_short": [("A", "Hello?")],
}


def synth(voice: str, text: str, path: Path) -> None:
    subprocess.run(["say", "-v", voice, "-o", str(path), text], check=True)


def build_call(name: str, lines: list[tuple[str, str]], agent_voice: str) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        silence = tmp_dir / "gap.aiff"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
             "-t", "0.6", str(silence)], check=True)
        parts = []
        for i, (who, text) in enumerate(lines):
            part = tmp_dir / f"{i:02d}.aiff"
            synth(agent_voice if who == "A" else CUSTOMER_VOICE, text, part)
            parts += [part, silence]
        listing = tmp_dir / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        out = OUT / f"{name}.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-ar", "22050", "-ac", "1", "-b:a", "64k", str(out)], check=True)
        return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows = []
    for name, lines in CALLS.items():
        is_ai = name.startswith("ai_")
        path = build_call(name, lines, BOT_VOICE if is_ai else AGENT_VOICE)
        print("✓", path.relative_to(ROOT))
        rows.append({
            "call_id": name,
            "recording_url": f"http://127.0.0.1:8765/{path.name}",
            "agent_type": "AI bot" if is_ai else "Human",
            "customer_name": {"human_call_nithin": "Nithin", "human_call_priya": "Priya"}.get(name, ""),
            "phone": {"human_call_nithin": "9037125616", "human_call_priya": "9811122233",
                      "ai_call_1": "9822233344", "ai_call_2": "9833344455"}.get(name, ""),
            "agent": "Kerala HiLITE Mall Store" if not is_ai else "Voice Bot v1",
            "campaign": "Mattress enquiry follow-up",
        })
    with (OUT / "calls.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("✓ samples/calls.csv (links expect: python3 -m http.server 8765 -d samples)")


if __name__ == "__main__":
    main()
