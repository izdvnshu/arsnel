<p align="center">
  <img src="docs/banner.svg" alt="ARSNEL" width="100%">
</p>

<h1 align="center"><code>ARSNEL</code></h1>

<p align="center"><code>local-first automation for your files, resumes and meetings.</code></p>

<p align="center">
  <img alt="python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-0A0A0A?style=flat-square&labelColor=0A0A0A&color=4169E1">
  <img alt="license MIT" src="https://img.shields.io/badge/license-MIT-0A0A0A?style=flat-square&labelColor=0A0A0A&color=4169E1">
</p>

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

ARSNEL is one Python toolkit with three modules behind a single command and a single config file:

- `arsnel organize` watches a folder and sorts files into category subfolders. It can also flag exact duplicates.
- `arsnel resume` compares a resume to a job description and returns missing keywords, tailored bullets and a match score.
- `arsnel notes` turns a meeting transcript into a summary and a numbered action list.

The two language features use a model running on your own computer through [ollama](https://ollama.com). Nothing is sent anywhere.

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Install

You need Python 3.11+, git and ollama. All are free. Install [ollama](https://ollama.com) first, then paste the block for your system.

### One command

**Windows (PowerShell script block)**

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/YOUR_USERNAME/arsnel/main/scripts/install.ps1)))
```

**Linux / macOS**

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/arsnel/main/scripts/install.sh)"
```

The installer creates a virtual environment in `~/.arsnel`, puts an `arsnel` launcher on your PATH, and pulls the default model if ollama is present. It never uses `sudo` or administrator rights, and it only accepts `https://` repositories. It works for public repositories.

Pin a release for a repeatable install, using the same tag in the URL and in `ARSNEL_REF`:

```powershell
$env:ARSNEL_REF = 'v0.1.0'
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/unfotable/arsnel/v0.1.0/scripts/install.ps1)))
```

```bash
ARSNEL_REF=v0.1.0 bash -c "$(curl -fsSL https://raw.githubusercontent.com/unfotable/arsnel/v0.1.0/scripts/install.sh)"
```

Prefer to read it first? Download, review, then run:

```powershell
irm https://raw.githubusercontent.com/unfotable/arsnel/main/scripts/install.ps1 -OutFile install.ps1
notepad install.ps1
.\install.ps1
```

```bash
curl -fsSLO https://raw.githubusercontent.com/unfotable/arsnel/main/scripts/install.sh
less install.sh
bash install.sh
```

Options (environment variables): `ARSNEL_REF`, `ARSNEL_MODEL`, `ARSNEL_SKIP_MODEL=1`, and `ARSNEL_DRY_RUN=1` to print every step without changing anything.

To uninstall, delete the `~/.arsnel` folder, and on Linux/macOS also `~/.local/bin/arsnel`. On Windows, remove `%USERPROFILE%\.arsnel\bin` from your user PATH.

### Manual install

**Linux / macOS**

```bash
set -e
git clone https://github.com/unfotable/arsnel.git
cd arsnel
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install .
ollama pull llama3.2
arsnel init
arsnel --help
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/unfotable/arsnel.git
cd arsnel
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install .
ollama pull llama3.2
arsnel init
arsnel --help
```

If PowerShell refuses to activate the environment, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

The install happens inside a virtual environment, so it never touches your system Python. Check that ollama is running with `curl http://localhost:11434` (it answers `Ollama is running`; on Windows use `curl.exe`).

Global options go before the command: `arsnel --config ~/my.yaml notes standup.txt`.

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Organizer

Sorts a folder (default: your Downloads) into category subfolders using the file extension, then refines the result with filename hints such as `Screenshot...`, `invoice...` or `cv...`. Compound extensions like `.tar.gz` are handled, and name collisions become `name (1).ext` instead of overwriting.

```bash
arsnel organize --once --dry-run   # preview only, nothing moves
arsnel organize --once             # sort what is there, then exit
arsnel organize                    # sort, then keep watching for new files
```

Terminal blocks in this README show representative output.

Files that are still downloading (`.crdownload`, `.part`, ...) are left alone, and new files are only moved after they stop changing. Existing files are shown to you first and moved only after you confirm (`--yes` skips the prompt).

