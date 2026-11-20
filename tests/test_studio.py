import json
import sys
import types
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from src import studio
from src.plan_validation import validate_plan


BRIEF = {
    "product_name": "Northstar Coffee",
    "description": "A coffee subscription delivered monthly.",
    "audience": "people working from home",
    "benefit": "good coffee without another errand",
    "cta": "Try a box",
    "required_points": ["monthly delivery"],
    "prohibited_claims": ["best in the world"],
}


class StudioTests(unittest.TestCase):
    def test_plan_validation_catches_bad_speakers_and_turn_limits(self):
        plan = {
            "topic": "coffee", "scene_description": "A kitchen.", "genre": "comedy", "script_style": "warm",
            "num_agents": 2,
            "agents": [
                {"name": "ALEX", "persona": "curious", "role": "host", "temperature": 0.6},
                {"name": "SAM", "persona": "dry", "role": "friend", "temperature": 0.5},
            ],
            "turn_order": ["ALEX", "SAM"], "max_turns": 8, "interrupt_conditions": [],
        }
        self.assertIs(validate_plan(plan), plan)
        with self.assertRaisesRegex(ValueError, "configured agent"):
            validate_plan({**plan, "turn_order": ["MISSING"]})
        with self.assertRaisesRegex(ValueError, "max_turns"):
            validate_plan({**plan, "max_turns": 1000})

    def test_brief_requires_core_fields_and_valid_duration(self):
        for missing in ("product_name", "description", "audience", "benefit"):
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                studio.AdBrief.from_json({**BRIEF, missing: ""})
        with self.assertRaisesRegex(ValueError, "5 and 120"):
            studio.AdBrief.from_json({**BRIEF, "duration": 121})

    def test_brief_rejects_malformed_api_values_instead_of_dropping_them(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            studio.AdBrief.from_json(None)
        with self.assertRaisesRegex(ValueError, "required_points"):
            studio.AdBrief.from_json({**BRIEF, "required_points": "monthly delivery"})
        with self.assertRaisesRegex(ValueError, "[Dd]uration"):
            studio.AdBrief.from_json({**BRIEF, "duration": 15.5})

    def test_mock_directions_are_three_and_distinct(self):
        result = studio.generate(BRIEF)
        self.assertEqual([x["name"] for x in result["directions"]], ["Clear", "Playful", "Bold"])
        self.assertEqual(len({x["script"] for x in result["directions"]}), 3)
        self.assertEqual(result["backend"], "Mock · offline")

    def test_multi_step_writer_calls_planner_then_each_direction(self):
        class FakeProvider:
            label = "Test · local"
            def __init__(self):
                self.prompts = []
            def generate(self, prompt, *, system=""):
                self.prompts.append(prompt)
                if len(self.prompts) == 1:
                    return '[{"name":"Clear","concept":"Direct","hook":"A"},{"name":"Playful","concept":"Twist","hook":"B"},{"name":"Bold","concept":"Strong","hook":"C"}]'
                return "Northstar Coffee gives good coffee without another errand. monthly delivery. Try a box."
        fake = FakeProvider()
        with patch.object(studio, "provider_for", return_value=fake):
            result = studio.generate(BRIEF, "groq")
        self.assertEqual(len(fake.prompts), 4)
        self.assertEqual(len(result["directions"]), 3)
        self.assertIn("monthly delivery", result["directions"][2]["script"])

    def test_multi_step_writer_rejects_malformed_plan(self):
        class FakeProvider:
            label = "Test"
            def generate(self, prompt, *, system=""):
                return "not JSON"
        with patch.object(studio, "provider_for", return_value=FakeProvider()):
            with self.assertRaisesRegex(RuntimeError, "malformed directions"):
                studio.generate(BRIEF, "groq")

    def test_multi_step_writer_rejects_duplicate_hooks(self):
        class FakeProvider:
            label = "Test"
            def generate(self, prompt, *, system=""):
                return '[{"name":"Clear","concept":"Direct","hook":"Same"},{"name":"Playful","concept":"Twist","hook":"Same"},{"name":"Bold","concept":"Strong","hook":"Third"}]'
        with patch.object(studio, "provider_for", return_value=FakeProvider()):
            with self.assertRaisesRegex(RuntimeError, "malformed directions"):
                studio.generate(BRIEF, "groq")

    def test_rewrite_keeps_required_point_and_cta(self):
        original = "Meet Northstar Coffee. It brings monthly delivery to your door. Try a box."
        result = studio.rewrite(BRIEF, original, "shorter")
        self.assertIn("monthly delivery", result["text"])
        self.assertIn("Try a box", result["text"])
        self.assertEqual(original, "Meet Northstar Coffee. It brings monthly delivery to your door. Try a box.")

    def test_less_salesy_action_changes_the_hook_without_losing_brief(self):
        original = studio.generate(BRIEF)["directions"][0]["script"]
        result = studio.rewrite(BRIEF, original, "less_salesy")
        self.assertNotEqual(result["text"], original)
        for fact in ("Northstar Coffee", "good coffee without another errand", "monthly delivery", "Try a box"):
            self.assertIn(fact, result["text"])

    def test_unknown_rewrite_action_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supported rewrite"):
            studio.rewrite(BRIEF, "text", "rewrite everything")

    def test_objection_is_brief_and_bounded(self):
        result = studio.make_objection(BRIEF)
        self.assertIn("people working from home", result["objection"])
        self.assertIn("proof", result["reply"])

    def test_model_objection_shape_is_checked(self):
        class FakeProvider:
            label = "Test"
            def generate(self, prompt, *, system=""):
                return '{"objection":"Why?"}'
        with patch.object(studio, "provider_for", return_value=FakeProvider()):
            with self.assertRaisesRegex(RuntimeError, "incomplete objection"):
                studio.make_objection(BRIEF, "groq")

    def test_campaign_uses_selected_copy_and_brief_cta(self):
        direction = studio.generate(BRIEF)["directions"][0]
        result = studio.campaign(BRIEF, direction)
        self.assertEqual(result["main_script"], direction["script"])
        self.assertEqual(result["brief"]["product_name"], "Northstar Coffee")
        self.assertTrue(result["variants"][0]["script"].endswith("Try a box."))
        self.assertIn("monthly delivery", result["variants"][0]["script"])
        self.assertIn("Short cut", result["checks"]["variants"])
        self.assertEqual(len(result["alternate_hooks"]), 3)

    def test_baseline_uses_same_brief_constraints(self):
        result = studio.baseline(BRIEF)
        self.assertIn("monthly delivery", result["script"])
        self.assertIn("Try a box", result["script"])
        self.assertEqual(result["backend"], "Mock · offline")

    def test_checks_report_cta_and_prohibited_claim(self):
        brief = studio.AdBrief.from_json(BRIEF)
        checks = studio._truthful_guard("The best in the world.", brief)
        self.assertEqual(checks[0], "CTA included: False")
        self.assertIn("best in the world", checks[3])

    def test_backend_configuration_errors_are_readable(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                studio.provider_for("groq")
            with self.assertRaisesRegex(RuntimeError, "existing GGUF"):
                studio.provider_for("llama.cpp")

    def test_local_model_provider_is_reused_for_follow_up_actions(self):
        class FakeLlama:
            def __init__(self, **kwargs):
                self.options = kwargs
        with tempfile.NamedTemporaryFile() as model:
            fake_module = types.SimpleNamespace(Llama=FakeLlama)
            studio._clear_provider_cache()
            with patch.dict(sys.modules, {"llama_cpp": fake_module}), patch.dict("os.environ", {"LLAMA_CPP_MODEL_PATH": model.name}):
                first = studio.provider_for("llama.cpp")
                second = studio.provider_for("llama.cpp")
            self.assertIs(first, second)
            studio._clear_provider_cache()

    def test_campaign_rejects_missing_script(self):
        with self.assertRaisesRegex(ValueError, "selected script"):
            studio.campaign(BRIEF, {})

    def test_hosted_rate_limit_and_timeout_are_readable(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            provider = studio.GroqProvider()
        error = urllib.error.HTTPError("https://example.invalid", 429, "limited", {}, None)
        with patch.object(studio.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "rate limited"):
                provider.generate("test")
        error = urllib.error.HTTPError("https://example.invalid", 401, "unauthorized", {}, None)
        with patch.object(studio.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "API key"):
                provider.generate("test")
        error = urllib.error.HTTPError("https://example.invalid", 404, "missing", {}, None)
        with patch.object(studio.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "GROQ_MODEL"):
                provider.generate("test")
        with patch.object(studio.urllib.request, "urlopen", side_effect=TimeoutError()):
            with self.assertRaisesRegex(RuntimeError, "30 second limit"):
                provider.generate("test")

    def test_hosted_request_uses_current_groq_completion_options(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"choices":[{"message":{"content":"A short line."},"finish_reason":"stop"}]}'

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            provider = studio.GroqProvider()
        with patch.object(studio.urllib.request, "urlopen", return_value=Response()) as urlopen:
            self.assertEqual(provider.generate("Write one line."), "A short line.")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["max_completion_tokens"], 1600)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertIs(payload["include_reasoning"], False)
        self.assertNotIn("reasoning_format", payload)
        self.assertNotIn("max_tokens", payload)

    def test_tts_unavailable_is_actionable(self):
        with patch.dict(sys.modules, {"pyttsx3": None}):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                studio.speak("Hello")
        with patch.dict(sys.modules, {"pyttsx3": None}):
            with self.assertRaisesRegex(RuntimeError, "voices are unavailable"):
                studio.voices()

    def test_voice_list_uses_and_stops_system_engine(self):
        class FakeEngine:
            stopped = False
            def getProperty(self, name):
                return [types.SimpleNamespace(id="en-test", name="English test")]
            def stop(self):
                self.stopped = True
        engine = FakeEngine()
        fake_module = types.SimpleNamespace(init=lambda: engine)
        with patch.dict(sys.modules, {"pyttsx3": fake_module}):
            self.assertEqual(studio.voices(), [{"id": "en-test", "name": "English test"}])
        self.assertTrue(engine.stopped)

    def test_tts_fake_success_writes_temp_audio_and_strips_speaker_label(self):
        captured = {}
        class FakeEngine:
            stopped = False
            def save_to_file(self, text, path):
                captured["text"] = text
                with open(path, "wb") as audio:
                    audio.write(b"fake-wav")
            def runAndWait(self):
                pass
            def stop(self):
                self.stopped = True
        fake_module = types.SimpleNamespace(init=lambda: FakeEngine())
        with patch.dict(sys.modules, {"pyttsx3": fake_module}):
            engine = fake_module.init()
            with patch.object(fake_module, "init", return_value=engine):
                result = studio.speak("SCENE: Kitchen\n\nALEX: Good morning.")
        self.assertEqual(captured["text"], "Good morning.")
        self.assertEqual(bytes.fromhex(result["audio"]), b"fake-wav")
        self.assertTrue(engine.stopped)

    def test_html_contains_core_flow_and_status(self):
        for text in ('aria-live="polite"', "Generate 3 routes", "Objection Gremlin", "Ad Battle Arena", "Campaign deliverables"):
            with self.subTest(text=text):
                self.assertIn(text, studio._HTML)


if __name__ == "__main__":
    unittest.main()
