import networkx as nx
from pyvis.network import Network
import os
import re


# ── Colour palette ────────────────────────────────────────────────── #
_COLOR_LEAF     = "#ff6b6b"   # warm red   – foundational / no prerequisites
_COLOR_CORE     = "#4a90d9"   # steel blue – advanced / has prerequisites
_COLOR_EDGE     = "#94a3b8"   # slate grey – prerequisite arrows
_COLOR_BG       = "#f8fafc"   # near-white – canvas background
_COLOR_HEADER   = "#1e293b"   # dark navy  – header bar


# ── Professional vis-network options ─────────────────────────────── #
# Hierarchical UD layout: leaves at top (level 0), terminals at bottom.
# hierarchicalRepulsion solver respects springLength & avoidOverlap.
_VIS_OPTIONS = """{
  "layout": {
    "hierarchical": {
      "enabled": true,
      "direction": "UD",
      "sortMethod": "directed",
      "nodeSpacing": 250,
      "levelSeparation": 180,
      "treeSpacing": 300,
      "blockShifting": true,
      "edgeMinimization": true,
      "parentCentralization": true
    }
  },
  "physics": {
    "enabled": true,
    "solver": "hierarchicalRepulsion",
    "hierarchicalRepulsion": {
      "centralGravity": 0.1,
      "springLength": 300,
      "springConstant": 0.01,
      "nodeDistance": 250,
      "damping": 0.09,
      "avoidOverlap": 1
    },
    "stabilization": {
      "enabled": true,
      "iterations": 1000,
      "updateInterval": 50,
      "fit": true
    }
  },
  "nodes": {
    "shape": "dot",
    "borderWidth": 2,
    "borderWidthSelected": 3,
    "shadow": {
      "enabled": true,
      "color": "rgba(0,0,0,0.15)",
      "size": 8,
      "x": 2,
      "y": 2
    },
    "font": {
      "size": 15,
      "face": "Inter, Roboto, sans-serif",
      "color": "#1e293b",
      "bold": { "mod": "bold" }
    }
  },
  "edges": {
    "color": {
      "color": \"""" + _COLOR_EDGE + """\",
      "highlight": "#3b82f6",
      "hover": "#3b82f6",
      "inherit": false
    },
    "width": 1.5,
    "smooth": {
      "type": "cubicBezier",
      "forceDirection": "vertical",
      "roundness": 0.4
    },
    "arrows": {
      "to": { "enabled": true, "scaleFactor": 0.7, "type": "arrow" }
    },
    "hoverWidth": 2.5,
    "selectionWidth": 2.5
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 150,
    "navigationButtons": true,
    "keyboard": { "enabled": true }
  }
}"""


# ── CSS + HTML injected after Pyvis generates the file ───────────── #
_INJECTED_CSS = """
  /* ── Google Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', Roboto, sans-serif;
    background: """ + _COLOR_BG + """;
    color: #1e293b;
  }

  /* ── Top header bar ── */
  #pg-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: """ + _COLOR_HEADER + """;
    color: #f1f5f9;
    padding: 14px 24px;
    gap: 16px;
  }
  #pg-header .pg-title {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    white-space: nowrap;
  }
  /* ── Legend panel ── */
  #pg-legend {
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 10px 14px;
    min-width: 230px;
    font-size: 0.75rem;
    color: #e2e8f0;
  }
  #pg-legend .pg-legend-title {
    font-weight: 600;
    font-size: 0.78rem;
    color: #f8fafc;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 2px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    padding-bottom: 4px;
  }
  .pg-legend-row {
    display: flex;
    align-items: center;
    gap: 8px;
    line-height: 1.4;
  }
  .pg-legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
    border: 2px solid rgba(255,255,255,0.3);
  }

  /* ── Graph canvas wrapper ── */
  #mynetwork {
    width: 100%;
    height: calc(100vh - 70px) !important;
    background: """ + _COLOR_BG + """;
    border: none !important;
  }
"""

