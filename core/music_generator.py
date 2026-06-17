"""
Music Generator
===============
Generates synthetic background music tracks as WAV files.
Styles: corporate | upbeat | dramatic | calm | none

Uses pure NumPy synthesis — no external music libraries required.
"""

import math
import struct
import wave
from pathlib import Path
from typing import Optional

import numpy as np


SAMPLE_RATE = 44100


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    samples = np.clip(samples, -1.0, 1.0)
    pcm     = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def _sine(freq: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq * t + phase)


def _tri(freq: float, t: np.ndarray) -> np.ndarray:
    return 2 * np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1


def _adsr(n: int, a: float, d: float, s: float, r: float,
           sustain_level: float = 0.7) -> np.ndarray:
    """ADSR envelope. a/d/r in seconds."""
    env = np.zeros(n)
    na  = min(int(a * SAMPLE_RATE), n)
    nd  = min(int(d * SAMPLE_RATE), max(0, n - na))
    nr  = min(int(r * SAMPLE_RATE), max(0, n - na - nd))
    ns  = max(0, n - na - nd - nr)

    if na > 0:
        env[:na] = np.linspace(0, 1, na)
    if nd > 0:
        env[na:na + nd] = np.linspace(1, sustain_level, nd)
    if ns > 0:
        env[na + nd:na + nd + ns] = sustain_level
    if nr > 0:
        ri = na + nd + ns
        env[ri:ri + nr] = np.linspace(sustain_level, 0, nr)
    return env


