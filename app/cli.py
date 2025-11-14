# app/cli.py
import click
from flask import current_app
from .extensions import db
from .models import Category


def _get_or_create_category(path: list[str]) -> Category:
    """
    Tworzy/znajduje kategorię po ścieżce hierarchicznej, np. ["Destylaty", "Cukrówka"].
    Zwraca obiekt najgłębszego węzła.
    """
    parent = None
    for name in path:
        name = name.strip()
        if not name:
            continue
        q = Category.query.filter_by(name=name, parent=parent).first()
        if not q:
            q = Category(name=name, parent=parent)
            db.session.add(q)
            db.session.flush()  # nadaj id, zanim pójdziemy głębiej
        parent = q
    return parent


def _seed_from_lines(lines: list[str]) -> tuple[int, int]:
    created = 0
    existed = 0
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(">")]
        # sprawdź czy istnieje już dokładnie taki węzeł
        parent = None
        exists_all = True
        for name in parts:
            found = Category.query.filter_by(name=name, parent=parent).first()
            if not found:
                exists_all = False
                break
            parent = found
        if exists_all:
            existed += 1
            continue
        _get_or_create_category(parts)
        created += 1
    db.session.commit()
    return created, existed


def _default_category_lines() -> list[str]:
    return [
        "Destylaty",
        "Destylaty > Cukrówka",
        "Destylaty > Zbożowe",
        "Destylaty > Owocowe > Jabłkowa",
        "Destylaty > Owocowe > Śliwkowa",
        "Nalewki",
        "Nalewki > Klasyczne > Wiśniówka",
        "Nalewki > Klasyczne > Pigwówka",
        "Nalewki > Ziołowe",
        "Wina",
        "Wina > Białe",
        "Wina > Czerwone",
        "Zestawy",
        "Zestawy > Startowe",
        "Zestawy > Degustacyjne",
        "Akcesoria",
        "Akcesoria > Butelki",
        "Akcesoria > Korki",
        "Akcesoria > Etykiety",
        "Drożdże i dodatki",
        "Drożdże i dodatki > Drożdże",
        "Drożdże i dodatki > Pożywki",
    ]


def register_cli(app):
    @app.cli.command("seed-categories")
    @click.option("--defaults", is_flag=True, help="Zasiej domyślne kategorie.")
    @click.option("--file", "file_path", type=click.Path(exists=True), help="Ścieżka do pliku z kategoriami.")
    def seed_categories(defaults: bool, file_path: str | None):
        """
        Wczytuje kategorie z pliku (linia = 'A > B > C') albo z zestawu domyślnego.
        """
        if not defaults and not file_path:
            raise click.UsageError("Użyj --defaults lub --file PATH")

        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = _default_category_lines()

        created, existed = _seed_from_lines(lines)
        click.echo(f"OK. Utworzone: {created}, już były: {existed}")

    @app.cli.command("list-categories")
    def list_categories():
        """
        Wypisuje drzewko kategorii (prosto, z wcięciami).
        """
        def dump(node: Category, level: int = 0):
            click.echo("  " * level + f"- {node.name} (id={node.id})")
            for child in sorted(node.children, key=lambda c: c.name.lower()):
                dump(child, level + 1)

        roots = Category.query.filter_by(parent_id=None).all()
        if not roots:
            click.echo("Brak kategorii. Użyj: flask --app run.py seed-categories --defaults")
            return
        for r in sorted(roots, key=lambda c: c.name.lower()):
            dump(r)
