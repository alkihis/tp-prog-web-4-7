import matplotlib.figure
from io import BytesIO
from flask import url_for

def getimage(parts: dict):
  parts_names = list(parts.keys())
  parts_values = list(parts.values())

  fig = matplotlib.figure.Figure()
  ax = fig.subplots(1, 1)

  fig.suptitle("Répartition")
  ax.barh(parts_names, parts_values)

  b = BytesIO()
  fig.savefig(b, format="png")

  return b.getvalue()

def getsvg(transcripts: list):
  # transcripts is {'start': int, 'end': int, 'id': str}[]

  begin = 1e1000
  end = 0

  # Recherche de la fenêtre
  for tr in transcripts:
    if begin > tr['start']:
      begin = tr['start']

    if end < tr['end']:
      end = tr['end']

  # Normalisation
  for tr in transcripts:
    tr['start'] -= begin
    tr['end'] -= begin

  window_size_inside = end - begin
  window_size_large = window_size_inside + 20

  if len(transcripts) == 0:
    return ""

  height = (len(transcripts) * 10) + 20
  computed = window_size_large / len(transcripts)

  # Génération des lignes
  lines = [
    f"""
    <line x1="0" y1="{window_size_large}" x2="{window_size_large}" y2="{window_size_large}" style="stroke:red; stroke-width: 50"/>
    <text x="0" y="{window_size_large - 50}" style="fill: #8c2300" font-size="150" font-family="Arial">{begin}</text>
    <text x="{window_size_inside - 750}" y="{window_size_large - 50}" style="fill: #8c2300" font-size="150" font-family="Arial">{end}</text>
    """
  ]

  cur_height = 100

  for tr in transcripts:
    begin_line = tr['start']
    end_line = tr['end']
    trid = tr['id']

    lines.append(f"""
      <g class="svg-transcript">
        <a target="_blank" href="{url_for('get_transcript', id=trid)}">
          <line x1="{begin_line}" y1="{cur_height}" x2="{end_line}" y2="{cur_height}" style="stroke: #4452a9; stroke-width: 200"/>
          <text x="{begin_line + 50}" y="{cur_height + 330}" style="fill: #08205d" font-size="250" font-family="Arial">{trid}</text>
        </a>
        <tspan x="{begin_line + 50}" y="{cur_height + 330}" class="svg-popup">Hello !</tspan>
      </g>
    """)

    cur_height += computed

  lines_joined = "\n".join(lines)

  return f"""
    <svg viewBox="0 0 {window_size_large} {window_size_large}" 
      style="height: {height*4}px; margin: auto; display: block; margin-top: 1rem;">
      {lines_joined}
    </svg>
  """
