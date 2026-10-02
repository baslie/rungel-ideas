"""Транскрипция + диаризация видео-отзывов из media/ -> work/<id>.json.

faster-whisper large-v3 (CUDA) даёт слова с таймкодами,
pyannote community-1 даёт сегменты спикеров; слова раскладываются по спикерам
по максимальному перекрытию и склеиваются в реплики.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).parent
MEDIA = ROOT / "media"
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)

PROMPT = "Отзыв о продукте RUNGEL (Рангель)."


def extract_wav(video: Path) -> Path:
    wav = WORK / f"{video.stem}.wav"
    if not wav.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
             "-vn", "-ac", "1", "-ar", "16000", str(wav)],
            check=True,
        )
    return wav


def transcribe(model, wav: Path):
    audio, _ = sf.read(str(wav), dtype="float32")
    segments, info = model.transcribe(
        audio, language="ru", beam_size=5, word_timestamps=True,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 300},
        initial_prompt=PROMPT, condition_on_previous_text=False,
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"start": w.start, "end": w.end, "word": w.word})
    return words, info.duration


def diarize(pipeline, wav: Path):
    if pipeline is None:
        return []
    data, sr = sf.read(str(wav), dtype="float32")
    waveform = torch.from_numpy(np.atleast_2d(data))
    out = pipeline({"waveform": waveform, "sample_rate": sr})
    ann = out.exclusive_speaker_diarization
    return [(t.start, t.end, spk) for t, _, spk in ann.itertracks(yield_label=True)]


def speaker_for(word, turns, prev):
    best, best_ov = None, 0.0
    for s, e, spk in turns:
        ov = min(e, word["end"]) - max(s, word["start"])
        if ov > best_ov:
            best, best_ov = spk, ov
    if best is None and turns:
        mid = (word["start"] + word["end"]) / 2
        best = min(turns, key=lambda t: min(abs(t[0] - mid), abs(t[1] - mid)))[2]
    return best or prev or "SPEAKER_00"


def merge(words, turns):
    # нормализуем имена спикеров в порядке появления: S1, S2, ...
    names, segs, prev = {}, [], None
    for w in words:
        raw = speaker_for(w, turns, prev)
        prev = raw
        spk = names.setdefault(raw, f"S{len(names) + 1}")
        gap = segs and w["start"] - segs[-1]["end"] > 1.5
        if segs and segs[-1]["speaker"] == spk and not gap:
            segs[-1]["text"] += w["word"]
            segs[-1]["end"] = w["end"]
        else:
            segs.append({"start": w["start"], "end": w["end"],
                         "speaker": spk, "text": w["word"]})
    for s in segs:
        s["text"] = s["text"].strip()
        s["start"], s["end"] = round(s["start"], 2), round(s["end"], 2)
    return segs


def main():
    from faster_whisper import WhisperModel

    model = WhisperModel("large-v3", device="cuda", compute_type="float16")

    pipeline = None
    token_file = ROOT / ".hf_token"
    if token_file.exists() and "--no-diar" not in sys.argv:
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1",
            token=token_file.read_text().strip())
        pipeline.to(torch.device("cpu"))  # на GPU рядом с large-v3 не хватает 8 ГБ
    else:
        print("! диаризация отключена (нет .hf_token)")

    for video in sorted(MEDIA.glob("*.mp4")):
        if (WORK / f"{video.stem}.json").exists() and "--force" not in sys.argv:
            continue
        torch.cuda.empty_cache()
        wav = extract_wav(video)
        words, duration = transcribe(model, wav)
        turns = diarize(pipeline, wav)
        segs = merge(words, turns)
        out = {"id": video.stem, "file": f"media/{video.name}",
               "duration": round(duration, 1),
               "speakers": sorted({s["speaker"] for s in segs}),
               "diarized": pipeline is not None, "segments": segs}
        (WORK / f"{video.stem}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{video.stem}: {len(segs)} реплик, спикеров {len(out['speakers'])}")


if __name__ == "__main__":
    main()
