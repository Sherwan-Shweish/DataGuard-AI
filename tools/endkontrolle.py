"""Endkontrolle: desktop/ gegen VarianceAI, Referenzagenten gegen die gelieferten ZIP-Dateien, ruff, Secrets.

Schreibt docs/endkontrolle.json (Grundlage für docs/Endabnahme.md).
Aufruf: ``uv run python tools/endkontrolle.py <VarianceAI-Projektordner> <Ordner mit den ZIP-Dateien>
         <Ordner mit den entpackten Referenzprojekten>``
"""

from __future__ import annotations

import filecmp
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[1]
IGNORIEREN = {"__pycache__", ".venv", ".pytest_cache", ".ruff_cache", ".DS_Store"}
ERLAUBT_DESKTOP = {"app.toml", "ressourcen/icon.png", "ressourcen/AppIcon.icns", "ressourcen/icon.svg"}
REFERENZEN = ("VarianceAI-v1.2", "FlowAudit-AI-v1.2.1", "ControllAI-v2.2.1")
SECRET_MUSTER = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")


def unterschiede(a: Path, b: Path, praefix: str = "") -> list[str]:
    """Relative Pfade, die nur in einem Ordner liegen oder inhaltlich verschieden sind (rekursiv)."""
    v = filecmp.dircmp(a, b, ignore=list(IGNORIEREN))
    aus = [f"{praefix}{n}" for n in v.left_only + v.right_only + v.diff_files + v.funny_files]
    for n in v.common_dirs:
        aus += unterschiede(a / n, b / n, f"{praefix}{n}/")
    return sorted(aus)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    variance, zip_ordner, ref_ordner = (Path(x) for x in argv)
    desktop = unterschiede(PROJEKT / "desktop", variance / "desktop")
    referenzen = {}
    for name in REFERENZEN:
        archiv = next(zip_ordner.glob(f"*{name}.zip"), None)
        ziel = next((p for p in (ref_ordner / name).iterdir() if p.is_dir()), None) if (ref_ordner / name).exists() \
            else None
        if archiv is None or ziel is None:
            referenzen[name] = -1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(archiv) as z:
                z.extractall(tmp)
            quelle = next(p for p in Path(tmp).iterdir() if p.is_dir())
            referenzen[name] = len([u for u in unterschiede(quelle, ziel) if not u.endswith(".db")])
    ruff = subprocess.run([sys.executable, "-m", "ruff", "check", "."], cwd=PROJEKT, capture_output=True, text=True)
    funde = []
    for datei in PROJEKT.rglob("*"):
        if datei.is_file() and not (set(datei.relative_to(PROJEKT).parts) & IGNORIEREN) and datei.suffix in (
                ".py", ".md", ".toml", ".json", ".txt", ".env", ".example", ".cfg", ".yml", ".yaml"):
            if SECRET_MUSTER.search(datei.read_text(encoding="utf-8", errors="ignore")):
                funde.append(str(datei.relative_to(PROJEKT)))
    bericht = {
        "desktop_unterschiede": desktop,
        "desktop_ok": set(desktop) <= ERLAUBT_DESKTOP,
        "referenzen": referenzen,
        "ruff": (ruff.stdout.strip().splitlines() or ["?"])[-1],
        "secrets": "keine gefunden" if not funde and not (PROJEKT / ".env").exists() else f"PRÜFEN: {funde}",
    }
    (PROJEKT / "docs" / "endkontrolle.json").write_text(json.dumps(bericht, ensure_ascii=False, indent=2) + "\n",
                                                        encoding="utf-8")
    print(json.dumps(bericht, ensure_ascii=False, indent=2))
    return 0 if bericht["desktop_ok"] and not any(referenzen.values()) and not funde else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
