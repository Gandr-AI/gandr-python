"""Gandr TTS, official Python client.

Install:  pip install gandr
First call in four lines:

    from gandr import Gandr
    g = Gandr("gnd_...")               # your API key
    audio = g.say("Your table is confirmed for Thursday at seven.")
    open("booking.wav", "wb").write(audio)

Docs: https://gandr.ai/docs
"""

from .client import Gandr, GandrError, Voice

__all__ = ["Gandr", "GandrError", "Voice"]
__version__ = "0.1.0"
