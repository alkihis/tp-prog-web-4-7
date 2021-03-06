import flask
from flask import send_from_directory, request, make_response, render_template, abort, g
import sqlite3
from get_image_mpl import getimage, getsvg
import typing
import datetime
import os
import json
import hashlib 

SITENAME = "http://localhost:5000"
SQLITE_FILE = "ensembl_hs63_simple.sqlite"

app = flask.Flask(__name__)

def get_db() -> sqlite3.Connection:
  """
    Renvoie la base de données SQLITE ensembl.
  """
  db = getattr(g, '_db_', None)

  if not db:
    db = g._db_ = sqlite3.connect(SQLITE_FILE)
    
  return db

def get_db_mtime():
  """
    Renvoie le temps de la dernière modification de la base de données.
  """
  return os.path.getmtime(SQLITE_FILE)

@app.teardown_request
def auto_db_close(teardown):
  """
    Après chaque requête, ferme la base de données.
  """
  # after each request, close database automatically
  # si jamais une exception a interrompu la requête par exemple
  db = get_db()
  if db:
    db.close()


@app.errorhandler(sqlite3.Error)
def handle_sqlite_exceptions(error: sqlite3.Error):
  return render_template('sql_error.html.jinja', error=error), 500


# Sert les fichiers statiques
@app.route('/<path:filename>')
def serve_root(filename):
  return send_from_directory('static', filename)


# Page parties => gènes
@app.route('/parts/<part>/genes')
def organism_parts(part: str):
  conn = get_db()

  offset = 0
  page_len = 30
  page = 1

  if request.args.get('page'):
    page_ = request.args.get('page')

    try:
      page_ = int(page_)

      if page > 0:
        page = page_
        offset = page_len * (page - 1)
    except:
      pass

  # Get all the rows that have a atlas_organism_part from Expression
  cur = conn.cursor()

  expressions = cur.execute(f"""
    SELECT DISTINCT t.ensembl_gene_id, g.associated_gene_name
    FROM Expression e 
    JOIN Transcripts t 
    ON e.ensembl_transcript_id=t.ensembl_transcript_id 
    JOIN Genes g 
    ON t.ensembl_gene_id=g.ensembl_gene_id 
    WHERE e.atlas_organism_part=?
    LIMIT {page_len + 1} OFFSET {offset}
  """, [part])

  exprs: typing.List[typing.Tuple[str, str]] = expressions.fetchall()

  if not exprs:
    abort(404)

  has_next = len(exprs) == page_len + 1
  has_before = offset != 0

  next_page = 0
  before_page = 0

  if has_next:
    next_page = page + 1
  if has_before:
    before_page = page - 1

  return render_template('part.html.jinja', 
    genes=exprs[0:page_len], 
    before_page=before_page, 
    next_page=next_page, 
    part=part, 
    has_next=has_next, 
    has_before=has_before
  )


# Homepage
@app.route('/')
def list_of_parts():
  conn = get_db()

  # Get all the rows that have a atlas_organism_part from Expression
  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT DISTINCT atlas_organism_part 
    FROM Expression 
    WHERE atlas_organism_part IS NOT NULL 
    ORDER BY atlas_organism_part ASC
  """)

  parts = [ part[0] for part in expressions.fetchall() ]

  return render_template('main.html.jinja', parts=parts)


# Page du gène
@app.route('/genes/<id>')
def get_gene(id: str):
  conn = get_db()

  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT *
    FROM Genes 
    WHERE ensembl_gene_id=?
  """, [id])

  row_gene = expressions.fetchone()

  if not row_gene:
    abort(404)

  gene_info = {
    'id': row_gene[0],
    'associated_gene_name': row_gene[1],
    'chromosome_name': row_gene[2],
    'band': row_gene[3],
    'strand': row_gene[4],
    'start': row_gene[5],
    'end': row_gene[6],
    'transcript_count': row_gene[7]
  }

  # Transcripts pour ce genes
  transcripts = cur.execute("""
    SELECT *
    FROM Transcripts 
    WHERE ensembl_gene_id=?
  """, [id])

  rows_transcripts = transcripts.fetchall()

  transcripts_infos = []
  transcripts_ids = []

  for row in rows_transcripts:
    transcripts_ids.append(row[0])
    transcripts_infos.append({
      'id': row[0],
      'start': row[2],
      'end': row[3]
    })

  # Recherche des parties d'organisme reliés
  parts = []

  if transcripts_ids:
    parts_organism = cur.execute("""
      SELECT DISTINCT atlas_organism_part
      FROM Expression 
      WHERE ensembl_transcript_id IN (%s)
      AND atlas_organism_part IS NOT NULL
    """ % ','.join(["?" for i in transcripts_ids]), transcripts_ids)

    parts = [ part[0] for part in parts_organism.fetchall() ]

  content_svg = get_gene_svg(gene_info['id'])

  return render_template('gene.html.jinja', 
    gene=gene_info, 
    transcripts=transcripts_infos,
    parts=parts,
    gene_svg_content=content_svg
  )