def _make_header_html(title: str) -> str:
    return f"""<div id="pg-header">
  <span class="pg-title">{title}</span>
  <div id="pg-legend">
    <div class="pg-legend-title">Legend</div>
    <div class="pg-legend-row">
      <div class="pg-legend-dot" style="background:{_COLOR_LEAF};"></div>
      <span><strong>Red</strong> &mdash; Foundational &nbsp;(Start Here)</span>
    </div>
    <div class="pg-legend-row">
      <div class="pg-legend-dot" style="background:{_COLOR_CORE};"></div>
      <span><strong>Blue</strong> &mdash; Advanced &nbsp;(Dependent)</span>
    </div>
    <div class="pg-legend-row">
      <div class="pg-legend-dot" style="background:#94a3b8; width:8px; height:8px;"></div>
      <span>Node Size &nbsp;&rarr;&nbsp; Pedagogical Importance</span>
    </div>
    <div class="pg-legend-row" style="margin-top:4px; color:#94a3b8;">
      <span>&#8679; Prerequisites flow top &rarr; bottom</span>
    </div>
  </div>
</div>
"""


class KnowledgeMapper:
    def __init__(self, output_dir="output/visualizations"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_graph(self, json_data: dict, video_id: str) -> str:
        concepts = json_data.get("concepts", [])
        summary  = json_data.get("video_summary", "")
        title    = video_id.replace("_", " ").title()

        # ── 1. Build NetworkX graph ───────────────────────────────── #
        G = nx.DiGraph()

        # Build a name→id lookup so string prerequisites (e.g. "Process")
        # produced by the LLM are resolved to the correct integer node ID,
        # preventing phantom duplicate nodes from being auto-created.
        name_to_id = {c["standard_term"].lower(): c["id"] for c in concepts}

        def _resolve_prereq(prereq, concept_id):
            """Return the integer node ID for a prerequisite, or None to skip."""
            if isinstance(prereq, int):
                return prereq if prereq in name_to_id.values() else None
            # String name — look up case-insensitively
            return name_to_id.get(str(prereq).lower())

        for concept in concepts:
            is_leaf   = len(concept.get("prerequisites", [])) == 0
            importance = concept.get("relative_importance", 5)

            G.add_node(
                concept["id"],
                label=concept["standard_term"],
                title=(
                    f"<b>{concept['standard_term']}</b><br>"
                    f"<i>Importance: {importance}/10</i><br><br>"
                    f"{concept.get('description', '')}"
                ),
                color=_COLOR_LEAF if is_leaf else _COLOR_CORE,
                size=14 + (importance * 3),   # range ≈ 17–44 px
            )

        for concept in concepts:
            importance = concept.get("relative_importance", 5)
            for raw_prereq in concept.get("prerequisites", []):
                prereq_id = _resolve_prereq(raw_prereq, concept["id"])
                if prereq_id is None or prereq_id == concept["id"]:
                    continue  # skip unresolvable or self-referential prereqs
                G.add_edge(
                    prereq_id,
                    concept["id"],
                    width=max(1.0, importance / 2.5),
                )

        # ── 2. Build Pyvis network ────────────────────────────────── #
        net = Network(height="100vh", width="100%", directed=True, notebook=False)
        net.from_nx(G)
        net.set_options(_VIS_OPTIONS)

        # ── 3. Save raw Pyvis HTML ────────────────────────────────── #
        output_path = os.path.join(self.output_dir, f"{video_id}_enhanced_flow.html")
        net.save_graph(output_path)

        # ── 4. Post-process: inject CSS + header + legend ─────────── #
        self._inject_ui(output_path, title)

        return output_path

    # ---------------------------------------------------------------- #

    @staticmethod
    def _inject_ui(html_path: str, title: str) -> None:
        """Read the Pyvis-generated HTML and inject professional styling."""
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # a) Inject CSS into <head>
        css_block = f"<style>\n{_INJECTED_CSS}\n  </style>\n</head>"
        html = html.replace("</head>", css_block, 1)

        # b) Update <title> tag
        html = re.sub(r"<title>.*?</title>", f"<title>{title} — Pedagogical Flow</title>", html)

        # c) Inject header div right after <body>
        header_html = _make_header_html(title)
        html = re.sub(r"(<body[^>]*>)", r"\1\n" + header_html, html, count=1)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)