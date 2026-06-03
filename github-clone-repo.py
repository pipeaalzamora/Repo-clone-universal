#!/usr/bin/env python3
"""
GitHub Cloner
Pide el token personal y el de organización, luego clona todo en ~/Documentos.
  - Repos personales  → ~/Documentos/github-personal/
  - Repos de org      → ~/Documentos/github-<nombre-org>/
"""

import os
import getpass
import subprocess
import requests


BASE_DIR = os.path.expanduser("~/Documentos")


# ─────────────────────────────────────────────
#  Helpers de API
# ─────────────────────────────────────────────

def get_all_pages(url: str, headers: dict) -> list:
    """Recorre todas las páginas paginadas de un endpoint de GitHub."""
    results = []
    while url:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        results.extend(r.json())
        url = r.links.get("next", {}).get("url")
    return results


def inject_token(clone_url: str, token: str) -> str:
    """Inserta el token en la URL HTTPS para clonar repos privados sin SSH."""
    return clone_url.replace("https://", f"https://{token}@")


def validate_token(token: str):
    """Valida el token y devuelve el login del usuario, o None si es inválido."""
    try:
        r = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}"},
        )
        r.raise_for_status()
        return r.json().get("login")
    except requests.HTTPError:
        return None


# ─────────────────────────────────────────────
#  Clonado
# ─────────────────────────────────────────────

def clone_or_pull(repo_url: str, dest_path: str) -> None:
    """Clona si la carpeta no existe, o hace pull si ya existe."""
    name = os.path.basename(dest_path)
    if os.path.exists(dest_path):
        print(f"    🔄  Actualizando  {name}")
        cmd = ["git", "-C", dest_path, "pull"]
    else:
        print(f"    ⬇️   Clonando      {name}")
        cmd = ["git", "clone", repo_url, dest_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ❌  Error: {result.stderr.strip()}")
    else:
        print(f"    ✅  OK")


def clone_personal(token: str) -> int:
    """Clona todos los repos personales en ~/Documentos/github-personal/."""
    dest = os.path.join(BASE_DIR, "github-personal")
    os.makedirs(dest, exist_ok=True)

    headers = {"Authorization": f"token {token}"}
    repos = get_all_pages(
        "https://api.github.com/user/repos?per_page=100&type=all",
        headers,
    )

    print(f"\n{'='*55}")
    print(f"📁  REPOS PERSONALES  ({len(repos)} encontrados)")
    print(f"    Destino: {dest}")
    print(f"{'='*55}\n")

    for repo in repos:
        tag = "🔒" if repo["private"] else "🌍"
        print(f"  {tag}  {repo['name']}")
        clone_or_pull(
            inject_token(repo["clone_url"], token),
            os.path.join(dest, repo["name"]),
        )

    return len(repos)


def clone_org(token: str, org_name: str) -> int:
    """Clona todos los repos de una organización en ~/Documentos/github-<org>/."""
    dest = os.path.join(BASE_DIR, f"github-{org_name}")
    os.makedirs(dest, exist_ok=True)

    headers = {"Authorization": f"token {token}"}
    try:
        repos = get_all_pages(
            f"https://api.github.com/orgs/{org_name}/repos?per_page=100&type=all",
            headers,
        )
    except requests.HTTPError as e:
        print(f"\n  ❌  No se pudo acceder a la organización '{org_name}': {e}")
        return 0

    print(f"\n{'='*55}")
    print(f"🏢  ORGANIZACIÓN: {org_name}  ({len(repos)} repos)")
    print(f"    Destino: {dest}")
    print(f"{'='*55}\n")

    for repo in repos:
        tag = "🔒" if repo["private"] else "🌍"
        print(f"  {tag}  {repo['name']}")
        clone_or_pull(
            inject_token(repo["clone_url"], token),
            os.path.join(dest, repo["name"]),
        )

    return len(repos)


def get_orgs(token: str) -> list[str]:
    """Devuelve la lista de organizaciones a las que pertenece el usuario."""
    headers = {"Authorization": f"token {token}"}
    try:
        orgs = get_all_pages(
            "https://api.github.com/user/orgs?per_page=100",
            headers,
        )
        return [o["login"] for o in orgs]
    except requests.HTTPError:
        return []


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main() -> None:
    print("\n🐙  GitHub Cloner")
    print("─" * 45)
    print("Deja en blanco y presiona Enter para omitir un token.\n")

    # ── Pedir tokens ────────────────────────────
    personal_token = getpass.getpass("🔑  Token personal (repos propios)     : ").strip() or None
    org_token      = getpass.getpass("🔑  Token de organización               : ").strip() or None

    if not personal_token and not org_token:
        print("\n❌  Debes proporcionar al menos un token.")
        return

    total = 0

    # ── Repos personales ────────────────────────
    if personal_token:
        username = validate_token(personal_token)
        if not username:
            print("\n❌  El token personal no es válido o no tiene permisos.")
            return
        print(f"\n✅  Token personal válido — usuario: {username}")
        total += clone_personal(personal_token)

    # ── Repos de organización ───────────────────
    if org_token:
        org_user = validate_token(org_token)
        if not org_user:
            print("\n❌  El token de organización no es válido.")
            return
        print(f"\n✅  Token de organización válido — usuario: {org_user}")

        # Detectar organizaciones disponibles con este token
        orgs = get_orgs(org_token)
        if not orgs:
            print("\n⚠️   No se encontraron organizaciones para ese token.")
        else:
            print(f"\n   Organizaciones encontradas: {', '.join(orgs)}\n")
            for org in orgs:
                total += clone_org(org_token, org)

    # ── Resumen ─────────────────────────────────
    print(f"\n{'='*55}")
    print(f"✅  ¡Listo! {total} repositorio(s) procesados en {BASE_DIR}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
