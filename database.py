import sqlite3
from flask import g

def get_db() -> sqlite3.Connection:
  db = getattr(g, '_db_', None)

  if not db:
    db = g._db_ = sqlite3.connect("ensembl_hs63_simple.sqlite")
  
  return db
    
