#!/usr/bin/env python3
"""Erzeuge 3 Varianten von Abb 5.1 mit unterschiedlichen Render-Strategien."""
import re
from pathlib import Path

SRC = Path("/home/nkccorp/Documents/repos/agents/assets/diagrams/abb-5-1-de.svg")
OUT_DIR = Path("/tmp/svg-test")
OUT_DIR.mkdir(parents=True, exist_ok=True)

src = SRC.read_text(encoding="utf-8")

def with_bg_rect(svg, bg_color):
    """Fügt background-rect direkt nach dem öffnenden <svg ...> tag ein."""
    # Suche schließendes ">" der svg-Eröffnung
    m = re.search(r"<svg[^>]*>", svg)
    if not m:
        return svg
    end = m.end()
    return svg[:end] + f'\n<rect width="100%" height="100%" fill="{bg_color}"/>' + svg[end:]

# -------- Variante A: Dark Theme, hardcoded Farben (wie altes SVG) --------
a = src
# Ersetze CSS-vars durch konkrete Hex
mapping_dark = {
    r"var\(--_arrow\)": "#3b82f6",
    r"var\(--_text\)": "#cbd5e1",
    r"var\(--_text-sec\)": "#94a3b8",
    r"var\(--_text-muted\)": "#64748b",
    r"var\(--_text-faint\)": "#475569",
    r"var\(--_line\)": "#4a6380",
    r"var\(--_node-fill\)": "#243347",
    r"var\(--_node-stroke\)": "#3b5068",
    r"var\(--_group-fill\)": "#1e293b",
    r"var\(--_group-hdr\)": "#212c3f",
    r"var\(--_inner-stroke\)": "#2c374a",
    r"var\(--_key-badge\)": "#293346",
    r"var\(--bg\)": "#1e293b",
    r"var\(--fg\)": "#cbd5e1",
}
for pat, rep in mapping_dark.items():
    a = re.sub(pat, rep, a)
a = with_bg_rect(a, "#1e293b")
(OUT_DIR / "variant-A-dark.svg").write_text(a, encoding="utf-8")

# -------- Variante B: Light Theme (für GitHub Lightmode) --------
b = src
mapping_light = {
    r"var\(--_arrow\)": "#2563eb",
    r"var\(--_text\)": "#0f172a",
    r"var\(--_text-sec\)": "#475569",
    r"var\(--_text-muted\)": "#64748b",
    r"var\(--_text-faint\)": "#94a3b8",
    r"var\(--_line\)": "#94a3b8",
    r"var\(--_node-fill\)": "#f8fafc",
    r"var\(--_node-stroke\)": "#cbd5e1",
    r"var\(--_group-fill\)": "#ffffff",
    r"var\(--_group-hdr\)": "#f1f5f9",
    r"var\(--_inner-stroke\)": "#e2e8f0",
    r"var\(--_key-badge\)": "#e2e8f0",
    r"var\(--bg\)": "#ffffff",
    r"var\(--fg\)": "#0f172a",
}
for pat, rep in mapping_light.items():
    b = re.sub(pat, rep, b)
b = with_bg_rect(b, "#ffffff")
(OUT_DIR / "variant-B-light.svg").write_text(b, encoding="utf-8")

# -------- Variante C: GitHub-adaptiv (transparent BG, dunkle Striche/Text) --------
c = src
mapping_github = {
    r"var\(--_arrow\)": "#0969da",
    r"var\(--_text\)": "#1f2328",
    r"var\(--_text-sec\)": "#656d76",
    r"var\(--_text-muted\)": "#8c959f",
    r"var\(--_text-faint\)": "#afb8c1",
    r"var\(--_line\)": "#656d76",
    r"var\(--_node-fill\)": "#f6f8fa",
    r"var\(--_node-stroke\)": "#d0d7de",
    r"var\(--_group-fill\)": "#ffffff",
    r"var\(--_group-hdr\)": "#f6f8fa",
    r"var\(--_inner-stroke\)": "#d0d7de",
    r"var\(--_key-badge\)": "#eaeef2",
    r"var\(--bg\)": "#ffffff",
    r"var\(--fg\)": "#1f2328",
}
for pat, rep in mapping_github.items():
    c = re.sub(pat, rep, c)
c = with_bg_rect(c, "#ffffff")
(OUT_DIR / "variant-C-github.svg").write_text(c, encoding="utf-8")

print(f"3 Varianten erstellt unter {OUT_DIR}")
