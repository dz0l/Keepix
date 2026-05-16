# Keepix

Deploy and operate the Keepix catalogue application on your own server.

---

## Requirements

- **OS:** Ubuntu Server 24 recommended (scripts target apt-based hosts).
- **Access:** Root or sudo; ability to bind the chosen HTTP port (default **80**).

---

## Install

Remote script (recommended):

```bash
curl -fsSL https://raw.githubusercontent.com/dz0l/Keepix/master/install.sh | sudo bash
```

Creates `/opt/keepix` by default (`KEEPIX_INSTALL_DIR`), installs Docker where needed, writes `.env` (generated `SECRET_KEY` and PostgreSQL credentials), configures `ALLOWED_HOSTS`, and starts Compose.

Equivalent using a cloned tree:

```bash
sudo git clone https://github.com/dz0l/Keepix.git /opt/keepix
sudo bash /opt/keepix/scripts/install_docker.sh /opt/keepix
```

First admin (`-it` is required so the password prompt works):

```bash
cd /opt/keepix
docker compose exec -it app python manage.py create_staff_user admin --role admin
```

Browse to `http://<server-ip>/accounts/login/` (replace host/port if you changed mapping).

---

## Update

```bash
sudo bash /opt/keepix/scripts/update_docker.sh /opt/keepix
```

Runs `git pull`, reconciles LAN IP into `ALLOWED_HOSTS`, and rebuilds/redploys Compose.

---

## Install-time overrides

Exported in the shell before `curl … | bash` or `scripts/install_docker.sh`:

| Variable | Meaning |
|---------|---------|
| `KEEPIX_INSTALL_DIR` | Install directory (default `/opt/keepix`) |
| `REPO_URL` | Clone URL used when the directory does not exist yet |
| `KEEPIX_APP_PORT` | Host TCP port nginx listens on (default `80`) |
| `KEEPIX_ALLOWED_HOSTS` | Comma-separated hostnames/IPs (`localhost`, primary IPv4, etc.) |
| `KEEPIX_DB_NAME`, `KEEPIX_DB_USER`, `KEEPIX_DB_PASSWORD`, `KEEPIX_SECRET_KEY` | Explicit secrets instead of installer-generated defaults |
| `KEEPIX_INTERACTIVE` | Set `1` for interactive prompts vs fully automatic installer |
| `KEEPIX_DEBUG` | Prefer `0` in production |

Host port override example:

```bash
sudo KEEPIX_APP_PORT=8080 bash -c 'curl -fsSL https://raw.githubusercontent.com/dz0l/Keepix/master/install.sh | bash'
```

---

## Management commands (`manage.py`)

From `/opt/keepix`:

```bash
docker compose exec app python manage.py <command>
```

Attach a TTY when the command prompts for input:

```bash
docker compose exec -it app python manage.py ...
```

| Command | Description |
|---------|-------------|
| `create_staff_user <username> --role admin\|user` | Creates a user (hidden password on TTY, or `KEEPIX_NEW_USER_PASSWORD` for non‑TTY flows). `--email` optional. |
| `list_deleted` | Prints deleted catalogue records to stdout (not exposed in UI). |
| `scan` | Prints CPU/memory/disk overview for operators via SSH. |
| `backup_db_auto` | Gzipped `pg_dump` into `BACKUP_DB_ROOT`; keeps the newest `BACKUP_DB_KEEP_LAST` files. |
| `backup_full` | Single `.tar.gz` with gzipped SQL dump and the whole `media/` tree (written to `BACKUP_FULL_ROOT` by default). Optional `--output /path/archive.tar.gz`. |

---

## Cron idea (automatic DB snapshots)

Adjust path as needed:

```cron
30 3 */10 * * root cd /opt/keepix && docker compose exec -T app python manage.py backup_db_auto >> /var/log/keepix_backup.log 2>&1
```

Run `backup_full` before major upgrades or when copying the server off-site. Restore: extract the archive, restore `media/`, then import `database.sql.gz` into PostgreSQL.

---

## Security

**Do not put account passwords on the CLI** — argv is visible via `ps` and may end up in shell history. Keepix exposes only `username`/`--role`; passwords use `getpass` with `docker compose exec -it …`, or `KEEPIX_NEW_USER_PASSWORD` for scripted runs (privileged environments only).

The installer stores database credentials exclusively in filesystem `.env` with restricted permissions—not in install URLs.

---

## Health probes

| Path | Purpose |
|------|---------|
| `/health/live/` | Process is alive. |
| `/health/ready/` | Alive and PostgreSQL answers `SELECT 1`. |

Served behind nginx on the published HTTP listener.

---

## Environment file template

Variables are enumerated in `.env.example`. Generated `.env` is created by the installers and **must stay out of Git**.

---

## Runtime layout (Compose)

| Service | Role |
|---------|------|
| `db` | PostgreSQL 16 |
| `app` | Gunicorn plus migrations/`collectstatic` on boot |
| `nginx` | Static assets proxy, Django upstream, `/internal-media/` internal offload for gated downloads |

Uploaded files reach clients only once Django authorizes access.

---

## Continuous integration

`.github/workflows/ci.yml` verifies `docker compose config` against a sanitized dummy `.env`.
