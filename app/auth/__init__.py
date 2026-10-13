from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..db import db
from ..models import User
from .forms import LoginForm, RegisterForm

bp = Blueprint("auth", __name__)


def _has_users() -> bool:
    return db.session.query(User.id).first() is not None


def _safe_next(target: str | None) -> str:
    if target and not urlparse(target).netloc and target.startswith("/"):
        return target
    return url_for("documents.shell")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("documents.shell"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Usuario ou senha invalidos.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            return redirect(_safe_next(request.args.get("next")))
    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("documents.shell"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash("Ja existe uma conta com esse usuario.", "warning")
        else:
            user = User(username=username)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Conta criada. Bem-vindo!", "success")
            return redirect(url_for("documents.shell"))
    return render_template("auth/register.html", form=form)


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Primeiro uso: cria o administrador inicial quando o banco nao tem usuarios."""
    if _has_users():
        return redirect(url_for("auth.login"))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data.strip())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Administrador criado. A base de conhecimento está pronta para uso.", "success")
        return redirect(url_for("documents.shell"))
    return render_template("auth/setup.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Voce saiu da sua conta.", "info")
    return redirect(url_for("auth.login"))
