"""Build the publishable pages: template + data JSON -> page. Usage: python3 build.py"""
import json, pathlib
here = pathlib.Path(__file__).parent
for name in ("report", "brief"):
    data = json.loads((here / f"{name}_data.json").read_text())
    tpl = (here / f"{name}_template.html").read_text()
    assert tpl.count("__DATA__") == 1
    (here / f"{name}.html").write_text(tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    print("built", name)
