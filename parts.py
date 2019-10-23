from main import app
from flask import render_template, abort
from database import get_db

@app.route('/parts/<part>/genes')
def organism_parts(part: str):
  conn = get_db()

  # Get all the rows that have a atlas_organism_part from Expression
  cur = conn.cursor()
  expressions = cur.execute("""
    SELECT DISTINCT t.ensembl_gene_id, g.associated_gene_name
    FROM Expression e 
    JOIN Transcripts t 
    ON e.ensembl_transcript_id=t.ensembl_transcript_id 
    JOIN Genes g 
    ON t.ensembl_gene_id=g.ensembl_gene_id 
    WHERE e.atlas_organism_part=?
  """, [part])

  # List[Tuple[str, str]]
  exprs = expressions.fetchall()

  if not exprs:
    abort(404)

  conn.close()

  return render_template('part.html', genes=exprs)
