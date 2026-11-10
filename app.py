"""
Run:
    pip install flask
    python app.py
Then open http://127.0.0.1:5000
"""
import os
import sqlite3

from flask import Flask, g, redirect, render_template, request, url_for

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todo.db")

PRIORITIES = ("high", "medium", "low")
FILTERS = ("all", "active", "done")
RANK_SQL = "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                   id          INTEGER PRIMARY KEY AUTOINCREMENT,
                   title       TEXT    NOT NULL,
                   description TEXT    NOT NULL DEFAULT '',
                   priority    TEXT    NOT NULL DEFAULT 'medium',
                   done        INTEGER NOT NULL DEFAULT 0,
                   position    INTEGER NOT NULL
               )"""
        )


# ----------------------------------------------------------------- helpers
def clean_filter(value):
    return value if value in FILTERS else "all"


def clean_priority(value):
    return value if value in PRIORITIES else "medium"


def back(filter_name):
    """Redirect to the list, keeping the current filter."""
    return redirect(url_for("index", filter=clean_filter(filter_name)))


def visible_tasks(filter_name):
    sql = "SELECT * FROM tasks"
    if filter_name == "active":
        sql += " WHERE done = 0"
    elif filter_name == "done":
        sql += " WHERE done = 1"
    sql += " ORDER BY position ASC, id ASC"
    return get_db().execute(sql).fetchall()


# ------------------------------------------------------------------ routes
@app.get("/")
def index():
    filter_name = clean_filter(request.args.get("filter"))
    db = get_db()
    tasks = visible_tasks(filter_name)

    total = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    left = db.execute("SELECT COUNT(*) FROM tasks WHERE done = 0").fetchone()[0]

    edit_id = request.args.get("edit", type=int)
    return render_template(
        "index.html",
        tasks=tasks,
        filter=filter_name,
        total=total,
        left=left,
        done_count=total - left,
        edit_id=edit_id,
    )


@app.post("/add")
def add():
    title = request.form.get("title", "").strip()[:120]
    description = request.form.get("description", "").strip()
    priority = clean_priority(request.form.get("priority"))

    if title:
        db = get_db()
        # New tasks go to the top of the list.
        top = db.execute("SELECT COALESCE(MIN(position), 0) FROM tasks").fetchone()[0]
        db.execute(
            "INSERT INTO tasks (title, description, priority, position) VALUES (?, ?, ?, ?)",
            (title, description, priority, top - 1),
        )
        db.commit()
    return back(request.form.get("filter"))


@app.post("/toggle/<int:task_id>")
def toggle(task_id):
    db = get_db()
    db.execute("UPDATE tasks SET done = 1 - done WHERE id = ?", (task_id,))
    db.commit()
    return back(request.form.get("filter"))


@app.post("/priority/<int:task_id>")
def set_priority(task_id):
    db = get_db()
    db.execute(
        "UPDATE tasks SET priority = ? WHERE id = ?",
        (clean_priority(request.form.get("priority")), task_id),
    )
    db.commit()
    return back(request.form.get("filter"))


@app.post("/edit/<int:task_id>")
def edit(task_id):
    title = request.form.get("title", "").strip()[:120]
    description = request.form.get("description", "").strip()
    if title:
        db = get_db()
        db.execute(
            "UPDATE tasks SET title = ?, description = ? WHERE id = ?",
            (title, description, task_id),
        )
        db.commit()
    return back(request.form.get("filter"))


@app.post("/delete/<int:task_id>")
def delete(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return back(request.form.get("filter"))


@app.post("/move/<int:task_id>/<direction>")
def move(task_id, direction):
    """Swap a task with its neighbour in the current (filtered) view."""
    filter_name = clean_filter(request.form.get("filter"))
    tasks = visible_tasks(filter_name)
    ids = [t["id"] for t in tasks]

    if task_id in ids and direction in ("up", "down"):
        i = ids.index(task_id)
        j = i - 1 if direction == "up" else i + 1
        if 0 <= j < len(tasks):
            a, b = tasks[i], tasks[j]
            db = get_db()
            db.execute("UPDATE tasks SET position = ? WHERE id = ?", (b["position"], a["id"]))
            db.execute("UPDATE tasks SET position = ? WHERE id = ?", (a["position"], b["id"]))
            db.commit()
    return back(filter_name)


@app.post("/sort")
def sort_by_priority():
    """High -> Medium -> Low. Manual order is kept within each priority."""
    db = get_db()
    rows = db.execute(
        f"SELECT id FROM tasks ORDER BY {RANK_SQL}, position ASC, id ASC"
    ).fetchall()
    for pos, row in enumerate(rows):
        db.execute("UPDATE tasks SET position = ? WHERE id = ?", (pos, row["id"]))
    db.commit()
    return back(request.form.get("filter"))


@app.post("/clear")
def clear_completed():
    db = get_db()
    db.execute("DELETE FROM tasks WHERE done = 1")
    db.commit()
    return back(request.form.get("filter"))


# -------------------------------------------------------------------- main
init_db()

if __name__ == "__main__":
    app.run(debug=True)