# Image matplotlib représentant les parties de gènes par transcripts
@app.route('/genes/<id>/parts.png')
def get_gene_image(id: str):
  conn = get_db()

  cur = conn.cursor()

  counts = cur.execute("""
    SELECT atlas_organism_part, COUNT(Ensembl_Transcript_ID)
    FROM Transcripts
    NATURAL JOIN Expression
    WHERE Ensembl_gene_id=?
    AND atlas_organism_part IS NOT NULL
    GROUP BY atlas_organism_part
    ORDER BY atlas_organism_part DESC
  """, [id])

  parts = {}

  for part, count in counts.fetchall():
    parts[part] = int(count)

  resp = make_response(getimage(parts)) 

  resp.headers['content-type'] = "image/png"
  return resp


# Image SVG représentant les transcripts et leur position pour un gène donné
@app.route('/genes/<id>/transcripts.svg')
def get_gene_svg(id: str):
  conn = get_db()

  cur = conn.cursor()

  transcripts = cur.execute("""
    SELECT *
    FROM Transcripts
    WHERE Ensembl_gene_id=?
  """, [id])

  res = []
  for tr_id, g_id, start, end, biotype in transcripts:
    res.append({ 'id': tr_id, 'start': start, 'end': end })

  svg_text = getsvg(res)

  return svg_text


# Page du transcript
@app.route('/transcripts/<id>')
def get_transcript(id: str):
  conn = get_db()

  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT *
    FROM Transcripts 
    WHERE ensembl_transcript_id=?
  """, [id])

  row_transcript = expressions.fetchone()

  if not row_transcript:
    abort(404)

  tr_info = {
    'id': row_transcript[0],
    'gene': row_transcript[1],
    'start': row_transcript[2],
    'end': row_transcript[3],
    'biotype': row_transcript[4]
  }

  parts_organism = cur.execute("""
      SELECT DISTINCT atlas_organism_part
      FROM Expression 
      WHERE ensembl_transcript_id=?
      AND atlas_organism_part IS NOT NULL
    """, [row_transcript[0]])

  parts = [ part[0] for part in parts_organism.fetchall() ]

  return render_template('transcript.html.jinja', transcript=tr_info, parts=parts)


#### API
#### ERRORS
ERROR_CODES = {
  1: ["Page not found", 404],
  2: ["Missing parameters", 400],
  3: ["Server error", 500],
  4: ["Invalid parameters", 400],
  5: ["Too many arguments", 400],
  6: ["Invalid argument type", 400],
  7: ["Element already exists", 409],
  8: ["Sort method is invalid", 400],
}

# Fonction générique pour envoyer une erreur en JSON.
def sendError(code: int, detail = None):
  if code in ERROR_CODES:
    if detail:
      resp: flask.Response = flask.jsonify({"error": ERROR_CODES[code][0], "detail": detail, "code": code})
    else:
      resp: flask.Response = flask.jsonify({"error": ERROR_CODES[code][0], "code": code})

    resp.status_code = ERROR_CODES[code][1]
    return resp

  raise IndexError("Code does not exists")


# Génère un dictionnaire représentant un gène 
# depuis une ligne de la base de données
def generate_gene_object_from_row(row_gene, detailed = False):
  if not detailed:
    return {
      "Ensembl_Gene_ID": row_gene[0],
      "Associated_Gene_Name": row_gene[1],
      "Chromosome_Name": row_gene[2],
      "Band": row_gene[3],
      "Strand": row_gene[4],
      "Gene_Start": row_gene[5],
      "Gene_End": row_gene[6],
      "Transcript_count": row_gene[7],
      "href": SITENAME + flask.url_for("get_gene", id=row_gene[0])
    }

  # detailed
  return {
    "Ensembl_Gene_ID": row_gene[0],
    "Associated_Gene_Name": row_gene[1],
    "Chromosome_Name": row_gene[2],
    "Band": row_gene[3],
    "Strand": row_gene[4],
    "Gene_Start": row_gene[5],
    "Gene_End": row_gene[6],
    "transcripts": generate_transcript_from_db(row_gene[0], True),
    "href": SITENAME + flask.url_for("get_gene", id=row_gene[0])
  }


# Génère un dictionnaire depuis un gène de la base de données par son ID
def generate_gene_from_db(id: str, detailed = False):
  conn = get_db()

  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT *
    FROM Genes 
    WHERE ensembl_gene_id=?
  """, [id])

  row_gene = expressions.fetchone()

  if not row_gene:
    return None

  return generate_gene_object_from_row(row_gene, detailed)


