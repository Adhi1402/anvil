"""Offline stand-ins so the whole app can be exercised without Google credentials.
FakeFirestore mimics the few Firestore calls Anvil uses; FakeGemini is a rule-based judge (NOT the real model),
so these tests prove the plumbing and enforcement logic, not Gemini's accuracy."""
import json
import uuid


class _Doc:
    def __init__(self, id_, data):
        self.id, self._d = id_, data
        self.exists = data is not None

    def to_dict(self):
        return json.loads(json.dumps(self._d)) if self._d is not None else None


class _Ref:
    def __init__(self, col, id_):
        self.col, self.id = col, id_

    def get(self, transaction=None):
        return _Doc(self.id, self.col.docs.get(self.id))

    def set(self, data):
        self.col.docs[self.id] = json.loads(json.dumps(data))


class _Query:
    def __init__(self, col, filters=(), order=None, desc=False, lim=None):
        self.col, self.filters, self.order, self.desc, self.lim = col, filters, order, desc, lim

    def where(self, filter):
        return _Query(self.col, self.filters + (filter,), self.order, self.desc, self.lim)

    def order_by(self, field, direction=None):
        return _Query(self.col, self.filters, field, direction == "DESCENDING", self.lim)

    def limit(self, n):
        return _Query(self.col, self.filters, self.order, self.desc, n)

    def stream(self):
        items = list(self.col.docs.items())
        for f in self.filters:
            def get(d):
                for part in f.field_path.split("."):
                    d = d.get(part) if isinstance(d, dict) else None
                return d
            items = [(i, d) for i, d in items if get(d) == f.value]
        if self.order:
            items.sort(key=lambda kv: kv[1].get(self.order, ""), reverse=self.desc)
        if self.lim:
            items = items[: self.lim]
        return [_Doc(i, d) for i, d in items]


class _Col(_Query):
    def __init__(self):
        self.docs = {}
        super().__init__(self)

    def document(self, id_=None):
        return _Ref(self, id_ or uuid.uuid4().hex[:20])

    def add(self, data):
        id_ = uuid.uuid4().hex[:20]
        self.docs[id_] = json.loads(json.dumps(data))
        return None, _Ref(self, id_)


class _Txn:
    def set(self, ref, data):
        ref.set(data)


class FakeFirestore:
    def __init__(self):
        self.cols = {}
        self._lock = __import__("threading").RLock()

    def atomic(self, fn):
        """Stand-in for a Firestore transaction: serialises read-modify-write like the real thing does."""
        with self._lock:
            return fn(_Txn())

    def collection(self, name):
        return self.cols.setdefault(name, _Col())


class _Usage:
    prompt_token_count, candidates_token_count, thoughts_token_count = 900, 60, 140


class _Resp:
    usage_metadata = _Usage()

    def __init__(self, text):
        self.text = text


class FakeGemini:
    """Rule-based judge + offer picker with the same call shape as the google-genai client."""
    calls = 0

    def __init__(self):
        self.models = self

    def generate_content(self, model, contents, config):
        FakeGemini.calls += 1
        if "EMPLOYEE REQUEST" in contents:                      # planner agent
            req = contents.split('EMPLOYEE REQUEST: "')[1].split('"')[0].lower()
            sections = {}
            for block in contents.split("OFFERS (index: offer)\n")[1].split("["):
                if not block.strip():
                    continue
                kind, rest = block.split("]", 1)
                sections[kind.lower()] = [json.loads(l.split(": ", 1)[1]) for l in rest.strip().splitlines()]
            legs = []
            for kind, offers in sections.items():
                def ok(o):
                    return o.get("refundable", True) and o.get("class", "economy") == "economy" and o["vendor"] in ("Air India", "Taj", "Uber")
                want = next((i for i, o in enumerate(offers) if "business" in req and o.get("class") == "business"), None)
                if want is None:
                    want = next(i for i, o in enumerate(offers) if ok(o))
                legs.append({"kind": kind, "choice": want, "rationale": "fake planner"})
            return _Resp(json.dumps({"legs": legs}))
        if "OFFERS (0-indexed)" in contents:
            offers = [json.loads(l.split(": ", 1)[1]) for l in contents.split("OFFERS (0-indexed):\n")[1].strip().splitlines()]
            for i, o in enumerate(offers):
                if o.get("class", "economy") == "economy" and o.get("refundable", True) \
                        and o["vendor"] in ("Air India", "IndiGo", "Taj", "Marriott", "Uber", "Ola Prime"):
                    return _Resp(json.dumps({"choice": i, "rationale": "cheapest compliant offer"}))
            return _Resp(json.dumps({"choice": -1, "rationale": "nothing compliant"}))
        mandate = json.loads(contents.split("MANDATE:\n")[1].split("\n\nACTION:")[0])
        action = json.loads(contents.split("ACTION:\n")[1])
        if action["type"].startswith("buy_"):                    # software domain: rule-based stand-in for the semantic judge
            hard = (action["vendor"] not in mandate["approved_vendors"] or action["category"] not in mandate["allowed_categories"]
                    or len(action.get("charges", []) or []) > 1 or bool(action.get("extra_charges")))
            soft = action["price"] > mandate["max_annual_cost_usd"] or action["seats"] > mandate["max_seats"] or (action.get("auto_renew") and not mandate["auto_renew_allowed"])
            v = "DRIFT" if hard else "REVIEW" if soft else "MATCH"
            return _Resp(json.dumps({"verdict": v, "severity": {"DRIFT": "high", "REVIEW": "low", "MATCH": "none"}[v], "violations": [], "explanation": f"fake software judge: {v}"}))
        from anvil.impact import findings, total_usd, CAP_FIELD
        hard = any(k in " ".join(findings(mandate, action)) for k in ("not approved", "destination", "split", "add-ons"))
        hard = hard or (action.get("class") not in (None, mandate["flight_class"]))
        cap = mandate.get(CAP_FIELD[action["type"]])
        soft = total_usd(action) > cap or action.get("refundable") is False
        v = "DRIFT" if hard else "REVIEW" if soft else "MATCH"
        return _Resp(json.dumps({"verdict": v, "severity": {"DRIFT": "high", "REVIEW": "low", "MATCH": "none"}[v],
                                 "violations": findings(mandate, action), "explanation": f"fake judge: {v}"}))


def install():
    """Patch the app to use the fakes. Returns (fake_db, flask_app)."""
    import anvil.gemini as gemini
    import data.store as store
    fake = FakeFirestore()
    store._db = fake
    gemini._client = FakeGemini()
    import main
    return fake, main.app
