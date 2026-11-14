"""Run every Streamlit page against a fake `streamlit` so import errors, typos and broken service calls are caught
without a browser.   python tests/smoke_pages.py [--click]    (--click presses every button / form submit)"""
import contextlib
import runpy
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CLICK = "--click" in sys.argv


class Fake:
    """Context manager that tolerates any attribute / call (used for columns, tabs, expanders, containers...)."""
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, name): return make_widget(name)
    def __iter__(self): return iter([Fake(), Fake(), Fake()])


def make_widget(name):
    def widget(*args, **kw):
        label = args[0] if args else ""
        if name in ("columns",):
            spec = args[0]
            return [Fake() for _ in range(spec if isinstance(spec, int) else len(spec))]
        if name == "tabs":
            return [Fake() for _ in args[0]]
        if name in ("selectbox", "radio"):
            opts = list(args[1]) if len(args) > 1 else list(kw.get("options", []))
            idx = kw.get("index", 0) or 0
            return opts[min(idx, len(opts) - 1)] if opts else None
        if name == "multiselect":
            return kw.get("default", [])
        if name == "slider":
            return kw.get("value", args[3] if len(args) > 3 else (args[1] if len(args) > 1 else 0))
        if name == "number_input":
            return kw.get("value", args[3] if len(args) > 3 else (args[1] if len(args) > 1 else 0))
        if name in ("text_input", "text_area"):
            return kw.get("value") or ("best way from Egmore to Tambaram at 9 am" if CLICK else "")
        if name in ("button", "form_submit_button"):
            return CLICK
        if name in ("checkbox", "toggle"):
            return kw.get("value", False)
        if name in ("expander", "container", "form", "spinner", "sidebar", "status", "empty"):
            return Fake()
        if name == "stop":
            raise SystemExit("st.stop()")
        if name in ("cache_resource", "cache_data"):
            if args and callable(args[0]):
                return args[0]
            return lambda fn: fn
        return None
    return widget


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.sidebar = Fake()
    def __getattr__(self, name): return make_widget(name)


sys.modules["streamlit"] = FakeStreamlit()
for mod in ("folium", "streamlit_folium", "map_engine"):          # need shapely / folium / internet; not needed for the smoke test
    sys.modules[mod] = MagicMock()

failures = []
pages = [ROOT / "frontend" / "app.py"] + sorted((ROOT / "frontend" / "pages").glob("*.py"))
for page in pages:
    if page.name.startswith("1_") and not CLICK:
        pass
    sys.modules["streamlit"].session_state.clear()
    try:
        with contextlib.redirect_stdout(open("/dev/null", "w")) if sys.platform != "win32" else contextlib.nullcontext():
            runpy.run_path(str(page), run_name="__main__")
        print(f"PASS {page.name}")
    except SystemExit as e:
        print(f"STOP {page.name}: {e}")
    except Exception as e:
        failures.append(page.name)
        import traceback; traceback.print_exc()
        print(f"FAIL {page.name}: {type(e).__name__}: {e}")
print("\nall pages ran" if not failures else f"\nFAILED: {failures}")
sys.exit(1 if failures else 0)
