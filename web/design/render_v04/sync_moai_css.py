"""Copy web/src/views/brand/moai.css verbatim into this render source (index.html).

The block sits between the 'Change it there and here together. */' marker and </style>.
Run after every moai.css change, then re-run wall_judge so app and source stay pixel-equal:
    python3 web/design/render_v04/sync_moai_css.py [path/to/moai.css]
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
css_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1] / "src" / "views" / "brand" / "moai.css"
page = HERE / "index.html"
css = css_path.read_text()
s = page.read_text()
marker = "Change it there and here together. */\n"
i = s.index(marker) + len(marker)
j = s.index("</style>", i)
page.write_text(s[:i] + css + s[j:])
print("synced", len(css), "chars from", css_path)
