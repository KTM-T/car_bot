from dotenv import load_dotenv
from groq import Groq

load_dotenv()

SYSTEM_PROMPT = """You are CarDiag, an expert automotive diagnostic assistant.
You help vehicle owners and mechanics diagnose car problems through conversation.

Your role:
- Ask focused follow-up questions to narrow down the root cause
- Give specific, actionable diagnostic steps in priority order
- Cite likely causes with probability reasoning based on symptoms
- Reference OBD codes, voltage specs, resistance values, and pressure specs where relevant
- Know the difference between urgent (stop driving now) and monitor-and-watch issues

Rules:
- Be direct. Name the likely part, the test to confirm it, and the fix.
- When a symptom has multiple causes, rank them by likelihood given what you know.
- Use real diagnostic values: voltages, ohm readings, psi specs, temperature ranges.
- If you need more info to diagnose accurately, ask ONE focused question at a time.
- Flag safety-critical issues immediately (oil pressure, brake failure, overheating).
- Keep responses concise. Short paragraphs or numbered steps. No filler.
- Do not invent symptoms the user hasn't described.
- Stay on automotive topics only."""


def stream_diagnosis(conversation: list[dict], user_message: str, api_key: str):
    """
    Generator that yields text chunks from Groq streaming.
    conversation: list of {role, content} dicts (prior turns)
    user_message: the latest user input
    """
    client = Groq(api_key=api_key)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversation)
    messages.append({"role": "user", "content": user_message})

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
        temperature=0.3,
        stream=True,
    )

    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield text
