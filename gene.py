from main import app
from database import get_db
from flask import abort

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
    """ % ','.join('?' for i in transcripts_ids), transcripts_ids)

    parts = [ part[0] for part in parts_organism.fetchall() ]

  conn.close()

  return render_template('gene.html', gene=gene_info, transcripts=transcripts_infos, parts=parts)