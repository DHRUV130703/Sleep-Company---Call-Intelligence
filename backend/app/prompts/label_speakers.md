version: 1
Below are the utterances of ONE sales phone call between The Sleep Company (a salesperson or a voice bot)
and a customer, transcribed by a speech-to-text model that doesn't know who is speaking.

For EVERY line return {i, role, text}:
- role: "agent" for The Sleep Company side (introduces the company, pitches mattresses/pillows/offers, asks
  qualifying questions, books visits or callbacks); "customer" for the other person. Use the conversation
  flow — speakers usually alternate, but not always.
- text: the same words, cleaned up:
  - {{script_rule}}
  - Fix obvious mishearings of names: The Sleep Company, SmartGRID, Ortho Pro, Elite, Luxe, HiLITE Mall, EMI.
  - Do NOT add, drop, summarise or translate meaning (unless the script rule says translate). Keep numbers as digits.
Return every line number exactly once, in order.

{{lines}}
