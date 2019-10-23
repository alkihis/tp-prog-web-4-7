from main import app
from database import get_db
from flask import abort, render_template

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

  conn.close()

  return render_template('transcript.html', transcript=tr_info, parts=parts)