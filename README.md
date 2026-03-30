# TelePDF

Local-first web app for archiving every PDF from a public Telegram source to a folder on your machine.

TelePDF is designed for people who want a self-hosted, personal archiver:

- sign in with their own Telegram account
- point the app at a public channel or account
- download every PDF into a local folder
- keep a CSV index for later search or processing

It is intentionally not a hosted SaaS product. The Telegram session, saved files, and local state stay on the user's machine.

## Why this exists

Some Telegram channels operate as document libraries. Legal channels, research feeds, public circulars, and publication archives often contain hundreds or thousands of PDF files. Downloading them manually is slow and error-prone.

TelePDF turns that into a simple local workflow.

## Features

- local-only web UI on `127.0.0.1`
- Telegram user-session login through `Telethon`
- accepts `@username` or `https://t.me/username`
- downloads every PDF attachment from the source
- avoids re-downloading the same Telegram message for the same output folder
- writes `telegram_pdf_index.csv` with message metadata
- works well as a base for later indexing or knowledge workflows

## Security model

- Your `api_id` and phone number are stored locally under `~/.telepdf` by default.
- Your `api_hash` is stored in the system secure store through `keyring`.
- New Telegram sessions are stored through the secure store when possible.
- Legacy local session files are still recognized so existing installs do not break immediately.
- You can override that location with the `TELEPDF_HOME` environment variable if you want a custom storage path.
- The repository ignores `data/` by default via `.gitignore` in case you choose a project-local runtime directory.
- This app should be run by the person who owns the Telegram account being used.
- Do not publish your local `data/` directory or session files.

## Requirements

- Python `3.9+`
- Telegram API credentials from `https://my.telegram.org`

## Quick start

### 1. Clone the repo

```bash
git clone https://github.com/Khxxxxd/telepdf.git
cd telepdf
```

### 2. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 3. Run the app

```bash
python3 -m telepdf
```

Then open:

```text
http://127.0.0.1:8000
```

## First-time setup

1. Go to `https://my.telegram.org`
2. Create a Telegram app
3. Copy your `api_id` and `api_hash`
4. Enter them in TelePDF with your phone number
5. Click `Send Telegram code`
6. Enter the code from Telegram
7. If your account uses 2FA, enter the password too

After that:

1. Enter a public source such as `@examplechannel`
2. Or enter `https://t.me/examplechannel`
3. Choose an output folder on your machine
4. Start the archive job

## Example use case

Archive a public legal channel into a local folder:

- Source: `https://t.me/kuwaitle`
- Output folder: `/Users/you/Documents/kuwait-laws`

The app will download PDFs into that folder and write:

```text
telegram_pdf_index.csv
```

## Project layout

```text
telepdf/
  README.md
  LICENSE
  requirements.txt
  pyproject.toml
  static/
  telepdf/
  tests/
```

## Local data

At runtime, the app creates this local storage directory by default:

```text
~/.telepdf/
  config.json
  auth_state.json
  ledger.json
```

If you want a different location:

```bash
TELEPDF_HOME=/path/to/telepdf-state python3 -m telepdf
```

The UI also includes:

- `Logout and clear local session`
- `Clear local app data`

These actions do not delete previously downloaded PDFs from your chosen output folder.

## Development

Run the app:

```bash
python3 -m telepdf --port 8000
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Open source publishing checklist

Before you publish your own fork:

- make sure `data/` is not committed
- remove any personal session files or local archives
- replace the example GitHub clone URL in this README
- add screenshots if you want a stronger project page
- choose your preferred license if MIT is not what you want

## License

MIT
