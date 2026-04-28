"""
Car Diagnostic Engine
Pure functions — no input()/print() calls.
Each function takes user answers as arguments and returns a dict:
  {
    "message": str,          # response text to show the user
    "follow_up": str | None, # next question to ask (None = done)
    "done": bool             # True when this diagnosis branch is complete
  }
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resp(message: str, follow_up: Optional[str] = None, done: bool = False) -> dict:
    return {"message": message.strip(), "follow_up": follow_up, "done": done}


def _parse_miles(raw: str) -> Optional[int]:
    try:
        cleaned = raw.lower().replace(",", "").replace("k", "000").strip()
        return int(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# KEYWORD ROUTER
# ---------------------------------------------------------------------------

KEYWORD_MAP = {
    # Engine
    "misfire": "misfire",
    "rough idle": "misfire",
    "stalling": "misfire",
    "rough": "misfire",
    "knock": "knock",
    "tapping": "knock",
    "ticking": "knock",
    "compression": "compression",
    "loss of power": "compression",
    "timing": "timing",
    "oil pressure": "oil_pressure",
    "oil light": "oil_pressure",
    "vacuum leak": "vacuum",
    "vacuum": "vacuum",
    "overheat": "overheat",
    "overheating": "overheat",
    "temperature": "overheat",
    "smoke": "smoke",
    "backfire": "backfire",
    "afterfire": "backfire",
    # Electrical
    "battery": "battery",
    "starter": "starter",
    "crank": "starter",
    "won't start": "starter",
    "alternator": "alternator",
    "charging": "alternator",
    "ground": "ground",
    "fuse": "fuse",
    "relay": "fuse",
    "sensor": "sensor",
    "p0": "sensor",
    "obd": "sensor",
    "drain": "drain",
    "parasitic": "drain",
    "short": "short",
    "open circuit": "short",
    "wiring": "short",
    "canbus": "canbus",
    "can bus": "canbus",
    "u0": "canbus",
    "communication": "canbus",
}

MENU_TEXT = """🚗 ULTIMATE CAR DIAGNOSTIC BOT

ENGINE SYMPTOMS:
  misfire · knock · compression · timing
  oil pressure · vacuum leak · overheat · smoke · backfire

ELECTRICAL SYMPTOMS:
  battery · starter · alternator · ground · fuse
  sensor · drain · short · canbus

