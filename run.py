import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # mesmo preparo do executavel: tabelas novas, indice e planilhas antigas
    from desktop import ensure_database

    ensure_database(app)
    debug = os.environ.get("FLASK_DEBUG", "") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=5000, debug=debug)
