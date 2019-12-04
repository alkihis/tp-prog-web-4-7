import matplotlib.figure
from io import BytesIO
from flask import url_for, render_template
import colorsys

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
  begin = 1e10000
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
  line_height = 700
  window_height = len(transcripts) * line_height

  if len(transcripts) == 0:
    return ""

  height = (len(transcripts) * 10) + 20

  for tr in transcripts:
    tr['start'] = (tr['start'] / window_size_inside) * window_height
    tr['end'] = (tr['end'] / window_size_inside) * window_height

  window_size_inside = window_height
  window_size_large = window_size_inside + 50

  N = 5
  HSV_tuples = [(x*1.0/N, 0.5, 0.5) for x in range(N)]
  colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples))

  return render_template("transcript.svg", **{
    "window_size_large": window_size_large,
    "window_size_inside": window_size_inside,
    "height": height,
    "window_size_height": window_height,
    "begin": begin,
    "end": end,
    "line_height": line_height,
    "transcripts": transcripts,
    "colors": colors,
  })
