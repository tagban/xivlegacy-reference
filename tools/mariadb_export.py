#!/usr/bin/env python3
"""Copy the game-data tables build.py reads from a XIVLegacy MariaDB
database into a SQLite file, so the site can be rebuilt from a current
server database (the server moved from SQLite to MariaDB in Nov 2026).

    tools/mariadb_export.py <mariadb database> <out.sqlite>

Connection settings come from the usual MariaDB client options
(~/.my.cnf, or DB_USER / DB_HOST / DB_PORT in the environment).
Only game-data tables are copied, never characters or accounts.
"""
import os, re, sqlite3, subprocess, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def tables_used():
    src = open(os.path.join(ROOT, "tools", "build.py")).read()
    return sorted(set(re.findall(r"(?:FROM|JOIN) ((?:gamedata|server)_[a-z_]+)", src)))


def client(db):
    cmd = ["mariadb", "--xml", "-N", db]
    for env, opt in (("DB_USER", "-u"), ("DB_HOST", "-h"), ("DB_PORT", "-P")):
        if os.environ.get(env):
            cmd[1:1] = [opt, os.environ[env]]
    return cmd


def query(db, sql):
    out = subprocess.run(client(db) + ["-e", sql], check=True, capture_output=True).stdout
    root = ET.fromstring(out)
    for row in root.iter("row"):
        yield [(None if f.get(NIL) == "true" else (f.text or "")) for f in row.iter("field")], \
              [f.get("name") for f in row.iter("field")]


def main():
    db, path = sys.argv[1], sys.argv[2]
    if os.path.exists(path):
        os.remove(path)
    out = sqlite3.connect(path)
    for table in tables_used():
        cols = [(r[0], r[1]) for r, _ in query(db,
                f"SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION")]
        if not cols:
            print(f"{table}: missing, skipped")
            continue
        ints = {n for n, t in cols if "int" in t}
        reals = {n for n, t in cols if t in ("float", "double", "decimal")}
        names = [n for n, _ in cols]
        out.execute(f'CREATE TABLE "{table}" ({", ".join(chr(34) + n + chr(34) for n in names)})')
        count = 0
        for vals, fields in query(db, f"SELECT * FROM `{table}`"):
            row = []
            for name, v in zip(fields, vals):
                if v is not None and name in ints:
                    v = int(v)
                elif v is not None and name in reals:
                    v = float(v)
                row.append(v)
            out.execute(f'INSERT INTO "{table}" ({", ".join(chr(34) + f + chr(34) for f in fields)}) '
                        f'VALUES ({", ".join("?" * len(row))})', row)
            count += 1
        print(f"{table}: {count} rows")
    out.commit()


if __name__ == "__main__":
    main()
