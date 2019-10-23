from main import app
from flask import render_template
from database import get_db

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


