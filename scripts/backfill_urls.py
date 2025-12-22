#!/usr/bin/env python3
"""
Backfill `url` column in the `files` table from Cloudinary.

Usage:
  - Ensure your environment has CLOUDINARY_* env vars or CLOUDINARY_URL
  - Ensure DATABASE_URL points to the database used by the running app
  - Activate virtualenv and run: python scripts/backfill_urls.py

This script will:
 1. Add a `url` column to `files` if it doesn't exist (sqlite or postgres)
 2. Query rows where url is NULL or empty and try to retrieve secure_url via Cloudinary API
 3. Update rows with the secure_url

Be careful when running against production DB; recommended to backup DB first.
"""
import os
import sys
from sqlalchemy import create_engine, inspect, Table, Column, String, MetaData, select
from sqlalchemy.orm import sessionmaker
import cloudinary
import cloudinary.api
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cloud.db")

def ensure_url_column(engine):
    insp = inspect(engine)
    cols = [c['name'] for c in insp.get_columns('files')]
    if 'url' in cols:
        print("'url' column already exists")
        return

    print("Adding 'url' column to files table")
    dialect = engine.dialect.name
    if dialect == 'sqlite':
        # sqlite supports ALTER TABLE ADD COLUMN
        with engine.connect() as conn:
            conn.execute("ALTER TABLE files ADD COLUMN url TEXT;")
    else:
        with engine.connect() as conn:
            conn.execute("ALTER TABLE files ADD COLUMN url TEXT;")
    print("Added 'url' column")

def backfill(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    metadata = MetaData()
    files_table = Table('files', metadata, autoload_with=engine)

    rows = session.execute(select([files_table.c.id, files_table.c.filename, files_table.c.url]).where(
        (files_table.c.url == None) | (files_table.c.url == "")
    )).fetchall()

    print(f"Found {len(rows)} rows to backfill")
    if len(rows) == 0:
        return

    for r in rows:
        fid = r[0]
        public_id = r[1]
        print(f"Processing id={fid} public_id={public_id}...")
        try:
            res = cloudinary.api.resource(public_id, resource_type='auto')
            secure_url = res.get('secure_url')
            if secure_url:
                session.execute(files_table.update().where(files_table.c.id==fid).values(url=secure_url))
                print(f" -> updated id={fid} url={secure_url}")
            else:
                print(f" -> no secure_url for {public_id}")
        except Exception as e:
            print(f" -> cloudinary lookup failed for {public_id}: {e}")

    session.commit()
    session.close()

def main():
    print(f"Using DATABASE_URL={DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    # configure cloudinary
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True
    )

    ensure_url_column(engine)
    backfill(engine)

if __name__ == '__main__':
    try:
        from sqlalchemy import create_engine
    except Exception as e:
        print('Missing dependencies. Activate venv and install requirements.txt')
        sys.exit(1)
    main()