```text
$ arsnel organize ~/Downloads --once --dry-run
ARSNEL · organize  /home/you/Downloads
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
Planned moves (4)
·········································································
: File                               : Destination          : Rule      :
·········································································
: Screenshot 2026-11-04 at 09.12.png : Images/Screenshots/  : filename  :
: invoice_october.pdf                : Documents/Finance/   : filename  :
: lecture-07-slides.pptx             : Presentations/       : extension :
: backup-2026.tar.gz                 : Archives/            : extension :
·········································································
Dry run: no files were moved.
```

Watch mode:

```text
$ arsnel organize
ARSNEL · organize  /home/you/Downloads
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
Move these files? [y/N]: y
4 moved
Watching /home/you/Downloads. Press Ctrl+C to stop.
moved resume_final_v3.pdf  ->  Documents/Career/
moved holiday.mov  ->  Videos/
```

### Duplicate finder

`--find-duplicates` groups files by size, then confirms matches with SHA-256, so only plausible candidates are read. It reports and never deletes.

```text
$ arsnel organize --find-duplicates
ARSNEL · organize  /home/you/Downloads
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
·····················································
: # : Size     : SHA-256      : Files               :
·····················································
: 1 : 4.2 MB   : 9f2c1ab07d3e : Images/trip.jpg     :
:   :          :              : Backup/trip (1).jpg :
: 2 : 310.0 KB : e3b0c44298fc : Documents/form.pdf  :
:   :          :              : form.pdf            :
·····················································
2 groups · 2 redundant files · 4.5 MB reclaimable
Nothing was deleted. Review the list and remove copies yourself.
```

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Resume

Takes a resume (`.txt`, `.md`, `.pdf` or `.docx`) and a job description (a file with `--jd`, or paste it when prompted), then reports:

- **missing keywords** the job asks for that your resume does not contain
- a **tailored bullet-point rewrite** that only uses facts already in your resume
- a **match score**: the share of job keywords found in your resume

```bash
arsnel resume my_resume.pdf --jd job.txt
cat job.txt | arsnel resume my_resume.docx      # piped input works too
arsnel resume my_resume.pdf --jd job.txt -e     # also save a Markdown report
```

```text
$ arsnel resume my_resume.pdf --jd job.txt
ARSNEL · resume  my_resume.pdf
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
· · · · · · · · · · · · · · · · · · · · ·
:                                       :
: Match score                           :
: ████████████████████············  62% :
:                                       :
· · · · · · · · · · · · · · · · · · · · ·
··························
: Keyword      : Status  :
··························
: Kubernetes   : missing :
: Terraform    : missing :
: Python       : matched :
: PostgreSQL   : matched :
··························
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
: Tailored bullet points                                             :
:                                                                    :
: · Built and deployed REST services in Python backed by PostgreSQL, :
:   cutting report latency by 40%.                                   :
: · Containerised legacy jobs with Docker to simplify releases.      :
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
```

The model extracts the keywords and drafts the bullets. The score is computed in plain code from the keyword list, so it is repeatable and does not depend on a small model's arithmetic. Keywords your resume gives no honest basis for are listed separately instead of being worked into the bullets. Scanned PDFs need OCR first; ARSNEL reads text only.

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Notes

Takes a transcript from a file (`.txt`, `.md`, `.vtt`, `.srt`) or pasted text and returns a clean summary, key points and a numbered action-item list with owner and due date when the transcript states them. Long transcripts are split to fit the model's context and merged afterwards.

```bash
arsnel notes standup.txt
arsnel notes meeting.vtt --export --title "Weekly sync"
arsnel notes < transcript.txt -o notes.md
```

```text
$ arsnel notes standup.txt --export
ARSNEL · notes  standup.txt
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
:                                                         :
: Summary                                                 :
: The team agreed to ship v2 on Friday once QA signs off. :
:                                                         :
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · ·
····························································
: # : Action item                     : Owner  : Due       :
····························································
: 1 : Send release notes to customers : Priya  : Thursday  :
: 2 : Book the demo room              : -      : -         :
: 3 : Confirm QA sign-off             : Marcus : Wednesday :
····························································
saved /home/you/arsnel-output/notes-standup-20261105-093000.md
```

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Configuration

