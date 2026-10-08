version: 2
Transcribe this sales phone call between a salesperson (or a voice bot) and a customer.

Rules:
- Split into segments at every change of speaker.
- speaker: AGENT for the salesperson or voice bot (introduces the company, pitches, asks qualifying questions),
  CUSTOMER for the customer, OTHER for anyone else.
- {{script_rule}}
- Write numbers and prices as digits (e.g. 39,000; 75x60).
- start and end are seconds from the beginning of THIS audio.
- Write only what is said. No summaries or notes. Skip silence, hold music and ringing.
{{context}}