Just describe your problem in plain English or use one of the keywords above.
Type 'help' to see this again."""


def route(text: str) -> Optional[str]:
    """Map a user message to a diagnosis key. Returns None if unrecognised."""
    t = text.lower().strip()
    for keyword, key in KEYWORD_MAP.items():
        if keyword in t:
            return key
    return None


# ---------------------------------------------------------------------------
# STATEFUL SESSION
# ---------------------------------------------------------------------------


class DiagSession:
    """
    Holds the state for one multi-turn diagnostic conversation.
    Call .respond(user_message) each turn; it returns a response dict.
    """

    def __init__(self):
        self.topic: Optional[str] = None  # current diagnosis branch
        self.step: int = 0  # which question we're on
        self.data: dict = {}  # answers collected so far
        self.history: list[dict] = []  # full turn log

    # ------------------------------------------------------------------
    def respond(self, user_message: str) -> dict:
        text = user_message.strip()
        result = self._dispatch(text)
        self.history.append({"user": text, "bot": result["message"]})
        if result.get("done"):
            self._reset()
        return result

    def _reset(self):
        self.topic = None
        self.step = 0
        self.data = {}

    # ------------------------------------------------------------------
    def _dispatch(self, text: str) -> dict:
        t = text.lower()

        # Global commands
        if t in ("help", "menu", "start"):
            self._reset()
            return _resp(MENU_TEXT, follow_up=None, done=False)
        if t in ("quit", "exit", "q"):
            return _resp("Goodbye! Safe driving and happy wrenching. 🔧", done=True)

        # Mid-session: continue current topic
        if self.topic:
            return self._continue(text)

        # New topic detection
        key = route(text)
        if key:
            self.topic = key
            self.step = 0
            self.data = {}
            return self._continue(text)

        return _resp(
            "⚠️ I didn't recognise that symptom.\n" + MENU_TEXT, follow_up=None
        )

    # ------------------------------------------------------------------
    def _continue(self, text: str) -> dict:
        handlers = {
            "misfire": _misfire,
            "knock": _knock,
            "compression": _compression,
            "timing": _timing,
            "oil_pressure": _oil_pressure,
            "vacuum": _vacuum,
            "overheat": _overheat,
            "smoke": _smoke,
            "backfire": _backfire,
            "battery": _battery,
            "starter": _starter,
            "alternator": _alternator,
            "ground": _ground,
            "fuse": _fuse,
            "sensor": _sensor,
            "drain": _drain,
            "short": _short,
            "canbus": _canbus,
        }
        fn = handlers.get(self.topic)
        if not fn:
            self._reset()
            return _resp("Unknown topic. " + MENU_TEXT, done=True)

        result = fn(self.step, text, self.data)
        self.step += 1
        return result


# ---------------------------------------------------------------------------
# DIAGNOSIS FUNCTIONS
# Each takes (step, answer, data) and returns a response dict.
# step=0 is always the opening question.
# ---------------------------------------------------------------------------

# ── MISFIRE ─────────────────────────────────────────────────────────────────


def _misfire(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Misfire / Rough Idle / Stalling ---\n"
            "Any check engine code? (e.g. P0301–P0306, or type 'none')",
            follow_up="OBD code",
        )
    if step == 1:
        data["code"] = a
        if "p030" in a:
            cyl = a.strip()[-1]
            data["cylinder"] = cyl
            return _resp(
                f"📌 Cylinder {cyl} misfire detected.\n\n"
                f"Possible causes:\n"
                f"  • Bad spark plug or ignition coil on cylinder {cyl}\n"
                f"  • Clogged or leaking fuel injector\n"
                f"  • Vacuum leak near that intake runner\n"
                f"  • Low compression in that cylinder\n\n"
                f"Diagnostic steps:\n"
                f"  1. Swap coil from cylinder {cyl} with an adjacent one and re-scan.\n"
                f"     If misfire code follows the coil → replace that coil.\n"
                f"  2. If misfire stays on same cylinder → do a compression test.\n"
                f"  3. If compression is good → swap fuel injector.\n\n"
                f"What's the vehicle's mileage?",
                follow_up="mileage",
            )
        else:
            return _resp(
                "No cylinder-specific code. Common causes:\n"
                "  1. Worn spark plugs or ignition coils\n"
                "  2. Clogged fuel injectors or failing fuel pump\n"
                "  3. Dirty/failed MAF sensor\n"
                "  4. TPS fault\n"
                "  5. EGR valve stuck open\n"
                "  6. CKP sensor failing intermittently\n"
                "  7. Low fuel pressure\n\n"
                "Does it get worse at idle, acceleration, or both?",
                follow_up="idle or acceleration",
            )
    if step == 2:
        if data.get("cylinder"):
            miles = _parse_miles(answer)
            if miles and miles >= 60000:
                advice = (
                    "⚠️ At this mileage, inspect ALL spark plugs and replace if worn."
                )
            elif miles:
                advice = "Low mileage — spark plugs likely OK. Focus on coil/injector swap test first."
            else:
                advice = "Tip: check spark plug gap and condition as a first step."
            return _resp(advice, done=True)
        else:
            if "idle" in a:
                focus = "→ Focus on: EGR valve, vacuum leaks, dirty throttle body, IAC motor."
            elif "accel" in a:
                focus = "→ Focus on: Fuel pressure, ignition coils under load, MAF sensor, clogged injectors."
            else:
                focus = "→ Recommend full tune-up: plugs, coils, fuel filter, clean MAF and throttle body."
            data["rpm_issue"] = a
            return _resp(f"{focus}\n\nApproximate mileage?", follow_up="mileage")
    if step == 3:
        miles = _parse_miles(answer)
        if miles and miles >= 100000:
            advice = "⚠️ High mileage: replace spark plugs, clean/replace fuel injectors, inspect coil boots."
        elif miles and miles >= 60000:
            advice = "Consider: spark plug replacement and MAF sensor cleaning as starting points."
        else:
            advice = "Low mileage misfires often point to ignition coil failure or injector issue. Run coil swap test."
        return _resp(advice, done=True)
    return _resp(
        "Misfire diagnosis complete. Type a new symptom to continue.", done=True
    )


# ── KNOCK ────────────────────────────────────────────────────────────────────


def _knock(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Knocking / Tapping Noises ---\n"
            "When does it knock? (idle / acceleration / hot / cold / always)",
            follow_up="when",
        )
    if step == 1:
        data["when"] = a
        if "hot" in a:
            msg = (
                "📌 Hot knock / low-speed knock:\n"
                "  • Oil too thin, degraded, or level low\n"
                "  • Possible worn rod or main bearings\n"
                "  → Check oil level and condition immediately.\n"
                "  → If knock persists after fresh oil: test oil pressure.\n\n"
                "When was the last oil change?"
            )
            return _resp(msg, follow_up="last oil change")
        if "cold" in a:
            return _resp(
                "📌 Cold knock (disappears after warm-up):\n"
                "  • Piston slap — minor slap is normal in worn engines\n"
                "  • Worn wrist pins (more metallic)\n"
                "  • Hydraulic lifter noise that quiets as oil circulates\n"
                "  → If it disappears within 60s: monitor, not urgent.\n"
                "  → If it lingers: do oil pressure test when warm.\n\n"
                "Does the knock frequency change with RPM? (y/n)",
                follow_up="rpm linked",
            )
        if "accel" in a:
            return _resp(
                "📌 Knock under acceleration (spark knock / detonation):\n"
                "  • Wrong octane fuel — try premium\n"
                "  • Ignition timing too advanced\n"
                "  • Carbon buildup raising compression\n"
                "  • Faulty coolant temp sensor (incorrect timing advance)\n"
                "  • Clogged EGR\n"
                "  → First try: premium fuel + fuel system cleaner.\n"
                "  → If persists: scan for knock sensor codes P0325–P0332.\n\n"
                "Does the knock frequency change with RPM? (y/n)",
                follow_up="rpm linked",
            )
        return _resp(
            "📌 General knocking / tapping:\n"
            "  • Deep rhythmic knock at engine speed → worn rod/main bearings (serious!)\n"
            "  • Light tapping (valve train) → worn lifters, low oil\n"
            "  • Metallic rattle on startup → timing chain tensioner worn\n"
            "  • Ticking near exhaust → exhaust manifold leak\n\n"
            "Does the knock frequency change with RPM? (y/n)",
            follow_up="rpm linked",
        )
    if step == 2:
        if data.get("when") == "hot":
            return _resp(
                f"Last oil change noted: {answer}.\n"
                "→ Change oil now if overdue. Use manufacturer-spec viscosity.\n"
                "→ If knock persists after fresh oil: check oil pressure.\n\n"
                "Does the knock change frequency with RPM? (y/n)",
                follow_up="rpm linked",
            )
        if "y" in a:
            return _resp(
                "→ Engine-speed linked knock = likely internal (bearings, pistons, valves).\n"
                "   Needs urgent inspection — do not ignore.",
                done=True,
            )
        return _resp(
            "→ Constant-frequency noise may be an accessory:\n"
            "   AC compressor, power steering pump, or alternator bearing.",
            done=True,
        )
    if step == 3:
        if "y" in a:
            return _resp(
                "→ Engine-speed linked knock = likely internal. Urgent inspection needed.",
                done=True,
            )
        return _resp(
            "→ Constant-frequency = likely an accessory bearing. Check AC compressor, PS pump, alternator.",
            done=True,
        )
    return _resp("Knock diagnosis complete.", done=True)


# ── COMPRESSION ──────────────────────────────────────────────────────────────


def _compression(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Low Compression / Loss of Power ---\n"
            "Have you done a compression test? (y/n)",
            follow_up="compression test done",
        )
    if step == 1:
        data["tested"] = a
        if "y" in a:
            return _resp(
                "Enter compression readings per cylinder, comma-separated.\n"
                "Example: 150,148,90,151",
                follow_up="readings",
            )
        return _resp(
            "Compression test procedure:\n"
            "  1. Warm engine, then shut off.\n"
            "  2. Remove all spark plugs.\n"
            "  3. Disable fuel & ignition (pull injector fuse/relay).\n"
            "  4. Thread gauge into each cylinder, crank 4–6 times.\n"
            "  5. Record all readings and compare.\n\n"
            "Healthy range: ~140–180 psi (gasoline engines).\n"
            "If all cylinders are low: check if timing belt/chain skipped a tooth first.\n\n"
            "Are two adjacent cylinders low? (y/n)",
            follow_up="adjacent low",
        )
    if step == 2:
        if data.get("tested", "").startswith("y"):
            # Parse readings
            try:
                readings = [int(x.strip()) for x in answer.split(",")]
                max_v = max(readings)
                min_v = min(readings)
                spread = round((max_v - min_v) / max_v * 100, 1)
                low_cyls = [i + 1 for i, v in enumerate(readings) if v < max_v * 0.75]
                borderline = [
                    i + 1
                    for i, v in enumerate(readings)
                    if max_v * 0.75 <= v < max_v * 0.90
                ]
                msg = f"📊 Results: max={max_v} psi, min={min_v} psi, spread={spread}%\n\n"
                if spread > 25:
                    msg += (
                        f"⚠️ Cylinders {low_cyls} are critically low (>25% below max).\n"
                        "  → Perform WET compression test (squirt oil in, retest):\n"
                        "     - Rises with oil → worn piston rings\n"
                        "     - Stays low with oil → burnt/leaking valves or head gasket"
                    )
                elif spread > 10:
                    msg += (
                        f"⚠️ Cylinders {borderline or low_cyls} are borderline (10–25% below max).\n"
                        "  → Do wet test on those cylinders. Monitor for developing misfire codes."
                    )
                else:
                    if min_v < 120:
                        msg += (
                            f"⚠️ Spread is acceptable but overall compression is low ({min_v} psi).\n"
                            "  → May indicate worn rings throughout or jumped timing chain."
                        )
                    else:
                        msg += "✅ Compression is within spec. Power loss is likely fuel, ignition, or sensor related."
                data["readings_parsed"] = True
                return _resp(
                    msg + "\n\nAre two adjacent cylinders notably lower? (y/n)",
                    follow_up="adjacent",
                )
            except ValueError:
                return _resp(
                    "Couldn't parse that. Use comma-separated numbers e.g. 150,148,90,151\n"
                    "Are two adjacent cylinders low? (y/n)",
                    follow_up="adjacent",
                )
        else:
            if "y" in a:
                return _resp(
                    "📌 Two adjacent low cylinders = head gasket failure between those cylinders is very likely.\n"
                    "  → Check for: white exhaust smoke, coolant loss without visible leak, milky oil on dipstick.",
                    done=True,
                )
            return _resp(
                "No adjacent low cylinders noted. Run the compression test to confirm diagnosis.",
                done=True,
            )
    if step == 3:
        if "y" in a:
            return _resp(
                "📌 Two adjacent low cylinders = head gasket failure between those cylinders is very likely.\n"
                "  → Signs to confirm: white exhaust smoke, coolant loss without visible leak, milky oil.",
                done=True,
            )
        return _resp("Compression diagnosis complete. Results noted above.", done=True)
    return _resp("Compression diagnosis complete.", done=True)


# ── TIMING ───────────────────────────────────────────────────────────────────


def _timing(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Timing Belt/Chain Issues ---\n"
            "What are the symptoms? (rattling / no start / rough idle / check engine / noise on startup)",
            follow_up="symptoms",
        )
    if step == 1:
        data["symptoms"] = a
        if "rattle" in a or "noise" in a:
            return _resp(
                "📌 Rattling / startup noise:\n"
                "  • Timing chain tensioner worn or failed\n"
                "  • Low oil pressure starving tensioner\n"
                "  • Timing chain stretch\n"
                "  → Check oil level first. If OK: replace chain, tensioner, and guides together.\n\n"
                "Is your engine interference or non-interference type? (interference / non-interference / unknown)",
                follow_up="engine type",
            )
        if "no start" in a:
            return _resp(
                "⚠️ Possible broken timing belt/chain — DO NOT crank engine further!\n"
                "  On interference engines, a jumped or broken belt BENDS valves.\n"
                "  → Remove timing/valve cover to inspect belt/chain visually first.\n\n"
                "Is your engine interference or non-interference type? (interference / non-interference / unknown)",
                follow_up="engine type",
            )
        if "check engine" in a:
            return _resp(
                "📌 Timing-related codes:\n"
                "  P0016/P0017: Crank-to-cam correlation error\n"
                "    → Stretched timing chain, failed cam phaser, or low oil (VVT needs oil pressure)\n"
                "  P0340/P0341: Camshaft position sensor\n"
                "  P0335/P0336: Crankshaft position sensor\n"
                "  → Check oil level first. If OK: inspect chain stretch and VVT solenoid screen.\n\n"
                "How old is the timing belt/chain service? (mileage or 'unknown')",
                follow_up="service age",
            )
        return _resp(
            "General timing maintenance:\n"
            "  • Timing BELT: replace every 60k–100k miles (check owner's manual)\n"
            "  • Timing CHAIN: usually lifetime, but stretches with poor oil maintenance\n"
            "  • Always replace water pump, tensioner, and idler pulleys with the belt\n\n"
            "How old is the timing belt/chain service? (mileage or 'unknown')",
            follow_up="service age",
        )
    if step == 2:
        if "interference" in a:
            return _resp(
                "⚠️ INTERFERENCE engine: assume valve damage until proven otherwise.\n"
                "  Use a borescope through the spark plug holes before cranking.\n"
                "  → If valves are bent: head rebuild/replacement required.",
                done=True,
            )
        if "non" in a:
            return _resp(
                "Non-interference engine: belt break won't bend valves.\n"
                "  → Replace belt and attempt start. Check CKP sensor if still no-start.",
                done=True,
            )
        if "unknown" in a or _parse_miles(a) is not None or a:
            if "unknown" in a:
                return _resp(
                    "⚠️ Service date unknown — treat as overdue.\n"
                    "  A broken timing belt is catastrophic and strands you without warning.",
                    done=True,
                )
            return _resp(
                f"Timing service age noted: {answer}.\n"
                "Cross-check with your vehicle's service interval in the owner's manual.",
                done=True,
            )
    return _resp("Timing diagnosis complete.", done=True)


# ── OIL PRESSURE ─────────────────────────────────────────────────────────────


def _oil_pressure(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Oil Pressure Problems ---\n"
            "Is the oil pressure warning light on? (y/n)",
            follow_up="warning light",
        )
    if step == 1:
        data["light"] = a
        if "y" in a:
            return _resp(
                "⚠️ STOP THE ENGINE IMMEDIATELY if still running!\n"
                "Running with low/no oil pressure destroys bearings within minutes.\n\n"
                "Diagnostic steps (engine OFF):\n"
                "  1. Check oil level on dipstick — add oil if low.\n"
                "  2. If oil is full: suspect a bad oil pressure sensor (common, cheap fix).\n"
                "     Unplug sensor connector — if light goes out → likely bad sensor.\n"
                "  3. Verify with a mechanical oil pressure gauge (screw-in tester).\n"
                "  4. If mechanical gauge also reads low → oil pump failure or blocked pickup screen.\n\n"
                "What's the vehicle's mileage?",
                follow_up="mileage",
            )
        return _resp(
            "Intermittent / suspected low pressure without warning light:\n"
            "  • Oil viscosity too thin (wrong grade or degraded oil)\n"
            "  • Partially clogged oil pickup screen\n"
            "  • Worn oil pump\n"
            "  • Excessive bearing clearances\n"
            "  → Install a mechanical oil pressure gauge to confirm.\n"
            "  → Normal rule of thumb: ~10 psi per 1000 RPM.\n\n"
            "Any ticking or rattling noise at startup? (y/n)",
            follow_up="startup noise",
        )
    if step == 2:
        if data.get("light", "").startswith("y"):
            miles = _parse_miles(answer)
            if miles and miles > 150000:
                advice = "⚠️ High mileage: bearing wear is a real possibility. Check oil for metallic debris."
            else:
                advice = "Start with oil level check, fresh oil change, and oil pressure sensor test."
            return _resp(
                f"{advice}\n\nAny ticking or rattling at startup? (y/n)",
                follow_up="startup noise",
            )
        if "y" in a:
            return _resp(
                "→ Hydraulic lifters or timing chain tensioner starved of oil at startup.\n"
                "  → Ensure oil level is correct. Consider shorter oil change intervals.\n"
                "  → In cold climates: use oil with better cold-flow rating.",
                done=True,
            )
        return _resp(
            "Oil pressure diagnosis complete. Monitor and retest with a mechanical gauge.",
            done=True,
        )
    if step == 3:
        if "y" in a:
            return _resp(
                "→ Startup ticking: hydraulic lifters or timing chain tensioner starved of oil.\n"
                "  → Correct oil level, shorten oil change interval, check cold-flow rating.",
                done=True,
            )
        return _resp(
            "No startup noise noted. Proceed with mechanical pressure gauge test.",
            done=True,
        )
    return _resp("Oil pressure diagnosis complete.", done=True)


# ── VACUUM LEAK ───────────────────────────────────────────────────────────────


def _vacuum(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Vacuum Leaks ---\n"
            "Symptoms: high/erratic idle, surging, stalling, lean codes.\n\n"
            "Any lean codes? (P0171 / P0174, or 'no')",
            follow_up="lean codes",
        )
    if step == 1:
        data["codes"] = a
        base = (
            "\nCommon vacuum leak locations:\n"
            "  1. Intake manifold gasket (very common on V6/V8 engines)\n"
            "  2. Cracked or disconnected vacuum hoses\n"
            "  3. Brake booster vacuum line\n"
            "  4. PCV valve or hose (often hardened/cracked)\n"
            "  5. Throttle body gasket\n"
            "  6. EGR valve diaphragm\n"
            "  7. EVAP purge solenoid hose\n\n"
            "Diagnosis methods:\n"
            "  A. Carb cleaner spray around suspect areas at idle — RPM rise = leak found (fire hazard, be careful!)\n"
            "  B. Smoke test: injects smoke into intake; leaks visible as smoke escaping\n"
            "  C. MAP sensor live data: should read ~8–12 inHg at idle\n\n"
            "Does idle RPM change when the engine is fully warm? (y/n)"
        )
        if "p017" in a or "p0174" in a:
            both = "p0171" in a and "p0174" in a
            prefix = (
                "📌 Both banks lean (P0171+P0174) = large leak or dirty MAF sensor.\n"
                "  → Clean MAF sensor first (cheap & easy). If codes return → smoke test."
                if both
                else "📌 Single bank lean = localized leak on that bank's side.\n"
                "  → Inspect hoses on that bank specifically."
            )
            return _resp(prefix + base, follow_up="warm idle change")
        return _resp("No lean codes." + base, follow_up="warm idle change")
    if step == 2:
        if "y" in a:
            return _resp(
                "→ Thermal expansion changes leak size when warm.\n"
                "  PCV hoses and intake manifold gaskets are prime suspects.\n"
                "  → Focus carb-cleaner test in those areas when engine is fully warm.",
                done=True,
            )
        return _resp(
            "→ Leak may only be present when cold or at a fixed size.\n"
            "  Smoke test is the most reliable method for stubborn leaks.",
            done=True,
        )
    return _resp("Vacuum leak diagnosis complete.", done=True)


# ── OVERHEATING ───────────────────────────────────────────────────────────────


def _overheat(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Engine Overheating ---\n"
            "Is coolant level low in the reservoir or radiator? (y/n)",
            follow_up="coolant low",
        )
    if step == 1:
        data["coolant_low"] = a
        return _resp(
            "Does the radiator fan run when the engine is hot (or AC is on)? (y/n)",
            follow_up="fan works",
        )
    if step == 2:
        data["fan"] = a
        return _resp("White smoke from the exhaust? (y/n)", follow_up="white smoke")
    if step == 3:
        data["smoke"] = a
        return _resp(
            "Does the interior heater blow hot air? (y/n)", follow_up="heater works"
        )
    if step == 4:
        data["heater"] = a
        lines = ["📊 Overheating Analysis:\n"]
        if data.get("smoke", "").startswith("y") and data.get(
            "coolant_low", ""
        ).startswith("y"):
            lines.append(
                "⚠️ STRONG HEAD GASKET FAILURE SIGNS:\n"
                "  Coolant loss + white smoke = coolant burning in cylinders.\n"
                "  DO NOT continue driving — engine damage worsens rapidly.\n"
                "  → Confirm with: block tester (combustion gases in coolant), compression test on adjacent cylinders."
            )
        elif data.get("smoke", "").startswith("y"):
            lines.append(
                "⚠️ White smoke even without low coolant can indicate a seeping head gasket.\n"
                "  → Check for milky oil on dipstick or under oil cap, sweet exhaust smell."
            )
        if data.get("coolant_low", "").startswith("y") and not data.get(
            "smoke", ""
        ).startswith("y"):
            lines.append(
                "📌 Coolant leak without white smoke (external leak):\n"
                "  → Check radiator, hoses, water pump weep hole, heater core.\n"
                "  → Pressure-test cooling system to find the source."
            )
        if data.get("fan", "").startswith("n"):
            lines.append(
                "📌 Cooling fan not running:\n"
                "  → Check fan fuse, fan relay, coolant temp sensor signal, fan motor.\n"
                "  → Test: unplug coolant temp sensor — many cars run fan at full speed as a failsafe."
            )
        if data.get("heater", "").startswith("n") and not data.get(
            "coolant_low", ""
        ).startswith("y"):
            lines.append(
                "📌 No heat + coolant OK + overheating:\n"
                "  → Air pocket trapped in cooling system (air in heater core = no heat)\n"
                "  → Stuck thermostat / failed water pump impeller\n"
                "  → Bleed/burp the cooling system, then test thermostat in hot water."
            )
        if (
            data.get("fan", "").startswith("y")
            and not data.get("coolant_low", "").startswith("y")
            and not data.get("smoke", "").startswith("y")
            and data.get("heater", "").startswith("y")
        ):
            lines.append(
                "📌 Subtle overheating with no obvious cause:\n"
                "  → Clogged/corroded radiator core\n"
                "  → Stuck thermostat (partially closed)\n"
                "  → Failing water pump (worn impeller)\n"
                "  → Flush and refill coolant if old or discoloured."
            )
        return _resp("\n".join(lines), done=True)
    return _resp("Overheating diagnosis complete.", done=True)


# ── SMOKE ─────────────────────────────────────────────────────────────────────


def _smoke(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Exhaust Smoke Color ---\n"
            "What color is the smoke? (white / blue / black / gray)",
            follow_up="color",
        )
    if step == 1:
        data["color"] = a
        if "white" in a:
            return _resp(
                "📌 White smoke:\n"
                "  A thin white puff on cold startup = normal condensation (disappears in 1–2 min).\n\n"
                "Does it persist after the engine is fully warm? (y/n)",
                follow_up="persists",
            )
        if "blue" in a:
            return _resp(
                "📌 Blue smoke = oil burning in combustion chamber.\n"
                "  Causes:\n"
                "  • Worn piston rings (worse under load/acceleration)\n"
                "  • Worn valve stem seals (worse at startup after sitting)\n"
                "  • Failing PCV system\n"
                "  • Turbo oil seal leak\n\n"
                "Is it worse on startup, under acceleration, or both? (startup / accel / both)",
                follow_up="when worse",
            )
        if "black" in a:
            return _resp(
                "📌 Black smoke = excess unburned fuel (rich mixture).\n"
                "  Causes:\n"
                "  • Faulty O2 sensor\n"
                "  • Dirty/failed MAF sensor\n"
                "  • Leaking or stuck-open fuel injector\n"
                "  • High fuel pressure (stuck fuel pressure regulator)\n"
                "  • Clogged air filter\n"
                "  → Check: air filter, scan for O2/MAF codes, live fuel trim data.\n"
                "  → Negative long-term fuel trim confirms rich condition.",
                done=True,
            )
        if "gray" in a:
            return _resp(
                "📌 Gray smoke = often oil or incomplete combustion.\n"
                "  • Failed PCV system forcing oil mist into intake\n"
                "  • Automatic transmission fluid sucked into intake (leaking vacuum modulator)\n"
                "  → Inspect PCV valve and hoses. Check ATF level on automatic transmissions.",
                done=True,
            )
        return _resp(
            "Common colors: white, blue, black, gray. Please describe the smoke color.",
            follow_up="color",
        )
    if step == 2:
        if "white" in data.get("color", ""):
            if "y" in a:
                return _resp(
                    "⚠️ Persistent white smoke = coolant entering the combustion chamber.\n"
                    "  Causes: head gasket failure, cracked cylinder head, cracked block.\n"
                    "  → Confirm with: block tester, compression test on adjacent cylinders.\n"
                    "  → Check for milky oil residue on dipstick or inside oil cap.",
                    done=True,
                )
            return _resp(
                "✅ Cold-start condensation — completely normal. No action needed.",
                done=True,
            )
        if "blue" in data.get("color", ""):
            if "startup" in a:
                return _resp(
                    "→ Worse on startup: valve stem seals most likely.\n"
                    "  Oil pools on valves overnight and burns off when engine first starts.",
                    done=True,
                )
            if "accel" in a:
                return _resp(
                    "→ Worse under load: piston rings most likely.\n"
                    "  Oil bypasses rings under combustion pressure.",
                    done=True,
                )
            return _resp(
                "→ Both startup and acceleration: severe ring and/or seal wear.\n"
                "  Do compression and leak-down tests to confirm.",
                done=True,
            )
    return _resp("Smoke diagnosis complete.", done=True)


# ── BACKFIRE ──────────────────────────────────────────────────────────────────


def _backfire(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Backfire / Afterfire ---\n"
            "Does it backfire on deceleration or acceleration? (decel / accel)",
            follow_up="when",
        )
    if step == 1:
        data["when"] = a
        if "decel" in a:
            return _resp(
                "📌 Backfire / popping on deceleration:\n"
                "  • Unburned fuel igniting in hot exhaust\n"
                "  • Vacuum leak, exhaust leak (air drawn in on decel), oversized exhaust\n"
                "  • Very common on modified exhausts with low back-pressure\n"
                "  → Check: intake vacuum hoses, exhaust manifold for cracks, O2 sensor response on decel.\n\n"
                "Is it a single loud bang or repeated pops? (bang / pops)",
                follow_up="bang or pops",
            )
        return _resp(
            "📌 Backfire on acceleration:\n"
            "Is it coming from the exhaust pipe or the intake/air filter area? (exhaust / intake)",
            follow_up="location",
        )
    if step == 2:
        if data.get("when") == "decel" or "decel" in data.get("when", ""):
            if "bang" in a:
                return _resp(
                    "→ Single loud bang: often rich-then-lean condition, or a significant timing issue.",
                    done=True,
                )
            return _resp(
                "→ Repeated pops: vacuum leak or exhaust leak causing cyclic lean/misfire on decel.",
                done=True,
            )
        # Acceleration backfire location
        if "intake" in a:
            return _resp(
                "→ Intake backfire = flame going back through the intake.\n"
                "  Causes:\n"
                "  • Ignition timing too retarded\n"
                "  • Stuck or burnt intake valve\n"
                "  • Severely lean mixture\n"
                "  → Check ignition timing, valve operation, fuel pressure.",
                done=True,
            )
        return _resp(
            "→ Exhaust backfire on acceleration:\n"
            "  • Ignition timing too advanced\n"
            "  • Lean mixture (not enough fuel)\n"
            "  • Clogged catalytic converter trapping unburned fuel\n"
            "  • Weak ignition spark\n"
            "  → Check timing, fuel pressure, spark condition, catalytic converter restriction.",
            done=True,
        )
    return _resp("Backfire diagnosis complete.", done=True)


# ── BATTERY ───────────────────────────────────────────────────────────────────


def _battery(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Battery & Charging System ---\n"
            "Battery voltage with engine OFF? (e.g. 12.6 — type 'no' if unknown)",
            follow_up="resting voltage",
        )
    if step == 1:
        data["rest_v"] = a
        if a != "no":
            try:
                v = float(a.replace("v", ""))
                if v > 12.9:
                    data["v_note"] = (
                        f"⚠️ {v}V is too high for resting — surface charge present.\n  Turn on headlights for 2 min, then retest."
                    )
                elif v >= 12.65:
                    data["v_note"] = f"✅ {v}V — battery fully charged."
                elif v >= 12.45:
                    data["v_note"] = f"🔋 {v}V — ~75% charged. Charge and load test."
                elif v >= 12.2:
                    data["v_note"] = (
                        f"⚠️ {v}V — ~50% charged. Likely needs replacement."
                    )
                elif v >= 11.9:
                    data["v_note"] = (
                        f"⚠️ {v}V — critically discharged. Charge fully, then load test."
                    )
                else:
                    data["v_note"] = (
                        f"❌ {v}V — possibly shorted cell. Replace battery."
                    )
            except ValueError:
                data["v_note"] = (
                    "Could not parse voltage. Use a multimeter set to DC voltage."
                )
        return _resp(
            (data.get("v_note", "") + "\n\n" if data.get("v_note") else "")
            + "Voltage with engine RUNNING? (should be 13.5–14.5V — type 'no' if not tested)",
            follow_up="running voltage",
        )
    if step == 2:
        data["run_v"] = a
        msg = ""
        if a != "no":
            try:
                rv = float(a.replace("v", ""))
                if rv >= 13.5 and rv <= 14.8:
                    msg = f"✅ Charging voltage {rv}V — alternator looks good.\n"
                elif rv < 13.5:
                    msg = f"⚠️ Low charging voltage ({rv}V) — alternator may be failing. Check belt tension and connections.\n"
                elif rv > 15.0:
                    msg = f"⚠️ Overcharging ({rv}V)! Faulty voltage regulator — can damage battery and electronics.\n"
            except ValueError:
                pass
        msg += (
            "\nCommon battery issues:\n"
            "  • Corroded terminals: clean with baking soda + water and wire brush\n"
            "  • Loose connections: tighten both terminals\n"
            "  • Age: batteries last 3–5 years on average\n"
            "  • Sulfation from deep discharges\n\n"
            "Approximate battery age? (e.g. '3 years', 'unknown')"
        )
        return _resp(msg, follow_up="battery age")
    if step == 3:
        try:
            years = float(
                a.replace("years", "")
                .replace("year", "")
                .replace("yr", "")
                .strip()
                .split()[0]
            )
            if years >= 4:
                advice = f"⚠️ At {years} years the battery is aging. Load test it — replace if it fails."
            elif years >= 2:
                advice = f"Battery is mid-life ({years} years). Worth a load test if experiencing symptoms."
            else:
                advice = f"Battery is relatively new ({years} years). Age is unlikely to be the issue."
        except (ValueError, IndexError):
            advice = f"Age noted: '{answer}'. If 4+ years, a free load test at an auto parts store is worthwhile."
        return _resp(advice, done=True)
    return _resp("Battery diagnosis complete.", done=True)


# ── STARTER ───────────────────────────────────────────────────────────────────


def _starter(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Starter Motor / Cranking Issues ---\n"
            "What happens when you turn the key or press start?\n"
            "(single-click / rapid-clicks / slow-crank / grind / nothing / cranks-but-no-start)",
            follow_up="symptom",
        )
    if step == 1:
        data["symptom"] = a
        if "single" in a and "click" in a:
            msg = (
                "📌 Single click = solenoid fires but motor doesn't spin.\n"
                "  • Battery too weak to sustain cranking current\n"
                "  • Bad connection at starter (corroded terminal or loose bolt)\n"
                "  • Seized starter motor or seized engine\n"
                "  → Test battery voltage UNDER LOAD while cranking. If it drops below 10V → weak battery.\n"
                "  → Check all cables: battery+ to starter, battery– to chassis, chassis to engine block.\n\n"
                "Does jump-starting help? (y/n/not tried)"
            )
        elif "rapid" in a and "click" in a:
            msg = (
                "📌 Rapid clicking = battery too weak to hold voltage during cranking.\n"
                "  Classic dead/weak battery symptom — also check for corroded terminals.\n"
                "  → Charge or jump-start. If it won't hold charge → battery has failed.\n\n"
                "Does jump-starting help? (y/n/not tried)"
            )
        elif "slow" in a:
            msg = (
                "📌 Slow cranking:\n"
                "  • Weak battery (most common)\n"
                "  • Corroded or undersized battery cables\n"
                "  • High internal engine resistance (thick oil in cold, or hydrolocked cylinder)\n"
                "  • Failing starter drawing too much current\n"
                "  → Voltage drop test: measure across positive cable while cranking — >0.5V drop = bad cable.\n\n"
                "Does jump-starting help? (y/n/not tried)"
            )
        elif "grind" in a:
            msg = (
                "📌 Grinding:\n"
                "  • Starter drive gear not fully engaging flywheel ring gear\n"
                "  • Worn starter drive (Bendix) or worn ring gear teeth\n"
                "  • Bad starter solenoid not pulling drive gear out fully\n"
                "  → Replace starter first. If new starter still grinds → ring gear is worn.\n\n"
                "Does jump-starting help? (y/n/not tried)"
            )
        elif "nothing" in a:
            msg = (
                "📌 No sound at all — no power reaching starter circuit.\n"
                "  • Check: main fuse, starter relay, ignition switch, neutral safety switch (auto) or clutch switch (manual)\n"
                "  • Push-button start: check brake switch, key fob battery, BCM communication\n"
                "  → Swap starter relay with an identical relay from the same fuse box.\n"
                "  → Use a test light at the starter trigger wire — 12V while cranking = starter/cable fault.\n\n"
                "Does jump-starting help? (y/n/not tried)"
            )
        else:
            msg = (
                "📌 Cranks normally but won't start:\n"
                "  → This is a fuel, spark, or timing issue — not the starter.\n"
                "  → Type 'misfire' for a detailed no-start/misfire diagnosis.\n\n"
                "Does jump-starting help? (y/n/not tried)"
            )
        return _resp(msg, follow_up="jump start")
    if step == 2:
        if "y" in a:
            return _resp(
                "→ Jump-starting works: the battery is the primary suspect. Test and likely replace.",
                done=True,
            )
        if "n" in a:
            return _resp(
                "→ Jump-start doesn't help: look at the starter, cables, neutral safety switch, or immobiliser.",
                done=True,
            )
        return _resp(
            "→ Try jump-starting as a diagnostic step to rule in or out the battery.",
            done=True,
        )
    return _resp("Starter diagnosis complete.", done=True)


# ── ALTERNATOR ────────────────────────────────────────────────────────────────


def _alternator(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Alternator Charging Issues ---\n"
            "Is the battery warning light on the dash? (y/n)",
            follow_up="battery light",
        )
    if step == 1:
        data["light"] = a
        msg = ""
        if "y" in a:
            msg = "📌 Battery light on = alternator not charging sufficiently.\n  → Confirm with voltmeter: should read 13.5–14.5V at battery with engine running.\n\n"
        return _resp(
            msg
            + "Voltage at battery with engine running? (e.g. 13.8 — type 'no' if not tested)",
            follow_up="running voltage",
        )
    if step == 2:
        data["run_v"] = a
        if a != "no":
            try:
                rv = float(a.replace("v", ""))
                if rv < 13.0:
                    v_msg = f"❌ Only {rv}V — alternator not charging. Battery will drain shortly.\n  → Check: drive belt condition/tension, alternator wiring connector, fusible link to alternator."
                elif rv < 13.5:
                    v_msg = f"⚠️ Low charging voltage ({rv}V) — possibly worn brushes or weak voltage regulator."
                elif rv <= 14.8:
                    v_msg = f"✅ Charging voltage {rv}V — within normal range."
                else:
                    v_msg = f"⚠️ Overcharging: {rv}V — faulty voltage regulator. Can damage battery and electronics."
                return _resp(
                    v_msg
                    + "\n\nIs the drive belt intact and not slipping? (y/n/unknown)",
                    follow_up="belt",
                )
            except ValueError:
                pass
        return _resp(
            "Is the drive belt intact and not slipping? (y/n/unknown)", follow_up="belt"
        )
    if step == 3:
        if "n" in a:
            return _resp(
                "→ Slipping or broken belt = alternator isn't spinning. Inspect belt and tensioner.",
                done=True,
            )
        return _resp(
            "Any burning smell or squealing from the engine bay? (y/n)",
            follow_up="smell",
        )
    if step == 4:
        if "y" in a:
            return _resp(
                "→ Burning smell: alternator internal short or bearing seizure.\n"
                "→ Squealing: worn alternator bearing or slipping belt.\n"
                "→ Replace alternator — a seized bearing can snap the serpentine belt.",
                done=True,
            )
        return _resp(
            "Alternator failure sequence for reference:\n"
            "  1. Charging voltage drops → battery drains while driving\n"
            "  2. Warning light appears\n"
            "  3. Lights dim, accessories struggle\n"
            "  4. Engine stalls when battery is fully depleted\n"
            "  → If you're at stage 1–2: you may have 30–60 min. Get to a shop.",
            done=True,
        )
    return _resp("Alternator diagnosis complete.", done=True)


# ── GROUND ────────────────────────────────────────────────────────────────────


def _ground(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Ground Faults / Corrosion ---\n"
            "Bad grounds cause misleading symptoms: erratic gauges, dim lights, random sensor codes, slow cranking.\n\n"
            "What symptom are you chasing?",
            follow_up="symptom",
        )
    if step == 1:
        data["symptom"] = answer
        return _resp(
            f"For '{answer}', check these critical ground points:\n\n"
            "  1. Battery negative → chassis (main ground strap at battery tray)\n"
            "  2. Engine block → chassis (braided wire, often near firewall or bell housing)\n"
            "  3. Engine block → battery negative (sometimes a separate cable)\n"
            "  4. ECU ground (small wire near intake manifold — check for corrosion at eyelet)\n"
            "  5. Body grounds (under seat, trunk, pillars — green oxidation is the enemy)\n"
            "  6. Headlight / taillight housing grounds\n\n"
            "Voltage Drop Test:\n"
            "  • Multimeter to DC millivolts\n"
            "  • Red probe on battery negative post, black probe on engine block\n"
            "  • Crank engine: should read <200mV. More = high resistance in ground path.\n\n"
            "Are any ground cables visibly corroded or green? (y/n)",
            follow_up="corroded",
        )
    if step == 2:
        if "y" in a:
            return _resp(
                "⚠️ Corroded ground found — this is very likely your root cause.\n"
                "  Fix: disconnect each point, clean with wire brush + sandpaper,\n"
                "  apply dielectric grease, and reconnect firmly.",
                done=True,
            )
        return _resp(
            "No visible corrosion noted. Perform the voltage drop test under load to find the high-resistance point.\n"
            "A reading >200mV on any ground path needs attention.",
            done=True,
        )
    return _resp("Ground diagnosis complete.", done=True)


# ── FUSE / RELAY ──────────────────────────────────────────────────────────────


def _fuse(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Fuses & Relays ---\n" "Which component stopped working?",
            follow_up="component",
        )
    if step == 1:
        data["component"] = answer
        return _resp(
            f"📌 Diagnosing failed component: {answer}\n\n"
            "Step 1 — Find the fuse and relay:\n"
            "  • Fuse boxes: under hood (high-current) and driver kick panel (low-current)\n"
            "  • Check the fuse box lid label or owner's manual for the correct location\n\n"
            "Step 2 — Test the fuse:\n"
            "  • Visual check: look for broken wire inside the fuse\n"
            "  • Better: multimeter continuity mode across fuse terminals with circuit powered\n"
            "  • Replace with same amperage fuse only\n\n"
            "Step 3 — Test the relay:\n"
            "  • Swap the relay with an identical one from the same fuse box (same part number)\n"
            "  • If component works after swap → replace that relay\n"
            "  • Coil resistance (pins 85–86): 60–120 ohms normally\n\n"
            "Is there 12V power at the component connector when it should be working? (y/n/unknown)",
            follow_up="power at connector",
        )
    if step == 2:
        if "y" in a:
            return _resp(
                f"→ Power present but {data.get('component', 'component')} not working:\n"
                "  The component itself has failed, or there's a bad ground on that circuit.\n"
                "  → Check the ground side: should show <0.5V to chassis with multimeter.",
                done=True,
            )
        if "n" in a:
            return _resp(
                f"→ No power at {data.get('component', 'component')}:\n"
                "  Trace back from component → relay → fuse → source. Open circuit or blown fuse.\n\n"
                "Does the fuse blow again immediately when replaced? (y/n)",
                follow_up="fuse blows again",
            )
        return _resp(
            f"→ Use a test light: probe the power terminal at the {data.get('component', 'component')} connector with key in RUN.\n"
            "  No light = no power. Trace back toward the fuse box.",
            done=True,
        )
    if step == 3:
        if "y" in a:
            return _resp(
                "📌 Fuse blows immediately = short circuit downstream.\n"
                "  → Unplug the component. If fuse still blows → short is in the wiring harness.\n"
                "  → If fuse no longer blows → short is inside the component itself.\n"
                "  → Inspect wiring for chafed insulation contacting chassis metal.",
                done=True,
            )
        return _resp(
            "→ Fuse holds after replacement. Component or its ground is the issue.",
            done=True,
        )
    return _resp("Fuse/relay diagnosis complete.", done=True)


# ── SENSOR ────────────────────────────────────────────────────────────────────

SENSOR_DB = {
    "maf": {
        "name": "Mass Air Flow (MAF)",
        "codes": "P0100–P0103",
        "symptoms": "Rough idle, hesitation, stalling, poor fuel economy, black smoke",
        "test": "Live data at idle: ~2–7 g/s; ~15–25 g/s at 2500 RPM. Tap lightly — RPM change = bad. Clean with MAF cleaner spray (do NOT touch the wire).",
        "fix": "Clean sensor first; replace if cleaning fails.",
    },
    "o2": {
        "name": "Oxygen (O2) Sensor",
        "codes": "P0130–P0167, P0135 (heater)",
        "symptoms": "Poor fuel economy, failed emissions, rich/lean codes, sluggish response",
        "test": "Live data: upstream O2 switches rapidly 0.1–0.9V at warm idle. Slow switching = lazy/dead sensor.",
        "fix": "Replace sensor. Reset fuel trims after.",
    },
    "tps": {
        "name": "Throttle Position Sensor (TPS)",
        "codes": "P0120–P0123",
        "symptoms": "Surging, stalling, no throttle response, limp mode",
        "test": "Live data: ~0.5V closed, ~4.5V fully open, smooth ramp. Any flat spots or jumps = bad.",
        "fix": "Adjust if adjustable; replace if not. Clean throttle body while at it.",
    },
    "cts": {
        "name": "Coolant Temp Sensor (CTS/ECT)",
        "codes": "P0115–P0118",
        "symptoms": "Hard cold start, fan always on, no temp gauge reading, rich when warm",
        "test": "Resistance: ~2000–3000Ω cold, ~200–300Ω at normal temp. Live data should climb from cold to ~90°C and hold.",
        "fix": "Replace sensor. Drain coolant first or use a rag to minimise spill.",
    },
    "ckp": {
        "name": "Crankshaft Position Sensor (CKP)",
        "codes": "P0335–P0338",
        "symptoms": "No spark, no start, stalling while driving (especially when hot)",
        "test": "Resistance: ~900–1200Ω. Check air gap (0.5–1.5mm to reluctor wheel). Oscilloscope shows clean square wave.",
        "fix": "Replace. Common hot-failure sensor — carry a spare on long trips.",
    },
    "cmp": {
        "name": "Camshaft Position Sensor (CMP)",
        "codes": "P0340–P0343",
        "symptoms": "Extended crank, hard start, misfire, no-start",
        "test": "Similar to CKP. Check connector — often fails there due to heat cycles.",
        "fix": "Replace. Verify timing chain isn't jumped if code returns after replacement.",
    },
    "knock": {
        "name": "Knock Sensor",
        "codes": "P0325–P0330",
        "symptoms": "Reduced power mode, pinging/detonation, poor performance",
        "test": "Resistance varies by type. Must be torqued to spec (18–22 ft-lb usually) — wrong torque causes false readings.",
        "fix": "Replace sensor. Check torque spec carefully.",
    },
    "abs": {
        "name": "ABS Wheel Speed Sensor",
        "codes": "C0031–C0050 range (varies)",
        "symptoms": "ABS warning light, traction control off, speedometer issues",
        "test": "Resistance (passive): 1000–2500Ω. Spin wheel by hand — should see AC signal on passive type.",
        "fix": "Clean sensor tip of metal debris first. Check wheel bearing play. Replace sensor if signal absent.",
    },
    "map": {
        "name": "MAP Sensor",
        "codes": "P0105–P0108",
        "symptoms": "Rich/lean condition, poor idle, hesitation (engines without MAF)",
        "test": "Live data at idle: ~8–12 inHg vacuum. Snap throttle: should briefly drop near 0.",
        "fix": "Check vacuum line to sensor first. Replace if voltage output is out of range.",
    },
}


def _sensor(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Sensor Diagnosis ---\n"
            "Available: MAF · O2 · TPS · CTS · CKP · CMP · Knock · ABS · MAP\n\n"
            "Enter a sensor name or trouble code (e.g. 'MAF', 'P0335', 'O2'):",
            follow_up="sensor or code",
        )
    if step == 1:
        matched = None
        for key, info in SENSOR_DB.items():
            if key in a or info["codes"].lower().replace(" ", "") in a.replace(" ", ""):
                matched = info
                break
            for seg in info["codes"].split(","):
                if seg.strip().lower().replace("–", "") in a.replace("-", "").replace(
                    "–", ""
                ):
                    matched = info
                    break
            if matched:
                break

        if matched:
            data["sensor"] = matched["name"]
            msg = (
                f"📌 {matched['name']}\n"
                f"   Codes: {matched['codes']}\n"
                f"   Symptoms: {matched['symptoms']}\n\n"
                f"   Test procedure:\n   {matched['test']}\n\n"
                f"   Fix: {matched['fix']}\n\n"
                "Want to check the sensor wiring too? (y/n)"
            )
            return _resp(msg, follow_up="check wiring")
        return _resp(
            "Sensor not in database. General steps:\n"
            "  1. Check connector: unplug and inspect for corrosion, bent pins, moisture\n"
            "  2. Power supply: most sensors need 5V reference + ground from ECU\n"
            "  3. Ground: measure sensor ground pin to battery negative (<0.2V OK)\n"
            "  4. Signal output: check with multimeter or oscilloscope\n"
            "  5. Compare live data to manufacturer spec\n"
            "  6. If wiring OK: replace with OEM quality part",
            done=True,
        )
    if step == 2:
        if "y" in a:
            return _resp(
                "Sensor wiring check:\n"
                "  • Voltage reference (orange/gray wire): ~5V with key on\n"
                "  • Ground (black): <0.2V at sensor connector with key on\n"
                "  • Signal (green/blue): varies by sensor — check with multimeter or scope\n"
                "  • Wiggle test: flex harness while watching live data for dropouts\n"
                "  • Inspect for chafing near brackets, heat shields, and moving parts",
                done=True,
            )
        return _resp(f"{data.get('sensor', 'Sensor')} diagnosis complete.", done=True)
    return _resp("Sensor diagnosis complete.", done=True)


# ── PARASITIC DRAIN ───────────────────────────────────────────────────────────


def _drain(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Parasitic Battery Drain ---\n"
            "Battery dead overnight despite a good alternator? Something is staying awake.\n\n"
            "Have you measured the drain with a multimeter in series? (y/n)",
            follow_up="measured",
        )
    if step == 1:
        data["measured"] = a
        if "y" in a:
            return _resp("What is the drain in milliamps (mA)?", follow_up="mA reading")
        return _resp(
            "How to measure parasitic drain:\n"
            "  1. Turn all accessories off, doors closed, key removed\n"
            "  2. Wait 20–30 min for all modules to enter sleep mode\n"
            "  3. Set multimeter to DC amps (10A range first)\n"
            "  4. Connect IN SERIES: disconnect battery negative, connect meter between cable and battery\n"
            "  5. Do NOT open doors or touch anything — this wakes modules\n"
            "  6. Switch to mA range if reading is under 1A\n"
            "  Normal: <50mA. Problem: >100mA sustained after sleep period.\n\n"
            "Any aftermarket electronics installed? (stereo / alarm / dashcam / remote start — y/n)",
            follow_up="aftermarket",
        )
    if step == 2:
        if data.get("measured", "").startswith("y"):
            # Parse mA reading
            try:
                ma = float(a.replace("ma", "").strip())
                if ma <= 50:
                    verdict = "✅ Normal drain (<50mA). Battery may simply be old and failing to hold charge.\n  → Do a battery load test at an auto parts store."
                elif ma <= 100:
                    verdict = f"⚠️ Slightly elevated ({ma}mA). Wait 30–45 min after key-off before measuring — modules need time to sleep."
                elif ma <= 300:
                    verdict = f"⚠️ Significant drain ({ma}mA). Will drain most batteries overnight.\n  → Use the fuse-pull method below."
                else:
                    verdict = f"❌ Severe drain ({ma}mA). Will drain battery within hours.\n  → Likely a stuck relay (fan, fuel pump) or shorted aftermarket accessory."
                data["verdict"] = verdict
            except ValueError:
                data["verdict"] = (
                    "Compare your reading to the 50mA threshold for normal drain."
                )
            return _resp(
                data["verdict"] + "\n\n"
                "🔍 Fuse-pull isolation method:\n"
                "  • With multimeter in series measuring drain:\n"
                "  • Pull fuses ONE AT A TIME from the fuse box\n"
                "  • When drain drops significantly → that circuit has the drain\n"
                "  • Re-insert fuse, then unplug components on that circuit one by one\n\n"
                "Any aftermarket electronics? (y/n)",
                follow_up="aftermarket",
            )
        # Came from 'no measured' branch
        if "y" in a:
            return _resp(
                "⚠️ Aftermarket installs are a very common drain source.\n"
                "  → Disconnect the aftermarket device completely and recheck drain.\n"
                "  → If drain drops: the device needs a switched 12V source, not always-hot.",
                done=True,
            )
        return _resp(
            "Common drain causes to investigate:\n"
            "  • Glove box / trunk light staying on\n"
            "  • Aftermarket stereo/alarm miswired to always-hot\n"
            "  • Faulty alternator diode (back-feeds battery)\n"
            "  • Stuck relay: fuel pump, cooling fan, interior light\n"
            "  • Module not sleeping: BCM, ECU, radio, telematics",
            done=True,
        )
    if step == 3:
        if "y" in a:
            return _resp(
                "⚠️ Aftermarket installs are a common drain culprit.\n"
                "  → Disconnect the device and recheck drain reading.\n"
                "  → If it drops: rewire to a switched 12V source (not always-hot).",
                done=True,
            )
        return _resp(
            "Common drain causes:\n"
            "  • Glove box / trunk light staying on\n"
            "  • Aftermarket device miswired to always-hot\n"
            "  • Faulty alternator diode\n"
            "  • Stuck relay (fuel pump, fan, interior light)\n"
            "  • Module not entering sleep (BCM, ECU, radio)",
            done=True,
        )
    return _resp("Parasitic drain diagnosis complete.", done=True)


# ── SHORT / OPEN ──────────────────────────────────────────────────────────────


def _short(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- Wiring Shorts & Open Circuits ---\n"
            "What symptom are you seeing? (blown fuse / dead component / intermittent)",
            follow_up="symptom",
        )
    if step == 1:
        data["symptom"] = a
        if "fuse" in a or "blown" in a:
            return _resp(
                "📌 Repeatedly blown fuse = short circuit.\n\n"
                "Diagnosis steps:\n"
                "  1. Unplug the component on that circuit\n"
                "     → Fuse still blows: short is in the WIRING HARNESS\n"
                "     → Fuse no longer blows: short is INSIDE THE COMPONENT\n"
                "  2. For harness short: wiggle harness while watching for intermittent contact\n"
                "  3. Ohmmeter: disconnect both ends of suspect wire. Measure resistance to chassis.\n"
                "     0 ohms to chassis = dead short. Trace wire for chafing.\n\n"
                "Common short locations:\n"
                "  • Door jam hinge (window/lock wiring)\n"
                "  • Chafed against sharp metal edges\n"
                "  • Melted insulation near exhaust\n"
                "  • Rodent-chewed wires\n\n"
                "Need wire splice repair guidance? (y/n)",
                follow_up="splice help",
            )
        if "dead" in a or "no power" in a:
            return _resp(
                "📌 Dead component = open circuit.\n\n"
                "Diagnosis steps:\n"
                "  1. Check fuse (test with multimeter even if it looks OK)\n"
                "  2. Check relay — swap with known-good identical relay\n"
                "  3. Test for power at component connector\n"
                "     → Power present but component dead: component failed or bad ground\n"
                "     → No power: trace back toward fuse box, test at each connector\n"
                "  4. Continuity test on suspect wire (disconnect both ends)\n"
                "     → No continuity = broken wire\n\n"
                "Need wire splice repair guidance? (y/n)",
                follow_up="splice help",
            )
        return _resp(
            "📌 Intermittent fault = high-resistance connection or wire break under flex.\n\n"
            "Diagnosis steps:\n"
            "  1. Wiggle test: flex wiring harness section by section while circuit is active\n"
            "     → Symptom changes = you've found the area\n"
            "  2. Check all connectors: unplug and inspect for corrosion, bent pins, moisture\n"
            "  3. Thermal test: does it fail when hot vs cold?\n"
            "  4. Voltage drop test: >0.5V drop along a wire under load = resistance problem\n\n"
            "Need wire splice repair guidance? (y/n)",
            follow_up="splice help",
        )
    if step == 2:
        if "y" in a:
            return _resp(
                "Proper wire splice method:\n"
                "  1. Cut out damaged section. Strip 1/2 inch from each end.\n"
                "  2. Match wire gauge (same or slightly heavier).\n"
                "  3. Join with solder + heat-shrink tubing (preferred), OR adhesive-lined butt connector.\n"
                "  4. Avoid twist-and-tape — corrodes and fails under vibration.\n"
                "  5. Route away from heat and metal edges; secure with zip ties.",
                done=True,
            )
        return _resp(
            "Wiring diagnosis complete. Use a wiring diagram (AllDataDIY or Mitchell 1) for circuit tracing.",
            done=True,
        )
    return _resp("Wiring diagnosis complete.", done=True)


# ── CAN BUS ───────────────────────────────────────────────────────────────────


def _canbus(step: int, answer: str, data: dict) -> dict:
    a = answer.lower()
    if step == 0:
        return _resp(
            "--- CAN Bus / Communication Errors ---\n"
            "CAN bus connects all modules (ECU, BCM, ABS, Airbag, etc.).\n\n"
            "Any U-codes? (e.g. U0100, U0155 — or 'no')",
            follow_up="U-codes",
        )
    if step == 1:
        data["codes"] = a
        code_info = ""
        if a != "no" and a:
            code_info = (
                f"📌 U-code(s): {answer}\n"
                "  U0100: Lost comms with ECM/PCM\n"
                "  U0101: Lost comms with TCM\n"
                "  U0121: Lost comms with ABS module\n"
                "  U0140: Lost comms with BCM\n"
                "  U0155: Lost comms with instrument cluster\n"
                "  Multiple U-codes at once = CAN bus failure, not multiple failed modules.\n\n"
            )
        return _resp(
            code_info + "📋 CAN bus physical checks:\n\n"
            "1. Termination resistance test (most important):\n"
            "   • Key OFF, disconnect battery\n"
            "   • Measure resistance between OBD2 port pin 6 (CAN High) and pin 14 (CAN Low)\n"
            "   • ✅ ~60 ohms = healthy (two 120Ω resistors in parallel)\n"
            "   • >120 ohms = one terminator missing or open CAN wire\n"
            "   • <60 ohms = short between CAN H and L, or faulty module loading bus\n\n"
            "2. CAN H / CAN L voltage (key ON, engine OFF):\n"
            "   • CAN High: ~2.5–3.5V\n"
            "   • CAN Low: ~1.5–2.5V\n"
            "   • Both at same voltage or 0V = bus is down\n\n"
            "Any recent aftermarket electrical work? (alarm / remote start / stereo — y/n)",
            follow_up="aftermarket",
        )
    if step == 2:
        if "y" in a:
            return _resp(
                "⚠️ Aftermarket installs commonly damage CAN bus wiring or add incorrect loads.\n"
                "  → Disconnect the device completely and recheck termination resistance.\n\n"
                "Do you have an oscilloscope or access to live CAN data? (y/n)",
                follow_up="oscilloscope",
            )
        return _resp(
            "Do you have an oscilloscope or access to live CAN data? (y/n)",
            follow_up="oscilloscope",
        )
    if step == 3:
        if "y" in a:
            return _resp(
                "With oscilloscope on CAN H and CAN L:\n"
                "  ✅ Healthy: complementary square waves — CAN H swings to ~3.5V, CAN L to ~1.5V\n"
                "  ⚠️ Dominant stuck (one line flat): bus error flooding from a faulty module\n"
                "  ❌ Silence (no traffic): bus is completely offline\n\n"
                "Module isolation method if resistance is wrong:\n"
                "  Disconnect modules one at a time until resistance returns to ~60Ω.\n"
                "  The module that restores bus when unplugged is the faulty one.",
                done=True,
            )
        return _resp(
            "Without a scope: focus on the 60-ohm resistance test and module unplugging method.\n"
            "A bi-directional scan tool is very helpful for isolating which module has failed.",
            done=True,
        )
    return _resp("CAN bus diagnosis complete.", done=True)
