"""TTS français local — Chatterbox (FR premium Thomcles + repli multilingue V2)."""
import io
import os
import re
import tempfile
import time
from pathlib import Path

import torch
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

BASE = Path(__file__).parent
VOICES = BASE / "voices"
VOICES.mkdir(exist_ok=True)


def resolve_device() -> str:
    """TTS_DEVICE=cpu|gpu|auto (défaut auto). Repli CPU si HIP indisponible."""
    want = os.getenv("TTS_DEVICE", "auto").lower()
    if want in ("gpu", "cuda"):
        return "cuda"  # échoue franchement si pas de GPU (choix explicite)
    if want == "cpu":
        return "cpu"
    try:
        if torch.cuda.is_available():
            torch.zeros(1, device="cuda")  # vraie alloc : détecte un HIP cassé
            print(f"[tts] GPU : {torch.cuda.get_device_name(0)}")
            return "cuda"
    except Exception as e:
        print(f"[tts] GPU inutilisable ({e}), repli CPU")
    return "cpu"


DEVICE = resolve_device()
FR_REPO = "Thomcles/Chatterbox-TTS-French"
FR_FILE = "t3_cfg.safetensors"
MAX_CHARS = 2000

app = FastAPI(title="TTS FR local")
_models: dict = {}


def get_base():
    if "base" not in _models:
        from chatterbox.tts import ChatterboxTTS

        _models["base"] = ChatterboxTTS.from_pretrained(device=DEVICE)
    return _models["base"]


def get_fr():
    """Base EN + patch T3 français (1400h Emilia FR). Repli multilingue si échec."""
    if "fr" not in _models:
        try:
            from huggingface_hub import hf_hub_download
            from safetensors.torch import load_file

            model = get_base()
            ckpt = hf_hub_download(repo_id=FR_REPO, filename=FR_FILE)
            model.t3.load_state_dict(load_file(ckpt, device="cpu"))
            model.t3.to(DEVICE).eval()
            _models["fr"] = model
        except Exception as e:
            print(f"[tts] patch FR indisponible ({e}), repli multilingue")
            _models["fr"] = get_multi()
    return _models["fr"]


def get_multi():
    if "multi" not in _models:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        _models["multi"] = ChatterboxMultilingualTTS.from_pretrained(
            device=torch.device(DEVICE)
        )
    return _models["multi"]


def split_sentences(text: str, limit: int = 300) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?…\n])\s+", text.strip()) if p.strip()]
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 > limit and cur:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks or [text.strip()]


def synthesize(text, model_name, ref_path, exaggeration, cfg, temperature):
    use_multi = model_name == "multi" or (
        model_name == "fr" and type(get_fr()).__name__ == "ChatterboxMultilingualTTS"
    )
    model = get_multi() if use_multi else get_fr()
    kw = dict(audio_prompt_path=ref_path, exaggeration=exaggeration,
              cfg_weight=cfg, temperature=temperature)
    wavs = []
    with torch.inference_mode():
        for chunk in split_sentences(text):
            if use_multi:
                w = model.generate(chunk, language_id="fr", **kw)
            else:
                w = model.generate(chunk, **kw)
            wavs.append(w)
    out = torch.cat([w.flatten() for w in wavs]).unsqueeze(0)
    return out, model.sr


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "index.html").read_text(encoding="utf-8")


@app.get("/api/voices")
def voices():
    return JSONResponse(sorted(p.name for p in VOICES.glob("*.wav")))


@app.get("/api/status")
def status():
    loaded = sorted(_models.keys())
    return {"device": DEVICE, "cuda": torch.cuda.is_available(), "loaded": loaded}


@app.post("/api/tts")
async def tts(
    text: str = Form(...),
    model: str = Form("fr"),
    voice: str = Form("default"),
    exaggeration: float = Form(0.5),
    cfg: float = Form(0.5),
    temperature: float = Form(0.8),
    ref: UploadFile | None = File(None),
):
    text = text.strip()
    if not 1 <= len(text) <= MAX_CHARS:
        raise HTTPException(400, f"Texte : 1 à {MAX_CHARS} caractères.")
    if model not in ("fr", "multi"):
        raise HTTPException(400, "Modèle inconnu.")
    ex = min(1.0, max(0.0, exaggeration))
    cg = min(1.0, max(0.0, cfg))
    tp = min(1.5, max(0.1, temperature))

    tmp = None
    try:
        ref_path = None
        if ref is not None and ref.filename:
            data = await ref.read()
            if len(data) > 10 * 1024 * 1024:
                raise HTTPException(400, "Référence vocale > 10 Mo.")
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(data)
            tmp.close()
            ref_path = tmp.name
        elif voice != "default":
            p = (VOICES / voice).resolve()
            if not str(p).startswith(str(VOICES.resolve())) or not p.is_file():
                raise HTTPException(400, "Voix inconnue.")
            ref_path = str(p)

        t0 = time.time()
        wav, sr = synthesize(text, model, ref_path, ex, cg, tp)
        dt = time.time() - t0
        print(f"[tts] {len(text)} car. -> {wav.shape[1]/sr:.1f}s audio en {dt:.1f}s")

        buf = io.BytesIO()
        sf.write(buf, wav.squeeze(0).cpu().numpy(), sr, format="WAV")
        return Response(
            buf.getvalue(),
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename=tts-{int(t0)}.wav"},
        )
    finally:
        if tmp:
            Path(tmp.name).unlink(missing_ok=True)
