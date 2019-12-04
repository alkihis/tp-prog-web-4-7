import matplotlib.figure
from io import BytesIO
from flask import url_for, render_template

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
  window_height = len(transcripts) * 700
  window_size_large = window_size_inside + 20

  if len(transcripts) == 0:
    return ""

  height = (len(transcripts) * 10) + 20
  computed = 700
  cur_height = 100

  return render_template("transcript.svg", **{
    "window_size_large": window_size_large,
    "window_size_inside": window_size_inside,
    "height": height,
    "window_size_height": window_height,
    "begin": begin,
    "end": end,
    "line_height": computed,
    "transcripts": transcripts,
  })
