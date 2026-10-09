"""What the AI must return (PRD §7.1, §7.5). Every AI answer is validated against these models.

Design choices that keep the AI reliable:
- No optional/null fields: unknown text is "", unknown time is -1. Simpler for the model, simpler for us.
- Lists instead of dicts with dynamic keys (e.g. scorecard is a list of {key, score, …}).
- Values that come from config (objection types, scorecard keys, failure patterns) are injected as
  enums at runtime by `json_schema_for()`, so editing the YAML changes what the AI can answer.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import get_business

# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


class RawSegment(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class RawTranscript(BaseModel):
    segments: list[RawSegment]


class LabeledLine(BaseModel):
    i: int
    role: Literal["agent", "customer"] = "customer"
    text: str = ""


class LabeledTranscript(BaseModel):
    segments: list[LabeledLine]


class RoleMap(BaseModel):
    agent_speaker: str = Field(description="The speaker label of the sales agent / bot")


# ---------------------------------------------------------------------------
# Per-call analysis
# ---------------------------------------------------------------------------

Disposition = Literal[
    "converted",
    "store_visit",
    "callback_scheduled",
    "agreed_next_step",
    "follow_up_pending",
    "not_interested",
    "not_qualified",
    "no_outcome",
]
Mood = Literal["positive", "neutral", "negative"]


# Every field below has a safe default: the AI is still asked for all of them (the schema marks every
# field required), but if it leaves a minor one out, the call is analysed anyway instead of failing.


class Summary(BaseModel):
    one_liner: str = ""
    bullets: list[str] = Field(default_factory=list, description="3-6 short factual bullets")


class CustomerInfo(BaseModel):
    name: str = ""
    city: str = ""
    pincode: str = ""
    products_discussed: list[str] = Field(default_factory=list)
    size: str = ""
    budget: str = ""
    pain_points: list[str] = Field(default_factory=list)
    competitors_mentioned: list[str] = Field(default_factory=list)


class Intent(BaseModel):
    score: int = Field(ge=0, le=100)
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)


class Objection(BaseModel):
    type: str = Field(default="other", json_schema_extra={"x-enum-from": "objection_types"})
    title: str = ""
    customer_quote: str = ""
    t: float = Field(default=-1, description="seconds into the call, -1 if unknown")
    handling: str = ""
    handled_well: bool = False
    customer_satisfied: bool = False
    better_response: str = ""


class BantItem(BaseModel):
    status: Literal["known", "partial", "unknown"] = "unknown"
    value: str = ""
    evidence: str = ""


class Bant(BaseModel):
    budget: BantItem = Field(default_factory=BantItem)
    authority: BantItem = Field(default_factory=BantItem)
    need: BantItem = Field(default_factory=BantItem)
    timeline: BantItem = Field(default_factory=BantItem)


class Outcome(BaseModel):
    disposition: Disposition = "no_outcome"
    next_step: str = ""
    next_step_when: str = Field(
        default="", description='When, exactly as said, e.g. "kal shaam 6 baje", "tomorrow"; "" if none'
    )
    escalated: bool = False


class MoodInfo(BaseModel):
    start: Mood = "neutral"
    end: Mood = "neutral"
    trajectory: Literal["improved", "same", "worsened"] = "same"


class ScoreItem(BaseModel):
    key: str = Field(json_schema_extra={"x-enum-from": "scorecard_keys"})
    score: int = Field(ge=1, le=5)
    reason: str = ""
    evidence: str = ""
    t: float = -1
    better: str = Field(
        default="",
        description='Score 1-3: what the agent should have said or done instead (one line); else ""',
    )


class KeyMoment(BaseModel):
    t: float = -1
    type: Literal[
        "price_asked",
        "objection",
        "commitment",
        "callback_agreed",
        "refusal",
        "question_unanswered",
        "escalation",
        "other",
    ] = "other"
    label: str = ""
    quote: str = ""


class NextAction(BaseModel):
    title: str = ""
    say: str = Field(default="", description="What to say on the follow-up, in the customer's language")
    why: str = ""
    when: str = Field(default="", description='Due, exactly as agreed in the call ("" if none)')


class PitchOpportunity(BaseModel):
    product: str = Field(json_schema_extra={"x-enum-from": "products"})
    fit_reason: str = Field(default="", description="Why this fits THIS customer, based on what they said")
    evidence: str = Field(default="", description="The customer's own words that show the need (exact quote)")
    say: str = Field(default="", description="How to pitch it on the next call, in the customer's language")
    t: float = -1


class FailurePattern(BaseModel):
    pattern: str = Field(json_schema_extra={"x-enum-from": "ai_failure_patterns"})
    description: str = ""
    quote: str = ""
    t: float = -1
    better_line: str = Field(
        default="",
        description="What the bot should have said instead — one natural line in the customer's language",
    )


class CallAnalysis(BaseModel):
    language: Literal["hinglish", "hindi", "english", "other"] = "other"
    summary: Summary = Field(default_factory=Summary)
    customer: CustomerInfo = Field(default_factory=CustomerInfo)
    intent: Intent
    objections: list[Objection] = Field(default_factory=list)
    bant: Bant = Field(default_factory=Bant)
    outcome: Outcome = Field(default_factory=Outcome)
    mood: MoodInfo = Field(default_factory=MoodInfo)
    scorecard: list[ScoreItem] = Field(default_factory=list)
    key_moments: list[KeyMoment] = Field(default_factory=list)
    friction_points: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    pitch_opportunities: list[PitchOpportunity] = Field(default_factory=list)
    ai_failure_patterns: list[FailurePattern] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Lead roll-up and AI vs Human synthesis
# ---------------------------------------------------------------------------


class LeadPath(BaseModel):
    bullets: list[str]
    next_actions: list[NextAction]


class Evidence(BaseModel):
    call_id: int
    quote: str


class Difference(BaseModel):
    theme: str
    ai: str
    human: str
    why: str
    evidence: list[Evidence]


class Change(BaseModel):
    priority: Literal["high", "medium", "low"]
    area: str = Field(default="", description="Which part of the bot changes, e.g. Script, Knowledge base")
    change: str
    rationale: str
    bot_line: str = Field(
        default="", description="The new line or behaviour for the bot, in the customer's language"
    )
    call_ids: list[int] = Field(default_factory=list, description="1-3 AI call_ids that show the problem")


class ComparisonSynthesis(BaseModel):
    verdict_headline: str
    verdict_detail: str = Field(default="", description="2-3 sentences: is the bot ready, what holds it back")
    differences: list[Difference]
    ai_better: list[str]
    human_better: list[str]
    outcomes_paragraph: str
    recommended_changes: list[Change]


# ---------------------------------------------------------------------------
# JSON schema for the AI (Gemini-compatible subset)
# ---------------------------------------------------------------------------

_DROP_KEYS = {"title", "default", "x-enum-from", "exclusiveMinimum", "exclusiveMaximum"}


def _config_enums() -> dict[str, list[str]]:
    b = get_business()
    return {
        "objection_types": b.intent.objection_types,
        "scorecard_keys": [d.key for d in b.scorecard.dimensions],
        "ai_failure_patterns": b.intent.ai_failure_patterns,
        "products": [p.name for p in b.catalog.products] + ["Other"],
    }


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic → a self-contained JSON schema (refs inlined, config enums injected)."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    enums = _config_enums()

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            out: dict[str, Any] = {}
            for k, v in node.items():
                if k == "properties":  # field names: keep every one (a field may be called "title")
                    out[k] = {name: walk(sub) for name, sub in v.items()}
                elif k not in _DROP_KEYS:
                    out[k] = walk(v)
            if src := node.get("x-enum-from"):
                out["enum"] = enums[src]
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(raw)  # type: ignore[no-any-return]
