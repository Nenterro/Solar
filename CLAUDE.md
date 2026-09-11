# Solar

Live telemetry and history for an off-grid solar setup: inverters over
RS232/RS485, a BMS, and the DESSMonitor cloud API. React + Vite frontend, a
Python service on the home server doing the polling.

## Where things live, and how they ship

Two halves, two completely separate deployment paths. Confusing them is how a
fix gets written, tested, committed — and never actually goes live.

### Frontend — this repo

Everything here is frontend: `src/`, `public/`, `index.html`, the Vite and
Vercel config.

- Worked on locally, on the dev machine.
- Committed and pushed to `main` on GitHub.
- **Vercel watches `main` and deploys from it.** Pushing is the deploy.

A frontend change is not live until it is pushed.

### Backend — the home server only

The Python telemetry service does not live here and is not in version control.
It lives at `~/Docker/solar-new/backend` on the home server, is a service in
`~/Docker/docker-compose.yml`, and is edited in place over SSH.

It needs the hardware: the container runs `privileged` with `/dev` mapped in,
because it talks to USB HID and serial adapters directly. It cannot run
anywhere but that machine, which is the real reason it does not belong here.

A backend change is not live until the container restarts. Pushing to GitHub
does nothing for it — there is nothing here to push.

**Do not add backend code to this repo.** `/backend/` is in `.gitignore` for
that reason. It was tracked here until September 2026 — 139 files, most of the
repo — which meant one service with two copies and nothing keeping them in
step.

## Working on the backend

The SSH address, paths and commands are in **`CLAUDE.local.md`**, gitignored
because this repo is public. It loads automatically alongside this file. If it
is missing — fresh clone, different machine — ask rather than guessing.

The backend directory is **bind-mounted** into the container
(`./solar-new/backend:/app`), so Python changes need only a restart:

```bash
cd ~/Docker && docker compose restart solar-backend
```

`--build` is only for `requirements.txt` changes. That is the opposite of the
budget app's ingest service, which bakes its code in and does need rebuilding.

`solar.db` (SQLite, all the history) sits in that same bind-mounted directory,
so it survives restarts and rebuilds. Be careful with anything that writes to
the backend directory in bulk.

## This repo

```bash
npm run dev
npx vite build
```

- The repo is **public**. No secrets, tokens, internal addresses or
  server-side config in committed files.
- The frontend reads the backend over HTTPS through the home server's reverse
  proxy — see `CLAUDE.local.md` for the hostname and routing.
