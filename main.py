import flask
from flask import send_from_directory, request, make_response
from flask import render_template, abort
from database import get_db
import sqlite3
from flask import g
from get_image_mpl import getimage, getsvg

CONFIG = "SQLITE"

app = flask.Flask(__name__)

def get_db() -> sqlite3.Connection:
  db = getattr(g, '_db_', None)

  if CONFIG == "SQLITE":
    if not db:
      db = g._db_ = sqlite3.connect("ensembl_hs63_simple.sqlite")
  else:
    import mysql.connector

    if not db:
      db = g._db_ = mysql.connector.connect(
        user="alkihis",
        password="mysqlpassword",
        host="alkihis.mysql.pythonanywhere-services.com",
        database="alkihis$ensembl"
      )
    
  return db

# Listen for get request on root
@app.route('/<path:filename>')
def serve_root(filename):
  return send_from_directory('static', filename)

@app.route('/parts/<part>/genes')
def organism_parts(part: str):
  conn = get_db()

  offset = 0
  page_len = 30
  page = 1

  print(request.args)

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

  expressions = cur.execute("""
    SELECT DISTINCT t.ensembl_gene_id, g.associated_gene_name
    FROM Expression e 
    JOIN Transcripts t 
    ON e.ensembl_transcript_id=t.ensembl_transcript_id 
    JOIN Genes g 
    ON t.ensembl_gene_id=g.ensembl_gene_id 
    WHERE e.atlas_organism_part=""" + ("?" if CONFIG == "SQLITE" else "%s") + f"""
    LIMIT {page_len + 1} OFFSET {offset}
  """, [part])

  # List[Tuple[str, str]]
  exprs = expressions.fetchall()

  if not exprs:
    abort(404)

  conn.close()

  has_next = len(exprs) == page_len + 1
  has_before = offset != 0

  next_page = 0
  before_page = 0

  if has_next:
    next_page = page + 1
  if has_before:
    before_page = page - 1

  return render_template('part.html', 
    genes=exprs[0:page_len], 
    before_page=before_page, 
    next_page=next_page, 
    part=part, 
    has_next=has_next, 
    has_before=has_before
  )

@app.route('/')
def list_of_parts():
  conn = get_db()

  try:
    # Get all the rows that have a atlas_organism_part from Expression
    cur = conn.cursor()
    expressions = cur.execute("SELECT DISTINCT atlas_organism_part FROM Expression WHERE atlas_organism_part IS NOT NULL ORDER BY atlas_organism_part ASC")

    parts = [ part[0] for part in expressions.fetchall() ]

    conn.close()
    return render_template('main.html', parts=parts)
  except:
    conn.close()

@app.route('/genes/<id>')
def get_gene(id: str):
  conn = get_db()

  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT *
    FROM Genes 
    WHERE ensembl_gene_id=""" + ("?" if CONFIG == "SQLITE" else "%s") + """
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
    WHERE ensembl_gene_id=""" + ("?" if CONFIG == "SQLITE" else "%s") + """
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
    """ % ','.join([("?" if CONFIG == "SQLITE" else "%s") for i in transcripts_ids]), transcripts_ids)

    parts = [ part[0] for part in parts_organism.fetchall() ]

  content_svg = get_gene_svg(gene_info['id'])
  conn.close()

  return render_template('gene.html', 
    gene=gene_info, 
    transcripts=transcripts_infos,
    parts=parts,
    gene_svg_content=content_svg
  )

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

@app.route('/transcripts/<id>')
def get_transcript(id: str):
  conn = get_db()

  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT *
    FROM Transcripts 
    WHERE ensembl_transcript_id=""" + ("?" if CONFIG == "SQLITE" else "%s") + """
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
      WHERE ensembl_transcript_id=""" + ("?" if CONFIG == "SQLITE" else "%s") + """
      AND atlas_organism_part IS NOT NULL
    """, [row_transcript[0]])

  parts = [ part[0] for part in parts_organism.fetchall() ]

  conn.close()

  return render_template('transcript.html', transcript=tr_info, parts=parts)
