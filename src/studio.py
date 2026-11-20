"""Local-first ad studio domain logic and small JSON web server."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from .model_config import GROQ_STUDIO_MODEL, groq_completion_options
from .advertising.brief import AdBrief


class TextProvider(Protocol):
    label: str
    def generate(self, prompt: str, *, system: str = "") -> str: ...


MOCK_BACKEND_LABEL = "Mock · offline"
_PROVIDER_LOCK = threading.Lock()
_PROVIDERS: dict[str, TextProvider] = {}
_TTS_LOCK = threading.Lock()


class GroqProvider:
    def __init__(self) -> None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        self.key = key
        self.model = GROQ_STUDIO_MODEL
        self.label = f"Groq · {self.model}"

    def generate(self, prompt: str, *, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.6,
        }
        payload.update(groq_completion_options(self.model, 1600))
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            body,
            {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                try:
                    result = json.loads(response.read())
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Groq returned invalid JSON.") from exc
            try:
                choice = result["choices"][0]
                content = choice["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError("Groq returned an unreadable response.") from exc
            if not isinstance(content, str) or not content.strip():
                if choice.get("finish_reason") == "length":
                    raise RuntimeError(
                        "Groq used the completion token budget before returning visible text. "
                        "Increase max_completion_tokens or lower reasoning effort."
                    )
                raise RuntimeError("The hosted model returned an empty response.")
            return content.strip()
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("Groq rejected the API key or this project lacks model access.") from exc
            if exc.code == 429:
                raise RuntimeError("The hosted model is rate limited. Try again shortly.") from exc
            if exc.code == 404:
                raise RuntimeError(f"Groq does not recognize model {self.model!r}; check GROQ_MODEL.") from exc
            if exc.code >= 500:
                raise RuntimeError("Groq is temporarily unavailable. Try again shortly.") from exc
            raise RuntimeError(f"The hosted model returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError("Could not reach the hosted model (30 second limit).") from exc


class LlamaCppProvider:
    def __init__(self) -> None:
        model_path = os.getenv("LLAMA_CPP_MODEL_PATH")
        if not model_path or not Path(model_path).is_file():
            raise RuntimeError("Set LLAMA_CPP_MODEL_PATH to an existing GGUF model file.")
        self.label = f"llama.cpp · {Path(model_path).name}"
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError("Install optional llama-cpp-python to use the local model.") from exc
        try:
            self.model = Llama(model_path=model_path, n_ctx=4096, verbose=False)
        except Exception as exc:
            raise RuntimeError(
                "Could not load the local GGUF model. Check its path and runtime compatibility."
            ) from exc
        self._generation_lock = threading.Lock()

    def generate(self, prompt: str, *, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        with self._generation_lock:
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=1200,
                temperature=0.65,
            )
        try:
            text = response["choices"][0]["message"].get("content", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("The local model returned an unreadable response.") from exc
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("The local model returned an empty response.")
        return text.strip()


def provider_for(name: str) -> TextProvider | None:
    # Keep local model weights loaded between rewrite and export requests.
    if name == "mock":
        return None
    if name not in {"groq", "llama.cpp"}:
        raise ValueError("Choose mock, Groq, or llama.cpp as the writing engine.")
    with _PROVIDER_LOCK:
        if name not in _PROVIDERS:
            _PROVIDERS[name] = GroqProvider() if name == "groq" else LlamaCppProvider()
        return _PROVIDERS[name]


def _clear_provider_cache() -> None:
    with _PROVIDER_LOCK:
        _PROVIDERS.clear()


def _truthful_guard(text: str, brief: AdBrief) -> list[str]:
    lower = text.lower()
    checks = [f"CTA included: {brief.cta.lower() in lower}"]
    product_facts_present = (
        brief.description.lower() in lower and brief.benefit.lower() in lower
    )
    checks.append(f"Product facts included: {product_facts_present}")
    required_points_present = (
        all(point.lower() in lower for point in brief.required_points)
        if brief.required_points
        else "none specified"
    )
    checks.append(f"Required points included: {required_points_present}")
    flagged = [claim for claim in brief.prohibited_claims if claim.lower() in lower]
    checks.append("Prohibited claims: " + (", ".join(flagged) if flagged else "none detected"))
    words = len(re.findall(r"\b[\w’'-]+\b", text))
    checks.append(f"Pacing estimate: ~{round(words / 2.5)} sec at 150 words/min (guidance only)")
    return checks


def _script(brief: AdBrief, lead: str, middle: str) -> str:
    facts = "; ".join(brief.required_points)
    return f"{lead}\n\n{brief.product_name}: {brief.benefit}. {middle} {facts}\n\n{brief.cta}."


def _directions(brief: AdBrief) -> list[dict[str, Any]]:
    product_fact = f"{brief.description}. "
    base = [
        (
            "Clear", "Benefit first", f"Meet {brief.product_name}.",
            f"{product_fact}Made for {brief.audience}, it helps with {brief.benefit}.",
        ),
        (
            "Playful", "A small everyday twist",
            "Your day called. It has a tiny upgrade in mind.",
            f"{product_fact}{brief.product_name} brings {brief.benefit} to "
            f"{brief.audience}—without making a big production of it.",
        ),
        (
            "Bold", "A confident, grounded claim",
            f"Make room for {brief.benefit}.",
            f"{product_fact}{brief.product_name} is designed for {brief.audience}. "
            "Here's a simpler way to move toward what matters.",
        ),
    ]
    directions = []
    for name, concept, hook, middle in base:
        script = _script(brief, hook, middle)
        directions.append({
            "name": name,
            "concept": concept,
            "hook": hook,
            "script": script,
            "checks": _truthful_guard(script, brief),
        })
    return directions


def _request(brief: AdBrief, task: str, provider: TextProvider) -> str:
    facts = json.dumps(asdict(brief), ensure_ascii=False)
    prompt = (
        f"Task: {task}\n"
        f"Ad brief (user-provided facts and constraints): {facts}\n"
        "Never invent product facts, proof, prices, guarantees, endorsements, or statistics. "
        "Preserve CTA and constraints. Output only requested ad copy."
    )
    system = "You are a careful short-form advertising writer. Keep claims grounded in the supplied brief."
    return provider.generate(prompt, system=system)


def _parse_direction_ideas(raw: str) -> list[dict[str, str]]:
    try:
        parsed = json.loads(raw[raw.index("["):raw.rindex("]") + 1])
    except (ValueError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError("Direction plan is not valid JSON.") from exc
    if not isinstance(parsed, list) or len(parsed) != 3:
        raise ValueError("Direction plan must contain exactly three ideas.")
    fields = ("name", "concept", "hook")
    for idea in parsed:
        if not isinstance(idea, dict) or any(
            not isinstance(idea.get(field), str) or not idea[field].strip()
            for field in fields
        ):
            raise ValueError("Each direction needs a name, concept, and hook.")
    if len({idea["name"].strip().lower() for idea in parsed}) != 3:
        raise ValueError("Direction names must be distinct.")
    if len({idea["hook"].strip().lower() for idea in parsed}) != 3:
        raise ValueError("Direction hooks must be distinct.")
    return parsed


def generate(brief_data: dict[str, Any], backend: str = "mock") -> dict[str, Any]:
    brief = AdBrief.from_json(brief_data)
    if backend == "mock":
        directions = _directions(brief)
    else:
        provider = provider_for(backend)
        planning_task = (
            "Plan exactly three distinct ad concepts: Clear (direct and benefit-led), "
            "Playful (surprising and personable), Bold (memorable but grounded). "
            "Return JSON array entries with name, concept, hook. Do not write scripts yet."
        )
        raw = _request(brief, planning_task, provider)
        try:
            ideas = _parse_direction_ideas(raw)
            directions = []
            for idea in ideas:
                task = (
                    "Write one concise ad script for this concept. "
                    f"Start with this hook: {idea['hook']}\n"
                    f"Concept: {idea['concept']}\n"
                    f"Include the required CTA and points. Target duration: {brief.duration} seconds."
                )
                script = _request(brief, task, provider)
                if not script.lower().startswith(idea["hook"].strip().lower()):
                    script = idea["hook"].strip() + "\n\n" + script
                facts = [brief.product_name, brief.description, brief.benefit, *brief.required_points, brief.cta]
                for fact in facts:
                    if fact.lower() not in script.lower():
                        script = script.rstrip() + "\n" + fact
                directions.append({
                    **idea,
                    "script": script,
                    "checks": _truthful_guard(script, brief),
                })
        except ValueError as exc:
            raise RuntimeError("The model returned malformed directions. Try again or use the offline demo.") from exc
    backend_label = provider.label if backend != "mock" else MOCK_BACKEND_LABEL
    return {"directions": directions, "backend": backend_label, "brief": asdict(brief)}


def rewrite(brief_data: dict[str, Any], text: str, action: str, backend: str = "mock") -> dict[str, Any]:
    brief = AdBrief.from_json(brief_data)
    if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
        raise ValueError("Script text must contain 1 to 20,000 characters.")
    actions = {"shorter": "Rewrite this ad to fit the target duration, keeping facts and CTA.", "hook": "Rewrite only the opening hook. Return the full ad with all other lines unchanged.", "less_salesy": "Make the language less salesy. Preserve all facts and CTA.", "playful": "Make the language more playful. Preserve all facts and CTA.", "benefit": "Make the core benefit clearer. Preserve all facts and CTA.", "line": "Improve only the first sentence; keep all remaining text unchanged."}
    if action not in actions:
        raise ValueError("Choose a supported rewrite action.")
    if backend == "mock":
        lines = text.splitlines()
        first = next((i for i, line in enumerate(lines) if line.strip()), 0)
        less_salesy = text.replace("!", ".")
        if less_salesy == text:
            lines[first] = f"For {brief.audience}: {brief.product_name} and {brief.benefit}."
            less_salesy = "\n".join(lines)
        replacements = {"shorter": f"{brief.product_name}: {brief.benefit}. {brief.cta}.", "hook": f"What if {brief.benefit} felt simpler?\n\n" + "\n".join(lines[first + 1:]), "less_salesy": less_salesy, "playful": f"Small plot twist: {brief.product_name} can help with {brief.benefit}. {brief.cta}.", "benefit": f"For {brief.audience}: {brief.product_name} helps with {brief.benefit}. {brief.cta}.", "line": f"A simpler way to think about {brief.benefit}.\n\n" + "\n".join(lines[first + 1:])}
        result = replacements[action]
    else:
        result = _request(brief, f"{actions[action]}\nExisting ad (edit only the requested part):\n{text}", provider_for(backend))
    required = [brief.product_name, brief.description, brief.benefit, *brief.required_points, brief.cta]
    missing = [fact for fact in required if fact.lower() not in result.lower()]
    if missing:
        result = result.rstrip() + "\n\n" + " ".join(missing)
    return {"text": result, "checks": _truthful_guard(result, brief)}


def make_objection(brief_data: dict[str, Any], backend: str = "mock") -> dict[str, str]:
    brief = AdBrief.from_json(brief_data)
    if backend == "mock":
        return {"objection": f"For {brief.audience}: what makes this different from the other ways to get {brief.benefit}?", "reply": "Answer with a verified detail from the brief. If it offers no proof or comparison, leave this concern unanswered."}
    raw = _request(brief, "Raise one specific, fair audience objection. Do not invent facts. Return JSON: objection and a safe reply that asks for evidence if none is supplied.", provider_for(backend))
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The model returned an unreadable objection.") from exc
    if not isinstance(result, dict) or any(not isinstance(result.get(key), str) or not result[key].strip() for key in ("objection", "reply")):
        raise RuntimeError("The model returned an incomplete objection.")
    return {key: result[key].strip()[:1000] for key in ("objection", "reply")}


def campaign(brief_data: dict[str, Any], direction: dict[str, Any], include_variants: bool = True) -> dict[str, Any]:
    brief = AdBrief.from_json(brief_data)
    if (not isinstance(direction, dict)
        or not isinstance(direction.get("script"), str)
        or not direction["script"].strip()
        or len(direction["script"]) > 20_000
        or ("name" in direction and not isinstance(direction["name"], str))):
        raise ValueError("A selected script is required to build a campaign pack.")
    if not isinstance(include_variants, bool):
        raise ValueError("include_variants must be true or false.")
    base = direction["script"]
    required = " ".join([brief.description, *brief.required_points])
    short = f"{brief.product_name}: {brief.benefit}. {required} {brief.cta}.".replace(".  ", ". ")
    variants = [{"label": "Short cut", "script": short}] if include_variants else []
    hooks = [f"A simpler way to get {brief.benefit}.", f"For {brief.audience}, small change: {brief.product_name}.", f"Make space for {brief.benefit}."]
    ctas = [brief.cta, "See how it works", "Explore the details"]
    return {
        "brief": asdict(brief),
        "selected_concept": direction.get("name", "Selected direction"),
        "main_script": base,
        "variants": variants,
        "alternate_hooks": hooks,
        "alternate_ctas": ctas,
        "checks": {
            "main_script": _truthful_guard(base, brief),
            "variants": {variant["label"]: _truthful_guard(variant["script"], brief) for variant in variants},
            "alternate_hooks": [_truthful_guard(hook, brief) for hook in hooks],
            "alternate_ctas": [_truthful_guard(cta, brief) for cta in ctas],
        },
    }


def baseline(brief_data: dict[str, Any], backend: str = "mock") -> dict[str, str]:
    brief = AdBrief.from_json(brief_data)
    provider = provider_for(backend)
    if backend == "mock":
        required = " ".join(brief.required_points)
        script = _script(brief, f"{brief.product_name}: {brief.benefit}.", f"For {brief.audience}, {brief.description}. {required}")
    else:
        script = _request(brief, f"Write one concise {brief.duration}-second ad script.", provider)
    required = [brief.product_name, brief.description, brief.benefit, *brief.required_points, brief.cta]
    for fact in required:
        if fact.lower() not in script.lower():
            script = script.rstrip() + "\n" + fact
    return {"script": script, "backend": provider.label if provider else MOCK_BACKEND_LABEL}


def _stop_engine(engine: Any) -> None:
    try:
        engine.stop()
    except Exception:
        pass


def speak(text: str, voice_id: str = "") -> dict[str, Any]:
    with _TTS_LOCK:
        return _speak_locked(text, voice_id)


def _speak_locked(text: str, voice_id: str) -> dict[str, Any]:
    try:
        import pyttsx3
    except ImportError:
        raise RuntimeError("Local voice preview is unavailable. Install pyttsx3 and a system speech engine.")
    try:
        engine = pyttsx3.init()
    except Exception as exc:
        raise RuntimeError("Local voice preview could not start. Check the system speech engine.") from exc
    try:
        if voice_id:
            available = {str(voice.id) for voice in engine.getProperty("voices")}
            if voice_id not in available:
                raise ValueError("That voice is no longer available on this system.")
            engine.setProperty("voice", voice_id)
        with tempfile.TemporaryDirectory(prefix="ad-studio-voice-") as folder:
            target = Path(folder) / "ad-preview.wav"
            lines = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith(("SCENE:", "ACTION:")):
                    continue
                line = re.sub(r"^[A-Z][A-Z0-9 _-]{0,30}:\s*", "", line)
                if line:
                    lines.append(line)
            if not lines:
                raise ValueError("Add spoken script lines before creating a voice preview.")
            engine.save_to_file(". ".join(lines), str(target))
            engine.runAndWait()
            if not target.is_file():
                raise RuntimeError("The local speech engine did not create an audio file.")
            return {"filename": target.name, "audio": target.read_bytes().hex()}
    finally:
        _stop_engine(engine)


def voices() -> list[dict[str, str]]:
    with _TTS_LOCK:
        return _voices_locked()


def _voices_locked() -> list[dict[str, str]]:
    try:
        import pyttsx3
        engine = pyttsx3.init()
    except Exception as exc:
        raise RuntimeError("Local voices are unavailable. Install pyttsx3 and a system speech engine.") from exc
    try:
        return [{"id": str(voice.id), "name": str(voice.name)} for voice in engine.getProperty("voices")]
    finally:
        _stop_engine(engine)


_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ad Studio</title><link rel="stylesheet" href="/studio.css"></head><body><main><header><div class="brand"><div class="logo" aria-hidden="true"><i></i><i></i><i></i></div><span>Ad Studio</span></div><div class="pill" id="backend-pill">Mock · offline</div></header><div class="intro"><h1>Find the line<br><em>that lands.</em></h1><p>Turn a product brief into three ad directions.</p></div><div class="layout"><aside class="panel"><h2>Your brief <button type="button" class="text-action" id="load-example">Load example brief</button></h2><div class="field"><label for="name">Product or service</label><input id="name" placeholder="e.g. Northstar Coffee"></div><div class="field"><label for="description">Product facts</label><textarea id="description" placeholder="A small-batch coffee subscription"></textarea><small>Use details you can substantiate.</small></div><div class="field"><label for="audience">Who is it for?</label><input id="audience" placeholder="People working from home"></div><div class="field"><label for="benefit">Main benefit</label><input id="benefit" placeholder="Good coffee without another errand"></div><details class="brief-options"><summary>Script settings <span id="settings-summary">15 seconds · Social video · Warm and clear</span></summary><div class="row"><div class="field"><label for="tone">Tone</label><input id="tone" value="Warm and clear"></div><div class="field"><label for="duration">Seconds</label><input id="duration" type="number" min="5" max="120" value="15"></div></div><div class="field"><label for="platform">Platform</label><select id="platform"><option>Social video</option><option>Reels</option><option>TikTok</option><option>YouTube</option><option>Radio</option><option>Other</option></select></div><div class="field"><label for="cta">Required call to action</label><input id="cta" value="Learn more"></div><div class="field"><label for="required">Must include (one per line)</label><textarea id="required" placeholder="Free delivery on first order"></textarea></div><div class="field"><label for="prohibited">Claims to avoid</label><textarea id="prohibited" placeholder="Best in the world"></textarea></div></details><div class="field"><label for="backend">Writing engine</label><select id="backend"><option value="mock">Mock · instant, offline</option><option value="llama.cpp">Local GGUF · llama.cpp</option><option value="groq">Groq · hosted</option></select><small>Engine changes apply next time. Hosted mode sends this brief to Groq.</small></div><button class="wide" id="generate">Generate 3 routes</button><div class="hint" id="status" role="status" aria-live="polite">No key needed for the demo.</div><div class="hint hidden" id="brief-edited">Based on the previous brief</div></aside><div class="content"><section class="section"><h2 id="directions-heading" tabindex="-1">Creative routes</h2><div class="empty-state" id="directions"><img src="/proof-desk.webp" alt="" width="1774" height="887"><p><strong>Your routes will appear here</strong><br>We’ll turn the brief into Clear, Playful, and Bold opening lines.</p></div></section><section class="section hidden" id="edit-section"><h2>Script editor <span>03 / REFINE</span></h2><textarea class="output" id="script" aria-label="Selected ad script" style="display:block;width:100%;min-height:150px;resize:vertical;font:inherit"></textarea><div class="toolbar" id="rewrites"><button class="secondary" data-action="shorter">Fit selected duration</button><button class="secondary" data-action="hook">Stronger hook</button><button class="secondary" data-action="less_salesy">Less salesy</button><button class="secondary" data-action="playful">More playful</button><button class="secondary" data-action="benefit">Clearer benefit</button><button class="secondary" data-action="line">Improve this line</button><button id="accept-rewrite" class="hidden">Accept draft</button><button class="secondary" id="undo">Undo</button></div><p class="hint">Each rewrite is a reviewable draft. Accept it or undo.</p><div class="checks" id="checks"></div></section><section class="section hidden" id="gremlin"><h2>03 &nbsp; Objection Gremlin</h2><p class="hint">One audience-shaped challenge. Your call: ignore it, answer it, or bring it into the script.</p><button class="secondary" id="challenge">Ask for an objection</button><div id="objection-box" class="hidden"><div class="output" id="objection"></div><div class="toolbar"><button class="secondary" data-gremlin="ignore">Ignore</button><button class="secondary" data-gremlin="answer">Answer with a verified detail</button><button class="secondary" data-gremlin="incorporate">Incorporate question</button></div><input id="verified" class="hidden" placeholder="Verified detail from your brief"><button id="apply-answer" class="hidden">Add answer</button></div><div id="gremlin-note" class="hint"></div></section><section class="section hidden" id="arena"><h2>04 &nbsp; Ad Battle Arena</h2><p class="hint">Compare the same brief through a one-prompt route and the writers’ room direction. This is exploratory feedback, not a performance study.</p><div class="grid" id="comparison"></div><div class="grid vote"><button class="secondary" data-vote="single">Vote single-prompt</button><button class="secondary" data-vote="room">Vote writers’ room</button><button class="secondary" data-vote="tie">Call it a tie</button></div><div id="vote-note" class="hint"></div></section><section class="section hidden" id="campaign"><h2>Campaign deliverables <span>04 / EXPORT</span></h2><label class="hint"><input type="checkbox" id="variants" checked> Include a short cut</label> <button id="pack">Build campaign pack</button><div class="toolbar"><label class="hint" for="voice">Local voice</label><select id="voice"><option value="">System default</option></select><button class="secondary" id="hear">Hear the ad (local)</button><button class="secondary" id="download-audio">Download audio</button></div><div id="audio-note" class="hint"></div><div id="pack-output" class="hidden"><div class="output" id="pack-text"></div><button class="secondary" id="download">Download campaign .txt</button></div></section></div></div><footer>Estimated duration is a guide. Review product claims before publishing.</footer></main><script src="/studio.js" defer></script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            body = _HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/studio.js":
            body = Path(__file__).with_name("studio.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/proof-desk.webp":
            body = Path(__file__).with_name("advertising").joinpath("assets", "proof-desk.webp").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/studio.css":
            body = Path(__file__).with_name("studio.css").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0:
                raise ValueError("Request body is empty.")
            if size > 100_000:
                raise ValueError("Request is too large.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Request body must be a JSON object.")
            route = self.path.removeprefix("/api/")
            backend = data.get("backend", "mock")
            if route == "generate": result = generate(data.get("brief", {}), backend)
            elif route == "rewrite": result = rewrite(data.get("brief", {}), data.get("text", ""), data.get("action", ""), backend)
            elif route == "objection": result = make_objection(data.get("brief", {}), backend)
            elif route == "campaign": result = campaign(data.get("brief", {}), data.get("direction", {}), data.get("include_variants", True))
            elif route == "checks":
                brief = AdBrief.from_json(data.get("brief", {}))
                text = data.get("text", "")
                if not isinstance(text, str) or len(text) > 20_000:
                    raise ValueError("Script text must be no more than 20,000 characters.")
                result = {"checks": _truthful_guard(text, brief)}
            elif route == "baseline": result = baseline(data.get("brief", {}), backend)
            elif route == "speak":
                text = data.get("text", "")
                voice = data.get("voice", "")
                if not isinstance(text, str) or len(text) > 5_000 or not isinstance(voice, str):
                    raise ValueError("Voice input is invalid or too long.")
                result = speak(text, voice)
            elif route == "voices": result = {"voices": voices()}
            else: raise ValueError("Unknown action.")
            self._json(200, result)
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": "Unexpected studio error. Try again or use mock mode."})

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Ad Studio ready at http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
