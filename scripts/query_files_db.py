#!/usr/bin/env python3
"""
Lightweight DB checker for the `files` table.
Usage:
  # use DATABASE_URL env
  DATABASE_URL="postgres://..." python query_files_db.py

  # or pass as argument
  python query_files_db.py --db "postgres://..."

If the URL starts with sqlite, the script will use sqlite3.
"""
import os
import sys
import argparse

try:
    import psycopg2
except Exception:
    psycopg2 = None

import sqlite3

DATABASE_URL="postgresql://postgres_datastorage_user:I3eaFA93a3KjiZdtNgIUOu19gcEbEJxM@dpg-d54hg7mr433s73d0knk0-a/postgres_datastorage"


QUERY = "SELECT id, filename, url, owner_id FROM files ORDER BY id DESC LIMIT 20;"


def run_sqlite(db_url):
    # db_url like sqlite:///./cloud.db or sqlite:///C:/path/to/db
    path = db_url
    if db_url.startswith('sqlite:///'):
        path = db_url[len('sqlite:///'):]
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(QUERY)
    rows = cur.fetchall()
    cur.execute("PRAGMA table_info(files);")
    cols = cur.fetchall()
    conn.close()
    return rows, cols


def run_postgres(db_url):
    if psycopg2 is None:
        print("psycopg2 not installed. Install with: pip install psycopg2-binary")
        sys.exit(2)
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(QUERY)
    rows = cur.fetchall()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='files';")
    cols = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows, cols


def pretty_print(rows, cols):
    print('\nColumns in `files` table:')
    if isinstance(cols, list):
        if cols and isinstance(cols[0], tuple):
            # sqlite PRAGMA output
            print(', '.join([c[1] for c in cols]))
        else:
            print(', '.join(cols) if cols else '(none)')
    else:
        print(cols)

    print('\nLatest rows (limit 20):')
    if not rows:
        print('(no rows)')
        return
    # determine column widths
    widths = [4, 20, 60, 8]
    header = ["id", "filename", "url", "owner_id"]
    fmt = " | ".join([f"{{:{w}}}" for w in widths])
    print(fmt.format(*header))
    print('-' * (sum(widths) + 3 * (len(widths)-1)))
    for r in rows:
        id_, filename, url, owner = r
        filename = (filename or '')[:widths[1]]
        url = (url or '')[:widths[2]]
        print(fmt.format(str(id_), filename, url, str(owner)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', help='DATABASE_URL override')
    args = p.parse_args()

    db_url = args.db or os.getenv('DATABASE_URL')
    if not db_url:
        print('Please provide DATABASE_URL via --db or environment variable DATABASE_URL')
        sys.exit(1)

    db_url = db_url.strip()
    try:
        if db_url.startswith('sqlite'):
            rows, cols = run_sqlite(db_url)
        else:
            rows, cols = run_postgres(db_url)
    except Exception as e:
        print('Error connecting/querying DB:', e)
        sys.exit(3)

    pretty_print(rows, cols)


if __name__ == '__main__':
    main()
