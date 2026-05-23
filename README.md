# 🐙 GitHub Mass Cloner

Clona repositorios de GitHub en masa — personales, de organizaciones, o uno específico por URL — con un solo comando.

---

## Requisitos

- Python 3.10+
- Git instalado y accesible en el `PATH`
- Librería `requests`

```bash
pip install requests
```

---

## Tokens de GitHub

El script maneja **tres tokens independientes**, uno por cada modo. Puedes usar el mismo para todos o tokens distintos según tus permisos.

| Token | Variable de entorno | Para qué |
|---|---|---|
| Personal | `GITHUB_TOKEN` | Clonar tus repos privados y públicos |
| Organización | `GITHUB_ORG_TOKEN` | Acceder a repos de una organización |
| Repo específico | `GITHUB_REPO_TOKEN` | Clonar un repo puntual por URL o `owner/repo` |

> Si solo defines `GITHUB_TOKEN`, los otros dos lo usan como fallback automáticamente.

Crea tus tokens en: **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**

Permisos recomendados:
- `repo` — repos privados
- `read:org` — repos de organizaciones

---

## Uso

### Modo interactivo (sin argumentos)

Ejecuta el script sin nada y te guía paso a paso, preguntando los tres tokens y qué quieres clonar:

```bash
python github-clone-repo.py
```

Ejemplo de sesión interactiva:

```
🐙  GitHub Mass Cloner — Modo interactivo
─────────────────────────────────────────────

🔑  TOKENS DE ACCESO

   Token personal (repos propios)         : ************
   Token de organización                  : ************
   Token para repo específico             : ************

📦  ¿QUÉ QUIERES CLONAR?

   ¿Clonar repos personales? [s/N]: s
   Organizaciones a clonar (separadas por coma, Enter para omitir): mi-empresa
   Repos específicos — 'owner/repo' o URL (separados por coma, Enter para omitir): torvalds/linux

   📂 Directorio destino [~/github_backup]:
```

---

### Por argumentos CLI

```bash
python github-clone-repo.py [opciones]
```

| Argumento | Corto | Descripción |
|---|---|---|
| `--token TOKEN` | `-t` | Token personal de GitHub |
| `--org-token TOKEN` | | Token para organizaciones |
| `--repo-token TOKEN` | | Token para repositorios específicos |
| `--personal` | `-p` | Clonar repos personales |
| `--orgs ORG1,ORG2` | `-o` | Organizaciones a clonar (separadas por coma) |
| `--repo OWNER/REPO` | `-r` | Repos específicos: `owner/repo` o URL completa (separados por coma) |
| `--dest DIRECTORIO` | `-d` | Carpeta destino (por defecto: `~/github_backup`) |
| `--no-report` | | No generar el reporte JSON al finalizar |

---

### Por variables de entorno

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export GITHUB_ORG_TOKEN="ghp_yyyyyyyyyyyy"
export GITHUB_REPO_TOKEN="ghp_zzzzzzzzzzzz"
export GITHUB_BACKUP_DIR="~/mis_repos"        # opcional
```

---

## Ejemplos

**Modo interactivo completo:**
```bash
python github-clone-repo.py
```

**Solo repos personales:**
```bash
python github-clone-repo.py --personal --token ghp_xxxx
```

**Solo una organización:**
```bash
python github-clone-repo.py --orgs mi-empresa --org-token ghp_yyyy
```

**Un repositorio específico por `owner/repo`:**
```bash
python github-clone-repo.py --repo torvalds/linux --repo-token ghp_zzzz
```

**Un repositorio específico por URL:**
```bash
python github-clone-repo.py --repo https://github.com/torvalds/linux --repo-token ghp_zzzz
```

**Varios repos específicos a la vez:**
```bash
python github-clone-repo.py --repo owner/repo1,owner/repo2,https://github.com/org/repo3
```

**Todo junto — personal + org + repo específico:**
```bash
python github-clone-repo.py \
  --personal --orgs org1,org2 --repo owner/repo \
  --token ghp_xxxx --org-token ghp_yyyy --repo-token ghp_zzzz \
  --dest ~/backups/github
```

**Con variables de entorno (sin escribir tokens):**
```bash
export GITHUB_TOKEN="ghp_xxxx"
export GITHUB_ORG_TOKEN="ghp_yyyy"
python github-clone-repo.py --personal --orgs mi-empresa
```

---

## Estructura de carpetas generada

```
~/github_backup/
├── personal/
│   ├── repo-1/
│   ├── repo-2/
│   └── ...
├── organizaciones/
│   ├── mi-empresa/
│   │   ├── proyecto-a/
│   │   └── ...
│   └── otra-org/
│       └── ...
├── especificos/
│   ├── linux/
│   └── ...
└── reporte.json
```

---

## Reporte JSON

Al finalizar se genera un `reporte.json` con la estructura de todo lo descargado. Puedes omitirlo con `--no-report`.

---

## Comportamiento al re-ejecutar

Si una carpeta de repositorio ya existe, el script hace `git pull` en lugar de clonar de nuevo. Puedes programarlo como tarea periódica para mantener todo actualizado.

---

## Seguridad

- **Nunca** escribas tokens directamente en el código.
- Usa variables de entorno o un gestor de secretos.
- En CI/CD almacena los tokens como variables secretas del pipeline.
- Los tokens se inyectan en la URL HTTPS solo en memoria, nunca se escriben en disco.