def _fade_in_out(n: int, fade_sec: float = 2.0) -> np.ndarray:
    env  = np.ones(n)
    fade = int(fade_sec * SAMPLE_RATE)
    fade = min(fade, n // 3)
    if fade > 0:
        env[:fade]  = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
    return env


def _note_freq(note: str) -> float:
    """Convert note name (e.g. 'A4', 'C3') to frequency."""
    notes = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    name, octave = note[0], int(note[1])
    semitone = notes[name] + (octave - 4) * 12
    return 440.0 * (2.0 ** (semitone / 12.0))


def _chord(notes: list, t: np.ndarray, amp: float = 0.25) -> np.ndarray:
    return sum(_sine(_note_freq(n), t) * amp for n in notes)


# ── Style generators ─────────────────────────────────────────────────────────

def _gen_corporate(duration: float) -> np.ndarray:
    """Clean, professional piano + pad."""
    n  = int(duration * SAMPLE_RATE)
    t  = np.linspace(0, duration, n)
    sr = SAMPLE_RATE

    # Pad chord progression (C - Am - F - G)
    chords = [
        (["C4", "E4", "G4"],  0.0),
        (["A3", "C4", "E4"],  duration * 0.25),
        (["F3", "A3", "C4"],  duration * 0.5),
        (["G3", "B3", "D4"],  duration * 0.75),
    ]
    pad = np.zeros(n)
    for ch_notes, start_t in chords:
        start_i = int(start_t * sr)
        end_i   = min(n, start_i + int(duration * 0.28 * sr))
        seg     = np.zeros(n)
        seg[start_i:end_i] = _chord(ch_notes, t[start_i:end_i], amp=0.15)
        env_seg             = np.zeros(n)
        seg_len             = end_i - start_i
        if seg_len > 0:
            env_seg[start_i:end_i] = _adsr(seg_len, 0.2, 0.1, 0.6, 0.3)
        pad += seg * env_seg

    # Light sub bass pulse
    bass = np.zeros(n)
    beat = int(sr * 0.5)
    bass_notes = [_note_freq("C2"), _note_freq("A1"), _note_freq("F1"), _note_freq("G1")]
    for bi, bn in enumerate(bass_notes):
        for b in range(bi * 2, (bi + 1) * 2):
            si = b * beat
            ei = min(n, si + beat)
            if si >= n:
                break
            seg = _sine(bn, t[si:ei]) * 0.12
            env = _adsr(ei - si, 0.02, 0.05, 0.5, 0.15)
            bass[si:ei] += seg * env

    mixed = pad + bass
    return mixed * _fade_in_out(n)


def _gen_upbeat(duration: float) -> np.ndarray:
    """Energetic, punchy synth with rhythm."""
    n  = int(duration * SAMPLE_RATE)
    t  = np.linspace(0, duration, n)
    sr = SAMPLE_RATE

    # Lead synth arpeggio
    arpegg = [_note_freq(x) for x in ["C4", "E4", "G4", "B4", "C5", "B4", "G4", "E4"]]
    step   = int(sr * 0.18)
    lead   = np.zeros(n)
    for i, freq in enumerate(arpegg * (int(duration / 1.44) + 2)):
        si = i * step
        ei = min(n, si + step)
        if si >= n:
            break
        seg = (_sine(freq, t[si:ei]) * 0.6 + _sine(freq * 2, t[si:ei]) * 0.15)
        env = _adsr(ei - si, 0.01, 0.04, 0.6, 0.06)
        lead[si:ei] += seg * env

    # Kick drum
    kick = np.zeros(n)
    beat = int(sr * 0.5)
    for b in range(int(duration / 0.5) + 1):
        si = b * beat
        ei = min(n, si + int(sr * 0.12))
        if si >= n:
            break
        env = np.exp(-np.linspace(0, 8, ei - si))
        kick[si:ei] += _sine(60 * np.exp(-np.linspace(0, 3, ei - si)), t[si:ei]) * env * 0.4

    mixed = lead * 0.5 + kick
    return mixed * _fade_in_out(n, fade_sec=1.5)


def _gen_dramatic(duration: float) -> np.ndarray:
    """Cinematic strings + deep bass."""
    n  = int(duration * SAMPLE_RATE)
    t  = np.linspace(0, duration, n)
    sr = SAMPLE_RATE

    # Sustained strings (sawtooth approximation)
    strings = np.zeros(n)
    chord   = [_note_freq(x) for x in ["C3", "G3", "E4", "G4"]]
    for freq in chord:
        # Sawtooth via multiple harmonics
        for h in range(1, 6):
            strings += _sine(freq * h, t) * (0.12 / h)

    env_strings = _adsr(n, 2.0, 1.0, 0.7, 3.0)
    strings    *= env_strings

    # Deep riser
    riser  = _sine(40 * (1 + t / duration), t) * 0.25
    riser *= np.linspace(0, 1, n)

    mixed = strings * 0.6 + riser * 0.4
    return mixed * _fade_in_out(n, fade_sec=3.0)


def _gen_calm(duration: float) -> np.ndarray:
    """Gentle ambient pads, slow evolution."""
    n  = int(duration * SAMPLE_RATE)
    t  = np.linspace(0, duration, n)
    sr = SAMPLE_RATE

    pad   = np.zeros(n)
    freqs = [_note_freq(x) for x in ["C3", "G3", "C4", "E4", "G4"]]
    for i, freq in enumerate(freqs):
        phase = i * 0.4
        pad  += _sine(freq, t, phase) * 0.15
        pad  += _sine(freq * 1.005, t, phase + 0.2) * 0.08  # slight detune

    # Slow LFO tremolo
    lfo  = 0.85 + 0.15 * _sine(0.15, t)
    pad *= lfo

    return pad * _fade_in_out(n, fade_sec=3.0)


GENERATORS = {
    "corporate": _gen_corporate,
    "upbeat":    _gen_upbeat,
    "dramatic":  _gen_dramatic,
    "calm":      _gen_calm,
}


def generate_music(style: str, duration: float, output_path: Path) -> Optional[Path]:
    """Generate background music WAV and return path. Returns None for 'none'."""
    if style == "none" or style not in GENERATORS:
        return None

    gen     = GENERATORS[style]
    samples = gen(max(duration, 2.0))

    # Normalise
    peak = np.abs(samples).max()
    if peak > 0:
        samples /= peak
    samples *= 0.85

    _write_wav(output_path, samples)
    return output_path
