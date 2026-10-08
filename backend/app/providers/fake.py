"""Fake providers: no network, no API keys. Used by tests and by TRANSCRIBER=fake / ANALYZER=fake (demo mode).

They return plausible, schema-valid answers so the whole app can be exercised offline.
"""

import re
from pathlib import Path
from typing import Any

from app.config import get_business
from app.contracts import RawSegment, RawTranscript

DEMO_DIALOG = [
    ("S1", "Hello, this is Aman from The Sleep Company. Am I speaking with the customer?"),
    ("S2", "Haan, boliye. Ortho Pro ka price kya hai?"),
    ("S1", "The Ortho Pro in 75x60 is 39,000 with the current offer."),
    ("S2", "Thoda zyada hai. Kal store aa ke dekhta hoon."),
    ("S1", "Sure, I will book your visit for tomorrow evening. Thank you!"),
]


class FakeTranscriber:
    name = "fake"
    model = "fake"

    async def transcribe(self, audio: Path, *, script: str, context: str = "") -> RawTranscript:
        segs, t = [], 0.0
        for speaker, text in DEMO_DIALOG:
            dur = max(1.5, len(text.split()) * 0.4)
            segs.append(RawSegment(speaker=speaker, start=round(t, 1), end=round(t + dur, 1), text=text))
            t += dur + 0.4
        return RawTranscript(segments=segs)


_LINE = re.compile(r"^\[(\d+)\]\[(\d+):(\d+)\] (AGENT|CUSTOMER|S\w*): (.+)$", re.M)


def _lines(prompt: str) -> list[tuple[float, str, str]]:
    return [(int(m[2]) * 60 + int(m[3]), m[4], m[5]) for m in _LINE.finditer(prompt)]


class FakeLLM:
    name = "fake"

    async def json(
        self, *, prompt: str, schema: dict[str, Any], model: str, audio: Path | None = None
    ) -> dict[str, Any]:
        props = schema.get("properties", {})
        if "agent_speaker" in props:
            return {"agent_speaker": "S1"}
        if "segments" in props:  # speaker labelling: alternate agent / customer
            n = len(re.findall(r"^\[\d+\]\[", prompt, re.M))
            return {
                "segments": [
                    {"i": i, "role": "agent" if i % 2 == 0 else "customer", "text": ""} for i in range(n)
                ]
            }
        if "verdict_headline" in props:
            return self._comparison(prompt)
        if "summary" in props:
            return self._call_analysis(prompt)
        if "bullets" in props:
            return {
                "bullets": ["Customer asked about price", "Store visit discussed"],
                "next_actions": [
                    {
                        "title": "Confirm the visit",
                        "say": "Namaste, aapka visit confirm karna tha.",
                        "why": "Visit was agreed",
                        "when": "tomorrow",
                    }
                ],
            }
        raise ValueError("FakeLLM: unknown schema")

    def _call_analysis(self, prompt: str) -> dict[str, Any]:
        lines = _lines(prompt)
        cust = [ln for ln in lines if ln[1] == "CUSTOMER"] or lines
        agent = [ln for ln in lines if ln[1] == "AGENT"] or lines
        first_c = cust[0] if cust else (0.0, "CUSTOMER", "")
        first_a = agent[0] if agent else (0.0, "AGENT", "")
        b = get_business()
        is_ai = "Agent type: AI voice bot" in prompt
        score = 2 if is_ai else 4
        item = {"status": "unknown", "value": "", "evidence": ""}
        return {
            "language": "hinglish",
            "summary": {
                "one_liner": "Customer asked about the Ortho Pro price; follow-up agreed.",
                "bullets": ["Customer asked the price", "Agent quoted the offer price", "Next step agreed"],
            },
            "customer": {
                "name": "",
                "city": "",
                "pincode": "",
                "products_discussed": ["Ortho Pro"],
                "size": "75x60",
                "budget": "",
                "pain_points": [],
                "competitors_mentioned": [],
            },
            "intent": {
                "score": 45 if is_ai else 78,
                "positive_factors": ["Asked the price"],
                "negative_factors": ["Found it expensive"],
            },
            "objections": [
                {
                    "type": "price",
                    "title": "Price feels high",
                    "customer_quote": first_c[2],
                    "t": first_c[0],
                    "handling": "Quoted the offer",
                    "handled_well": not is_ai,
                    "customer_satisfied": not is_ai,
                    "better_response": "Offer EMI options",
                }
            ],
            "bant": {"budget": item, "authority": item, "need": item, "timeline": item},
            "outcome": {
                "disposition": "callback_scheduled" if is_ai else "store_visit",
                "next_step": "Follow up",
                "next_step_when": "tomorrow",
                "escalated": False,
            },
            "mood": {
                "start": "neutral",
                "end": "neutral" if is_ai else "positive",
                "trajectory": "same" if is_ai else "improved",
            },
            "scorecard": [
                {
                    "key": d.key,
                    "score": score,
                    "reason": "Demo score",
                    "evidence": first_a[2],
                    "t": first_a[0],
                }
                for d in b.scorecard.dimensions
            ],
            "key_moments": [
                {"t": first_c[0], "type": "price_asked", "label": "Price asked", "quote": first_c[2]}
            ],
            "friction_points": ["Repeated the opening line"] if is_ai else [],
            "unanswered_questions": [],
            "next_actions": [
                {
                    "title": "Call back with offer details",
                    "say": "Namaste, offer details share karne the.",
                    "why": "Price was the main question",
                    "when": "tomorrow",
                }
            ],
            "pitch_opportunities": [
                {
                    "product": "EMI / offer",
                    "fit_reason": "Customer found the price high",
                    "evidence": first_c[2],
                    "say": "Aapke liye EMI option bhi hai.",
                    "t": first_c[0],
                }
            ],
            "ai_failure_patterns": [
                {
                    "pattern": "scripted_repeat",
                    "description": "Repeated the opening",
                    "quote": first_a[2],
                    "t": first_a[0],
                }
            ]
            if is_ai
            else [],
        }

    def _comparison(self, prompt: str) -> dict[str, Any]:
        quotes = re.findall(r"call_id=(\d+) .*?quote: \"(.+?)\"", prompt)
        ev = [{"call_id": int(cid), "quote": q} for cid, q in quotes[:2]]
        return {
            "verdict_headline": "Humans answer what the customer asked; the bot repeats scripted lines.",
            "differences": [
                {
                    "theme": "Answering the question",
                    "ai": "Repeats the opening line",
                    "human": "Gives the price first",
                    "why": "Unanswered price questions end calls",
                    "evidence": ev,
                }
            ],
            "ai_better": ["Consistent greeting"],
            "human_better": ["Adapts to what the customer says"],
            "outcomes_paragraph": "Human calls ended with concrete next steps more often.",
            "recommended_changes": [
                {
                    "priority": "high",
                    "change": "Answer price questions directly",
                    "rationale": "Price is the most common first question",
                }
            ],
        }