# Génère un dictionnaire représentant un transcript
# depuis une ligne de la base de données
def generate_transcript_object_from_row(row_transcript):
  return {
    "Ensembl_Transcript_ID": row_transcript[0],
    "Transcript_Start": row_transcript[2],
    "Transcript_End": row_transcript[3],
  }


# Génère un dictionnaire depuis un transcript 
# de la base de données par son ID
def generate_transcript_from_db(id: str, from_gene_id = False):
  conn = get_db()
  cur = conn.cursor()

  # Transcript ID
  if not from_gene_id:
    # Transcripts pour ce genes
    transcripts = cur.execute("""
      SELECT *
      FROM Transcripts 
      WHERE ensembl_transcript_id=?
    """, [id])

    row_transcript = transcripts.fetchone()

    if row_transcript:
      return None
    
    return generate_transcript_object_from_row(row_transcript)
  
  # List of gene IDs
  else:
    # Transcripts pour ce genes
    transcripts = cur.execute("""
      SELECT *
      FROM Transcripts 
      WHERE ensembl_gene_id=?
    """, [id])

    rows_transcripts = transcripts.fetchall()

  return [
    generate_transcript_object_from_row(x)
    for x in rows_transcripts
  ]


# Obtenir un gène par son ID (API)
@app.route('/api/genes/<id>', methods=["GET"])
def api_get_gene(id: str):
  custom_etag = str(get_db_mtime())
  if custom_etag in request.if_none_match:
    resp = make_response("", 304) # 304 not modified
    resp.set_etag(custom_etag)
    return resp

  conn = get_db()

  row_gene = generate_gene_from_db(id, True)

  if not row_gene:
    abort(sendError(1))

  rq = flask.jsonify(row_gene)
  rq.set_etag(custom_etag)

  return rq


# Obtenir une ligne de gènes (API)
@app.route('/api/genes')
def api_get_gene_collection():  
  offset = 0

  if request.args.get('offset'):
    o = request.args.get('offset')

    try:
      o = int(o)

      if o > 0:
        offset = o
      else:
        raise ValueError()
    except:
      abort(sendError(4, "Invalid offset parameter"))

  custom_etag = str(get_db_mtime()) + str(offset)
  if custom_etag in request.if_none_match:
    resp = make_response("", 304) # 304 not modified
    resp.set_etag(custom_etag)
    return resp

  mode_sort = "Ensembl_gene_id"
  way = 'ASC'

  if 'sort' in request.args:
    sorts_to_column = {
      'gene': 'Ensembl_gene_id',
      'count': 'Transcript_count',
      'strand': 'Strand',
      'start': 'Gene_start',
      'end': 'Gene_end'
    }

    if request.args['sort'] in sorts_to_column:
      mode_sort = sorts_to_column[request.args['sort']]
    else:
      abort(sendError(8))
  
  if 'way' in request.args and request.args['way'] == 'desc':
    way = "DESC"

  conn = get_db()

  cur = conn.cursor()

  expressions = cur.execute(f"""
    SELECT *
    FROM Genes 
    ORDER BY {mode_sort} {way}
    LIMIT 100 OFFSET {offset}
  """)

  rows = expressions.fetchall()

  response = {
    "items": [generate_gene_object_from_row(x) for x in rows],
    "first": offset,
    "last": (offset + 100) - 1,
    "prev": SITENAME + flask.url_for("api_get_gene_collection", offset=max(offset - 100, 0)),
    "next": SITENAME + flask.url_for("api_get_gene_collection", offset=offset + 100)
  }

  rq = flask.jsonify(response)
  rq.set_etag(custom_etag)

  return rq


# Supprimer un gène par son ID (API)
@app.route('/api/genes/<id>', methods=["DELETE"])
def api_delete_gene(id: str):
  conn = get_db()
  cur = conn.cursor()

  gene = generate_gene_from_db(id)

  if not gene:
    abort(sendError(1))

  cur.execute("""
    DELETE FROM Genes 
    WHERE ensembl_gene_id=?
  """, [id])

  conn.commit()

  return flask.jsonify({ "deleted": id })


