"""Export the ResearchPilot LangGraph as an image (and Mermaid source).

Usage:
    uv run python scripts/export_graph.py

Writes:
    docs/graph.mmd  — Mermaid source (always, no network needed)
    docs/graph.png  — PNG rendering (best effort; may require network)
"""

from __future__ import annotations

from pathlib import Path

from backend.app.graph.graph import get_graph

OUT_DIR = Path(__file__).resolve().parents[1] / "docs"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = get_graph().get_graph()

    # 1) Mermaid source — always works, no dependencies or network.
    mmd_path = OUT_DIR / "graph.mmd"
    mmd_path.write_text(graph.draw_mermaid(), encoding="utf-8")
    print(f"Wrote {mmd_path}")

    # 2) PNG — uses the Mermaid.INK API by default (needs internet).
    png_path = OUT_DIR / "graph.png"
    try:
        png_bytes = graph.draw_mermaid_png()
        png_path.write_bytes(png_bytes)
        print(f"Wrote {png_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not render PNG ({exc}).")
        print("The Mermaid source was still written; paste graph.mmd into")
        print("https://mermaid.live to export a PNG/SVG manually.")


if __name__ == "__main__":
    main()
