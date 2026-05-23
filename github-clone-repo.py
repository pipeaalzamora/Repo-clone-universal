#!/usr/bin/env python3
"""
GitHub Mass Cloner
Clona repositorios de GitHub:
  - Personales (públicos y privados)
  - De organización(es)
  - Uno específico por URL o "owner/repo"
Soporta configuración por argumentos CLI, variables de entorno o modo interactivo.
"""

import os
import sys
import json
import argparse
import subprocess
import getpass
import requests


# ─────────────────────────────────────────────
#  Utilidades de API
# ─────────────────────────────────────────────

def get_all_pages(url: str, headers: dict) -> list:
    """Recorre todas las páginas de un endpoint paginado de GitHub."""
    results = []
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        results.extend(response.json())
        url = response.links.get("next", {}).get("url")
    return results


def inject_token(clone_url: str, token: str) -> str:
    """Inyecta el token en la URL HTTPS para autenticación sin SSH."""
    return clone_url.replace("https://", f"https://{token}@")


def validate_token(token: str) -> dict | None:
    """Valida el token y devuelve la info del usuario autenticado, o None si falla."""
    headers = {"Authorization": f"token {token}"}
    try:
        r = requests.get("https://api.github.com/user", headers=headers)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError:
        return None


def resolve_repo_url(repo_ref: str, token: str) -> tuple[str, str]:
    """
    Dado 'owner/repo' o una URL completa de GitHub,
    devuelve (clone_url_con_token, nombre_del_repo).
    """
    # Normalizar: si viene como URL extraer owner/repo
    repo_ref = repo_ref.strip().rstrip("/")
    if repo_ref.startswith("https://github.com/"):
        repo_ref = repo_ref.replace("https://github.com/", "")
        if repo_ref.endswith(".git"):
            repo_ref = repo_ref[:-4]

    if "/" not in repo_ref:
        raise ValueError(f"Formato inválido: usa 'owner/repo' o la URL completa de GitHub.")

    owner, name = repo_ref.split("/", 1)
    headers = {"Authorization": f"token {token}"}
    r = requests.get(f"https://api.github.com/repos/{owner}/{name}", headers=headers)
    r.raise_for_status()
    data = r.json()
    return inject_token(data["clone_url"], token), data["name"]


# ─────────────────────────────────────────────
#  Git helpers
# ─────────────────────────────────────────────