def check_each_new_gene(data: dict, index = 1, check_existing = True):
  """
    Vérification de la validité d'un gène (représenté sous forme de dictionnaire)

    data: Gène

    index: Position dans l'avancement de la vérification (optionnel, utilisé pour les message d'erreur)

    check_existing: Vérifier ou non si le gène existe déjà
  """

  if type(data) is not dict:
    abort(sendError(6, f"Invalid type for element {index}"))

  count = 0
  for p in ["Ensembl_Gene_ID", "Chromosome_Name", "Band", "Gene_Start", "Gene_End"]:
    count += 1
    if not p in data:
      abort(sendError(2, f"Parameter {p} is missing in JSON object in element {index}."))

  if check_existing:
    gene = generate_gene_from_db(data['Ensembl_Gene_ID'])

    if gene:
      abort(sendError(7))

  if "Strand" in data:
    count += 1

  if "Associated_Gene_Name" in data:
    count += 1
  
  for p in ["Ensembl_Gene_ID", "Chromosome_Name", "Band", "Associated_Gene_Name"]:
    if p in data and type(data[p]) is not str:
      abort(sendError(6, f"Parameter {p} is not of type string in element {index}."))

  for p in ["Strand", "Gene_Start", "Gene_End"]:
    if p in data and type(data[p]) is not int:
      abort(sendError(6, f"Parameter {p} is not of type int in element {index}."))

  if len(data) > count:
    abort(sendError(5))

  if data['Gene_Start'] >= data['Gene_End']:
    abort(sendError(4, f"Gene end must be superior to gene start in element {index}"))


# Publier un nouveau gène ou actualiser un gène existant (API)
@app.route('/api/genes/<id>', methods=["PUT"])
def api_put_gene(id: str):
  if not request.is_json:
    abort(sendError(4, "Request body must be JSON-encoded"))

  data = request.json

  check_each_new_gene(data, 1, False)

  if data['Ensembl_Gene_ID'] != id:
    abort(sendError(4, "Parameter Ensembl_Gene_ID must match URL parameter"))

  old_gene = generate_gene_from_db(id)

  conn = get_db()
  cur = conn.cursor()
  cur.execute("""
    INSERT OR REPLACE INTO Genes 
    (ensembl_gene_id, associated_gene_name, Chromosome_Name, band, strand, gene_start, gene_end)
    VALUES 
    (?, ?, ?, ?, ?, ?, ?)
  """, [
    data['Ensembl_Gene_ID'],
    data['Associated_Gene_Name'] if 'Associated_Gene_Name' in data else None,
    data['Chromosome_Name'],
    data['Band'],
    data['Strand'] if 'Strand' in data else None,
    data['Gene_Start'],
    data['Gene_End'],
  ])

  conn.commit()

  actual_gene = generate_gene_from_db(id)
  dump_actual = json.dumps(actual_gene)

  # Calcule le ETag
  etag = hashlib.md5(dump_actual.encode()).hexdigest()

  # Test la différence entre old et actual
  if dump_actual == json.dumps(old_gene):
    if etag in request.if_none_match:
      resp = make_response("", 304) # 304 not modified
      resp.set_etag(etag)
      return resp

  rq = flask.jsonify(actual_gene)
  rq.set_etag(etag)

  return rq


# Publier un nouveau gène (API)
@app.route('/api/genes', methods=["POST"])
def api_create_new_gene():
  if not request.is_json:
    abort(sendError(4, "Request body must be JSON-encoded"))

  data = request.json

  if type(data) is not list:
    data = [data]

  index = 1
  ids = set()

  for e in data:
    check_each_new_gene(e, index)

    if e['Ensembl_Gene_ID'] in ids:
      abort(sendError(4, f"Identifier {e['Ensembl_Gene_ID']} is sended multiple times"))
    ids.add(e['Ensembl_Gene_ID'])

    index += 1
  
  conn = get_db()
  cur = conn.cursor()

  for e in data:
    cur.execute("""
      INSERT INTO Genes (ensembl_gene_id, associated_gene_name, Chromosome_Name, band, strand, gene_start, gene_end)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
      e['Ensembl_Gene_ID'],
      e['Associated_Gene_Name'] if 'Associated_Gene_Name' in e else None,
      e['Chromosome_Name'],
      e['Band'],
      e['Strand'] if 'Strand' in e else None,
      e['Gene_Start'],
      e['Gene_End'],
    ])

  conn.commit()

  return flask.jsonify({"created": [
    SITENAME + flask.url_for("get_gene", id=e['Ensembl_Gene_ID'])
    for e in data
  ]})