One file, `config.yaml`, shared by all modules. ARSNEL looks for it in this order: `--config`, `$ARSNEL_CONFIG`, `./config.yaml`, `~/.arsnel/config.yaml`. Every key is optional. See [`config.example.yaml`](config.example.yaml).

```yaml
organizer:
  watch_dir: ~/Downloads
  extra_extensions: { Ebooks: [.mobi, .azw] }
  filename_rules: [{ pattern: "^meeting", folder: "Work/Meetings" }]
llm:
  model: llama3.2          # any model you have pulled
output:
  format: markdown         # also save a .md file for resume and notes runs
  directory: ~/arsnel-output
```

Paths are handled with `pathlib`, so the same config works on Windows, macOS and Linux. A larger model (for example `ollama pull llama3.1:8b`, then `model: llama3.1:8b`) usually gives better rewrites and summaries than the small default, at the cost of speed.

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Why this is free forever

```text
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
: Everything runs on your machine.                         :
: No account. No API key. No telemetry. No subscription.   :
: After setup it keeps working with the network unplugged. :
· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · 
```

ARSNEL has no paid API, hosted service or account anywhere in its code. The only network access is the one-time download of Python packages and the ollama model. After that, the organizer, the resume tool and the notes tool run offline, and your resumes and meeting transcripts never leave your machine.

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Security

```text
· · · · · · · · · · · · · · · · · · · · · · · 
: Local only: model server on 127.0.0.1      :
: Read-only on everything it does not move   :
: Warns before sending text off this machine :
· · · · · · · · · · · · · · · · · · · · · · · 
```

- ollama listens on `127.0.0.1:11434` by default. Leave it that way; do not set `OLLAMA_HOST=0.0.0.0` on a shared network.
- If `llm.host` in your config points at another machine, ARSNEL prints a warning, because your resume and transcript text would travel there.
- The organizer only moves files inside the folder you give it, never deletes, and rejects folder rules containing `..` or absolute paths.
- Secrets live only in `.env` (see below). `config.yaml` is for settings and ARSNEL refuses to load it if it contains a key such as `api_key` or `token`, or a URL with a password.
- Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

### Secrets and `.env`

ARSNEL needs no API key. If you ever point `llm.host` at an auth-protected remote server, keep the key in a `.env` file:

```bash
cp .env.example .env
chmod 600 .env                     # Windows: not needed
# then edit .env and set ARSNEL_LLM_API_KEY=...
```

- `.env` is git-ignored (`.env.example` is the only variant that is committed). Real environment variables override the file.
- The key is read from the environment only, never from `config.yaml`, never printed, and never written to disk by ARSNEL.
- ARSNEL refuses to send a key over plain `http://` to anything other than this machine; use an `https://` host.
- ARSNEL warns if `.env` is readable by other users on Linux or macOS.

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Development

```bash
pip install -e ".[dev]"
pytest
```

The tests cover the organizer's sorting rules, the duplicate finder, config loading, the shared LLM wrapper, and the resume and notes logic (with a fake model, so no ollama is needed). GitHub Actions runs them on Linux, macOS and Windows on every push.

```text
scripts/            install.sh, install.ps1 (one-command installers)
arsnel/
  cli.py            typer CLI entrypoint
  config.py         shared config.yaml loader (rejects secrets)
  env.py            .env loader for secrets
  llm_client.py     the only place that talks to ollama
  ui.py             rich theme: royal blue, dotted boxes
  organizer/        categories, sorter, duplicates, watcher
  resume/           parser, analyzer
  notes/            summarizer
tests/
```

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## Roadmap

```text
· [x] organizer: extension and filename sorting
· [x] organizer: SHA-256 duplicate finder
· [x] resume: keyword gaps, bullet rewrite, match score
· [x] notes: summary, action items, Markdown export
· [ ] organizer: undo the last sort
· [ ] organizer: move duplicates to a review folder
· [ ] resume: cover-letter draft from the same inputs
· [ ] notes: speaker-aware action items
· [ ] optional local transcription for audio recordings
· [ ] publish to PyPI
```

<p align="center">· · · · · · · · · · · · · · · · · · · · · · · · · · · · · · </p>

## License

[MIT](LICENSE)