def clone_or_pull(repo_url: str, dest_path: str) -> None:
    """Clona el repo si no existe, o hace git pull si ya existe."""
    if os.path.exists(dest_path):
        print(f"    🔄 Actualizando: {os.path.basename(dest_path)}")
        cmd = ["git", "-C", dest_path, "pull"]
    else:
        print(f"    ⬇️  Clonando:     {os.path.basename(dest_path)}")
        cmd = ["git", "clone", repo_url, dest_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ❌ Error: {result.stderr.strip()}")
    else:
        print(f"    ✅ OK")


# ─────────────────────────────────────────────
#  Modos de clonado
# ─────────────────────────────────────────────

def clone_personal(token: str, base_dir: str) -> int:
    """Clona todos los repos personales (públicos y privados) del usuario autenticado."""
    print("\n" + "=" * 55)
    print("📁  REPOSITORIOS PERSONALES")
    print("=" * 55)

    headers = {"Authorization": f"token {token}"}
    repos = get_all_pages(
        "https://api.github.com/user/repos?per_page=100&type=all",
        headers
    )

    dest_base = os.path.join(base_dir, "personal")
    os.makedirs(dest_base, exist_ok=True)
    print(f"   Encontrados: {len(repos)} repositorios\n")

    for repo in repos:
        visibility = "🔒 Privado" if repo["private"] else "🌍 Público"
        print(f"  {visibility} → {repo['name']}")
        clone_or_pull(
            inject_token(repo["clone_url"], token),
            os.path.join(dest_base, repo["name"])
        )

    return len(repos)


def clone_org(token: str, org_name: str, base_dir: str) -> int:
    """Clona todos los repos de una organización."""
    print("\n" + "=" * 55)
    print(f"🏢  ORGANIZACIÓN: {org_name}")
    print("=" * 55)

    headers = {"Authorization": f"token {token}"}
    try:
        repos = get_all_pages(
            f"https://api.github.com/orgs/{org_name}/repos?per_page=100&type=all",
            headers
        )
    except requests.HTTPError as e:
        print(f"   ❌ No se pudo acceder a la organización '{org_name}': {e}")
        return 0

    dest_base = os.path.join(base_dir, "organizaciones", org_name)
    os.makedirs(dest_base, exist_ok=True)
    print(f"   Encontrados: {len(repos)} repositorios\n")

    for repo in repos:
        visibility = "🔒 Privado" if repo["private"] else "🌍 Público"
        print(f"  {visibility} → {repo['name']}")
        clone_or_pull(
            inject_token(repo["clone_url"], token),
            os.path.join(dest_base, repo["name"])
        )

    return len(repos)


def clone_specific(token: str, repo_refs: list[str], base_dir: str) -> int:
    """Clona repositorios específicos dados como 'owner/repo' o URL de GitHub."""
    print("\n" + "=" * 55)
    print("🔗  REPOSITORIOS ESPECÍFICOS")
    print("=" * 55)

    dest_base = os.path.join(base_dir, "especificos")
    os.makedirs(dest_base, exist_ok=True)

    count = 0
    for ref in repo_refs:
        try:
            clone_url, name = resolve_repo_url(ref, token)
            print(f"  📦 {ref}")
            clone_or_pull(clone_url, os.path.join(dest_base, name))
            count += 1
        except (requests.HTTPError, ValueError) as e:
            print(f"  ❌ Error con '{ref}': {e}")

    return count


# ─────────────────────────────────────────────
#  Reporte
# ─────────────────────────────────────────────

def generate_report(base_dir: str) -> None:
    """Genera un reporte JSON con la estructura de lo descargado."""
    report = {}
    for root, dirs, _ in os.walk(base_dir):
        depth = root.replace(base_dir, "").count(os.sep)
        if depth <= 2:
            relative = os.path.relpath(root, base_dir)
            report[relative] = sorted(dirs)

    report_path = os.path.join(base_dir, "reporte.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n📊 Reporte guardado en: {report_path}")


# ─────────────────────────────────────────────
#  Modo interactivo
# ─────────────────────────────────────────────

def ask(prompt: str, secret: bool = False, default: str = "") -> str:
    """Pide un valor al usuario, opcionalmente ocultándolo."""
    if secret:
        value = getpass.getpass(prompt).strip()
    else:
        value = input(prompt).strip()
    return value if value else default


def interactive_mode() -> argparse.Namespace:
    """Solicita los datos al usuario de forma interactiva."""
    print("\n🐙  GitHub Mass Cloner — Modo interactivo")
    print("─" * 45)

    args = argparse.Namespace(
        token=None,
        org_token=None,
        repo_token=None,
        personal=False,
        orgs=[],
        repos=[],
        dest=os.path.expanduser("~/github_backup"),
        no_report=False,
    )

    # ── Tokens ──────────────────────────────────
    print("\n🔑  TOKENS DE ACCESO")
    print("   (Deja en blanco para omitir si no usas ese modo)\n")

    personal_token = os.environ.get("GITHUB_TOKEN") or ask(
        "   Token personal (repos propios)         : ", secret=True
    )
    args.token = personal_token or None

    org_token = os.environ.get("GITHUB_ORG_TOKEN") or ask(
        "   Token de organización                  : ", secret=True
    )
    args.org_token = org_token or None

    repo_token = os.environ.get("GITHUB_REPO_TOKEN") or ask(
        "   Token para repo específico             : ", secret=True
    )
    args.repo_token = repo_token or None

    # ── Qué clonar ──────────────────────────────
    print("\n📦  ¿QUÉ QUIERES CLONAR?")
    print("   Puedes activar una o varias opciones.\n")

    if args.token:
        resp = ask("   ¿Clonar repos personales? [s/N]: ").lower()
        args.personal = resp in ("s", "si", "sí", "y", "yes")

    if args.org_token or args.token:
        raw_orgs = ask(
            "   Organizaciones a clonar (separadas por coma, Enter para omitir): "
        )
        args.orgs = [o.strip() for o in raw_orgs.split(",") if o.strip()] if raw_orgs else []

    effective_repo_token = args.repo_token or args.token
    if effective_repo_token:
        raw_repos = ask(
            "   Repos específicos — 'owner/repo' o URL (separados por coma, Enter para omitir): "
        )
        args.repos = [r.strip() for r in raw_repos.split(",") if r.strip()] if raw_repos else []

    # ── Destino ─────────────────────────────────
    print()
    dest = ask(f"   📂 Directorio destino [{args.dest}]: ", default=args.dest)
    args.dest = os.path.expanduser(dest)

    return args


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-clone-repo",
        description="Clona en masa repositorios de GitHub (personal, organizaciones o repos específicos).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Variables de entorno soportadas:
  GITHUB_TOKEN        Token personal de GitHub
  GITHUB_ORG_TOKEN    Token para organizaciones
  GITHUB_REPO_TOKEN   Token para repositorios específicos
  GITHUB_BACKUP_DIR   Directorio destino por defecto

Ejemplos:
  # Modo interactivo
  python github-clone-repo.py

  # Solo repos personales
  python github-clone-repo.py --personal --token ghp_xxxx

  # Solo una organización
  python github-clone-repo.py --orgs mi-empresa --org-token ghp_yyyy

  # Repositorio específico
  python github-clone-repo.py --repo owner/repo --repo-token ghp_zzzz

  # Todo junto
  python github-clone-repo.py --personal --orgs org1,org2 --repo owner/repo \\
    --token ghp_xxxx --org-token ghp_yyyy --repo-token ghp_zzzz

  # Múltiples repos específicos
  python github-clone-repo.py --repo owner/repo1,owner/repo2,https://github.com/org/repo3
        """
    )

    parser.add_argument("--token", "-t",
        default=os.environ.get("GITHUB_TOKEN"), metavar="TOKEN",
        help="Token personal de GitHub.")
    parser.add_argument("--org-token",
        default=os.environ.get("GITHUB_ORG_TOKEN"), metavar="TOKEN",
        help="Token para organizaciones (si se omite, usa --token).")
    parser.add_argument("--repo-token",
        default=os.environ.get("GITHUB_REPO_TOKEN"), metavar="TOKEN",
        help="Token para repositorios específicos (si se omite, usa --token).")

    parser.add_argument("--personal", "-p",
        action="store_true",
        help="Clonar todos los repositorios personales.")
    parser.add_argument("--orgs", "-o",
        metavar="ORG1,ORG2,...",
        help="Organizaciones a clonar, separadas por comas.")
    parser.add_argument("--repo", "-r",
        metavar="OWNER/REPO,...",
        help="Repositorios específicos: 'owner/repo' o URL completa, separados por comas.")

    parser.add_argument("--dest", "-d",
        default=os.environ.get("GITHUB_BACKUP_DIR", os.path.expanduser("~/github_backup")),
        metavar="DIRECTORIO",
        help="Directorio destino (por defecto: ~/github_backup).")
    parser.add_argument("--no-report",
        action="store_true",
        help="Omitir la generación del reporte JSON.")

    return parser


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Detectar si se pasó algún argumento de acción
    has_action = args.personal or args.orgs or args.repo
    has_token  = args.token or args.org_token or args.repo_token

    if not has_action and not has_token and sys.stdin.isatty():
        args = interactive_mode()
    elif not has_action and not has_token:
        parser.print_help()
        sys.exit(0)

    # Normalizar listas
    orgs  = [o.strip() for o in args.orgs.split(",")  if o.strip()] if args.orgs  else []
    repos = [r.strip() for r in args.repo.split(",")  if r.strip()] if args.repo  else []

    # Tokens efectivos (fallback al personal si no se especifica otro)
    personal_token = args.token
    org_token      = args.org_token  or personal_token
    repo_token     = args.repo_token or personal_token

    # Validar token personal si se va a usar
    username = "—"
    if args.personal and not personal_token:
        personal_token = getpass.getpass("🔑 Token personal de GitHub: ").strip()
    if personal_token:
        user_info = validate_token(personal_token)
        if not user_info:
            print("❌ El token personal no es válido o no tiene permisos suficientes.")
            sys.exit(1)
        username = user_info.get("login", "desconocido")

    # Validar token de org si se va a usar y es distinto
    if orgs and org_token and org_token != personal_token:
        if not validate_token(org_token):
            print("❌ El token de organización no es válido.")
            sys.exit(1)

    # Validar token de repo específico si es distinto
    if repos and repo_token and repo_token != personal_token and repo_token != org_token:
        if not validate_token(repo_token):
            print("❌ El token para repositorios específicos no es válido.")
            sys.exit(1)

    base_dir = os.path.expanduser(args.dest)
    os.makedirs(base_dir, exist_ok=True)

    # Resumen
    print(f"\n🚀  GitHub Mass Cloner")
    print(f"    Usuario : {username}")
    print(f"    Destino : {base_dir}")
    if args.personal:  print(f"    Personal: ✅")
    if orgs:           print(f"    Orgs    : {', '.join(orgs)}")
    if repos:          print(f"    Repos   : {', '.join(repos)}")

    total = 0

    if args.personal and personal_token:
        total += clone_personal(personal_token, base_dir)

    for org in orgs:
        total += clone_org(org_token, org, base_dir)

    if repos:
        total += clone_specific(repo_token, repos, base_dir)

    if not args.no_report and total > 0:
        generate_report(base_dir)

    print(f"\n✅  ¡Listo! {total} repositorio(s) procesados en: {base_dir}\n")


if __name__ == "__main__":
    main()
